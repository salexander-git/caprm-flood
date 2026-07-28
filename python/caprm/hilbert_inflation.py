"""Aggregate the Hilbert query's per-property counter columns into the B3b
inflation result and the box-vs-disk gate decision.

This is an aggregation over the counter columns of a Hilbert output CSV. It is
deliberately NOT part of `compare_python_cpp_water.py`: that harness decides
agreement (is the answer right), this one decides cost (what exactness cost).

Counter semantics, all per property, all at the tight query radius
`R = d_best + L/2 + tie_tol`:

    n_true_r      entries whose NEAREST POINT satisfies the range predicate at
                  the answer radius `d_best + tie_tol`. Always >= 1. This is the
                  honest denominator: what an exact index would have to admit if
                  its entries had zero extent.
    n_disk_infl   midpoints in disk(R). What midpoint ordering FORCES the query
                  to admit for exactness over extended objects.
    n_disk_unc    midpoints in disk(d_best + L_uncapped/2 + tie_tol), the
                  counterfactual had B1 not split long segments. Zero when the
                  run did not request it.
    n_decomp      entries the range decomposition actually read
                  (`cpp_entries_scanned`). Exceeds n_disk_infl by the region
                  predicate's over-covering plus leaf-block overshoot.
    n_disk_r      B3a's intended denominator, retained and reported as
                  degenerate: it tests MIDPOINTS against a radius derived from a
                  SEGMENT distance, so it counts only the coincidence that a
                  perpendicular foot landed within tie_tol of its own midpoint.

Ratios reported:

    geometric inflation, capped     sum(n_disk_infl) / sum(n_true_r)
    geometric inflation, uncapped   sum(n_disk_unc)  / sum(n_true_r)
    what the B1 split bought        sum(n_disk_unc)  / sum(n_disk_infl)
    box-vs-disk indexing inflation  sum(n_decomp)    / sum(n_disk_infl)

Sum-of-numerator over sum-of-denominator is used for the headline (it is the
cost ratio of the whole workload). Per-property ratio percentiles are reported
alongside it because a mean can hide a tail, and the gate is decided on the
tail.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "property_id",
    "cpp_nearest_water_distance_m",
    "cpp_entries_scanned",
    "cpp_n_disk_r",
    "cpp_n_true_r",
    "cpp_n_disk_infl",
    "cpp_n_disk_unc",
    "cpp_seed_probes",
    "region_mode",
    "seed_mode",
    "verification_mode",
}

# Declared BEFORE measuring (Nucleus 18.12). The disk predicate is only built if
# the box predicate's over-covering exceeds this on the tail, not on the mean.
GATE_TAIL_PERCENTILE = 99.0
GATE_TAIL_RATIO_MAX = 3.0

PERCENTILES = (50.0, 90.0, 99.0, 99.9)


def require_columns(frame: pd.DataFrame, table_name: str) -> None:
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(
            f"{table_name} is missing required columns: {missing}. "
            "A pre-B3b Hilbert CSV cannot be summarized: it has no "
            "cpp_n_true_r column."
        )


def single_value(frame: pd.DataFrame, column: str, table_name: str) -> str:
    values = frame[column].astype("string").unique().tolist()
    if len(values) != 1:
        raise ValueError(
            f"{table_name} column {column} is not single-valued: {values}"
        )
    return str(values[0])


def describe_ratio(
    numerator: pd.Series,
    denominator: pd.Series,
) -> dict[str, Any]:
    """Aggregate ratio plus the per-property distribution.

    The aggregate is sum/sum, not the mean of per-property ratios: the question
    is what the workload cost, and a mean of ratios would weight a property that
    admitted two entries equally with one that admitted two thousand.
    """
    denominator_total = int(denominator.sum())
    numerator_total = int(numerator.sum())

    per_property = np.where(
        denominator.to_numpy() > 0,
        numerator.to_numpy() / np.maximum(denominator.to_numpy(), 1),
        np.nan,
    )
    finite = per_property[np.isfinite(per_property)]

    summary: dict[str, Any] = {
        "numerator_total": numerator_total,
        "denominator_total": denominator_total,
        "aggregate_ratio": (
            numerator_total / denominator_total
            if denominator_total
            else None
        ),
        "properties_with_zero_denominator": int(
            (denominator.to_numpy() <= 0).sum()
        ),
    }

    if finite.size:
        summary["per_property_mean"] = float(finite.mean())
        for percentile in PERCENTILES:
            summary[f"per_property_p{percentile:g}"] = float(
                np.percentile(finite, percentile)
            )
        summary["per_property_max"] = float(finite.max())

    return summary


def summarize_counters(
    frame: pd.DataFrame,
    table_name: str,
) -> dict[str, Any]:
    """Counter aggregation for one Hilbert output CSV."""
    require_columns(frame, table_name)

    if not frame["property_id"].is_unique:
        raise ValueError(f"{table_name} contains duplicate property IDs.")

    uncapped_measured = bool((frame["cpp_n_disk_unc"] > 0).any())

    summary: dict[str, Any] = {
        "table": table_name,
        "rows": int(len(frame)),
        "unique_property_ids": int(frame["property_id"].nunique()),
        "region_mode": single_value(frame, "region_mode", table_name),
        "seed_mode": single_value(frame, "seed_mode", table_name),
        "verification_mode": single_value(
            frame, "verification_mode", table_name
        ),
        "uncapped_counterfactual_measured": uncapped_measured,
        "totals": {
            "n_true_r": int(frame["cpp_n_true_r"].sum()),
            "n_disk_infl": int(frame["cpp_n_disk_infl"].sum()),
            "n_disk_unc": int(frame["cpp_n_disk_unc"].sum()),
            "n_decomp": int(frame["cpp_entries_scanned"].sum()),
            "n_disk_r": int(frame["cpp_n_disk_r"].sum()),
            "seed_probes": int(frame["cpp_seed_probes"].sum()),
        },
        "per_property_means": {
            "n_true_r": float(frame["cpp_n_true_r"].mean()),
            "n_disk_infl": float(frame["cpp_n_disk_infl"].mean()),
            "n_disk_unc": float(frame["cpp_n_disk_unc"].mean()),
            "n_decomp": float(frame["cpp_entries_scanned"].mean()),
            "seed_probes": float(frame["cpp_seed_probes"].mean()),
        },
    }

    # The provable per-property chain. Re-checked here on the delivered artifact
    # rather than trusted from the run that produced it.
    violations = {
        "n_disk_r_gt_n_true_r": int(
            (frame["cpp_n_disk_r"] > frame["cpp_n_true_r"]).sum()
        ),
        "n_true_r_lt_1": int((frame["cpp_n_true_r"] < 1).sum()),
        "n_true_r_gt_n_disk_infl": int(
            (frame["cpp_n_true_r"] > frame["cpp_n_disk_infl"]).sum()
        ),
        "n_disk_infl_gt_n_decomp": int(
            (frame["cpp_n_disk_infl"] > frame["cpp_entries_scanned"]).sum()
        ),
    }
    if uncapped_measured:
        violations["n_disk_unc_lt_n_disk_infl"] = int(
            (frame["cpp_n_disk_unc"] < frame["cpp_n_disk_infl"]).sum()
        )
    summary["ordering_violations"] = violations
    summary["ordering_holds"] = all(
        count == 0 for count in violations.values()
    )

    summary["geometric_inflation_capped"] = describe_ratio(
        frame["cpp_n_disk_infl"], frame["cpp_n_true_r"]
    )
    summary["box_vs_disk_inflation"] = describe_ratio(
        frame["cpp_entries_scanned"], frame["cpp_n_disk_infl"]
    )

    if uncapped_measured:
        summary["geometric_inflation_uncapped"] = describe_ratio(
            frame["cpp_n_disk_unc"], frame["cpp_n_true_r"]
        )
        summary["split_gain_uncapped_over_capped"] = describe_ratio(
            frame["cpp_n_disk_unc"], frame["cpp_n_disk_infl"]
        )

    # B3a's degenerate denominator, recorded as a measured fact so the next
    # chunk does not re-derive it or reuse it.
    nonzero = int((frame["cpp_n_disk_r"] > 0).sum())
    summary["degenerate_b3a_denominator"] = {
        "n_disk_r_total": int(frame["cpp_n_disk_r"].sum()),
        "properties_with_nonzero_n_disk_r": nonzero,
        "fraction_nonzero": nonzero / len(frame) if len(frame) else None,
    }

    return summary


def inflation_by_distance_decile(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Cost profile against distance to water.

    Inflation is a fixed metric addition to a radius, so its relative cost must
    fall as the answer distance grows. Reporting by decile shows whether the
    aggregate is carried by near-water properties, which a single mean hides.
    """
    require_columns(frame, "frame")
    working = frame.copy()
    working["decile"] = pd.qcut(
        working["cpp_nearest_water_distance_m"].rank(method="first"),
        10,
        labels=False,
    )

    rows: list[dict[str, Any]] = []
    for decile, group in working.groupby("decile", observed=True):
        true_total = int(group["cpp_n_true_r"].sum())
        infl_total = int(group["cpp_n_disk_infl"].sum())
        unc_total = int(group["cpp_n_disk_unc"].sum())
        rows.append({
            "decile": int(decile) + 1,
            "properties": int(len(group)),
            "distance_min_m": float(
                group["cpp_nearest_water_distance_m"].min()
            ),
            "distance_max_m": float(
                group["cpp_nearest_water_distance_m"].max()
            ),
            "mean_n_true_r": float(group["cpp_n_true_r"].mean()),
            "mean_n_disk_infl": float(group["cpp_n_disk_infl"].mean()),
            "mean_n_disk_unc": float(group["cpp_n_disk_unc"].mean()),
            "geometric_inflation_capped": (
                infl_total / true_total if true_total else None
            ),
            "geometric_inflation_uncapped": (
                unc_total / true_total if true_total else None
            ),
            "box_vs_disk_inflation": (
                int(group["cpp_entries_scanned"].sum()) / infl_total
                if infl_total
                else None
            ),
        })
    return rows


