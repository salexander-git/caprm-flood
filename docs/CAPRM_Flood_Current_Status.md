# CAPRM-Flood Current Status — 2026-07-15

## Purpose

This document records the exact current operational state of CAPRM-Flood as of **July 15, 2026**.

It is intended to answer:

- What is implemented now?
- What has been validated?
- What files and outputs currently exist?
- What is committed to GitHub?
- What remains unfinished in Milestone 3?
- What should the next implementation conversation begin with?

For durable project identity, architecture, and design principles, see:

```text
CAPRM_Flood_Project_Nucleus_2026-07-15.md
```

For ordered future work, see:

```text
CAPRM_Flood_Roadmap.md
```

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
Milestone 3: substantially implemented, not yet frozen as complete
Milestone 4: not yet started as a dedicated implementation phase
```

The immediate priority is to finish and harden Milestone 3.

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
python/scripts/summarize_scoring_inputs.py     (new, added during Milestone 3 A1)
```

Ignored by rule, not untracked:

```text
milestone2_closeout_context.zip                (*.zip)
.venv/  .pytest_cache/  cpp/spatial_core/build/
```

`summarize_scoring_inputs.py` is real source and should be committed with the
A1 work. The remainder are local presentation, editor, and scratch files to be
triaged separately.

## Documentation state

The repository tracks `docs/CAPRM-Flood Project Nucleus 6.2.26.pdf`, the
superseded June 2 nucleus, which describes the project as still in the
Milestone 1 spike phase.

The current canonical documents — this file, the July 15 nucleus, and the
roadmap — are **not** in the repository.

A visitor to GitHub therefore finds only the stale nucleus. This must be
corrected in A6.

---

# 4. Current `.gitignore` Policy

The repository currently ignores:

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
```

Important consequence:

Some older files under `data/raw/`, `data/processed/`, and `outputs/` are still tracked because they were committed before the ignore rules were applied.

Current examples include:

```text
data/processed/monroe_property_points_sample.geojson
data/raw/usgs_3dhp_monroe.gpkg

