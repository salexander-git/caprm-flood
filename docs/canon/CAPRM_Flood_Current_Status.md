# CAPRM-Flood Current Status — 2026-07-30

## Purpose of This Document

This document records the exact current operational state of CAPRM-Flood as of **July 30, 2026**.

```text
Verified at commit:   see section 2
Test suite:           486 passed  (full suite, no --ignore)
Product audit:        49 pass, 1 warn, 0 fail
Scoring policy:       preliminary_exposure_index_v2
Phase C partition:    blocked K-fold, b=10,000 m, w=2,125 m, K=5, 5 seeds
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
Milestone 4: index structure and learned approximation — in progress
Milestone 4: chunks B1-B5 complete and validated countywide.
             B1 committed at 998c859; B2 (entry-extent sweep, verification-
             mode fork), B3a/B3b (Hilbert ordering, exact inflated-disk query,
             countywide agreement, inflation cost, box-vs-disk gate) and B4
             (recursive model index) at 97bfb1e, and B5 (RMI inference in
             C++) at f2e2e00. B5c (resolve-descent instrumentation) is
             validated; commit pending. Next chunk: B6.
             Operating point: 25 m entry-extent cap, original verification,
             `disk` region predicate (the default since B4).
             B4 trained a two-stage RMI over the 1,189,589 sorted Hilbert
             keys: 131,072 linear second-stage models, an exhaustive
             per-model error bound, 6.323 mean last-mile probes against the
             binary-search control's 20.2376 (3.20x).
             Immediate next task: B5 (port RMI inference to C++ behind
             `--seed rmi`; acceptance is byte-identical evidence to the
             `--seed binary` control).
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
<C1_REMEDIATION_HASH>  Milestone 4 C1: Phase C modules, tests, scipy pin,
                       partition manifest
```

Replace `<C1_REMEDIATION_HASH>` in the follow-up commit described at the end of
this section. Until it is replaced, this document does not record where its own
state lives, which is precisely the failure this section exists to prevent.

Milestone 4 C1 commit lineage:

```text
9b561d1  C1 partition of record: spatial_kfold, spatial_split, builder, tests.
         INCOMPLETE AS PUSHED — `spatial_kfold.py` imports `caprm.split_gate`,
         which this commit did not contain, so a clean checkout of 9b561d1
         cannot import the module or collect its tests. It also carried B6d's
         documentation edits under a C1 message, and set this section to
         `664a431` while HEAD was `9b561d1`.
<next>   C1 remediation: the twelve dependency modules and tests, the scipy
         pin, and outputs/validation/c1_kfold_manifest.json.
```

Both defects are recorded rather than rewritten. The first is the reason the
clean-clone check below is now part of the commit sequence; the second is the
recurrence this section has already logged twice.

**Step 6.5 of the commit sequence, added 2026-07-30.** Before pushing, verify
that the repository AS TRACKED is complete:

```powershell
git clone --depth 1 . $env:TEMP\caprm-verify
cd $env:TEMP\caprm-verify
python -m pytest -q
```

`git status` cannot detect a commit that depends on an untracked file, because
the file is present locally. A clean clone can. This is the same principle as
B6b's positive control: a check that cannot fail on the condition it targets is
not a check.

Synchronization status at the last check:

```text
HEAD == origin/master
ahead: 0
behind: 0
```

The local repository and GitHub remote are synchronized through commit
86ff32b (HEAD == origin/master, verified 2026-07-29). Milestone 4 commit
lineage:

```text
998c859  B1
27031d9  B2
97bfb1e  B3a, B3b, B4
f2e2e00  B5
00c5fd2  docs: record B5's hash; pin rasterio and its transitive closure
ff8121f  B5c
86ff32b  docs: README and validation.md through B5c
```

Two corrections this section had accumulated. B2 is at 27031d9, not at 97bfb1e
as previously recorded. B5c is committed at ff8121f; the step-8 hash-recording
convention was followed for B5 at 00c5fd2 and lapsed for B5c, which is exactly
the failure mode the convention exists to prevent and is why the recommended
first prompt tells a new assistant to check this hash against `git log -1`
before trusting anything else in this document.

B6a, B6b and B6c are present in the working tree and NOT yet committed; see
section 21.

**A document that records its own commit hash is stale the instant it is
committed.** This is structural, not an oversight, and the fix is a convention
rather than vigilance: every chunk ends with a small follow-up commit whose only
job is to write the previous commit's hash into this section. Treat it as step 8
of the working standard's commit sequence.

**The three canonical documents live under `docs/canon/`, not at the repository
root and no longer directly under `docs/`.** They were moved from `docs/` to
`docs/canon/` on 2026-07-29. `git add CAPRM_Flood_Current_Status.md` fails with
"pathspec did not match any files"; the correct paths are
`docs/canon/CAPRM_Flood_Current_Status.md`,
`docs/canon/CAPRM_Flood_Project_Nucleus_2026-07-15.md` and
`docs/canon/CAPRM_Flood_Roadmap.md`. Confirm with
`git ls-files | Select-String CAPRM_Flood`.

The move should be staged as a rename so history follows the files:
`git add -A docs/` will detect it. Anything that referenced the old paths —
`README.md`, `docs/kickoff_prompts_m4.md`, `docs/caprm_flood_m4_chunking_plan.md`
— must be updated in the same commit, or the pointers a new assistant is told to
follow will be dead.

`models/` is a tracked directory and `models/water_hilbert_rmi.bin` is tracked
and clean: `git check-ignore -v models/water_hilbert_rmi.bin` prints nothing,
so no ignore rule matches and no force-add is needed.

Uncommitted in the working tree after the B5 commit, unrelated to Milestone 4
and not to be staged with it:

```text
 M docs/caprm_flood_m4_chunking_plan.md
 M docs/caprm_flood_m4_kickoff_prompts.md
 M docs/scoring_methodology.md
   (plus course, poster, and presentation files)
```

`python/caprm/spatial_split.py`, `python/caprm/build_spatial_split.py` and
`tests/test_spatial_split.py` are no longer untracked; they were committed at
C1 together with the Phase C modules built on them. `requirements.txt` is
committed with `scipy==1.18.0` pinned.

Two items previously flagged here are resolved:

- **`requirements.txt` — reviewed 2026-07-28 and APPROVED for commit.** The
  26-line diff is a reproducibility improvement, not drift. It pins
  `rasterio`, which was the file's one unpinned dependency and therefore its one
  open reproducibility hole; it adds the transitive closure from `pip freeze`
  (affine, attrs, click, cligj, colorama, contourpy, cycler, fonttools,
  iniconfig, kiwisolver, pillow, pluggy, Pygments, pyparsing); it documents
  `pytest>=8.0,<9.0` as a deliberate range to be pinned exactly at the PHASE D
  freeze; and it carries a commented `# scipy==` with an instruction to pin it
  in the SAME change that commits `spatial_split.py`, which is exactly the
  discipline section 16 asks for. Two follow-ups, neither blocking: `matplotlib`
  is now pinned but is imported by no tracked module — it belongs to the poster
  and chart work, so either mark it as such or split a dev-requirements file —
  and the file has no trailing newline.
- **`--keys`**, a stray file created by a malformed `train_hilbert_rmi.py`
  invocation in which the flag was consumed as a path, has been deleted.

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

Untracked, part of B2 (stage in the B2 commit):

```text
python/scripts/sweep_segment_bvh_cap.py
python/scripts/plot_segment_bvh_cap_sweep.py
tests/cpp/test_water_segment_bvh_verify_modes.cpp
```

Untracked, part of B3a (stage in the B3a commit; place at repo paths shown):

```text
cpp/spatial_core/src/water_distance_hilbert.cpp
tests/cpp/hilbert_probe.cpp
tests/fixture_crosscheck.py                    (MODIFIED: extended to Hilbert)
```

Untracked, part of B4 (stage in the B4 commit; place at repo paths shown):

```text
python/caprm/rmi.py
python/scripts/train_hilbert_rmi.py
tests/test_rmi.py
models/water_hilbert_rmi.bin                   (tracked artifact; see section 4)
outputs/validation/water_hilbert_rmi_manifest.json
outputs/validation/water_hilbert_countywide_manifest_b4.json
cpp/spatial_core/src/water_distance_hilbert.cpp  (MODIFIED: disk default,
                                                  --dump-keys)
tests/fixture_crosscheck.py                    (MODIFIED: optional trailing
                                                  positionals, default-predicate
                                                  and key-dump checks)
```

Untracked, NOT part of B2 — Phase C spatial-split WIP, do not stage with B2:

```text
python/caprm/spatial_split.py
python/caprm/build_spatial_split.py
tests/test_spatial_split.py
```

Untracked presentation, report, and scratch — triage separately, do not stage:

```text
docs/*.docx  docs/report/*  docs/sample_poster_*.pdf
presentation_assets/  how-ref
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
├── hilbert_inflation.py     (Milestone 4 B3b)
├── hydrography.py
├── ingest.py
├── rmi.py                   (Milestone 4 B4)
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

Section 5 was written before Milestone 4 and had drifted; the Milestone 4
modules above were added at B3b and B4 and are now listed rather than left to
the per-chunk file lists in section 21.

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
├── compare_seed_modes.py            (Milestone 4 B5c)
├── prepare_terrain_raster.py
├── rmi_probe_args.py                (Milestone 4 B5c)
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
├── water_distance_bruteforce.cpp        implementation 1
├── water_distance_indexed.cpp           implementation 2
├── water_distance_segment_bvh.cpp       implementation 3   (B1)
└── water_distance_hilbert.cpp           implementations 4/5 (B3/B4/B5)
```

Tracked model artifacts:

```text
models/water_hilbert_rmi.bin   4,194,400 bytes  (Milestone 4 B4)
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
├── test_water_validate.py
├── test_hilbert_inflation.py            (Milestone 4 B3b)
├── test_rmi.py                          (Milestone 4 B4)
├── fixture_crosscheck.py                cross-implementation fixture harness
└── cpp/
    ├── test_water_segment_bvh.cpp       (Milestone 4 B1)
    └── test_water_segment_bvh_verify_modes.cpp   (Milestone 4 B2)
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

Measured on 2026-07-30:

```text
python -m pytest -q
486 passed
```

**The `--ignore=tests/test_spatial_split.py` flag is retired.** scipy is
installed and pinned as `scipy==1.18.0` in `requirements.txt` as of the C1
commit, so `tests/test_spatial_split.py` collects and runs. Any figure in this
document or in `README.md` quoting 181, 257 or 304 tests is superseded.

Phase C added, at C1:

```text
tests/test_spatial_split.py       11   (pre-existing WIP, previously ignored)
tests/test_supervised_dataset.py  11   (C1)
tests/test_spatial_correlation.py 16   (C1)
tests/test_split_gate.py          16   (C1)
tests/test_spatial_kfold.py       20   (C1)
```

The remaining growth from 257 to 486 is Milestone 4 B6's own test modules,
which postdate the 2026-07-28 per-module table above. That table is retained as
a historical record and is no longer a current inventory; regenerate the
breakdown with `python -m pytest --collect-only -q` if a current one is needed.

Two C++ unit suites are not counted above:

```text
tests/cpp/test_water_segment_bvh.cpp                 80021 checks, 0 failures
tests/cpp/test_water_segment_bvh_verify_modes.cpp      607 checks, 0 failures
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
3. Segment BVH              2D, ~1M segments            implemented and validated
4. Hilbert + binary search  1D, ~1M segments            DONE  B3   control
5. Hilbert + RMI            1D, ~1M segments            DONE  B4/B5  learned
6. + learned radius         seeds the search disk       not started  stretch
```

Implementation 3 (Segment BVH) is complete and validated countywide
(`water_distance_segment_bvh.cpp`): field-for-field agreement with the Python
reference on all 267,362 properties, maximum absolute error 4.658e-10 m. Committed at 97bfb1e. See section 21 for the
measured result.

Supporting work:

```text
maximum segment length L measured          done  (B1a: L = 5,748.24 m)
segment splitting implemented              done  (distance-exact, cap 100 m)
entry-extent parameter swept               DONE  (B2, 25 m cap chosen)
grouping half of the extent axis           out of scope, documented
verification-mode A/B fork                 DONE  (B2)
disk-to-curve-range decomposition          not started
search-radius inflation characterized      not started
spatial-block partition for the surrogate  DONE  (C1, blocked K-fold)
neural surrogate                           C2, not started
```

## Open question carried out of C1

`python/caprm/water_validate.py` reads both the Python reference and the C++
output with pandas' default CSV float parser, which C1 measured to be not
correctly rounded (34,221 eastings and 43,206 northings shifted by up to
9.31e-10 m on the countywide coordinate file). `water_export.py:294` writes the
C++ inputs with `%.17g`, so the export side is lossless. Whether the two
implementations ever derive different doubles from the same coordinate text is a
one-line experiment that has NOT been run. It is unlikely to explain the
4.658e-10 m agreement residual — distances are O(10^3) m where the ULP is
~1e-13 — and it is recorded here so the question is not lost rather than as a
finding. It belongs in its own chunk, not in PHASE C.

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
C2. Train the surrogate
```

PHASE B is closed. PHASE C chunk C1 is complete; see the C1 result subsection
below and the C2 statement at the end of this section.

B1 through B5c are complete and validated countywide. Committed: B1 at 998c859,
B2/B3a/B3b/B4 at 97bfb1e, B5 at f2e2e00. B5c's commit is pending. The B1 result
below is retained as the historical baseline; B2, B3a, B3b, B4, B5 and B5c
follow it.

**The three canonical countywide C++ inputs**, recorded here because they existed
only in shell history until B5c and cost three failed runs to rediscover:

```text
outputs/cpp_input/water_properties_projected_countywide.csv
    sample_order,property_id,projected_x,projected_y
outputs/cpp_input/water_features_countywide.csv
outputs/cpp_input/water_vertices_countywide.csv
```

**Trap:** `outputs/cpp_input/properties_projected_countywide.csv` also exists and
is one prefix away. It is the FEMA-side export with schema
`property_id,projected_x,projected_y,longitude,latitude` and no `sample_order`,
so the water binaries reject it. The water family also carries `_10000` and
`_100000` workloads with identical schemas, which gives B6 a scaling axis at no
ingestion cost.

## B1 result — Segment BVH, measured 2026-07-22

B1a — measure L. Over `outputs/cpp_input/water_vertices_countywide.csv`
(sha256 `dbdce9b217e55798b6f2db486fb101ea4226c555b1c07994cd800ff2d46dd09a`):
1,063,159 segments; mean length 9.840 m; **L = 5,748.2396 m**, one boundary
chord of feature_index 7445 (`waterbody:L1E1P`, Lake Ontario). Naive midpoint
inflation L/2 = 2,874 m was therefore untenable and long segments are split
before indexing.

