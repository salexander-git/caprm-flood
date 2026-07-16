# CAPRM-Flood Roadmap — 2026-07-15

## Purpose

This document defines the ordered implementation roadmap for CAPRM-Flood from the current state on **July 15, 2026** through project completion.

It should be read together with:

```text
CAPRM_Flood_Project_Nucleus_2026-07-15.md
CAPRM_Flood_Current_Status.md
Capstone_Proposal.pdf
Professor_Milestone_Requirements.txt
```

This roadmap is intentionally implementation-focused. It identifies:

- major remaining work chunks;
- the order in which they should be completed;
- the technical goals of each chunk;
- key design decisions;
- validation gates;
- expected deliverables;
- dependencies between chunks.

The project should proceed by completing and validating one chunk at a time rather than opening several partially finished branches of work simultaneously.

---

# 1. Current Starting Point

As of July 15, 2026:

```text
Milestone 1: complete and validated
Milestone 2: complete and validated
Milestone 3: terrain evidence and preliminary exposure index implemented
Milestone 3: not yet frozen as complete
Milestone 4: not yet started as a dedicated implementation phase
```

Current Git commit:

```text
0dd85ab Add Milestone 3 terrain evidence and exposure scoring
```

Current countywide workload:

```text
267,362 unique property IDs
```

Current implemented evidence families:

```text
1. FEMA flood-hazard evidence
2. nearest-water / hydrography evidence
3. terrain / elevation evidence
```

Current derived layer:

```text
preliminary exposure index
```

Current next priority:

```text
finish Milestone 3 before adding the next major evidence family
```

---

# 2. Roadmap Overview

The remaining project should be completed in the following major phases:

```text
PHASE A — Finish Milestone 3
    A1. Reconstruct and audit current scoring behavior
    A2. Harden scoring methodology
    A3. Implement sensitivity analysis
    A4. Audit terrain and index evidence products
    A5. Regenerate and freeze final Milestone 3 artifacts
    A6. Complete Milestone 3 reproducibility/runbook documentation

PHASE B — Add precipitation evidence
    B1. Select and document authoritative precipitation source/method
    B2. Build precipitation ingestion/cache pipeline
    B3. Derive property-level precipitation evidence
    B4. Validate and manifest precipitation evidence
    B5. Integrate precipitation into the derived scoring layer

PHASE C — Final index stabilization
    C1. Revisit component normalization with all intended evidence families
    C2. Re-run sensitivity analysis
    C3. Evaluate dominance/correlation/redundancy
    C4. Freeze final exposure-index methodology
    C5. Regenerate countywide final index

PHASE D — Milestone 4 / final engineering hardening
    D1. End-to-end reproducibility audit
    D2. Performance and scaling audit
    D3. Validation consolidation
    D4. Repository and documentation cleanup
    D5. Final result summaries and figures
    D6. Freeze release-quality project state

PHASE E — Final academic deliverables
    E1. Final report
    E2. Final presentation/demo
    E3. Portfolio/GitHub polish
```

The exact academic labeling of Phases B–D may be aligned with the professor's milestone requirements once `Professor_Milestone_Requirements.txt` is finalized, but the technical order should remain approximately as shown.

---

# 3. PHASE A — Finish Milestone 3

Milestone 3 should end with a stable, validated terrain evidence product and a defensible preliminary multi-component relative exposure index.

The goal is not simply to confirm that a score can be computed. The goal is to make the scoring implementation explicit, testable, interpretable, and robust enough to support later expansion.

---

## A1. Reconstruct and Audit Current Scoring Behavior

### Goal

Establish the exact current behavior of the scoring implementation before changing it.

### Files to inspect

```text
python/caprm/scoring.py
python/scripts/build_exposure_index.py
tests/test_scoring.py
outputs/index/property_exposure_index_countywide.csv
outputs/validation/property_exposure_index_countywide_manifest.json
outputs/validation/milestone3_results_summary.md
```

### Required reconstruction

Document:

