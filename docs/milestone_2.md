# Milestone 2: Indexed Nearest-Water Evidence and Countywide Integration

## Objective

Milestone 2 adds a second independently validated geospatial feature family and moves CAPRM-Flood from a prototype spatial join into a benchmarkable system:

> Implement and validate property-to-water nearest-distance extraction in Python and C++, introduce spatial indexing and a reproducible benchmark harness, and produce an integrated property-level evidence table containing both FEMA and water-proximity features.

The milestone contributes:

- **feature breadth:** FEMA membership plus nearest-water distance;
- **systems depth:** exact C++ geometry with a feature-level bounding-volume hierarchy instead of an all-features linear search;
- **evaluation depth:** strict numerical agreement, deterministic edge-case behavior, operation counts, throughput, runtime, scaling, and countywide application.

## Deliverables

| Initial deliverable | Implemented artifact | Status |
|---|---|---|
| Official Monroe County hydrography | USGS 3DHP cache and checksum-backed manifest | Complete |
| Documented inclusion rules | Flowline and waterbody feature-type filters in configuration and manifest | Complete |
| Distance-valid CRS | EPSG:26918 for all nearest-water calculations | Complete |
| Python nearest-water reference | Shapely STRtree baseline with deterministic ties and provenance | Complete |
| Independent C++ nearest geometry | Exact point-to-segment and point-to-polygon calculations | Complete |
| C++ spatial index | Feature BVH with bounding-box lower-bound pruning | Complete |
| 1K correctness comparison | Full-field Python/C++ agreement | Complete |
| Synthetic/targeted edge cases | Distance, waterbody interior, hole, tie, validation, cache, and export tests | Complete |
| Benchmarks at 1K, 10K, and 100K | Canonical run CSVs and JSON summaries | Complete |
| Indexed versus brute-force comparison | Direct measured comparisons through countywide scale | Complete |
| Integrated FEMA-plus-water output | Property evidence CSV and provenance manifest | Complete |
| All available Monroe County property IDs | 267,362 unique `SBL` records | Complete |
| Milestone documentation | README and Milestone 2 method/result documents | Complete |

## Data and workloads

### Hydrography

The final cache contains:

```text
8,572 features
5,600 retained flowlines
2,972 retained waterbodies
1,072,254 vertices
1,063,159 segments
```

It covers the official Monroe County boundary plus a 20 km metric buffer. The nearest-water reference requires every accepted distance to be strictly below the buffer, proving that a feature outside the cached study area cannot be closer for a property covered by the county polygon.

### Deterministic property workloads

The immutable 1K regression cache is preserved exactly. The 10K and 100K workloads retain it as an ordered prefix and append the first unique nonmissing `SBL` records encountered in ascending ArcGIS `OBJECTID` order.

The countywide workload preserves the entire validated 100K workload as its exact prefix, then scans all remaining source rows and appends each previously unseen canonical `SBL` once.

Countywide source accounting:

```text
267,414 matching ArcGIS object IDs
267,362 selected unique SBL values
52 duplicate SBL rows excluded
0 missing canonical IDs excluded
```

These workloads are deterministic computational fixtures. The 1K, 10K, and 100K sets are not claimed to be random or statistically representative property samples.

## Python reference implementation

The Python nearest-water reference:

1. verifies the hydrography cache checksum and manifest;
2. projects property and hydrography geometry to EPSG:26918;
3. builds a Shapely STRtree;
4. requests all equally nearest geometries;
5. computes exact point-to-feature distances;
6. assigns zero distance inside a waterbody polygon while respecting holes;
7. resolves equal-distance ties deterministically by canonical water feature ID;
8. preserves feature class, type, source identifiers, name, tie count, CRS, and projected coordinates;
9. rejects a result that cannot satisfy the 20 km cache-completeness proof.

Python is the trusted behavioral reference, not the system being performance-evaluated.

## Independent C++ implementations

### Brute force

For each property, the brute-force implementation evaluates every water feature, computes exact distance to its line segments or polygon rings, applies waterbody interior/hole semantics, and selects the same deterministic canonical nearest feature used by Python.

### Feature BVH

The indexed implementation builds an axis-aligned bounding-volume hierarchy over feature bounding boxes. Query traversal uses each node's minimum possible point-to-box distance as a lower bound. Nodes and features that cannot improve or tie the current best result are pruned; exact geometry distance is evaluated only for surviving candidates.

The BVH uses a leaf size of eight features. Both implementations share the same exact geometry and tie-resolution semantics, making the comparison isolate search strategy rather than feature meaning.

## Correctness results

