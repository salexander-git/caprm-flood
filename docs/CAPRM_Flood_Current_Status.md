# CAPRM-Flood Current Status — 2026-07-16

## Purpose of This Document

This document records the exact current operational state of CAPRM-Flood as of **July 16, 2026**.

```text
Verified at commit:   see section 2
Test suite:           181 passed
Product audit:        49 pass, 1 warn, 0 fail
Scoring policy:       preliminary_exposure_index_v2
```

**Staleness check.** This document lives in the repository. If you are reading
it through a synced integration rather than the working tree, confirm the
commit recorded in section 2 matches `git log -1 --oneline` before relying on
anything here. Integration syncs lag; the working tree does not.

Where the canonical documents differ in role:

- **Nucleus** defines what CAPRM-Flood fundamentally is, why it exists, how it is architected, and which engineering principles govern it.
- **This document** records the exact present implementation state, latest outputs, test status, and immediate next task.
- **Roadmap** records remaining work in ordered implementation chunks.
- **`docs/scoring_methodology.md`** records the scoring layer's exact behavior.
- **`docs/milestone_3.md`** records how to reproduce Milestone 3 from source data.

---

# 1. Current Phase

Current academic/project phase:

```text
Milestone 3
```

Current implementation state:

```text
Milestone 1: complete and validated
Milestone 2: complete and validated
Milestone 3: complete and frozen
Milestone 4: index structure and learned approximation — starting
Milestone 4: not yet started as a dedicated implementation phase
```

Milestone 3 is frozen and the exposure index is no longer under active work.

Milestone 4 concentrates the project's computer-science contribution on index
structure and learned approximation. See `CAPRM_Flood_Roadmap.md` and Nucleus
section 14b. Precipitation is a gated stretch goal behind that work.

Final report writing is intentionally deferred until the remaining Milestone 3 implementation and validation work is complete.

---

# 2. Git Repository State

GitHub repository:

```text
https://github.com/salexander-git/caprm-flood
```

Primary branch:

```text
master
```

Current synchronized commit:

```text
0dd85ab Add Milestone 3 terrain evidence and exposure scoring
```

Synchronization status at the last check:

```text
HEAD == origin/master
ahead: 0
behind: 0
```

The local repository and GitHub remote are therefore synchronized through the current committed Milestone 3 implementation.

The Milestone 3 commit added:

```text
python/caprm/scoring.py
python/caprm/terrain.py

python/scripts/build_exposure_index.py
python/scripts/build_terrain_evidence.py
python/scripts/prepare_terrain_raster.py
python/scripts/summarize_milestone3_results.py

tests/test_scoring.py
tests/test_terrain.py
```

It also modified:

```text
requirements.txt
```

The commit contained:

```text
9 files changed
1646 insertions
```

---

# 3. Untracked Local Files

Untracked and not ignored:

```text
.vscode/
MILESTONE 2 PRESENTATION NOTES.docx
git_log_current.txt
git_status_current.txt
how-ref
m2_presentation_script.docx
presentation_assets/
report body .docx
repository_tree_current.txt
```

Ignored by rule, not untracked:

```text
milestone2_closeout_context.zip                (*.zip)
.venv/  .pytest_cache/  cpp/spatial_core/build/
```

These are local presentation, editor, and scratch files to be triaged
separately.

## Documentation state

The repository previously tracked `docs/CAPRM-Flood Project Nucleus 6.2.26.pdf`,
the superseded June 2 nucleus, which described the project as still in the
Milestone 1 spike phase. It was retired at commit `683af3f`, and the current
canonical documents were added to `docs/` in the same commit.

---

# 4. Current `.gitignore` Policy

```text
.venv/
__pycache__/
*.pyc

data/raw/
data/processed/
outputs/

*.gpkg
*.shp
*.shx
*.dbf
*.prj
*.cpg
*.tif
*.tiff
*.zip

build/
cmake-build-*/
*.exe
*.obj
*.pdb

.env
.DS_Store

# Editor state
.vscode/
.idea/
.pytest_cache/

# Regenerable scratch output
git_log_current.txt
git_status_current.txt
repository_tree_current.txt
```

## Files tracked despite the ignore rules

