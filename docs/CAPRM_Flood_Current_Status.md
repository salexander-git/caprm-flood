# CAPRM-Flood Current Status — 2026-07-28

## Purpose of This Document

This document records the exact current operational state of CAPRM-Flood as of **July 28, 2026**.

```text
Verified at commit:   see section 2
Test suite:           257 passed  (excluding untracked spatial_split WIP)
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
Milestone 4: index structure and learned approximation — in progress
Milestone 4: chunks B1-B4 complete and validated countywide.
             B1 committed at 998c859. B2 (entry-extent sweep, verification-
             mode fork), B3a/B3b (Hilbert ordering, exact inflated-disk query,
             countywide agreement, inflation cost, box-vs-disk gate) and B4
             (recursive model index) are validated; commits pending.
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
1de25f5 Milestone 4: record B1 commit state, revise B2-B6 prompts
```

Synchronization status at the last check:

```text
HEAD == origin/master
ahead: 0
behind: 0
```

The local repository and GitHub remote are synchronized through commit
1de25f5 (HEAD == origin/master, ahead 0, behind 0, verified 2026-07-23).
That commit contains Milestone 4 B1 (998c859) and the B1 commit-state and
prompt revisions. B2's implementation is present in the working tree but
not yet committed; see section 21.

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

Measured on 2026-07-28:

```text
python -m pytest -q --ignore=tests/test_spatial_split.py
257 passed in 3.64s
```

Per module:

```text
tests/test_scoring.py             44
tests/test_sensitivity.py         38
tests/test_audit.py               38
tests/test_rmi.py                 47   (Milestone 4 B4)
tests/test_hilbert_inflation.py   13   (Milestone 4 B3b)
tests/test_water_benchmark.py     14   (Milestone 4 B2, +11 over B1)
tests/test_water_segment_split.py  5   (Milestone 4 B1)
pre-existing modules              61
```

**The `--ignore` flag is required and is not a Milestone 4 issue.**
`tests/test_spatial_split.py` imports `caprm.spatial_split`, which imports
`scipy.spatial.cKDTree`. scipy is not installed in the venv, so pytest aborts
during collection and runs zero tests. Both files are untracked (`??`) with no
commit history and postdate the 2026-07-16 repository inventory; they are
Phase C spatial-block-split work in progress. When Phase C begins, scipy must
be installed *and* declared in `requirements.txt` in the same change. Until
then the tracked suite is green at 210.

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
4. Hilbert + binary search  1D, ~1M segments            not started  control
5. Hilbert + RMI            1D, ~1M segments            not started  learned
6. + learned radius         seeds the search disk       not started  stretch
```

Implementation 3 (Segment BVH) is complete and validated countywide
(`water_distance_segment_bvh.cpp`): field-for-field agreement with the Python
reference on all 267,362 properties, maximum absolute error 4.658e-10 m. Not
yet committed. See section 21 for the measured result.

Supporting work:

```text
maximum segment length L measured          done  (B1a: L = 5,748.24 m)
segment splitting implemented              done  (distance-exact, cap 100 m)
entry-extent parameter swept               DONE  (B2, 25 m cap chosen)
grouping half of the extent axis           out of scope, documented
verification-mode A/B fork                 DONE  (B2)
disk-to-curve-range decomposition          not started
search-radius inflation characterized      not started
neural surrogate, spatial-block split      not started
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
B5. Port RMI inference to C++
```

B1 through B4 are complete and validated countywide. B1 is committed at
998c859. B2, B3a, B3b, and B4 are validated but not yet committed. The B1
result below is retained as the historical baseline; B2, B3a, B3b, and B4
follow it.

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

## Milestone 4 chunk B3a (validated on fixture, commit pending)

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

Not done in B3a (scoped to B3b): no countywide run; commit pending.

The B3a note that the geometric inflation ratio "aggregates to 0 on the sparse
fixture" was wrong in its attribution and is corrected in B3b below: the ratio
was 0 because its denominator is degenerate by construction, not because the
fixture is small.

## Milestone 4 chunk B3b (validated countywide 2026-07-28, commit pending)

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

## Milestone 4 chunk B4 (validated countywide 2026-07-28, commit pending)

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
model, so the artifact cannot live under `outputs/`. **OPEN: confirm with
`git check-ignore -v models/water_hilbert_rmi.bin` and, if it needs `-f`, add the
path to the tracked-despite-ignore list in section 4.**

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

**OPEN, recommended before commit:** `compare_python_cpp_water.py` was NOT run
against `cpp_nearest_water_hilbert_countywide_b4.csv`. B3b established
field-for-field agreement for (original, disk) and all nine counters reproduce
that run exactly, which is strong evidence — but the agreement harness has not
been run on this specific file and this document does not claim it has.

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

## Files, B2 (validated, commit pending)

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

## Next task — B5, port RMI inference to C++

B4 is complete. The model exists, its bound is exhaustive and verified on the
artifact as written to disk, and the seam it plugs into was proved
correctness-neutral and tested with `--seed zero` before the model existed.

B5 replaces one function. `--seed rmi` currently parses and errors; it becomes a
model loader plus the five-line inference recorded in the B4 subsection, and
nothing else changes.

```text
acceptance    --seed rmi output byte-identical to --seed binary on every column
              except the seed instrumentation, countywide
