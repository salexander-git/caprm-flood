# CAPRM-Flood

CAPRM-Flood is a reproducible C++/Python geospatial evidence-extraction framework for large-batch property-level flood exposure analysis. The current case study covers Monroe County, New York and processes a countywide workload of **267,362 unique property identifiers**.

The project derives three geospatial evidence families:

1. **FEMA flood-hazard evidence** — flood-zone and Special Flood Hazard Area membership.
2. **Nearest-water evidence** — distance to the nearest mapped USGS hydrographic feature, with deterministic feature identity and classification.
3. **Terrain evidence** — property elevation, local mean elevation, relative elevation, and local slope derived from a projected digital elevation model.

These validated evidence products feed a separate, transparent **preliminary relative exposure index** with explicit component normalization, weights, and countywide ranking. The index is frozen at scoring policy `preliminary_exposure_index_v2`, characterized as moderately sensitive to weight choice across 40 measured scenarios, and audited against its own manifests. It is the application layer, not the claim.

Milestone 4 is where the project's computer-science contribution is concentrated. It adds no evidence family. It asks whether **learned spatial indexing extends to exact nearest-neighbour queries over extended objects** — line segments and polygon boundaries — and what exactness costs. The learned-index literature is evaluated almost exclusively on point data and several published methods return approximate results, so this is an unexamined corner rather than an open problem, and the contribution available is a rigorous measurement the literature lacks.

The central engineering goals are correct spatial computation, explicit CRS handling, deterministic outputs, independent Python/C++ validation, provenance, reproducibility, and scalable countywide processing.

## Current milestone status

### Milestone 1 — complete and validated

Milestone 1 established the FEMA point-in-polygon validation foundation:

- deterministic 1,000-property regression fixture;
- Python GeoPandas/Shapely reference computation;
- independent C++ FEMA point-in-polygon implementation;
- canonical FEMA feature identity using `FLD_AR_ID`;
- explicit Python/C++ comparison;
- **1,000 / 1,000 validated property agreement**.

### Milestone 2 — complete and validated

Milestone 2 added nearest-water evidence and countywide scaling:

- deterministic 1K, 10K, 100K, and countywide property workloads;
- USGS hydrography ingestion and caching;
- Python STRtree nearest-water reference implementation;
- independent C++ brute-force nearest-water implementation;
- independent C++ indexed nearest-water implementation;
- deterministic nearest-feature tie resolution;
- strict Python/C++ validation at increasing scales;
- reproducible benchmark harness and summaries;
- integrated FEMA-plus-water property evidence;
- countywide application to **267,362 unique property identifiers**.

The countywide indexed nearest-water implementation reproduced all 267,362 Python results within a maximum absolute distance error of `4.658e-10 m`. In the canonical one-run countywide benchmark, the indexed implementation was `20.39x` faster in reported computation time and `19.83x` faster in total process time than brute force.

### Milestone 3 — complete and frozen

Milestone 3 implemented:

- projected DEM preparation;
- countywide terrain evidence extraction;
- elevation, local mean elevation, relative elevation, and slope features;
- terrain provenance/manifest generation;
- deterministic exposure-index generation at scoring policy `preliminary_exposure_index_v2`;
- index manifest generation;
- measured component influence by exact variance decomposition;
- rank-based sensitivity analysis across 40 weighting scenarios;
- an automated product audit that verifies stored artifacts against their own manifests;
- Milestone 3 result summarization;
- terrain, scoring, sensitivity, and audit tests.

Current countywide terrain results:

```text
properties: 267,362
unique property IDs: 267,362
missing slope values: 0
elevation range: approximately 75.000–296.309 m
```

Frozen preliminary exposure-index results:

```text
properties:                267,362
unique property IDs:       267,362
index minimum:             7.914598933
index maximum:             99.929084911
index mean:                34.63218408001099
index median:              33.7284299935
index standard deviation:  13.063711939924076
weights:                   fema 0.40, water 0.35,
                           terrain_absolute 0.15, terrain_relative 0.10
```

Nominal weight is not influence. Water carries 35 percent of the weight and 65 percent of the variance; FEMA carries 40 percent and 17 percent, because 98.1 percent of properties are tied at the same FEMA component value and constants do not affect ranking.

Measured rank stability:

```text
verdict                      moderately sensitive
minimum Spearman             0.875   (equal weighting)
median Spearman              0.996
minimum top-decile overlap   0.761   (equal weighting)
median top-decile overlap    0.946
```