Some files under `data/` and `outputs/` remain tracked because they were
committed before the ignore rules were applied. Verified by
`python/scripts/inventory_repository.py` on 2026-07-16:

```text
data/raw/usgs_3dhp_monroe.gpkg                    21,155,840 bytes   tracked
```

This is the **only large tracked file in the repository**. Every other file
above 5 MB reports `ignored`. It matches `*.gpkg`. The hydrography cache is
checksummed in `docs/data_sources.md` and regenerable by
`cache_hydrography.py`, so the working copy does not depend on it being
tracked.

Also tracked and empty, from Milestone 1:

```text
outputs/validation/fema_pip_refresh_stderr.txt
outputs/validation/fema_pip_refresh_stdout.txt
```

`outputs/validation/repository_inventory.json` was untracked at commit time
because it is regenerated on every inventory run and would otherwise dirty
the working tree whenever the repository is inspected.

Repository inventory as of 2026-07-16:

```text
362 files inventoried
108 tracked
248 ignored
  6 untracked
```

## PowerShell encoding note

The repository's Markdown is correct UTF-8. `Get-Content` in PowerShell 5.1
defaults to cp1252 and will render `km²` as `kmÂ²` and curly quotes as
`â€œ`. This is a display artefact, not file corruption; verified with
`Select-String -Encoding UTF8`, which found no mojibake sequences in
`docs/*.md` or `README.md`.

Use `-Encoding UTF8` when inspecting these files from PowerShell.

---

# 5. Current Core Source Tree

Important tracked source modules currently include:

```text
python/caprm/
├── __init__.py
├── audit.py
├── baseline.py
├── crs.py
├── evidence.py
├── export.py
├── hydrography.py
├── ingest.py
├── scoring.py
├── sensitivity.py
├── study_area.py
├── terrain.py
├── validate.py
├── water_benchmark.py
├── water_distance.py
├── water_export.py
└── water_validate.py
```

Important tracked scripts include:

```text
python/scripts/
├── analyze_scoring_sensitivity.py
├── audit_milestone3_products.py
├── benchmark_water_cpp.py
├── build_exposure_index.py
├── build_property_evidence.py
├── build_terrain_evidence.py
├── cache_hydrography.py
├── capture_environment.py
├── compare_python_cpp_fema.py
├── compare_python_cpp_water.py
├── create_cpp_dev_fixture.py
├── debug_cpp_fixture.py
├── export_cpp_inputs.py
├── export_water_cpp_inputs.py
├── inspect_fema_schema.py
├── inventory_repository.py
├── materialize_countywide_property_workload.py
├── materialize_property_cache.py
├── materialize_property_workload.py
├── prepare_terrain_raster.py
├── run_fema_baseline.py
├── run_water_baseline.py
├── summarize_baseline.py
├── summarize_component_correlation.py
├── summarize_milestone3_results.py
└── summarize_scoring_inputs.py
```

Important C++ sources include:

```text
cpp/spatial_core/src/
├── fema_pip_dev.cpp
├── water_distance_bruteforce.cpp
└── water_distance_indexed.cpp
```

Important tests include:

```text
tests/
├── conftest.py
├── test_audit.py
├── test_baseline.py
├── test_evidence.py
├── test_export.py
├── test_hydrography.py
├── test_ingest.py
├── test_materialize_countywide_property_workload.py
├── test_scoring.py
├── test_sensitivity.py
├── test_study_area.py
├── test_terrain.py
├── test_validate.py
├── test_water_benchmark.py
├── test_water_distance.py
├── test_water_export.py
└── test_water_validate.py
```

---

# 6. Milestone 1 Status

Milestone 1 is complete and validated.

Implemented:

- FEMA NFHL ingestion;
- property workload preparation;
- CRS normalization;
- Python FEMA point-in-polygon baseline;
- independent C++ FEMA point-in-polygon implementation;
- C++ input export;
- Python/C++ result comparison;
- deterministic validation artifacts;
- stable 1,000-property regression fixture;
- canonical FEMA feature identity using `FLD_AR_ID`.

Validated result:

```text
1,000 / 1,000 property agreement
```

The 1,000-property fixture should remain preserved as a stable regression artifact.

---

# 7. Milestone 2 Status

Milestone 2 is complete and validated.

Implemented:

- USGS hydrography ingestion/cache;
- nearest-water evidence;
- projected metric distance computation;
- Python STRtree-based nearest-feature reference;
- C++ brute-force nearest-water implementation;
- C++ indexed nearest-water implementation;
- deterministic nearest-feature tie resolution;
- water benchmark tooling;
- workload scaling from smaller deterministic sets to countywide;
- integrated FEMA/water evidence;
- validation summaries and manifests.

The validated Milestone 2 FEMA/water evidence remains an upstream source-family product and should not be overwritten by later terrain or scoring work.

---

# 8. Countywide Property Workload

The current countywide workload contains:

```text
267,362 unique property IDs
```

This workload is now the primary large-batch dataset used for Milestone 3 terrain and index generation.

The earlier 1,000-property fixture remains the regression/validation fixture.

---

# 9. Milestone 3 Implemented Components

Milestone 3 includes:

```text
A. terrain evidence extraction
B. exposure-index generation, scoring policy preliminary_exposure_index_v2
C. rank-based sensitivity analysis
D. product audit
```

Implemented modules:

```text
python/caprm/terrain.py
python/caprm/scoring.py
python/caprm/sensitivity.py
python/caprm/audit.py
```

Implemented scripts:

```text
python/scripts/prepare_terrain_raster.py
python/scripts/build_terrain_evidence.py
python/scripts/build_exposure_index.py
python/scripts/summarize_milestone3_results.py
python/scripts/summarize_scoring_inputs.py
python/scripts/summarize_component_correlation.py
python/scripts/analyze_scoring_sensitivity.py
python/scripts/audit_milestone3_products.py
```

Tests:

```text
tests/test_terrain.py
tests/test_scoring.py
tests/test_sensitivity.py
tests/test_audit.py
```

The scoring methodology is documented in `docs/scoring_methodology.md`.

---

# 10. Terrain Raster Preparation

Implemented script:

```text
python/scripts/prepare_terrain_raster.py
```

Current terrain raster paths include:

```text
data/raw/terrain/source_dem/monroe_3dep_13arcsec.tif
data/raw/terrain/monroe_dem_utm18.tif
```

The source DEM is prepared into a projected raster suitable for metric terrain operations.

The projected terrain CRS follows the project's Monroe County metric CRS policy:

```text
EPSG:26918
NAD83 / UTM zone 18N
```

The raster-preparation stage is intended to make downstream local neighborhood operations spatially meaningful in meters.

---

# 11. Terrain Evidence Module

Implemented module:

```text
python/caprm/terrain.py
```

Implemented evidence-building script:

```text
python/scripts/build_terrain_evidence.py
```

The terrain pipeline derives property-level fields including:

```text
property_id
terrain_elevation_m
terrain_local_mean_elevation_m
terrain_relative_elevation_m
terrain_slope_degrees
terrain_sample_radius_m
terrain_crs
```

The exact runtime schema should be verified against the current generated CSV before final Milestone 3 freeze.

The terrain output is a separate source-family evidence product.

It should not overwrite the validated Milestone 2 FEMA/water evidence.

---

# 12. Terrain Output

Verified from `outputs/validation/property_terrain_evidence_countywide_manifest.json`
and the generated CSV on 2026-07-16:

```text
output sha256:                 e7768c538b41639032af176bd789bec76137c29348bc9be931ca7b4c44e5d3de
properties:                    267,362
unique property IDs:           267,362
null elevation:                0
null relative elevation:       0
null slope:                    0
elevation:                     75.000 - 296.309 m   (mean 143.197, median 146.828)
relative elevation:            -20.669 - +30.149 m  (mean 0.247, median 0.175)
slope:                         0.000 - 58.139 deg   (mean 1.906, median 1.234)
terrain CRS values present:    EPSG:26918 only
schema:                        7 columns, matches caprm.terrain.OUTPUT_COLUMNS
```

Plausibility: the 75.0 m elevation floor is consistent with Lake Ontario
(~74.2 m). The 1.234 degree median slope is consistent with a flat lake-plain
county. The 58.139 degree maximum is consistent with the Genesee gorge. These
are consistency observations, not independent verification against an
external elevation source.

Slope is preserved as terrain evidence and does not enter the exposure index.

---

