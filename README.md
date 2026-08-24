# CAPRM-Flood

**Exact nearest-neighbour search over extended spatial objects, measured five
ways against one reference.**

CAPRM-Flood extracts property-level flood-exposure evidence for Monroe County,
New York — 267,362 properties against 8,572 mapped water features — and then
uses that workload to ask a question the learned-index literature has not
answered: does a learned spatial index still pay when the query must be *exact*
and the objects are line segments and polygon boundaries rather than points?

Five independent C++ implementations of the same nearest-water query were built
over one geometry kernel and one tie rule, each validated field-for-field
against a frozen Python reference. The answer is measured, not argued.

```text
rung                          index                        us/property   checks/property
1  brute force                none                            3993.925         1,063,159
2  feature hierarchy          2D BVH, 8,572 features           235.449            70,771
3  segment hierarchy          2D BVH, 1,189,589 entries         34.099             9,408
4  Hilbert + binary search    1D order, 1,189,589 entries       66.389            11,022
5  Hilbert + learned index    1D order, RMI-seeded               70.692            11,022
```

Countywide, original-geometry verification, one invocation. Absolutes move about
one percent between invocations while adjacent ratios agree to 0.116 percentage
points, so ratios are quoted within an invocation and absolutes with their
invocation named. Rung 1 carries a 31.71 percent spread at n=3, five times any
other cell, and appears in no adjacent comparison.

## What the measurements say

**Exactness is free at the hierarchy, and it is not free at the ordering.**
Rebuilding the index at segment granularity rather than feature granularity is
worth **6.90×** — the largest single win in the project — because the feature
hierarchy indexes objects rather than geometry, and the county's largest water
features are near almost everything in it.

**The learned index lost, and the phase said in advance that it might.** At the
shipped configuration the RMI seeder produces byte-identical evidence and runs
the query **6.48 percent slower** than the exact binary-search control. It saves
about 20 key probes per property and spends about 211 extra point-to-segment
distance computations to do it. The mechanism is convexity, not miss frequency:
search cost grows as the square of the seed radius, the miss *rate* moves only
1.19×, but the worst overestimate moves from 32× to 517× the true radius.
**The mean prediction error is the wrong summary statistic for a predictor that
feeds a radius.**

**The sign of that result is set by a parameter the literature holds fixed.**
Across nine seed windows the learned-to-control ratio moves from 1.11620 at
W = 8 to 1.00002 at W = 2048. The durable finding is therefore not "learning did
not help" but that the reported benefit of a learned spatial index depends on
configuration that published comparisons do not report.

**A registered prediction was refuted.** Before the analysis ran, the surrogate
phase predicted in its own stored artifact that prediction error would spike
along FEMA flood-zone boundaries. It does not. The mechanism behind the
prediction was confirmed; the spatial claim was not. Under a buffered blocked
split the coordinates-only surrogate is not separable from a constant predictor
at all.

Reporting the two negative results is what makes the positive ones credible.

## Verified state

```text
Python test suite     656 passed, 0 failed
Artifact audit        49 pass, 1 warn, 0 fail
Cross-implementation  5 designs x 267,362 properties x 10 fields, full agreement
Max distance error    4.658e-10 m against a 1e-6 m tolerance
Scoring policy        preliminary_exposure_index_v2, frozen
Rank stability        moderately sensitive (40 scenarios, min Spearman 0.875)
```

The single audit warning is recorded, not suppressed: two manifest key
conventions coexist across the products, so any tool reading manifests
generically must handle both.

Every figure above except the test count traces to a tracked artifact; the test
count you reproduce by running the suite.
**[`docs/evidence_index.md`](docs/evidence_index.md)** maps each claim to the
file and the field that establishes it.

## What to look at

If you are reading this to judge the engineering rather than to use the tool:

