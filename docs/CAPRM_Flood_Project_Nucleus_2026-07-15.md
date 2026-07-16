# CAPRM-Flood Project Nucleus — 2026-07-15

## Purpose of This Document

This document is the canonical context-restoration source for **CAPRM-Flood** as of **July 15, 2026**. It exists so that a new AI assistant, collaborator, reviewer, or future project conversation can reconstruct the project's purpose, architecture, technical history, standards, and current implementation state without relying on stale proposal-era assumptions or raw chat transcripts.

This nucleus should be treated as the durable description of the project. More time-sensitive operational detail will be maintained separately in:

- `CAPRM_Flood_Current_Status.md`
- `CAPRM_Flood_Roadmap.md`
- `Capstone_Proposal.pdf`
- `Professor_Milestone_Requirements.txt`

Where those documents differ in role:

- **This nucleus** defines what CAPRM-Flood fundamentally is, why it exists, how it is architected, and which engineering principles govern it.
- **Current Status** records the exact present implementation state, latest outputs, test status, and immediate next task.
- **Roadmap** records remaining work in ordered implementation chunks.
- **Capstone Proposal** preserves the original submitted academic framing.
- **Professor Milestone Requirements** preserves the external course requirements that constrain deliverables.

This document supersedes the earlier project nucleus dated June 2, 2026 wherever the earlier document describes the project as still being in the Milestone 1 technical-spike phase.

---

# 1. Project Identity

**Project title:**  
**CAPRM-Flood: A Reproducible C++/Python Framework for Property-Level Flood Exposure Indexing**

**Student:** Sterling Alexander  
**Program:** M.S. Computer Science, Rochester Institute of Technology  
**Course:** CSCI 788 Computer Science MS Project, Summer 2026  
**Advisor:** Professor Minseok Kwon  
**Primary study area:** Monroe County / Rochester, New York

CAPRM-Flood is a **reproducible geospatial evidence-extraction and relative exposure-indexing system** for large batches of property locations.

Its central technical task is to take a stable set of property identifiers and coordinates, join those locations to multiple public geospatial hazard datasets, derive structured property-level evidence, validate that evidence against independent or trusted reference implementations, and combine selected evidence into an interpretable relative flood-exposure index.

The project is best understood as a **spatial data-processing system with a flood-exposure application**.

The core flow is:

```text
property locations
    ↓
public hazard and terrain datasets
    ↓
validated spatial feature extraction
    ↓
source-family evidence tables
    ↓
normalized component scores
    ↓
transparent relative exposure index
    ↓
property-level evidence, score, and regional ranking
```

The flood-exposure index is the application-layer output. The main computer science and engineering contribution is the system that makes the evidence behind that index **correct, deterministic, reproducible, benchmarkable, inspectable, and traceable to source data**.

---

# 2. Core Problem

Given a large set of property locations in a selected region and a collection of public flood-related geospatial datasets, CAPRM-Flood asks:

> Can a transparent C++/Python processing system derive defensible property-level flood-exposure evidence efficiently and reproducibly, validate the spatial computations across implementations, and convert those evidence fields into an interpretable relative exposure ranking?

The project addresses this as a batch-processing and evidence-engineering problem.

For each property, the system is designed to answer questions such as:

- Is the property point located inside a mapped FEMA flood-hazard polygon?
- What FEMA flood-zone attributes apply to the location?
- How far is the property from the nearest mapped hydrographic feature?
- What is the local ground elevation?
- How does the property's elevation compare with its nearby terrain?
- What local slope is represented by the elevation surface around the property?
- Eventually, what precipitation-frequency evidence applies at or near the property?
- How can these heterogeneous evidence fields be normalized into explicit component scores?
- How stable is the final relative ranking when scoring assumptions or weights change?

The objective is not merely to produce a number. The objective is to produce a number whose underlying evidence can be inspected and defended.

---

# 3. Practical System Behavior

At minimum, CAPRM-Flood accepts property records containing:

```text
property_id
latitude
longitude
```

The property identifier must be stable and unique within the workload. It exists to preserve traceability between input records and all downstream evidence and scoring outputs.

The system then performs source-specific spatial processing.

Current implemented evidence families are:

1. **FEMA flood-hazard evidence**
2. **Hydrography / nearest-water evidence**
3. **Terrain / elevation evidence**

