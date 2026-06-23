# Validation

## Validation contract

CAPRM-Flood treats Python GeoPandas/Shapely calculations as trusted geospatial references and evaluates independently implemented C++ results against them before making systems-performance claims.

Validation requires:

- complete property-ID coverage;
- no missing Python or C++ rows;
- exact categorical and identifier agreement;
- documented numerical tolerance for distance;
- explicit CRS agreement;
- nonzero exit status when the comparison contract fails.

## FEMA validation

The FEMA comparison aligns results by canonical `property_id` and checks:

```text
matched_fema_polygon
is_sfha / cpp_sfha_result
fema_zone
fema_feature_index
```

The feature-index check is intentionally stricter than Boolean SFHA agreement. It verifies that Python and C++ selected the same exported FEMA source feature.

### Results

| Workload | Rows | Coverage | All-field agreement |
|---:|---:|---:|---:|
| 1K | 1,000 | 100% | 1,000/1,000 |
| 10K | 10,000 | 100% | 10,000/10,000 |
| 100K | 100,000 | 100% | 100,000/100,000 |
| Countywide | 267,362 | 100% | 267,362/267,362 |

The countywide comparison includes the four properties unmatched by both implementations.

## Nearest-water validation

The water comparison aligns the union of Python and C++ property IDs and checks:

```text
nearest-water distance within 1e-6 m
canonical nearest feature ID
feature class
feature type
source feature ID
source object ID
feature name
multiple-nearest tie count
distance CRS
```

Both C++ algorithms are validated independently against Python.

### Results

| Workload | Brute-force agreement | Indexed agreement | Maximum absolute error |
|---:|---:|---:|---:|
| 1K | 1,000/1,000 | 1,000/1,000 | `4.386e-10 m` |
| 10K | 10,000/10,000 | 10,000/10,000 | `4.637e-10 m` |
| 100K | 100,000/100,000 | 100,000/100,000 | `4.656e-10 m` |
| Countywide | 267,362/267,362 | 267,362/267,362 | `4.658e-10 m` |

The observed errors are approximately four orders of magnitude below the `1e-6 m` acceptance tolerance.

## Geometry semantics

### FEMA polygons

- Python uses `within` semantics.
- C++ reconstructs feature parts and rings.
- Exterior rings include the feature interior.
- Interior holes are excluded.
- Feature bounding boxes prefilter impossible matches.

### Water lines and polygons

- Line distance is the minimum exact point-to-segment distance.
- A property inside a waterbody polygon has distance zero.
- A point inside a polygon hole is not treated as inside water.
- Polygon boundary and segment distance are handled by the same exact geometry kernel in brute force and BVH search.
- Equal-distance nearest features are retained for tie counting and resolved by deterministic canonical feature ID order.

## Cache and workload validation

The data pipeline validates:

- immutable 1K regression-cache checksum;
- exact nested prefixes for 10K, 100K, and countywide workloads;
- unique canonical `SBL` values;
- contiguous `sample_order`;
- finite Point geometry;
- current-source overlap and coordinate drift within `1e-9` degrees;
- hydrography checksum and CRS agreement;
- reference-to-export property and feature alignment;
- expected feature, vertex, and segment counts across benchmark trials.

The countywide cache retained all 267,362 unique current-source `SBL` values and matched all 100,000 validated-prefix coordinates within tolerance.

## Automated tests

The Python test suite covers:

- FEMA baseline and comparison behavior;
- deterministic ingestion, ArcGIS batching, retry logic, duplicate IDs, and cache validation;
- county study-area retrieval and caching;
- hydrography inclusion, cache, and geometry behavior;
- nearest-water distance, ties, waterbody interiors, holes, and completeness;
- C++ input flattening and alignment;
- strict water comparison logic;
- benchmark output parsing and summary generation;
- integrated evidence schema and provenance requirements;
- larger and countywide workload construction.

Final result:

```text
55 passed in 1.06s
```

## Evidence integration gate

`build_property_evidence.py` refuses to build the integrated table unless:

- both FEMA and water baseline inputs exist;
- FEMA validation reports full agreement;
- indexed-water validation reports full agreement;
- the benchmark summary contains both `brute_force` and `feature_bvh` results;
- property IDs and required evidence fields align.

The resulting manifest stores validation-summary paths and checksums, benchmark metadata, output checksum, schema version, aggregate evidence statistics, and explicit confirmation that scoring is not included.

## Known limitations

- Agreement with Python validates implementation consistency; it is not independent ground-truth validation of FEMA or USGS source accuracy.
- Invalid FEMA source geometries were retained when baseline-referenced. Full agreement does not repair or certify those geometries.
- The `within` predicate excludes exact polygon-boundary points by definition. Boundary behavior should remain explicit if later requirements change to `covers` or another predicate.
- Peak memory is not validated or benchmarked.
- Large-scale benchmark timing has only one measured trial at 100K and countywide scale.
- The current C++ computation timer includes CSV output and progress logging.
- Property centroids can misrepresent parcel or building intersection with a hazard feature.
