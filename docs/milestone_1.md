# Milestone 1: FEMA Flood-Zone Membership Spike

## Goal

Milestone 1 establishes the minimum viable CAPRM-Flood spatial feature-extraction pipeline:

1. load Monroe County property points,
2. load FEMA flood-zone polygons,
3. normalize coordinate reference systems,
4. compute FEMA/SFHA membership using a Python GeoPandas/Shapely baseline,
5. compute the same membership using an independent C++ point-in-polygon implementation,
6. compare the Python and C++ outputs for correctness.

The purpose of this milestone is not to compute the full CAPRM-Flood exposure index. It isolates the first spatial feature: whether a property point falls inside a FEMA flood-hazard polygon and whether the matched polygon is marked as a Special Flood Hazard Area.

## Data Sources Used

### Property Points

Source: NYS Tax Parcel Centroid Points.

For the current spike, the pipeline queries a 1,000-record Monroe County sample from the NYS parcel centroid service. Each record provides a parcel/property identifier and point geometry.

### Flood-Zone Polygons

Source: FEMA National Flood Hazard Layer.

For Milestone 1, the pipeline uses the `S_FLD_HAZ_AR` flood-hazard polygon layer from the local FEMA NFHL shapefile extract.

## CRS Handling

The property service response is read as EPSG:4326.

The FEMA flood polygon shapefile is read as EPSG:4269.

Both layers are transformed to the project CRS, EPSG:3857, before spatial membership testing.

Observed run output:

```text
Property CRS before transform: EPSG:4326
FEMA CRS before transform: EPSG:4269
Project CRS: EPSG:3857
```

## Python Baseline

The Python baseline is implemented in:

```text
python/scripts/run_fema_baseline.py
```

It performs a GeoPandas spatial join between projected property points and projected FEMA flood-zone polygons.

Baseline output:

```text
outputs/baseline/python_fema_membership.csv
```

Core output fields:

```text
property_id
latitude
longitude
projected_x
projected_y
fema_zone
sfha_flag
is_sfha
source_geometry_id
fema_feature_index
matched_fema_polygon
python_sfha_result
```

The field `matched_fema_polygon` means the property point matched some FEMA flood-hazard-area polygon, including Zone X polygons. It does not by itself mean the point is in a Special Flood Hazard Area.

The field `is_sfha` is the FEMA-derived Boolean for Special Flood Hazard Area membership.

Python baseline summary:

```text
Total properties: 1000
Matched FEMA polygon: 1000
Unmatched FEMA polygon: 0
SFHA true: 241
SFHA false: 759
FEMA zones observed in property sample: AE, X
```

## C++ Prototype

The C++ point-in-polygon prototype is implemented in:

```text
cpp/spatial_core/src/fema_pip_dev.cpp
```

The C++ prototype reads projected property points and simplified FEMA polygon ring fixtures exported by Python.

Primary C++ inputs for the 1,000-property validation:

```text
outputs/cpp_input/properties_projected.csv
outputs/cpp_input/fema_polygon_rings_joined_sample.csv
```

C++ output:

```text
outputs/cpp/cpp_fema_membership_1000.csv
```

Core output fields:

```text
property_id
cpp_matched_fema_polygon
cpp_sfha_result
cpp_fema_zone
cpp_fema_feature_index
```

The prototype uses ring-based point-in-polygon testing with hole handling and a bounding-box prefilter for each FEMA feature.

## Python/C++ Validation

The comparison script is:

```text
python/scripts/compare_python_cpp_fema.py
```

It compares the Python baseline against the C++ output by property identifier.

Validation summary:

```json
{
  "total_cpp_rows": 1000,
  "total_joined_rows": 1000,
  "missing_python_rows": 0,
  "matched_agreements": 1000,
  "sfha_agreements": 1000,
  "zone_agreements": 1000,
  "feature_index_agreements": 1000,
  "all_fields_agree": 1000,
  "matched_agreement_rate": 1.0,
  "sfha_agreement_rate": 1.0,
  "zone_agreement_rate": 1.0,
  "feature_index_agreement_rate": 1.0,
  "all_fields_agreement_rate": 1.0
}
```

## Milestone 1 Result

Milestone 1 demonstrates that CAPRM-Flood can ingest property points and FEMA flood-zone polygons, normalize CRS, compute a Python FEMA/SFHA membership baseline, independently compute matching C++ point-in-polygon results, and validate 1000/1000 agreement between the two implementations.

## Current Limitations

The current validation uses a 1,000-record service-return sample, not a statistically representative sample of all Monroe County properties.

The C++ implementation is still a development prototype. It uses a per-feature bounding-box prefilter but does not yet use a full spatial index such as an R-tree.

Only the FEMA/SFHA membership feature is implemented in this milestone. Nearest-water distance, elevation/terrain, precipitation indicators, scoring, and percentile ranking are later milestones.