A preliminary derived exposure-index layer has also been implemented.

Planned later work adds precipitation evidence and then revisits the scoring/index design with a fuller evidence set.

The architecture intentionally keeps source-family evidence products separate from derived scoring products.

Conceptually:

```text
property workload
    │
    ├── FEMA NFHL processing
    │       └── FEMA evidence
    │
    ├── USGS hydrography processing
    │       └── nearest-water evidence
    │
    ├── USGS elevation/terrain processing
    │       └── terrain evidence
    │
    └── future precipitation processing
            └── precipitation evidence

validated evidence products
    ↓
derived scoring/index pipeline
    ↓
relative exposure index + percentile ranking
```

This separation matters because evidence extraction and scoring are different responsibilities. A source-family evidence table should remain valid even if the project later changes component normalization, weights, or index methodology.

---

# 4. Study Region and Property Workload

The initial and current case study is **Monroe County / Rochester, New York**.

The property workload is based on public parcel/property point data and is represented internally as property identifiers plus coordinates.

The system has progressed from a fixed validation fixture to a full countywide workload:

- an immutable **1,000-property fixture** for regression and Python/C++ comparison;
- larger deterministic workloads for scaling and validation;
- a countywide workload containing **267,362 unique property IDs**.

The 1,000-property fixture is intentionally preserved as a stable regression artifact. It should not be casually regenerated or replaced because its value comes from providing a repeatable, immutable comparison set across code changes.

---

# 5. Data Sources and Evidence Families

## 5.1 Property Locations

Primary role:

- provide the property identifier and coordinate input to which all hazard evidence is attached.

The property record is the stable join key across downstream products.

## 5.2 FEMA National Flood Hazard Layer

Purpose:

- determine flood-zone polygon membership;
- attach mapped FEMA zone information;
- identify Special Flood Hazard Area status;
- preserve a canonical FEMA source-feature identifier for traceability.

Core evidence includes fields such as:

```text
property_id
fema_zone
sfha_flag
canonical FEMA feature identifier
```

The project standardized on the FEMA field `FLD_AR_ID` as the canonical flood-area feature identifier rather than relying on an unstable internal geometry index.

### Observed zone domain

The countywide FEMA evidence contains exactly five mapped zone values plus
unmatched properties:

```text
X    262,297   not SFHA
AE     4,226   SFHA
A        408   SFHA
AO       388   SFHA
VE        39   SFHA
unmatched  4   no zone
```

SFHA status is perfectly determined by zone in this dataset: every matched
non-X zone is SFHA, and X never is. `is_sfha` therefore carries no information
beyond `fema_zone` for the current workload. That relationship is a property of
this data, not a guarantee of the FEMA schema, and should not be assumed to hold
for another county or a future NFHL vintage.

## 5.3 USGS Hydrography / 3D Hydrography Program

Purpose:

- derive the distance from each property to the nearest mapped water feature;
- preserve the identity and classification of that nearest feature;
- provide a spatially interpretable water-proximity exposure proxy.

The current implementation uses projected coordinates for metric distance computation and treats nearest-water evidence as its own validated source-family product.

Core evidence includes the property identifier, nearest-water distance in meters, canonical nearest-feature identity, and feature classification/type information where available.

## 5.4 USGS Elevation / Terrain

Purpose:

- add a raster-derived evidence family that captures the property's elevation and local terrain context.

The implemented terrain pipeline prepares a projected digital elevation model and derives property-level fields including:

```text
property_id
terrain_elevation_m
terrain_local_mean_elevation_m
terrain_relative_elevation_m
terrain_slope_degrees
terrain_sample_radius_m
terrain_crs
```

The terrain evidence product is accompanied by provenance information such as source identity/checksum and CRS information in validation metadata/manifests.

The current countywide terrain run covers **267,362 unique properties** and produced **0 missing slope values**.

Observed countywide elevation values in the current output span approximately:

```text
75.000 m to 296.309 m
```

These values are evidence fields, not direct calibrated flood probabilities.

## 5.5 Precipitation

Precipitation is part of the intended evidence architecture but is **not yet the completed fourth source family** as of July 15, 2026.

The intended role is to add an extreme-precipitation or precipitation-frequency indicator from a defensible public source such as NOAA precipitation-frequency data.

Precipitation is expected to be implemented after the current Milestone 3 terrain/index work is completed and stabilized.