- each evidence input consumed;
- each component score produced;
- the normalization rule for each component;
- whether normalization is min-max, percentile-based, threshold-based, or otherwise;
- directionality of each component;
- clipping behavior;
- missing-value behavior;
- current weights;
- score range;
- final composite formula;
- ranking method;
- percentile method;
- deterministic tie behavior;
- manifest/provenance fields.

### Key design principle

Do not modify scoring until the current behavior has been completely reconstructed.

### Deliverable

A concise current-scoring specification, either:

```text
docs/scoring_methodology.md
```

or an equivalent canonical section in repository documentation.

### Status as of 2026-07-15

Reconstruction: **complete.** Current scoring behavior established from
`python/caprm/scoring.py` and confirmed against generated artifacts via
`python/scripts/summarize_scoring_inputs.py`. Measured findings recorded in
`CAPRM_Flood_Current_Status.md` §14 and §14b.

Deliverable `docs/scoring_methodology.md`: **outstanding.**

### Completion gate

Met when `docs/scoring_methodology.md` states the current formula unambiguously
and every claim in it traces to source code or a measured artifact.
---

## A2. Harden Scoring Methodology

### Goal

Make every score component defensible, explicit, and stable under reruns.

### Design questions

For each component:

1. What physical or exposure relationship is it intended to represent?
2. Does higher raw evidence imply higher or lower exposure?
3. What transformation converts raw evidence to a bounded score?
4. Is the transformation interpretable?
5. Does the transformation behave reasonably for extreme values?
6. Is the transformation dependent on the current study-area distribution?
7. How are missing values handled?
8. Does the score duplicate information already represented by another component?

### Preferred properties

The final component transforms should be:

- deterministic;
- monotonic where the physical relationship is assumed monotonic;
- explicit;
- easy to test;
- resistant to pathological outliers;
- documented in plain language;
- reversible enough to understand why a property received a score.

### Avoid

- hidden learned weights;
- opaque transformations without justification;
- arbitrary constants with no documented rationale;
- normalization rules that change silently between runs;
- silently imputing missing evidence;
- allowing one extreme component to dominate unintentionally.

### Deliverables

Potential code/document outputs:

```text
python/caprm/scoring.py
tests/test_scoring.py
docs/scoring_methodology.md
```
### Concrete decisions required, from measured A1 findings

**A2-1 — Unknown-zone guard.** `fema_component_score` enumerates X, AO, A, AE,
VE. All five occur; nothing else does. But an unenumerated zone would silently
score 0.0 — *below* zone X's 10.0 — inverting the intended ordering with no
error. A future NFHL vintage adding AH, AR, A99, D, or a 0.2%-annual-chance
zone would trigger this. Preferred fix: raise on an unrecognized matched zone
rather than extend the lookup speculatively. Fail loudly, do not guess.

**A2-2 — The `is_sfha` override is dead code.** `is_sfha & score < 80 → 90`
cannot fire: all 5,061 SFHA properties score ≥ 80 from zone alone. Decide
explicitly whether it is a deliberate safety net for zones that do not occur
here, or removable. Either way it needs a test, because right now it is
unreachable *and* unverified.

**A2-3 — Terrain sub-weights.** The 0.60/0.40 absolute/relative split is a
magic constant: not in DEFAULT_WEIGHTS, not validated, not in any manifest, not
tested. Must be exposed, justified, or both — **before A3**, or the sensitivity
analysis will hold an untested assumption fixed while declaring the index
stable.

**A2-4 — Slope.** Computed per property, stored, required by
TERRAIN_REQUIRED_COLUMNS, and never scored. Either give it a component or drop
it from the required set. Do not leave the score implying it uses terrain
steepness when it does not.

**A2-5 — Thread weights through the pipeline. Blocks A3.** `build_exposure_index`
accepts a `weights` argument, but the CLI has no `--weights` flag,
`summarize_exposure_index` hard-codes DEFAULT_WEIGHTS regardless of what ran,
the manifest records DEFAULT_WEIGHTS rather than the weights used, and
`scoring_policy_version` is constant. Harmless today because only defaults run.
Under A3 every alternative-weight scenario would emit artifacts claiming
0.40/0.35/0.25. This is a correctness bug the moment A3 starts.

