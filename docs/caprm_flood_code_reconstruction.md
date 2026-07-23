# CAPRM-Flood — Code Reconstruction (Current State)

Reconstructed 2026-07-21 for Milestone 4 planning, from the repository tree plus
six source files supplied directly. This is a working reconstruction of *current
behavior*, not a design document.

## Provenance legend

Every file summary is marked with how the summary was produced:

- **[SRC]** — read from the actual source file in this session. Grounded.
- **[DOC]** — not read this session; summarized from the canonical documents
  (Nucleus §19, Current Status §5, `scoring_methodology.md`, milestone docs) plus
  the filename and tree. Treat as *inferred* and verify by reading source before
  relying on it for implementation.

Six files are [SRC]; everything else is [DOC]. Where a [DOC] summary is thin, that
reflects that the documents describe the file only briefly.

---

## 1. File-by-file summaries

### C++ — `cpp/spatial_core/src/`

- **`water_distance_bruteforce.cpp`** **[SRC]** — Self-contained brute-force
  nearest-water program: robust CSV parsing, geometry structures
  (`Point`/`WaterFeature`/`Ring`), input readers (`read_properties`,
  `read_feature_metadata`, `read_vertices`), `validate_geometry` (which also
  returns the total segment count), the exact point-to-segment kernel
  (`point_segment_distance_squared`) with polygon inside/on-boundary handling,
  and the tie rule (1e-6 m tolerance, lexicographic on `water_feature_id`). Holds
  the shared kernel the indexed program reuses.
- **`water_distance_indexed.cpp`** **[SRC]** — `#include`s the brute-force `.cpp`
  (via a `#define main` rename) to reuse its kernel and IO, then adds a
  median-split **Feature BVH** over feature bounding boxes (leaf size 8) with
  best-first priority-queue traversal and squared lower-bound pruning. Emits the
  same evidence fields plus per-property instrumentation (`segment_checks`,
  `candidate_feature_checks`, `node_visits`) and `algorithm=feature_bvh`.
- **`fema_pip_dev.cpp`** **[SRC]** — Standalone FEMA point-in-polygon program:
  reads property points and exploded FEMA polygon rings, does a bbox pre-filter
  then a ray-crossing containment test, and writes per-property zone / SFHA /
  source-geometry membership. Independent of the water files (its own IO helpers).

### Python library — `python/caprm/`

- **`water_distance.py`** **[SRC]** — Python nearest-water *reference*: loads the
  hydrography cache (flowlines + waterbodies), validates CRS/IDs/geometry,
  reprojects to the distance CRS, builds a Shapely `STRtree`, and for each property
  runs `query_nearest` (all matches + distances), applies the 1e-6 m tie tolerance,
  resolves ties lexicographically on `water_feature_id`, recomputes the selected
  distance exactly, and enforces a completeness check (every distance strictly
  below the query buffer). 10-column output schema.
- **`water_export.py`** **[SRC]** — Exports C++ inputs for the water path: a
  projected-properties CSV, a feature-metadata CSV (dense `water_feature_index`
  after stable sort on `water_feature_id`), and a per-vertex CSV
  (feature/part/ring/vertex, `%.17g`). Counts line parts, polygon rings, vertices,
  and **segments** (`len(coords) - 1` per part/ring); SHA-256s every output; checks
  the Python reference's feature IDs all exist in the export.
- **`water_benchmark.py`** **[SRC]** — Benchmark harness for the two water
  executables: runs warmups + alternating-order repetitions, parses each program's
  stdout metrics, and summarizes timings/segment-check reduction/speedup. **Knows
  exactly two algorithms** — `brute_force` and `feature_bvh` — hard-coded in the
  parser and the summarizer.
- **`baseline.py`** **[DOC]** — FEMA point-in-polygon Python reference (the trusted
  side of the FEMA C++ comparison).
- **`hydrography.py`** **[DOC]** — USGS 3DHP ingestion and cache construction for
  the county-plus-buffer study area.
- **`terrain.py`** **[DOC]** — DEM sampling and terrain-metric derivation
  (elevation, local-mean, relative elevation, slope); raises on wrong/absent
  projected CRS.
- **`scoring.py`** **[DOC]** — Four-component exposure index
  (`preliminary_exposure_index_v2`): FEMA absolute lookup + water/terrain-abs/
  terrain-rel percentile ranks, explicit weights, composite rounded before
  percentile ranking; includes `component_influence` (variance decomposition).
- **`sensitivity.py`** **[DOC]** — Rank-stability analysis across weight scenarios
  (Spearman, top-decile overlap, per-property percentile shift) with thresholds
  declared before measurement and calibrating reference corners.
- **`audit.py`** **[DOC]** — Reads *stored* Milestone 3 artifacts and checks them
  against their manifests: SHA-256 match, shared property-ID sets, recomputed
  derived fields, weights-reproduce-index, range checks. `manifest_field` tolerates
  two manifest schema conventions.
- **`evidence.py`** **[DOC]** — Joins FEMA + water into the integrated flood
  evidence product.