# 13. Preliminary Exposure Index

Implemented module:

```text
python/caprm/scoring.py
```

Implemented generation script:

```text
python/scripts/build_exposure_index.py
```

Scoring policy version:

```text
preliminary_exposure_index_v2
```

The index has four components, each with one declared weight. No component
applies an internal sub-weight, so the manifest's weights plus the two
evidence tables are sufficient to reproduce the index. That property is a
requirement, and `audit_milestone3_products.py` verifies it against the
stored artifact on every run.

```text
component          weight   evidence                        normalization
fema               0.40     fema_zone, matched_fema_polygon absolute lookup
water              0.35     nearest_water_distance_m        percentile rank
terrain_absolute   0.15     terrain_elevation_m             percentile rank
terrain_relative   0.10     terrain_relative_elevation_m    percentile rank
```

The v1 policy applied 0.25 to a terrain component split internally 0.60
absolute / 0.40 relative. Scoring is linear, so the flat and nested forms are
algebraically identical: 0.25 x 0.60 = 0.15 and 0.25 x 0.40 = 0.10. Verified
across the countywide workload at a maximum absolute difference of 5.0e-13,
and locked by `test_flat_weights_reproduce_legacy_nested_policy`.

The nesting was removed because the sub-weights were absent from
`DEFAULT_WEIGHTS`, unchecked by `validate_weights`, and absent from every
manifest. The consequence was not cosmetic: the manifest could not reproduce
the score.

Current flow:

```text
validated evidence
    v
component normalization
    v
component scores
    v
explicit weighting
    v
composite exposure index, rounded to 9 decimal places
    v
countywide percentile ranking
```

Weights are configurable through `--weights` on `build_exposure_index.py`.
`summarize_exposure_index` requires weights as an argument rather than
defaulting, so an alternative scenario cannot report the baseline
configuration.

The scoring product is downstream from the source-family evidence products.
Scoring changes do not modify the underlying FEMA/water or terrain evidence.

---

# 14. Exposure Index Output

Scoring policy `preliminary_exposure_index_v2`. Verified 2026-07-16:

```text
output sha256:             3cae2e830a5867bee4d51a36f1c5c04f05ee0a6a26d64dace27da75d3c4911b0
properties:                267,362
unique property IDs:       267,362
index minimum:             7.914598933
index maximum:             99.929084911
index mean:                34.63218408001099
index median:              33.7284299935
index standard deviation:  13.063711939924076
percentile minimum:        0.00037402473051518164
percentile maximum:        100.0
weights:                   fema 0.40, water 0.35, terrain_absolute 0.15, terrain_relative 0.10
```

Measured component influence:

```text
component          weight   std      variance share   Spearman vs index
water              0.35     28.868   0.653            0.893
fema               0.40     11.391   0.168            0.235
terrain_absolute   0.15     28.868   0.135            0.431
terrain_relative   0.10     28.868   0.043            0.167
```

Nominal weight is not influence. Water carries 35% of the weight and 65% of
the variance; FEMA carries 40% and 17%. The three percentile components are
uniform by construction, so their standard deviation is pinned at
100/sqrt(12) = 28.87. The FEMA component is concentrated: 262,297 of 267,362
properties (98.1%) are tied at 10.0.

This is not a defect. FEMA adds a constant to 98.1% of properties, and
constants do not affect ranking. Its role is to move the 1.9% it has
information about decisively: an AE property receives 0.40 x (95 - 10) = +34
on a composite whose standard deviation is 13.06.

See `docs/scoring_methodology.md` section 12.

The composite is rounded to 9 decimal places before ranking. See section 10
of the methodology document for the lattice derivation.

---

# 14b. Measured Scoring Input Domain

Generated by `python/scripts/summarize_scoring_inputs.py` ->
`outputs/validation/scoring_inputs_summary.json`.

Evidence table: 267,362 rows, 267,362 unique IDs, 24 columns, all six
scoring-required columns present, `distance_crs` = EPSG:26918 only.

FEMA zone x SFHA distribution:

```text
matched   X    not SFHA   262,297
matched   AE   SFHA         4,226
matched   A    SFHA           408
matched   AO   SFHA           388
matched   VE   SFHA            39
unmatched      no zone          4
                          -------
                          267,362
```

