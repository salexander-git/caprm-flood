# Data Sources

## Property Points

Primary source: NYS Tax Parcel Centroid Points.

The service contains 2025 parcel centroid data for all New York State counties and is updated annually. The initial project filter is Monroe County. Relevant fields may include `OBJECTID`, `COUNTY_NAME`, `MUNI_NAME`, `PRINT_KEY`, `SBL`, and property assessment fields where available.

Source:
https://gisservices.its.ny.gov/arcgis/rest/services/NYS_Tax_Parcel_Centroid_Points/FeatureServer/0

## Flood-Hazard Polygons

Primary source: FEMA National Flood Hazard Layer.

Milestone 1 uses FEMA flood-hazard polygons for the study region. The expected FEMA feature class is `S_FLD_HAZ_AR`, with fields such as flood zone and SFHA indicator where available.

Source:
https://www.fema.gov/flood-maps/national-flood-hazard-layer

## Milestone 1 Scope

Milestone 1 extracts FEMA flood-zone membership for property points using a Python GeoPandas/Shapely baseline. The C++ version will be compared against this output.