**A2-6 — Component test coverage.** `water_component_score` and
`terrain_component_score` have **no tests at all** — directionality is entirely
unverified. FEMA tests cover only X/AE/VE. Nothing tests unmatched → 0.0, the
SFHA override, AO, A, monotonicity, determinism, or non-default weights.

### Completion gate

All component-scoring behavior must have unit tests covering:

- minimum/boundary cases;
- maximum/boundary cases;
- monotonic behavior;
- clipping;
- missing values;
- deterministic results.

---

## A3. Implement Sensitivity Analysis

### Goal

Determine how dependent property rankings are on component-weight assumptions.

This is the central methodological validation task for the current index.

### Core question

```text
If plausible component weights change, do the same properties remain relatively high or low exposure?
```

### Recommended baseline analysis

Define:

```text
baseline weight configuration
```

Then define a controlled family of alternative configurations.

At minimum, test:

```text
equal weighting
baseline weighting
one-component-emphasized scenarios
one-component-deemphasized scenarios
small perturbations around baseline
```

The exact number of scenarios should be large enough to reveal sensitivity without becoming an arbitrary combinatorial search.

### Metrics to compute

Recommended ranking-stability metrics include:

- Spearman rank correlation;
- top-decile overlap;
- top-5% overlap;
- median absolute percentile shift;
- maximum percentile shift;
- per-property rank variability;
- component contribution summaries.

Where useful, also inspect:

- properties whose ranks are highly unstable;
- properties whose ranks remain consistently high;
- properties whose ranks remain consistently low.

### Design decision

Use rank-based sensitivity metrics because the index is primarily interpreted as a **relative ranking**.

Raw score differences matter less than whether materially different weighting assumptions move properties substantially within the countywide ranking.

### Expected code

Likely new files:

```text
python/caprm/sensitivity.py
python/scripts/analyze_scoring_sensitivity.py
tests/test_sensitivity.py
```

Exact names may vary after inspecting current conventions.

### Expected outputs

Potential outputs:

```text
outputs/analysis/scoring_sensitivity_summary.csv
outputs/analysis/scoring_sensitivity_property_shifts.csv
outputs/validation/scoring_sensitivity_manifest.json
outputs/validation/scoring_sensitivity_summary.md
```

### Completion gate

Milestone 3 should explicitly characterize the current index as:

```text
stable
moderately sensitive
or highly sensitive
```

under the tested plausible weight configurations.

That conclusion must be supported by measured rank-stability results.

---

## A4. Audit Terrain and Index Evidence Products

### Goal

Confirm that the countywide products are structurally complete, internally consistent, and reproducible.

### Terrain audit

Check:

- total row count;
- unique property count;
- duplicate property IDs;
- missing property IDs;
- null elevation values;
- null local-mean values;
- null relative-elevation values;
- null slope values;
- value ranges;
- impossible or suspicious values;
- CRS metadata;
- sampling-radius consistency;
- source raster checksum;
- manifest consistency.

### Index audit

Check:

- total row count;
- unique property count;
- join completeness;
- missing component scores;
- missing final scores;
- final score range;
- percentile range;
- duplicate ranks/tie behavior;
- deterministic ordering;
- component-score ranges;
- contribution totals where applicable.

### Cross-product checks

Verify:

```text
countywide property workload
↕
FEMA/water evidence
↕
terrain evidence
↕
exposure index
```

The expected property population should be preserved unless an explicit exclusion policy exists.

### Deliverable

Add or extend automated validation helpers rather than relying entirely on manual inspection.

### Completion gate

All final Milestone 3 countywide products pass the agreed audit with no unexplained row loss, duplicate IDs, or invalid values.

### Additional audit items, from measured findings

- **Unify manifest schemas.** The flood evidence manifest uses
  `evidence_summary` / `output_csv`; terrain and index use `summary` / `output`.
  Either unify or document the divergence deliberately.
- **Refresh `inventory_repository.py`.** Its `EXPECTED_PATHS` list is stale: it
  expects `compare_python_cpp_dev.py` and `cpp/spatial_core/CMakeLists.txt`,
  which do not exist (the project builds C++ directly with g++), and contains no
  Milestone 3 paths. It would currently report false failures. This script
  already implements most of D4 — fix the list rather than writing a new tool.