These counts independently match those recorded in `docs/milestone_2.md`.

Consequences for the scoring implementation:

1. Every zone present in the data is explicitly enumerated by
   `fema_component_score`. No property reaches the unmatched default except
   the 4 unmatched. The unhandled-zone gap is latent, not active. A matched
   property in an unenumerated zone now raises rather than scoring 0.0,
   which would have placed it below zone X.
2. `is_sfha` is perfectly collinear with `fema_zone` in this workload and
   adds no information to the component. It is retained as a validation
   cross-check enforcing that a property cannot be SFHA without matching a
   flood-hazard polygon.
3. The v1 `is_sfha & score < 80 -> 90` override was unreachable: all 5,061
   SFHA properties already score 80 or above from their zone alone. Removed
   in v2 rather than left as dead, untested code.

Nearest-water distance: 0.0 - 2,630.235 m, mean 506.411, median 325.346,
0 nulls, 266 properties at exactly zero, 265,773 distinct values.

Terrain slope: 0 nulls confirmed, so no property fell on a raster edge where
the 3x3 slope window would be unavailable.

Manifest schema inconsistency, measured:

```text
property_flood_evidence_countywide_manifest.json   evidence_summary / output_csv
property_terrain_evidence_countywide_manifest.json summary / output
property_exposure_index_countywide_manifest.json   summary / output
```

Three evidence products, two manifest conventions. Deliberate decision:
`caprm.audit.manifest_field` reads both and records which convention each
artifact uses. Unifying would require regenerating a validated upstream
Milestone 2 product for a cosmetic gain.

---

# 14c. Sensitivity Result

Generated by `python/scripts/analyze_scoring_sensitivity.py` ->
`outputs/validation/scoring_sensitivity_manifest.json`.

```text
verdict:                       moderately sensitive
scenarios:                     40
plausible scenarios:           36
reference corners:             4
minimum Spearman:              0.875  (equal weighting)
median Spearman:               0.996
minimum top-decile overlap:    0.761  (equal weighting)
median top-decile overlap:     0.946
maximum percentile shift:      47.5
median of median shift:        1.56
reference corner Spearman:     0.167 - 0.893
reference corner overlap:      >= 0.289
```

Thresholds were declared in `caprm.sensitivity` before any result was
measured: stable requires >= 0.95 Spearman and >= 0.80 top-decile overlap;
moderately sensitive requires >= 0.85 and >= 0.60. They are a judgement call
with no external standard. The verdict is driven by the worst plausible
scenario, not the average.

The reference corners calibrate the metric. Three of four components are
percentile ranks, and reweighting a linear sum of rank variables tends to
preserve order, so a high correlation could have been an artifact of the
design rather than a finding. The corners span 0.167 to 0.893, so the metric
discriminates and the plausible-scenario results can be interpreted.

The verdict hinges on one scenario. Every other plausible scenario sits near
0.996. `equal` alone falls below the stable bar. This is not general
instability; it is one specific sensitivity: the index is stable unless you
stop privileging water.

`water_only` correlates 0.893 with the baseline, higher than `equal` at
0.875. Putting all weight on water alone reproduces the baseline ranking
better than weighting all four components equally. The baseline is
substantially a water-proximity ranking with a decisive FEMA correction on
the 1.9% of properties FEMA has information about, adjusted by terrain.

Per-property rank variability across the 36 plausible scenarios:

```text
median percentile range:       18.0
mean percentile range:         18.9
p95 percentile range:          39.7
maximum percentile range:      63.0
properties moving > 10 points: 207,417  (77.6%)
properties moving > 25 points:  69,041  (25.8%)
```

The extremes are immovable and the middle churns. Top-ranked properties vary
by 0.0004 percentile points across all 36 scenarios. All 20 most-unstable
properties have a baseline percentile between 59 and 66.

The honest summary: the index reliably identifies the extremes; the middle
ordering depends on weighting assumptions.

---

# 14d. Product Audit

Generated by `python/scripts/audit_milestone3_products.py` ->
`outputs/validation/milestone3_audit.json`. Exits nonzero on any failure.

```text
status: warn
pass 49   warn 1   fail 0
```

The single warning is `manifest_schema_consistency`, the documented
divergence described in section 14b.