---

# 6. Python and C++ Architecture

CAPRM-Flood deliberately uses both Python and C++.

The languages have different responsibilities rather than existing merely for language diversity.

## Python responsibilities

Python is the orchestration, reference, preprocessing, validation, and derived-analysis layer.

It is responsible for work such as:

- reading and normalizing geospatial datasets;
- enforcing CRS policy;
- building deterministic property workloads;
- constructing trusted/reference spatial computations;
- exporting C++ inputs;
- reading and comparing C++ outputs;
- generating validation summaries and manifests;
- preparing terrain rasters;
- sampling raster evidence;
- deriving terrain metrics;
- constructing the preliminary exposure index;
- generating summary artifacts;
- running the automated test suite.

Key Python packages/modules include project code under:

```text
python/caprm/
python/scripts/
```

The Python layer is also where reproducibility metadata, provenance capture, and cross-implementation validation are coordinated.

## C++ responsibilities

C++ performs meaningful spatial computation independently of the Python reference path.

Current C++ work includes:

- FEMA point-in-polygon lookup;
- nearest-water distance computation;
- brute-force nearest-feature search for correctness reference;
- indexed nearest-feature search for performance comparison.

The C++ component is not intended to be a decorative wrapper around Python. It exists to demonstrate independent spatial implementation, correctness comparison, indexing/performance tradeoffs, and systems-level reasoning.

The central design principle is:

> Python provides a trusted reference and orchestration layer; C++ independently performs selected spatial kernels whose correctness and performance can be measured against the Python implementation.

---

# 7. Coordinate Reference System Policy

CRS handling is a first-class engineering requirement.

The detailed canonical policy lives in the repository at `docs/crs_policy.md`.
This section records the durable principle; that file records the operational rules.

## Principle

The CRS must match the operation. Topological membership and metric distance
have different requirements, and the project uses different CRSs for each.

## CRS roles

| Purpose | CRS | Use |
|---|---|---|
| Source / reporting | EPSG:4326 | Property longitude/latitude; cached service geometry |
| FEMA topology | EPSG:3857 | Point-in-polygon membership only |
| Metric distance | EPSG:26918 | Nearest-water distance; study-area buffer |
| Terrain raster | EPSG:26918 | Projected DEM sampling, local windows, slope |
| FEMA source | EPSG:4269 | Observed CRS of NFHL input before transformation |

## Why FEMA uses EPSG:3857

FEMA membership asks whether a point lies inside a polygon. That question is
topological and does not measure anything, so EPSG:3857's well-known distance
distortion is irrelevant to it. The validated path is retained deliberately.

EPSG:3857 coordinate differences are never interpreted as meters. A distance
result must never originate from the FEMA projection.

## Why metric work uses EPSG:26918

NAD83 / UTM zone 18N is locally appropriate for Monroe County and expresses
planar distance in meters. Properties and hydrography are both transformed to
it before any distance calculation. The county polygon is projected to it
before the 20 km buffer, because buffering in degrees would be meaningless.

## C++ boundary

C++ performs no CRS discovery or transformation. Python exports coordinates
already projected for one CRS per run and records that CRS in manifests and
output rows: EPSG:3857 for FEMA inputs, EPSG:26918 for water inputs.

## Enforcement

CRS metadata is checked, normalized, propagated, and recorded. Mixing
projections silently, mislabeling a CRS, or computing distance in degrees is
a hard error, not a warning. `caprm.scoring` and `caprm.terrain` both raise
when an input's declared CRS is not EPSG:26918.

## New evidence families

Any future raster or interpolated family must document its own native CRS,
resampling or interpolation policy, target CRS, units, and distortion
implications. It must not inherit the FEMA EPSG:3857 path merely because that
path exists.

# 8. Determinism and Traceability

A central project standard is that identical validated inputs and configurations should produce identical logical outputs.

Deterministic behavior includes:

- stable property identifiers;
- stable workload ordering;
- deterministic fixture generation/materialization;
- canonical source-feature identifiers;
- explicit tie-breaking rules;
- explicit CRS transformations;
- stable output schemas;
- source hashes/checksums where appropriate;
- manifests describing input and output artifacts.

Where multiple spatial features can satisfy a relationship, the system must define deterministic resolution behavior rather than depending on library iteration order.

