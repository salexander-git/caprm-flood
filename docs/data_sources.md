# Data Sources

## Scope

CAPRM-Flood uses five authoritative geospatial inputs for Monroe County, New York:

1. NYS Tax Parcel Centroid Points for property locations.
2. FEMA National Flood Hazard Layer polygons for flood-zone evidence.
3. U.S. Census Bureau TIGERweb county boundaries for the official study-area geometry.
4. USGS 3D Hydrography Program flowlines and waterbodies for nearest-water evidence.
5. USGS 3D Elevation Program 1/3 arc-second DEM for terrain evidence.

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

The project preserves:

- polygon-match status;
- flood-zone label;
- `SFHA_TF` and normalized `is_sfha` value;
- stable source feature ID;
- local source feature index used for exact Python/C++ agreement.

FEMA geometry is projected to EPSG:3857 for the validated topological point-in-polygon path. This CRS is not used for nearest-water distance.

### Observed zone domain

The countywide evidence contains exactly five mapped zone values:

```text
X: 262,297
AE: 4,226
A: 408
AO: 388
VE: 39
missing (unmatched): 4
```

Every matched non-X zone is SFHA and X never is, so `is_sfha` carries no information beyond `fema_zone` for this workload. This is a property of the current data, not a guarantee of the FEMA schema. `caprm.scoring` raises on a matched property carrying any zone outside this set rather than assigning it a default score.

### Invalid geometry policy

The export retains baseline-referenced FEMA features even when the source layer reports invalid geometry, because dropping a referenced feature would make the C++ fixture incomplete. Polygon parts and rings are flattened in their existing source order for independent C++ processing. The countywide export included 69 invalid source geometries among 1,382 selected FEMA features.

This is an implementation limitation: agreement demonstrates that Python and C++ reproduced the selected baseline behavior for these records; it does not certify that every source polygon is topologically ideal.

### Limitations

- FEMA zones describe mapped flood hazards and are not a complete property-loss model.
- A centroid can fall outside a hazard polygon even when another part of the parcel or a structure intersects it.
- Four countywide property points did not match any exported flood-hazard-area polygon.
- FEMA source vintages and map revisions can change the result.
- The NFHL input is acquired manually. There is no download script and no recorded retrieval date.

## Official county boundary

**Source:** U.S. Census Bureau TIGERweb Counties
**Service:** `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer`
**Layer:** 1, Counties
**County GEOID:** `36055`
**Source vintage:** January 1, 2025
**Cache:** `data/raw/census_monroe_county_2025.geojson`

The county polygon defines the study area used to select hydrography. The cache manifest reports:

```text
county area: 3,541.112 km2
county-plus-buffer study area: 9,682.441 km2
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

- "Nearest water" means nearest included USGS feature, not nearest perennial, navigable, flood-contributing, or hydraulically connected water body.
- The result depends on the configured feature-type inclusion rules.
- Source names can be missing.
- Public services are dynamic; regeneration from a later source state can change features and distances.
- Geometry resolution and classification reflect the source, not a field survey.
- Proximity is exposure evidence, not a direct flood-probability estimate.

## Terrain elevation

**Source:** USGS 3D Elevation Program (3DEP), seamless 1/3 arc-second DEM
**Product page:** `https://www.usgs.gov/3d-elevation-program/about-3dep-products-services`
**Data catalog:** `https://www.sciencebase.gov/catalog/item/4f70aa9fe4b058caae3f8de5`
**Download client:** `https://apps.nationalmap.gov/downloader/`
**Availability index:** `https://index.nationalmap.gov/arcgis/rest/services/3DEPElevationIndex/MapServer`
**Surface:** bare earth
**License:** public domain, no use restrictions

### Product characteristics

The 3DEP seamless 1/3 arc-second layer is approximately 10 m resolution. USGS distributes it in geographic coordinates in decimal degrees conforming to NAD 83, with elevation values in meters referenced to NAVD 88 over the continental United States, pre-staged as 1x1 degree GeoTIFF tiles.

### Local source cache

```text
data/raw/terrain/source_dem/monroe_3dep_13arcsec.tif
SHA-256: 29ff2c5ec8abe1d020993d50023b65a4adf9ac0a48a8d099ce2608f195aa1ded
```

Verified from `outputs/validation/terrain_raster_prepare_manifest.json`:

```text
horizontal CRS:   EPSG:4269   NAD83 geographic
vertical datum:   NAVD88      EPSG:5703, meters
dimensions:       7344 x 5400
data type:        float32
nodata:           -999999.0
pixel size:       9.259260e-05 degrees
extent:           -78.020084 to -77.340084 longitude
                   42.900090 to  43.400090 latitude
```

The pixel size confirms the product: `9.259260e-05 x 3600 = 0.3333` arc-seconds.

The cached file is a **clipped extract**, not a standard 1x1 degree tile: it spans roughly 0.68 by 0.50 degrees, cut to Monroe County plus a margin.

### Projected raster

`python/scripts/prepare_terrain_raster.py` reprojects the source into the project distance CRS so that neighborhood and slope calculations operate in meters.

```text
data/raw/terrain/monroe_dem_utm18.tif
SHA-256: 069cfd98ff0c112bc80c7d7078b31f7a48132d8434c3a9563b2e0bab79ec4c66
```

```text
target CRS:       EPSG:26918   NAD83 / UTM zone 18N
resampling:       bilinear
dimensions:       6635 x 6662
data type:        float32
nodata:           -999999.0
pixel size:       8.601124 m
extent:           253430.895 to 310499.352 easting
                  4752375.818 to 4809676.505 northing
```

The projected pixel size is chosen by `rasterio.warp.calculate_default_transform` rather than specified. It is 8.601 m rather than 10 m because a 1/3 arc-second cell is not square on the ground: at 43 degrees latitude it spans roughly 7.5 m east-west and 10.3 m north-south.

This matters downstream. The terrain sampling radius is expressed in meters and converted to whole pixels, so a 90 m radius becomes `ceil(90 / 8.601) = 11` pixels, and the local neighborhood is a **23 x 23 pixel square approximately 198 m across**, not a 90 m circle.

### Derived evidence

```text
outputs/evidence/property_terrain_evidence_countywide.csv
SHA-256: e7768c538b41639032af176bd789bec76137c29348bc9be931ca7b4c44e5d3de
```

```text
267,362 properties
0 null elevation, local mean, relative elevation, or slope
elevation:           75.000 to 296.309 m   (mean 143.197, median 146.828)
relative elevation: -20.669 to  30.149 m   (mean 0.247, median 0.175)
slope:                0.000 to  58.139 deg (mean 1.906, median 1.234)
```

Manifest:

```text
outputs/validation/property_terrain_evidence_countywide_manifest.json
```

### Plausibility observations

These are consistency checks, not validation against an independent elevation source.

The 75.0 m elevation floor is broadly consistent with Lake Ontario, whose low-water datum is about 74.2 m in IGLD85. IGLD85 and NAVD88 are different vertical datums and differ by up to roughly a meter in the Great Lakes basin, so this is an approximate agreement rather than a precise one.

The 1.234 degree median slope is consistent with a lake-plain county. The 58.139 degree maximum is consistent with the Genesee gorge, which runs through Rochester.

### Limitations

- **The retrieval date is not recorded.** USGS updates the seamless 1/3 arc-second layer continually in the current folder, retaining previously created 1-degree blocks in a historical folder with an appended `YYYYMMDD` suffix. A later download of the same extent can therefore return different elevation data with no visible signal. The recorded SHA-256 is the only thing pinning which elevation data produced these results.
- **There is no download script.** Unlike hydrography, which has `cache_hydrography.py` and a checksum-backed manifest with a completeness proof, the DEM is acquired manually. The FEMA input shares this limitation.
- **The extent is clipped to approximately Monroe County.** Extending the property workload beyond the current county would require acquiring a new DEM. The eastern bound sits close to the county line; the terrain build raises if any property falls outside the raster, and no property did.
- **Bilinear resampling smooths the surface.** This slightly reduces local relief, so computed slope and relative-elevation magnitudes are marginally conservative relative to the source grid.
- **The local window is clipped at the raster edge.** A property within 11 pixels of the DEM boundary has its local mean computed over fewer cells, biasing its relative elevation. Zero missing slope values prove no property lies within one pixel of the edge; it does not prove none lies within eleven.
- **Bare earth is not the built surface.** The DEM does not represent buildings, vegetation, culverts, levees, or other flood-control structures.
- **A parcel centroid elevation is not a structure elevation.** No first-floor or foundation elevation is used or implied.
- **Terrain has no configuration entry.** The property, FEMA, study-area, and hydrography sources are declared in `configs/*.yaml`. The terrain paths, CRS, and sampling radius live only in the terrain scripts' CLI defaults.

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