load-time     assert the model header's training-array sha256 against the array
              the index just built
              (9f118bfc923dbf1a062a13fb7c0a662901ab8fdebbb3fd7ed7e93a497aad02f0)
              assert the manifest's probe records, which is how the
              uint64->double rounding assumption becomes checked rather than
              inherited
window        the current path reads +/-64 entries around the seed and needs no
              bound at all. The stored-key bound is the academic deliverable;
              the domain bound is a diagnostic and at 69,543 is not a usable
              window. Do not build machinery as though either gates correctness.
measure       predicted-vs-actual error on the 267,362 real property keys.
              94.240% within +/-64 is an INDEX-key figure and does not carry
              over.
```

Open decision carried into B5: whether to clamp each occupied leaf's prediction
to that leaf's observed target range. It would collapse the domain bound to
roughly a leaf's span, provably, for one extra clamp and two more values per
leaf. It is a model change and needs a decision before the artifact layout moves
again.

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

> We are continuing CAPRM-Flood at Milestone 4, chunk B5. Read Nucleus sections
> 14b, 18.19, 18.20, 18.22 and 18.23, this document's sections 19b and 21
> including the B3b and B4 subsections, and `CAPRM_Flood_Roadmap.md` PHASE B
> before proposing anything.
>
> Confirm the commit recorded in this document's section 2 matches
> `git log -1 --oneline`. If it does not, say so before continuing — you are
> reading a stale copy.
>
> Milestones 1 through 3 are frozen. The exposure index is not under active
> work and must not be modified.
>
> B1 through B4 are complete and validated countywide. B4 trained a two-stage
> RMI over the 1,189,589 sorted Hilbert keys: 131,072 linear second-stage
> models, 4,194,400 bytes, an exhaustive per-model error bound, 6.323 mean
> last-mile probes against the binary-search control's 20.2376.
>
> B5 ports inference to C++ and changes ONE function. `--seed rmi` currently
> parses and errors; it becomes a model loader plus five lines of arithmetic.
> The exact distance kernel, the 1e-6 m tie tolerance, lexicographic
> tie-breaking on water_feature_id, the region predicate, and every emitted
> field do not change.
>
> Acceptance is byte-identical evidence to `--seed binary` on every column
> except the seed instrumentation, countywide. B3b proved that seam
> correctness-neutral and tested it with `--seed zero`, so any deviation is
> attributable to the model alone.
>
> Do not size a search window from either recorded bound before reading why.
> The query path currently reads +/-64 entries around the seed and needs no
> bound at all. The stored-key bound is the academic deliverable; the domain
> bound reaches 69,543 at the selected model and is a diagnostic, not a usable
> window. Neither gates correctness.
>
> Before proposing an end-to-end speedup, read the ceiling: the RMI replaces
> about 20 probes out of about 11,022 phase-2 segment checks per property, and
> B4 measured the saving at about 0.13 percent of counted query work for a
> model 44 percent the size of the key array.

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
maximum segment length, sweeps the entry-extent parameter that trades pruning
against search-radius inflation, orders segments along a Hilbert curve,
validates the resulting query path with a binary-search control that isolates
the contribution of learning from the contribution of dimensionality reduction,
trains a recursive model index, and benchmarks the result against an exact
baseline whose correctness is already proven field-by-field against an
independent implementation. As of B4 the ladder's first four rungs are
measured: segment granularity cut phase-2 work 7.28x and distance-exact
splitting cut admitted entries 546x, both classical; the 1D Hilbert reduction
cost 13.4 percent in phase-2 work; and the trained index cut seed probes 3.20x,
which is about 0.13 percent of counted query work because phase-1 admission was
already a rounding error. The equi-depth diagnostic locates the remaining model
error in the router rather than the leaves. Precipitation remains a gated
stretch goal behind that work.