| | |
| --- | --- |
| [`cpp/spatial_core/src/`](cpp/spatial_core/src/) | Five nearest-water implementations. Each file `#include`s the one below it, so the distance kernel and the tie rule are *reused* across the ladder rather than reimplemented — which is what makes adjacent rungs differ by one variable. |
| [`python/caprm/audit.py`](python/caprm/audit.py) | Audits stored artifacts against their own manifests rather than auditing the code that wrote them, so it catches drift the unit tests cannot see. |
| [`python/caprm/sensitivity.py`](python/caprm/sensitivity.py) | Stability thresholds declared in source before any result was measured, with reference corners included so a high correlation among plausible scenarios can be interpreted at all. |
| [`python/caprm/rmi.py`](python/caprm/rmi.py) | The recursive model index: numpy least squares, no framework, with a per-model error bound verified exhaustively over all 1,189,589 keys. Python trains, C++ infers. |
| [`python/caprm/ladder_benchmark.py`](python/caprm/ladder_benchmark.py) | The measurement harness. Repetition protocol declared before measuring, blocked and cyclically rotated ordering, session guards, crash-safe append-and-fsync. Two sittings of an identical configuration once measured 11.02 percent apart on provably identical work; that is the evidence behind the session guard. |
| [`outputs/validation/b6_benchmark_tables.md`](outputs/validation/b6_benchmark_tables.md) | Published results. Any comparison whose gap sits inside its own cells' range is printed `NOT RESOLVED` rather than as though it carried a claim. |

## What this is not

The exposure index is a **relative regional ranking**, not a calibrated flood
probability, an expected loss, an insurance price, or an actuarial estimate.
Three of its four components are percentile ranks computed within the workload,
so a score states a position among these 267,362 properties and is not
comparable across workloads or across NFHL vintages.

Agreement across five implementations validates the *implementation*. Five
programs reproducing an identical distance to within a nanometre establishes
nothing about whether distance to the nearest mapped water feature is a good
proxy for flood exposure.

## Quick start

What a clone can do without downloading anything, and what it cannot.

**Tracked, so this works immediately:** the 1,000-property sample workload
(`data/processed/monroe_property_points_sample.geojson`), the county's
hydrography (`data/raw/usgs_3dhp_monroe.gpkg`, 21.2 MB), the trained RMI
(`models/water_hilbert_rmi.bin`), the full test suite, and every manifest that
carries a published number.

**Not tracked, so these need acquiring from [`docs/data_sources.md`](docs/data_sources.md)
first:** the FEMA NFHL shapefile, the 3DEP DEM, and the countywide parcel
centroids. They are hundreds of megabytes and are public.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest          # 656 passed
```

That is the whole verification loop for the Python side. To exercise the
geometry against real data at the sample scale — no downloads needed beyond
what is tracked:

```powershell
# Python nearest-water reference over the 1,000-property sample
.\.venv\Scripts\python.exe python/scripts/run_water_baseline.py `
  --config configs/monroe_fema_spike.yaml

# The same query in C++, then a field-for-field comparison
cmake -S cpp/spatial_core -B cpp/spatial_core/cmake-build -DCMAKE_BUILD_TYPE=Release
cmake --build cpp/spatial_core/cmake-build --parallel

.\.venv\Scripts\python.exe python/scripts/export_water_cpp_inputs.py `
  --config configs/monroe_fema_spike.yaml `
  --reference outputs/baseline/python_nearest_water.csv `
  --properties-output outputs/cpp_input/water_properties_projected.csv `
  --features-output outputs/cpp_input/water_features.csv `
  --vertices-output outputs/cpp_input/water_vertices.csv `
  --manifest-output outputs/validation/water_cpp_input_manifest.json
```

To read the results rather than recompute them, start at
[`docs/evidence_index.md`](docs/evidence_index.md) — every published figure,
the file that establishes it, and the field within that file.

The countywide sequence below is the full path, and assumes the source data has
been acquired and the caches built.

## Contents