B1b/c — Segment BVH + distance-exact splitting. Implemented in
`cpp/spatial_core/src/water_distance_segment_bvh.cpp`. A BVH over length-capped
sub-segment boxes (cap 100 m), leaves carrying the parent `water_feature_id`,
best-first traversal to collect candidate features, then the **unchanged** exact
kernel and tie rule over those candidates. The reported distance is computed
over original geometry, so output is byte-identical to the reference rather
than merely within tolerance. The kernel, `water_export.py`, and the tie rule
were not modified.

### Split cost (manifest: `outputs/validation/water_segment_split_countywide_manifest.json`)

```text
original segments      1,063,159
split segments         1,068,510
added segments             5,351      +0.50%
max length before      5,748.2396 m
max length after          99.9975 m   57x reduction
segments over 100 m        4,333
segments over 200 m          657
segments over 500 m           19
segments over 1000 m           4
```

Capping is close to free: a 0.50 percent increase in index entries bounds the
`L/2` inflation term from 2,874 m to 50 m. That is a B3 input, not a B1
footnote.

### Countywide agreement (`outputs/validation/water_segment_bvh_summary.json`)

```text
total_union_rows                267,362
all_fields_agree                267,362      exit code 0
maximum_absolute_error_m          4.657998431412125e-10
mean_absolute_error_m             3.731e-11
median_absolute_error_m           3.411e-13
```

The maximum error equals the Feature BVH's countywide figure recorded in
`docs/crs_policy.md`. That is the expected signature: because the distance is
computed by the unchanged kernel over original geometry, the residual is pure
Python/C++ floating-point difference with no index contribution.

### Artifact checks on the countywide output

```text
rows                      267,362
unique property_ids       267,362
nulls in required cols          0
empty feature names       208,340      unnamed 3DHP flowlines, expected
exact-zero distances          266      all class = waterbody
distance range            0.0 to 2,630.2349 m   within the 20,000 m buffer
tie_count minimum               1
distance_crs             EPSG:26918    single value
algorithm                segment_bvh   single value
segment checks total  2,597,922,599    matches the comparator summary
```

All 266 exact zeros resolve to `waterbody` features, which is the direct test of
the interior-zero invariant rather than a count alone.

### Measured query behavior (single countywide run, not a benchmark)

```text
wall clock                       10.135 s
properties per second            26,379.4
index node visits per property       28.29
segment box tests per property        6.49
candidate features per property       1.497
segment checks per property       9,716.87
```

Against the Milestone 2 counters in section 19b:

```text
                    segment checks/property    candidate features/property
brute force              1,063,159                        n/a
Feature BVH                 70,771    93.34% pruned      5.498
Segment BVH                  9,716.87 99.09% pruned      1.497
```

**7.28x fewer segment checks than the Feature BVH** and 109.4x fewer than brute
force. Candidate features fell 3.67x, and the features selected are also
smaller — 6,490 segments each versus the Feature BVH's 12,872 — because the
tighter phase-1 threshold stops admitting the enormous features that section
19b identified as the Feature BVH's failure mode.

**This is a pruning result, not yet a speedup claim.** The 10.135 s is one
unrepeated run; wall-clock comparison requires `benchmark_water_cpp.py` under
its repetition protocol, which is B2/B6 work.

## B2 result — entry-extent sweep, measured 2026-07-23

B2 swept the segment-BVH entry-extent cap at 10, 25, 50, 100, 200, 500, and 0
(no split) metres, each under both verification modes, 7 repetitions with 1
warmup, countywide (267,362 properties). All 14 points agree field-for-field
with the Python reference and the sweep is accepted.

Command (PowerShell):

```text
.\.venv\Scripts\python.exe python\scripts\sweep_segment_bvh_cap.py
```

### Entries, extent, memory, and cost

```text
cap(m)  entries    d vs none  extent(m)   L/2(m)   idx(MB)  chk/p A   sec A   sec B  B x
10      1,683,537   +58.35%     10.000     5.000    157.3   9,124.7   9.713   1.641  5.92
25      1,189,589   +11.89%     25.000    12.500    119.8   9,407.6   9.596   1.705  5.63
50      1,092,224    +2.73%     49.9999   25.000    102.6   9,838.4   9.984   1.768  5.65
100     1,068,510    +0.50%     99.9975   49.999     98.1   9,716.9   9.817   1.630  6.02
200     1,063,936    +0.073%   199.796    99.898     97.3  10,378.4  10.260   1.645  6.24
500     1,063,200    +0.0039%  492.571   246.286     97.1   9,627.3   9.751   1.629  5.98
none    1,063,159     0.00%   5748.240  2874.120     97.1   9,636.3   9.754   1.618  6.03
```

`A` = verify over original geometry (default). `B` = verify over split
geometry. `sec` = median of 7 computation-seconds reps. `L/2` is IMPLIED for
B3, not measured: B1's index has no midpoint ordering, so inflation does not
exist in it yet.

### Verification decomposition and the split-mode result

```text
original mode, per property:  line candidates      155.3 checks    1.6%
                              polygon candidates  9,561.6 checks   98.4%
```

Split-geometry verification removes 30% of checks and runs 6.0x faster.
Decomposition at the 100 m cap: 1.43x fewer checks times 4.21x cheaper per
check equals the 6.02x wall-clock ratio. The per-check speedup is why: an
original-mode check is a full projection plus parity in `evaluate_ring`; a
split-mode check is parity only in `ring_contains_point`. Same counter name,
4x different work. Segment-check counts are therefore comparable within a
verification mode and not across modes — a constraint the B6 benchmark inherits.

```text
containment bbox pre-filter skip rate    57.6% to 59.3% countywide
of the 2,926.5 checks/property saved at cap 100:
    94.7% from the pre-filter, 5.3% from line-candidate elimination
```

### Agreement and the boundary-epsilon hazard (closed)

```text
all 14 points: all_fields_agree 267,362; 266 exact zeros, all waterbody;
0 nulls; distances in [0, 2630.235]; single distance_crs and algorithm
max abs error, original mode    4.657998431412125e-10 m   identical to B1
max abs error, split mode       8.82e-10 to 9.17e-10 m at caps 10-200;
                                exactly 4.658e-10 at caps 500 and none
minimum nonzero distance        0.002166405818047 m, at every point
```

The minimum nonzero distance is ~1.8 million times the 1e-9 m snapping band,
so the two verification modes cannot classify any property differently. The
on-boundary branch never fires countywide: all 266 exact zeros come from
ray-crossing parity over genuine interiors. Hazard closed with a measured
number.

### Chosen operating point: 25 m cap, original verification

Query cost is flat across the sweep (6.9% wall-clock spread over a 575x extent
range), so the cap is not chosen on B2 performance. It is chosen for the B3
inflated-disk radius `r + L/2`:

```text
cap    L/2      area inflation at r=325 m (county median)   at r=10 m
100 m  50.0 m              1.34x                               36.0x
 25 m  12.5 m              1.08x                                5.1x
 10 m   5.0 m              1.03x                                2.3x
```

25 m gives a 4x smaller inflation radius than B1's 100 m for +11.89% entries
and +22% index memory (98.1 to 119.8 MB). 10 m gives 2.5x more reduction for
another +41% entries and +32% memory; that array is also the B4 RMI training
array, so its size compounds downstream. The elbow is at 25. If B3's measured
inflation cost argues for 10 m, re-running the sweep is one command.

Original stays default because split raises max abs error from 4.658e-10 to
9.06e-10, forfeiting B1's byte-identical reproduction of the Python reference,
for a query speedup the frozen M2/M3 evidence does not need. Split is carried
forward as a validated flag and a first-class row in the B6 ladder.

### Where the remaining work now sits

Phase-1 search costs roughly 35 box and node operations per property. Phase-2
verification costs 9,716.87 segment checks, because the exact kernel rescans
each candidate feature's entire original geometry. Over 99 percent of remaining
work is verification, not search. B2 confirmed this quantitatively and showed
the verification cost is dominated by the polygon containment predicate (98.4%
of checks), roughly halvable by an exact bounding-box pre-filter but not
eliminable without a dedicated containment structure — a target for B3+.

## Milestone 4 chunk B3a (validated on fixture, committed at 97bfb1e)

`cpp/spatial_core/src/water_distance_hilbert.cpp` replaces the segment BVH's 2D
box hierarchy (phase 1 only) with a 1D Hilbert ordering of split-segment
midpoints and an exact inflated-disk range query. Phase 2 verification is
unchanged from B2: it reuses `distance_to_feature` (original mode, byte-identical)
or the split minimum plus `polygon_contains_point` (split mode), selected by the
same `VerificationMode` flag. The translation unit `#include`s
`water_distance_segment_bvh.cpp` and reuses its kernel, IO, tie rule, and
containment predicates.

Query mechanism: entry midpoints are Hilbert-ordered (order p = 32, per-axis
normalization, both recorded in the manifest); the nearest-neighbour query is
made exact by inflating the admission radius to `R = d_best + L/2 + tie_tol`
(the `tie_tol` term is required so the tie counter matches the reference);
candidate curve intervals are found by recursive quadrant decomposition with a
swappable region predicate. The aligned-square key range identity
`[min-over-4-corner-cells, +4^k)` is orientation-free and was verified
exhaustively for p=1..8 and against brute cell enumeration
(`tests/cpp/hilbert_probe.cpp`), so no curve-orientation state is carried.

The query records three admitted-entry counts per property —
`disk(r + tie_tol)`, `disk(r + L/2 + tie_tol)`, and the box decomposition —
yielding two stacked inflations (geometric L/2 and box-vs-disk indexing). The
box-primary (DiskBBox) region is the B3a operating predicate; the tighter Disk
region is present and validated but gated for B3b as a one-predicate swap.

### Validation (fixture cross-check, 2026-07-28)

```text
command   python tests/fixture_crosscheck.py --work-dir <tmp> \
            --bruteforce ... --indexed ... --segment-bvh ... --hilbert ...
toolchain g++ 13.3, -std=c++17 -O2 -Wall -Wextra; pandas 3.0.2
result    ALL CROSS-CHECKS PASSED

hilbert(original, disk_bbox)  max abs error 0.000e+00 m   0 field mismatches
hilbert(original, disk)       max abs error 0.000e+00 m   0 field mismatches
hilbert(split,    disk_bbox)  max abs error 8.215e-10 m   0 non-distance
                                                          mismatches (asserted
                                                          < 1e-6 m)
collision check   523 distinct cells == 523 entries at p=32; min order = 10
ordering          N_disk_r <= N_disk_infl <= N_decomp per property   holds
region monotone   disk scans <= disk_bbox scans per property         holds
interior-zero     p00000 interior, p00001 boundary, p00003 holed-outside-hole
                  all exactly 0.0 in BOTH original and split modes
hilbert_probe     PART1 PASS (aligned-square range identity, p=1..8)
                  PART2 PASS (decomposition == brute enumeration, 2000 boxes)
```

Bug found and fixed during validation: `1u << 32` was 32-bit undefined
behaviour, collapsing the normalization so every midpoint mapped to cell 0; the
index silently degenerated to brute force and still returned correct answers,
so field agreement did not expose it. The `distinct_cells == index_entries`
collision assertion caught it. Fixed with 64-bit shifts throughout.

Not done in B3a (scoped to B3b): no countywide run. Committed at 97bfb1e.

The B3a note that the geometric inflation ratio "aggregates to 0 on the sparse
fixture" was wrong in its attribution and is corrected in B3b below: the ratio
was 0 because its denominator is degenerate by construction, not because the
fixture is small.

## Milestone 4 chunk B3b (validated countywide 2026-07-28, committed at 97bfb1e)

B3b validated the exact Hilbert path at countywide scale, isolated the seed
seam that B5 replaces, corrected the inflation instrument before measuring with
it, and recorded the box-vs-disk gate decision. The B1/B2 sources are
byte-for-byte unchanged: `water_distance_bruteforce.cpp`,
`water_distance_segment_bvh.cpp`, `water_distance_indexed.cpp`.

### The seed seam

Implementations #4 and #5 are one binary differing only in how the start
position is found. Everything downstream — inflated-disk decomposition,
verification, tie rule — is shared code on the same path.

```text
--seed binary   default, the B3 control: lower_bound over the sorted keys,
                written out so cpp_seed_probes is measurable
--seed rmi      parses and errors, naming B4/B5 as the missing pieces; the
                switch surface is frozen now so B5 adds only a model loader
--seed zero     test mode: position 0 for every query, the worst legal hint
```

The seam is correctness-neutral, provably: `d_seed` is the minimum over a window
of REAL segments of an ACHIEVED point-to-segment distance, so `d_seed >= d_true`
for any window at any position, however that position was obtained. `R_seed`
therefore always covers the true answer, `d_best` is exact, and the final
candidate set is rebuilt by an independent descent that never references the
seed. A mispredicting model widens the first descent and slows the query; it
cannot change an emitted field.

This is tested rather than argued: `--seed zero` output is byte-identical to
`--seed binary` on every column except the seed instrumentation. That is B5's
acceptance criterion, exercised before the model exists.

`zero` rather than `null` because pandas parses a literal `null` CSV value as
NaN, which would have tripped the countywide no-nulls check. Caught by the new
test, not in production.

### The inflation denominator was degenerate and was replaced

B3a instrumented `n_disk_r` — midpoints in `disk(d_best + tie_tol)` — as the
uninflated disk. It is degenerate by construction: `d_best` is a distance to the
nearest POINT ON A SEGMENT while the counter tests MIDPOINTS, and
`|p - m_i| >= d(p, s_i) >= d_best` for every entry, so an entry is counted only
when its perpendicular foot lands within `tie_tol` of its own midpoint. A
coincidence counter, not a population.

Measured: nonzero on 0 of 1,093 fixture properties and on **193 of 267,362**
countywide (0.072%). Dividing by it would have reported the capped inflation as
**14,238x instead of 6.40x** — a number built entirely from 193 accidents. The
B3a stdout printed `0.000000` rather than failing because of a
`tot_ndr ? ... : 0.0` guard.

Replacement: `n_true_r = |{entries : d(p, s_i) <= d_best + tie_tol}|`, the
entries that genuinely satisfy the range predicate at the answer radius — what an
exact index would admit if its entries had zero extent. It is `>= 1` always and
exact from the tight descent alone, since any such entry has its midpoint in
`disk(R)` by the lemma. `n_disk_r` is retained and reported as degenerate rather
than deleted.

Provable per-property chain, asserted on every artifact:

```text
n_disk_r <= n_true_r <= n_disk_infl <= n_disk_unc
n_disk_infl <= n_decomp
```

### The uncapped counterfactual

`--uncapped-half <m>` re-counts midpoints in `disk(d_best + <m> + tie_tol)` on
the same midpoint set, through a counting-only descent that adds a block's entry
count in O(1) when the block's bounds lie inside the disk, so cost tracks the
circle's boundary rather than the enclosed population. The same routine is an
independent second implementation of `n_disk_r` and `n_disk_infl` under
`--verify-counts`.