- **`crs.py`** **[DOC]** — CRS normalization / validation helpers.
- **`export.py`** **[DOC]** — FEMA C++ input export (polygon rings, projected
  properties) — the FEMA analogue of `water_export.py`.
- **`validate.py`** **[DOC]** — Python/C++ comparison contract for the FEMA path.
- **`water_validate.py`** **[DOC]** — Python/C++ comparison contract for the water
  path.
- **`study_area.py`** **[DOC]** — County boundary load and 20 km buffered study
  area (projected before buffering).
- **`ingest.py`** **[DOC]** — Config/workload path resolution.
- **`__init__.py`** **[DOC]** — Empty package marker.

### Python scripts — `python/scripts/` (all [DOC])

Workload build: `materialize_property_workload.py`,
`materialize_countywide_property_workload.py`, `materialize_property_cache.py`.
FEMA path: `run_fema_baseline.py`, `export_cpp_inputs.py`,
`compare_python_cpp_fema.py`, `inspect_fema_schema.py`,
`create_cpp_dev_fixture.py`, `debug_cpp_fixture.py`, `summarize_baseline.py`.
Water path: `cache_hydrography.py`, `run_water_baseline.py`,
`export_water_cpp_inputs.py`, `compare_python_cpp_water.py`,
`benchmark_water_cpp.py`.
Terrain / scoring: `prepare_terrain_raster.py`, `build_terrain_evidence.py`,
`build_property_evidence.py`, `build_exposure_index.py`,
`summarize_scoring_inputs.py`, `summarize_component_correlation.py`,
`analyze_scoring_sensitivity.py`, `summarize_milestone3_results.py`.
Ops: `audit_milestone3_products.py`, `capture_environment.py`,
`inventory_repository.py`.

### Tests — `tests/` (all [DOC])

`conftest.py` plus one module per library area: `test_baseline`, `test_evidence`,
`test_export`, `test_hydrography`, `test_ingest`, `test_study_area`,
`test_validate`, `test_water_distance`, `test_water_export`,
`test_water_validate`, `test_water_benchmark`,
`test_materialize_countywide_property_workload`, `test_terrain`, `test_scoring`
(44), `test_sensitivity` (38), `test_audit` (38). Documents record **181 passing**.
There are **no C++ unit tests** by design; C++ correctness rests on field-by-field
comparison against the Python reference.

---

## 2. Top-down functional trace

Plain-language walk of what happens, in order, from raw data to final artifacts.
Water-path stages are grounded in [SRC] reading; others are [DOC].

**Stage 0 — Config and workload.** A workload YAML in `configs/` (1K / 10K / 100K /
countywide) names the study area and property inputs. `ingest.py` resolves paths;
the `materialize_*` scripts build the deterministic property workload (stable
`property_id` + coordinates, 267,362 unique countywide) from parcel/point data in
`data/processed/`. **Provenance:** property-cache manifests in
`outputs/validation/` with row/ID counts.

**Stage 1 — FEMA evidence.** The local NFHL (`data/raw/fema_nfhl_monroe/`, observed
EPSG:4269) is ingested; `baseline.py` projects to EPSG:3857 and runs Python
point-in-polygon, attaching `fema_zone`, `is_sfha`, and canonical `FLD_AR_ID`.
`export.py` writes exploded polygon rings + projected properties for C++;
`fema_pip_dev.cpp` recomputes membership independently; `validate.py` /
`compare_python_cpp_fema.py` compare the two. **Validation:** exact membership
agreement (1,000/1,000 on the fixture; agreement at every scale).

**Stage 2 — Hydrography cache.** `study_area.py` projects the county polygon to
EPSG:26918 and buffers 20 km; `hydrography.py` / `cache_hydrography.py` query USGS
3DHP into `data/raw/usgs_3dhp_monroe.gpkg` (flowlines + waterbodies layers).
**Checksum:** `hydrography_cache_manifest.json`.

**Stage 3 — Nearest-water evidence (the Milestone 4 target path).**
`water_distance.py` loads the cache, reprojects to EPSG:26918, builds a Shapely
STRtree, and computes each property's nearest-water distance + canonical feature
identity, tie-broken lexicographically on `water_feature_id` at 1e-6 m. This is the
**exact reference / oracle**. `water_export.py` exports the projected properties,
feature metadata, and per-vertex geometry for C++ (SHA-256 each). The two C++
programs — `water_distance_bruteforce.cpp` (kernel) and `water_distance_indexed.cpp`
(Feature BVH) — recompute the same answer. `water_validate.py` /
`compare_python_cpp_water.py` compare field-by-field. **Validation:** max distance
error 4.658e-10 m countywide. **Benchmark:** `water_benchmark.py` /
`benchmark_water_cpp.py` time brute-force vs Feature BVH → `outputs/benchmark/` +
`water_cpp_benchmark_*_summary.json`. The 104× finding (Current Status §19b) is
arithmetic on these counters.

**Stage 4 — Integrated FEMA + water evidence.** `evidence.py` /
`build_property_evidence.py` join stages 1 and 3 into
`property_flood_evidence_*.csv`. **Provenance:** `property_flood_evidence_*_manifest.json`.