Verified: manifest checksums match the files on disk; all four products
describe the same 267,362 properties; the manifest's weights reproduce the
stored index; relative elevation reproduces from elevation minus local mean;
the stored percentile reproduces from the stored index; output is sorted by
property_id; every component and composite value lies within 0-100.

The audit reads the stored artifacts rather than the code that produced
them, so it catches drift the unit tests cannot see. Its highest-value check
is the manifest checksum: nothing else in the pipeline notices an artifact
regenerated without its manifest, and once that happens every provenance
claim about the artifact is false.

---

# 15. Milestone 3 Documentation

Generated summary:

```text
outputs/validation/milestone3_results_summary.md
```

Produced by `python/scripts/summarize_milestone3_results.py` from the terrain
and index manifests. Reads no CSV.

Repository documentation:

```text
docs/milestone_3.md            Runbook: prerequisites, environment, source
                               acquisition, pipeline with exact commands,
                               validation criteria, known asymmetries
docs/scoring_methodology.md    Component definitions, weights, rounding,
                               influence, sensitivity verdict
docs/data_sources.md           Provenance for all five source families
docs/crs_policy.md             Projections, vertical datum, distortion
docs/validation.md             Python/C++ agreement contract and results
docs/benchmark_results.md      Nearest-water benchmark methodology
docs/milestone_1.md            Milestone 1 method and results
docs/milestone_2.md            Milestone 2 method and results
```

---

# 16. Test Status

Measured on 2026-07-16:

```text
python -m pytest -q
181 passed
```

Per module:

```text
tests/test_scoring.py       44
tests/test_sensitivity.py   38
tests/test_audit.py         38
pre-existing modules        61
```

This supersedes `55 passed in 1.06s` in `README.md`, which is stale.
`docs/milestone_2.md` records the same figure correctly as a Milestone 2
historical record.

---

# 17. Current Evidence-Product Boundaries

The project currently maintains the following logical separation:

```text
FEMA/water evidence
terrain evidence
exposure index
```

Future architecture will add:

```text
precipitation evidence
```

These products should remain logically separate.

Current rule:

> Do not overwrite the validated Milestone 2 FEMA/water evidence when adding terrain or rescoring the exposure index.

The final index may join multiple source families, but source evidence should remain independently inspectable and reusable.

---

# 18. Current Validation Position

Established:

```text
FEMA polygon membership, Python/C++ exact agreement at every scale
nearest-water spatial computation, max error 4.658e-10 m countywide
deterministic fixture behavior
composite arithmetic reproduces the artifact to 5.0e-10
the four-weight model reproduces the retired nested policy exactly
the stored percentile reproduces from the stored index
every component's directionality is tested
determinism and row-order independence are tested
non-default weights reach the composite and are reported correctly
components are near-orthogonal, max pairwise |rho| = 0.152
rank stability measured across 40 scenarios with declared thresholds
all four products describe the same 267,362 properties
manifests agree with the artifacts on disk
```

Not established:

```text
whether the weights are defensible
whether the four components are the right components
whether the index corresponds to any real-world flood outcome
```

No validation against observed flooding has been attempted, and none is
planned. Sensitivity measures how much the ranking depends on the weights; it
does not establish that the weights are right.

---

# 19. Milestone 3 Work — Complete

```text
A1  reconstruct and audit current scoring behavior    COMPLETE
A2  harden scoring methodology                        COMPLETE
A3  implement sensitivity analysis                    COMPLETE
A4  audit terrain and index evidence products         COMPLETE
A5  regenerate and freeze final Milestone 3 artifacts COMPLETE
A6  reproducibility and runbook documentation         COMPLETE
```

Milestone 3 is frozen.

---

# 19b. The Unexploited Result in the Milestone 2 Benchmark

Derived on 2026-07-16 by arithmetic on counters already recorded in
`outputs/benchmark/water_cpp_benchmark_countywide_runs.csv` and
`docs/benchmark_results.md`. No new measurement was taken.

```text
brute-force segment checks   284,248,316,558 / 267,362 =  1,063,159 per property
indexed segment checks        18,921,369,157 / 267,362 =     70,771 per property
BVH candidate features                                          5.498 per property

segment checks per candidate feature    70,771 / 5.498 =     12,872
average water feature      1,063,159 segments / 8,572  =        124 segments

                                          12,872 / 124 =       104x
```