This is a RADIUS counterfactual on a fixed point set, not a simulated unsplit
index: it holds geometry constant and varies only the admission radius. A
faithful unsplit rebuild would explode the candidate set and phase-2 cost by
orders of magnitude. The controlled comparison is the more informative one, and
the limitation is stated rather than elided.

### Schema additions

Counters only. No evidence field, kernel, tolerance, or tie rule changed.

```text
cpp_n_true_r, cpp_n_disk_unc, cpp_seed_probes, seed_mode
manifest: seed_mode, seed_window_entries, uncapped_inflation_half_m,
          count_cross_check
```

`CPP_REQUIRED_COLUMNS` in `water_validate.py` is a subset check, so
`compare_python_cpp_water.py` is unaffected.

### Countywide agreement (`outputs/validation/water_hilbert_summary_*.json`)

Reference `outputs/baseline/python_nearest_water_countywide.csv`, tolerance
1e-6 m unmodified.

```text
mode / region        union rows  all_fields_agree  max abs err (m)      exit
original, disk_bbox    267,362        267,362      4.657998431412125e-10   0
split,    disk_bbox    267,362        267,362      9.156906344287563e-10   0
original, disk         267,362        267,362      4.657998431412125e-10   0

missing_python_rows 0, missing_cpp_rows 0, coverage_rate 1.0 in all three.
feature_id_agreements 267,362 in all three, including split mode.
```

Original mode reproduces B1 and the Feature BVH exactly, and not only at the
maximum: mean 3.7314969885911784e-11 and median 3.410605131648481e-13 match B1's
countywide figures digit for digit. The Hilbert path therefore selected the same
feature and computed the same distance for every one of the 267,362 properties
while examining a different candidate set. The error distribution is identical,
not merely bounded by the same tolerance, because original-mode verification
recomputes distance over original geometry with the unchanged kernel and the
residual is pure Python/C++ floating point with no index contribution.

Split mode lands in the 8.8e-10 to 9.2e-10 band B2 measured at caps 10-200.

`disk` and `disk_bbox` agree bit-for-bit on max, mean, and median. With the
counter-side region invariance below, the two predicates are confirmed
equivalent from both the answer side and the admitted-set side.

### Artifact checks on the countywide output

```text
rows                        267,362
unique property_ids         267,362
nulls in required columns         0
empty feature names         208,340    unnamed 3DHP flowlines; identical to B1
exact-zero distances            266    all class = waterbody
distance range              0.0 to 2,630.23485692034 m
distance_crs                EPSG:26918   single value
algorithm                   hilbert      single value
region_mode / seed_mode     disk_bbox / binary   single values
verification_mode           original     single value
mean seed probes            20.237640352780126
max seed probes             21
```

The 266 exact zeros are the load-bearing check. Interior-zero rode on 2D box
overlap under B1; B3a re-proved it for 1D midpoint selection, and it survives
countywide, all on `waterbody` features. The empty-name count matching B1's
208,340 exactly is further evidence the two paths select identical features.

Seed probes: `log2(1,189,589) = 20.18` and `ceil(log2 N) = 21` is the
theoretical worst case for `lower_bound` on this array. Measured mean 20.2376,
measured max exactly 21 — the control attains its bound. That is the number B6
measures the RMI against.

### Index (`outputs/validation/water_hilbert_countywide_manifest.json`)

```text
index entries                    1,189,589   cap 25 m, matches B2's sweep
max split segment length L       24.999998220193326 m
inflation half L/2               12.499999110096663 m
Hilbert order                    32 bits/axis
normalization min_x / min_y      110,690.62769492628 / 4,718,978.519074164
normalization scale_x / scale_y  14,101.011597461484 / 23,725.593186389768 cells/m
key array bytes                  9,516,712
distinct cells at order 32       1,189,510 of 1,189,589   79 collisions
```

### Inflation cost (`outputs/validation/water_hilbert_inflation_summary.json`)

```text
                                      per property   aggregate ratio
entries satisfying the predicate         1.6067          —
  N_true_r
admitted, capped   (r + 12.5 m)         10.2783        6.397x
  N_disk_infl
admitted, uncapped (r + 2,874.12 m)  5,612.61       3,493.296x
  N_disk_unc
entries read by the decomposition       89.2325          —
  N_decomp

what the B1 split bought   N_disk_unc / N_disk_infl   546.063x
```

**This is the phase's answer to what exactness costs over extended objects.**
Capping segments at 25 m costs 11.89 percent more index entries (B2) and returns
a 546x reduction in admitted entries per query. Without the cap every one of the
267,362 queries would have had to admit 5,613 entries on average to remain exact,
against the 1.61 that actually satisfy the range predicate — a 3,493x geometric
inflation caused by one Lake Ontario boundary chord of 5,748.24 m. With the cap
it is 6.4x. B1a justified splitting by an entry-count argument; this is the
measurement that justifies it by its effect on query work.

Two internal consistency checks hold: `3493.296 / 6.397 = 546.1` as required,
and the counting descent's re-derivation of `n_disk_r` and `n_disk_infl` agreed
with the scan-derived counters on all 267,362 properties (`--verify-counts`).

Inflation by distance decile is a shallow arc — 5.18 nearest, peaking at 6.83 in
decile 7, 5.74 farthest — so no distance band is disproportionately penalized.

### Region invariance

```text
n_disk_r, n_true_r, n_disk_infl   identical, all 267,362 rows, both predicates
n_decomp under disk > under bbox  0 properties
```

### Box-vs-disk gate: ENABLE

Threshold declared before measurement: p99 of the per-property ratio, 3.0x.

```text
                    N_decomp / N_disk_infl
                    aggregate    p99      max
disk_bbox              8.682     181.0   1,015.0
disk                   4.630      44.0     170.0

phase-1 work reduction if enabled   1.875x   (89.23 -> 47.59 entries/property)
phase-2 segment checks              11,922.31 -> 11,021.83 per property, -7.55%
verdict                             enable_disk_predicate
```

The verdict is unambiguous — the aggregate alone clears 3x — but the p99 of 181
overstates the case and must not be quoted as the payoff. The decile table shows
the ratio climbing 3.58 to 27.56 from nearest to farthest decile while
`N_disk_infl` falls to 9.2: far-from-water properties have a large, nearly empty
disk, so the tail is driven by a small denominator rather than large absolute
waste. **The number to record is 1.875x phase-1 and 7.55% phase-2.**

The phase-2 saving is larger in absolute terms, since B2 established that over 99
percent of remaining work is verification. It arises because the box predicate
admits more entries, which admits more candidate features, each triggering a full
`distance_to_feature` rescan.

Decision: `disk` becomes the default region predicate for B4 onward. It is
answer-identical (verified bit-for-bit), cheaper on both phases, and already
implemented and validated — one line in the `region_kind` default. B6 must run
the whole ladder under one predicate; mixing them would confound the 4-vs-3
comparison.

### Phase-2 cost of the 1D reduction (a B6 preview, counters not timings)

```text
                                 segment checks / property
segment BVH (B1, original)              9,716.87
hilbert disk_bbox (original)           11,922.31    +22.7%
hilbert disk (original)                11,021.83    +13.4%
hilbert disk_bbox (split)               7,952.52    -33.3% vs original
```

The Hilbert query admits a coarser candidate feature set than the segment BVH's
best-first traversal, so leaving the tree costs roughly 23 percent more phase-2
work at the B3b operating predicate, or 13 percent with the disk predicate
enabled. This is the 4-vs-3 comparison appearing before B6 runs it, and it is a
partially negative result for dimensionality reduction. Stated in advance of the
benchmark, per Nucleus 18.18. Wall-clock claims remain B6's; these are counters,
and the runs that produced them carried `--verify-counts` and `--uncapped-half`,
so their timings are not benchmark-eligible.

### Where the RMI can and cannot help

Phase-1 admission is now a rounding error in the query's total work: about 20
seed probes and 89 entry distance computations against 11,922 phase-2 segment
checks per property. The B5 RMI replaces **only** the ~20 probes. Even a perfect
position predictor therefore cannot produce a large end-to-end speedup on this
workload, in either verification mode.

The RMI's quality must accordingly be judged on search-side metrics —
predicted-position error, search-window size, key throughput — and B6 must
report the end-to-end result honestly against this ceiling rather than against
an expectation the data cannot support.

One framing correction for B4: the classic learned-index size claim is "a model
replaces a structure," measured against a B-tree's internal nodes. **There is no
B-tree here.** Binary search over a sorted array needs no auxiliary structure, so
against rung 4 the RMI only ADDS bytes. The defensible size comparison is rung 5
against rung 3 — the segment BVH's 119.8 MB index (B2, cap 25) versus the
Hilbert sorted array plus a small model. Only the key array is currently
measured, at 9,516,712 bytes; a full memory comparison of both paths has not been
taken and is a B6 column.

### Files, B3b

```text
modified  cpp/spatial_core/src/water_distance_hilbert.cpp
modified  tests/fixture_crosscheck.py
added     python/caprm/hilbert_inflation.py
added     python/scripts/summarize_hilbert_inflation.py
added     tests/test_hilbert_inflation.py
added     outputs/validation/water_hilbert_countywide_manifest.json
added     outputs/validation/water_hilbert_inflation_summary.json
added     outputs/validation/water_hilbert_summary_{original,split,disk}.json
added     outputs/analysis/water_hilbert_inflation_by_decile.csv
```

The three countywide Hilbert CSVs and the two ad-hoc check scripts under
`outputs/validation/` are generated and not committed, matching the `outputs/`
ignore rule. The summary JSONs carry the input SHA-256s.

### Validation performed

```text
g++ -std=c++17 -O2 -static -Wall -Wextra    builds clean, no warnings
tests/fixture_crosscheck.py                 ALL CROSS-CHECKS PASSED
tests/test_hilbert_inflation.py             13 passed
python -m pytest -q --ignore=tests/test_spatial_split.py   210 passed (+13)
compare_python_cpp_water.py x3              exit 0, 267,362/267,362 each
summarize_hilbert_inflation.py              exit 0, ordering and invariance hold
determinism                                 two runs byte-identical
```

The fixture cross-check produced identical figures on Windows/MSYS2 UCRT64 and
Linux/g++ 13.3 (8.215e-10 m split-mode error, 523/523 distinct cells, probes
<= 10, zero-seed identity), so B3b is deterministic across compiler and platform
as B1 and B2 were.

### Recorded, not blocking

- The fixture's `distinct_cells == index_entries` assertion is fixture-scoped.
  Countywide there are **79 collisions** in 1,189,589 entries (99.993 percent
  distinct) — coincident midpoints from shared or duplicated geometry, benign
  under the Roadmap's "Note on lossiness" and covered by the seed window. It is
  nothing like the `1u << 32` degeneration B3a caught, which put every midpoint
  in cell 0. Do not lift that strict assertion to countywide scale; it needs to
  be a rate bound there.
- `min_order_for_distinct_cells` reports 32 countywide, which is a sentinel and
  not a measurement: the search loop leaves the value at `order` when no
  resolution achieves full distinctness. It should report "not achieved".
  Cosmetic.
- The normalization extent is 304.6 km in x and 181.0 km in y, far larger than
  Monroe County, because the Lake Ontario polygon spans the whole lake.
  Resolution is not harmed (0.07 mm cells), but B4 should know its training keys
  are spread over a domain several times the county's extent before fitting a
  CDF to them.

## Milestone 4 chunk B4 (validated countywide 2026-07-28, committed at 97bfb1e)

B4 trained the recursive model index, enabled the `disk` region predicate
recorded in the B3b gate decision, and added a key export so the training array
is the index's own array rather than a reconstruction of it.

### The `disk` default, and why it is now tested

`region_kind` defaults to `Region::Kind::Disk`. Every existing
`fixture_crosscheck.py` call passed `region_mode` positionally, so the default
had no coverage at all. `run_hilbert` now stops at the first omitted positional,
and one call omits `region_mode` entirely and asserts the emitted `region_mode`
column is `disk`. A changed default is now catchable.

### `--dump-keys`, and why a Python reconstruction was rejected

The RMI trains on the sorted 64-bit key array, which existed only in C++ memory.
The alternative — rebuilding the split, the normalization and the Hilbert
transform in Python — was rejected on three grounds:

```text
provenance     Nucleus 18.10 and 18.20 require a manifest to reproduce the
               result it describes and hold a model to CSV standards. A
               training-array SHA-256 whose correspondence to the index rests
               on a floating-point argument satisfies neither.
detectability  the C++ split computes piece * (1.0/pieces); the existing Python
               splitter computes piece/pieces. These are not bit-identical in
               general. At a 0.07 mm cell the expected number of differing keys
               over 1,189,589 entries is order 1 — and you cannot tell which
               case you are in without the C++ array, which is the thing being
               reconstructed.
duplication    a Python twin of the splitter is a permanent hazard: any future
               change to the C++ splitter silently invalidates it and nothing
               fails loudly.
```

`--dump-keys <path>` writes the sorted array as raw little-endian uint64 and
prints its byte and entry counts. It is off the query path, costs nothing unless
requested, and is an export of an artifact already in memory — not a migration
of functionality into C++.

### Countywide index run (the key dump, and a clean timing)

`disk` predicate, `original` verification, no `--verify-counts`, no
`--uncapped-half`.

```text
seed probes / property             20.237640      matches B3b exactly
N_true_r / property                 1.606679      matches B3b exactly
N_disk_infl / property             10.278319      matches B3b exactly
N_decomp / property                47.592623      matches B3b disk exactly
capped inflation                    6.397244      matches B3b exactly
box-vs-disk inflation (disk)        4.630390      matches B3b exactly
phase-2 segment checks / property  11,021.825858  matches B3b disk exactly
degenerate N_disk_r                193 of 267,362 matches B3b exactly
range nodes visited / property     60.319907
ranges emitted / property           5.610842
```

Nine independent counters reproduce B3b's disk-predicate run digit for digit, so
the `--dump-keys` patch and the default change are behaviour-neutral at
countywide scale, not only on the fixture.

```text
query wall clock       20.227759 s for 267,362 properties
throughput             13,217.579134 properties/sec
```

This is the first benchmark-eligible wall-clock figure for the Hilbert path —
every earlier one carried counter instrumentation. It is ONE run with no warm-up
or repetition protocol, so it is recorded as an observation and is not a B6
result. B6 owns the ladder timings.

### The training array

```text
outputs/cpp_input/water_hilbert_keys_countywide.bin
sha256      9f118bfc923dbf1a062a13fb7c0a662901ab8fdebbb3fd7ed7e93a497aad02f0
entries     1,189,589        matches the B3b manifest
bytes       9,516,712        matches the B3b manifest
distinct    1,189,510        matches the B3b manifest
duplicates  79               longest run 2, so all 79 are simple pairs
convention  lower_bound_first_of_run
```