- **Resolve empty directories.** `benchmarks/`, `docker/`, `data/sample/`, and
  `cpp/spatial_core/include/` are empty. Remove or populate.


---

## A5. Regenerate and Freeze Final Milestone 3 Artifacts

### Goal

Create one final reproducible Milestone 3 output set from the committed implementation.

### Sequence

After scoring and sensitivity methodology are finalized:

1. rerun terrain preparation if necessary;
2. regenerate countywide terrain evidence;
3. regenerate terrain manifest;
4. regenerate preliminary/final Milestone 3 exposure index;
5. regenerate index manifest;
6. run sensitivity analysis;
7. regenerate Milestone 3 summary;
8. rerun full tests;
9. record exact output statistics;
10. commit code/document changes;
11. push to GitHub.

### Final artifacts should include

```text
terrain evidence
terrain manifest
exposure index
index manifest
sensitivity outputs
sensitivity manifest
Milestone 3 summary
final test result
updated documentation
```

### Completion gate

Milestone 3 is frozen only when:

```text
code committed
tests passing
outputs regenerated
manifests current
sensitivity analysis complete
documentation current
GitHub synchronized
```

---

## A6. Complete Milestone 3 Reproducibility / Runbook Documentation

### Goal

Make Milestone 3 rerunnable without relying on chat history.

### Required content

Document:

- required external datasets;
- expected local paths;
- environment setup;
- dependency installation;
- exact script order;
- expected inputs;
- expected outputs;
- approximate runtime where useful;
- which outputs are intentionally ignored by Git;
- how to validate success;
- how to regenerate manifests;
- how to rerun the full test suite.

### Recommended file

```text
docs/milestone_3.md
```

or an equivalent current runbook.

### Completion gate

Another technically competent person should be able to reproduce the Milestone 3 pipeline using the repository and required source data without needing private conversation history.


### Additional documentation items, from repository inspection

- **`docs/data_sources.md` has no terrain section.** It documents FEMA, the
  county boundary, and hydrography with service URLs, vintages, cache paths, and
  limitations. The DEM's source, resolution, vintage, download path, and
  licensing are undocumented. A6 cannot close without this.
- **`docs/crs_policy.md` has no terrain section.** The file already requires that
  every new raster family document its native CRS, resampling policy, target CRS,
  units, and distortion. Terrain satisfies part of this in its manifest but has
  no entry in the policy document.
- **Correct `README.md`.** It states two evidence families, Milestone 2 complete,
  and 55 passing tests. Actual: three families, Milestone 3 implemented, 69 tests.
- **Fix the nucleus contradiction.** The repo tracks the superseded June 2
  nucleus PDF and does not contain the current canonical documents. Add the
  current set; remove or archive the stale PDF.
- **Regenerate environment capture.** `capture_environment.py` already implements
  this; its output is scoped `milestone_1_environment.json`. Needs a Milestone 3 run.
---

# 4. PHASE B — Add Precipitation Evidence

After Milestone 3 is frozen, add precipitation as the next evidence family.

This should be treated as a new source-family pipeline, not as a direct modification of existing FEMA/water/terrain evidence.

---

## B1. Select the Precipitation Source and Method

### Goal

Choose a defensible public precipitation-frequency dataset and define exactly what property-level evidence will be derived.

### Candidate direction

NOAA precipitation-frequency data is the expected starting point.

Before implementation, verify:

- current authoritative source;
- spatial resolution;
- available recurrence intervals;
- available durations;
- coordinate/reference system;
- access format;
- licensing/usage terms;
- geographic coverage;
- update/version metadata.

### Methodological decision

Choose evidence fields that have clear physical meaning.

Potential examples:

```text
24-hour precipitation depth for selected recurrence interval
1-hour precipitation depth for selected recurrence interval
multiple recurrence-interval depths
derived local precipitation severity indicator
```

Do not add many precipitation fields merely because they are available.

Select only fields that contribute meaningfully to exposure interpretation.

### Research question

Determine whether the best representation is:

- one selected design-storm depth;
- several recurrence intervals;
- a compact derived precipitation component.

