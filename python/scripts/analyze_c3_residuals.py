"""C3. Where the C2 surrogate fails, and why.

    python python/scripts/analyze_c3_residuals.py

Reads only generated artifacts and modifies none of them. Nothing here trains,
retunes or re-selects an operating point.

Inputs
    outputs/training/supervised_dataset_v2.csv        coordinates, all 267,362
    outputs/training/supervised_dataset_v2_manifest.json
    outputs/index/property_exposure_index_countywide.csv   the four components
    outputs/training/c2_predictions_<partition>_seed<seed>.csv
    outputs/validation/c2_surrogate_manifest.json     the declared prediction
    outputs/splits/                                   optional, for the
                                                      distance-to-training
                                                      competitor

Writes
    outputs/validation/c3_error_analysis.json
    outputs/validation/c3_binned_<partition>.csv
    outputs/validation/c3_binned_majority_<partition>.csv
    outputs/validation/c3_class_decomposition_<partition>.csv
    outputs/validation/c3_competitors_<partition>.csv
    outputs/validation/c3_stratified_<partition>.csv
    outputs/validation/c3_bootstrap_<partition>.csv
    outputs/validation/c3_worst_cases_<partition>.csv
    outputs/training/c3_property_features.csv         the per-property geometry

The geometry is computed once over the full countywide property set, not over
the tested subset. A boundary is a property of the field; computing it from the
holdout alone would make the proxy depend on the partition, which is exactly the
confound the chunk exists to separate.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from caprm.error_analysis import (  # noqa: E402
    DEFAULT_COARSE_EDGES_M,
    DEFAULT_DISTANCE_EDGES_M,
    TOOL_VERSION,
    BootstrapConfig,
    bin_residuals,
    label_recovery,
    boundary_distance_by_class,
    class_decomposition,
    cluster_bootstrap_mean_abs,
    competitor_ranking,
    distance_to_convex_hull,
    distance_to_nearest_training,
    evaluate_prediction,
    local_neighbourhood_range,
    majority_class,
    stratified_table,
)
from caprm.surrogate_data import (  # noqa: E402
    PARTITION_BLOCKED,
    PARTITION_RANDOM,
    iter_splits,
    load_partition_inputs,
)

KEY = "property_id"
FEMA = "fema_component_0_100"
COMPONENTS = (
    FEMA,
    "water_component_0_100",
    "terrain_absolute_component_0_100",
    "terrain_relative_component_0_100",
)
LABEL = "exposure_index_0_100"
PARTITIONS = (PARTITION_BLOCKED, PARTITION_RANDOM)


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="C3 residual structure analysis")
    p.add_argument("--dataset", default="outputs/training/supervised_dataset_v2.csv")
    p.add_argument(
        "--dataset-manifest",
        default="outputs/training/supervised_dataset_v2_manifest.json",
    )
    p.add_argument("--index", default="outputs/index/property_exposure_index_countywide.csv")
    p.add_argument("--kfold-manifest", default="outputs/validation/c1_kfold_manifest.json")
    p.add_argument("--surrogate-manifest", default="outputs/validation/c2_surrogate_manifest.json")
    p.add_argument("--predictions-dir", default="outputs/training")
    p.add_argument("--split-dir", default="outputs/splits")
    p.add_argument(
        "--random-control-csv", default="outputs/splits/random_control_countywide.csv"
    )
    p.add_argument("--out-validation", default="outputs/validation")
    p.add_argument("--out-training", default="outputs/training")
    p.add_argument("--k-neighbours", type=int, default=9)
    p.add_argument("--bootstrap-resamples", type=int, default=200)
    p.add_argument("--bootstrap-seed", type=int, default=20260730)
    p.add_argument("--n-worst", type=int, default=25)
    p.add_argument(
        "--skip-training-distance",
        action="store_true",
        help="omit the distance-to-nearest-training competitor (it needs the C1 "
        "split files and costs one KD-tree per fold); recorded in the manifest "
        "so a run without it cannot be mistaken for a run with it",
    )
    return p.parse_args(argv)


def build_property_features(
    dataset: pd.DataFrame, index: pd.DataFrame, k: int
) -> pd.DataFrame:
    """The per-property geometry, computed once over all 267,362 properties."""
    merged = dataset.merge(index, on=KEY, how="inner", validate="one_to_one")
    if len(merged) != len(dataset):
        raise SystemExit(
            f"join dropped rows: dataset={len(dataset)} joined={len(merged)}; the "
            "index and the supervised dataset do not describe the same properties"
        )
    x = merged["x"].to_numpy(np.float64)
    y = merged["y"].to_numpy(np.float64)

    merged["fema_boundary_distance_m"] = boundary_distance_by_class(x, y, merged[FEMA].to_numpy())
    merged["county_edge_distance_m"] = distance_to_convex_hull(x, y)
    for column in COMPONENTS:
        merged[f"local_range__{column}"] = local_neighbourhood_range(
            x, y, merged[column].to_numpy(np.float64), k=k
        )
    return merged


def load_predictions(directory: Path, partition: str, seeds: list[int]) -> pd.DataFrame:
    frames = []
    for seed in seeds:
        path = directory / f"c2_predictions_{partition}_seed{seed}.csv"
        if not path.exists():
            raise SystemExit(f"missing prediction file: {path}")
        frame = pd.read_csv(path, dtype={KEY: str}, float_precision="round_trip")
        for column in (KEY, "x", "y", "fold", "actual", "predicted", "residual"):
            if column not in frame.columns:
                raise SystemExit(f"{path} missing column {column!r}")
        frame["seed"] = int(seed)
        frame["source_sha256"] = sha256_file(path)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def training_distance_column(
    inputs, partition: str, seeds: list[int], split_dir: Path,
    random_control_csv: Path, predictions: pd.DataFrame,
) -> np.ndarray:
    """Per test row, the distance to the nearest training property of ITS fold.

    Reconstructed through ``caprm.surrogate_data.iter_splits``, which is the same
    function C2 trained through, so these are C2's training sets and not a
    re-derivation that could differ.
    """
    row_of_property = {pid: i for i, pid in enumerate(inputs.property_id)}
    out = np.full(len(predictions), np.nan)
    key = list(zip(predictions["seed"].to_numpy(), predictions["fold"].to_numpy()))
    positions: dict[tuple[int, int], list[int]] = {}
    for row, k in enumerate(key):
        positions.setdefault((int(k[0]), int(k[1])), []).append(row)

    for seed in seeds:
        for split in iter_splits(inputs, partition, seed, split_dir, random_control_csv):
            rows = positions.get((int(seed), int(split.fold)))
            if not rows:
                continue
            rows_array = np.asarray(rows, dtype=np.int64)
            wanted = predictions[KEY].to_numpy()[rows_array]
            query_index = np.fromiter(
                (row_of_property[p] for p in wanted), dtype=np.int64, count=wanted.size
            )
            out[rows_array] = distance_to_nearest_training(
                inputs.x, inputs.y, split.train_index, query_index
            )
    return out


def analyse_partition(
    tested: pd.DataFrame, majority_value: float, args: argparse.Namespace
) -> dict[str, Any]:
    """Every table for one partition, pooled and per seed."""
    is_majority = tested[FEMA].to_numpy() == majority_value
    majority = tested[is_majority]

    distance = tested["fema_boundary_distance_m"].to_numpy()
    residual = tested["residual"].to_numpy()
    actual = tested["actual"].to_numpy()

    binned_all = bin_residuals(distance, residual, actual, DEFAULT_DISTANCE_EDGES_M)
    binned_majority = bin_residuals(
        majority["fema_boundary_distance_m"].to_numpy(),
        majority["residual"].to_numpy(),
        majority["actual"].to_numpy(),
        DEFAULT_DISTANCE_EDGES_M,
    )
    classes = class_decomposition(tested[FEMA].to_numpy(), residual, actual)

    candidates = {
        "fema_boundary_distance_m": majority["fema_boundary_distance_m"].to_numpy(),
        "label_magnitude": majority["actual"].to_numpy(),
        "county_edge_distance_m": majority["county_edge_distance_m"].to_numpy(),
    }
    for column in COMPONENTS:
        candidates[f"local_range__{column}"] = majority[f"local_range__{column}"].to_numpy()
    if "training_distance_m" in majority.columns and majority["training_distance_m"].notna().any():
        candidates["training_distance_m"] = majority["training_distance_m"].to_numpy()

    ranking = competitor_ranking(
        candidates, majority["residual"].to_numpy(), majority["actual"].to_numpy()
    )

    mean_abs, counts = stratified_table(
        majority["fema_boundary_distance_m"].to_numpy(),
        majority["residual"].to_numpy(),
        majority["actual"].to_numpy(),
        edges=DEFAULT_COARSE_EDGES_M,
    )
    stratified = (
        mean_abs.stack().rename("mean_abs").to_frame()
        .join(counts.stack().rename("n"))
        .reset_index()
    )
    stratified["distance_bin"] = stratified["distance_bin"].astype(str)

    intervals = pd.IntervalIndex.from_breaks(list(DEFAULT_DISTANCE_EDGES_M), closed="left")
    group = pd.cut(
        majority["fema_boundary_distance_m"], bins=list(DEFAULT_DISTANCE_EDGES_M), right=False
    ).astype(str)
    bootstrap = cluster_bootstrap_mean_abs(
        group.to_numpy(),
        majority[KEY].to_numpy(),
        majority["residual"].to_numpy(),
        BootstrapConfig(n_resamples=args.bootstrap_resamples, seed=args.bootstrap_seed),
    )
    # first-appearance order is an artifact of row order; the table is read
    # left to right by distance and is written that way
    bootstrap = (
        bootstrap.set_index("group")
        .reindex([str(i) for i in intervals])
        .rename_axis("group")
        .reset_index()
    )

    per_seed = []
    for seed, chunk in tested.groupby("seed"):
        chunk_majority = chunk[chunk[FEMA].to_numpy() == majority_value]
        near = chunk_majority[chunk_majority["fema_boundary_distance_m"] < 100.0]
        far = chunk_majority[chunk_majority["fema_boundary_distance_m"] >= 3200.0]
        minority = chunk[chunk[FEMA].to_numpy() != majority_value]
        per_seed.append(
            {
                "seed": int(seed),
                "n_test_rows": int(len(chunk)),
                "rmse": float(np.sqrt(np.mean(chunk["residual"].to_numpy() ** 2))),
                "majority_mean_abs_within_100m": float(near["residual"].abs().mean())
                if len(near) else float("nan"),
                "n_within_100m": int(len(near)),
                "majority_mean_abs_beyond_3200m": float(far["residual"].abs().mean())
                if len(far) else float("nan"),
                "n_beyond_3200m": int(len(far)),
                "minority_mean_abs": float(minority["residual"].abs().mean())
                if len(minority) else float("nan"),
                "n_minority": int(len(minority)),
            }
        )

    worst = (
        tested.assign(abs_residual=tested["residual"].abs())
        .nlargest(args.n_worst, "abs_residual")
        [[KEY, "seed", "fold", "x", "y", FEMA, "water_component_0_100",
          "fema_boundary_distance_m", "actual", "predicted", "residual", "abs_residual"]]
    )

    verdict = evaluate_prediction(binned_majority, classes, ranking, majority_value)
    recovery = label_recovery(binned_majority)
    return {
        "label_recovery": recovery,
        "tables": {
            "binned": binned_all,
            "binned_majority": binned_majority,
            "class_decomposition": classes,
            "competitors": ranking,
            "stratified": stratified,
            "bootstrap": bootstrap,
            "worst_cases": worst,
        },
        "per_seed": per_seed,
        "verdict": verdict,
        "n_test_rows": int(len(tested)),
        "n_unique_properties": int(tested[KEY].nunique()),
        "n_majority_rows": int(is_majority.sum()),
        "majority_row_share": float(is_majority.mean()),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_validation = Path(args.out_validation)
    out_training = Path(args.out_training)
    out_validation.mkdir(parents=True, exist_ok=True)
    out_training.mkdir(parents=True, exist_ok=True)

    dataset_path, index_path = Path(args.dataset), Path(args.index)
    dataset_manifest = json.loads(Path(args.dataset_manifest).read_text(encoding="utf-8"))
    surrogate_manifest = json.loads(Path(args.surrogate_manifest).read_text(encoding="utf-8"))

    # provenance before analysis: an input that is not the one the manifest
    # describes makes every number below a statement about a different file
    index_sha = sha256_file(index_path)
    expected_index_sha = dataset_manifest["verification"]["index_sha256"]
    if index_sha != expected_index_sha:
        raise SystemExit(
            f"{index_path} sha256={index_sha} but supervised_dataset_v2_manifest.json "
            f"records {expected_index_sha}; refusing to analyse a different index"
        )
    dataset_sha = sha256_file(dataset_path)
    expected_dataset_sha = dataset_manifest["output_sha256"]
    if dataset_sha != expected_dataset_sha:
        raise SystemExit(
            f"{dataset_path} sha256={dataset_sha} but its manifest records "
            f"{expected_dataset_sha}"
        )

    inputs = load_partition_inputs(dataset_path, args.kfold_manifest)
    seeds = [int(s) for s in surrogate_manifest["inputs"]["seeds"]]

    dataset = pd.read_csv(dataset_path, dtype={KEY: str}, float_precision="round_trip")
    index = pd.read_csv(index_path, dtype={KEY: str}, float_precision="round_trip")[
        [KEY, *COMPONENTS]
    ]
    features = build_property_features(dataset, index, args.k_neighbours)
    features.to_csv(
        out_training / "c3_property_features.csv", index=False,
        lineterminator="\n", float_format="%.17g",
    )

    majority_value, majority_count, majority_share = majority_class(features[FEMA].to_numpy())
    base_rates = (
        features[FEMA].value_counts().sort_index().rename("n").to_frame()
        .assign(share=lambda f: f["n"] / len(features))
    )

    results: dict[str, Any] = {}
    for partition in PARTITIONS:
        predictions = load_predictions(Path(args.predictions_dir), partition, seeds)
        tested = predictions.merge(
            features.drop(columns=["x", "y"]), on=KEY, how="left", validate="many_to_one"
        )
        missing = int(tested[FEMA].isna().sum())
        if missing:
            raise SystemExit(
                f"{missing} predicted rows have no property in the feature table; "
                "the prediction files and the index describe different properties"
            )
        if not args.skip_training_distance:
            tested["training_distance_m"] = training_distance_column(
                inputs, partition, seeds, Path(args.split_dir),
                Path(args.random_control_csv), tested,
            )

        analysis = analyse_partition(tested, majority_value, args)
        for name, frame in analysis.pop("tables").items():
            frame.to_csv(
                out_validation / f"c3_{name}_{partition}.csv", index=False,
                lineterminator="\n", float_format="%.10g",
            )
        analysis["prediction_sources"] = sorted(predictions["source_sha256"].unique().tolist())
        analysis["training_distance_computed"] = not args.skip_training_distance
        results[partition] = analysis

    manifest = {
        "task": "C3_error_analysis",
        "schema_version": "c3_error_analysis_v1",
        "tool_version": TOOL_VERSION,
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "crs": "EPSG:26918",
        "inputs": {
            "dataset": str(dataset_path),
            "dataset_sha256": dataset_sha,
            "index": str(index_path),
            "index_sha256": index_sha,
            "surrogate_manifest": str(args.surrogate_manifest),
            "surrogate_manifest_sha256": sha256_file(Path(args.surrogate_manifest)),
            "seeds": seeds,
        },
        "declared_prediction": surrogate_manifest.get("declared_prediction_for_c3"),
        "configuration": {
            "distance_edges_m": [None if np.isinf(e) else e for e in DEFAULT_DISTANCE_EDGES_M],
            "coarse_edges_m": [None if np.isinf(e) else e for e in DEFAULT_COARSE_EDGES_M],
            "k_neighbours": args.k_neighbours,
            "bootstrap_resamples": args.bootstrap_resamples,
            "bootstrap_seed": args.bootstrap_seed,
        },
        "base_rates": {
            "majority_class": majority_value,
            "majority_count": majority_count,
            "majority_share": majority_share,
            "per_class": {str(k): {"n": int(v["n"]), "share": float(v["share"])}
                          for k, v in base_rates.iterrows()},
            "n_properties": int(len(features)),
        },
        "boundary_proxy": {
            "definition": "distance to the nearest property carrying a different "
                          "FEMA component, per-class cKDTree",
            "limitations": [
                "bounded below by property spacing (C1 median nearest-neighbour "
                "distance 24.4 m), so a parcel on a polygon edge does not read 0",
                "locates a boundary only as precisely as the parcels sample it",
                "an SFHA polygon containing no parcels is invisible to it",
            ],
            "min_m": float(features["fema_boundary_distance_m"].min()),
            "median_m": float(features["fema_boundary_distance_m"].median()),
            "max_m": float(features["fema_boundary_distance_m"].max()),
        },
        "results": results,
    }
    path = out_validation / "c3_error_analysis.json"
    path.write_text(json.dumps(manifest, indent=2, default=float), encoding="utf-8")

    for partition in PARTITIONS:
        v = results[partition]["verdict"]
        print(f"{partition}: {v['verdict']}  "
              f"class_effect={v['class_effect']} "
              f"proximity_effect={v['proximity_effect']} "
              f"small_elsewhere={v['small_elsewhere']}")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())