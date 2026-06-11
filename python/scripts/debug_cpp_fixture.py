from pathlib import Path

import pandas as pd


PROPERTIES = Path("outputs/cpp_input/properties_projected_dev.csv")
RINGS = Path("outputs/cpp_input/fema_polygon_rings_dev.csv")
BASELINE = Path("outputs/baseline/python_fema_membership.csv")


def point_in_ring(x: float, y: float, ring: pd.DataFrame) -> bool:
    coords = list(zip(ring["x"], ring["y"]))

    if len(coords) < 4:
        return False

    inside = False
    j = len(coords) - 1

    for i in range(len(coords)):
        xi, yi = coords[i]
        xj, yj = coords[j]

        crosses = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi) + xi
        )

        if crosses:
            inside = not inside

        j = i

    return inside


def main() -> None:
    properties = pd.read_csv(PROPERTIES)
    rings = pd.read_csv(RINGS)
    baseline = pd.read_csv(BASELINE)

    baseline["property_id"] = baseline["property_id"].astype(str)
    properties["property_id"] = properties["property_id"].astype(str)

    baseline_lookup = baseline.set_index("property_id")

    print(f"Dev properties: {len(properties)}")
    print(f"Ring rows: {len(rings)}")
    print(f"Ring FEMA features: {rings['fema_feature_index'].nunique()}")

    for _, prop in properties.head(10).iterrows():
        property_id = str(prop["property_id"])
        x = float(prop["projected_x"])
        y = float(prop["projected_y"])

        expected_feature = int(baseline_lookup.loc[property_id, "fema_feature_index"])
        expected_sfha = bool(baseline_lookup.loc[property_id, "is_sfha"])

        feature_rings = rings[rings["fema_feature_index"] == expected_feature]

        matched_any_ring = False

        for (part_index, ring_index), ring in feature_rings.groupby(
            ["part_index", "ring_index"]
        ):
            if ring_index != 0:
                continue

            if point_in_ring(x, y, ring):
                matched_any_ring = True
                break

        print(
            {
                "property_id": property_id,
                "expected_feature": expected_feature,
                "expected_sfha": expected_sfha,
                "rings_for_feature": len(feature_rings),
                "manual_python_ring_match": matched_any_ring,
            }
        )


if __name__ == "__main__":
    main()