For nearest-feature ties, canonical feature identifiers are used to make resolution reproducible.

This determinism is important for:

- regression testing;
- Python/C++ comparison;
- reproducible milestone results;
- debugging disagreements;
- trustworthy future reruns.

---

# 9. Evidence-Product Architecture

CAPRM-Flood uses a **source-family evidence architecture**.

The project should preserve distinct products for distinct evidence sources.

Current conceptual product boundaries are:

```text
FEMA / water evidence
terrain evidence
future precipitation evidence
derived exposure index
```

A validated upstream evidence table should not be overwritten merely because a new evidence family is added.

For example, adding terrain evidence does not invalidate or replace the validated FEMA/water evidence product.

Likewise, the exposure index is a **derived product**. It may join or consume upstream evidence, but changes in scoring methodology should not mutate the underlying evidence records.

This architecture allows:

- independent source validation;
- easier provenance tracking;
- component-specific debugging;
- future rescoring without redoing all geospatial extraction;
- cleaner schema evolution;
- clearer separation between observed/derived evidence and modeling assumptions.

---

# 10. Validation Philosophy

The project treats correctness claims as evidence-dependent.

A claim is not considered earned merely because the code runs.

Validation methods include:

- trusted Python reference implementations;
- independent C++ implementations;
- exact or tolerance-based field comparison;
- deterministic repeated runs;
- stable regression fixtures;
- explicit disagreement analysis;
- unit tests;
- integration-oriented scripts;
- manifest/checksum comparison;
- scaling tests and benchmarks where applicable.

The most important rule is:

> When two implementations disagree, the disagreement must be explained. It should not be hidden by looser wording or silently accepted.

The project also distinguishes validation appropriate to different computation types.

Examples:

- polygon membership can often be compared exactly;
- floating-point distance computations may require an explicit numeric tolerance;
- raster-derived terrain values require source/CRS provenance and targeted tests around sampling and derived calculations.

---

# 11. Reproducibility Standard

CAPRM-Flood is intended to be rerunnable and auditable.

Reproducibility mechanisms already used across the project include:

- a structured Git repository;
- configuration files for workload variants;
- scripted preprocessing;
- deterministic workload generation;
- source and artifact checksums;
- JSON manifests;
- environment capture;
- validation summaries;
- automated tests;
- CLI-oriented Python scripts;
- preserved regression fixtures.

Large raw datasets, derived rasters, and countywide generated outputs are generally not appropriate for normal Git tracking. The repository instead preserves code, small fixtures, configuration, documentation, and validation metadata sufficient to describe and reproduce the workflow when the required source data is available.

The repository should continue moving toward a clean documented end-to-end runbook so that another technically competent person can reconstruct the workflow without relying on private chat history.

---

# 12. Milestone 1 — FEMA Spatial Validation Foundation

Milestone 1 established the minimum viable spatial feature-extraction system.

It implemented and validated:

- repository structure;
- real property-coordinate input;
- FEMA NFHL polygon ingestion;
- CRS checking and normalization;
- Python FEMA point-in-polygon baseline;
- independent C++ point-in-polygon implementation;
- projected/exported C++ fixtures;
- Python/C++ comparison tooling;
- deterministic output and validation artifacts;
- a stable 1,000-property regression fixture.

The completed validation achieved:

```text
1,000 / 1,000 property agreement
```

across the validated FEMA comparison fields, with no missing property results in the fixture.

Milestone 1 also hardened the original prototype by preserving the fixture, recording hashes/manifests, standardizing canonical FEMA feature identity using `FLD_AR_ID`, and adding tests and reproducibility scripts.

The lasting architectural contribution of Milestone 1 is not simply FEMA lookup. It is the project's validation pattern:

```text
trusted Python computation
    ↕
independent C++ computation
    ↓
explicit agreement analysis
    ↓
preserved validation artifact
```

That pattern became the basis for later spatial kernels.

---

# 13. Milestone 2 — Nearest-Water Evidence and Countywide Scaling

Milestone 2 extended the project from polygon membership to nearest-feature spatial analysis.

It added:

- USGS hydrography ingestion;
- hydrography caching;
- nearest-water feature extraction;
- projected metric distance in EPSG:26918;
- Python spatial-index reference computation using Shapely/STRtree;
- C++ brute-force nearest-water computation;
- C++ indexed nearest-water computation;
- deterministic nearest-feature identity and tie resolution;
- benchmark tooling;
- countywide property workload materialization;
- integrated FEMA + water evidence;
- validation manifests and summaries.

