# CRS Policy

Every spatial layer must have its CRS inspected before spatial operations.

Milestone 1 requires property points and FEMA flood polygons to be transformed into a shared project CRS before point-in-polygon lookup. The initial project CRS is EPSG:3857 for compatibility with the NYS parcel centroid service and because the first operation is topological membership rather than metric distance.

For later nearest-water distance and terrain-derived features, CAPRM-Flood should switch to or additionally use a local projected CRS suitable for metric distances in Monroe County, New York.

Logged CRS fields:
- original property CRS
- original FEMA CRS
- project CRS
- transformation performed