outputs/baseline/python_fema_membership.csv
outputs/baseline/python_nearest_water.csv
outputs/benchmark/water_cpp_benchmark_runs.csv
outputs/cpp/cpp_nearest_water_bruteforce.csv
outputs/cpp/cpp_nearest_water_indexed.csv
outputs/validation/*.json
outputs/validation/*.csv
```

This is not blocking current development, but repository cleanup may be appropriate later.

---

# 5. Current Core Source Tree

Important tracked source modules currently include:

```text
python/caprm/
├── __init__.py
├── baseline.py
├── crs.py
├── evidence.py
├── export.py
├── hydrography.py
├── ingest.py
├── scoring.py
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
└── summarize_milestone3_results.py
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
├── test_baseline.py
├── test_evidence.py
├── test_export.py
├── test_hydrography.py
├── test_ingest.py
├── test_materialize_countywide_property_workload.py
├── test_scoring.py
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

Milestone 3 currently includes two major implemented components:

```text
A. terrain evidence extraction
B. preliminary exposure-index generation
```

These are implemented and tested, but Milestone 3 is not yet formally frozen as complete.

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
and the generated CSV on 2026-07-15:

```text
properties:                    267,362
unique property IDs:           267,362
null elevation:                0
null relative elevation:       0
null slope:                    0
elevation:                     75.000 – 296.309 m   (mean 143.197, median 146.828)
relative elevation:            -20.669 – +30.149 m  (mean 0.247, median 0.175)
slope:                         0.000 – 58.139°      (mean 1.906, median 1.234)
terrain CRS values present:    EPSG:26918 only
schema:                        7 columns, matches caprm.terrain.OUTPUT_COLUMNS
```

Plausibility: the 75.0 m elevation floor is consistent with Lake Ontario
(~74.2 m). The 1.234° median slope is consistent with a flat lake-plain county.
These are consistency observations, not independent verification against an
external elevation source.

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

The scoring layer consumes validated evidence and produces a deterministic relative exposure index.

Current conceptual flow:

```text
validated evidence
    ↓
component normalization
    ↓
component scores
    ↓
explicit weighting
    ↓
composite exposure index
    ↓
countywide percentile/ranking context
```

The scoring product is downstream from the source-family evidence products.

Scoring changes should not modify the underlying FEMA/water or terrain evidence.

---

# 14. Exposure Index Output

Verified from the index manifest and CSV on 2026-07-15:

```text
properties:                267,362
unique property IDs:       267,362
index minimum:             7.914598933281469
index maximum:             99.92908491109432
index mean:                34.63218408001137
index median:              33.72842999379119
percentile minimum:        0.00037402473051518164
percentile maximum:        100.0
mean FEMA component:       11.580179681480539
mean water component:      50.00018701236526
mean terrain component:    50.00018701236526
weights recorded:          fema 0.40, water 0.35, terrain 0.25
```

The composite arithmetic reproduces exactly:

```text
0.40(11.580179681480539) + 0.35(50.00018701236526) + 0.25(50.00018701236526)
  = 34.63218408001137 = mean_exposure_index
```

The water and terrain component means are identical at 50.00018701236526,
which equals (n+1)/(2n)·100 for n = 267,362. This is the structural signature of
percentile normalization and confirms the transform behaves as specified.

These values reflect the preliminary scoring configuration and are not the
frozen Milestone 3 result.

# 14b. Measured Scoring Input Domain

Generated by `python/scripts/summarize_scoring_inputs.py` →
`outputs/validation/scoring_inputs_summary.json` on 2026-07-15.

Evidence table: 267,362 rows, 267,362 unique IDs, 24 columns, all six
scoring-required columns present, `distance_crs` = EPSG:26918 only.

FEMA zone × SFHA distribution:

```text
matched  X    not SFHA   262,297
matched  AE   SFHA         4,226
matched  A    SFHA           408
matched  AO   SFHA           388
matched  VE   SFHA            39
unmatched     no zone          4
                          -------
                          267,362
```

Consequences for the current scoring implementation:

1. Every zone present in the data is explicitly enumerated by
   `fema_component_score`. No property reaches the 0.0 default except the
   4 unmatched. The unhandled-zone gap is **latent, not active**.
2. The `is_sfha & score < 80 → 90` override is **unreachable on this data**.
   All 5,061 SFHA properties already score 80 or above from their zone alone.
   The rule is both untested and dead.
3. `is_sfha` is perfectly collinear with `fema_zone` here and adds no
   information to the component.

Nearest-water distance: 0.0 – 2,630.235 m, mean 506.411, median 325.346,
0 nulls, 266 properties at exactly zero, 265,773 distinct values
(1,589 tied distances resolved by average rank).

Terrain slope: 0 nulls confirmed, so no property fell on a raster edge where
the 3×3 slope window would be unavailable.

Manifest schema inconsistency, measured:

```text
property_flood_evidence_countywide_manifest.json   evidence_summary / output_csv
property_terrain_evidence_countywide_manifest.json summary / output
property_exposure_index_countywide_manifest.json   summary / output
```

Three evidence products, two manifest conventions. Any tool reading manifests
generically must handle both, or the schema should be unified in A4.

---

# 15. Milestone 3 Summary Artifact

Implemented script:

```text
python/scripts/summarize_milestone3_results.py
```

Current generated summary:

```text
outputs/validation/milestone3_results_summary.md
```

This summary should be regenerated after the final Milestone 3 scoring and validation decisions are fixed.

---

# 16. Test Status

Measured on 2026-07-15 at commit `0dd85ab`:

```text
python -m pytest -q
69 passed in 3.78s
```

No warnings were reported in the summary line.

This supersedes the `55 passed in 1.06s` figure still recorded in `README.md`
and `docs/milestone_2.md`. The Milestone 2 document's figure is correct as a
historical Milestone 2 record; the README's is stale and must be corrected.

The suite must be rerun and this count re-recorded after every remaining
Milestone 3 change.

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

Current validation strength is highest for:

```text
FEMA polygon membership
nearest-water spatial computation
deterministic fixture behavior
Python/C++ cross-implementation agreement
```

Terrain validation currently includes:

- automated unit tests;
- successful projected raster preparation;
- successful countywide property extraction;
- complete slope coverage in the current countywide output;
- manifest/provenance capture.

Before Milestone 3 is frozen, terrain validation should be reviewed for whether additional targeted plausibility checks or sampled manual/independent checks are warranted.

The exposure index currently has deterministic implementation tests, but the main remaining validation question is methodological rather than purely computational:

```text
How sensitive are rankings and conclusions to scoring normalization and component-weight assumptions?
```

That question remains a central unfinished Milestone 3 task.

---

# 19. Remaining Milestone 3 Work

Milestone 3 should not yet be declared complete.

Remaining work is expected to include the following major areas.

## 19.1 Scoring methodology hardening

Review and finalize:

- exact component normalization;
- directionality of each component;
- clipping/bound behavior;
- missing-value policy;
- component weights;
- interpretation of the composite index;
- percentile/rank semantics.

The implementation should remain explicit and deterministic.

## 19.2 Sensitivity analysis

Evaluate how stable countywide rankings are under plausible alternative scoring weights or configurations.

The goal is to determine whether the ranking is:

- broadly stable;
- moderately sensitive;
- highly dependent on one component or one weighting assumption.

The final system should report this honestly.

## 19.3 Terrain/index audit

Audit:

- row counts;
- unique property IDs;
- null values;
- field ranges;
- CRS metadata;
- manifest content;
- source checksums;
- join completeness;
- deterministic regeneration.

## 19.4 Final Milestone 3 artifact regeneration

After the scoring policy is finalized:

- regenerate terrain evidence if necessary;
- regenerate exposure index;
- regenerate manifests;
- regenerate milestone summary;
- rerun the full test suite;
- record final summary statistics.

## 19.5 Reproducibility/runbook cleanup

Ensure another technically competent person can reproduce the Milestone 3 pipeline from documented commands.

This likely requires:

- confirming script order;
- documenting required inputs;
- documenting expected outputs;
- documenting environment/dependencies;
- documenting large-file handling;
- clarifying which outputs are generated versus Git-tracked.

## 19.6 Documentation update

Update current repository documentation so that it no longer presents the project as stopping at Milestone 2.

The new canonical context files should also be added deliberately once complete.

---

# 20. Not Yet Implemented

As of July 15, 2026, the following major planned work remains outside the completed implementation.

## Precipitation evidence

A dedicated precipitation evidence family has not yet been completed.

Expected future role:

- add extreme precipitation / precipitation-frequency context;
- use a defensible public source;
- preserve provenance;
- keep the precipitation evidence product separate from the score.

## Final scoring/index freeze

The preliminary index exists, but the final scoring policy has not yet been frozen.

## Final end-to-end reproducibility audit

The project has strong reproducibility mechanisms already, but the full final workflow still needs to be documented and audited as a complete system.

## Final report / final presentation completion

These are not the current implementation priority.

---

# 21. Immediate Next Task

```text
A1 completion: write docs/scoring_methodology.md
```

Reconstruction is complete. Current scoring behavior has been established from
source and confirmed against measured artifacts, recorded in §14, §14b, and
`outputs/validation/scoring_inputs_summary.json`.

The remaining A1 deliverable is the written specification. No further terminal
output or artifact generation is required to produce it.

A2 must not begin until that document exists.

---

# 22. Recommended First Prompt for a New AI Assistant

Use:

> We are continuing CAPRM-Flood from an existing implementation. Read `CAPRM_Flood_Project_Nucleus_2026-07-15.md`, `CAPRM_Flood_Current_Status.md`, `CAPRM_Flood_Roadmap.md`, and the current repository before proposing changes.
>
> We are currently finishing Milestone 3.
>
> First inspect and summarize the current scoring implementation in:
>
> - `python/caprm/scoring.py`
> - `python/scripts/build_exposure_index.py`
> - `tests/test_scoring.py`
>
> Reconstruct the exact current component scores, normalization rules, weights, missing-value handling, and final ranking behavior.
>
> Then propose a technically defensible sensitivity-analysis plan for the current index.
>
> Do not rewrite the scoring architecture yet. First establish the current behavior and identify the smallest set of changes needed to make the methodology defensible and testable.

---

# 23. Current Canonical Summary

As of July 15, 2026, CAPRM-Flood has completed and validated Milestones 1 and 2, including FEMA point-in-polygon processing, nearest-water evidence, Python/C++ cross-implementation validation, deterministic fixtures, manifests, benchmarks, and countywide scaling. Milestone 3 has added projected DEM preparation, countywide terrain evidence for 267,362 unique properties, zero missing slope values in the current output, and a preliminary deterministic relative exposure index. The current implementation is committed and synchronized to GitHub at commit `0dd85ab`. The full automated test suite has passed. Milestone 3 remains open primarily for scoring-methodology hardening, sensitivity analysis, final artifact auditing/regeneration, and reproducibility/runbook cleanup before the milestone is frozen as complete.