The brute-force C++ implementation serves an important correctness role. The indexed C++ implementation exists to evaluate the performance benefit of spatial indexing while preserving agreement with the reference behavior.

Validation and scaling work progressed through deterministic workloads at approximately:

```text
1K properties
10K properties
100K properties
267,362 countywide properties
```

By the end of Milestone 2, CAPRM-Flood had become a countywide, multi-source spatial evidence system rather than a small FEMA-only prototype.

The validated Milestone 2 FEMA/water evidence is a preserved upstream product and should not be overwritten by Milestone 3 terrain or scoring outputs.

---

# 14. Milestone 3 — Terrain Evidence and Preliminary Exposure Index

Milestone 3 introduces the third implemented evidence family: raster-derived terrain.

Current Milestone 3 implementation includes:

```text
python/caprm/terrain.py
python/caprm/scoring.py

python/scripts/prepare_terrain_raster.py
python/scripts/build_terrain_evidence.py
python/scripts/build_exposure_index.py
python/scripts/summarize_milestone3_results.py

tests/test_terrain.py
tests/test_scoring.py
```

The implementation was committed to Git at:

```text
0dd85ab Add Milestone 3 terrain evidence and exposure scoring
```

and pushed to the GitHub repository's `master` branch on July 15, 2026.

Current generated terrain/index artifacts include:

```text
data/raw/terrain/source_dem/monroe_3dep_13arcsec.tif
data/raw/terrain/monroe_dem_utm18.tif

outputs/evidence/property_terrain_evidence_countywide.csv
outputs/validation/property_terrain_evidence_countywide_manifest.json

outputs/index/property_exposure_index_countywide.csv
outputs/validation/property_exposure_index_countywide_manifest.json

outputs/validation/milestone3_results_summary.md
```

These large data/output paths are runtime artifacts rather than ordinary Git-tracked source files.

The current countywide terrain and preliminary index products contain:

```text
267,362 unique property IDs
0 missing slope values
terrain elevation range: approximately 75.000–296.309 m
preliminary exposure index range: approximately 7.915–99.929
preliminary exposure index mean: approximately 34.632
preliminary exposure index median: approximately 33.728
```

The full automated test suite passed after the terrain and preliminary scoring implementation.

Milestone 3 is not yet considered fully closed merely because these outputs exist. Remaining work includes hardening the scoring methodology, sensitivity analysis, reproducibility cleanup, final regeneration/audit of milestone artifacts, and documentation/runbook work.

Those remaining tasks belong in `CAPRM_Flood_Roadmap.md` and `CAPRM_Flood_Current_Status.md`, rather than being expanded exhaustively here.

---

# 15. Terrain Design

The terrain pipeline converts a source DEM into a projected raster appropriate for metric neighborhood operations.

The terrain stage then derives property-level raster evidence that includes:

- elevation at the property;
- local mean elevation around the property;
- relative elevation compared with the local neighborhood;
- slope;
- sampling-radius metadata;
- CRS/provenance metadata.

The design intentionally goes beyond a single elevation lookup because absolute elevation alone does not fully describe local topographic context.

At the same time, the project should avoid claiming that these terrain fields by themselves represent modeled flood depth, hydraulic connectivity, or hydrologic inundation.

The implemented terrain metrics are transparent physical-context features that can be inspected and scored.

Future terrain sophistication should only be added if it materially improves defensibility and remains feasible within the capstone schedule.

---

# 16. Preliminary Exposure Index

The project includes a preliminary deterministic exposure-index implementation in:

```text
python/caprm/scoring.py
python/scripts/build_exposure_index.py
```

The conceptual scoring pipeline is:

```text
validated evidence
    ↓
component normalization
    ↓
explicit component weighting
    ↓
composite relative exposure index
    ↓
countywide percentile/rank context
```

The scoring layer is intentionally downstream from evidence extraction.

Its main design requirements are:

- component calculations must be explicit;
- weights must be explicit;
- assumptions must be inspectable;
- output must retain enough evidence to explain why a property received a score;
- scoring changes must not alter the upstream source evidence;
- rankings must be described as relative to the selected study region;
- sensitivity analysis must test how dependent the rankings are on weighting assumptions.