The trainer refuses to run unless `index_entries`, `key_array_bytes` and
`distinct_cells_at_order` all match the index manifest, so a stale or mismatched
dump fails before any model is fitted.

### Architecture and the float contract

Two-stage RMI after Kraska et al., SIGMOD 2018. Linear at both stages, numpy
least squares, no framework. Inference is four multiply-adds, two clamps and two
floors:

```text
xd  = (double) key
x   = (xd - key_min_d) * inv_span
j   = clamp(floor(root_a + root_b*x), 0, n_leaves-1)
p   = clamp(leaf_a[j] + leaf_b[j]*x, 0.0, n_keys-1.0)
pos = (size_t) floor(p)
```

Leaves are fitted on centred `x` (a leaf spans ~1e-5 of [0,1]; the uncentred
normal equations lose most of their digits there) and stored in `a + b*x` form,
which is safe to evaluate because the two large terms cancel to well under one
array slot.

`key_min` and `key_max` are stored as raw uint64 rather than as decimal doubles,
so C++ derives its constants from integers and no decimal round-trip can drift.

**Recorded as an assumption, not a proof:** numpy guarantees
round-to-nearest-even for `uint64 -> float64`; C++ does not. [conv.fpint]
permits either adjacent representable value. x86-64/SSE2 rounds to nearest under
the default MXCSR mode, which is the target every measurement here was taken on.
The manifest carries probe keys with their normalized `x` as hex bit patterns
and their predicted positions so B5 can assert this at model load rather than
inherit it.

### The sweep

Selection rule declared before training (Nucleus 18.12): lowest mean last-mile
probes among leaf counts within a size cap of half the 9,516,712-byte key array
(4,758,356 bytes); target <= 10.0 probes, half the control.

```text
leaves   occupied  max load  max err  mean|err|  probes    <=64      bytes
   256        104    54,347   13,547    1165.29  12.625    5.81%      8,288
 1,024        294    32,675    4,448     377.47  11.054   18.13%     32,864
 4,096        819    24,076    4,831     189.73   9.664   39.73%    131,168
16,384      2,452    10,873    2,744      79.24   8.319   72.88%    524,384
65,536      7,441     5,363    2,543      28.61   6.962   90.90%  2,097,248
131,072    12,449     3,409    1,650      19.01   6.323   94.24%  4,194,400

equi-depth reference (perfect router, same leaf models — NOT shippable)
   256                            5,290            10.734
 1,024                            1,017             9.017
 4,096                              534             7.365
16,384                               71             5.654
65,536                                9             3.822
131,072                               4             2.967
```

Selected: **131,072 second-stage models, `target_met`**. 262,144 would be
8,388,704 bytes and was excluded by the cap.

Global max error is NOT monotone in leaf count (4,448 at 1,024 against 4,831 at
4,096): a larger leaf count can place a boundary that gives some leaf a worse
extrapolation. The probe metric, which weights per-leaf windows by keys, is
monotone.

### The result: the router binds, not the leaves

At 131,072 leaves a perfect router leaves a maximum error of **4 positions**
across 131,072 linear models. The fitted model's maximum error is **1,650** — a
factor of 412. In probe terms the root costs **3.356 of the 6.323 probes, 53
percent of the last mile**.

One line per leaf models the local CDF of this Hilbert key distribution to
within a handful of positions. One line for the whole distribution cannot route
to those leaves.

Leaf occupancy grows by roughly 2.8x to 3.0x per 4x in leaf count through
65,536, then only 1.67x at 131,072 — saturation begins at the top of the sweep,
later and less sharply than a synthetic clustered array predicted during
authoring. Occupancy fraction falls throughout: 40.6 percent at 256 to 9.50
percent at 131,072.

### Against the control, and against the ceiling

```text
mean last-mile probes      6.323   vs control 20.237640   3.20x
probes saved / query      13.91
model bytes            4,194,400   44.07% of the key array it augments
within the +/-64 seed window       94.240% of index keys
```

The ceiling B3b recorded before B4 trained anything holds. Per property the
query performs 20.24 seed probes, 47.59 entry reads and 11,021.83 phase-2
segment checks, so 13.91 saved probes is **about 0.13 percent of counted query
work** — and it costs 44 percent more memory than the sorted array it sits
beside. This is a confirmed prediction, not a retrofit.

**The model is not the win. B1's rebuild at segment granularity is** (70,771 ->
9,716.87 segment checks per property, 7.28x) **and B1a's distance-exact split
is** (546x fewer admitted entries for 11.89 percent more index entries). Both
are classical. Leaving the tree for a 1D order cost 13.4 percent in phase-2
work; learning recovered about 0.13 percent of it.

### The domain bound: measured, non-monotone, and not usable as a window

The acceptance bound covers index keys. B5 queries with property-point keys,
which are not index keys, so a second bound was measured over the whole 64-bit
key domain — as an ADDITIONAL recorded quantity, leaving the acceptance
criterion unchanged.

It is measured rather than derived. The candidate set is every stored value and
its two neighbours, every leaf boundary and its predecessor, and both ends of
the domain; leaf boundaries are found by binary search over the key domain, not
by inverting the root algebraically. The argument that this set suffices —
`rank` changes only at stored keys, the leaf changes only at boundaries, and
between breakpoints the prediction is a floor of a clamp of an affine function
of a monotone `x`, so extremes fall at interval endpoints — is stated in
`domain_candidate_keys` and then re-tested against 2,000,000 uniformly random
keys.

```text
leaves     domain max error per model
   256         362,341
 1,024         135,845
 4,096         105,358
16,384          36,376
65,536          30,797
131,072         69,543          <- selected; WORSE than 65,536

leaves reachable by any key    109,134 of 131,072
unreachable                     21,938
random-key spot check       2,000,000 keys, 0 violations
```

The bound gets worse from 65,536 to 131,072. Cause: occupied leaves whose routed
key range extends far past their training keys, where the fitted line is
extrapolating. A window sized from 69,543 costs about 18 probes — barely better
than the 20.24 control. **The domain bound as it stands is a diagnostic, not a
usable window.**

Recorded mitigation, NOT implemented: clamping each occupied leaf's prediction to
that leaf's own observed target range would collapse the domain bound to roughly
the leaf's span, provably — for a query key inside leaf `j` but outside its
training keys, no stored key lies between, so the true rank equals the rank at
the nearest training key, which is inside the leaf's observed range. Cost is one
extra clamp and two more values per leaf. It is a model change, not a bound
change, and is deferred pending a decision.

### Neither bound gates correctness

Nucleus 18.22. The seed seam is correctness-neutral, proved and tested with
`--seed zero`, and the current query path uses a fixed +/-64 window with no bound
at all. The stored-key bound is the academic deliverable — model plus proven
bound is what makes this an index in Kraska's sense rather than a heuristic. The
domain bound is an informative window sizer. B5 should not build machinery as
though either gates anything.

### Model artifact

```text
models/water_hilbert_rmi.bin
sha256   9be3263cd40e8f7edbac762834879f45c769b6f1b1cb26c202c0c1bc3c4ef844
bytes    4,194,400   = 96-byte header + 32 bytes x 131,072 leaves
header   magic, format version, leaf stride, n_keys, n_leaves,
         key_min, key_max, root_a, root_b, training-array sha256
leaf     a, b (float64); err_min, err_max, gap_err_min, gap_err_max (int32)
```

The header carries the training-array SHA-256 so B5 asserts at load that the
model matches the array it is indexing.

`random_seed` is recorded as 0 with `training_is_deterministic: true`. Least
squares consults no RNG; the field exists for contract compliance and so a future
stochastic variant is reproducible. Determinism is instead checked by refitting
from scratch and requiring byte-identical output — which passed.

### Files, B4

```text
modified  cpp/spatial_core/src/water_distance_hilbert.cpp   (disk default;
          --dump-keys)
modified  tests/fixture_crosscheck.py   (optional trailing positionals;
          default-predicate check; key-dump check; numpy import)
added     python/caprm/rmi.py
added     python/scripts/train_hilbert_rmi.py
added     tests/test_rmi.py
added     models/water_hilbert_rmi.bin
added     outputs/validation/water_hilbert_rmi_manifest.json
added     outputs/validation/water_hilbert_countywide_manifest_b4.json
```

Generated and not committed, matching the `outputs/` ignore rule:
`outputs/cpp_input/water_hilbert_keys_countywide.bin` (9,516,712 bytes) and
`outputs/cpp/cpp_nearest_water_hilbert_countywide_b4.csv`.

`models/` is a new tracked directory: `outputs/` is ignored and B5 must load the
model, so the artifact cannot live under `outputs/`. **RESOLVED 2026-07-28
(B5):** `git check-ignore -v models/water_hilbert_rmi.bin` prints nothing, so no
ignore rule matches, no `-f` was needed, and section 4's
tracked-despite-ignore list needs no entry.

The B4 run wrote to new output and manifest paths rather than overwriting
`cpp_nearest_water_hilbert_countywide_disk.csv` (`8ad41e83...`) and
`water_hilbert_countywide_manifest.json` (`3711101d...`), whose SHA-256s are
recorded as inputs in `water_hilbert_inflation_summary.json`. B3b's artifacts are
byte-intact and the B4 model pins to
`water_hilbert_countywide_manifest_b4.json`
(`4c9518e526ae84f6ccbfdc4efbec020787546de608757c445d9c2aeebd587370`), which
describes the build it was actually trained against.

`requirements.txt` needs no change (numpy 2.4.6, pandas 3.0.3 already pinned; no
new dependency).

### Validation performed

```text
g++ -std=c++17 -O2 -Wall -Wextra          builds clean, no warnings (Linux 13.3)
tests/fixture_crosscheck.py               ALL CROSS-CHECKS PASSED
  new: default region predicate is `disk`
  new: key dump 523 entries, 523 distinct, sorted, 4184 bytes == manifest
python -m pytest tests/test_rmi.py -q     47 passed in 0.39s
python -m pytest -q --ignore=tests/test_spatial_split.py
                                          257 passed in 3.64s  (+47 over B3b)
exhaustive bound, all 1,189,589 keys      holds, asymmetric and symmetric, at
                                          every swept leaf count and on the
                                          artifact reloaded from disk
domain bound, 2,000,000 random keys       0 violations
determinism                               refit byte-identical
```

The fixture cross-check produced identical figures on Windows/venv and
Linux/g++ 13.3 (8.215e-10 m split-mode error, 523/523 distinct cells, probes
<= 10, zero-seed identity, 4.810086 capped inflation, 8.987174 box-vs-disk), so
B4 is deterministic across compiler and platform as B1-B3b were.

**CLOSED 2026-07-28 by a digest chain (B5), not by rerunning the harness.**
`compare_python_cpp_water.py` was never run against
`cpp_nearest_water_hilbert_countywide_b4.csv` directly. It does not need to be:

```text
water_hilbert_summary_disk.json   validated cpp_nearest_water_hilbert_countywide_disk.csv
                                  267,362/267,362 all_fields_agree, max abs err 4.658e-10
that file's sha256                8ad41e8391f64e683e67ac253dc4d1e4302da7706f893763d0d32a689d6b7e9e
                                  (recorded as an input digest in
                                  water_hilbert_inflation_summary.json, re-measured at B5)
b4 output sha256                  8ad41e83...7e9e   identical
b5 binary output sha256           8ad41e83...7e9e   identical
b5 rmi output                     identical to b5 binary on 27 of 29 columns,
                                  i.e. every column the harness compares
```

Agreement of the B4 and B5 outputs with the Python reference therefore follows
by transitivity of byte identity, which is a stronger statement than a rerun
would produce. The one assumption is that `water_hilbert_summary_disk.json`
describes the file now digesting to `8ad41e83…`, which the inflation summary's
recorded input digests establish.

### Recorded, not blocking

- The selection is cap-bound, not converged. Probes were still falling
  (6.962 -> 6.323) when the 4,758,356-byte budget ended the sweep. Where the
  curve flattens is unknown. Raising the cap to find out means moving a declared
  threshold after seeing results — a deliberate decision, not a quiet edit.
- On bytes per probe saved, 16,384 leaves reads better: 524,384 bytes (5.51
  percent of the key array) for 8.319 probes, 2.43x against the control. The
  declared rule stands and selected 131,072; this is the honest alternative
  reading if B6 weights memory.
- 94.240 percent within the +/-64 window is measured on INDEX keys. B5 queries
  with property-point keys; the operational hit rate is unmeasured and is a B5
  measurement.
- A full memory comparison of the Hilbert path against the segment BVH's
  119.8 MB has still not been taken. Only the key array (9,516,712 bytes) and now
  the model (4,194,400 bytes) are measured. Both paths also carry the ~1.19M
  segment array. This remains a B6 column.

## Files, B1 (committed at 998c859)

```text
cpp/spatial_core/src/water_distance_segment_bvh.cpp
python/scripts/split_water_segments.py
tests/cpp/test_water_segment_bvh.cpp
tests/test_water_segment_split.py
tests/fixture_crosscheck.py
outputs/validation/water_segment_split_countywide_manifest.json
outputs/validation/water_segment_bvh_summary.json
outputs/validation/water_segment_bvh_agreement.csv
```

## Files, B2 (committed at 97bfb1e)

```text
modified  cpp/spatial_core/src/water_distance_segment_bvh.cpp   (verify-mode fork)
modified  python/caprm/water_benchmark.py                       (segment_bvh support)
modified  tests/cpp/test_water_segment_bvh.cpp                  (query() signature)
modified  tests/test_water_benchmark.py
added     python/scripts/sweep_segment_bvh_cap.py
added     python/scripts/plot_segment_bvh_cap_sweep.py
added     tests/cpp/test_water_segment_bvh_verify_modes.cpp
```

Modified for this chunk: this document, `CAPRM_Flood_Roadmap.md`,
`CAPRM_Flood_Project_Nucleus_2026-07-15.md`. `requirements.txt` needs no change
(matplotlib==3.11.0, rasterio==1.5.0 already pinned; scipy held for Phase C).

Generated and intentionally not committed (matches the `outputs/` ignore rule):
the 14 sweep output CSVs under `outputs/cpp/segment_bvh_cap_sweep/`, the runs
CSV, and the figure. The small sweep summary at
`outputs/validation/water_segment_bvh_cap_sweep_summary.json` carries the
provenance (input SHA-256s and the frozen-summary checksum).

## Validation performed

```text
g++ -std=c++17 -O2 -static -Wall -Wextra          builds clean, no warnings
tests/cpp/test_water_segment_bvh.exe              80021 checks, 0 failures
python tests/test_water_segment_split.py          5/5 passed
python tests/fixture_crosscheck.py                0 field mismatches, 0.0 m error
python -m pytest -q --ignore=tests/test_spatial_split.py    197 passed
python/scripts/compare_python_cpp_water.py        exit 0, all fields agree
```

