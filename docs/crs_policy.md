# CRS Policy

## Principle

Every input layer must have a declared coordinate reference system, and all geometries participating in one spatial operation must be transformed to a shared CRS before that operation. The selected CRS must match the operation: topological membership and metric distance have different requirements.

## CRS roles

| Purpose | CRS | Use |
|---|---|---|
| Source/reporting coordinates | EPSG:4326 | Property longitude/latitude and cached web-service geometry |
| FEMA topology path | EPSG:3857 | Existing validated point-in-polygon implementation |
| Water-distance path | EPSG:26918 | Metric nearest-water calculation for Monroe County |
| FEMA source | EPSG:4269 | Observed CRS of local NFHL polygon input before transformation |
| Hydrography query | EPSG:26918 | County-plus-buffer spatial query and metric study-area construction |

## FEMA membership

Property points and FEMA flood-hazard polygons are transformed to EPSG:3857 before the `within` point-in-polygon operation.

EPSG:3857 is retained for this validated path because the result is topological membership rather than a metric distance or area. The project does not interpret EPSG:3857 coordinate differences as meters for exposure calculations.

Output preserves:

```text
longitude
latitude
fema_projected_x
fema_projected_y
fema_project_crs
```

## Nearest-water distance

All water distances are computed in:

```text
EPSG:26918 — NAD83 / UTM zone 18N
```

EPSG:26918 is a locally appropriate projected CRS for Monroe County and expresses planar distance in meters. Both properties and hydrography are transformed to this CRS before Python STRtree queries or C++ input export.

Output preserves:

```text
water_projected_x
water_projected_y
distance_crs
nearest_water_distance_m
```

EPSG:3857 must not be substituted for final distance values.

## Study-area buffer

The official county polygon is projected to EPSG:26918 before applying the 20,000 m outward buffer used to query hydrography. Buffering in a geographic CRS would be invalid because coordinate units would be degrees rather than meters.

## C++ boundary

C++ does not perform CRS discovery or transformation. Python exports already projected coordinates and records the CRS in manifests and output rows. Each C++ run must receive inputs generated for one shared CRS:

- FEMA C++ inputs: EPSG:3857;
- water C++ inputs: EPSG:26918.

Mixing projected inputs, mislabeled CRS values, or source longitude/latitude with metric geometry is a hard error.

## Validation requirements

A pipeline stage must reject or halt when:

- an input CRS is missing;
- configured and cached CRS metadata disagree;
- a hydrography cache checksum differs from its manifest;
- a C++ output reports a different distance CRS from the Python reference;
- property coordinates are nonfinite;
- a distance result is not provably complete within the configured cache buffer.

## Reporting policy

Every baseline, C++ export, validation summary, and integrated evidence manifest should record the relevant CRS. Documentation and presentation material must distinguish:

- geographic source/reporting coordinates;
- FEMA topological projection;
- metric water-distance projection.

A correct statement is:

> FEMA membership is computed after projecting both layers to a shared CRS. Nearest-water distance is computed separately in EPSG:26918 and reported in meters.

An incorrect statement is:

> All project distances are computed in EPSG:3857.

## Future features

Elevation, terrain, precipitation, and any future area/distance transformations must document their own native CRS, resampling or interpolation policy, target CRS, units, and distortion implications. They should not inherit the FEMA EPSG:3857 path merely because it already exists.
