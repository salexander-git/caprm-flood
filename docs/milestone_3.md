# Milestone 3: Terrain Evidence and Exposure Index

## Purpose

This document is the runbook for reproducing Milestone 3 from the repository
and its required source data, without reference to any prior conversation.

Milestone 3 adds the third evidence family, raster-derived terrain, and the
project's first derived scoring layer: a four-component relative exposure
index with measured component influence, rank-based sensitivity analysis, and
an automated product audit.

For the scoring behavior itself, see `docs/scoring_methodology.md`. For source
provenance, see `docs/data_sources.md`. For projection and datum rules, see
`docs/crs_policy.md`.

---

## 1. Prerequisites

Milestone 3 consumes the validated Milestone 2 evidence table. It does not
regenerate it.

| Required input | Produced by |
|---|---|
| `outputs/evidence/property_flood_evidence_countywide.csv` | Milestone 2, `build_property_evidence.py` |
| `data/raw/terrain/source_dem/monroe_3dep_13arcsec.tif` | manual download, see section 3 |

Both are Git-ignored. Neither is in the repository.

If the Milestone 2 evidence table is absent, reproduce Milestone 2 first. See
`docs/milestone_2.md`.

---

## 2. Environment

From the repository root, in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Expected:

```text
181 passed
```

Milestone 3 requires `rasterio` in addition to the Milestone 2 dependencies.
No Milestone 3 step invokes C++, so the executables are not needed here.

Optionally capture the environment for the record:

```powershell
.\.venv\Scripts\python.exe python\scripts\capture_environment.py
```

---

## 3. Source data acquisition

### The DEM

The terrain source is a clipped extract of the **USGS 3D Elevation Program
seamless 1/3 arc-second DEM** (approximately 10 m, bare earth, public domain).

Download client:

```text
https://apps.nationalmap.gov/downloader/
```

Select **Elevation Products (3DEP)**, then **1/3 arc-second DEM**, for an area
covering Monroe County, New York.

Place the result at:

```text
data/raw/terrain/source_dem/monroe_3dep_13arcsec.tif
```

### Verifying you have the same data

The extract used to produce the frozen Milestone 3 results:

```text
SHA-256:     29ff2c5ec8abe1d020993d50023b65a4adf9ac0a48a8d099ce2608f195aa1ded
CRS:         EPSG:4269   NAD83 geographic
vertical:    NAVD88, meters
dimensions:  7344 x 5400
pixel:       9.259260e-05 degrees   (0.3333 arc-seconds)
nodata:      -999999.0
extent:      -78.020084 to -77.340084 longitude
              42.900090 to  43.400090 latitude
```

```powershell
.\.venv\Scripts\python.exe -c "import hashlib,pathlib;p=pathlib.Path('data/raw/terrain/source_dem/monroe_3dep_13arcsec.tif');h=hashlib.sha256();h.update(p.read_bytes());print(h.hexdigest())"
```

**A different checksum does not mean you did something wrong.** USGS updates
the seamless 1/3 arc-second layer continually, so a download today can differ
from the one above. Your results will then differ slightly from the recorded
figures. That is a limitation of the source, recorded in
`docs/data_sources.md`; it is not a defect in the pipeline.

If your checksum differs, regenerate everything downstream and record your own
figures rather than citing this document's.

---

## 4. Pipeline

Run from the repository root. Each step depends on the previous one.

### Step 1 — Reproject the DEM

```powershell
.\.venv\Scripts\python.exe python\scripts\prepare_terrain_raster.py `
  --source data/raw/terrain/source_dem/monroe_3dep_13arcsec.tif `
  --output data/raw/terrain/monroe_dem_utm18.tif `
  --target-crs EPSG:26918 `
  --resampling bilinear `
  --manifest-output outputs/validation/terrain_raster_prepare_manifest.json
```

**Why:** the source is a geographic raster in degrees. Neighborhood and slope
calculations need meters. The script rejects a target CRS that is not
projected.

**Produces:**

```text
data/raw/terrain/monroe_dem_utm18.tif
  SHA-256: 069cfd98ff0c112bc80c7d7078b31f7a48132d8434c3a9563b2e0bab79ec4c66
  CRS EPSG:26918, 6635 x 6662, pixel 8.601124 m, nodata -999999.0