B2 validation, 2026-07-23:

```text
g++ ... water_distance_segment_bvh.cpp                builds clean, no warnings
tests/cpp/test_water_segment_bvh.exe                  80021 checks, 0 failures
tests/cpp/test_water_segment_bvh_verify_modes.exe       607 checks, 0 failures
python -m pytest -q --ignore=tests/test_spatial_split.py    197 passed (+11)
python/scripts/sweep_segment_bvh_cap.py               accepted, 14/14 points
    all_fields_agree 267,362 at every (cap, mode)
```

The C++ unit suites were run on both Linux/g++ 13.3 and Windows/MSYS2 UCRT64
and produced identical counters, so the implementation is deterministic across
compiler and platform.

## Next task — B6, benchmark the five-implementation ladder

B1 through B5c are complete and validated countywide. The ladder is built, every
rung claiming exactness produces byte-identical evidence, and the learned rung's
cost is now attributable to a counted quantity rather than to wall clock alone.

B6 measures. It builds nothing.

```text
report as     three ADJACENT comparisons: 3 vs 2 granularity, 4 vs 3
              dimensionality reduction, 5 vs 4 machine learning.
              Never one global 5 vs 3 -- that confounds the last two.
protocol      a stated repetition and warm-up protocol with dispersion
              reported. B5c measured 3.85 percent spread between two runs of
              the SAME configuration, which is the order of the effects being
              claimed. No wall-clock assertion survives n=1.
scaling       the water workload ladder (_10000, _100000, _countywide) is
              already exported with identical schemas. Learned indexes are
              usually argued to win AS N GROWS; a three-point curve per rung is
              a far stronger answer to "when does learning help" than one point.
window        sweep SEED_WINDOW over {8,16,32,64,128,256,512} for BOTH seeders,
              upward as well as downward. Binary misses the +/-64 window on
              38.62 percent of queries, so this is a query-design parameter, not
              an RMI tuning knob. Compare only at matched window size.
memory        peak RSS per rung, measured not reasoned. There is no B-tree here,
              so against rung 4 the model only ADDS bytes; the defensible size
              comparison is rung 5 against rung 3.
eligibility   no run carrying --verify-counts, --uncapped-half or
              --seed-error-stats is benchmark-eligible. --query-stats IS free
              and eligible.
```

The headline is already known and must be reported: the learned rung produces
identical evidence and is slower, at an exchange rate of about 10 extra distance
computations per key probe saved. Nucleus 18.18 and section 14b both committed
the project to reporting whichever way it fell.

Deferred, unchanged since B4: whether to clamp each occupied leaf's prediction to
that leaf's observed target range. B5c strengthens the case — the cost of a miss
is quadratic and the RMI's tail reaches 517x the true radius against binary's
32x, so collapsing the tail is worth more than improving the mean. It remains a
model change that moves the artifact layout and its SHA-256, so it stays a
deliberate decision rather than a B6 edit.

## Milestone 4 chunk B5 (validated countywide 2026-07-28, committed at f2e2e00)

`--seed rmi` stopped erroring and became a model loader plus inference. One
function changed. The exact distance kernel, the 1e-6 m tie tolerance,
lexicographic tie-breaking on `water_feature_id`, the region predicate and every
emitted field are untouched.

### Acceptance — met

```text
rmi vs binary, countywide     267,362 rows, identical on 27 of 29 columns
                              (all but cpp_seed_probes and seed_mode),
                              compared as text with dtype=str, no float reparse
b5 binary vs b4 output        sha256 8ad41e8391f64e683e67ac253dc4d1e4302da7706f893763d0d32a689d6b7e9e
                              identical, and three-way with B3b's disk-mode file
binary seed-error self-test   267,362 / 267,362 exact zero, max |err| = 0
ten countywide counters       reproduce B3b/B4 digit for digit
```

The self-test matters more than it looks: under `--seed binary` the predicted
position IS `lower_bound`, so the measured error must be identically zero. It is.
The harness was therefore validated on a known answer before its rmi figures
were believed.

### The float contract is checked, not inherited

C++ does not verify the training-array SHA-256; see Nucleus 18.20 for the
recorded weakening and why it was accepted. It verifies at load: magic, format
version, leaf stride, file size, `n_keys` against the built index,
`key_min`/`key_max` against the index's first and last key, an unconditional
round-to-nearest-even self-check on `(double)(2^53+3)`, and five probe records
transcribed from the model manifest — each asserting `index.keys[i] == key` and
then reproducing `x` bit-for-bit, the routed leaf and the predicted position.

Probe records are REQUIRED with `--seed rmi`; the program fails closed rather
than running unchecked. Seven misconfigurations are asserted to fail in the
fixture: missing probes, missing model, `--rmi-model` under a non-rmi seed, a
tampered probe position, a probe key that does not match `index.keys[i]`, a
corrupted magic, and a truncated file.

### The measurement B4 could not take

```text
                          index keys (B4)   property keys (B5)
within +/-64                    94.240%            86.630%
outside the window                  n/a    35,745 of 267,362
exact zero                          n/a    99,453  (37.20%)
mean |error|                      19.01             55.77
p50 / p90 / p99 / p99.9      9/39/191/373    5/100/731/5,389
max |error|                    1,650            17,995
signed mean                         n/a             -9.09
```

B4 flagged that the index-key figure would not carry over. It does not, and the
shape of the gap is specific: the model is SHARPER at the centre (median 5
against 9, 37 percent exact) and an order of magnitude worse in the tail. That
is extrapolation outside a leaf's training keys — the same mechanism behind the
non-monotone domain bound B4 measured.

### Wall clock: the model made the query slower

```text
B4 clean binary,      no flags      20.227759 s    13,217.58 properties/s
B5 run 1  binary + seed-error       20.644707 s    12,950.63 properties/s
B5 run 2  rmi    + seed-error       21.439414 s    12,470.58 properties/s   +3.85%
```

An advance prediction that the rmi run would land near 20.23 s — implying a ~2
percent time share for the seam — was made before run 2 and was WRONG by 1.21 s.
Recorded as a wrong prediction rather than dropped.

Accounting, all three single unrepeated runs with no warm-up protocol:

```text
cost of one extra lower_bound   0.416948 s = 1.559 us/property   (run 1 - B4;
                                the only difference is --seed-error-stats)
if seeding costs the same, the seam SAVED about   0.417 s
observed change                                  +0.795 s
unexplained cost elsewhere                  about 1.212 s
                                = 4.53 us/property, or <= 33.9 us per property
                                  that missed the +/-64 window
```

This is inference, not measurement. It assumes the seeding binary search costs
what the reference `lower_bound` costs and that model inference is negligible.
The mechanism is the resolve descent widening on a mispredicted seed (Nucleus
18.22), and it is UNCOUNTED, which is what B5c exists to fix.

**B5's honest headline:** the RMI wins the search it replaces — zero key
comparisons against 20.2376 probes — and appears to lose more than it wins on
the descent that search was feeding, because the seam's value here is the
quality of the `d_seed` it produces rather than the lookup cost it saves.

### Files, B5

```text
modified  cpp/spatial_core/src/water_distance_hilbert.cpp   (+576 lines,
          18 hunks: RmiModel, rmi_predict, loader, probe binding, seed-error
          report, three new options)
modified  tests/fixture_crosscheck.py   (fixture-scale model trained through the
          real trainer CLI; rmi seam assertion; 7 negative cases)
added     outputs/validation/water_hilbert_seed_error_b5_{binary,rmi}.json
added     outputs/cpp/cpp_nearest_water_hilbert_countywide_b5_{binary,rmi}.csv
added     outputs/validation/water_hilbert_countywide_manifest_b5_{binary,rmi}.json
```

`compare_python_cpp_water.py` and `water_validate.py` need no change:
`CPP_REQUIRED_COLUMNS` is a subset check and B5 added no CSV column. Adding a
per-property seed column was rejected precisely because it would break the
byte-identity test that is the acceptance criterion.

`requirements.txt` needs no change; no new dependency.

New CLI surface:

```text
--rmi-model <path>       the B4 artifact
--rmi-probes <records>   REQUIRED with --seed rmi; semicolon-separated
                         'index,key,x_hex,leaf,position' from the model manifest
--seed-error-stats <p>   predicted-vs-actual seed error over the property keys,
                         own JSON, works under every seed mode. A run carrying
                         it is NOT benchmark-eligible.
```

Build flag added to the documented command: `-ffp-contract=off`. It changes
nothing on baseline SSE2, but a `-march=native` build on Haswell or later could
contract `a + b*x` into an FMA and shift `x`. The probe records catch that at
load; the flag prevents it.

### Validation performed

```text
g++ -std=c++17 -O2 -ffp-contract=off -Wall -Wextra   builds clean, no warnings
                                                     (Linux g++ 13.3 and
                                                     Windows MSYS2 UCRT64)
tests/fixture_crosscheck.py            ALL CROSS-CHECKS PASSED, both platforms
  new: rmi seam byte-identical to binary
  new: binary seed-error self-test 1093/1093 exact
  new: 7 negative cases all refuse
python -m pytest -q --ignore=tests/test_spatial_split.py   257 passed (x2)
countywide acceptance                  267,362 rows, 27/29 columns identical
countywide digest chain                b5 binary == b4 == B3b disk file
```

### Outstanding before commit

```text
determinism      the countywide rmi rerun has NOT been run. Every prior chunk
                 asserted two runs byte-identical; B5 has not yet.
```

### Recorded, not blocking

- The exact countywide C++ input paths are recorded in NO canonical document and
  in no script default. Only `water_vertices_countywide.csv` and the key dump
  appear anywhere. Every countywide run's inputs currently live in shell
  history, which section 8 of the working standard forbids. Record the three
  paths here once they are read off `outputs/cpp_input/`.
- The `--rmi-probes` string must be derived from the model manifest at run time,
  not transcribed by hand. B6's harness needs it programmatically in any case:
  `python -c "import json; r=json.load(open('outputs/validation/water_hilbert_rmi_manifest.json'))['probe_records']; print(';'.join(f\"{p['index']},{p['key']},{p['x_hex']},{p['leaf']},{p['predicted_position']}\" for p in r))"`
- `--seed zero` and `--seed rmi` now both report `cpp_seed_probes = 0`, so the
  column no longer distinguishes them on its own. `seed_mode` does.

---

## Milestone 4 chunk B5c (validated countywide 2026-07-28, commit pending)

B5 measured the learned rung slower than its control and could not say why in
any counted quantity. B5c makes the difference countable. Nothing else changed:
no kernel, tolerance, tie rule, region predicate, or emitted field.

### Why it was invisible

The Hilbert query runs two descents. Resolve at
`R_seed = d_seed + L/2 + tie_tol` obtains `d_best`; tight at
`R = d_best + L/2 + tie_tol` builds the final candidate set. Every emitted
counter comes from the tight descent, which is seed-invariant by construction —
that is exactly why `--seed zero` and `--seed rmi` produce byte-identical
evidence. The resolve descent is the only thing a seed position affects, and its
`ScanContext` was accumulating `nodes_visited` and `entries_scanned` and then
discarding them when it went out of scope.

B5c copies them out. The change is additive and free.

### The counted result

```text
                              binary        rmi        ratio
resolve entries / property   141.1742   352.5154      2.497x
resolve nodes / property      70.9135    83.1684      1.173x
window missed                103,242    123,011      38.62% -> 46.01%
mean d_seed / d_best          1.1717     1.5388
max  d_seed / d_best         32.2332   517.3435
tight entries / property      47.5926    47.5926      identical
tight nodes / property        60.3199    60.3199      identical
phase-2 segment checks     11,021.8259 11,021.8259   identical
query seconds                19.4774    20.6303      +5.92%
```

**The exchange rate is the finding.** The RMI saves 20.2376 key probes per
property and spends 211.34 extra point-to-segment distance computations to do
it — 10.44 to 1 in the wrong direction. B5's hypothesis is confirmed by counters
that are deterministic and reproduce exactly across compiler and platform, not by
wall clock alone.

Convexity, not miss frequency, is the mechanism. Cost grows as `R_seed^2`, so it
is convex in `d_seed / d_best`. The mean ratio moving 1.1717 -> 1.5388 predicts
about 1.72x more entries under uniform density; measured is 2.497x. The excess is
Jensen plus the tail: the maximum ratio moves 32.2 -> 517.3 while the miss RATE
moves only 1.19x. The model misses slightly more often and much harder.

Arithmetic against the clock: 1.1529 s over 56,504,623 extra resolve entries is
**20.40 ns per entry**, the right order for a midpoint read plus a distance
computation with cache misses. B5's inferred 1.212 s of unattributed cost sits
close to the measured 1.1529 s.

### The caveat, stated with the result

**The wall-clock difference does not by itself establish the claim, and this
chunk's own data shows why.** B4's clean binary run was 20.2278 s; B5c's binary
run, same configuration apart from free counters, is 19.4774 s. That is 0.7503 s
of spread, 3.85 percent, between runs that should be identical — the same order
as the 1.1529 s, 5.92 percent, binary-vs-rmi difference being attributed. The
counters carry the claim. B6 owes a repetition protocol before any wall-clock
figure is asserted.

### A second finding, and it is not about the model

**The exact binary-search control misses the +/-64 seed window on 38.62 percent
of queries.** A perfect `lower_bound` position still fails to put the nearest
split segment within 64 entries on more than a third of properties. That is a
property of Hilbert locality over extended objects on this data, not of the RMI,
and it makes `SEED_WINDOW` a live query-design parameter for both rungs.

It corrects the B6 sweep design recorded before B5c: the window must be swept
UPWARD as well as downward, and for BOTH seeders, over roughly
{8, 16, 32, 64, 128, 256, 512}. At 64 the window costs 128 distance computations
and leaves 141 resolve entries for binary; a larger window costs 2W but shrinks
`R_seed` and may cut resolve entries sharply. If the best operating point owes
nothing to learning, that is a legitimate B6 result and belongs in the table
stated as what it is.

### Acceptance — met

```text
counted difference       resolve entries 141.17 (binary) vs 352.52 (rmi)
                         the two seeders differ in a counted quantity, not
                         only in wall clock
seed-invariance          tight descent and phase-2 identical to the last digit
byte-identity            267,362 rows, identical on 27 of 29 columns
control path untouched   b5c_binary sha256
                         8ad41e8391f64e683e67ac253dc4d1e4302da7706f893763d0d32a689d6b7e9e
                         four-way identical with b5_binary, the B4 output, and
                         B3b's disk-mode file
determinism              b5c_rmi == b5c_rmi_rerun, sha256
                         86f05df0c4a32fd69fb4a63be3437edbc20466ec5beb3f22d8dae871302421aa
                         this also closes the determinism check B5 left open
lemma asserted           d_seed / d_best >= 1.0 on every run; a violation would
                         mean the resolve descent had missed the true nearest
                         segment, i.e. the exactness argument had failed
```

