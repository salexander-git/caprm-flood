# Milestone 1

## Goal

Establish the minimum viable CAPRM-Flood spatial feature-extraction pipeline.

## Target Workflow

1. Load Monroe County property points.
2. Load FEMA flood-hazard polygons.
3. Inspect and normalize CRS.
4. Run a Python GeoPandas/Shapely point-in-polygon spatial join.
5. Produce a minimal CSV with property-level FEMA flood-zone membership.
6. Prepare the output schema for later C++ comparison.

## Target Output

`outputs/baseline/python_fema_membership.csv`

Minimum fields:
- property_id
- latitude
- longitude
- projected_x
- projected_y
- fema_zone
- sfha_flag
- source_geometry_id
- python_result

## Current Limitations

C++ comparison is not yet implemented.
Nearest-water, elevation, and precipitation features are not part of Milestone 1.