**Stage 5 — Terrain evidence.** `prepare_terrain_raster.py` reprojects the USGS 3DEP
DEM (`data/raw/terrain/`) from EPSG:4269 to EPSG:26918 (bilinear, ~8.601 m pixel);
`terrain.py` / `build_terrain_evidence.py` sample elevation, local-mean, relative
elevation, and slope per property → `property_terrain_evidence_countywide.csv`.
**Checksum/CRS:** `terrain_raster_prepare_manifest.json`,
`property_terrain_evidence_countywide_manifest.json` (single CRS enforced).

**Stage 6 — Exposure index (frozen).** `scoring.py` / `build_exposure_index.py`
consume the two evidence tables (read-only) and produce the four-component index at
`preliminary_exposure_index_v2` → `property_exposure_index_countywide.csv`, composite
rounded before percentile ranking. **Provenance:**
`property_exposure_index_countywide_manifest.json` (weights reproduce the index).

**Stage 7 — Characterization.** `summarize_scoring_inputs.py`,
`summarize_component_correlation.py`, and `analyze_scoring_sensitivity.py` measure
the input domain, component orthogonality (max |ρ| = 0.152), and rank stability
(verdict: moderately sensitive). Outputs to `outputs/analysis/` and
`outputs/validation/`.

**Stage 8 — Audit and summary.** `audit_milestone3_products.py` re-reads the stored
artifacts against their manifests (49 pass / 1 warn / 0 fail; the warn is a known
manifest-schema divergence). `summarize_milestone3_results.py` writes the Milestone 3
results summary. `inventory_repository.py` and `capture_environment.py` record
repository and environment state.

---

## 3. Findings relevant to Milestone 4 / B1

Observations from reading the water-path source. These shape B1 and should be
verified against data before being built on.

1. **Segments already exist explicitly in the export.** `water_export.py` and C++
   `validate_geometry` both compute segment count as `len(coords) - 1` per line
   part and polygon ring. The exported `water_vertices_countywide.csv` therefore
   *already* encodes every segment (consecutive vertices within one
   part/ring). **L can be measured from that CSV without touching the raw
   `.gpkg`.**
2. **Polygon interiors return distance 0 — a real exactness subtlety.**
   `distance_to_polygon_feature` returns 0.0 when a point is inside or on a
   waterbody polygon, independent of the nearest boundary segment. A segment index
   over *boundary* segments alone would return the boundary distance, not 0, for
   the ~266 properties recorded at exactly zero. B1's segment index must preserve
   polygon-membership → 0, not just nearest-segment distance. This is the first
   compatibility implication to design for.
3. **The benchmark harness hard-codes two algorithms.**
   `water_benchmark.parse_cpp_benchmark_output` and `summarize_benchmark_runs`
   accept only `brute_force` and `feature_bvh`. B6 must extend both to accept
   `segment_bvh`, `hilbert_binary`, and `hilbert_rmi`.
4. **The shared-kernel include pattern is the extension point.**
   `water_distance_indexed.cpp` reuses the brute-force kernel by `#include`-ing the
   `.cpp`. A segment-BVH / Hilbert / RMI program follows the same pattern: include
   the kernel, add a new index, keep `point_segment_distance_squared` and the tie
   rule untouched.
5. **The tie rule must ride on each segment.** Ties resolve lexicographically on
   `water_feature_id` (1e-6 m). Every segment leaf must carry its parent feature's
   `water_feature_id`, or the tie rule breaks.

---

## 4. Current artifacts (from the repository tree)

- **Evidence:** `outputs/evidence/property_flood_evidence_countywide.csv`,
  `property_terrain_evidence_countywide.csv` (+ 10K/100K variants).
- **Index:** `outputs/index/property_exposure_index_countywide.csv`.
- **Baselines:** `outputs/baseline/python_fema_membership_*.csv`,
  `python_nearest_water_*.csv`.
- **C++ outputs:** `outputs/cpp/cpp_fema_membership_*.csv`,
  `cpp_nearest_water_bruteforce_*.csv`, `cpp_nearest_water_indexed_*.csv`.
- **C++ inputs:** `outputs/cpp_input/` (FEMA rings, water features, water vertices,
  projected properties, per scale).
- **Benchmarks:** `outputs/benchmark/water_cpp_benchmark_*_runs.csv`.
- **Analysis:** `outputs/analysis/scoring_sensitivity_summary.csv`,
  `scoring_sensitivity_property_shifts.csv`.
- **Validation/manifests:** ~90 files in `outputs/validation/` (per-stage manifests
  with SHA-256, agreement reports, summaries, `milestone3_audit.json`,
  `repository_inventory.json`, `milestone_1_environment.json`).
- **Presentation:** `presentation_assets/charts/` (Milestone 3 slide figures).

## 5. Not yet inspected this session

The 44 [DOC] files above are described from documentation only. Highest-value to
read from source before their stages are touched: `water_validate.py` (B1/B3/B6
acceptance runs through it), `hydrography.py` (defines the `.gpkg` layers/schema L
is measured from), and — when scoring is revisited — `scoring.py`, `sensitivity.py`,
`audit.py`.