The current index should be treated as **preliminary** until the remaining Milestone 3 sensitivity and scoring-policy work is complete.

The project should not present one weighting configuration as objectively true merely because it produces a clean ranking.

## Known properties of the current preliminary implementation

Recorded here because they are durable facts about the design, not transient status:

- The index consumes FEMA zone/SFHA/match, nearest-water distance, terrain
  elevation, and terrain relative elevation. **Slope is extracted and stored as
  evidence but does not enter any score.**
- The terrain component contains internal sub-weights (0.60 absolute elevation,
  0.40 relative elevation) that are separate from the three top-level component
  weights and are not currently exposed as configuration.
- The FEMA component is absolute and threshold-based. The water and terrain
  components are percentile ranks over the supplied workload, so they are
  distribution-dependent by construction: scoring a subset yields different
  scores for the same property. The index is meaningful only for the full
  countywide workload.
- Because percentile components have a mean fixed near 50 by construction, the
  countywide mean of the composite is determined almost entirely by the FEMA
  component.

---

# 17. Interpretation of the Index

CAPRM-Flood's strongest positive framing is:

> CAPRM-Flood is a reproducible C++/Python geospatial evidence-extraction framework for large-batch property-to-hazard spatial joins, demonstrated through a transparent property-level relative flood-exposure indexing workload.

The index is intended to summarize selected public geospatial exposure indicators in an interpretable way.

It is useful for:

- property-level exposure screening;
- research and exploratory analysis;
- comparing properties within the study region;
- portfolio-level exploration;
- validating and organizing public geospatial hazard evidence;
- creating structured features for possible downstream modeling;
- demonstrating reproducible spatial systems engineering.

A brief scope boundary is necessary for accurate interpretation:

> CAPRM-Flood does not currently claim calibrated flood probability, expected financial loss, insurance pricing, or actuarial-grade risk. Its index is a transparent relative exposure summary built from explicit public-data evidence and scoring assumptions.

This limitation should be stated clearly when relevant, but it should not dominate the description of the project.

---

# 18. Key Engineering Decisions and Why They Matter

## 18.1 Preserve evidence separately from scores

Reason:

Scoring methodology can change. Source evidence should remain stable and reusable.

## 18.2 Use canonical source identifiers

Reason:

Library row numbers or geometry positions are not durable identifiers. Canonical IDs improve reproducibility, provenance, and deterministic tie handling.

## 18.3 Use projected CRS for metric distance

Reason:

Distance in longitude/latitude degrees is not an acceptable substitute for meter-based spatial measurement.

## 18.4 Maintain an independent C++ path

Reason:

The C++ component must demonstrate meaningful computational work and enable correctness/performance comparison rather than acting as a thin wrapper around Python.

## 18.5 Keep a stable regression fixture

Reason:

A fixed 1,000-property sample allows later code changes to be checked against known validated behavior.

## 18.6 Use brute-force and indexed nearest-water implementations

Reason:

The brute-force implementation provides a simple correctness baseline; the indexed implementation evaluates the acceleration gained from spatial indexing.

## 18.7 Record manifests and hashes

Reason:

Reproducibility requires knowing exactly which inputs and outputs produced a result, not merely remembering that a script was run.

## 18.8 Build countywide outputs only after smaller deterministic validation

Reason:

Scaling a wrong algorithm only produces wrong results faster. Validation precedes scale.

## 18.9 Keep large geospatial data outside ordinary Git tracking

Reason:

The repository should remain usable and reviewable while preserving scripts, manifests, small fixtures, and instructions needed to reconstruct large artifacts.

---

# 19. Repository Structure and Current Source Responsibilities

The repository is organized around code, configuration, documentation, tests, data staging, and generated outputs.

Core source areas include:

```text
caprm-flood/
├── configs/                 Workload YAML (1K, 10K, 100K, countywide)
├── cpp/spatial_core/
│   ├── src/                 fema_pip_dev, water_distance_bruteforce,
│   │                        water_distance_indexed
│   ├── include/             empty
│   └── tests/               no C++ test source
├── docs/                    Methods, policy, milestone, and source documentation
├── python/
│   ├── caprm/               Library modules
│   └── scripts/             CLI entry points
├── tests/                   Python test suite
├── data/                    Cached source and derived data (Git-ignored)
├── outputs/                 Generated artifacts (Git-ignored)
├── .gitignore
├── README.md
└── requirements.txt
```

