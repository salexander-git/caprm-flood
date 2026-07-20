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
| Terrain source | EPSG:4269 | Observed CRS of the USGS 3DEP DEM before transformation |
| Terrain path | EPSG:26918 | Metric raster sampling, local-neighborhood windows, and slope |

## Vertical datum

The horizontal CRSs above locate a property. They say nothing about elevation, and until terrain evidence existed the project had no vertical reference at all.

| Purpose | Datum | Use |
|---|---|---|
| Terrain elevation | NAVD88, EPSG:5703 | All elevation values, in meters |

Every elevation figure the project reports is NAVD88 meters, inherited from the USGS 3DEP source. This includes `terrain_elevation_m`, `terrain_local_mean_elevation_m`, and `terrain_relative_elevation_m`.

Relative elevation is a difference between two values in the same datum, so it is datum-independent. Absolute elevation is not.

Comparisons against external water levels require care. Lake Ontario's low-water datum is published in IGLD85, which is not NAVD88; the two differ by up to roughly a meter in the Great Lakes basin. Any statement relating a property elevation to a lake or river level must state which datum it uses, or be presented as approximate.

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
EPSG:26918 - NAD83 / UTM zone 18N
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

## Terrain

Terrain is the project's first raster evidence family, and the first to require a vertical datum and a resampling decision.

### Native CRS

The USGS 3DEP 1/3 arc-second DEM is distributed in geographic coordinates:

```text
horizontal: EPSG:4269   NAD83 geographic, decimal degrees
vertical:   EPSG:5703   NAVD88, meters
pixel:      9.259260e-05 degrees   (0.3333 arc-seconds)
```

A geographic raster cannot be sampled for metric neighborhood operations. At 43 degrees latitude a 1/3 arc-second cell spans roughly 7.5 m east-west and 10.3 m north-south, so a fixed pixel radius would describe an anisotropic ground area that varies with latitude.

### Reprojection policy

`python/scripts/prepare_terrain_raster.py` reprojects the source into the project distance CRS before any sampling:

```text
target CRS:   EPSG:26918   NAD83 / UTM zone 18N
resampling:   bilinear
pixel:        8.601124 m   (square)
```

The script rejects a target CRS that is not projected.

The projected pixel size is chosen by `rasterio.warp.calculate_default_transform` rather than specified. It is recorded in `outputs/validation/terrain_raster_prepare_manifest.json` along with both rasters' checksums, dimensions, bounds, nodata, and transforms.

### Resampling rationale

Bilinear is appropriate because elevation is a continuous surface: interpolating between cells is meaningful, whereas nearest-neighbour would preserve exact source values at the cost of stair-step artefacts that would propagate directly into slope.

The trade-off is that bilinear smooths. Local relief is slightly reduced, so computed slope and relative-elevation magnitudes are marginally conservative relative to the source grid. This is a known consequence, not an error.

### Unit expectations

After reprojection, and only after reprojection:

- pixel offsets convert to meters at 8.601124 m per pixel;
- the sampling radius in meters converts to whole pixels by `ceil(radius / pixel)`;
- slope is computed from elevation differences in meters over ground distances in meters, and reported in degrees.

The terrain evidence records `terrain_crs` per row, and `caprm.terrain` raises when the raster's CRS is not the expected projected CRS, when the raster is not projected at all, or when the evidence table's `distance_crs` disagrees with it.

### Neighborhood shape

The sampling radius is a **square half-width in pixels**, not a circular radius. A 90 m radius on an 8.601 m grid becomes 11 pixels, so the local mean is taken over a 23 x 23 pixel box roughly 198 m across. The field name says radius; the implementation reads a box.

Windows are clamped at the raster edge, so a property within 11 pixels of the boundary has its local mean computed over fewer cells.

## Distortion implications

UTM zone 18N spans 78W to 72W with its central meridian at 75W. Monroe County lies in the **western part of the zone**, roughly 77.3W to 78.0W, with the terrain raster's western bound at 78.020W, marginally past the zone edge.

The UTM scale factor is 0.9996 at the central meridian and grows outward. Across Monroe County it runs approximately:

```text
eastern county edge, ~77.3W:   k ~ 1.00003
western county edge, ~78.0W:   k ~ 1.00033
```

So planar distances are overstated by up to roughly `3e-4`, about **0.3 m per kilometre**, at the county's western edge.

This is negligible for the project's purposes, and it is smaller than the resolution of the underlying data. It should nonetheless be stated when discussing precision, because it is the honest counterpoint to the project's implementation-agreement figures:

> The countywide Python/C++ nearest-water agreement is `4.658e-10 m`. That number measures agreement between two independent implementations of the same calculation in the same projection. It is not accuracy against ground truth. The projection alone contributes roughly 0.9 m to the 2.63 km maximum observed water distance.

A larger study area would make this worse. Extending beyond zone 18, or beyond the county, would require revisiting the projected CRS rather than reusing EPSG:26918 by default.

## C++ boundary

C++ does not perform CRS discovery or transformation. Python exports already projected coordinates and records the CRS in manifests and output rows. Each C++ run must receive inputs generated for one shared CRS:

- FEMA C++ inputs: EPSG:3857;
- water C++ inputs: EPSG:26918.

Mixing projected inputs, mislabeled CRS values, or source longitude/latitude with metric geometry is a hard error.

C++ performs no terrain work. Raster sampling is Python-only.

## Validation requirements

A pipeline stage must reject or halt when:

- an input CRS is missing;
- configured and cached CRS metadata disagree;
- a hydrography cache checksum differs from its manifest;
- a C++ output reports a different distance CRS from the Python reference;
- property coordinates are nonfinite;
- a distance result is not provably complete within the configured cache buffer;
- a terrain raster is not projected, or its CRS is not the expected projected CRS;
- an evidence or terrain table presents more than one distinct CRS value;
- a property falls outside the terrain raster.

## Reporting policy

Every baseline, C++ export, validation summary, and integrated evidence manifest should record the relevant CRS. Documentation and presentation material must distinguish:

- geographic source/reporting coordinates;
- FEMA topological projection;
- metric water-distance projection;
- metric terrain projection;
- the vertical datum of any elevation value.

A correct statement is:

> FEMA membership is computed after projecting both layers to a shared CRS. Nearest-water distance is computed separately in EPSG:26918 and reported in meters. Terrain is resampled into EPSG:26918 before sampling, and elevations are NAVD88 meters.

Incorrect statements include:

> All project distances are computed in EPSG:3857.

> The terrain sampling radius is a 90 m circle.

> Property elevations are heights above lake level.

## Future features

Precipitation and any future area, distance, or raster transformation must document its own native CRS, resampling or interpolation policy, target CRS, units, vertical datum where applicable, and distortion implications. It must not inherit the FEMA EPSG:3857 path merely because it already exists, nor the terrain EPSG:26918 path without confirming the projection suits its extent.