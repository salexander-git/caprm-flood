# CRS Policy

## Purpose

CAPRM-Flood performs spatial joins and spatial lookups across public geospatial datasets. Every input layer must have its coordinate reference system inspected and normalized before spatial operations are performed.

## Milestone 1 CRS Behavior

Milestone 1 uses two spatial inputs:

```text
NYS Tax Parcel Centroid Points
FEMA NFHL S_FLD_HAZ_AR polygons
```

Observed CRS values during the Milestone 1 run:

```text
Property CRS before transform: EPSG:4326
FEMA CRS before transform: EPSG:4269
Project CRS: EPSG:3857
```

Both datasets are transformed to the project CRS before point-in-polygon testing.

## Project CRS for Milestone 1

The current project CRS is:

```text
EPSG:3857
```

EPSG:3857 is acceptable for the current milestone because the operation being validated is topological point-in-polygon membership, not a distance or area measurement.

## Longitude/Latitude Preservation

The pipeline preserves original geographic coordinates for reporting:

```text
longitude
latitude
```

It also writes projected coordinates used for spatial operations:

```text
projected_x
projected_y
```

This allows outputs to remain interpretable while ensuring the spatial operation uses a shared projected coordinate system.

## Later Distance Features

Future CAPRM-Flood features, especially nearest-water distance and elevation/terrain-derived calculations, should not rely on EPSG:3857 for final metric distance calculations.

For later distance-sensitive work, the project should use a local projected CRS appropriate for Monroe County, New York, or explicitly document the distortion implications of the selected CRS.

## Required Logging

Every pipeline run should record:

```text
original property CRS
original FEMA CRS
project CRS
whether transformation occurred
output coordinate fields
```

## Current Implementation

CRS inspection and transformation currently occur in:

```text
python/scripts/run_fema_baseline.py
python/scripts/export_cpp_inputs.py
```

The C++ implementation assumes its inputs are already projected into a shared coordinate system. CRS handling remains the responsibility of the Python ingestion/export pipeline for Milestone 1.