Current `docs/` contents:

```text
docs/benchmark_results.md      Nearest-water benchmark methodology and results
docs/crs_policy.md             Canonical operational CRS policy
docs/data_sources.md           Source provenance, vintages, inclusion rules, limits
docs/milestone_1.md            Milestone 1 method and results
docs/milestone_2.md            Milestone 2 method and results
docs/validation.md             Validation contract and agreement results
docs/report/                   In-progress report sections
```

The following directories exist but are empty: `benchmarks/`, `docker/`,
`data/sample/`, `cpp/spatial_core/include/`. They should be removed or populated
deliberately rather than left as ambiguous scaffolding.

There are no C++ unit tests. Every C++ correctness claim rests on field-by-field
comparison against the Python reference over the full property-ID union. This is
a deliberate consequence of the validation architecture — comparison against an
independent implementation is a stronger check than self-authored unit
assertions — but it should be stated plainly rather than implied.
Important current modules include:

```text
python/caprm/baseline.py
python/caprm/crs.py
python/caprm/evidence.py
python/caprm/export.py
python/caprm/hydrography.py
python/caprm/ingest.py
python/caprm/scoring.py
python/caprm/study_area.py
python/caprm/terrain.py
python/caprm/validate.py
python/caprm/water_benchmark.py
python/caprm/water_distance.py
python/caprm/water_export.py
python/caprm/water_validate.py
```

Key C++ sources include:

```text
cpp/spatial_core/src/fema_pip_dev.cpp
cpp/spatial_core/src/water_distance_bruteforce.cpp
cpp/spatial_core/src/water_distance_indexed.cpp
```

The repository also contains scripts for:

- property workload materialization;
- FEMA baseline execution;
- C++ input export;
- Python/C++ comparison;
- hydrography caching;
- water benchmarking;
- environment capture;
- terrain raster preparation;
- terrain evidence generation;
- exposure-index generation;
- milestone summary generation.

The repository should be understood by reading the code and current documentation together. Historical nucleus/proposal documents may contain planned items that have since been completed, changed, or deferred.

---

# 20. Git and Repository State as of 2026-07-15

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

As of the synchronization check on July 15, 2026:

```text
HEAD == origin/master
ahead: 0
behind: 0
```

The GitHub repository therefore contains the committed implementation through the current Milestone 3 terrain and preliminary scoring work.

Some local presentation, Word-document, editor, and temporary inventory files remain intentionally untracked and are not part of the canonical source repository.

---

# 21. Academic and Professional Standard

This project must satisfy more than course completion.

It is intended to function as a serious employer-facing technical artifact demonstrating that Sterling can:

- structure a nontrivial software/data project;
- reason about geospatial systems;
- work across Python and C++;
- manage CRS and computational-geometry concerns;
- build deterministic pipelines;
- validate independent implementations;
- benchmark algorithms and spatial indexes;
- design traceable evidence schemas;
- work with raster and vector geospatial data;
- create reproducible CLI-oriented workflows;
- distinguish measured evidence from modeling assumptions;
- explain technical limitations honestly;
- defend design choices rather than merely present functioning code.

The project's credibility depends on implementation and evidence, not on polished language alone.

Claims such as "correct," "reproducible," "high-performance," or "defensible" should only be made when the repository, tests, manifests, validation results, and benchmarks support them.

---

# 22. Evaluation Standards

When evaluating a new technical idea or change, use these criteria:

## Course value

Does it materially improve the CSCI 788 capstone?

## Computer-science substance

Does it add meaningful systems, algorithms, data engineering, computational geometry, validation, or performance work?

## Professional signal

Would a technical interviewer understand why the work demonstrates engineering competence?

## Research awareness

Is the methodology situated honestly relative to existing geospatial/flood-risk methods?

## Feasibility

Can it be completed and validated without undermining the quality of the core project?

A technically interesting addition that cannot be validated or finished may be worse than a smaller feature completed rigorously.

---

# 23. AI-Assisted Development Standard

AI may accelerate explanation, code review, architecture planning, debugging, documentation, and implementation, but it must not become a substitute for technical understanding.

The standard is not:

> Can an AI generate code that passes?

The standard is:

> Can Sterling explain what the code does, why the design is defensible, how correctness was validated, what assumptions remain, and where the system can fail?