### Completion gate

The chosen precipitation evidence definition is documented before ingestion code is written.

---

## B2. Build Precipitation Ingestion / Cache Pipeline

### Goal

Create a reproducible local source-data preparation stage.

### Requirements

The pipeline should capture:

- source URL or source identifier;
- retrieval date;
- source version/date if available;
- source checksum;
- CRS/spatial metadata;
- transformed/local cache path.

### Expected architecture

```text
authoritative precipitation source
    ↓
download/cache
    ↓
normalize spatial representation
    ↓
local reproducible artifact
```

### Completion gate

A deterministic cache/preparation step produces a documented local artifact with provenance metadata.

---

## B3. Derive Property-Level Precipitation Evidence

### Goal

Produce one row of precipitation evidence per countywide property.

### Key questions

The extraction method depends on the source format.

Possible approaches include:

- raster sampling;
- gridded interpolation;
- polygon/region lookup;
- point interpolation from published stations or grids.

The method must be selected based on the actual authoritative source structure.

### Output boundary

Create a separate evidence product:

```text
outputs/evidence/property_precipitation_evidence_countywide.csv
```

Potential manifest:

```text
outputs/validation/property_precipitation_evidence_countywide_manifest.json
```

### Completion gate

All expected properties have precipitation evidence or an explicitly documented missing-data status.

---

## B4. Validate Precipitation Evidence

### Goal

Establish confidence that property-level precipitation values were extracted correctly.

### Validation methods may include

- spot checks against authoritative source values;
- known-location comparisons;
- range checks;
- interpolation consistency checks;
- repeated deterministic runs;
- checksum/manifests;
- unit tests for extraction logic.

### Completion gate

The precipitation product has a validation story appropriate to its source and extraction method.

---

## B5. Integrate Precipitation Into the Derived Scoring Layer

### Goal

Add precipitation as a new component without mutating upstream evidence.

### Required work

- define precipitation score transform;
- define directionality;
- document normalization;
- update weights;
- update tests;
- regenerate index;
- rerun sensitivity analysis.

### Completion gate

The scoring layer can generate a full multi-source index using:

```text
FEMA
water proximity
terrain
precipitation
```

with explicit component contributions.

---

# 5. PHASE C — Final Index Stabilization

Once all intended evidence families are present, the index should be reconsidered as a whole.

This is the point at which the scoring methodology becomes a final project result rather than a preliminary implementation.

---

## C1. Revisit Component Normalization

### Goal

Ensure each evidence family contributes on a comparable and defensible scale.

Review:

- FEMA component;
- water-distance component;
- terrain component(s);
- precipitation component.

Questions:

- Are components bounded consistently?
- Are transformations monotonic?
- Are thresholds justified?
- Does one component have excessive variance?
- Does one component dominate the composite mechanically?

---

## C2. Re-run Full Sensitivity Analysis

Repeat the sensitivity framework with the final evidence set.

Report:

- baseline versus alternatives;
- rank correlation;
- top-decile stability;
- unstable properties;
- dominant components.

This becomes part of the final methodological defense of the index.

---

## C3. Evaluate Correlation and Redundancy

### Goal

Determine whether multiple components are measuring nearly the same spatial phenomenon.

Examples to investigate:

- FEMA zone versus water proximity;
- elevation versus relative elevation;
- terrain slope versus relative elevation;
- precipitation variables at multiple durations/recurrence intervals.

### Possible analyses

- Pearson correlation where appropriate;
- Spearman correlation;
- pairwise plots;
- component contribution distributions.

### Design principle

Do not automatically remove correlated features.

Use correlation analysis to understand redundancy and avoid unintentionally double-weighting the same underlying signal.

---

## C4. Freeze Final Exposure-Index Methodology

### Required final specification

Document:

- evidence fields used;
- transforms;
- normalization;
- missing-value policy;
- component weights;
- composite formula;
- percentile/ranking definition;
- tie behavior;
- study-area dependence;
- sensitivity findings.

### Completion gate

The index methodology is stable enough that later work focuses on reporting and validation rather than redesign.

---

## C5. Regenerate Final Countywide Index