- [Quick start](#quick-start) — what a clone can run with no downloads
- [Architecture](#architecture) — what Python owns, what C++ owns, and why
- [Reproducing the validated countywide evidence](#reproducing-the-validated-countywide-fema--water-evidence)
- [Environment](#environment) and [C++ builds](#c-builds)
- [Repository map](#repository-map)
- [Known limitations](#current-known-limitations) — read before quoting a figure
- [`docs/evidence_index.md`](docs/evidence_index.md) — claim → artifact → field
- [`docs/milestones.md`](docs/milestones.md) — how the project got here
- [The report](docs/report/report.pdf) — the capstone write-up, and its [LaTeX body](docs/report_draft.txt)

## The three evidence families

1. **FEMA flood-hazard evidence** — flood-zone and Special Flood Hazard Area membership, with canonical feature identity via `FLD_AR_ID`.
2. **Nearest-water evidence** — distance to the nearest mapped USGS hydrographic feature, with deterministic feature identity, classification, and tie count.
3. **Terrain evidence** — elevation, local mean elevation, relative elevation, and local slope from a projected DEM.

These feed a separate, explicitly weighted **preliminary relative exposure
index**. The boundary between evidence and scoring is enforced in the artifacts:
the evidence manifest carries `scoring_included: false`. Validated source
evidence stays reusable if the scoring methodology changes.

The central engineering goals are correct spatial computation, explicit CRS
handling, deterministic outputs, independent Python/C++ validation, provenance,
reproducibility, and scalable countywide processing.

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

A precipitation evidence family was scoped and not built; see
[Scoped and not built](#scoped-and-not-built).

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

cpp/spatial_core/          CMakeLists.txt builds all fourteen binaries
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
                           - spatial correlation, blocked split, leakage gate
                           - neural surrogate (data, training, evaluation)
                           - error analysis against the registered prediction
                           - inference and pipeline cost measurement

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
                           - evidence_index.md   claim -> artifact -> field
                           - milestones.md       what each milestone delivered
                           - errata.md           report vs repository
                           - canon/              long-form working record

LICENSE                    MIT. The ingested public datasets are not covered
                           by it; their terms are in docs/data_sources.md.
pyproject.toml             Installs caprm from python/ and configures pytest.
.github/workflows/         CI: Python suite, plus all fourteen C++ binaries
                           and the native invariant suites under ctest.
```

## Outputs

Products, by family. Sizes are countywide.

```text
outputs/baseline/       Python reference computations          ~250 MB
outputs/cpp_input/      Projected, flattened C++ input tables   ~75 MB
outputs/cpp/            C++ per-property outputs               ~250 MB
outputs/evidence/       FEMA/water and terrain evidence        ~100 MB
outputs/index/          Exposure index and countywide rank
outputs/benchmark/      Timing run tables                     tracked
outputs/validation/     Manifests, summaries, agreement        tracked
                        reports, and the published benchmark   (manifests
                        tables                                  only)
outputs/figures/        Report and poster figures             tracked
models/                 water_hilbert_rmi.bin  (4,194,400 B)  tracked
```

`outputs/` is ignored wholesale; the manifests and timing tables are tracked
explicitly. [`docs/evidence_index.md`](docs/evidence_index.md) lists every
tracked artifact against the claim it establishes, and every untracked one
against the command that regenerates it.

`b6_analysis.json` and `b6_benchmark_tables.md` are generated by
`python/scripts/analyze_b6_results.py` and must not be hand-edited. Every
derived number in the benchmark tables is computed there and nowhere else, so an
analysis performed in conversation is not reportable until it lands in that
script with a test.

Two C++ input files differ by one prefix and are not interchangeable:

```text
outputs/cpp_input/water_properties_projected_countywide.csv   water family
    sample_order,property_id,projected_x,projected_y
outputs/cpp_input/properties_projected_countywide.csv         FEMA family
    different schema, no sample_order
```

The water binaries reject the FEMA export rather than misreading it.

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
python -m pytest -q
656 passed
```

No flags are required. Python 3.14.0; every dependency including `scipy` is pinned in `requirements.txt`.

## C++ builds

These five lines are the verified path. They produced every binary behind every
measurement in this repository, and they were re-run against the current source
on 2026-08-24 with g++ 15.2.0 (MSYS2): all five compile clean under
`-Wall -Wextra`.

```powershell
g++ -std=c++17 -O2 cpp/spatial_core/src/fema_pip_dev.cpp -o cpp/spatial_core/build/fema_pip_dev.exe
g++ -std=c++17 -O2 cpp/spatial_core/src/water_distance_bruteforce.cpp -o cpp/spatial_core/build/water_distance_bruteforce.exe
g++ -std=c++17 -O2 cpp/spatial_core/src/water_distance_indexed.cpp -o cpp/spatial_core/build/water_distance_indexed.exe
g++ -std=c++17 -O2 -Wall -Wextra cpp/spatial_core/src/water_distance_segment_bvh.cpp -o cpp/spatial_core/build/water_distance_segment_bvh.exe
g++ -std=c++17 -O2 -ffp-contract=off -Wall -Wextra cpp/spatial_core/src/water_distance_hilbert.cpp -o cpp/spatial_core/build/water_distance_hilbert.exe
```

The two native invariant suites, which have no Python counterpart to compare
against:

```powershell
g++ -std=c++17 -O2 -Wall -Wextra tests/cpp/test_water_segment_bvh.cpp -o cpp/spatial_core/build/test_water_segment_bvh.exe
g++ -std=c++17 -O2 -Wall -Wextra tests/cpp/test_water_segment_bvh_verify_modes.cpp -o cpp/spatial_core/build/test_water_segment_bvh_verify_modes.exe
```

Both pass as of 2026-08-24: 80,021 checks and 607 checks respectively, 0
failures. The first includes 100,000 randomized field-for-field trials against
the brute-force kernel across two split caps.

### CMake

`cpp/spatial_core/CMakeLists.txt` builds all fourteen binaries plus the two
suites under `ctest`, including the nine `SEED_WINDOW` variants behind a
`seed_window_sweep` target.

```powershell
cmake -S cpp/spatial_core -B cpp/spatial_core/cmake-build -DCMAKE_BUILD_TYPE=Release
cmake --build cpp/spatial_core/cmake-build --parallel
cmake --build cpp/spatial_core/cmake-build --target seed_window_sweep --parallel
ctest --test-dir cpp/spatial_core/cmake-build --output-on-failure
```

**It has not been executed.** CMake is not installed on the machine this
repository was developed on, so the file is unverified. Use the direct `g++`
lines above if you want the path that is known to work.

The ladder is five separate translation units rather than a library, and
deliberately so. Each source `#include`s the one below it, so the distance
kernel and the tie rule are reused rather than reimplemented — which is what
makes adjacent rungs differ by exactly one variable. Linking them together
would defeat that.

Two compile settings are load-bearing rather than stylistic:

- `-ffp-contract=off` on the Hilbert binary. It changes nothing on baseline
  SSE2, but a `-march=native` build on Haswell or later can contract `a + b*x`
  into a fused multiply-add and shift the RMI's normalized input. The manifest
  probe catches that at load; the flag prevents it.
- `CAPRM_SEED_WINDOW` as a compile-time definition. B6b built nine binaries
  across nine windows and verified byte-neutrality at every one — after a first
  attempt passed the neutrality gate on binaries whose source never referenced
  the macro. A neutrality gate requires a positive control.

Use the same compiler and optimization settings when comparing benchmark runs.
Every published figure was taken at `-O2` with these flags.

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

## Milestone 4 Phase C workflow entry points

Phase C asks whether the pipeline's own output can be predicted from
coordinates alone. Its result is negative, and the order below is the order that
makes the negative reportable: the partition is built and gated *before* any
model exists, and the prediction about error structure is registered in C2's
artifact *before* C3 runs.

```powershell
# C1. The supervised dataset, the correlation study that sets the buffer width,
#     and the blocked K-fold partition with its leakage gate.
.\.venv\Scripts\python.exe python\scriptsuild_supervised_dataset.py
.\.venv\Scripts\python.exe python\scripts\measure_spatial_correlation.py
.\.venv\Scripts\python.exe python\scriptsuild_spatial_kfold.py
```

The gate requires both negative controls to FAIL. A partition that passes
alongside its controls has not demonstrated anything, and
`c1_kfold_manifest.json` records `controls.blocked_unbuffered.failed_as_expected`
so the check is visible rather than assumed.

```powershell
# C2. Train against that partition and against the random control.
.\.venv\Scripts\python.exe python\scripts	rain_surrogate.py --tag headline

# C3. Error analysis against the prediction registered in C2's manifest.
.\.venv\Scripts\python.exe python\scriptsnalyze_c3_residuals.py

# C4. Inference cost, then the exact pipeline's own cost.
.\.venv\Scripts\python.exe python\scriptsenchmark_c4_inference.py --blas-threads 8
.\.venv\Scripts\python.exe python\scriptsenchmark_c4_pipeline.py --workloads 10000 100000
.\.venv\Scripts\python.exe python\scriptsenchmark_c4_pipeline.py --workloads countywide
```

The pipeline harness writes every stage output under `outputs/scratch/c4/` and
asserts it is there before the stage runs, so a timing run cannot touch a frozen
product, manifest or fixture.

Reusable implementation:

```text
python/caprm/spatial_correlation.py
python/caprm/spatial_split.py
python/caprm/spatial_kfold.py
python/caprm/split_gate.py
python/caprm/supervised_dataset.py
python/caprm/surrogate.py
python/caprm/surrogate_data.py
python/caprm/surrogate_run.py
python/caprm/error_analysis.py
python/caprm/c4_benchmark.py
python/caprm/c4_analysis.py
python/caprm/pipeline_cost.py
```

Tests:

```text
tests/test_spatial_correlation.py   tests/test_surrogate.py
tests/test_spatial_split.py         tests/test_surrogate_data.py
tests/test_spatial_kfold.py         tests/test_surrogate_run.py
tests/test_split_gate.py            tests/test_error_analysis.py
tests/test_supervised_dataset.py    tests/test_c4_benchmark.py
tests/test_pipeline_cost.py         tests/test_c4_analysis.py
```

## Project status

All four milestones are complete. The capstone report is written, submitted, and
accepted. No measurement remains open.

```text
Milestone 1   FEMA point-in-polygon foundation                  complete
Milestone 2   nearest-water evidence, countywide scaling        complete
Milestone 3   terrain evidence, exposure index, audit           complete, frozen
Milestone 4   Phase B, five-rung indexing ladder                complete
              Phase C, surrogate feasibility                    complete
```

[`docs/milestones.md`](docs/milestones.md) records what each milestone delivered.

### Scoped and not built

These were identified, ranked, and left undone deliberately. Each is listed here
rather than omitted, because a reader is entitled to know where the line was
drawn.

- **Rung 6, the learned radius.** Seeding the search disk from a learned
  distance field, making the approximate answer load-bearing for the exact one.
  Phase C's finding removes its premise: a coordinates-only surrogate is not
  separable from a constant predictor, so it has no distance field to offer.
- **The index-size axis.** Every workload here varies query *count* at a fixed
  1,189,589-entry index. The learned-index literature's central claim is that
  the advantage grows with index size, and this project does not test it. Doing
  so needs a defensible hydrography subsetting scheme, a reference recomputed at
  each subset, and the model retrained at each N.
- **The segment hierarchy in production.** It is 6.90x faster and equally exact,
  and it is not what produced the shipped evidence. Adopting it would require
  regenerating and revalidating every downstream product. The manifest records
  which implementation ran; see [Known limitations](#current-known-limitations).
- **Precipitation as a fourth evidence family.** Outranked rather than
  cancelled. It adds ingestion, provenance and validation work and no
  algorithmic content, and the project's identified weakness was that its
  computer-science contribution had stalled.

## Documentation

Start here:

- [**Evidence index**](docs/evidence_index.md) — every published claim, the file
  that establishes it, and the field within that file. Also lists what is not
  tracked, beside the command that regenerates it.
- [**Milestone history**](docs/milestones.md) — what each milestone delivered.
- [**Errata**](docs/errata.md) — every published figure was re-checked against
  the artifact carrying it after submission. Three discrepancies are recorded
  there; the rest reconciled exactly.
- [**The report**](docs/report/report.pdf) — the capstone write-up. The
  [LaTeX body](docs/report_draft.txt) is tracked beside it; it is the body
  only, without preamble or bibliography, and does not compile standalone. See
  [`docs/errata.md`](docs/errata.md).

Methods and policy:

- [Scoring methodology](docs/scoring_methodology.md)
- [Validation](docs/validation.md)
- [Benchmark results](docs/benchmark_results.md)
- [Data sources](docs/data_sources.md)
- [CRS policy](docs/crs_policy.md)
- [Milestone 1](docs/milestone_1.md), [Milestone 2](docs/milestone_2.md), [Milestone 3](docs/milestone_3.md)

The three canonical documents under `docs/canon/` record durable architecture,
implementation state, and the roadmap as it stood during development. They are
long-form working documents rather than a reader's entry point, and each carries
a header stating what it is current through.

Where any two sources conflict, prefer the generated artifacts first, then this
README, then the canonical documents.

## Scope and interpretation

CAPRM-Flood produces transparent property-level geospatial exposure evidence and a relative regional exposure index.

The current index is intended for comparative screening and analysis. It does not currently claim calibrated flood probability, expected financial loss, insurance pricing, or actuarial-grade risk.

## Current known limitations

- The exposure index remains **preliminary**. It is frozen and characterized as moderately sensitive to weight choice, not calibrated.
- **The shipped evidence was not produced by the fastest validated implementation.** The evidence table was generated and validated under the feature-level hierarchy, recorded in its manifest as `water_validation.algorithm: feature_bvh`. The segment-level hierarchy is equally exact and 6.90x faster. Adopting it would require regenerating and revalidating every downstream product, which was not undertaken. The manifest says which implementation ran, so no figure derived from that table is ambiguous about its provenance.
- **The artifact audit returns one warning, and it is not suppressed.** Two manifest key conventions coexist across the products: the flood-evidence manifest nests its summary under one key, the terrain and index manifests under another. Any tool reading manifests generically must handle both. The audit records this as a warning rather than a failure because nothing is wrong with any individual artifact; what is wrong is that they are not uniform.
- **One county, one set of dataset vintages, one machine.** The relative ordering of index designs is a measurement over this workload on this hardware. The seed-window dependence reported above is precisely a demonstration that such orderings move with configuration, so it should not be read as a general ranking of index designs.
- Precipitation evidence was scoped and deliberately not built. It adds a fourth source family with no algorithmic content, and was outranked by the Milestone 4 computational work.
- Memory is measured per rung on three instruments that disagree in direction, and none may be quoted alone (Nucleus 18.24). Countywide, on persistent structure the Hilbert path is 8.74x smaller than the segment BVH — a 9,516,712-byte key array plus a 4,194,400-byte model against 119,768,836 bytes of BVH; on peak resident memory the segment BVH is 1.25x smaller; on peak committed memory the Hilbert path is 1.20x smaller. Peak resident memory is the wrong instrument for a model's size cost specifically, because the peak occurs during index construction before the model is loaded. A ~160 MB transient in the Hilbert path's resident peak is constant across a 27x range of query count, which places it in index construction, and remains unattributed beyond that.
- **Wall-clock figures follow B6a's repetition protocol** — 3+1 warm-up at rung 1 and 7+1 at rungs 2-5, blocked by repetition and cyclically rotated by block index, with dispersion reported as min/median/max and relative spread always. Absolutes move about 1 percent between invocations while adjacent ratios agree to 0.116 percentage points, so ratios are reported within an invocation and absolutes with their invocation named. `brute_force@countywide` carries a 31.71 percent spread at n=3, five times any other cell, so its figure is an order-of-magnitude statement and rung 1 appears in no adjacent comparison.
- C++ `computation_seconds` includes geometry queries, CSV row writing, and progress logging; query-only and output-only time are not separated.
- Runs carrying `--verify-counts`, `--uncapped-half` or `--seed-error-stats` are not benchmark-eligible: each adds work per property. `--query-stats` is free and is eligible.
- **The Milestone 4 negative result is measured at one index size**, 1,189,589 entries. The `_10000`/`_100000`/`_countywide` workloads vary query COUNT, not index size: the exporter writes the whole feature table regardless of the property set, so all three build the identical index. The learned-index literature's central claim is that the advantage grows with index size, and this project does not test that; a true index-size axis needs a defensible hydrography subsetting scheme, a reference recomputed at each subset, and the model retrained at each N. It is deferred as a stretch chunk.
- Below roughly twelve thousand properties the Hilbert path spends more time constructing its index than using it. Index construction is 0.912181 s and is constant across every workload while query cost is linear in the property count, so build equals query at Q = 12,301 under original-geometry verification and Q = 24,749 under split. Any end-to-end claim about this path states whether construction is included, and at what query count.
- **The Python pipeline's per-property cost is not constant in workload size, so its marginal cost cannot be quoted as a single number.** Measured at three workloads under a boundary declared in source before the first run, `nearest_water_python` costs 780.9, 1234.2 and 1232.7 us/property at 10K, 100K and countywide. Three of the four stages fit a negative fixed cost, which is not physical and is what a straight line does when asked to reach points whose per-unit cost is still rising. The `a + b*N` fits are published with their residuals in `docs/c4_inference_tables.md`; `b` is a slope through three points that do not lie on one line, and is not a marginal cost on its own.
- The C++ path does not itself verify the trained model's training-array SHA-256; it verifies a fingerprint (array length, five sampled keys, and the full inference chain) while the trainer verifies the digest. The provenance chain closes across the two languages but not inside either alone.
- **The C++ build is not covered by the Python suite, and one native test suite was silently broken because of it.** `tests/cpp/test_water_segment_bvh.cpp` failed to compile from the B2 verification-mode fork until 2026-08-24, because the query signature gained three parameters and the test was not updated. Nothing detected it: `pytest` does not build C++, and the native suites were compiled by hand. Both suites now build and pass, and the CI workflow builds them on every push, but the underlying asymmetry remains — a C++ change can break a C++ test without any Python test noticing.
- The C++ ladder is deliberately not a reusable library: each rung is its own translation unit that `#include`s the one below it, which is what keeps the kernel and tie rule shared. The primary correctness claim rests on field-by-field comparison against the Python reference; the two native suites cover geometric invariants that have no Python counterpart.
- Public ArcGIS, FEMA, USGS, and future NOAA source data can change; manifests and checksums identify the exact cached inputs used for reported results.