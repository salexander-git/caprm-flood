from pathlib import Path

import pandas as pd


BASELINE_INPUT = Path("outputs/baseline/python_fema_membership.csv")
PROPERTIES_INPUT = Path("outputs/cpp_input/properties_projected.csv")
RINGS_INPUT = Path("outputs/cpp_input/fema_polygon_rings_joined_sample.csv")

PROPERTIES_OUTPUT = Path("outputs/cpp_input/properties_projected_dev.csv")
RINGS_OUTPUT = Path("outputs/cpp_input/fema_polygon_rings_dev.csv")

MAX_PROPERTIES = 25


def main() -> None:
    baseline = pd.read_csv(BASELINE_INPUT)
    properties = pd.read_csv(PROPERTIES_INPUT)

    # Keep a tiny but useful sample: some SFHA=True and some SFHA=False rows.
    sfha_rows = baseline[baseline["is_sfha"].astype(bool)].head(MAX_PROPERTIES // 2)
    non_sfha_rows = baseline[~baseline["is_sfha"].astype(bool)].head(
        MAX_PROPERTIES - len(sfha_rows)
    )

    dev_baseline = pd.concat([sfha_rows, non_sfha_rows], ignore_index=True)

    dev_property_ids = set(dev_baseline["property_id"].astype(str))
    dev_feature_indices = set(dev_baseline["fema_feature_index"].dropna().astype(int))

    dev_properties = properties[
        properties["property_id"].astype(str).isin(dev_property_ids)
    ].copy()

    # Preserve the same order as dev_baseline.
    order = {str(pid): i for i, pid in enumerate(dev_baseline["property_id"].astype(str))}
    dev_properties["__order"] = dev_properties["property_id"].astype(str).map(order)
    dev_properties = dev_properties.sort_values("__order").drop(columns=["__order"])

    print(f"Selected {len(dev_properties)} dev properties")
    print(f"Selected {len(dev_feature_indices)} matched FEMA feature indices")
    print(f"Feature indices: {sorted(dev_feature_indices)}")

    PROPERTIES_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    dev_properties.to_csv(PROPERTIES_OUTPUT, index=False)

    chunks = []
    for chunk in pd.read_csv(RINGS_INPUT, chunksize=250_000):
        keep = chunk["fema_feature_index"].astype(int).isin(dev_feature_indices)
        if keep.any():
            chunks.append(chunk[keep])

    if not chunks:
        raise RuntimeError("No matching FEMA ring rows found for dev fixture.")

    dev_rings = pd.concat(chunks, ignore_index=True)
    dev_rings.to_csv(RINGS_OUTPUT, index=False)

    print(f"Wrote {PROPERTIES_OUTPUT}")
    print(f"Wrote {RINGS_OUTPUT}")
    print(f"Dev ring vertices: {len(dev_rings)}")
    print(f"Dev ring file size bytes: {RINGS_OUTPUT.stat().st_size}")


if __name__ == "__main__":
    main()