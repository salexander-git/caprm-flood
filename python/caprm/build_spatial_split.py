"""Build the Phase C spatially-blocked train/val/test split (task C1).

READ-ONLY with respect to frozen products. Consumes:
  * the frozen projected coordinates (EPSG:26918, meters), by default
    outputs/cpp_input/water_properties_projected_countywide.csv
    (columns: sample_order, property_id, projected_x, projected_y), and
  * the frozen exposure index
    outputs/index/property_exposure_index_countywide.csv
    (target column: exposure_index_0_100).

Produces:
  * a split assignment CSV (property_id, split, block_id, block_i, block_j), and
  * a manifest JSON (block size, buffer, seed, fractions, origin, input/output
    SHA-256s, join validation, per-split counts, dropped counts, verified min
    train<->test and train<->val separation, CRS).

The exposure-index value is NOT copied into the split file: C2 re-joins the label
from the frozen index by property_id, keeping the frozen index the single source
of the target. This script only validates that the join is clean.

Example (PowerShell, run from the repo root):

    python python/scripts/build_spatial_split.py `
        --block-size 2000 --buffer 2000 --seed 20260722

Every parameter has a default; override any of them explicitly.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from caprm.spatial_split import (  # noqa: E402
    DISTANCE_CRS,
    SplitConfig,
    build_split,
)

SPLIT_TOOL_VERSION = "caprm.spatial_split/c1.0"

DEFAULT_COORDS = Path(
    "outputs/cpp_input/water_properties_projected_countywide.csv"
)
DEFAULT_INDEX = Path("outputs/index/property_exposure_index_countywide.csv")
DEFAULT_OUT_SPLIT = Path("outputs/splits/spatial_split_countywide.csv")
DEFAULT_OUT_MANIFEST = Path(
    "outputs/validation/spatial_split_countywide_manifest.json"
)

# UTM zone 18N, Monroe County: a wide sanity box in meters. Used only to catch
# gross CRS mistakes (e.g. lon/lat passed by accident), never to reject data on
# the edges.
UTM18N_X_RANGE = (200_000.0, 400_000.0)
UTM18N_Y_RANGE = (4_600_000.0, 4_900_000.0)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_coordinates(
    path: Path, id_col: str, x_col: str, y_col: str
) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={id_col: "string"})
    for column in (id_col, x_col, y_col):
        if column not in frame.columns:
            raise ValueError(
                f"Coordinate file {path} is missing column '{column}'. "
                f"Available: {list(frame.columns)}"
            )
    frame = frame[[id_col, x_col, y_col]].rename(
        columns={id_col: "property_id", x_col: "x", y_col: "y"}
    )
    frame["property_id"] = frame["property_id"].str.strip()
    frame["x"] = pd.to_numeric(frame["x"], errors="raise").astype("float64")
    frame["y"] = pd.to_numeric(frame["y"], errors="raise").astype("float64")

    if frame["property_id"].isna().any() or frame["property_id"].eq("").any():
        raise ValueError("Coordinate file contains missing property IDs.")
    if frame["property_id"].duplicated().any():
        raise ValueError("Coordinate file contains duplicate property IDs.")
    if not np.isfinite(frame[["x", "y"]].to_numpy()).all():
        raise ValueError("Coordinate file contains non-finite coordinates.")

    _check_crs_plausibility(frame["x"].to_numpy(), frame["y"].to_numpy(), path)
    return frame


def _check_crs_plausibility(x: np.ndarray, y: np.ndarray, path: Path) -> None:
    # Hard error on the classic mistake: coordinates that look like lon/lat.
    if (np.abs(x) <= 180.0).all() and (np.abs(y) <= 90.0).all():
        raise ValueError(
            f"Coordinates in {path} look like longitude/latitude, not "
            f"EPSG:26918 meters. Refusing to build metric blocks in degrees."
        )


def load_index(path: Path, id_col: str, value_col: str) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={id_col: "string"})
    if id_col not in frame.columns:
        raise ValueError(
            f"Index file {path} is missing ID column '{id_col}'. "
            f"Available: {list(frame.columns)}"
        )
    if value_col not in frame.columns:
        raise ValueError(
            f"Index file {path} is missing target column '{value_col}'. "
            f"Available: {list(frame.columns)}"
        )
    scoring_policy_version = None
    if "scoring_policy_version" in frame.columns:
        versions = set(frame["scoring_policy_version"].astype("string").unique())
        if len(versions) != 1:
            raise ValueError(
                f"Index file has multiple scoring_policy_version values: "
                f"{sorted(versions)}"
            )
        scoring_policy_version = next(iter(versions))

    out = frame[[id_col, value_col]].rename(
        columns={id_col: "property_id", value_col: "target"}
    )
    out["property_id"] = out["property_id"].str.strip()
    out["target"] = pd.to_numeric(out["target"], errors="raise").astype("float64")
    if out["property_id"].duplicated().any():
        raise ValueError("Index file contains duplicate property IDs.")
    out.attrs["scoring_policy_version"] = scoring_policy_version
    out.attrs["target_column"] = value_col
    return out


def validate_join(coords: pd.DataFrame, index: pd.DataFrame) -> dict:
    coord_ids = set(coords["property_id"])
    index_ids = set(index["property_id"])
    coords_only = sorted(coord_ids - index_ids)
    index_only = sorted(index_ids - coord_ids)
    if coords_only or index_only:
        raise ValueError(
            "Coordinate and index property-ID sets differ. "
            f"{len(coords_only)} coords-only (e.g. {coords_only[:5]}), "
            f"{len(index_only)} index-only (e.g. {index_only[:5]}). "
            "The split is built on the frozen index population; investigate "
            "the mismatch rather than silently dropping rows."
        )
    return {
        "n_matched": len(coord_ids),
        "coords_only": len(coords_only),
        "index_only": len(index_only),
    }


def build(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coords", type=Path, default=DEFAULT_COORDS)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--out-split", type=Path, default=DEFAULT_OUT_SPLIT)
    parser.add_argument("--out-manifest", type=Path, default=DEFAULT_OUT_MANIFEST)
    parser.add_argument("--coord-id-col", default="property_id")
    parser.add_argument("--coord-x-col", default="projected_x")
    parser.add_argument("--coord-y-col", default="projected_y")
    parser.add_argument("--index-id-col", default="property_id")
    parser.add_argument("--index-value-col", default="exposure_index_0_100")
    parser.add_argument("--block-size", type=float, default=2000.0)
    parser.add_argument("--buffer", type=float, default=2000.0)
    parser.add_argument("--seed", type=int, default=20260722)
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--origin-x", type=float, default=0.0)
    parser.add_argument("--origin-y", type=float, default=0.0)
    args = parser.parse_args(argv)

    config = SplitConfig(
        block_size_m=args.block_size,
        buffer_m=args.buffer,
        seed=args.seed,
        train_fraction=args.train_fraction,
        val_fraction=args.val_fraction,
        origin_x_m=args.origin_x,
        origin_y_m=args.origin_y,
    )

    coords = load_coordinates(
        args.coords, args.coord_id_col, args.coord_x_col, args.coord_y_col
    )
    index = load_index(args.index, args.index_id_col, args.index_value_col)
    join_stats = validate_join(coords, index)

    coords = coords.sort_values("property_id", kind="stable").reset_index(drop=True)
    result = build_split(
        coords["property_id"].to_numpy(dtype=object),
        coords["x"].to_numpy(),
        coords["y"].to_numpy(),
        config,
    )

    split_frame = pd.DataFrame(
        {
            "property_id": result.property_id,
            "split": result.split,
            "block_id": [
                f"{int(i)}_{int(j)}"
                for i, j in zip(result.block_i, result.block_j)
            ],
            "block_i": result.block_i,
            "block_j": result.block_j,
        }
    )

    args.out_split.parent.mkdir(parents=True, exist_ok=True)
    split_frame.to_csv(args.out_split, index=False)

    mtt = result.stats["min_separation_m"]["test_train"]
    mvt = result.stats["min_separation_m"]["val_train"]
    manifest = {
        "task": "C1_spatial_block_split",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "tool_version": SPLIT_TOOL_VERSION,
        "crs": DISTANCE_CRS,
        "config": {
            "block_size_m": config.block_size_m,
            "buffer_m": config.buffer_m,
            "seed": config.seed,
            "train_fraction": config.train_fraction,
            "val_fraction": config.val_fraction,
            "test_fraction": config.test_fraction,
            "origin_x_m": config.origin_x_m,
            "origin_y_m": config.origin_y_m,
            "block_split_hash": "blake2b(f'{seed}:{i}:{j}')",
        },
        "inputs": {
            "coordinates": {
                "path": str(args.coords),
                "sha256": sha256(args.coords),
                "n_rows": int(len(coords)),
                "id_col": args.coord_id_col,
                "x_col": args.coord_x_col,
                "y_col": args.coord_y_col,
                "declared_crs": DISTANCE_CRS,
            },
            "exposure_index": {
                "path": str(args.index),
                "sha256": sha256(args.index),
                "n_rows": int(len(index)),
                "id_col": args.index_id_col,
                "target_col": index.attrs["target_column"],
                "scoring_policy_version": index.attrs["scoring_policy_version"],
            },
        },
        "join": join_stats,
        "output": {
            "split_path": str(args.out_split),
            "split_sha256": sha256(args.out_split),
            "n_rows": int(len(split_frame)),
            "columns": list(split_frame.columns),
            "canonical_columns": ["property_id", "split", "block_id"],
        },
        "stats": result.stats,
        "acceptance": {
            "min_test_train_m": mtt,
            "min_val_train_m": mvt,
            "min_test_train_ge_w": (mtt is None) or (mtt >= config.buffer_m),
            "min_val_train_ge_w": (mvt is None) or (mvt >= config.buffer_m),
            "test_survivors": int(result.stats["counts_final"]["test"]),
            "val_survivors": int(result.stats["counts_final"]["val"]),
        },
    }

    args.out_manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.out_manifest.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, default=str)

    print(json.dumps(manifest, indent=2, default=str))

    if not manifest["acceptance"]["min_test_train_ge_w"]:
        print("ACCEPTANCE FAILED: min test<->train separation below w.")
        return 1
    if manifest["acceptance"]["test_survivors"] == 0:
        print("ACCEPTANCE FAILED: no surviving test properties.")
        return 1
    print("ACCEPTANCE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())