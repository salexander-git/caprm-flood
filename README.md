# CAPRM-Flood

CAPRM-Flood is a reproducible C++/Python geospatial feature-extraction framework for property-level flood-exposure evidence. The current implementation covers Monroe County, New York and produces two independently validated evidence families:

1. FEMA flood-zone and Special Flood Hazard Area membership.
2. Nearest-water distance from USGS 3D Hydrography Program features.

The project is a feature-extraction and benchmarking system. It is not an actuarial model, flood-loss predictor, insurance-pricing tool, hydrologic simulation, or final composite risk score.

## Milestone status

Milestone 2 is computationally complete:

- deterministic 1K, 10K, 100K, and countywide property workloads;
- Python GeoPandas/Shapely reference implementations;
- independent C++ FEMA point-in-polygon and nearest-water implementations;
- brute-force and feature-BVH nearest-water algorithms;
- strict Python/C++ validation at every scale;
- reproducible benchmark harness and summaries;
- integrated FEMA-plus-water property evidence;
- complete countywide application to 267,362 unique property identifiers;
- 55 passing Python tests.

The countywide indexed nearest-water implementation reproduced all 267,362 Python results within a maximum absolute distance error of `4.658e-10 m`. In the canonical one-run countywide benchmark, the feature BVH was `20.39x` faster in reported computation time and `19.83x` faster in total process time than brute force.

## Architecture

```text
Public geospatial sources
        |
        v
Python ingestion, validation, CRS normalization, and caching
        |
        +--> Python trusted FEMA and nearest-water references
        |
        +--> deterministic projected C++ input tables
                    |
                    v
          Independent C++ spatial computation
          - FEMA point-in-polygon
          - brute-force nearest water
          - feature-BVH nearest water
                    |
                    v
          strict Python/C++ comparison
                    |
                    v
          benchmark summaries and integrated evidence
```

Python owns public-data access, configuration, CRS transformation, reference calculations, fixture generation, comparison, benchmarking orchestration, evidence integration, and manifests. C++ owns the independently implemented geometry kernels and indexed query execution.

## Repository map

```text
configs/                   Workload-specific YAML configurations
cpp/spatial_core/src/      C++ FEMA and nearest-water implementations
python/caprm/              Reusable Python ingestion, geometry, validation,
                           benchmark, and evidence modules
python/scripts/            Command-line workflow entry points
tests/                     Python unit and integration tests
data/                      Cached source and deterministic property data
outputs/baseline/          Python reference outputs
outputs/cpp_input/         Projected and flattened C++ inputs
outputs/cpp/               C++ property-level outputs
outputs/benchmark/         Per-run benchmark records
outputs/validation/        Manifests, summaries, and agreement reports
outputs/evidence/          Integrated FEMA-plus-water evidence tables
docs/                      Milestone methods, results, and limitations
```

## Core outputs

Countywide outputs:

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

## Environment

The tested Python dependencies are pinned in `requirements.txt`. From PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Latest test result:

```text
55 passed in 1.06s
```

## C++ builds

The current repository uses direct executable builds rather than CMake. A representative GNU C++ build from the repository root is:

```powershell
g++ -std=c++17 -O2 cpp/spatial_core/src/fema_pip_dev.cpp -o cpp/spatial_core/build/fema_pip_dev.exe
g++ -std=c++17 -O2 cpp/spatial_core/src/water_distance_bruteforce.cpp -o cpp/spatial_core/build/water_distance_bruteforce.exe
g++ -std=c++17 -O2 cpp/spatial_core/src/water_distance_indexed.cpp -o cpp/spatial_core/build/water_distance_indexed.exe
```

Use the same compiler and optimization settings when comparing benchmark runs.

## Reproducing the countywide evidence from existing caches

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

## Documentation

- [Milestone 2](docs/milestone_2.md)
- [Benchmark results](docs/benchmark_results.md)
- [Data sources](docs/data_sources.md)
- [CRS policy](docs/crs_policy.md)
- [Validation](docs/validation.md)
- [Milestone 1](docs/milestone_1.md)

## Current limitations

- No composite exposure score, percentile, loss estimate, or insurance interpretation is produced.
- Benchmark peak memory is not measured.
- C++ `computation_seconds` includes geometry queries, CSV row writing, and progress logging; query-only and output-only time are not separated.
- The 100K and countywide benchmarks use one measured repetition and no warmup because brute force is expensive.
- The 1K benchmark used an earlier 4,159-feature hydrography fixture; the 10K, 100K, and countywide benchmarks use the final 8,572-feature cache.
- The C++ source is functional but not yet organized as a reusable CMake library with native C++ unit tests.
- Public ArcGIS services and FEMA/USGS data can change; manifests and checksums identify the exact cached inputs used for the reported results.