Produce the final countywide property-level derived index.

Expected product:

```text
outputs/index/property_exposure_index_countywide.csv
```

The final manifest should record:

- exact evidence inputs;
- checksums;
- scoring configuration;
- code/version identifier;
- row counts;
- timestamp;
- summary statistics.

---

# 6. PHASE D — Milestone 4 / Final Engineering Hardening

The final engineering phase should consolidate the project as a reproducible, reviewable technical system.

---

## D1. End-to-End Reproducibility Audit

### Goal

Verify that the project can be reconstructed from source data and repository code.

Audit:

```text
environment
data acquisition
property workload
FEMA processing
hydrography processing
C++ validation
terrain preparation
terrain extraction
precipitation extraction
scoring
sensitivity analysis
final summaries
```

### Deliverable

A single high-level runbook/README path from raw inputs to final outputs.

---

## D2. Performance and Scaling Audit

### Goal

Consolidate the project's performance claims.

Review existing:

- brute-force nearest-water timings;
- indexed nearest-water timings;
- workload scaling results.

Where useful, add:

- final countywide runtimes;
- memory considerations;
- Python versus C++ kernel comparisons;
- indexed versus brute-force comparison summaries.

Do not create artificial benchmarks that are not relevant to the actual architecture.

---

## D3. Validation Consolidation

Create one final validation narrative covering:

```text
FEMA
water
terrain
precipitation
scoring
sensitivity
```

Each evidence family should clearly state:

- what was validated;
- how it was validated;
- what tolerance was used;
- what remains a limitation.

---

## D4. Repository Cleanup

Review:

- tracked legacy raw data;
- tracked generated outputs;
- `.gitignore`;
- temporary files;
- duplicate documentation;
- stale scripts;
- naming inconsistencies.

Do not remove historical artifacts that are still needed for milestone reproducibility without a deliberate migration plan.

---

## D5. Final Result Summaries and Figures

Generate only figures/tables that directly support the final report and presentation.

Likely useful outputs include:

- system architecture diagram;
- Python/C++ validation summary;
- indexed-versus-brute-force benchmark;
- countywide score distribution;
- map of relative exposure;
- sensitivity/rank-stability figure;
- representative property evidence breakdown.

Avoid decorative plots that do not support a specific claim.

---

## D6. Freeze Release-Quality Project State

Before final academic submission:

```text
full tests pass
repository clean
GitHub synchronized
final code committed
final methodology documented
final outputs regenerated
final manifests current
final validation summary complete
```

Create a final tagged release only if useful and time permits.

---

# 7. PHASE E — Final Academic Deliverables

This phase begins only after the implementation is stable enough that report-writing will not be repeatedly invalidated by code changes.

---

## E1. Final Report

The report should explain:

- motivation;
- related work;
- system architecture;
- data sources;
- CRS policy;
- Python/C++ design;
- evidence extraction;
- validation;
- performance;
- terrain methodology;
- precipitation methodology;
- scoring methodology;
- sensitivity analysis;
- results;
- limitations;
- future work.

The report should preserve a clear distinction between:

```text
measured geospatial evidence
derived component scores
composite relative index
```

---

## E2. Final Presentation / Demo

The presentation should emphasize:

- the engineering problem;
- multi-source geospatial pipeline;
- Python/C++ independent validation;
- scaling to 267,362 properties;
- terrain and precipitation expansion;
- final scoring logic;
- sensitivity results;
- reproducibility.

The strongest demo is one where a single property can be traced from coordinates through source evidence to final component contributions and countywide rank.

---

## E3. Portfolio / GitHub Polish

After academic completion:

- update README;
- add architecture diagram;
- document setup;
- document sample run;
- add representative outputs;
- clarify data-download requirements;
- remove stale private/course-only clutter where appropriate;
- make the repository employer-readable.

If the repository will become public, review all tracked files first.

---

# 8. Major Design Decisions to Preserve

The following decisions should remain stable unless there is a strong technical reason to revisit them.

## Evidence/source separation

Keep:

```text
FEMA/water evidence
terrain evidence
precipitation evidence
derived index
```

as distinct logical products.

## Canonical identifiers