def box_vs_disk_gate(
    disk_bbox_summary: dict[str, Any],
    disk_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    """Decide whether to switch the tighter disk predicate on.

    The threshold is declared before measurement. The decision is taken on the
    tail, not the mean: the box predicate over-covers the disk by a bounded
    factor on average but the cost that matters is the worst properties.
    """
    key = f"per_property_p{GATE_TAIL_PERCENTILE:g}"
    box = disk_bbox_summary["box_vs_disk_inflation"]
    tail = box.get(key)

    gate: dict[str, Any] = {
        "threshold_percentile": GATE_TAIL_PERCENTILE,
        "threshold_ratio_max": GATE_TAIL_RATIO_MAX,
        "disk_bbox_aggregate_ratio": box["aggregate_ratio"],
        "disk_bbox_tail_ratio": tail,
        "disk_bbox_max_ratio": box.get("per_property_max"),
    }

    if disk_summary is not None:
        disk_box = disk_summary["box_vs_disk_inflation"]
        gate["disk_aggregate_ratio"] = disk_box["aggregate_ratio"]
        gate["disk_tail_ratio"] = disk_box.get(key)
        gate["disk_max_ratio"] = disk_box.get("per_property_max")
        if (
            disk_box["aggregate_ratio"] is not None
            and box["aggregate_ratio"] is not None
        ):
            gate["work_reduction_if_enabled"] = (
                box["aggregate_ratio"] / disk_box["aggregate_ratio"]
            )

    if tail is None:
        gate["verdict"] = "undetermined"
        gate["rationale"] = "No tail ratio available."
        return gate

    if tail <= GATE_TAIL_RATIO_MAX:
        gate["verdict"] = "disk_predicate_stays_off"
        gate["rationale"] = (
            f"Box-vs-disk over-covering at p{GATE_TAIL_PERCENTILE:g} is "
            f"{tail:.3f}x, within the {GATE_TAIL_RATIO_MAX:g}x threshold "
            "declared before measurement. The tighter disk predicate is not "
            "enabled: a clean negative result."
        )
    else:
        gate["verdict"] = "enable_disk_predicate"
        gate["rationale"] = (
            f"Box-vs-disk over-covering at p{GATE_TAIL_PERCENTILE:g} is "
            f"{tail:.3f}x, above the {GATE_TAIL_RATIO_MAX:g}x threshold. "
            "The disk predicate is the measured target for enabling."
        )
    return gate