Thresholds were declared before any result was measured. The verdict hinges on one scenario: every other plausible configuration sits near 0.996, and `equal` alone falls below the stable bar. This is not general instability — the index is stable unless you stop privileging water.

The index is frozen and remains **preliminary**. It is no longer the subject of active work.

### Milestone 4 — current phase, learned indexing of extended spatial objects

Milestone 4 builds a five-rung ladder of nearest-water implementations over the same geometry kernel, the same tie rule, and one validation standard, so that adjacent rungs isolate one variable each.

```text
1. brute force              no index                    Milestone 2
2. Feature BVH              2D,  8,572 features         Milestone 2
3. Segment BVH              2D, ~1.19M entries          B1, B2
4. Hilbert + binary search  1D, ~1.19M entries          B3   control
5. Hilbert + RMI            1D, ~1.19M entries          B4, B5   learned
6. + learned radius         seeds the search disk       B7   stretch
```

The path was forced by the project's own measurement rather than chosen to accommodate machine learning. The Feature BVH examines only 5.498 candidate features per property yet still performs 70,771 segment checks, because it indexes features rather than geometry and the largest water features are near almost everything in the county — the selected features are roughly 104 times larger than the average water feature. Rebuilding at segment granularity is what makes a learned index possible at all, and ~1.19M entries is squarely learned-index scale.

Complete and validated countywide through chunk B6c-2:

- **B1** — segment-granularity BVH with distance-exact splitting. `L = 5,748.2396 m` measured before anything was built on it. 267,362/267,362 field-for-field agreement at `4.658e-10 m`. Phase-2 work fell from 70,771 to 9,716.87 segment checks per property, **7.28x**, at B1's uncapped-equivalent 100 m entry-extent cap. At the 25 m operating point B2 selected, the countywide figure is **9,407.62** checks per property under original-geometry verification and **6,453.70** under split; the B6 tables report both.
- **B2** — entry-extent sweep under both verification strategies, 14/14 points at full agreement. The cap is *not* a performance dial: across a 575-fold range of maximum entry extent, median query time varies under 10 percent. It is chosen for its only downstream consumer, the `L/2` inflation radius. Operating point: 25 m cap.
- **B3** — Hilbert ordering of entry midpoints, exact inflated-disk query by recursive quadrant decomposition, and a binary-search control. Capping at 25 m costs 11.89 percent more entries and returns a **546x** reduction in admitted entries per query.
- **B4** — a two-stage recursive model index after Kraska et al., SIGMOD 2018. 131,072 linear second-stage models, 4,194,400 bytes, with a per-model error bound verified exhaustively over all 1,189,589 keys. The finding is the equi-depth diagnostic: **the router binds, not the leaves.**
- **B5** — inference ported to C++. Output byte-identical to the control on 267,362 properties.
- **B5c** — resolve-descent instrumentation, so the learned rung's cost is counted rather than inferred.

**The measured result is negative, and it is reported because the phase said in advance that it would be.** At the shipped configuration — countywide, seed window W = 64, original-geometry verification — the learned rung produces identical evidence and runs the query 6.48 percent slower:

```text
                              binary        rmi
resolve entries / property   141.1742   352.5154     2.497x
window missed                103,242    123,011      38.62% -> 46.01%
mean d_seed / d_best          1.1717     1.5388
tight entries / property      47.5926    47.5926     identical
```

The model saves about 20 key probes per property and spends about 211 extra point-to-segment distance computations to do it — roughly ten to one in the wrong direction. The mechanism is convexity rather than miss frequency: search cost grows as the square of the seed radius, the miss *rate* moves only 1.19x, and the worst overestimate moves from 32x to 517x the true radius. **The mean prediction error is the wrong summary statistic for a predictor that feeds a radius.**

A second finding is not about the model at all: the exact binary-search control misses its ±64 seed window on 38.62 percent of queries, which makes the window a query-design parameter for both rungs.

**That percentage is conditional, and B6 measured the conditions.** Across nine seed windows the learned-to-control wall-clock ratio moves from 1.11620 at W = 8 to 1.00002 at W = 2048, so the sign of 5 vs 4 is set by the seed window rather than by the model. Under split-geometry verification the same countywide gap reads +12.52 percent — the absolute penalty per property is unchanged and the denominator shrank, so the counted quantity is the invariant and the percentage is the artifact. The durable finding is therefore not “learning did not help” but that the reported benefit of a learned spatial index depends on parameters the literature holds fixed and does not report. See Nucleus 18.26 and 18.27.