**The Feature BVH selects features roughly 104 times larger than the average
water feature.**

This is structural rather than a defect. Lake Ontario, the Genesee River, and
the Erie Canal are each one feature, each enormous, and each near almost
everything in the county. Best-first traversal descends into one of them and
then checks every segment it contains, because the tree indexes **features,
not geometry**. The bounding box of Lake Ontario is a poor proxy for the
distance to Lake Ontario.

This is why pruning stops at 93.34 percent rather than 99.9 percent: the index
stops discriminating precisely where the work is concentrated.

It is also why the granularity change is what makes a learned index legitimate
here. 8,572 features is far below the scale at which learned index structures
are meaningful; roughly 1,063,159 segments is squarely within it. The project's
own data forced the granularity, and the granularity is what makes the
comparison honest rather than contrived.

## Where this leads

Segments are small and roughly uniform, so unlike features they can be ordered
along a space-filling curve by a representative point without the ordering
becoming meaningless. That is what makes a learned index possible at all — and
it places the project in a corner of the literature that has not been examined,
because learned spatial indexes are evaluated almost exclusively on point data
and several return approximate results.

See Nucleus section 14b for the research question, the citations establishing
the gap, and the search-radius inflation that representative-point ordering
imposes on extended objects.

---

# 20. Not Yet Implemented

## Milestone 4 — learned indexing of extended spatial objects

```text
1. brute force              no index                    existing
2. Feature BVH              2D,  8,572 features         existing
3. Segment BVH              2D, ~1M segments            not started
4. Hilbert + binary search  1D, ~1M segments            not started  control
5. Hilbert + RMI            1D, ~1M segments            not started  learned
6. + learned radius         seeds the search disk       not started  stretch
```

Supporting work, none started:

```text
maximum segment length L measured
run-size parameter swept
disk-to-curve-range decomposition
search-radius inflation characterized
neural surrogate, spatial-block split
```

Nothing in Milestone 4 changes the exposure index, the evidence products, or
the exact distance kernel. Every implementation that claims exactness must
reproduce the existing Python reference field-for-field through the existing
comparison harness.

Implementation 4 is not optional. Without it, comparing a segment index against
a learned index confounds the dimensionality reduction with the learning.

## Precipitation — gated stretch goal

Permitted only after the Milestone 4 computational work is complete and
documented. See Nucleus section 14b.

## Final scoring/index freeze

The index is frozen at `preliminary_exposure_index_v2` and remains labelled
preliminary. Under the Milestone 4 scope it is no longer the subject of active
work; if precipitation lands as a stretch goal, the index would be revisited
at that point and not before.

## Final end-to-end reproducibility audit

Not yet performed as one operation. See PHASE D.

## Runtime instrumentation

The project has detailed C++ benchmarks and no measurement of the Python
pipeline that produces every Milestone 3 result. See PHASE D2.

---

# 21. Immediate Next Task

```text
B1. Measure the maximum segment length, then rebuild the index at
    segment granularity
```

## Measure L first

Before writing any index code, measure the longest segment in the cached
hydrography. It is one pass over `data/raw/usgs_3dhp_monroe.gpkg`.

`L` determines whether search-radius inflation is a footnote or the entire
story. Ordering extended objects by a representative point requires searching
`disk(r + L/2)` to remain exact, so a single long segment — a straight canal
reach represented as one segment, for instance — inflates every query in the
index.

If `L` is small relative to typical nearest-water distances, which have a
median of 325 m, inflation is cheap and the rest of the phase proceeds as
planned. If `L` is large, splitting long segments at a maximum length becomes a
parameter with a cost, and that is a finding rather than an inconvenience.

Do not design around this number before measuring it.

## Then rebuild at segment granularity

The Feature BVH indexes 8,572 features. Rebuild the hierarchy over roughly
1,063,159 segments, reusing the exact distance kernel, the 1e-6 m tie
tolerance, and lexicographic tie-breaking on `water_feature_id` without
modification. Each leaf must retain the parent feature's `water_feature_id`,
because the tie rule resolves on it.

