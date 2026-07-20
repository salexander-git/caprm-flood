# CAPRM-Flood

CAPRM-Flood is a reproducible C++/Python geospatial evidence-extraction framework for large-batch property-level flood exposure analysis. The current case study covers Monroe County, New York and processes a countywide workload of **267,362 unique property identifiers**.

The project currently derives three geospatial evidence families:

1. **FEMA flood-hazard evidence** — flood-zone and Special Flood Hazard Area membership.
2. **Nearest-water evidence** — distance to the nearest mapped USGS hydrographic feature, with deterministic feature identity and classification.
3. **Terrain evidence** — property elevation, local mean elevation, relative elevation, and local slope derived from a projected digital elevation model.

These validated evidence products feed a separate, transparent **preliminary relative exposure index** with explicit component normalization, weights, and countywide ranking. The index is currently being hardened through sensitivity analysis and additional methodological validation.

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

### Milestone 3 — current phase

Milestone 3 has implemented:

- projected DEM preparation;
- countywide terrain evidence extraction;
- elevation, local mean elevation, relative elevation, and slope features;
- terrain provenance/manifest generation;
- preliminary deterministic exposure-index generation;
- index manifest generation;
- Milestone 3 result summarization;
- new terrain and scoring tests.

Current countywide terrain results:

```text
properties: 267,362
unique property IDs: 267,362
missing slope values: 0
elevation range: approximately 75.000–296.309 m
```

Current preliminary exposure-index results:

```text
properties: 267,362
unique property IDs: 267,362
index range: approximately 7.915–99.929
index mean: approximately 34.632
index median: approximately 33.728
```

The full Python test suite passed after the current Milestone 3 implementation.

Milestone 3 is not yet frozen as complete. Remaining work includes:

- scoring-methodology hardening;
- rank-based sensitivity analysis;
- terrain/index artifact auditing;
- final Milestone 3 regeneration;
- reproducibility/runbook documentation.

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
        |   - indexed nearest water
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
- indexed nearest-water computation.

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
                           - result summarization

tests/                     Python unit and integration tests

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
Full test suite passing as of 2026-07-15.
```

## C++ builds

The repository currently uses direct executable builds rather than CMake.

Representative GNU C++ builds from the repository root:

```powershell
g++ -std=c++17 -O2 cpp/spatial_core/src/fema_pip_dev.cpp -o cpp/spatial_core/build/fema_pip_dev.exe
g++ -std=c++17 -O2 cpp/spatial_core/src/water_distance_bruteforce.cpp -o cpp/spatial_core/build/water_distance_bruteforce.exe
g++ -std=c++17 -O2 cpp/spatial_core/src/water_distance_indexed.cpp -o cpp/spatial_core/build/water_distance_indexed.exe
```

Use the same compiler and optimization settings when comparing benchmark runs.

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

The exact finalized end-to-end Milestone 3 runbook will be documented after scoring hardening and sensitivity analysis are complete.

## Current roadmap

Immediate work:

1. reconstruct and document the exact current scoring behavior;
2. harden normalization, directionality, weighting, clipping, and missing-value policy;
3. implement rank-based scoring sensitivity analysis;
4. audit terrain and index products;
5. regenerate and freeze final Milestone 3 artifacts;
6. complete Milestone 3 reproducibility documentation.

After Milestone 3:

1. add precipitation as a separate evidence family;
2. validate precipitation evidence;
3. integrate precipitation into the scoring layer;
4. rerun full sensitivity and redundancy analysis;
5. freeze the final relative exposure-index methodology;
6. complete end-to-end engineering hardening and final academic deliverables.

## Documentation

Current repository documentation includes:

- [Milestone 2](docs/milestone_2.md)
- [Benchmark results](docs/benchmark_results.md)
- [Data sources](docs/data_sources.md)
- [CRS policy](docs/crs_policy.md)
- [Validation](docs/validation.md)
- [Milestone 1](docs/milestone_1.md)

Canonical July 15 project-context documents are maintained separately during the current handoff and should be added deliberately to the repository/project knowledge once finalized:

```text
CAPRM_Flood_Project_Nucleus_2026-07-15.md
CAPRM_Flood_Current_Status.md
CAPRM_Flood_Roadmap.md
Capstone_Proposal.pdf
Professor_Milestone_Requirements.txt
```

## Scope and interpretation

CAPRM-Flood produces transparent property-level geospatial exposure evidence and a relative regional exposure index.

The current index is intended for comparative screening and analysis. It does not currently claim calibrated flood probability, expected financial loss, insurance pricing, or actuarial-grade risk.

## Current known limitations

- The exposure-index methodology is still preliminary pending sensitivity analysis and final scoring-policy review.
- Precipitation evidence has not yet been added.
- Benchmark peak memory is not currently measured.
- C++ `computation_seconds` includes geometry queries, CSV row writing, and progress logging; query-only and output-only time are not separated.
- The 100K and countywide water benchmarks use one measured repetition and no warmup because brute-force execution is expensive.
- The C++ source is functional but is not yet organized as a reusable CMake library with native C++ unit tests.
- Public ArcGIS, FEMA, USGS, and future NOAA source data can change; manifests and checksums identify the exact cached inputs used for reported results.
