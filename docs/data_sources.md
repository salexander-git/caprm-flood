# Data Sources

## Scope

Milestone 2 uses four authoritative geospatial inputs for Monroe County, New York:

1. NYS Tax Parcel Centroid Points for property locations.
2. FEMA National Flood Hazard Layer polygons for flood-zone evidence.
3. U.S. Census Bureau TIGERweb county boundaries for the official study-area geometry.
4. USGS 3D Hydrography Program flowlines and waterbodies for nearest-water evidence.

Cached data and manifests are part of the reproducibility contract because the public services are dynamic.

## Property points

**Source:** NYS Tax Parcel Centroid Points  
**Service:** `https://gisservices.its.ny.gov/arcgis/rest/services/NYS_Tax_Parcel_Centroid_Points/FeatureServer/0`  
**County filter:** `COUNTY_NAME = 'Monroe'`  
**Canonical property identifier:** `SBL`  
**Source geometry:** Point, interpreted as EPSG:4326

### Selection policy

For deterministic larger workloads:

1. request all matching ArcGIS object IDs;
2. process records in ascending `OBJECTID` order;
3. retain the first nonmissing occurrence of each canonical `SBL`;
4. skip later duplicate `SBL` records;
5. preserve the validated prior workload as an exact ordered prefix.

Countywide accounting at acquisition time:

```text
267,414 matching object IDs
267,362 unique retained SBL values
52 duplicate SBL rows excluded
0 missing SBL rows excluded
```

The countywide cache is:

```text
data/processed/monroe_property_points_countywide.geojson
SHA-256: a0b4b1963caa05679b1e7e30b7150528c63d64e3c35178dd93e99a00bcab8179
```

The 1K fixture remains immutable, and the 10K, 100K, and countywide caches preserve validated prefixes.

### Limitations

- A parcel centroid is not a building footprint, structure entrance, or occupied-address point.
- `SBL` identifies the canonical source property record used by this project, not necessarily a universal property identifier across jurisdictions or source vintages.
- Source records can be edited, deleted, duplicated, or repositioned over time.
- The deterministic prefixes are computational workloads, not random or demographically representative samples.

## FEMA flood-hazard polygons

**Source:** FEMA National Flood Hazard Layer  
**Local feature class:** `S_FLD_HAZ_AR`  
**Local path:** `data/raw/fema_nfhl_monroe/S_FLD_HAZ_AR.shp`  
**Observed source CRS:** EPSG:4269  
**Stable source feature field:** `FLD_AR_ID` when available

Milestone 2 preserves:

- polygon-match status;
- flood-zone label;
- `SFHA_TF` and normalized `is_sfha` value;
- stable source feature ID;
- local source feature index used for exact Python/C++ agreement.

FEMA geometry is projected to EPSG:3857 for the validated topological point-in-polygon path. This CRS is not used for nearest-water distance.

### Invalid geometry policy

The export retains baseline-referenced FEMA features even when the source layer reports invalid geometry, because dropping a referenced feature would make the C++ fixture incomplete. Polygon parts and rings are flattened in their existing source order for independent C++ processing. The countywide export included 69 invalid source geometries among 1,382 selected FEMA features.

This is an implementation limitation: agreement demonstrates that Python and C++ reproduced the selected baseline behavior for these records; it does not certify that every source polygon is topologically ideal.

### Limitations

- FEMA zones describe mapped flood hazards and are not a complete property-loss model.
- A centroid can fall outside a hazard polygon even when another part of the parcel or a structure intersects it.
- Four countywide property points did not match any exported flood-hazard-area polygon.
- FEMA source vintages and map revisions can change the result.

## Official county boundary

**Source:** U.S. Census Bureau TIGERweb Counties  
**Service:** `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer`  
**Layer:** 1, Counties  
**County GEOID:** `36055`  
**Source vintage:** January 1, 2025  
**Cache:** `data/raw/census_monroe_county_2025.geojson`

The county polygon defines the study area used to select hydrography. The cache manifest reports:

```text
county area: 3,541.112 km²
county-plus-buffer study area: 9,682.441 km²
```

## Hydrography

**Source:** USGS 3D Hydrography Program  
**Service:** `https://hydro.nationalmap.gov/arcgis/rest/services/3DHP_all/MapServer`  
**Query CRS:** EPSG:26918  
**Cache CRS:** EPSG:4326  
**Distance CRS:** EPSG:26918  
**Study area:** official county polygon plus 20,000 m outward buffer

### Included layers and rules

#### Flowline, layer 50

Included numeric feature types:

```text
1, 2, 3
```

Final retained features:

```text
5,600 total
5,600 retained flowlines after the study-area filter
```

The current manifest's retained flowlines comprise channel-line and canal geometries. The canonical cache should be treated as the authoritative exact count and classification source.

#### Waterbody, layer 60

Included numeric feature types:

```text
1, 2, 3, 4
```

Final retained features:

```text
2,972 total
```

The retained collection includes lakes, rivers, canals, and one ocean-or-Great-Lake feature class record where applicable.

### Final cache

```text
data/raw/usgs_3dhp_monroe.gpkg
8,572 total features
1,072,254 vertices
1,063,159 segments
SHA-256: 3510ad04f6aae545274ea34bd4a33f17da5667c679f495cfb4706ffc6d7c5de8
```

Manifest:

```text
outputs/validation/hydrography_cache_manifest.json
```

### Completeness rule

All selected hydrography features intersecting the official county boundary plus the configured 20 km buffer are cached. For a property covered by the county polygon, a nearest distance strictly less than 20 km proves that no feature outside the cached study area can be closer.

Every reported countywide nearest-water distance satisfies this condition; the maximum observed distance was approximately 2.630 km.

### Limitations

- “Nearest water” means nearest included USGS feature, not nearest perennial, navigable, flood-contributing, or hydraulically connected water body.
- The result depends on the configured feature-type inclusion rules.
- Source names can be missing.
- Public services are dynamic; regeneration from a later source state can change features and distances.
- Geometry resolution and classification reflect the source, not a field survey.
- Proximity is exposure evidence, not a direct flood-probability estimate.

## Provenance policy

Every generated cache or evidence product should record, where applicable:

- source URL and filter;
- acquisition or creation timestamp;
- input and output paths;
- SHA-256 checksums;
- CRS values;
- inclusion rules;
- selected/excluded row counts;
- property ordering and deduplication rules;
- validation summary references.

Do not replace a cached source file without regenerating its manifest and every downstream artifact whose checksum contract depends on it.