Also complete and validated:

- **B6a** — a measurement harness with a repetition and warm-up protocol declared before measuring, blocked and cyclically rotated ordering, session guards, and crash-safe append-and-fsync recording. Two sittings of an identical rung-1 configuration were measured 11.02 percent apart on provably identical work, which is the evidence behind the session guard.
- **B6b** — `SEED_WINDOW` as a compile-time parameter across nine windows, byte-neutral at every one. The first attempt built seven binaries against source that never referenced the macro and the neutrality gate passed on them; the rule extracted is that a neutrality gate requires a positive control (Nucleus 18.25).
- **B6c** — the five-rung ladder at three workloads and a nine-window seed sweep at two workloads. 252 timed runs, exactness closed for all fifteen ladder cells.
- **B6c-2** — the Option A / Option B verification cross-product. Both pre-declared predictions held: 4 vs 3 predicted ~5.5x and measured 5.774x countywide; 5 vs 4 predicted +12.8 percent and measured +12.52.

Remaining: **B6d** — the published tables and the canonical-document pass. No measurement remains.

## Architecture

```text
Property locations
        |
        v
Python ingestion, CRS normalization, caching, and orchestration
        |
        +--> FEMA flood-hazard reference evidence
        |
        +--> Python nearest-water reference
        |
        +--> projected C++ input tables
        |           |
        |           v
        |   Independent C++ spatial computation
        |   - FEMA point-in-polygon
        |   - brute-force nearest water
        |   - Feature BVH nearest water
        |   - Segment BVH nearest water
        |   - Hilbert + binary search / Hilbert + RMI
        |           |
        |           v
        |   strict Python/C++ validation
        |
        +--> projected DEM preparation
        |           |
        |           v
        |   terrain raster sampling
        |   - elevation
        |   - local mean elevation
        |   - relative elevation
        |   - slope
        |
        v
Separate source-family evidence products
        |
        v
Explicit scoring / normalization layer
        |
        v
Relative exposure index + countywide rank
```

Python owns:

- public-data access;
- configuration;
- CRS inspection and transformation;
- trusted/reference calculations;
- deterministic workload and fixture generation;
- C++ input export;
- cross-implementation validation;
- benchmarking orchestration;
- terrain raster preparation and sampling;
- evidence integration;
- scoring;
- manifests and summaries.

C++ owns:

- independently implemented performance-relevant geometry kernels;
- FEMA point-in-polygon lookup;
- brute-force nearest-water computation;
- Feature BVH and Segment BVH nearest-water computation;
- Hilbert-ordered nearest-water computation with a binary-search or learned seed;
- learned-index *inference*.

**Python trains; C++ infers.** The recursive model index is fitted in `python/caprm/rmi.py` with numpy least squares and no framework; the C++ path loads the artifact and evaluates four multiply-adds, two clamps and two floors. The training array is exported by the implementation that built it (`--dump-keys`) rather than reconstructed in Python, because a reconstruction's checksum would attest to what Python built and the two can differ by a floating-point ULP in the segment split.

The C++ path is used for independent correctness comparison and performance evaluation rather than as a thin wrapper around Python.

## Evidence-product boundaries

CAPRM-Flood keeps upstream evidence separate from downstream scoring.

Current logical products are:

```text
FEMA / water evidence
terrain evidence
preliminary exposure index
```

A future precipitation evidence family will be added separately.

Validated source evidence should remain reusable even if the scoring methodology changes.

## CRS policy

Metric spatial operations for the Monroe County case study use:

```text
EPSG:26918
NAD83 / UTM zone 18N
```

CAPRM-Flood does not use longitude/latitude degrees as metric distance units. CRS metadata is explicitly inspected, transformed, and preserved through the workflow.

## Repository map