Use stable source identifiers rather than row indices or geometry order.

## Projected CRS for metric operations

Use:

```text
EPSG:26918
```

for Monroe County metric distance/neighborhood operations unless a later method has a clearly documented need for another CRS.

## Independent Python/C++ validation

Preserve independent implementations for the spatial kernels already validated.

## Stable regression fixture

Do not regenerate the 1,000-property fixture casually.

## Deterministic behavior

Preserve deterministic ordering and tie resolution.

## Explicit scoring

Keep component transforms and weights transparent.

## Validation before scale

Validate on stable smaller workloads before trusting countywide outputs.

## Large-data Git discipline

Do not add full countywide rasters or large generated outputs to normal Git tracking merely to make them visible to an AI assistant.

---

# 9. Areas Where New Research May Be Worthwhile

The project should not browse for novelty by default, but several remaining design decisions may benefit from targeted review of current authoritative methods.

## Precipitation methodology

Research may be warranted for:

- current NOAA precipitation-frequency products;
- best practice for property-level extraction;
- appropriate recurrence intervals and durations.

## Terrain-derived flood proxies

Research may be warranted for:

- relative elevation formulations;
- local slope derivation;
- HAND or related terrain-context metrics;
- whether a more hydrologically meaningful terrain feature is feasible within scope.

Any addition should be judged against implementation cost and validation burden.

## Multi-criteria scoring

Research may be warranted for:

- transparent weighted-index design;
- normalization strategies;
- robustness/sensitivity analysis;
- rank stability.

The project should favor interpretable, defensible methods over sophisticated methods that cannot be explained or validated.

---

# 10. Completion Criteria by Phase

## Milestone 3 complete when

```text
current scoring behavior documented
scoring methodology hardened
sensitivity analysis implemented
terrain/index audit passed
final Milestone 3 artifacts regenerated
full test suite passes
Milestone 3 runbook/documentation complete
GitHub synchronized
```

## Precipitation phase complete when

```text
authoritative source selected
pipeline implemented
countywide evidence generated
validation complete
manifest complete
scoring integration complete
tests pass
```

## Final index complete when

```text
all intended evidence families integrated
normalization reviewed
correlation/redundancy analyzed
sensitivity analysis rerun
final weights/methodology frozen
countywide final index regenerated
```

## Final engineering phase complete when

```text
end-to-end runbook complete
validation consolidated
performance claims supported
repository cleaned
final outputs/manifests regenerated
tests pass
GitHub synchronized
```

## Project complete when

```text
technical implementation frozen
final report complete
final presentation complete
repository/portfolio state polished
```

---

# 11. Immediate Next Conversation

The next implementation conversation should focus only on:

```text
A1. Reconstruct and audit current scoring behavior
```

Suggested prompt:

> We are continuing CAPRM-Flood at Milestone 3. Read the current nucleus, current-status document, roadmap, and repository.
>
> Do not change code yet.
>
> Inspect:
>
> - `python/caprm/scoring.py`
> - `python/scripts/build_exposure_index.py`
> - `tests/test_scoring.py`
>
> Reconstruct the exact current scoring behavior, including every component, raw input, normalization rule, directionality, weight, missing-value policy, clipping rule, composite formula, percentile/ranking behavior, and deterministic tie behavior.
>
> Then identify which parts are already defensible and which require methodological hardening before sensitivity analysis.
>
> Preserve the existing evidence-product boundaries and do not redesign unrelated architecture.

---

# 12. Canonical Roadmap Summary

CAPRM-Flood should now finish Milestone 3 by documenting and hardening the current scoring implementation, implementing rank-based sensitivity analysis, auditing countywide terrain/index products, regenerating final milestone artifacts, and completing reproducibility documentation. After Milestone 3 is frozen, the project should add precipitation as a separate evidence family, validate it independently, and integrate it into the derived scoring layer. The complete evidence set should then be used to stabilize the final relative exposure-index methodology through normalization review, correlation/redundancy analysis, and a second full sensitivity analysis. The final engineering phase should consolidate reproducibility, validation, performance, repository hygiene, and final artifacts before report and presentation work becomes the primary focus.