Every Python/C++ validation was a complete property-ID union comparison. Water validation checked distance tolerance, selected feature ID, class, type, source ID, source object ID, name, tie count, and CRS.

| Workload | FEMA full-field agreement | Brute-force water agreement | Indexed water agreement | Maximum water error |
|---:|---:|---:|---:|---:|
| 1,000 | 1,000/1,000 | 1,000/1,000 | 1,000/1,000 | `4.386e-10 m` |
| 10,000 | 10,000/10,000 | 10,000/10,000 | 10,000/10,000 | `4.637e-10 m` |
| 100,000 | 100,000/100,000 | 100,000/100,000 | 100,000/100,000 | `4.656e-10 m` |
| 267,362 | 267,362/267,362 | 267,362/267,362 | 267,362/267,362 | `4.658e-10 m` |

The final Python test suite reported:

```text
55 passed in 1.06s
```

## Benchmark results

Canonical benchmark summaries were produced by `python/scripts/benchmark_water_cpp.py`, which alternates algorithm order for repeated trials, records executable checksums, parses executable-reported metrics, and measures subprocess wall-clock duration.

| Workload | Trials / warmups | Brute computation | BVH computation | Computation speedup | Brute total | BVH total | Total speedup | Segment reduction |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1K | 7 / 1 | 2.333 s | 0.101 s | 23.11x | 3.190 s | 0.968 s | 3.29x | 95.21% |
| 10K | 7 / 1 | 48.945 s | 1.024 s | 47.80x | 50.285 s | 2.337 s | 21.52x | 96.80% |
| 100K | 1 / 0 | 395.093 s | 31.231 s | 12.65x | 396.580 s | 32.633 s | 12.15x | 89.35% |
| Countywide | 1 / 0 | 1,139.744 s | 55.892 s | 20.39x | 1,141.386 s | 57.567 s | 19.83x | 93.34% |

The countywide BVH considered an average of `5.498` candidate features per property, or approximately `0.0641%` of the 8,572-feature collection. It reduced exact segment checks from `284,248,316,558` to `18,921,369,157`.

The speedup is workload-dependent rather than monotonic because the number and complexity of surviving geometries vary with property location. The 1K benchmark also used an earlier 4,159-feature hydrography fixture and should not be treated as a directly comparable point on the final-cache scaling curve.

See `docs/benchmark_results.md` for methodology and limitations.

## Integrated countywide evidence

The final evidence table contains one row per countywide canonical property ID and combines:

- source coordinates and both projected coordinate pairs;
- FEMA polygon match, zone, SFHA flag, stable source feature ID, and feature index;
- nearest-water distance, canonical feature ID, class, type, source IDs, name, and tie count;
- explicit CRS fields.

Countywide evidence summary:

```text
267,362 properties
267,358 matched to a FEMA polygon
4 unmatched FEMA properties
5,061 SFHA properties
262,301 non-SFHA properties
266 properties at zero water distance
308 multiple-nearest ties
2,934 distinct selected nearest-water features
median nearest-water distance: 325.346 m
mean nearest-water distance: 506.411 m
maximum nearest-water distance: 2,630.235 m
```

FEMA zone counts:

```text
X: 262,297
AE: 4,226
A: 408
AO: 388
VE: 39
missing: 4
```

Primary artifacts:

```text
outputs/evidence/property_flood_evidence_countywide.csv
outputs/validation/property_flood_evidence_countywide_manifest.json
```

The evidence manifest records input checksums, validation summaries, benchmark summary, output checksum, schema, CRS values, and aggregate evidence statistics.

## Completion assessment

Milestone 2 meets its minimum target and its central halfway-point claims:

- two principal exposure-feature families are implemented;
- both are independently reproduced in Python and C++;
- the indexed C++ search avoids all-feature distance calculation;
- complete countywide evidence is generated in one integrated table;
- correctness and performance artifacts are reproducible and checksum-backed.

## Explicit limitations and deferred goals

The following are not claimed as completed:

- **Peak memory:** not measured.
- **Query-only versus output-only timing:** not separated. C++ `computation_seconds` includes exact query work, CSV row writing, and progress logging.
- **Repeated large-scale trials:** 100K and countywide use one measured repetition and no warmup.
- **Stable packaged C++ library:** the current sources compile into working executables but are not organized through CMake or native C++ unit tests.
- **Scoring path:** no normalized component score, composite exposure index, percentile, or sensitivity analysis is included.
- **Additional feature families:** elevation/terrain and precipitation remain later work.
- **One-million-property benchmark:** impossible with unique Monroe County `SBL` records and would require synthetic replication or a larger region.

These limitations do not invalidate the Milestone 2 correctness or indexed-search claims, but they constrain broader performance and product claims.