```text
configs/                   Workload-specific YAML configurations

cpp/spatial_core/src/      C++ FEMA and nearest-water implementations
                           - fema_pip_dev.cpp
                           - water_distance_bruteforce.cpp        (1)
                           - water_distance_indexed.cpp           (2)
                           - water_distance_segment_bvh.cpp       (3)
                           - water_distance_hilbert.cpp           (4 and 5)
                           Each includes the file below it, so the exact
                           kernel and tie rule are reused, not reimplemented.

models/                    Tracked model artifacts
                           - water_hilbert_rmi.bin  (4,194,400 bytes)
                           Tracked deliberately: outputs/ is ignored and the
                           C++ query path must load the model at run time.

python/caprm/              Reusable Python modules
                           - ingestion
                           - CRS handling
                           - FEMA evidence
                           - hydrography
                           - nearest-water computation
                           - validation
                           - benchmarking
                           - terrain
                           - scoring
                           - sensitivity
                           - product auditing
                           - Hilbert inflation instrumentation
                           - recursive model index (fit, bounds, serialization)

python/scripts/            Command-line workflow entry points
                           - workload materialization
                           - FEMA baseline
                           - hydrography caching
                           - water baseline
                           - C++ input export
                           - Python/C++ comparison
                           - benchmarking
                           - terrain raster preparation
                           - terrain evidence generation
                           - exposure-index generation
                           - scoring sensitivity analysis
                           - product auditing
                           - RMI training
                           - RMI probe-argument derivation
                           - seed-mode acceptance comparison
                           - result summarization

tests/                     Python unit and integration tests
tests/cpp/                 C++ unit suites for geometric invariants that have
                           no Python counterpart to compare against
tests/fixture_crosscheck.py
                           Cross-implementation fixture: runs every C++ binary
                           through the real CSV I/O path and asserts
                           field-for-field agreement plus the seam invariants

data/                      Cached source and deterministic property data
                           Large/raw geospatial artifacts are generally
                           excluded from normal Git tracking.

outputs/baseline/          Python reference outputs
outputs/cpp_input/         Projected and flattened C++ inputs
outputs/cpp/               C++ property-level outputs
outputs/benchmark/         Benchmark records
outputs/evidence/          Source-family evidence products
outputs/index/             Derived exposure-index outputs
outputs/validation/        Manifests, summaries, and agreement reports

docs/                      Project methods, milestones, data sources,
                           CRS policy, validation, and benchmark documentation
```

## Current core outputs

### Milestone 2 countywide outputs

```text
data/processed/monroe_property_points_countywide.geojson

outputs/baseline/python_fema_membership_countywide.csv
outputs/baseline/python_nearest_water_countywide.csv

outputs/cpp/cpp_fema_membership_countywide.csv
outputs/cpp/cpp_nearest_water_bruteforce_countywide.csv
outputs/cpp/cpp_nearest_water_indexed_countywide.csv

outputs/benchmark/water_cpp_benchmark_countywide_runs.csv

outputs/evidence/property_flood_evidence_countywide.csv
outputs/validation/property_flood_evidence_countywide_manifest.json
```

### Milestone 3 countywide outputs

```text
data/raw/terrain/source_dem/monroe_3dep_13arcsec.tif
data/raw/terrain/monroe_dem_utm18.tif

outputs/evidence/property_terrain_evidence_countywide.csv
outputs/validation/property_terrain_evidence_countywide_manifest.json

outputs/index/property_exposure_index_countywide.csv
outputs/validation/property_exposure_index_countywide_manifest.json

outputs/validation/milestone3_results_summary.md
```

### Milestone 4 countywide outputs

```text
outputs/cpp_input/water_hilbert_keys_countywide.bin

models/water_hilbert_rmi.bin
outputs/validation/water_hilbert_rmi_manifest.json

outputs/cpp/cpp_nearest_water_hilbert_countywide_b5c_binary.csv
outputs/cpp/cpp_nearest_water_hilbert_countywide_b5c_rmi.csv

outputs/validation/water_hilbert_countywide_manifest_b4.json
outputs/validation/water_hilbert_summary_{original,split,disk}.json
outputs/validation/water_hilbert_inflation_summary.json
outputs/validation/water_hilbert_query_stats_b5c_{binary,rmi}.json
outputs/validation/water_hilbert_seed_error_b5_{binary,rmi}.json

outputs/analysis/water_hilbert_inflation_by_decile.csv

outputs/benchmark/water_ladder_runs_{ladder,sweep,b6c2,sweepB,gridAB}.csv and .jsonl
outputs/validation/water_ladder_summary_{ladder,sweep,b6c2,sweepB,gridAB}.json
outputs/validation/b6c_{ladder,sweep}_counters.csv
outputs/validation/{b6c2,gridAB}_counters.csv
outputs/validation/b6b_window_sweep_counters_10000.csv
outputs/validation/ladder_{agreement,summary}_*.{csv,json}
outputs/validation/b6_analysis.json
outputs/validation/b6_benchmark_tables.md
```