### Files, B5c

```text
modified  cpp/spatial_core/src/water_distance_hilbert.cpp   (12 hunks, additive:
          resolve counters, d_seed/d_best capture, --query-stats)
modified  tests/fixture_crosscheck.py   (B5c gate: counters differ, tight
          descent identical, d_seed/d_best >= 1)
added     python/scripts/rmi_probe_args.py
added     python/scripts/compare_seed_modes.py
added     outputs/validation/water_hilbert_query_stats_b5c_{binary,rmi}.json
added     outputs/cpp/cpp_nearest_water_hilbert_countywide_b5c_{binary,rmi}.csv
```

The two scripts exist because the alternative kept failing. Deriving the
`--rmi-probes` string by quoting Python at a PowerShell prompt was attempted
three times and mangled three times, in three different ways; and a hand-copied
probe constant in a shell command is exactly the provenance section 8 forbids.
`rmi_probe_args.py` derives it from the manifest; `compare_seed_modes.py` is the
acceptance check as a tool, comparing as TEXT with `dtype=str` so the check is on
the bytes the program wrote rather than on floats pandas re-parsed. B6 needs both
programmatically.

### Design note: why --query-stats is not the index manifest

The chunk specification said "stdout and the manifest." The manifest is written
BEFORE the query runs and describes the index; putting run aggregates there would
mean either reordering that write — losing the property that a manifest still
lands if the query throws — or writing the file twice. So the aggregates go to
stdout unconditionally and to a separate `--query-stats` JSON, on the same
reasoning that separated the seed-error report at B5. Unlike
`--seed-error-stats`, this report is **benchmark-eligible**: the counters are
free, which matters because B6 needs them on the runs it times.

### Validation performed

```text
g++ -std=c++17 -O2 -ffp-contract=off -static -Wall -Wextra   clean, no warnings
tests/fixture_crosscheck.py       ALL CROSS-CHECKS PASSED
  new: B5c resolve descent 79.58 (binary) vs 84.21 (rmi) entries;
       tight descent identical at 73.72
  new: seed quality, window missed 217 vs 284 of 1,093;
       mean d_seed/d_best 1.0719 vs 1.1564
python -m pytest -q --ignore=tests/test_spatial_split.py   257 passed
countywide                        acceptance, control-path and determinism
                                  digests all as recorded above
```

Fixture figures were bit-identical on Linux/g++ 13.3 and Windows/MSYS2 UCRT64,
so B5c is deterministic across compiler and platform as B1-B5 were.

---

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

## B6a result — the measurement harness, 2026-07-29

New: `python/caprm/ladder_benchmark.py`, `python/scripts/benchmark_water_ladder.py`,
`tests/test_ladder_benchmark.py`. No implementation source modified. Kept
separate from `water_benchmark.py`, whose `summarize_benchmark_runs` asserts the
algorithm set equals `{brute_force, feature_bvh}` and whose output is the
Milestone 2 artifact cited in section 19b; the new module imports its stdout
prefix maps rather than restating them.

Protocol, declared before measuring: 3 + 1 warm-up for rung 1 and 7 + 1 for
rungs 2-5, because rung 1 resolves a ~20x effect and rungs 4/5 a ~6 percent one
against ~4 percent noise; blocked by repetition and cyclically rotated by block
index; stdout to a pipe on every run, since all five binaries print progress from
inside the timed region; `--verify-counts`, `--uncapped-half` and
`--seed-error-stats` refused by assertion, `--query-stats` required on rungs 4-5;
dispersion as min/median/max and relative spread always, standard deviation only
at n >= 5; every run appended and fsynced to a JSON-lines sidecar; every row
carries a session id and a cell whose repetitions span sessions is refused.

Proving run at `_10000`: 31 timed runs, five cells, one output digest per cell,
no deterministic counter drift, five-of-five exact agreement at 10,000/10,000
with maximum absolute error 4.63671767647611e-10 m identical across all five
rungs — the residual is pure Python/C++ floating point with no index
contribution.

**Two sittings of the identical configuration disagreed.** Rung 1 moved 11.02
percent between them, 39.940 s to 44.342 s, on provably identical work; rungs
2-5 moved under 1 percent; every adjacent RATIO among rungs 2-5 reproduced to
within 0.25 percent. This is the evidence behind the session guard. The first
sitting's summary was overwritten before the sidecar existed and survives only
as transcribed values: 39.9400 / 1.1608 / 0.0753 / 0.3520 / 0.4077 s. Recorded
here as transcription, which is weaker than an artifact, with the overwrite as
the reason.

---

## B6b result — SEED_WINDOW as a build parameter, 2026-07-29

One hunk in `cpp/spatial_core/src/water_distance_hilbert.cpp`: an `#ifndef
CAPRM_SEED_WINDOW` guard defaulting to 64, plus `static_assert(SEED_WINDOW >=
1)`. Compile-time rather than a runtime flag deliberately: a runtime bound would
put a variable where the compiler sees a constant, changing loop bounds and
unrolling inside the timed region, and would make every measurement including
W=64 non-comparable with everything recorded through B5c. Build flags gain
`-Wl,--no-insert-timestamp`.

Gates, all passed on the post-edit source: countywide default build reproduces
`8ad41e83...d6b7e9e`; `fixture_crosscheck.py` ALL CROSS-CHECKS PASSED; nine
windows {8..2048} x two seeders at `_10000`, all 18 runs exit 0 against the two
expected digests; every binary self-reports its window on stdout and in its
`--query-stats` JSON, cross-checked against the `-D` value.

**The first attempt failed silently and is recorded in Nucleus 18.25.** Seven
binaries built with `-D` against source that never referenced the macro; the
compiler discarded the definition without warning; all seven were W=64; the
neutrality digest gate passed on them. The rule extracted: a neutrality gate
requires a positive control.

Range extension to W = 1024 and 2048 was declared AFTER seeing the {8..512}
results and is recorded as such (Nucleus 18.12): the pre-declared range did not
bracket either seeder's optimum. No result from {8..512} was revised.

---

## B6c result — the ladder and the window sweep, 2026-07-29

Two invocations, deliberately separate, with no comparison crossing them.

```text
A  ladder   5 rungs x 3 workloads at W=64        15 cells, 108 runs, ~1.9 h
B  sweep    2 rungs x 9 windows at countywide    18 cells, 144 runs, ~1.1 h
```

Every run in B was digest-gated and passed. Exactness closed for all fifteen
ladder cells: `_10000` and `_100000` at 10,000/10,000 and 100,000/100,000, and
countywide at 267,362/267,362 for brute force, the feature BVH and the segment
BVH, with the two Hilbert rungs inheriting validation through byte-identity to
`8ad41e83...` and `86f05df0...`. The countywide maximum absolute error is
4.657998431412125e-10 m for brute force, the feature BVH and the segment BVH
alike — three index structures, three traversal orders, one residual, which is
Nucleus 18.16 measured three ways at full scale.

### The three adjacent comparisons, Option A (original-geometry verification)

```text
             2 v 1        3 v 2         4 v 3          5 v 4    n
_10000       33.6x     15.681x     4.732x slower     +14.31%   3/7
_100000      11.3x     14.928x     2.138x slower      +9.80%   3/7
countywide   17.0x      6.905x     1.947x slower      +6.48%   3/7
```

Segment checks per property beside the clock, never inferred from it:

```text
             brute force   feature BVH   segment BVH   hilbert (both seeders)
_10000        1,063,159      34,011.2       1,269.29        1,486.11
_100000       1,063,159     113,194.9       6,697.86        8,056.00
countywide    1,063,159      70,770.6       9,407.62       11,021.83
```

Three durable readings. Every comparison SHRINKS as the query count grows,
because phase-2 verification is seed- and index-invariant common work that
dilutes what the index does. The 4-v-3 phase-2 penalty is +17.1 percent at
`_10000` and +17.2 percent at countywide against segment-BVH baselines that
differ 7.4-fold — the cost of flattening 2D to 1D is stable where the absolute
work is not. And `_100000` does 1.599x more feature-BVH work per property than
countywide while doing LESS segment-BVH work, which the counter explains: 17,377
segments per candidate feature against 12,873, so the feature BVH's cost tracks
feature SIZE and the segment BVH's does not. That is B1's granularity premise
measured against a workload contrast rather than asserted.

**`brute_force@countywide` carries a 31.71 percent spread at n=3**, five times
any other cell and rising with run length across all three workloads. Its number
is an order-of-magnitude statement, ~17x, not a measurement. Rung 1 is in no
adjacent comparison.

### The window sweep, countywide

```text
W        binary s    rmi s   rmi/binary   binary missed   exchange rate
   8      18.1273   20.2337    1.11620        69.88%        17.55:1
  64      17.9349   19.0764    1.06365        38.62%        10.44:1
 512      18.3422   18.5639    1.01209        17.13%         3.07:1
2048      20.8680   20.8683    1.00001        11.84%         0.83:1
```

Monotone across nine points, converging to unity to five decimal places. See
Nucleus 18.26 and 18.27.

### The cost model

B5c's independently isolated 20.40 ns per resolve-descent entry predicts twelve
measured wall-clock gaps within roughly 10 percent everywhere and within 0.2
percent at the countywide operating point; the least-squares slope through the
origin over the sweep is 21.02 ns/entry. A joint fit over the eighteen sweep
cells separates two access patterns — ~3.2 ns for a sequential window-scan entry
against ~25 ns for a scattered resolve-descent entry, R^2 0.997 with structured
residuals. That second fit is exploratory, not a validated prediction.

### Cross-invocation term, measured

```text
                    invocation A   invocation B    diff
hilbert_binary         17.7500       17.9349      +1.04%
hilbert_rmi            18.9003       19.0764      +0.93%
5 v 4 ratio            1.06481        1.06365      0.116 pp
```

Absolutes move ~1 percent between invocations; the ratio agrees to 0.116
percentage points. This is why the project reports ratios within an invocation
and absolutes with their invocation named.

### Memory, countywide

```text
                    structure      peak RSS      peak commit
segment_bvh        119,768,836   185,774,080    342,327,296
hilbert_rmi         13,711,112   232,501,248    285,212,672
                   8.74x smaller  1.25x larger   1.20x smaller
```

Three instruments, two directions. See Nucleus 18.24.

### Correction carried by B6c