When an AI assistant proposes changes, it should:

1. inspect or reconstruct the current repository state first;
2. identify the exact files involved;
3. distinguish existing behavior from proposed behavior;
4. explain the design decision;
5. identify compatibility implications;
6. preserve validated artifacts unless replacement is intentional;
7. define how the change will be tested and validated;
8. avoid inventing project facts that are not supported by code, artifacts, or explicit project history.

The assistant should prioritize correctness and continuity over unnecessary redesign.

---

# 24. Working Style for Future Project Conversations

When continuing CAPRM-Flood, the assistant should behave as a rigorous technical collaborator.

It should:

- use precise technical language;
- explain new concepts in plain terms when first introduced;
- be direct when a claim is not yet supported;
- preserve completed architecture unless there is a concrete reason to change it;
- avoid restarting solved decisions;
- inspect existing code before proposing duplicate functionality;
- treat tests and validation artifacts as part of the product;
- prefer explicit copy-pasteable implementation changes when Sterling is manually editing;
- keep report-writing work separate when the current task is implementation;
- distinguish project facts, assumptions, proposals, and future work.

For substantial implementation changes, the preferred workflow is:

```text
establish current state
    ↓
identify relevant files
    ↓
explain proposed design
    ↓
identify compatibility/provenance concerns
    ↓
implement
    ↓
test
    ↓
validate
    ↓
regenerate artifacts
    ↓
audit outputs
    ↓
document
```

---

# 25. Current Project Phase

As of July 15, 2026:

- Milestone 1 is complete and validated.
- Milestone 2 is complete and validated.
- Milestone 3 has implemented countywide terrain evidence and a preliminary exposure index.
- The full test suite has passed after the current terrain/scoring implementation.
- The repository is synchronized to GitHub through commit `0dd85ab`.
- Milestone 3 still requires final hardening and completion work before it should be frozen as complete.
- Precipitation remains a later evidence-family addition.
- Final report work is not the immediate implementation priority.

The precise remaining tasks should be read from `CAPRM_Flood_Roadmap.md` once that document is created.

The exact latest implementation/output state should be read from `CAPRM_Flood_Current_Status.md` once that document is created.

---

# 26. Handoff Protocol for a New AI Assistant

A new assistant continuing this project should begin by reading:

1. `CAPRM_Flood_Project_Nucleus_2026-07-15.md`
2. `CAPRM_Flood_Current_Status.md`
3. `CAPRM_Flood_Roadmap.md`
4. `Capstone_Proposal.pdf`
5. `Professor_Milestone_Requirements.txt`
6. the current GitHub repository

Before writing new code, the assistant should reconstruct:

- the project purpose;
- the architecture;
- the Python/C++ boundary;
- completed Milestones 1 and 2;
- current Milestone 3 implementation;
- the evidence-product separation;
- the current repository tree;
- the exact next roadmap chunk.

It should then identify any contradiction between the canonical documents and the current repository.

When conflicts exist, prefer:

1. current validated code and artifacts;
2. `CAPRM_Flood_Current_Status.md`;
3. this nucleus;
4. `CAPRM_Flood_Roadmap.md`;
5. older proposal-era documents.

Older documents are valuable for project intent, but they may describe work that has since been completed or revised.

---

# 27. Canonical One-Paragraph Summary

CAPRM-Flood is a reproducible C++/Python geospatial evidence-extraction framework for large-batch property-to-hazard spatial joins, demonstrated through a property-level relative flood-exposure indexing workload for Monroe County, New York. The system ingests property coordinates and public hazard data, derives validated FEMA flood-zone, nearest-water, and terrain evidence, preserves source provenance and deterministic behavior, compares independent Python and C++ spatial implementations for correctness and performance, and feeds validated evidence into an explicit preliminary scoring layer that produces relative exposure scores and regional rankings. The project's central engineering values are correct spatial computation, CRS discipline, deterministic outputs, source-family evidence separation, independent validation, manifests/checksums, benchmarkable implementations, and reproducible workflows. As of July 15, 2026, Milestones 1 and 2 are validated, countywide terrain evidence and preliminary exposure scoring are implemented for 267,362 properties, the automated test suite passes, and the project is completing the remaining Milestone 3 hardening work before moving to later precipitation and final-project completion tasks.