`b6_analysis.json` and `b6_benchmark_tables.md` are generated by `python/scripts/analyze_b6_results.py` and must not be hand-edited. Every derived number in the benchmark tables is computed there and nowhere else, so an analysis performed in conversation is not reportable until it lands in that script with a test.

The three canonical countywide C++ inputs for the water family are:

```text
outputs/cpp_input/water_properties_projected_countywide.csv
    sample_order,property_id,projected_x,projected_y
outputs/cpp_input/water_features_countywide.csv
outputs/cpp_input/water_vertices_countywide.csv
```

`outputs/cpp_input/properties_projected_countywide.csv` is one prefix away and is
the **FEMA-side** export, with a different schema and no `sample_order`. The
water binaries reject it.

Large runtime data and generated outputs are generally ignored by Git. The repository preserves code, configuration, small fixtures, validation metadata, and documentation needed to reconstruct the workflow when the required source data is available.

## Environment

Python dependencies are pinned in `requirements.txt`.

From PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest
```

Current status:

```text
python -m pytest -q --ignore=tests/test_spatial_split.py
257 passed
```

The `--ignore` flag is required and is not a Milestone 4 issue: `tests/test_spatial_split.py` imports `scipy.spatial.cKDTree`, scipy is not installed, and pytest otherwise aborts during collection and runs zero tests. That file and the module it imports are untracked Phase C work in progress; when Phase C begins, scipy must be installed *and* declared in `requirements.txt` in the same change.

## C++ builds

The repository currently uses direct executable builds rather than CMake.

Representative GNU C++ builds from the repository root:

```powershell
g++ -std=c++17 -O2 cpp/spatial_core/src/fema_pip_dev.cpp -o cpp/spatial_core/build/fema_pip_dev.exe
g++ -std=c++17 -O2 cpp/spatial_core/src/water_distance_bruteforce.cpp -o cpp/spatial_core/build/water_distance_bruteforce.exe
g++ -std=c++17 -O2 cpp/spatial_core/src/water_distance_indexed.cpp -o cpp/spatial_core/build/water_distance_indexed.exe
g++ -std=c++17 -O2 -Wall -Wextra cpp/spatial_core/src/water_distance_segment_bvh.cpp -o cpp/spatial_core/build/water_distance_segment_bvh.exe
g++ -std=c++17 -O2 -ffp-contract=off -Wall -Wextra cpp/spatial_core/src/water_distance_hilbert.cpp -o cpp/spatial_core/build/water_distance_hilbert.exe
```

Use the same compiler and optimization settings when comparing benchmark runs.

`-ffp-contract=off` is required for the Hilbert binary. It changes nothing on baseline SSE2, but a `-march=native` build on Haswell or later could contract `a + b*x` into a fused multiply-add and shift the model's normalized input. The manifest probe records catch that at load; the flag prevents it.

## Reproducing the validated countywide FEMA / water evidence

The following sequence assumes the property, FEMA, county-boundary, and hydrography caches already exist and that the C++ executables have been built.

### 1. Python references

```powershell
.\.venv\Scripts\python.exe python/scripts/run_fema_baseline.py `
  --config configs/monroe_fema_spike_countywide.yaml

.\.venv\Scripts\python.exe python/scripts/run_water_baseline.py `
  --config configs/monroe_fema_spike_countywide.yaml
```

### 2. C++ inputs

```powershell
.\.venv\Scripts\python.exe python/scripts/export_cpp_inputs.py `
  --config configs/monroe_fema_spike_countywide.yaml `
  --scope baseline `
  --baseline-input outputs/baseline/python_fema_membership_countywide.csv `
  --properties-output outputs/cpp_input/properties_projected_countywide.csv `
  --rings-output outputs/cpp_input/fema_polygon_rings_joined_countywide.csv `
  --manifest-output outputs/validation/cpp_input_export_countywide_manifest.json

.\.venv\Scripts\python.exe python/scripts/export_water_cpp_inputs.py `
  --config configs/monroe_fema_spike_countywide.yaml `
  --reference outputs/baseline/python_nearest_water_countywide.csv `
  --properties-output outputs/cpp_input/water_properties_projected_countywide.csv `
  --features-output outputs/cpp_input/water_features_countywide.csv `
  --vertices-output outputs/cpp_input/water_vertices_countywide.csv `
  --manifest-output outputs/validation/water_cpp_input_countywide_manifest.json