This is expected to beat the Feature BVH substantially, and it is the honest
baseline the learned index must then beat. Racing a learned index against the
Feature BVH rather than against a segment index would be a rigged comparison
and an examiner would see it immediately.

Doing it first also de-risks the phase: it lands in days, it produces a result
either way, and it uses only infrastructure that already exists.

## Acceptance

The existing comparison harness reports the same exact agreement it reports
today, because nothing about the semantics changed. If agreement degrades, the
kernel was touched and the change is wrong.

See `CAPRM_Flood_Roadmap.md` PHASE B and Nucleus section 14b.

## Deferred to PHASE D

Recorded and not blocking:

- `data/raw/usgs_3dhp_monroe.gpkg` is tracked at 21 MB despite matching
  `*.gpkg` in `.gitignore`. It is the only large tracked file in the
  repository.
- `inventory_repository.py` computes `expected_paths` but never prints it, so
  the check is silent on the console.
- Empty tracked files from Milestone 1:
  `outputs/validation/fema_pip_refresh_stderr.txt` and `_stdout.txt`.
- Untracked local course files awaiting a decision: `how-ref`,
  `m2_presentation_script.docx`, `MILESTONE 2 PRESENTATION NOTES.docx`,
  `report body .docx`, `presentation_assets/`.
- No runtime instrumentation for the Python pipeline. See PHASE D2.
- `explain_property.py` remains unbuilt. Tracing one property from coordinates
  to rank is the strongest available demo.

---

# 22. Recommended First Prompt for a New AI Assistant

Use:

> We are continuing CAPRM-Flood at Milestone 4, chunk B1. Read Nucleus section
> 14b, this document's sections 19b and 21, and `CAPRM_Flood_Roadmap.md`
> PHASE B before proposing anything.
>
> Confirm the commit recorded in this document's section 2 matches
> `git log -1 --oneline`. If it does not, say so before continuing — you are
> reading a stale copy.
>
> Milestones 1 through 3 are frozen. The exposure index is not under active
> work and must not be modified.
>
> B1 measures the maximum segment length in the cached hydrography, then
> rebuilds the water spatial index over segments rather than features. Inspect
> `cpp/spatial_core/src/water_distance_indexed.cpp` and
> `python/caprm/water_distance.py` and state their current behavior from source
> before proposing a change.
>
> The exact distance kernel, the 1e-6 m tie tolerance, and lexicographic
> tie-breaking on water_feature_id do not change. Acceptance is that the
> existing comparison harness reports the same exact agreement it reports
> today.

---

# 23. Current Canonical Summary

As of July 16, 2026, CAPRM-Flood has completed and frozen Milestones 1, 2, and
3. Three evidence families spanning three different data topologies — FEMA
vector polygons, hydrography lines and areas, and a terrain raster — produce
one evidence contract for 267,362 unique Monroe County properties, with exact
Python/C++ agreement on every compared field at every scale. Milestone 3 added
a four-component exposure index at scoring policy
`preliminary_exposure_index_v2`, measured component influence by exact variance
decomposition, characterized the ranking as moderately sensitive to weight
choice across 40 configurations with metric calibration, and shipped an
automated product audit that verifies the stored artifacts against their own
manifests. The suite passes at 181 tests and the audit reports no failures. The
index is frozen and remains preliminary; it is the application layer, not the
claim. Milestone 4 concentrates the project's computer-science contribution on
a question its own Milestone 2 benchmark raised and did not answer: the Feature
BVH examines only 5.498 candidate features per property yet still performs
70,771 segment checks, because it indexes features rather than geometry and the
largest water features are near everything. Rebuilding at segment granularity
leads into a corner of the literature that has not been examined — learned
spatial indexes are evaluated almost exclusively on point data and several
return approximate results, whereas this project's data is extended objects and
its query is exact nearest neighbour. Milestone 4 therefore measures the
maximum segment length, sweeps the run-size parameter that trades pruning
against search-radius inflation, orders segments along a Hilbert curve,
validates the resulting query path with a binary-search control that isolates
the contribution of learning from the contribution of dimensionality reduction,
trains a recursive model index, and benchmarks the result against an exact
baseline whose correctness is already proven field-by-field against an
independent implementation. Precipitation remains a gated stretch goal behind
that work.