outputs/validation/terrain_raster_prepare_manifest.json
```

The projected pixel size is chosen by `rasterio.warp.calculate_default_transform`,
not specified. It is 8.601 m rather than 10 m because a 1/3 arc-second cell is
not square on the ground at this latitude.

**Work:** one full reprojection of a ~40 million pixel raster. The output is
roughly 175 MB.

### Step 2 — Extract terrain evidence

```powershell
.\.venv\Scripts\python.exe python\scripts\build_terrain_evidence.py
```

Defaults:

```text
--evidence              outputs/evidence/property_flood_evidence_countywide.csv
--terrain-raster        data/raw/terrain/monroe_dem_utm18.tif
--terrain-crs           EPSG:26918
--sample-radius-meters  90.0
--output                outputs/evidence/property_terrain_evidence_countywide.csv
--manifest-output       outputs/validation/property_terrain_evidence_countywide_manifest.json
```

**Why it reads the flood evidence table:** terrain reuses the projected
coordinates (`water_projected_x`, `water_projected_y`) already computed in
EPSG:26918 by Milestone 2, rather than reprojecting the property workload
again. This is an architectural coupling worth knowing about: the terrain
family cannot be built without the FEMA/water product.

**Produces:**

```text
outputs/evidence/property_terrain_evidence_countywide.csv
  SHA-256: e7768c538b41639032af176bd789bec76137c29348bc9be931ca7b4c44e5d3de
  267,362 rows, 7 columns

outputs/validation/property_terrain_evidence_countywide_manifest.json
```

**Work:** three windowed raster reads per property — the centre cell, the
local neighborhood, and a 3x3 slope window — for **802,086 reads** across
267,362 properties. **This is the slowest step in the milestone by a wide
margin.** It is not hung.

**Expected result:**

```text
267,362 properties, 0 nulls in any field
elevation:           75.000 to 296.309 m
relative elevation: -20.669 to  30.149 m
slope:                0.000 to  58.139 degrees
```

The script raises if any property falls outside the raster.

### Step 3 — Build the exposure index

```powershell
.\.venv\Scripts\python.exe python\scripts\build_exposure_index.py
```

Defaults use `caprm.scoring.DEFAULT_WEIGHTS`. To score an alternative
configuration:

```powershell
.\.venv\Scripts\python.exe python\scripts\build_exposure_index.py `
  --weights '{"fema":0.25,"water":0.25,"terrain_absolute":0.25,"terrain_relative":0.25}' `
  --output outputs/index/property_exposure_index_equal.csv `
  --manifest-output outputs/validation/property_exposure_index_equal_manifest.json
```

**Produces:**

```text
outputs/index/property_exposure_index_countywide.csv
  SHA-256: 3cae2e830a5867bee4d51a36f1c5c04f05ee0a6a26d64dace27da75d3c4911b0

outputs/validation/property_exposure_index_countywide_manifest.json
```

**Expected result:**

```text
scoring policy:  preliminary_exposure_index_v2
properties:      267,362
index:           7.914598933 to 99.929084911
mean:            34.63218408001099
median:          33.7284299935
```

The manifest records the weights actually applied. Those weights plus the two
evidence tables are sufficient to recompute the index.

### Step 4 — Describe the scoring inputs

```powershell
.\.venv\Scripts\python.exe python\scripts\summarize_scoring_inputs.py
```

Read-only. Reports the measured input domain the scoring layer sees: FEMA zone
and SFHA distribution, distance and elevation ranges, CRS values, and each
manifest's key convention.

**Produces:** `outputs/validation/scoring_inputs_summary.json`

### Step 5 — Measure component redundancy

```powershell
.\.venv\Scripts\python.exe python\scripts\summarize_component_correlation.py
```

Read-only. Rank correlation and high-exposure tail overlap between the four
components, plus a regression check that the components recompute the shipped
index.

**Produces:** `outputs/validation/component_correlation_summary.json`

**Expected:** `recomputed_composite.agrees: true`, maximum pairwise Spearman
0.152.

### Step 6 — Run the sensitivity analysis

```powershell
.\.venv\Scripts\python.exe python\scripts\analyze_scoring_sensitivity.py
```

40 weight scenarios: baseline, equal, eight single-component reweightings, two
terrain-family, 24 seeded Dirichlet perturbations, and four reference corners.
Deterministic: the seed is recorded in the manifest.

**Produces:**

```text
outputs/analysis/scoring_sensitivity_summary.csv
outputs/analysis/scoring_sensitivity_property_shifts.csv
outputs/validation/scoring_sensitivity_manifest.json
outputs/validation/scoring_sensitivity_summary.md
```

**Expected:** verdict `moderately_sensitive`, minimum Spearman 0.875 on the
`equal` scenario.

**Work:** the index is built once and every scenario reweights the same four
component columns, so this is 40 dot products and 40 rank operations over
267,362 rows rather than 40 pipeline runs.

### Step 7 — Generate the milestone summary

```powershell
.\.venv\Scripts\python.exe python\scripts\summarize_milestone3_results.py
```

Renders the terrain and index manifests as Markdown. Reads no CSV.

**Produces:** `outputs/validation/milestone3_results_summary.md`

### Step 8 — Audit the products

```powershell
.\.venv\Scripts\python.exe python\scripts\audit_milestone3_products.py
```

**Exits nonzero on any failure.** This is the completion gate.

**Produces:** `outputs/validation/milestone3_audit.json`

**Expected:**

```text
Audit status: warn
pass 49  warn 1  fail 0
```

The single expected warning is `manifest_schema_consistency`: the Milestone 2
evidence manifest uses `evidence_summary` / `output_csv` while the Milestone 3
manifests use `summary` / `output`. This is deliberate and documented; see
section 7.