```

### 3. Independent C++ computations

```powershell
.\cpp\spatial_core\build\fema_pip_dev.exe `
  outputs/cpp_input/properties_projected_countywide.csv `
  outputs/cpp_input/fema_polygon_rings_joined_countywide.csv `
  outputs/cpp/cpp_fema_membership_countywide.csv

.\cpp\spatial_core\build\water_distance_bruteforce.exe `
  outputs/cpp_input/water_properties_projected_countywide.csv `
  outputs/cpp_input/water_features_countywide.csv `
  outputs/cpp_input/water_vertices_countywide.csv `
  outputs/cpp/cpp_nearest_water_bruteforce_countywide.csv `
  EPSG:26918

.\cpp\spatial_core\build\water_distance_indexed.exe `
  outputs/cpp_input/water_properties_projected_countywide.csv `
  outputs/cpp_input/water_features_countywide.csv `
  outputs/cpp_input/water_vertices_countywide.csv `
  outputs/cpp/cpp_nearest_water_indexed_countywide.csv `
  EPSG:26918
```

### 4. Correctness validation

```powershell
.\.venv\Scripts\python.exe python/scripts/compare_python_cpp_fema.py `
  --python-baseline outputs/baseline/python_fema_membership_countywide.csv `
  --cpp-output outputs/cpp/cpp_fema_membership_countywide.csv `
  --detail-output outputs/validation/fema_pip_countywide_agreement_report.csv `
  --summary-output outputs/validation/fema_pip_countywide_summary.json `
  --scope union

.\.venv\Scripts\python.exe python/scripts/compare_python_cpp_water.py `
  --python-reference outputs/baseline/python_nearest_water_countywide.csv `
  --cpp-output outputs/cpp/cpp_nearest_water_bruteforce_countywide.csv `
  --detail-output outputs/validation/water_bruteforce_countywide_agreement.csv `
  --summary-output outputs/validation/water_bruteforce_countywide_summary.json `
  --distance-tolerance-meters 1e-6

.\.venv\Scripts\python.exe python/scripts/compare_python_cpp_water.py `
  --python-reference outputs/baseline/python_nearest_water_countywide.csv `
  --cpp-output outputs/cpp/cpp_nearest_water_indexed_countywide.csv `
  --detail-output outputs/validation/water_indexed_countywide_agreement.csv `
  --summary-output outputs/validation/water_indexed_countywide_summary.json `
  --distance-tolerance-meters 1e-6
```

### 5. Canonical benchmark and evidence integration

```powershell
.\.venv\Scripts\python.exe python/scripts/benchmark_water_cpp.py `
  --properties outputs/cpp_input/water_properties_projected_countywide.csv `
  --features outputs/cpp_input/water_features_countywide.csv `
  --vertices outputs/cpp_input/water_vertices_countywide.csv `
  --runs-output outputs/benchmark/water_cpp_benchmark_countywide_runs.csv `
  --summary-output outputs/validation/water_cpp_benchmark_countywide_summary.json `
  --temporary-output-directory outputs/benchmark/temporary_water_outputs_countywide `
  --repetitions 1 `
  --warmups 0

.\.venv\Scripts\python.exe python/scripts/build_property_evidence.py `
  --config configs/monroe_fema_spike_countywide.yaml `
  --fema-validation outputs/validation/fema_pip_countywide_summary.json `
  --water-validation outputs/validation/water_indexed_countywide_summary.json `
  --benchmark-summary outputs/validation/water_cpp_benchmark_countywide_summary.json