`9,716.87` is B1's cap=100 figure, not the cap=25 operating point the ladder
runs. The cap=25 countywide value is 9,407.6 (B2's sweep table) and B6c measured
9,407.617649. Four turns of B6 analysis used the wrong baseline, and the
corrected 4-v-3 phase-2 penalty is +17.2 percent countywide rather than +13.4.
The wrong figure still appears in `docs/kickoff_prompts_m4.md` and in
`tests/test_ladder_benchmark.py`'s `SEGMENT_BVH_STDOUT` fixture and must be
fixed there.

---

## Artifacts generated by B6a-B6c

```text
outputs/benchmark/water_ladder_runs_{ladder,sweep}.csv and .jsonl
outputs/benchmark/water_ladder_runs_b6b_verify10k_w{8..2048}.csv
outputs/benchmark/water_ladder_runs_b6b_neutrality.csv
outputs/validation/water_ladder_summary_{ladder,sweep}.json
outputs/validation/water_ladder_summary_b6b_*.json
outputs/validation/b6b_window_sweep_counters_10000.csv
outputs/validation/b6c_{ladder,sweep}_counters.csv
outputs/validation/ladder_agreement_*.csv, ladder_summary_*.json  (15 cells)
outputs/validation/b6_analysis.json, b6_benchmark_tables.md
cpp/spatial_core/build/water_distance_hilbert_w{8..2048}.exe
```

---

## B6c-2 result — the verification cross-product, 2026-07-29

`verification_mode` became a third cell dimension in the harness:
`RungSpec.verification_mode_position` (index 2 for rungs 3-5, `None` for rungs
1-2, which verify over original geometry by construction), substituted by
`verification_positionals()`, which asserts the slot holds a known mode before
writing to it. The cell key omits `@original`, so B6c's recorded keys stay
comparable. Digest keys now match against the full cell key, and an unqualified
`rung=` digest no longer spans verification modes — it still spans seed windows,
which are byte-neutral. That distinction was a bug caught on the first run: the
Option B cells inherited the Option A digests and failed.

### Exactness — Option B is a reportable mode

All three countywide split cells exit 0 at 267,362/267,362 with **zero
`feature_id` disagreements**, maximum absolute error 9.156906344287563e-10 m,
identical across the three and inside B2's predicted 8.82e-10 to 9.17e-10 range.

### The cross-product, countywide, W=64, one invocation

```text
                    Option A       Option B      A -> B
segment_bvh          9.6261 s       1.6435 s     5.857x
hilbert_binary      18.8119 s       9.4895 s     1.982x
hilbert_rmi         20.1691 s      10.6772 s     1.889x

4 v 3   1.954x slower  ->  5.774x slower     amplification 2.95x
5 v 4     +7.21%       ->    +12.52%
```

Both pre-declared predictions held: 4-v-3 predicted ~5.5x, measured 5.774x;
5-v-4 predicted +12.8 percent, measured +12.52.

### Optional sweeps

**Nine-window sweep under Option B, countywide** (`sweepB`, 18 cells). The
rmi/binary ratio spans 1.21402 at W=8 to 0.99875 at W=2048, a WIDER range than
Option A's, so the window dependence is not an artifact of the diluted column.
Slope through the origin 21.19 ns/entry against Option A's 21.02. The sub-unity
points at W=1024 and 2048 have gap/range of 0.12 and 0.02 and are NOT a measured
learned win.

**Mode x workload grid** (`gridAB`, 18 cells). See Nucleus 18.27 for the
denominator finding and 18.28 for the amortization crossover. Check-count ratios
across all six mode pairs: 1.4308x to 1.4974x, mean 1.4602x, against B2's 1.43x.
Resolve entries, candidate features and memory are identical between modes at
every workload.

### Diagnostics

`--seed-error-stats` at W=2048 countywide, not benchmark-eligible, writing
`outputs/validation/diag_seed_error_w2048.json`: 31,643 of 267,362 properties
(11.835 percent) have their nearest split segment outside a ±2048 window; mean
`d_seed/d_best` 1.060939, max 23.432272. The per-property content of that JSON has
not yet been read and is the input to the open question below. The one-property
memory isolation produced index construction at 0.912181 s but no memory figure;
see Nucleus 18.24.

### Canonical digests established by B6c-2

```text
segment_bvh@10000@split              f17a3580cde5b54ae969d10f5270daf05c209bb2d0a2506fa387ef68ff6dccdb
segment_bvh@100000@split             4c715a915d6a7711f49ffffd1e61953240f231afe6fbc858e67dafa9470abf8c
segment_bvh@countywide@split         90ecb3c996b07057d65a50fd074b48868d05262d2cec8bb25047bea48f79b3ea
hilbert_binary@10000@split@w64       824482df5ee14d6ea8a5520f64bc274c5d99cf8a22f262dc6527a6946e3adfa0
hilbert_binary@100000@split@w64      c8f03e38907376a6e2a8f1384d61686b09073f875e772bb51f01ec83cebb5421
hilbert_binary@countywide@split@w64  05c799b1fcef76bee01701d88ae4f2512d0e6b460aa63aa7f17143616ede12ee
hilbert_rmi@10000@split@w64          ce547239478e4e5cd82eb9119de388851b92a9ca77cff2dd62b3f43517c968c9
hilbert_rmi@100000@split@w64         22c69b1be847127bf5ac4df20adc5b2f7b940f1ef0628ef9706282d48cbe1010
hilbert_rmi@countywide@split@w64     008945d1a38aff3570c2eafaed7ec1b6276243062b63f1dd5c8fafa78b424620
```

### OUTSTANDING — six cells not yet validated against the reference

The `_10000` and `_100000` Option B cells from `gridAB` have digests but have NOT
been run through `compare_python_cpp_water.py`. The completion gate requires exact
agreement for every implementation claiming exactness at every workload, so B6d
must close this before PHASE B closes.

### Artifacts

```text
outputs/benchmark/water_ladder_runs_{b6c2,sweepB,gridAB}.csv and .jsonl
outputs/validation/water_ladder_summary_{b6c2,sweepB,gridAB}.json
outputs/validation/{b6c2,gridAB}_counters.csv
outputs/validation/diag_seed_error_w2048.{json,txt}
outputs/benchmark/diag_{seed_error_w2048,one_property}.csv
outputs/validation/ladder_{agreement,summary}_*_split*.{csv,json}   (3 countywide)
```

---

## B6d result — the published tables and the close-out, 2026-07-30

B6d wrote no new measurement. It patched the derivation layer, closed the last
exactness cells, and published the cross-product.

**The mode dimension, and what it was actually doing.** `analyze_b6_results.py`
turned out to be a thin CLI; every derivation lives in
`python/caprm/ladder_analysis.py`, and that is the file B6d patched. The defect
was worse than mixing modes. `adjacent_comparisons` built a per-workload dict as
`by_algorithm[row["algorithm"]] = row`, so a frame containing both modes emitted
ONE set of comparisons drawn from whichever mode iterated last, with no mode
recorded on the output. Measured on the `b6c2` artifact before the patch: two
Option B rows, Option A dropped entirely, and five invariants failing because the
byte-neutrality check was comparing Option A's digest against Option B's — a
check that is correct and a grouping that was not.

**One defect shape, six sites.** Fixing mode surfaced the identical shape in
INVOCATION, and each site announced itself as a number moving rather than as an
error:

```text
cost_model sweep population   slope 21.02 -> 21.46; sweep's W=64 and b6c2's
                                W=64 collided in one group
cost_model population key     one Option B point joined Option A's nine-window
                                sweep
adjacent_comparisons          countywide 3-v-2 read 6.540x instead of 6.905x,
                                mixing ladder's rung 2 with b6c2's rung 3
verification_decomposition    calibrating on one invocation and applying the
                                constant to another drove rung 3's own residual
                                to -1.689 us/property
access_pattern_fit            countywide Option A collapsed to R^2 0.688
```

Workload, verification mode and invocation are now part of every grouping key.
Comparisons that must borrow across an invocation — rung 2 exists in one
invocation only, so Option B's 3-v-2 cannot be formed without it — carry
`crosses_invocation: true` rather than being suppressed or emitted silently.

**A second rung-boundary error, found the same way.** The search/verification
decomposition initially applied rung 3's per-check constant to every rung and
gave brute force a search cost of -2,261 us/property. A brute-force check and a
segment-BVH check are not the same unit of work; B2's rule that counts are
comparable within a verification mode and not across implementations that verify
differently extends to this, and `DECOMPOSABLE_RUNGS = (3, 4, 5)` now encodes it.

**The slope reconciliation.** 20.33 and 21.02 were never in conflict. They are
different populations of the same fit, published under one label. Each population
is now named and emitted separately:

```text
all_points          n=29   20.50 ns/entry   sweep plus single-window workloads
window_sweep_only   n=18   21.10 ns/entry   countywide@original@sweep_runs and
                                              countywide@split@sweep_split_runs
resolvable_only     n=15   21.34 ns/entry   gap exceeds both cells' full range
B5c isolated constant       20.40 ns/entry   measured before any B6 timing
```

**The six exactness cells are closed.** Every implementation claiming exactness
now agrees field-for-field with the Python reference at every workload in both
verification modes.

```text
segment_bvh    @10000 @split   10,000/10,000 all fields   max 8.659526e-10 m
hilbert_binary @10000 @split   10,000/10,000 all fields   max 8.659526e-10 m
hilbert_rmi    @10000 @split   10,000/10,000 all fields   max 8.659526e-10 m
segment_bvh    @100000@split  100,000/100,000 all fields  max 9.066881e-10 m
hilbert_binary @100000@split  100,000/100,000 all fields  max 9.066881e-10 m
hilbert_rmi    @100000@split  100,000/100,000 all fields  max 9.066881e-10 m
```

The Option B bound is wider than Option A's 4.658e-10 m, as expected: split
geometry introduces one additional rounding in the split-point computation.

**The cross-product, published.** Three adjacent comparisons, two modes, three
workloads. Cross-invocation rows omitted here and flagged in the artifact.

```text
workload    mode      3 v 2            4 v 3           5 v 4
10000       original  15.690x faster   4.735x slower   1.143x slower
10000       split     --               8.488x slower   1.179x slower
100000      original  14.928x faster   2.138x slower   1.098x slower  NOT RESOLVED
100000      split     --               5.747x slower   1.192x slower
countywide  original   6.905x faster   1.954x slower   1.072x slower
countywide  split      --              5.774x slower   1.125x slower
```

The absolute 5-v-4 gap holds between 4.442 and 6.188 us/property across all six
cells while the percentage ranges 7.2 to 19.2. That is the whole point: the
counted quantity is the invariant and the percentage is an artifact of how much
shared verification work sits in the denominator.

**The result that changes the claim.** Under split-geometry verification at
W=2048 the ratio is **0.99875** — the learned rung is faster. The sign does not
merely approach 1.0, it crosses it.

```text
countywide original   W8 1.11620  ->  W2048 1.00002
countywide split      W8 1.21402  ->  W2048 0.99875
```

The measured negative is real at the shipped configuration and is not a property
of learned indexing on this data. It is a property of a two-parameter operating
point that the literature does not report.

**Search and verification, separated.** Per-check cost is calibrated from rung 3
alone, per workload and per mode, assuming rung 3's search is 0.6 percent of its
query time (B1 counted ~0.4 percent by a different route). Rungs 4 and 5 never
enter the calibration, so their agreement is an out-of-sample test of
mode-invariant search:

```text
per-check ns    10000       5.9340 original   4.3332 split
                100000      4.0092 original   1.1880 split
                countywide  3.9998 original   0.9918 split   (4.03x; B2: 4.21x)
```

Cross-mode search disagreement is 1.0 to 2.6 percent at five of six cells;
`100000 hilbert_binary` sits at 10.3 percent and is the one cell where linearity
in the check count visibly strains.

**The exactly-determined solve is recorded as a failure.** Two rungs times two
modes is four equations in four unknowns and needs no assumed search fraction. It
is unusable: both check-count ratios are ~1.45, so the constraints are nearly
collinear. On the countywide `b6c2` group it returns a rung-3 search cost of
-6.82 us/property with a per-check ratio of 2.27x against B2's 4.21x. **Its
`usable` flag tests non-negativity only, and that is necessary but not
sufficient** — on the `gridAB` group the solve returns a positive search cost and
a per-check ratio of 0.575x, implying Option B checks cost MORE than Option A,
which contradicts B2 by a factor of seven. The diagnostic is kept because the
anchored calibration needs its justification on the record; it is not a gate.

**Inflation, and its opposite motion.** Capped geometric inflation and phase-2
verification move in opposite directions across workloads, so neither figure means
anything without its workload named. It is also not monotone in query count:

```text
workload    entries in range  admitted  inflation  phase-2 checks  2W/counted
10000                 1.6906   11.7066    6.9245x        1,486.11      1.1322
100000                1.5887    9.5768    6.0282x        8,056.00      1.5507
countywide            1.6067   10.2783    6.3972x       11,021.83      0.9067
```

**The locality premium, now fitted in both modes.** The `2W` window scan is an
uncounted additive term whose per-entry cost differs from a resolve-descent
entry's because one access pattern is sequential and the other scattered. The fit
requires a free intercept to absorb the mode-invariant verification term; without
one the regressors are asked to explain ~42 us/property they have no access to
and the fit inverts to R^2 = -50.

```text
countywide original  3.057 ns window   22.450 ns resolve   7.343x   R^2 0.9899
countywide split     3.314 ns window   23.005 ns resolve   6.941x   R^2 0.9825
```

Exploratory, not a validated prediction. It is reported because it is the reason
an uncounted entry and a counted entry must never be summed.

**Memory, three instruments, still disagreeing in direction.** None may be quoted
alone (Nucleus 18.24).

```text
cell                            structure       peak RSS      peak commit
brute_force@countywide                 --     72,503,296       85,061,632
segment_bvh@countywide        119,768,836    185,843,712      342,319,104
hilbert_binary@countywide@w64   9,516,712    232,357,888      285,175,808
hilbert_rmi@countywide@w64     13,711,112    232,370,176      285,171,712
```

### Files changed by B6d

```text
python/caprm/ladder_analysis.py        mode and invocation dimensions;
                                         DECOMPOSABLE_RUNGS; cost-model
                                         populations; verification_decomposition,
                                         inflation_axis, access_pattern_fit
python/scripts/analyze_b6_results.py   five sources, absent-source reporting,
                                         the new tables
tests/test_ladder_analysis.py          NEW, 38 tests
tests/test_ladder_benchmark.py         SEGMENT_BVH_STDOUT total corrected from
                                         97,168,700 (B1's cap=100 figure) to
                                         94,076,176
docs/benchmark_results.md              PHASE B section added
README.md                              11 corrections
outputs/validation/b6_analysis.json    regenerated, 5 sources
outputs/validation/b6_benchmark_tables.md   regenerated
outputs/validation/ladder_summary_{segment_bvh,hilbert_binary,hilbert_rmi}_{10000,100000}_split.json
```

### Tests and validation

```text
pytest tests/test_ladder_analysis.py tests/test_ladder_benchmark.py -q
  70 passed in 2.03s

python/scripts/analyze_b6_results.py
  Invariants: 137 passed, 0 failed
  all_points n=29 20.50 / window_sweep_only n=18 21.10 / resolvable_only n=15 21.34
  no absent sources, no unphysical cells
```

Regression: ladder plus sweep alone still reproduce 64/64 invariants, slope
20.334356 and the countywide Option A comparisons at 6.905x / 1.947x / 1.065x —
the previously published values, unchanged by the patch.

### Reconciliations still open against this artifact

```text
per-check split cost   0.9918 ns here against Nucleus 18.19's 0.922
locality premium       7.343x here against Nucleus 18.19's ~7.8x
peak RSS segment_bvh   185,843,712 here against B6c's 185,774,080
```

All three are within the ~1 percent cross-invocation drift B6a measured, except
the premium. The artifact is authoritative; the Nucleus prose was written from a
conversation-side calculation, which is the practice B6d exists to end.

---

## C1 result — training data and a blocked K-fold partition, 2026-07-30

C1 built no model. It built the dataset and the partition, and the partition was
the whole chunk.

### The dataset

`outputs/training/supervised_dataset_v2.csv`, SHA-256
`2e3132faf5ce2dc0f31bd4d7ff40041171f4f68d99e91b5a5c2f350151ba7799`, built by
`python/scripts/build_supervised_dataset.py` from the frozen index and the
frozen projected coordinates. `scoring.py` is not imported; the label is read,
never recomputed.

```text
rows / unique property_id      267,362 / 267,362, both sides
key-set asymmetry              0 in each direction
nulls, any column              0
scoring_policy_version         exactly ['preliminary_exposure_index_v2']
index CSV vs its manifest      SHA-256 match
label mean / sigma             34.63218408001099 / 13.063711939924076
```

The mean and sigma reproduce the frozen index manifest to all printed digits,
which is an independent check that the join preserved row identity.

**Two dtype hazards, both closed.** The key is text: 267,361 IDs are
zero-padded 20-character digits and one is alphanumeric,
`1600100001003000WC`. Read without an explicit string dtype it loses leading
zeros on 267,361 rows and coerces one to NaN, and the join then fails looking
like a data problem. Separately, pandas' DEFAULT CSV float parser is not
correctly rounded: on the countywide coordinate file it disagrees with
`float_precision="round_trip"` on 34,221 eastings and 43,206 northings by up to
9.31e-10 m, the same order as `BOUNDARY_EPSILON_METERS`. Reader and writer are
pinned together (`round_trip` in, `%.17g` out) so the dataset reproduces its
source coordinates exactly. Whether the same parser sits between the Python
reference and the C++ output in `water_validate.py` is an OPEN QUESTION recorded
in section 20, not a claim; distances are O(10^3) m where the ULP is ~1e-13, so
it is unlikely to explain the 4.658e-10 m agreement residual.

### The label is a well-defined function of position

376 co-located coordinate groups covering 1,700 rows, **zero** carrying
differing labels; maximum within-group label range 0.0. The irreducible floor
for any coordinate-only surrogate is 6.27e-16 RMSE against a target variance of
170.66 — float noise from subtracting a group mean. **Every C2 residual is model
error; none is target ambiguity.**

### Correlation length, measured and model-free

`outputs/validation/spatial_correlation_v2.json`, from
`python/scripts/measure_spatial_correlation.py`. Empirical semivariogram in two
passes: KD-tree ball queries from sampled centres against all 267,362 points for
short lags, chunked exhaustive pairwise over a 20,000-point subsample for long
lags. Sill = sample variance = 170.66057.

```text
gamma/sill    0.10    0.25    0.50    0.75    0.90    0.95
lag (m)        125     625   2,125   6,125   7,625   8,125
```

At 12.5 m separation gamma/sill is 0.018: adjacent parcels are near-duplicates,
now with a number.

**A fitted range cannot carry this decision.** Fitting the standard exponential
model and sweeping only the fit window moves the range parameter from 503.5 m to
16,592 m — 33-fold — at R^2 >= 0.952 throughout. The block edge is therefore
chosen against the model-free crossing lags, and `fit_exponential` is labelled a
diagnostic and swept for exactly this reason. This is Nucleus 18.27 recurring in
a new place.

**The field is non-stationary.** The variogram does not plateau and overshoots
to gamma/sill = 1.11 at 12.6 km. A degree-3 polynomial trend accounts for
R^2 = 0.2527 and barely moves the short-lag shape. No partition of a 51 x 48 km
county decorrelates this field. What C1 can claim is a measured separation with
a stated residual, not decorrelation.

### The gate, and why the Roadmap's wording was replaced

The criterion, defined once in `caprm/split_gate.py`: a partition passes at
separation `s` when every surviving holdout property lies at least `s` metres
from every training property. `>=` and not `>` — two points on the facing edges
of an `s`-wide gap are exactly `s` apart, and `>` is a latent failure.

The Roadmap's grid wording — no test property within one block of a training
property — was measured and found **unachievable**. `min_chebyshev_to_train` is
1 in every configuration measured: at a 70 percent train block share every
occupied block has a training block within Chebyshev 1. The metric criterion is
binding; the Chebyshev figure is reported beside it rather than derived from it,
because the two genuinely diverge. The Chebyshev value is minimised over ALL
training blocks, not read off the metrically nearest training property — those
are different quantities, and conflating them is the Nucleus 18.29 defect shape.

### Why a single blocked holdout was rejected

Holding separation fixed and varying only the seed across ten draws
(`outputs/validation/c1_split_seed_stability.json`):

```text
geometry                  test-mean-label range   baseline RMSE range   R^2 range
b2000 0.70/0.15 w625            9.82 pts               6.58            -0.885 … 0.042
b3000 0.60/0.20 w625            7.29 pts               3.05            -1.086 … -0.128
b4000 0.50/0.25 w2125          11.94 pts              18.69            -4.514 … 0.573
b8000 0.60/0.20 w2125          13.14 pts              11.58            -2.325 … -0.110
```

Population mean 34.632, sigma 13.064. The seed moves the test set's own mean by
up to one sigma and the baseline RMSE by more than the RMSE itself. See Nucleus
18.32.

### The partition of record

`python/scripts/build_spatial_kfold.py`, manifest at
`outputs/validation/c1_kfold_manifest.json`.

```text
buffer w        2,125 m   the lag at gamma/sill = 0.50, READ from the variogram
                          artifact at runtime rather than typed in
block edge b   10,000 m   chosen on fold balance and seed stability, declared
                          before coverage was examined
K                     5   every occupied block is test exactly once, val once
seeds                 5   20260722 … 20260726, all persisted
isolation          test separated from validation as well as training
grid origin        (0, 0) in EPSG:26918
fold hash          blake2b(f'{seed}:fold:{i}:{j}') % K
```

29 occupied blocks; folds 5/6/7/5/6 at the primary seed.

```text
     seed  tested   cov%    RMSE       R^2   testMean  testStd   minSep
 20260722   89,344  33.42  15.386  -0.3646    36.497   13.171   2125.0
 20260723  100,257  37.50  15.429  -0.4343    35.299   12.883   2125.0
 20260724  130,187  48.69  14.049  -0.1465    31.899   13.121   2125.0
 20260725  118,357  44.27  15.538  -0.4137    33.919   13.068   2125.0
 20260726  126,177  47.19  16.530  -0.5418    32.116   13.312   2125.0
```

Test sigma now tracks the population (12.88–13.31) where the single holdout gave
7.78–16.31.

### Controls, through the identical gate, judged at 2,125 m

```text
random                       n=40,205             min 0.000 m   100.0% violate   FAIL
blocked unbuffered, f0..f4   n=11,751…76,741  min 5.9–13.3 m   7,388–40,217     FAIL
blocked buffered             every fold, every seed  min 2125.0 m   0 violate    PASS
```

The random control's minimum is exactly 0.000 m because the 1,700
coordinate-duplicate rows land on both sides. The unbuffered rung is the one
that matters: it isolates the buffer's contribution from blocking's, and it
fails, so the buffer is not over-building.

### The nearest-training-neighbour baseline, declared before any model

Aggregate over the union of each seed's folds, every property predicted at most
once:

```text
blocked K-fold      RMSE 14.05 … 16.53      R^2 -0.542 … -0.147
random split        RMSE  4.933             R^2  0.8526 … 0.8667 (10 seeds)
```

Non-overlapping ranges. A random split would have credited "copy your nearest
training neighbour" with R^2 = 0.86. **A C2 surrogate that does not beat RMSE
16.53 on every seed has learned the neighbourhood, not the function.**

### Acceptance

```text
blocked_gate_passed_every_fold_every_seed   true   (25 fold x seed cells)
unbuffered_control_failed                   true
random_control_failed                       true
deterministic_every_seed                    true   (rebuild, identical assignment)
aggregate_baseline_rmse_range               2.4807489792742867
aggregate_baseline_r2_min                   -0.5417604651882764
aggregate_baseline_r2_max                   -0.14653213654891473
```

### Cross-platform reproduction

C1-a's artifacts were generated independently on Linux / Python 3.12 / scipy
1.17.1 / numpy 2.4.4 and on Windows / Python 3.14 / scipy 1.18.0 / numpy 2.4.6.
`c1_split_geometry_sweep.json` and `c1_split_seed_stability.json` are
IDENTICAL; the variogram CSVs are byte-identical; the 39 MB dataset reproduces
to the same SHA-256. `spatial_correlation_v2.json` differs in 99 scalars, ALL
inside `exponential_fit_window_sweep`, at most 1.0e-7 relative — the
Levenberg-Marquardt iteration terminating differently. The one quantity that
moved is the one already labelled a diagnostic.

### What C1 did not achieve, stated plainly

- **K-fold reduces seed dependence; it does not remove it.** Aggregate RMSE
  range 2.48 against 3.05–18.69 across single-holdout geometries, but coverage
  still swings 89,344 to 130,187, because the seed still sets fold composition
  and fold composition sets which properties survive erosion. C2 reports across
  all five seeds; a single-seed figure is a diagnostic, never a claim.
- **The test set is not a random sample of the county.** It is deliberately the
  subset far from training data. Error measured on it is error at separation
  >= 2,125 m. C4 must frame it that way.
- **The field is not decorrelated at 2,125 m.** gamma/sill = 0.50 is a stated
  residual dependence.

### Files, C1

```text
python/caprm/supervised_dataset.py            new
python/caprm/spatial_correlation.py           new
python/caprm/split_gate.py                    new
python/caprm/spatial_kfold.py                 new
python/caprm/spatial_split.py                 committed (was untracked WIP);
                                              modified once, to add a hash
                                              namespace whose default
                                              reproduces the original key byte
                                              for byte
python/caprm/build_spatial_split.py           committed (was untracked WIP)
python/scripts/build_supervised_dataset.py    new
python/scripts/measure_spatial_correlation.py new
python/scripts/sweep_split_geometry.py        new
python/scripts/measure_split_seed_stability.py new
python/scripts/build_spatial_kfold.py         new
tests/test_supervised_dataset.py              new  (11)
tests/test_spatial_correlation.py             new  (16)
tests/test_split_gate.py                      new  (16)
tests/test_spatial_kfold.py                   new  (20)
tests/test_spatial_split.py                   committed (11, previously ignored)
requirements.txt                              scipy==1.18.0 pinned
```

Unmodified: `scoring.py`, the v2 index, its manifest, and every Milestone 1–3
evidence product.

### Artifacts of record

```text
outputs/training/supervised_dataset_v2.csv            39 MB, regenerable, untracked
outputs/training/supervised_dataset_v2_manifest.json
outputs/validation/spatial_correlation_v2.json        + three variogram CSVs
outputs/validation/c1_split_geometry_sweep.json
outputs/validation/c1_split_seed_stability.json
outputs/validation/c1_kfold_manifest.json             the partition of record
outputs/splits/spatial_kfold_countywide_seed*.csv     5 x ~10.5 MB, regenerable
outputs/splits/random_control_countywide.csv
```

The split CSVs are fully determined by seed, config and dataset, so only the
manifests are tracked; each carries the checksums needed to verify a
regeneration.

---

## Immediate next task — C2

**C2. Train the surrogate.** A small MLP mapping `(x, y)` in EPSG:26918 to
`exposure_index_0_100` at `preliminary_exposure_index_v2`, trained and evaluated
under the C1 partition and reported across all five recorded seeds.

The constraints C1 hands it, none negotiable:

1. Train on the pipeline's own deterministic output. Never on flood outcomes:
   FEMA zone determines mandatory insurance purchase, which determines who can
   file a claim, so claims correlate with the FEMA component by construction.
2. Do not replace the scoring layer. Its only defensible property is that it is
   interpretable.
3. Beat the declared floor. Nearest-training-neighbour scores RMSE 14.05 to
   16.53 across the five seeds. A surrogate below that on some seeds and above
   on others has not beaten it.
4. Report across five seeds. A single-seed number is a diagnostic (Nucleus
   18.32).
5. A model is an artifact (Nucleus 18.20): architecture, seed, split manifest
   digest, loss curve, and a weight checksum, or it did not happen.
6. Every number reported lands in a module with a test before it is quoted.

The mechanistic prediction to declare BEFORE training, so C3 can confirm or
refute it: **FEMA zones are discontinuities.** 98.1 percent of properties sit at
the same FEMA component and the index steps sharply across a zone boundary. A
smooth network cannot represent a step; it can only ramp. Residuals should
therefore spike along zone boundaries and stay small elsewhere. Confirming or
refuting that is C3's real result, and the prediction must not be adjusted after
the fact.

---

# 22. Recommended First Prompt for a New AI Assistant

Use:

> We are continuing CAPRM-Flood at Milestone 4, PHASE C, chunk C2 — training the
> neural surrogate. Read Nucleus sections 14b, 18.17, 18.18, 18.20, 18.22,
> 18.25, 18.27, 18.29, 18.32 and 18.33; this document's sections 16, 20 and 21
> including the C1 result subsection; and `CAPRM_Flood_Roadmap.md` PHASE C,
> before proposing anything.
>
> Confirm the commit recorded in this document's section 2 matches
> `git log -1 --oneline`. If it does not, say so before continuing — you are
> reading a stale copy. The canonical documents live under `docs/canon/`.
>
> Milestones 1 through 3 are frozen. The exposure index is not under active work
> and must not be modified. `python/caprm/scoring.py` is read-only for the whole
> of PHASE C. PHASE B is closed; no kernel, tolerance, tie rule, region
> predicate or emitted field changes.
>
> C1 is complete. The dataset is `outputs/training/supervised_dataset_v2.csv`
> and the partition of record is `outputs/validation/c1_kfold_manifest.json`:
> blocked K-fold, block edge 10,000 m, buffer 2,125 m, K = 5, five recorded
> seeds, test isolated from validation as well as training. The gate passed on
> all 25 fold-by-seed cells with both controls failing. Do not rebuild the
> partition; consume it.
>
> Six traps, all measured and all still walkable-into:
>
> - **A single-seed number is not a result.** The seed moves a blocked split's
>   reported error materially (Nucleus 18.32). Report across all five.
> - **The floor is already declared.** Nearest-training-neighbour scores RMSE
>   14.05 to 16.53. Beating it on some seeds is not beating it.
> - **Test error is error at separation >= 2,125 m**, not countywide error.
>   Never quote it as the latter.
> - **The target has zero coordinate ambiguity** (measured: 376 co-located
>   groups, none conflicting). Any residual is model error. Do not attribute it
>   to label noise.
> - **Read the split, do not recompute it.** The split file stores `fold` and a
>   `dropped_mask` bitmask; `caprm.spatial_kfold.roles_from_codes` rebuilds the
>   full role matrix and is tested to do so exactly.
> - **A parameter that moves the headline must be swept, not fixed silently**
>   (Nucleus 18.27). If a Fourier feature scale changes the answer, the sweep is
>   the result.
>
> Every number reported in conversation must land in a module with a test before
> it is quoted, the rule `analyze_b6_results.py` exists to enforce.
>
> Completion gate for C2: a trained model per seed, each an artifact with
> architecture, seed, split-manifest digest, loss curve and weight checksum;
> test error reported across all five seeds against the declared floor; the
> memorization gap against the random control measured and reported; and the
> three canonical documents updated.

---

# 23. Current Canonical Summary

As of July 28, 2026, CAPRM-Flood has completed and frozen Milestones 1, 2, and
3. Three evidence families spanning three different data topologies — FEMA
vector polygons, hydrography lines and areas, and a terrain raster — produce
one evidence contract for 267,362 unique Monroe County properties, with exact
Python/C++ agreement on every compared field at every scale. Milestone 3 added
a four-component exposure index at scoring policy
`preliminary_exposure_index_v2`, measured component influence by exact variance
decomposition, characterized the ranking as moderately sensitive to weight
choice across 40 configurations with metric calibration, and shipped an
automated product audit that verifies the stored artifacts against their own
manifests. The suite passed at 181 tests when Milestone 3 froze and passes at
257 now, the growth being Milestone 4's own tests; the audit reports no
failures. The
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
maximum segment length, sweeps the entry-extent parameter that trades pruning
against search-radius inflation, orders segments along a Hilbert curve,
validates the resulting query path with a binary-search control that isolates
the contribution of learning from the contribution of dimensionality reduction,
trains a recursive model index, and benchmarks the result against an exact
baseline whose correctness is already proven field-by-field against an
independent implementation. As of B6d all five rungs are built,
measured in both verification modes at three workloads, and validated exactly: segment granularity cut phase-2 work 7.28x and distance-exact
splitting cut admitted entries 546x, both classical; the 1D Hilbert reduction
cost 13.4 percent in phase-2 work; the trained index cut seed probes 3.20x on
index keys, which is about 0.13 percent of counted query work because phase-1
admission was already a rounding error; and the ported model, whose output is
byte-identical to its control on all 267,362 properties, ran the countywide
query slower at the shipped configuration — 7.2 percent under Option A at seed
window 64, where B5c's single unrepeated run had read 3.85 percent. B6 then
showed that figure has no fixed sign: across nine seed windows it moves to
1.00002 under Option A and to 0.99875 under Option B, where the learned rung is
FASTER. The negative result is real at the operating point and is a property of
that operating point rather than of learned indexing on this data. The equi-depth diagnostic locates the remaining model
error in the router rather than the leaves, and B5c counted the slowdown rather than
inferring it: a mispredicted seed widens the resolve descent from 141.17 to
352.52 entries per property, so the model buys 20.24 saved key probes for 211.34
extra distance computations, about ten to one against. The mechanism is
convexity — cost grows as the square of the search radius, the RMI's worst
overestimate reaches 517x the true radius against the control's 32x, and the
miss RATE barely moves — so the mean prediction error is the wrong summary
statistic for a predictor that feeds a radius. The project's most transferable
Milestone 4 finding so far is therefore methodological: a component proved
correctness-neutral is not thereby cost-neutral, a ceiling expressed in counts
bounds nothing about duration, and the value of an exact seed position on this
query is the quality of the bound it yields rather than the lookups it saves.
Precipitation remains a gated stretch goal behind that work.