Reading the property workload GeoJSON is the slowest part. To skip it:

```powershell
.\.venv\Scripts\python.exe python\scripts\audit_milestone3_products.py --workload ""
```

The chain is then compared against the flood evidence rather than its true
source, and the audit warns accordingly.

### Step 9 — Run the tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

```text
181 passed
```

---

## 5. Validating success

Milestone 3 has reproduced correctly when all of the following hold.

| Check | Where |
|---|---|
| 181 tests pass | `pytest -q` |
| Audit exits zero, `fail 0` | `audit_milestone3_products.py` |
| 267,362 properties in terrain, index, and evidence | audit `population_*` checks |
| Manifest checksums match the files on disk | audit `*_checksum` checks |
| The manifest's weights recompute the stored index | audit `index_composite_derivation` |
| The stored percentile recomputes from the stored index | audit `index_percentile_derivation` |
| Components are near-orthogonal | `component_correlation_summary.json` |
| Sensitivity verdict is produced | `scoring_sensitivity_manifest.json` |

The audit is the single command that checks most of this. **If it exits zero,
the products are internally consistent, agree with their manifests, and
describe the same property population.** It does not mean the evidence is
accurate or the scoring methodology is correct.

### If the audit fails

`*_checksum` failures mean an artifact was regenerated without its manifest,
or vice versa. Rerun the generating step; do not edit the manifest.

`population_*` failures mean the products describe different property sets.
Regenerate the chain from step 2.

`index_composite_derivation` failure means the manifest cannot reproduce its
own index. This is the most serious failure the audit can report.

---

## 6. Outputs and Git

**Nothing Milestone 3 generates is tracked.** `.gitignore` excludes
`data/raw/`, `data/processed/`, `outputs/`, and `*.tif`.

Tracked: code, tests, configuration, and documentation. Generated: everything
under `outputs/` and `data/`.

Consequence: cloning the repository gives you the ability to reproduce
Milestone 3, not its results. The checksums in this document and in
`docs/scoring_methodology.md` are the record of what the frozen run produced.

Some artifacts under `outputs/` and `data/` remain tracked from before the
ignore rules were applied. See `CAPRM_Flood_Current_Status.md` section 4.

---

## 7. Known asymmetries and limitations

Recorded here because a reader reproducing this milestone will encounter them.

**The DEM has no download script and no recorded retrieval date.** Hydrography
has `cache_hydrography.py`, a checksum-backed manifest, and a completeness
proof. The DEM has a checksum and nothing else. USGS updates the seamless
layer continually, so the checksum is the only thing pinning which elevation
data produced these results. FEMA shares this limitation.

**Terrain has no configuration entry.** Property points, FEMA, the study area,
and hydrography are declared in `configs/*.yaml`. The terrain paths, CRS, and
sampling radius exist only as CLI defaults in the terrain scripts.

**The sampling radius is a square half-width, not a circle.** 90 m on an
8.601 m grid becomes 11 pixels, so the local mean is taken over a 23 x 23
pixel box roughly 198 m across. The field is named
`terrain_sample_radius_m`; the implementation reads a box.

**The local window is clipped at the raster edge.** A property within 11
pixels of the DEM boundary has its local mean computed over fewer cells,
biasing its relative elevation. Zero missing slope values prove no property
lies within one pixel of the edge; they do not prove none lies within eleven.

**Bilinear resampling smooths.** Slope and relative-elevation magnitudes are
marginally conservative relative to the source grid.

**Slope is extracted but not scored.** It is preserved as terrain evidence and
does not enter the exposure index.

**Two manifest conventions are in use.** The Milestone 2 evidence manifest
predates the Milestone 3 convention. Unifying it would mean regenerating a
validated upstream product for a cosmetic gain. `caprm.audit.manifest_field`
reads both.

**Elevations are NAVD88 meters.** Comparisons against Great Lakes water levels,
which are published in IGLD85, are approximate. See `docs/crs_policy.md`.

**Monroe County sits near the western edge of UTM zone 18N.** Planar distances
are overstated by up to roughly 0.3 m per kilometre. Negligible here, but it is
the honest counterpoint to the project's `1e-10 m` implementation-agreement
figures. See `docs/crs_policy.md`.

**The index is not validated against observed flooding.** No such validation
has been attempted, and none is planned. Sensitivity measures how much the
ranking depends on the weights; it does not establish that the weights are
right.

---

## 8. Regenerating a single artifact

Manifests are written by the script that produces the artifact they describe.
There is no separate manifest-regeneration step, and editing a manifest by
hand will fail the audit.

To regenerate an artifact and its manifest together, rerun its step from
section 4. Downstream artifacts must then be regenerated too, because their
manifests record the input checksums:

```text
terrain raster  ->  terrain evidence  ->  index  ->  sensitivity
                                             |
                                             +->  milestone summary
                                             +->  audit
```

Rerun the audit last. It is the check that catches a partial regeneration.