```

## Milestone 3 workflow entry points

Current Milestone 3 implementation is centered on:

```text
python/scripts/prepare_terrain_raster.py
python/scripts/build_terrain_evidence.py
python/scripts/build_exposure_index.py
python/scripts/summarize_milestone3_results.py
```

Reusable implementation:

```text
python/caprm/terrain.py
python/caprm/scoring.py
```

Tests:

```text
tests/test_terrain.py
tests/test_scoring.py
```

Sensitivity, auditing, and summarization:

```text
python/scripts/analyze_scoring_sensitivity.py
python/scripts/audit_milestone3_products.py
python/scripts/summarize_milestone3_results.py
```

## Milestone 4 workflow entry points

Build the Hilbert index, export its own key array, and train the model. The training array is exported by the C++ implementation that built it rather than reconstructed in Python, so its checksum attests to what the index holds.

```powershell
.\cpp\spatial_core\build\water_distance_hilbert.exe outputs/cpp_input/water_properties_projected_countywide.csv outputs/cpp_input/water_features_countywide.csv outputs/cpp_input/water_vertices_countywide.csv outputs/cpp/cpp_nearest_water_hilbert_countywide.csv EPSG:26918 25 original disk 32 outputs/validation/water_hilbert_countywide_manifest.json --dump-keys outputs/cpp_input/water_hilbert_keys_countywide.bin
```

```powershell
.\.venv\Scripts\python.exe python\scripts\train_hilbert_rmi.py --keys outputs/cpp_input/water_hilbert_keys_countywide.bin --index-manifest outputs/validation/water_hilbert_countywide_manifest.json --model-output models/water_hilbert_rmi.bin --manifest-output outputs/validation/water_hilbert_rmi_manifest.json
```

Derive the probe argument from the model manifest — never transcribe it — then run the learned rung:

```powershell
$P = (.\.venv\Scripts\python.exe python\scripts\rmi_probe_args.py --expect-records 5)
```

```powershell
.\cpp\spatial_core\build\water_distance_hilbert.exe outputs/cpp_input/water_properties_projected_countywide.csv outputs/cpp_input/water_features_countywide.csv outputs/cpp_input/water_vertices_countywide.csv outputs/cpp/cpp_nearest_water_hilbert_countywide_rmi.csv EPSG:26918 25 original disk 32 --seed rmi --rmi-model models/water_hilbert_rmi.bin --rmi-probes $P --query-stats outputs/validation/water_hilbert_query_stats_rmi.json
```

Assert the acceptance criterion — the learned rung must change no emitted field:

```powershell
.\.venv\Scripts\python.exe python\scripts\compare_seed_modes.py --left outputs/cpp/cpp_nearest_water_hilbert_countywide.csv --right outputs/cpp/cpp_nearest_water_hilbert_countywide_rmi.csv
```

Cross-implementation fixture, which exercises every binary through the real CSV path:

```powershell
.\.venv\Scripts\python.exe tests\fixture_crosscheck.py
```

Reusable implementation:

```text
python/caprm/rmi.py
python/caprm/hilbert_inflation.py
```

Tests:

```text
tests/test_rmi.py
tests/test_hilbert_inflation.py
tests/test_ladder_benchmark.py
tests/cpp/test_water_segment_bvh.cpp
tests/cpp/test_water_segment_bvh_verify_modes.cpp
```

## Current roadmap

Immediate work — Milestone 4 chunk B6d, the close-out. No measurement remains:

1. give `python/caprm/ladder_analysis.py` a verification-mode dimension, so that pointing the analysis at the cross-product invocations cannot mix Option A and Option B inside one comparison;
2. close the six outstanding exactness cells — the `_10000` and `_100000` Option B cells have digests but have not been run through `compare_python_cpp_water.py`, and the completion gate requires exact agreement for every implementation claiming exactness at every workload;
3. publish the benchmark table as three adjacent comparisons per workload **and** per verification mode, with wall clock beside counts, `n` beside every figure, and any comparison whose gap sits inside its cells' own range marked NOT RESOLVED rather than printed as though it carried a claim;
4. report search and verification as separate columns throughout, and report 4 vs 3 in both modes with Option A labelled diluted;
5. report inflation as a first-class axis, including the uncounted `2W` window scan and its ~7.8x locality premium over a resolve-descent entry;
6. update `docs/benchmark_results.md` and the three canonical documents, and verify this README does not contradict them.

Complete: B6a (harness and protocol), B6b (`SEED_WINDOW` as a compile-time parameter), B6c (the ladder and the nine-window sweep), B6c-2 (the verification cross-product).

After Milestone 4 Phase B:

1. train a neural surrogate of the pipeline's own deterministic output, split by spatial block rather than randomly;
2. close the loop by using the surrogate's distance field to seed the exact query's search radius, making the approximate answer load-bearing for the exact one;
3. consolidate reproducibility, runtime instrumentation, and repository hygiene;
4. deliver the report and poster.

Precipitation is retained as a **gated stretch goal**, permitted only after the Milestone 4 computational work is complete and documented. It is not cancelled; it is outranked. A fourth evidence family adds ingestion, provenance, and validation work and no algorithmic content, and the project's identified weakness was that its computer-science contribution had stalled.

## Documentation

Current repository documentation includes:

- [Milestone 2](docs/milestone_2.md)
- [Benchmark results](docs/benchmark_results.md)
- [Data sources](docs/data_sources.md)
- [CRS policy](docs/crs_policy.md)
- [Validation](docs/validation.md)
- [Milestone 1](docs/milestone_1.md)

The three living canonical documents are tracked under `docs/canon/` and are reviewed at the end of every completed chunk:

```text
docs/canon/CAPRM_Flood_Project_Nucleus_2026-07-15.md   durable architecture, decisions, methodology
docs/canon/CAPRM_Flood_Current_Status.md               exact present state, current commit, next task
docs/canon/CAPRM_Flood_Roadmap.md                      remaining work in dependency order
```

Where they conflict with each other, prefer current validated code and generated artifacts first, then Current Status, then the Nucleus, then the Roadmap.

## Scope and interpretation

CAPRM-Flood produces transparent property-level geospatial exposure evidence and a relative regional exposure index.

The current index is intended for comparative screening and analysis. It does not currently claim calibrated flood probability, expected financial loss, insurance pricing, or actuarial-grade risk.

## Current known limitations

- The exposure index remains **preliminary**. It is frozen and characterized as moderately sensitive to weight choice, not calibrated.
- Precipitation evidence has not yet been added and is gated behind Milestone 4.
- Memory is measured per rung on three instruments that disagree in direction, and none may be quoted alone (Nucleus 18.24). Countywide, on persistent structure the Hilbert path is 8.74x smaller than the segment BVH — a 9,516,712-byte key array plus a 4,194,400-byte model against 119,768,836 bytes of BVH; on peak resident memory the segment BVH is 1.25x smaller; on peak committed memory the Hilbert path is 1.20x smaller. Peak resident memory is the wrong instrument for a model's size cost specifically, because the peak occurs during index construction before the model is loaded. A ~160 MB transient in the Hilbert path's resident peak is constant across a 27x range of query count, which places it in index construction, and remains unattributed beyond that.
- **Wall-clock figures follow B6a's repetition protocol** — 3+1 warm-up at rung 1 and 7+1 at rungs 2-5, blocked by repetition and cyclically rotated by block index, with dispersion reported as min/median/max and relative spread always. Absolutes move about 1 percent between invocations while adjacent ratios agree to 0.116 percentage points, so ratios are reported within an invocation and absolutes with their invocation named. `brute_force@countywide` carries a 31.71 percent spread at n=3, five times any other cell, so its figure is an order-of-magnitude statement and rung 1 appears in no adjacent comparison.
- C++ `computation_seconds` includes geometry queries, CSV row writing, and progress logging; query-only and output-only time are not separated.
- Runs carrying `--verify-counts`, `--uncapped-half` or `--seed-error-stats` are not benchmark-eligible: each adds work per property. `--query-stats` is free and is eligible.
- **The Milestone 4 negative result is measured at one index size**, 1,189,589 entries. The `_10000`/`_100000`/`_countywide` workloads vary query COUNT, not index size: the exporter writes the whole feature table regardless of the property set, so all three build the identical index. The learned-index literature's central claim is that the advantage grows with index size, and this project does not test that; a true index-size axis needs a defensible hydrography subsetting scheme, a reference recomputed at each subset, and the model retrained at each N. It is deferred as a stretch chunk.
- Below roughly twelve thousand properties the Hilbert path spends more time constructing its index than using it. Index construction is 0.912181 s and is constant across every workload while query cost is linear in the property count, so build equals query at Q = 12,301 under original-geometry verification and Q = 24,749 under split. Any end-to-end claim about this path states whether construction is included, and at what query count.
- The Python pipeline that produces every Milestone 3 result has no runtime instrumentation.
- The C++ path does not itself verify the trained model's training-array SHA-256; it verifies a fingerprint (array length, five sampled keys, and the full inference chain) while the trainer verifies the digest. The provenance chain closes across the two languages but not inside either alone.
- The C++ source is functional but is not organized as a reusable CMake library. Two native unit suites exist for geometric invariants that have no Python counterpart; the primary correctness claim still rests on field-by-field comparison against the Python reference.
- Public ArcGIS, FEMA, USGS, and future NOAA source data can change; manifests and checksums identify the exact cached inputs used for reported results.