# CAPRM-Flood Project Nucleus — 2026-07-30

## Purpose of This Document

This document is the canonical context-restoration source for **CAPRM-Flood** as of **July 28, 2026**. It exists so that a new AI assistant, collaborator, reviewer, or future project conversation can reconstruct the project's purpose, architecture, technical history, standards, and current implementation state without relying on stale proposal-era assumptions or raw chat transcripts.

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

The index is not the claim. It is the reason the extraction has to be fast, exact, and checkable.

---

# 2. Core Problem

Given a large set of property locations in a selected region and a collection of public flood-related geospatial datasets, CAPRM-Flood asks:

> Can a transparent C++/Python processing system derive defensible property-level flood-exposure evidence efficiently and reproducibly, validate the spatial computations across implementations, and convert those evidence fields into an interpretable relative exposure ranking?

The project addresses this as a batch-processing and evidence-engineering problem.

Milestones 1 through 3 answered that question affirmatively and produced the evidence. Milestone 4 asks the sharper form of it:

> The exact geometric computation is expensive. What are the ways to make it cheap, what does each one cost, and how do you know?

Two answers exist, and the project implements both:

```text
learn where to look     -> a learned spatial index.  Still exact. Faster.
learn the answer        -> a neural surrogate.       Approximate. Fastest.
                                                     The error is structured.
```

Pursuing the first leads somewhere the literature has not been. Learned spatial
indexes are evaluated almost exclusively on point data, and several return
approximate results. This project's data is line segments and polygon
boundaries, and its query is exact nearest neighbour. Section 14b states the
resulting research question and the evidence that the gap is real.

Both are measured against an exact baseline whose correctness is already proven
field-by-field against an independent implementation. That combination —
an approximate method, and infrastructure that can prove exactly how wrong it
is — is the project's distinguishing property. The learned-index literature
reports speed and assumes correctness; this project can verify it.

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

A derived exposure-index layer has also been implemented, together with
rank-based sensitivity analysis and an automated product audit.

A fourth precipitation family is planned as a gated stretch goal. See section 14b.

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
non-X zone is SFHA, and X never is. `is_sfha` therefore carries no
information beyond `fema_zone` for the current workload, and does not
contribute to the score. It is retained as a validation cross-check enforcing
the FEMA invariant that a property cannot be SFHA without matching a
flood-hazard polygon.

The zone-to-SFHA relationship is a property of this data, not a guarantee of
the FEMA schema, and should not be assumed to hold for another county or a
future NFHL vintage.

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

The detailed operational policy lives in the repository at
`docs/crs_policy.md`. This section records the durable principle; that file
records the rules.

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

---

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

## Where machine learning sits in the boundary

Milestone 4 introduces trained models. They do not change the boundary; they
follow it.

```text
Python  trains.    Model fitting, evaluation, error analysis, held-out
                   splits, artifacts, manifests. Training is offline, once,
                   and reproducibility comes from a recorded seed and a
                   checksummed model artifact.

C++     infers.    A recursive model index is a handful of multiply-adds.
                   Porting inference is trivial; porting training would be
                   pointless. Inference is on the query path, which is the
                   only place performance is claimed.
```

A trained model is an artifact like any other: it has a manifest, a checksum,
a recorded seed, and a documented training set. A result produced by a model
whose weights are not checksummed is not reproducible.

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

# 14. Milestone 3 — Terrain Evidence and Exposure Index

Milestone 3 introduces the third implemented evidence family, raster-derived
terrain, and the first derived scoring layer.

Current implementation:

```text
python/caprm/terrain.py
python/caprm/scoring.py
python/caprm/sensitivity.py
python/caprm/audit.py

python/scripts/prepare_terrain_raster.py
python/scripts/build_terrain_evidence.py
python/scripts/build_exposure_index.py
python/scripts/summarize_milestone3_results.py
python/scripts/summarize_scoring_inputs.py
python/scripts/summarize_component_correlation.py
python/scripts/analyze_scoring_sensitivity.py
python/scripts/audit_milestone3_products.py

tests/test_terrain.py
tests/test_scoring.py
tests/test_sensitivity.py
tests/test_audit.py

docs/scoring_methodology.md
```

The current countywide products contain:

```text
267,362 unique property IDs
0 missing slope values
terrain elevation range: approximately 75.000–296.309 m
exposure index range: approximately 7.915–99.929
exposure index mean: approximately 34.632
exposure index median: approximately 33.728
```

Scoring policy `preliminary_exposure_index_v2`.

Milestone 3's lasting contributions are not the terrain fields or the score.
They are three methodological patterns:

**A manifest must reproduce the result it describes.** The first scoring
implementation recorded three weights while applying five. The index could not
be recomputed from its own manifest. This is now a structural requirement
verified on every audit run.

**A stability metric must be calibrated before it is trusted.** Three of four
components are percentile ranks, and reweighting a linear sum of rank
variables tends to preserve order, so a high rank correlation could have been
an artifact of the design rather than a finding. Reference configurations that
are deliberately implausible establish the floor.

**Measured influence is not nominal weight.** A weight expresses intent; the
variance decomposition expresses effect. Reporting only the former invites a
reader to assume the wrong component dominates.

The exact remaining tasks belong in `CAPRM_Flood_Roadmap.md` and
`CAPRM_Flood_Current_Status.md`.

---

# 14b. Milestone 4 — Learned Indexing of Extended Spatial Objects

Milestone 4 is where the project's computer-science contribution is
concentrated. It adds no evidence family. It asks a question the literature has
not asked, using a dataset that forced the question.

## The research question

> Learned spatial indexes are evaluated almost exclusively on **point** data
> with range and kNN queries, and several return **approximate** results. Does
> the approach extend to **exact nearest-neighbour queries over extended
> objects** — line segments and polygon boundaries — and what does exactness
> cost?

## The gap, and the evidence that it exists

The learned spatial index literature is large and active: ZM-index, ML-Index,
HM-Index, IF-Index, RSMI, LISA, Flood, Tsunami, LMSFC, WaZI, SLBRIN. Every one
of them indexes point data.

This is not an inference from reading them. The RLR-Tree authors state it as a
limitation of the entire class:

> "they can only handle spatial point objects while our proposed method is able
> to handle any spatial data, such as rectangular objects"
> — RLR-Tree, arXiv:2103.04541

The same passage records two further weaknesses:

> "some of these learned indices return approximate query results while our
> query results are accurate"

> "some of them do not consider KNN queries ... LISA extends their algorithm
> for range queries to handle KNN queries by issuing a series of range queries
> until k points are found. However, the query performance largely depends on
> the size of the region used."

A comprehensive benchmark now exists — *How good are multi-dimensional learned
indexes? An experimental survey*, VLDB Journal 2024 — and it finds that IF-Index,
Flood, and LISA robustly outperform non-learned baselines while ZM-index,
ML-Index, and RSMI cannot systematically do so. It evaluates point data.

So three properties are simultaneously outside the literature:

```text
extended objects        rather than points
exact nearest neighbour rather than kNN over points, or approximate results
verified exactness      rather than assumed exactness
```

**This is an unexplored corner, not an open problem.** The distinction matters
and the project should state it plainly. Nobody has done this because nobody
needed to, not because it is hard. The contribution available here is a
rigorous measurement the literature lacks, not a solution to something the
field is stuck on.

## Why the project arrives here without contrivance

The path was forced by the project's own measurement, not chosen to
accommodate machine learning:

```text
the Feature BVH stalls at 93.34% pruning
  because water features are enormous and 104x size-heterogeneous
    so index segments rather than features
      segments are small and roughly uniform in size
        so they can be ordered by midpoint along a space-filling curve,
        nearly losslessly
          which is what makes a learned index possible at all
            and roughly 1,063,159 segments is squarely learned-index scale
```

**The reason nobody learned-indexes extended objects is that extended objects
break space-filling curves.** A long object occupies many cells; its midpoint
is a lie; the smallest-enclosing-cell approach places anything crossing a
partition boundary at the root. This is why R-trees exist.

The granularity change dissolves that objection. A segment between two
consecutive vertices of Lake Ontario's boundary is small. The project did not
select segments to enable learning; it selected them because its own benchmark
showed features were 104 times too large, and the learning became possible as a
consequence.

## The technical problem: search-radius inflation

Ordering segments by midpoint breaks exact nearest-neighbour search unless the
search radius is inflated.

A segment's midpoint can lie outside a query disk while its nearest point lies
inside it. Searching `disk(r)` by midpoint therefore misses that segment. To
remain exact, the search must cover:

```text
disk(r + L/2)      where L is the longest segment in the index
```

**That inflation is the entire cost of treating extended objects as points**,
and it is tunable. Grouping segments into runs reduces node count and improves
traversal, but enlarges the extent of each entry and therefore the inflation.
No theory predicts the optimum; it is an empirical property of the data.

A single long segment inflates every query in the index. Whether the project's
hydrography contains such outliers — a straight canal reach represented as one
long segment, for instance — is measurable and must be measured before anything
is built on top of it.

## The project's unusual asset

The learned-index literature generally reports speed and assumes correctness.
Some of it returns approximate results by design.

This project has an **exactness oracle**: a trusted Python reference and a
comparison harness that has already proven field-by-field agreement across
267,362 properties. Any learned method can therefore be verified rather than
asserted.

That combination — an approximate method, and infrastructure that can prove
exactly how wrong it is — is what the project has and the literature generally
does not.

## The implementations

```text
1. brute force              no index                    existing
2. Feature BVH              2D,  8,572 features         existing
3. Segment BVH              2D, ~1M segments            implemented
4. Hilbert + binary search  1D, ~1M segments            control
5. Hilbert + RMI            1D, ~1M segments            learned position
6. + learned radius         seeds the search disk       stretch
```

The comparisons that matter are adjacent, never global:

```text
3 vs 2   granularity              does indexing geometry beat indexing features
4 vs 3   dimensionality reduction what does flattening 2D to 1D cost
5 vs 4   machine learning         same data, order, decomposition, and kernel.
                                  The only difference is whether a model or a
                                  binary search finds the position.
6 vs 5   learned radius           does predicting the answer accelerate
                                  computing it exactly
```

**Implementation 4 is not optional.** Without it, comparing a segment index
against a learned index confounds the dimensionality reduction with the
learning, and a loss could not be attributed to either.

## The segment index method (implementation 3, implemented)

Implementation 3 is a bounding-volume hierarchy over individual boundary
segments rather than whole features, built by the same `#include`-the-kernel
pattern the Feature BVH uses, so the exact point-to-segment kernel and the tie
rule are reused unchanged. Two design elements make it a durable part of the
methodology:

**Distance-exact splitting.** Before indexing, any segment longer than a cap
(default 100 m) is subdivided into equal collinear pieces so no leaf box spans
more than the cap. This bounds the `L/2` midpoint inflation that the later
Hilbert phase depends on (uncapped, one Lake Ontario boundary chord of 5,748 m
would inflate every query by 2,874 m). The subdivision changes no distance: every
piece lies on its original segment, so the minimum point-to-piece distance equals
the point-to-original distance. Splitting therefore only tightens index boxes; it
never alters a reported nearest-water distance. The pieces exist solely as BVH
leaf boxes — the reported distance is always computed by the unchanged kernel over
the original geometry, which is why the segment-index output is byte-identical to
the reference rather than merely within tolerance.

**Two-phase query, and polygon-interior → 0 without a containment index.** A
best-first traversal collects the set of candidate features whose sub-segment
boxes can compete at the final threshold; the unchanged exact kernel and tie rule
then run over those candidates. Polygon-interior → 0 (the ~266 properties inside a
waterbody, whose exact distance is 0 regardless of the nearest boundary segment)
is preserved without a separate point-in-polygon index, because the USGS 3DHP
hydrography partitions water area without overlap: a point inside a polygon has
that polygon's own boundary as its nearest boundary, so the polygon is always a
candidate and its interior-zero result is always reached. This invariant is stated
rather than assumed, and is checked empirically by countywide field-for-field
agreement and by the interior-zero rows remaining exactly 0. Each leaf carries its
parent feature's `water_feature_id`, because the tie rule resolves on it.

The measurement half of splitting lives in a Python pre-index pass
(`split_water_segments.py`) that reports the length distribution and writes a
provenance manifest; the geometric subdivision itself happens in memory in the C++
program. The vertex export is not modified, so upstream evidence products and their
manifests are untouched.

**Measured result (2026-07-22, countywide).** The granularity hypothesis in
section 14b held. Segment checks per property fell from the Feature BVH's 70,771
to 9,716.87 — 99.09 percent pruned, 7.28 times better — with candidate features
per property falling from 5.498 to 1.497, and the features selected also being
smaller (6,490 segments each versus 12,872). Exactness was preserved: 267,362 of
267,362 properties agree field-for-field with the Python reference at a maximum
absolute error of 4.658e-10 m, the same figure the Feature BVH reports, and all
266 interior-zero properties resolve to `waterbody` features at exactly 0.
Capping segment length at 100 m cost 0.50 percent additional index entries while
reducing maximum entry extent 57-fold.

Two durable consequences follow. First, the `L/2` search-radius inflation that
section 18.19 identifies as the price of representative-point ordering is
**tunable to near-zero cost** on this data — 2,874 m becomes 50 m for half a
percent more entries — so inflation need not dominate the later one-dimensional
implementations. Second, the bottleneck has moved: phase-1 search costs roughly
35 box and node operations per property, while phase-2 exact verification costs
9,716.87 segment checks, because the kernel rescans each candidate feature's
entire original geometry. Over 99 percent of the remaining work is proving the
answer rather than finding it, which is where further index work must aim.

**Measured result (2026-07-23, countywide).** B2 swept the entry-extent cap
under both verification strategies. Two findings are durable beyond the numbers.

First, treating the entry-extent cap as a performance dial is a category error
on this data. Across a 575-fold range of maximum entry extent — a 10 m cap up to
no split at all — median query time varies 6.9 percent under original-geometry
verification and 9.3 percent under split-geometry verification, and verification
checks vary 13.7 percent and non-monotonically. Every repetition of a given
configuration was bit-identical, so the variation is deterministic tree-topology
behaviour, not scatter. The cap therefore cannot be chosen on query performance;
it is chosen for its only downstream consumer, the `L/2` inflation radius the
one-dimensional implementations inherit. The chosen operating point is a 25 m
cap, giving `L/2` = 12.5 m — a 1.08x area inflation at the county's 325 m median
nearest-water distance — for 11.9 percent more entries than the uncapped index.

Second, and binding on every later implementation: a segment check is not a
mode-invariant unit of cost. Split-geometry verification removes 30 percent of
segment checks yet runs 6.0 times faster, because the two count different work.
An original-mode check is a full point-to-segment projection fused with the
ring-crossing parity inside `evaluate_ring`; a split-mode check is the crossing
parity alone in `ring_contains_point`, whose y-straddle clause short-circuits
before the division on most segments. The decomposition is exact at the 100 m
cap: 1.43x fewer checks times 4.21x cheaper per check equals the 6.02x
wall-clock ratio, and the per-check ratio is stable (3.86x-4.21x) across the
whole sweep. **Segment-check counts are comparable within a verification mode
and not across modes**, and by extension not across implementations that verify
differently. The five-implementation benchmark must therefore report wall clock
beside counts and never infer a speedup from counts — doing the latter would
have understated B2's measured 6.0x as an implied 1.43x, a four-fold error.

This also answers the second half of the section 14b research question, "what
does exactness cost over extended objects." Under original-mode verification,
98.4 percent of per-property segment checks fall on polygon candidates and 1.6
percent on line candidates, so the cost of exactness is the inside/outside
predicate, not the distance. A point inside a polygon part must lie inside that
part's exterior-ring bounding box, so a bounding-box pre-filter skips the ring
walk for parts that cannot contain the point — exact, not approximate. Countywide
that filter skips 57.6 to 59.3 percent of polygon parts and accounts for 94.7
percent of split mode's saving. The predicate cost is thus roughly halved by an
exact spatial pre-filter but not eliminable without a dedicated containment
structure, which is a target for later work rather than for the index itself.

The boundary-epsilon hazard the split strategy could in principle introduce is
closed with a number: the kernel snaps a point to a boundary below
`BOUNDARY_EPSILON_METERS` = 1e-9 m, and the split interpolation perturbs
distances by up to 1.18e-9 m, the same order. The minimum nonzero countywide
distance is 0.002166 m — about 1.8 million times the snapping band — so no
property can be classified differently by the two strategies, and the
on-boundary branch never fires countywide; all 266 interior zeros come from
ray-crossing parity over genuine interiors. Original-geometry verification
remains the default because split verification raises maximum absolute error
from 4.658e-10 m to 9.06e-10 m, forfeiting byte-identical reproduction of the
Python reference for a speedup the frozen Milestone 2/3 evidence does not need.
Split is carried forward as a validated flag and a first-class row in the
benchmark.

## The learned radius, and why it unifies the two halves

The RLR-Tree authors note that kNN performance "largely depends on the size of
the region used." That region can be learned.

The neural surrogate trains a mapping from coordinates to the index. The water
component of the index is a percentile of distance-to-nearest-water, so the same
machinery trains a mapping from coordinates to that distance — a **distance
field**.

A predicted radius seeds the exact query. Search `disk(r_hat + L/2)`; if a
candidate is found at distance `d <= r_hat`, then `disk(d)` was fully covered
and `d` is provably correct. If nothing is found, double and retry.

**Overestimating is safe and merely slower. Underestimating costs a retry.**
Biasing the model to overestimate makes it an admissible heuristic. The exact
kernel still decides, so correctness never depends on the model being good.

This makes the surrogate load-bearing rather than a curiosity: the approximate
answer is used to make the exact answer fast. The two halves of Milestone 4
stop being separate projects.

## Why this does not deviate from the project

`benchmarkable` is one of the six properties named in the contribution
statement in section 1. Milestone 4 is the most benchmarkable work the project
can do: six implementations, one exact geometry kernel, one validation harness,
exact agreement required of every implementation that claims to be exact.

The exposure index is unchanged and remains preliminary. It stops being the
story and returns to being the application layer.

## Honest risks, stated in advance

**The result may be uninteresting.** If segments are effectively points, the
finding reduces to "learned indexes work on points," which is known. The
mitigation is that the inflation radius *is* the extended-object problem, and
characterizing its cost is a contribution regardless of which implementation
wins.

**The learned index may lose.** At roughly one million keys in two dimensions,
a well-built segment index may simply be better. This is unremarkable: the
published record already shows that ZM-index, ML-Index, and RSMI cannot
systematically outperform non-learned indexes. A negative result, measured
against an exact baseline with verified correctness, is a finding.

**It did lose, and the shape of the loss is the contribution.** B6 measured it
countywide: at the shipped configuration the learned rung is 6.48 percent slower
than its own binary-search control. But that figure is not a property of the
model. It moves from +11.6 percent to +0.001 percent across nine seed-window
sizes, and roughly doubles under split-geometry verification. See section 18.27.

**Scope of the B5/B5c/B6 negative result.** It is measured at ONE index size,
1,189,589 entries. The learned-index literature's central claim is that the
advantage grows with index size, and this project does not test that. The
`_10000`/`_100000`/`_countywide` workloads vary QUERY COUNT, not index size: the
exporter writes the whole feature table from the hydrography cache regardless of
the property set, so all three workloads carry 8,572 features and 1,072,254
vertices and build the identical index (verified by row count and by input
digest, 2026-07-29). A true index-size axis requires a defensible hydrography
subsetting scheme, a reference recomputed at each subset, and the RMI retrained
at each N, since a model fitted to 1.19M keys says nothing at 100K. It is
deferred as a stretch chunk. Until it exists, the finding is: at ~1.19M
extended-object entries, on this workload, at this window, under this
verification mode, a two-stage RMI seed loses to binary search by about ten
distance computations per probe saved.

**The project will not beat R-trees.** It does not need to. The question is
whether the approach extends to a query class the literature has not touched,
and what it costs.

## Scope decision: precipitation becomes a gated stretch goal

Precipitation was planned as the fourth evidence family and was presented as a
Milestone 3 forward-looking goal. It is not cancelled. It is outranked.

A fourth family adds ingestion, provenance, and validation work, and adds no
algorithmic content. The project's identified weakness is that its
computer-science contribution stalled after Milestone 2's Feature BVH; a
fourth data source would not address it. The remaining time buys more by going
deeper on index structure than wider on evidence.

**Gate.** Precipitation may begin only after the segment index, the learned
index, and the surrogate are complete and documented. A stretch goal without an
explicit precondition becomes roadmap noise.

**Its value is architectural, not evidentiary.** Precipitation is the fourth
data topology — interpolated point statistics. Section 1 claims the evidence
contract generalizes across topologies, and terrain demonstrated that for
raster. Precipitation would confirm the claim rather than restate it. That is
worth having if the time exists, and not worth having at the cost of the
computational work.

**Ordering consequence.** The surrogate learns a mapping from coordinates to
the index as frozen at `preliminary_exposure_index_v2`. If precipitation lands
afterward, the index becomes a five-component v3 and the surrogate continues to
describe v2. That is acceptable and must be documented rather than repaired:
the surrogate's claim is that it can approximate a deterministic geometric
function, not that it approximates whichever index is current.

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

The project includes a deterministic exposure-index implementation in:

```text
python/caprm/scoring.py
python/scripts/build_exposure_index.py
```

The methodology is documented in `docs/scoring_methodology.md`.

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

The current index should be treated as **preliminary** until the precipitation
evidence family is added and the final index methodology is revisited with the
full evidence set.

The project should not present one weighting configuration as objectively true
merely because it produces a clean ranking.

## Durable properties of the scoring layer

Recorded here because they are facts about the design rather than transient
status.

**Four components, four declared weights.** No component applies an internal
sub-weight. The manifest's weights plus the evidence tables are sufficient to
reproduce the index. This is a requirement, not a convenience: a manifest that
records some of the constants and leaves the rest in source cannot support a
reproducibility claim.

**Slope is extracted and preserved as evidence but does not score.** Whether
it should is a methodology question, not a defect. The directionality is not
obvious: steep slope implies runoff, flat implies ponding.

**FEMA is absolute; water and terrain are percentile ranks over the
workload.** The percentile components are distribution-dependent by
construction, so scoring a subset yields different scores for the same
property. The index is meaningful only for the full countywide population and
is not comparable across workloads or NFHL vintages.

**The composite is rounded before ranking** so that properties tied in
substance share a rank. The composite lies on a lattice, and float noise would
otherwise impose an ordering sourced from operation order rather than
evidence.

**Nominal weight is not influence.** Influence scales with weight times spread,
and the components do not have equal spread. Percentile components are uniform
by construction (σ ≈ 28.87); the FEMA component is concentrated (σ ≈ 11.39,
with 98.1% of properties tied at one value). Water carries 35% of the weight
and 65% of the variance; FEMA carries 40% and 17%.

This is not a defect to be corrected. FEMA adds a constant to 98.1% of
properties, and constants do not affect ranking; its role is to move the 1.9%
it has information about decisively. Transforming the component to give it
comparable spread would invent distinctions the source data does not contain.

**The components are near-orthogonal.** Maximum pairwise rank correlation is
0.152. None duplicates another.

**Rank stability is moderately sensitive to weight choice.** The extremes are
immovable; the middle ordering depends on assumptions. The measured
characterization is that the index reliably identifies the extremes.

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

## 18.10 A manifest must reproduce the result it describes

Reason:

No constant may live only in source. A manifest recording some of the inputs
to a calculation, with the rest hidden in code, cannot support a
reproducibility claim, and is worse than an obviously incomplete manifest
because it looks complete.

## 18.11 Round a derived score before ranking it

Reason:

A composite built from rank-based components lies on a lattice, so distinct
inputs collide on identical values. Float noise separates those collisions by
around 1e-14, which lets a rank function impose an ordering sourced from
operation order rather than from evidence. Rounding at a threshold derived
from the lattice spacing merges only values tied in substance.

## 18.12 Declare a threshold before measuring against it

Reason:

A threshold chosen after inspecting the result it is meant to judge makes the
verdict unfalsifiable.

## 18.13 Calibrate a metric before trusting it

Reason:

A stability metric that cannot distinguish a genuinely different configuration
from the baseline is uninformative, and a high score on it means nothing.
Include deliberately implausible reference configurations to establish the
floor; exclude them from the verdict; report them alongside it.

## 18.14 Never manufacture spread

Reason:

Transforming a component to give it variance the source data does not contain
invents distinctions that do not exist. A component concentrated on one value
is reporting faithfully that its source has nothing further to say.

---

## 18.15 An approximate method must be measured against an exact one

Reason:

An approximation is only meaningful relative to the thing it approximates. The
project already has an exact baseline whose correctness is proven field-by-
field against an independent implementation, so any learned or approximate
method can be measured rather than asserted. The learned-index literature
generally reports speed and assumes correctness; this project has no reason
to.

## 18.16 An index may change what is examined, never what is computed

Reason:

The Feature BVH established this: it changes search strategy, not distance
semantics. The rule extends to a learned index without modification, and it is
what makes learning safe here. A model that predicts badly produces a wider
candidate window and a slower query. It cannot produce a wrong answer, because
the exact kernel still decides. Correctness does not depend on the model being
good.

## 18.17 Split spatially, not randomly

Reason:

Adjacent parcels are near-duplicates: they share a FEMA polygon, sit metres
apart on the same DEM cells, and often select the same nearest water feature.
A random train/test split places near-identical records on both sides and
reports a generalization score that is really a memorization score. Any
held-out evaluation in this project must partition by spatial block.

**Measured at C1, 2026-07-30.** The median nearest-neighbour spacing between
properties is 24.4 m, and 1,700 rows share an exact coordinate with another row.
Under a random split the minimum test-to-train distance is therefore exactly
0.000 m and 96.6 percent of test properties sit within 125 m of a training
property. A nearest-training-neighbour predictor — which has learned nothing but
"copy your neighbour" — scores R^2 = 0.8526 to 0.8667 across ten random splits
and -0.542 to -0.147 under the blocked K-fold partition. The ranges do not
overlap. That gap is the size of the error this principle prevents, and it is
what the discipline bought.

## 18.18 A negative result is a result

Reason:

The learned index may lose to a well-built segment index at this scale. Stated
in advance, measured against an exact baseline, and explained, that is a
finding. Tuning until the preferred method wins is not.

## 18.19 An index over extended objects must inflate its search radius

Reason:

Ordering extended objects by a representative point is lossy: a segment's
midpoint can lie outside a query disk while its nearest point lies inside.
Exactness therefore requires searching `disk(r + L/2)`, where `L` is the
longest object in the index.

This is the price of treating extended objects as points, it is the reason the
learned-index literature has stayed on point data, and it is tunable rather
than fixed. It must be measured before it is designed around: a single long
segment inflates every query in the index.

Measured update (B2, 2026-07-23): with segments capped at 25 m the inflation
term is 12.5 m, a 1.08x area correction at the county median distance, so on this
data the inflation is a small correction rather than the dominant cost. The
principle stands; its magnitude on capped extended objects does not dominate.

Mechanism (B3a, 2026-07-28): the inflation is realized by an exact query over a
Hilbert ordering of entry midpoints. The admission radius is
`R = d_best + L/2 + tie_tol` (the tie term is required for the tie counter to
match the reference); candidate curve intervals are found by recursive quadrant
decomposition with a swappable region predicate, using the orientation-free
aligned-square key-range identity `[min-over-4-corners, +4^k)`. Any 1D index in
this phase — binary search, B-tree, or RMI — sits on this same query path; the
model only predicts where in the sorted array to start. The box-primary predicate
over-covers the disk; whether the tighter disk predicate is worth building is a
B3b decision gated on a measured countywide over-covering ratio, not assumed.
The capped-versus-uncapped inflation contrast (L = 5,748.24 m uncapped) is the
phase's quantitative answer to what exactness costs over extended objects.

Instrument correction (B3b, 2026-07-28): the ratio's denominator had to be
replaced before it could be measured. B3a instrumented `n_disk_r` — midpoints in
`disk(d_best + tie_tol)` — as the uninflated disk. That counter is degenerate by
construction, not by sparsity: `d_best` is a distance to the nearest POINT ON A
SEGMENT while the counter tests MIDPOINTS, and `|p - m_i| >= d(p, s_i) >= d_best`
for every entry, so an entry is counted only when its perpendicular foot happens
to land within `tie_tol` of its own midpoint. Measured: nonzero on 0 of 1,093
fixture properties and 193 of 267,362 countywide. The denominator is now
`n_true_r = |{entries : d(p, s_i) <= d_best + tie_tol}|` — the entries that
genuinely satisfy the range predicate at the answer radius, which is what an
exact index would admit if its entries had zero extent. It is `>= 1` always and
exact from the tight descent alone. Durable rule: when a ratio is defined over an
index of extended objects, check that its denominator counts a population and not
a coincidence.

Measured countywide (B3b, 2026-07-28): capped at 25 m the exact query admits
10.28 entries per property against the 1.61 that actually satisfy the range
predicate — a 6.40x geometric inflation. Uncapped, the same queries would admit
5,612.61, a 3,493.30x inflation, because one Lake Ontario boundary chord of
5,748.24 m sets L for the entire index. Splitting therefore bought a **546x
reduction in admitted entries per query** for 11.89 percent more index entries.

The durable claim: on extended-object data the inflation penalty that has kept
the learned-index literature on point data is not intrinsic to extended objects.
It is a function of the longest object in the index, and it is removable by a
distance-exact preprocessing step costing a fraction of a percent of index size.
What remains after capping — 6.4x — is a modest constant, not a barrier. The
barrier is real only if the index is built over the geometry as given.

Second durable claim from the same measurement: the inflation is no longer where
the cost is. At 10.28 admitted entries against 11,922 phase-2 segment checks per
property, phase-1 admission is a rounding error in the query's total work. B2
reached the same conclusion about the segment BVH by a different route. Further
work on this query belongs in verification, not in search — and that bounds what
any learned index can achieve here.

**Measured at a second operating point (B6, 2026-07-29).** The inflation term
behaves as this section predicts when the query population moves, which means it
is a property of the workload as well as of the index. On the 10,000-property
subset, whose properties sit nearer water than the county as a whole, `N_true_r`
rises 1.6067 -> 1.6906 and admitted midpoints rise 10.2783 -> 11.7066, so the
capped geometric inflation rises 6.397x -> 6.9245x, while phase-2 segment checks
FALL 11,021.83 -> 1,486.11 per property. Nearer water means fewer and smaller
candidate features to rescan, and simultaneously a larger `(r + L/2)^2 / r^2`
because `L/2` = 12.5 m is a bigger fraction of a smaller `r`. Any inflation
figure must therefore name the workload that produced it.

**The window scan is inflation's uncounted twin.** The seed window reads `2W`
entries either side of the seed position, and that work appears in NO emitted
counter. At W = 2048 it is 4,096 distance computations per query against 72.88
counted resolve-descent entries — the uncounted work exceeds the entire counted
query. It is analytically known rather than instrumented, so it is reported as a
known additive term; but B6's joint fit over eighteen countywide cells puts a
sequential window-scan entry at ~3.2 ns against ~25 ns for a scattered
resolve-descent entry, a 7.8x locality premium, so the two must never be summed
as though an entry were an entry. B2 said a segment check is not
mode-invariant; B6 says an entry is not access-pattern-invariant.

**The cost of exactness, measured (B6c-2, 2026-07-29).** B2 implemented both
verification modes behind one flag; B6c-2 ran the cross-product. Option A rescans
each candidate feature's entire original geometry and is byte-identical to the
reference; Option B rescans only the split segments the index holds and agrees to
9.157e-10 m with zero `feature_id` disagreements at 267,362 properties.

The check-count ratio is stable across six independent mode pairs — three
workloads times two rungs — at 1.4308x to 1.4974x, mean 1.4602x, against B2's
predicted 1.43x. Calibrating the per-check cost from rung 3 alone gives 3.806 ns
for an Option A check (projection plus parity) against 0.922 ns for an Option B
check (parity only), a ratio of 4.130x against B2's independently measured 4.21x.
The two multiply to the 5.88x wall-clock difference rung 3 shows countywide.

Using that per-check constant, borrowed from rung 3, to predict the HILBERT
path's search cost independently in each mode agrees to 0.2 percent for rung 4.
Search cost is therefore mode-invariant, as it must be, and the decomposition is
sound enough to publish: countywide under Option A the segment BVH's search is
0.6 percent of query time (B1 derived ~0.4 percent by a different route), while
the Hilbert path's search is 41 percent under Option A and 80 percent under
Option B.

## 18.20 A model is an artifact

Reason:

Weights, a seed, a training-set checksum, and a manifest, or the result is not
reproducible. A model is held to the same provenance standard as a CSV.

Practice established (B4, 2026-07-28): the training array must be exported by
the implementation that built it, not reconstructed by the consumer. B4's keys
come from `water_distance_hilbert --dump-keys` because a Python rebuild of the
split, the normalization and the Hilbert transform would (a) duplicate the C++
splitter's logic, so a future change to it fails silently rather than loudly,
and (b) yield a checksum attesting to what Python built. The two can differ by
one floating-point ULP in the segment split, and the difference is undetectable
without the array being reconstructed. Exporting an array already in memory is
not a migration of functionality across the Python/C++ boundary; reconstructing
it would be.

The model header therefore carries the training-array SHA-256, and the manifest
carries probe keys with their normalized inputs as hex bit patterns, so the
consumer asserts the correspondence at load rather than inheriting it. Where a
numerical contract cannot be proved — `uint64` to `double` conversion is
implementation-defined in C++ under [conv.fpint], while numpy guarantees
round-to-nearest-even — it is recorded as a stated assumption with a runtime
check, not asserted as a proof.

Recorded weakening (B5, 2026-07-28): the C++ inference path does NOT verify the
training-array SHA-256. Nothing in this project implements SHA-256, and adding
roughly a hundred lines of it inside a chunk scoped as "swap one function" was
judged the wrong trade. What C++ checks instead, at no cost: the array length,
the array's content at five fixed positions carried by the probe records, and
the full inference chain — normalization, root, leaf, floor — reproducing `x`
bit-for-bit at each of those keys. The digest is verified by the trainer, which
refuses to fit unless the key dump matches the index manifest, and the fixture
asserts that the digest C++ reads out of the model header equals hashlib's
digest of the dump the trainer consumed. The provenance chain is therefore
closed across the two languages but not inside either one alone. This is a real
weakening of the principle above, and it is written here rather than left for
someone to discover by grepping for a check that is not there. Implementing
SHA-256 in C++ remains available as a separate chunk; it is well specified and
has published test vectors, so it would be genuinely testable.

## 18.21 Every phase update records interpretation, not only metrics

Reason:

A chunk is not closed when its numbers exist; it is closed when the durable
meaning of those numbers is written where the next chunk will read it. The
meaning of a result — the mechanism behind it, what it proves or refutes, what
cost model or validity boundary it establishes — is a Nucleus edit. The measured
values, artifacts, and next task are a Current Status edit. A metric recorded
without its meaning is technical debt: the next chunk either re-derives it or
misuses it, as a segment-check count would be misused if carried across
verification modes (B2).

## 18.22 An unsound predictor may cost time; it may never cost correctness

Reason:

18.16 says an index changes what is examined, never what is computed. B3b makes
that concrete and testable at the one seam a learned index occupies. The Hilbert
query finds a start position, reads a window around it to obtain `d_seed`, and
descends at `R_seed = d_seed + L/2 + tie_tol`. Because `d_seed` is the minimum
over a window of REAL segments of an ACHIEVED point-to-segment distance,
`d_seed >= d_true` holds for any window at any position, however that position
was obtained. `R_seed` therefore always covers the true answer, `d_best` is
exact, and the final candidate set is rebuilt by an independent descent that
never references the seed. A mispredicting model widens the first descent and
slows the query; it cannot change an emitted field.

The argument is not left as prose. `--seed zero` returns position 0 for every
query — the worst legal hint — and the fixture asserts its output is identical to
`--seed binary` on every column except the seed instrumentation. That is B5's
acceptance criterion, exercised before the model exists. The general rule: when a
component is claimed to be correctness-neutral, ship a degenerate implementation
of it and assert the outputs match, rather than arguing from the design.

Measured (B3b, 2026-07-28): the binary-search control performs 20.2376 key
comparisons per query on average and 21 at worst over 1,189,589 entries, exactly
`ceil(log2 N)`. The seam is therefore characterized before the model exists. B5's
RMI must beat about 20 dependent, cache-missing probes with a handful of
multiply-adds plus a bounded window scan, and any deviation in the emitted
evidence is attributable to the model alone.

Measured (B4, 2026-07-28): the model exists and beats the control on the seam it
occupies — 6.323 mean last-mile probes against 20.2376, a 3.20x reduction, with
a per-model error bound verified exhaustively over all 1,189,589 keys and
re-verified on the artifact as reloaded from disk. The ceiling recorded before
training also held: 13.91 saved probes against 11,021.83 phase-2 segment checks
per property is about 0.13 percent of counted query work, bought with a model 44
percent the size of the key array it augments. Both halves of that sentence are
the result. Stating the ceiling in advance is what makes the second half a
confirmed prediction rather than an excuse.

A corollary for any future bound in this project: the exhaustive bound covers the
keys IN the index, and the queries are not index keys. A bound measured over the
training set is an academic deliverable; it is not automatically a window. B4
measured the domain-wide bound separately and found it non-monotone in model
count and an order of magnitude too wide to size a window with — a fact invisible
from the training-set bound, which was +/-12 on the same leaf where the domain
bound was 341,353 during authoring. Correctness was never at stake either way,
which is the point of this section: the bounds are performance contracts, and a
performance contract that does not cover the inputs is a measurement, not a
guarantee.

Measured (B5, 2026-07-28): the ported model returns a position in zero key
comparisons, and its output is byte-identical to the binary control on every
column except the seed instrumentation over all 267,362 properties. The seam is
therefore correctness-neutral in practice as well as in argument. On the real
property-point keys the model lands within the +/-64 window on 86.630 percent of
queries against 94.240 percent on index keys, predicts 37.20 percent of them
exactly, and has a tail an order of magnitude worse than the training-set tail:
p99.9 absolute error 5,389 against 373, maximum 17,995 against 1,650. The
corollary above is thus confirmed on operational inputs, and the shape of the
failure is specific — the model is SHARPER at the centre (median absolute error
5 against 9) and far worse in the tail, which is what extrapolation outside a
leaf's training keys produces.

The query got SLOWER: 21.439 s against the binary control's 20.645 s under
identical instrumentation, +3.85 percent, on single unrepeated runs. Two durable
consequences follow.

First: an exact seed position is worth more than the probes it costs. The
Hilbert query runs two descents — resolve at `R_seed = d_seed + L/2 + tie_tol`,
then tight at `R = d_best + L/2 + tie_tol`. A mispredicted position centres the
+/-64 window away from the true neighbourhood, which worsens `d_seed`, which
widens the resolve descent. The seam's value on this query shape is the QUALITY
of the `d_seed` it yields, not the lookup cost it saves. Lookup-cost accounting —
which is what the learned-index literature reports — cannot see that tradeoff at
all, and on this workload it has the wrong sign.

Second, and methodologically the more useful: instrumentation chosen for one
chunk's question can blind the next chunk's. B3b counted the tight descent
because the inflation ratios are defined at the tight radius, which was correct
for B3b and left the resolve descent — the only thing a seed position can affect
— entirely uncounted. So B5's regression appears in wall clock and in nothing
else: all ten emitted counters reproduce B3b digit for digit while the run is
four percent slower. The durable rule: when a component has been proved
correctness-neutral, check before comparing implementations that differ only in
it that the component is also COUNTER-VISIBLE. Correctness-neutral and
cost-neutral are different claims, and only the first was tested.

This also explains the sign disagreement between the two cost models. The
ceiling recorded in advance said the model could save at most 0.13 percent of
counted work; measurement says it cost 3.85 percent of time. Both follow from
the counted work never having included the descent the seed drives. The ceiling
was not wrong about what it measured; it was measuring the wrong thing. B2's
warning that "a segment check is not a mode-invariant unit of cost" therefore
generalizes: a counter is not a unit of time, and a ceiling expressed in counts
bounds nothing about duration.

Counted (B5c, 2026-07-28). Instrumenting the resolve descent converted the
hypothesis above into a measurement, countywide:

```text
                              binary        rmi        ratio
resolve entries / property   141.1742   352.5154      2.497x
resolve nodes / property      70.9135    83.1684      1.173x
window missed                103,242    123,011      38.62% -> 46.01%
mean d_seed / d_best          1.1717     1.5388
max  d_seed / d_best         32.2332   517.3435
tight entries / property      47.5926    47.5926      identical
phase-2 segment checks     11,021.8259 11,021.8259   identical
```

**The exchange rate is the result: the model saves about 20 key probes per
property and spends about 211 extra point-to-segment distance computations to
do it — roughly 10 to 1 in the wrong direction.** The seed-invariant half of the
query is identical to the last digit, which is the counter-side statement of the
byte-identity the CSV comparison already established.

The mechanism is convexity, not miss frequency. Admitted area grows as
`R_seed^2 = (d_seed + L/2 + tie_tol)^2`, so cost is convex in `d_seed / d_best`.
Moving the MEAN ratio from 1.1717 to 1.5388 predicts about 1.72x more entries
under a uniform-density reading; the measured factor is 2.497x, and the excess is
Jensen's inequality plus a heavy tail — the maximum ratio moves from 32.2 to
517.3 while the miss RATE moves only 1.19x. The model does not miss much more
often than binary search; when it misses, it misses far worse, and the cost of a
miss is quadratic. A durable corollary for any predictor feeding a radius: the
mean prediction error is the wrong summary statistic, because the cost function
is convex in it.

An independent finding from the same run, and not about the model: **the exact
binary-search control misses the +/-64 seed window on 38.62 percent of queries.**
A perfect `lower_bound` position still does not put the nearest split segment
within 64 entries on more than a third of properties. That is a statement about
Hilbert locality over extended objects on this data, and it means the seed window
is a live query-design parameter for BOTH rungs rather than a tuning knob for the
learned one. B6 must sweep it upward as well as downward and for both seeders,
and if the best operating point turns out to owe nothing to learning, that
belongs in the benchmark table stated as what it is.

Recorded against over-claiming: the wall-clock difference here is 1.1529 s,
5.92 percent, while two runs of the SAME binary configuration in different chunks
differ by 0.7503 s, 3.85 percent. The timing is therefore consistent with the
counted difference and does not by itself establish it. The counters carry the
claim, because they are deterministic and reproduce exactly across compiler and
platform; B6 still owes a repetition protocol before any wall-clock figure is
asserted.

**Replicated, and the first wall-clock statement that survives its own noise
(B6, 2026-07-29).** The convexity mechanism reproduces at independent operating
points. On the 10,000-property workload the mean `d_seed / d_best` ratio moves
1.2521 (binary) -> 2.0385 (rmi), a 1.628x move predicting about 2.65x more
admitted entries under a uniform-density reading; measured resolve entries move
113.0575 -> 385.7320, a factor of 3.412. Jensen plus the tail accounts for the
excess, as it did countywide.

More consequentially, the counted quantity now PREDICTS the clock. B5c isolated
the marginal cost of one resolve-descent entry at 20.40 ns before any B6 timing
existed. Multiplying that constant by the counted entry difference reproduces
twelve independently measured wall-clock gaps:

```text
                        delta entries   predicted us   measured us   ratio
_10000      W=64           272.675          5.563         5.010      0.901
_100000     W=64           279.542          5.703         5.271      0.924
countywide  W=64           211.341          4.311         4.302      0.998
countywide  W=8..2048      nine points, least-squares slope through the
                           origin: 21.02 ns/entry against the isolated 20.40
```

A mechanism that computes the number is stronger than a mechanism that narrates
it. The caveat travels with it: the per-point ratio degrades once the gap falls
inside the cells' range, so the fit is carried by the resolvable points.

Under the B6 protocol — 7 repetitions, 1 warm-up, blocked by repetition — the
5-v-4 effect at `_10000` is +15.83 percent with NON-OVERLAPPING ranges: the
learned rung's fastest run, 0.406175 s, is slower than the control's slowest,
0.357990 s. B5c's +5.92 percent at n=1 against a 3.85 percent same-configuration
spread could not carry the claim; this can. The durable point is procedural: the
protocol, not the effect, was what changed.

**The cost model is mode-invariant (B6c-2, 2026-07-29).** Two independent
nine-window fits, one in each verification regime, put the marginal cost of a
resolve-descent entry at 21.02 ns (Option A) and 21.19 ns (Option B) — 0.8
percent apart, and both within 4 percent of B5c's isolated 20.40 ns. The
verification mode changes what fraction of the query the index controls; it does
not change what an entry costs. A single Option A cell that came out at 24.02
ns/entry was investigated and is ordinary variance: its gap/range was 1.62,
against five measurements of the same quantity spanning 20.20 to 22.88 ns.

The uncounted `2W` window scan is likewise mode-invariant, at 2.84 ns per entry
under Option A and 3.18 ns under Option B, consistent with the ~3.2 ns the joint
fit returns. The scan never touches verification geometry, so it should not care
about the mode, and it does not.

## 18.23 A two-stage linear RMI binds at the router, not at the leaves

Reason:

B4 fitted 131,072 linear second-stage models over 1,189,589 Hilbert keys and
measured, as a diagnostic, what the same leaf models achieve under a perfect
equi-depth router — routing that cannot be shipped, because it needs stored
boundaries and is therefore a lookup table rather than a linear stage.

```text
                     max error per model    mean last-mile probes
fitted linear root              1,650                      6.323
perfect router                      4                      2.967
```

One line per leaf models the local CDF of this distribution to within a handful
of positions. One line for the whole distribution cannot route to those leaves.
The router accounts for 53 percent of the remaining probe cost and a factor of
412 in maximum error.

The durable rule: when a hierarchical model underperforms, measure the stages
separately before adding capacity. Reporting only the end-to-end error leaves the
two causes confounded, and the obvious response — more leaves — attacks the half
that was already nearly exact. Leaf occupancy in B4 fell from 40.6 percent to
9.50 percent across the sweep precisely because added capacity went where it was
not needed.

This also bounds what the architecture can reach here without changing what
"linear at both stages" means. The remaining error is routing error, and removing
it requires either a nonlinear root or a stored boundary table — both of which
leave the design the phase committed to. That is a statement about where the
capacity binds, not a defect.

---

## 18.24 Structure size and peak memory are different claims

Reason:

B6 measured both for the first time and they disagree in direction. Countywide,
on persistent structure the Hilbert path is 8.74x smaller than the segment BVH —
9,516,712 bytes of keys plus a 4,194,400-byte model against 119,768,836 bytes of
BVH. On peak RESIDENT memory the segment BVH is 1.25x smaller, 185.77 MB against
232.50 MB. On peak COMMITTED memory the Hilbert path is 1.20x smaller, 285.21 MB
against 342.33 MB. Three instruments, two directions.

The attribution is measured, not argued. The BVH's peak resident memory is its
rung-1 baseline plus its index almost exactly (113.27 MB measured against
119.77 MB reported, the gap being working-set trimming), while it commits 257 MB
above baseline — roughly twice its final index — because construction allocates
temporaries the working set never holds simultaneously. The Hilbert path's peak
resident memory exceeds its baseline by 160-166 MB against a 9.5 MB persistent
key array, and that excess is CONSTANT across a 27x range of query count, which
places it in index construction rather than in the query. It remains
unattributed beyond that.

Two consequences. Neither figure may be quoted alone, because "the learned path
uses less memory" and "the learned path uses more memory" are both true of
different quantities. And peak resident memory is the wrong instrument for a
model's size cost specifically: the learned rung's peak exceeds the control's by
53,248 bytes against a 4,194,400-byte model, 1.3 percent of it, because the peak
occurs during index construction before the model is loaded. Report a model's
cost from its bytes and its load-time allocation, never from process peak.

**Verification mode is memory-neutral (B6c-2).** Resident and committed peaks
agree between the two modes to within 0.1 percent at every rung and every
workload, and `index_bytes` is identical. Expected — the mode changes which
geometry is rescanned, not what is stored — but now measured.

**The ~160 MB transient remains unattributed.** A one-property run was intended
to isolate it, on the reasoning that with query cost near zero the peak would be
almost entirely index construction. The run succeeded and reported index
construction at 0.912181 s, but the binary does not print peak memory — the
harness measures it from the parent — and reading the child's peak counters from
a PowerShell one-liner after exit returned empty. The isolation therefore did not
happen. The reliable route is the harness, whose Win32 handle stays valid after
exit; doing so needs a one-property workload registered in the CLI. Recorded as
attempted and unresolved rather than dropped.

---

## 18.25 A null result from an instrument not shown to be live is not a result

Reason:

B6b's first attempt built seven binaries with `-DCAPRM_SEED_WINDOW=8..512`
against a source file that never referenced the macro. A compiler accepts and
discards a `-D` that nothing uses, without a warning. All seven were the default
window.

The countywide neutrality gate PASSED on that build, and could not have done
otherwise: unmodified source produces the canonical digest by construction, so
the gate cannot distinguish "the parameter is present and neutral" from "the
parameter was never added." Had the binaries not self-reported their window, the
sweep would have produced seven identical rows, and the natural reading —
"`SEED_WINDOW` has no measurable effect" — would have been false, publishable,
and consistent with every piece of evidence collected. The eventual measurement
moves the 5-v-4 comparison by 29 percentage points.

The rule: a neutrality gate requires a positive control. Before an identity is
evidence of neutrality, some setting of the same parameter must be shown to
CHANGE something. Here the control was the W=8 build moving
`resolve_entries_per_property` and `fraction_window_missed`; only after that
fired did the W=64 identity mean anything. A build system that cannot fail is
not a check.

Corollary on checksums. MinGW writes a link timestamp into the PE header, so
binaries built seconds apart differ regardless of source. An executable digest
taken without `-Wl,--no-insert-timestamp` records WHEN it was built, not WHAT,
and any provenance argument resting on such a digest is void. This project
treats checksums as provenance, so the flag is not optional.

---

## 18.26 The seed window, not the model, determines the sign of 5 vs 4

Reason:

Measured at nine window sizes on both the 10,000-property and countywide
workloads, both seeders, with byte-identical evidence at every point (B6,
2026-07-29). Countywide:

```text
W        rmi/binary   binary missed   binary resolve   rmi resolve
   8       1.11620        69.88%          167.97           523.04
  64       1.06365        38.62%          141.17           352.52
 512       1.01209        17.13%           87.91           150.06
2048       1.00001        11.84%           77.46            94.19
```

The learned rung converges on its control not by improving but by having its
error made irrelevant: a wide window recovers a good `d_seed` from a bad
position, so `R_seed` shrinks toward `R` and the resolve descent stops being
seed-sensitive. At W = 2048 on the 10,000-property workload every counted
quantity is identical to the last digit and only the control's 20.22 key probes
distinguish the two rungs.

Three durable consequences.

First, 5 vs 4 is CONDITIONAL. Reporting it at one window reports one point on a
monotone curve, and the point the project happened to ship at is not privileged.

Second, both seeders have an interior wall-clock optimum, because the window's
own `2W` scan is unbounded in `W` while the resolve descent it buys has a floor.
At each seeder's own best measured window the learned rung is still slower.

Third, an independent result from the same sweep, and not about the model at
all: the EXACT binary-search control misses its window on 11.84 percent of
countywide queries at W = 2048. Widening from ±512 to ±2048, over an index of
1,189,589 entries, buys 1.3 percentage points. Hilbert locality over extended
objects has a hard core that window size does not reach, and that is a statement
about space-filling curves rather than about learning.

---

## 18.27 The reported benefit of a learned spatial index depends on parameters
## the literature holds fixed and does not report

Reason:

This is the phase's contribution, and it is methodological rather than a
benchmark result. The project set out to ask whether learned indexing helps for
exact nearest-neighbour search over extended objects. It answers that — no, not
here — but the more durable finding is that the question as usually posed is
underdetermined.

Three independent demonstrations, all measured on the same ladder, all with
byte-identical evidence at every point:

```text
axis                 range measured        effect on the comparison
seed window          W = 8 .. 2048         5-v-4: +11.6% -> +0.001% (Option A)
                                                  +21.4% -> -0.1%   (Option B)
verification mode    original vs split     4-v-3: 1.96x -> 5.72x countywide
                                           5-v-4: the PERCENTAGE roughly doubles
                                           while the absolute gap is unchanged
query workload       10K, 100K, 267K       4-v-3: 4.77x -> 1.96x under Option A,
                                           8.48x -> 5.72x under Option B, and the
                                           feature-size counter explains why
```

**The verification mode's effect on 5 vs 4 is a denominator effect, and saying so
is more defensible than "it doubles."** Measured at three workloads (B6c-2):

```text
workload        A %      B %     A us/p   B us/p   counted prediction
_10000        16.45%   17.92%     5.940    5.620         5.563
_100000        5.91%   19.25%     3.590    6.188         5.703
countywide     5.72%   12.16%     4.243    4.482         4.311
```

Option B's ABSOLUTE gap matches B5c's counted prediction at all three workloads
(1.010, 1.085, 1.039). Option A's is erratic, and its worst point, `_100000`, has
a gap smaller than the cell's own spread — gap/range 0.68 — so its +5.91 percent
was never a measurement. The learned rung's penalty is 4.3 to 6.2 microseconds
per property in both columns, exactly as the resolve-descent counter says. What
the mode changes is the denominator: verification is a large shared term that
compresses every percentage toward zero. **The counted quantity is the invariant
and the percentage is the artifact.**

**For 4 vs 3 the mode genuinely misleads.** Rungs 3 and 4 share the verification
term, so under Option A the ratio divides two numbers that mostly consist of the
same thing:

```text
workload        Option A     Option B
_10000           4.765x       8.478x
_100000          2.248x       5.746x
countywide       1.959x       5.723x
```

Under Option B the cost of flattening 2D to 1D is 5.72x countywide and 5.75x at
`_100000` — stable across a 2.7x change in query count. Under Option A it reads
1.96x and drifts with workload. **Option B is the correct column for reporting
4 vs 3**, and any Option A figure for it must be labelled as diluted.

None of these three is reported as a variable in the learned-spatial-index
literature this project reviewed. The seed window is an implementation detail
that never appears; exactness is usually not attempted, so the verification
fork does not exist; and workload composition is treated as a fixed benchmark
rather than as a parameter whose effect is measurable.

Why each one moves the answer:

- **The seed window** determines how much a bad predicted position costs. Wide
  enough, and any seed is as good as any other, so the model's advantage and its
  disadvantage both vanish. A paper reporting a learned win at one window has
  reported one point on a curve.
- **The verification mode** determines what fraction of query time the index
  controls at all. Under byte-identical verification, exact rescanning is ~99
  percent of the work and dilutes every index effect toward zero. A method
  evaluated only in that regime will report small effects regardless of merit.
- **The workload** determines the size of the features near the queries, and the
  feature BVH's cost tracks feature SIZE rather than feature count: 17,377
  segments per candidate feature on one subset against 12,873 countywide, which
  reproduces its 1.6x wall-clock difference exactly.

What this obliges the project to do. Every comparison it publishes names its
window, its verification mode and its workload. Every claim about the learned
rung is stated as conditional on those three. And the negative result is framed
not as "learning did not help" but as "learning did not help HERE, and here is
the parameter space in which that sentence is meaningful" — which is a stronger
claim than the win would have been, and is the half of the section 14b research
question the literature has not measured.

The requirement this places on future work, including PHASE C and any B7: a
result that cannot name the parameter values it holds fixed is not reportable.

---

## 18.28 The Hilbert index costs more to build than to use below ~12,000 queries

Reason:

Index construction is 0.912181 s and is CONSTANT across every workload, because
the index is built from the hydrography and the hydrography does not vary with
the property set (see 14b on query count versus index size). Query cost is linear
in the number of properties. So there is a crossover, and it is measurable rather
than notional:

```text
                       build / query      Option A      Option B
_10000    (Q = 10K)                        252.5%        290.8%
_100000   (Q = 100K)                        15.0%         28.4%
countywide (Q = 267K)                        4.6%          9.3%

build equals query at        Q = 12,301 (Option A)   Q = 24,749 (Option B)
```

Two consequences. Below roughly twelve thousand properties the Hilbert path
spends more time constructing its index than using it, and the threshold doubles
in the faster verification mode because the query it must amortise against is
cheaper. And `_10000` is therefore structurally unsuited to a wall-clock claim,
independently of the composition argument in 18.19 — build cost dominates the
thing being measured by two and a half times.

Any end-to-end claim about this path states whether index construction is
included, and at what query count.

---

## 18.29. One defect shape, six sites: a dimension the code does not know is a dimension

The single most repeated engineering error in PHASE B was not arithmetic. It was
a grouping key that omitted a dimension the data actually varied along, and its
signature is that it produces a plausible number rather than an error.

The canonical instance: `by_algorithm[row["algorithm"]] = row` inside a loop over
a workload group. Feed it a frame containing two verification modes and the
second assignment overwrites the first, so the function emits one complete-looking
set of comparisons drawn from whichever mode happened to iterate last, records no
mode on the output, and raises nothing. Measured on the `b6c2` artifact, it
dropped Option A entirely.

Fixing mode then exposed the same shape in INVOCATION at four further sites — the
cost model's sweep population, the cost model's population key, the adjacent
comparisons, and the access-pattern fit. Every one announced itself as a number
moving rather than as a failure: a slope drifting 21.02 to 21.46, a granularity
ratio reading 6.540x instead of 6.905x, an R^2 falling from 0.99 to 0.69, a
residual search cost going negative.

The rule extracted: **a dimension along which the data varies belongs in the
grouping key, not in a filter applied afterwards and not in a convention the
author remembers.** A filter can be forgotten at one call site. A key cannot.
Where a comparison genuinely must cross a boundary, it is emitted WITH that fact
attached rather than suppressed or silently allowed — `crosses_invocation` is a
column, not a policy.

The corollary for a reviewer: an analysis layer that has never been fed data
varying along a dimension has not been tested against that dimension, however
carefully it was written. `ladder_analysis.py` was correct for as long as every
artifact it read was Option A.

## 18.30. The learned rung's sign is not fixed, and it crosses

Nucleus 18.27 recorded that the reported benefit of a learned spatial index
depends on parameters the literature holds fixed. B6d strengthened that from a
statement about magnitude to a statement about sign.

```text
countywide original   W8 1.11620  ->  W2048 1.00002
countywide split      W8 1.21402  ->  W2048 0.99875
```

At W=2048 under split-geometry verification the learned rung is FASTER than its
exact control. The same code, the same index, the same 1,189,589 entries, the
same byte-identical output — and the direction of the headline comparison is set
by a compile-time constant and a verification-mode argument that no paper in this
literature reports.

This is why the project publishes the absolute microseconds-per-property gap
beside every ratio. Across all six cross-product cells the 5-v-4 absolute gap
holds between 4.442 and 6.188 us/property while the percentage ranges 7.2 to
19.2. The counted quantity is the invariant; the percentage is an artifact of how
much shared verification work sits in the denominator. A percentage that moves
2.7x while the underlying cost moves 1.4x is measuring the denominator.

## 18.31. Decomposing search from verification, and why it needs an outside number

Search cost is mode-invariant: the traversal does not know which geometry the
kernel will later rescan. For one rung measured in both modes that gives two
equations in three unknowns, and adding a second rung appears to close the system
exactly — four equations, four unknowns, no assumption required.

**The exactly-determined solve is unusable, and its failure is the finding.** Both
rungs' check-count ratios are ~1.45, so the two constraints are nearly collinear.
On the countywide cross-product it returns a rung-3 search cost of -6.82
us/property with a per-check ratio of 2.27x against the 4.21x B2 measured
independently. An exactly-determined system is not a well-conditioned one.

The decomposition is therefore ANCHORED: rung 3's search is a known small
fraction of its query time (~0.4 percent counted at B1, ~0.6 percent at B6c-2),
the per-check costs follow, and the validation is out-of-sample — rungs 4 and 5
never enter the calibration, and their search estimates must agree between modes.
They do, to 1.0-2.6 percent at five of six cells.

Two boundaries the method has, both found by measurement rather than argument:

- **It applies to rungs 3-5 only.** Applied to rungs 1-2 it gave brute force a
  search cost of -2,261 us/property. A brute-force check and a segment-BVH check
  are not the same unit of work; B2's rule that counts are comparable within a
  mode and not across implementations that verify differently extends to this.
- **Non-negativity is a necessary condition, not a sufficient one.** The retained
  diagnostic's `usable` flag tests only that the implied search cost is positive.
  On one invocation group the solve passes that test and still returns a per-check
  ratio of 0.575x — implying Option B checks cost more than Option A, contradicting
  B2 by a factor of seven. A sanity check that admits an answer contradicting an
  independent measurement is not yet a gate, and it is documented as a diagnostic
  rather than promoted to one.

## 18.32 A blocked split's reported error is a property of its seed

Reason:

C1 held the separation fixed and varied only which blocks the hash assigned,
across ten seeds and four geometries:

```text
geometry                  test-mean-label range   baseline RMSE range   R^2 range
b2000 0.70/0.15 w625            9.82 pts               6.58            -0.885 … 0.042
b3000 0.60/0.20 w625            7.29 pts               3.05            -1.086 … -0.128
b4000 0.50/0.25 w2125          11.94 pts              18.69            -4.514 … 0.573
b8000 0.60/0.20 w2125          13.14 pts              11.58            -2.325 … -0.110
```

Population mean 34.632, sigma 13.064. The seed moves the test set's own mean by
up to one sigma, and at b=4000 moves the baseline RMSE by more than the RMSE
itself. At b=8000 a nominal 70/15/15 realises as 31/2/9 blocks — a two-block
validation set.

This is 18.26 and 18.27 arriving in the PARTITION rather than the index: the
reported quantity's magnitude, and here its sign, set by a parameter the
literature holds fixed and does not report.

C1 adopted blocked K-fold in response — every occupied block is test exactly
once and validation exactly once, so no block selection is left for a seed to
make. It reduces the leverage without removing it: aggregate baseline RMSE range
falls to 2.48, and the test set's mean tracks the population within 2.7 points
instead of 13, but coverage still swings 89,344 to 130,187 properties, because
the seed still sets fold composition and fold composition sets which properties
survive erosion.

The operating rule that follows: **a PHASE C result is reported across the five
recorded seeds, and a single-seed figure is a diagnostic, never a claim.** The
comparison that survives this is one between non-overlapping RANGES, not one
between two point estimates.

## 18.33 A holdout must be isolated from validation, not only from training

Reason:

The Roadmap's completion gate constrains holdout against TRAINING. Measured at
C1, the minimum test-to-validation separation under that gate was 5.9 to 9.8 m —
touching. Validation is seen during model selection, so that is a selection
leak: second order against the training leak, and real.

Isolating test from both cost 32 percent of test coverage and moved the
nearest-neighbour baseline RMSE by 0.2. The cost was paid, because a leak that
has been measured and then left in place is worse than one that was never
looked for.

Two general rules follow. First, a separation guarantee must name every split
the model saw in any capacity, not only the one it fitted on. Second, a flag
that turns such a guarantee off is only credible if a test shows it changes
something — `test_build_kfold_leaves_test_beside_validation_when_isolation_is_off`
exists for exactly that reason, and it is the same requirement 18.25 places on a
neutrality gate.

## 18.34 A geometric criterion and a grid criterion are not interchangeable

Reason:

The Roadmap's C1 gate was worded on the block grid: no test property within one
block of a training property. C1 measured it and found it unachievable. At a 70
percent train block share every occupied block has a training block within
Chebyshev separation 1, so `min_chebyshev_to_train` is 1 in every configuration
tested, and the grid criterion cannot hold for any partition that retains a test
set unless training rows are also dropped.

Nor does either criterion imply the other. Points in Chebyshev-adjacent blocks
can be up to `2*b*sqrt(2)` apart; points `s` metres apart can still share a
block edge. The project therefore states the metric criterion as binding,
measures both, and reports the grid figure beside it rather than deriving one
from the other.

One trap inside the grid figure is worth naming because it produces a plausible
number rather than an error: the Chebyshev separation must be minimised over ALL
training blocks, not read off the block of the metrically nearest training
property. Those are different quantities — the closest training point in metres
need not sit in the grid-closest training block — and conflating them is the
18.29 defect shape in a new place.

The boundary itself is `>=`, not `>`. Two points on the facing edges of an
`s`-wide gap are exactly `s` apart, and an assertion written `>` is a latent
failure that fires once, on a rerun, for no reason a reader can reconstruct.

## 18.35 A commit that depends on an untracked file passes every local check

Reason:

C1's first commit shipped `spatial_kfold.py`, which imports `caprm.split_gate`,
without shipping `split_gate.py`. It was pushed. Every local check passed —
`git status` was clean for what was staged, the full test suite was green, the
module imported — because the missing file was sitting in the working directory
the whole time. A clean checkout of that commit cannot import the module or
collect its tests.

The general shape: **a check performed in the environment that contains the
defect cannot detect it.** This is 18.25's positive-control rule applied to the
repository rather than to a build flag, and the fix is the same in kind — run
the check somewhere the defect would have to show:

```powershell
git clone --depth 1 . $env:TEMP\caprm-verify
cd $env:TEMP\caprm-verify
python -m pytest -q
```

A clean clone that cannot collect its own tests is a repository that does not
reflect the validated implementation, whatever the working tree says. This is
step 6.5 of the commit sequence.

# 19. Repository Structure and Current Source Responsibilities

The repository is organized around code, configuration, documentation, tests,
data staging, and generated outputs.

```text
caprm-flood/
├── configs/                 Workload YAML (1K, 10K, 100K, countywide)
├── cpp/spatial_core/
│   └── src/                 fema_pip_dev, water_distance_bruteforce,
│                            water_distance_indexed, water_distance_segment_bvh,
│                            water_distance_hilbert
├── docs/                    Methods, policy, milestone, and source documentation
├── models/                  Trained model artifacts (TRACKED, not ignored;
│                            Milestone 4 B4 onward)
├── python/
│   ├── caprm/               Library modules
│   └── scripts/             CLI entry points
├── tests/                   Python test suite
│   └── cpp/                 C++ unit suites (Milestone 4 B1/B2)
├── data/                    Cached source and derived data (Git-ignored)
├── outputs/                 Generated artifacts (Git-ignored)
├── .gitignore
├── README.md
└── requirements.txt
```

Library modules:

```text
python/caprm/audit.py            Product structure and provenance auditing
python/caprm/rmi.py              Recursive model index: fit, exhaustive bound,
                                 domain bound, serialization (Milestone 4 B4)
python/caprm/baseline.py         FEMA point-in-polygon reference
python/caprm/crs.py              CRS normalization
python/caprm/evidence.py         Integrated FEMA + water evidence
python/caprm/export.py           C++ input export
python/caprm/hydrography.py      USGS 3DHP ingestion and cache
python/caprm/ingest.py           Configuration and path resolution
python/caprm/scoring.py          Component scores and exposure index
python/caprm/sensitivity.py      Rank-stability analysis
python/caprm/study_area.py       County boundary and buffered study area
python/caprm/terrain.py          DEM sampling and terrain metrics
python/caprm/validate.py         Python/C++ comparison contracts
python/caprm/water_benchmark.py  Benchmark harness support
python/caprm/water_distance.py   Nearest-water reference
python/caprm/water_export.py     Water C++ input export
python/caprm/water_validate.py   Water comparison contracts
```

Key C++ sources:

```text
cpp/spatial_core/src/fema_pip_dev.cpp
cpp/spatial_core/src/water_distance_bruteforce.cpp        implementation 1
cpp/spatial_core/src/water_distance_indexed.cpp           implementation 2
cpp/spatial_core/src/water_distance_segment_bvh.cpp       implementation 3 (B1)
cpp/spatial_core/src/water_distance_hilbert.cpp           implementations 4/5
                                                          (B3/B4/B5)
```

Implementations 3, 4 and 5 are built by `#include`-ing the file below them, so
the exact point-to-segment kernel, the tie tolerance and the tie rule are reused
unchanged rather than reimplemented. `water_distance_hilbert.cpp` is one binary
covering both rungs 4 and 5; they differ only at the seed seam behind `--seed`.

Current `docs/` contents:

```text
docs/canon/                    The three canonical documents (moved from docs/
                               on 2026-07-29): Nucleus, Current Status, Roadmap.
                               Precedence order is defined in section 26.
docs/benchmark_results.md      Nearest-water benchmark methodology and results
docs/crs_policy.md             Canonical operational CRS policy
docs/data_sources.md           Source provenance, vintages, inclusion rules, limits
docs/milestone_1.md            Milestone 1 method and results
docs/milestone_2.md            Milestone 2 method and results
docs/scoring_methodology.md    Scoring behavior, influence, sensitivity
docs/validation.md             Validation contract and agreement results
docs/report/                   In-progress report sections
```

The primary C++ correctness claim rests on field-by-field comparison against the
Python reference over the full property-ID union, not on self-authored unit
assertions. This is a deliberate consequence of the validation architecture:
comparison against an independent implementation is a stronger check. It should
be stated plainly rather than implied.

Superseded at B1/B2 (2026-07-28): the project now also carries two C++ unit
suites, `tests/cpp/test_water_segment_bvh.cpp` (80,021 checks) and
`tests/cpp/test_water_segment_bvh_verify_modes.cpp` (607 checks), for geometric
invariants that have no Python counterpart to compare against. They supplement
the comparison harness; they do not replace it. Earlier statements in this
document that there are no C++ unit tests were true before B1 and are not now.

The repository should be understood by reading the code and current
documentation together. Historical nucleus/proposal documents may contain
planned items that have since been completed, changed, or deferred.

---

# 20. Git and Repository State

GitHub repository:

```text
https://github.com/salexander-git/caprm-flood
```

Primary branch:

```text
master
```

The current commit, synchronization status, and exact artifact checksums are
recorded in `CAPRM_Flood_Current_Status.md` rather than here, because they
change with every completed task and this document records durable facts.

Some local presentation, Word-document, editor, and temporary inventory files
remain intentionally untracked and are not part of the canonical source
repository.

`models/` is an exception to the "generated artifacts are ignored" rule and is
tracked deliberately: `outputs/` is Git-ignored, and the C++ query path must
load the trained model at run time, so the artifact cannot live there. Verified
at B5 (2026-07-28) that no ignore rule matches it, so no force-add is required.

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

As of July 28, 2026:

- Milestones 1, 2, and 3 are complete, validated, and frozen.
- Milestone 3 delivered countywide terrain evidence, a four-component exposure
  index at scoring policy `preliminary_exposure_index_v2`, measured component
  influence, rank-based sensitivity analysis, an automated product audit, and
  a reproducibility runbook. The measured sensitivity verdict is moderately
  sensitive. The suite passed at 181 tests then and passes at 257 now, the
  growth being Milestone 4's own tests.
- **Milestone 4 is index structure and learned approximation.** See section
  14b. It adds no evidence family. PHASE B chunks B1 through B5 are complete
  and validated countywide: the five-rung ladder is built and every rung that
  claims exactness has been shown to produce byte-identical evidence. The
  learned rung is measured SLOWER than its control, for a reason recorded in
  18.22, and the benchmark that reports it is B6.
- **Precipitation is a gated stretch goal**, permitted only after the Milestone 4
  computational work is complete and documented. See section 14b.
- The exposure index is frozen as-is and remains preliminary. It is no longer
  the subject of active work.
- Report and poster work follow Milestone 4.

The precise remaining tasks should be read from `CAPRM_Flood_Roadmap.md`.

The exact latest implementation and output state should be read from
`CAPRM_Flood_Current_Status.md`.

---

# 26. Handoff Protocol for a New AI Assistant

A new assistant continuing this project should begin by reading:

1. `docs/canon/CAPRM_Flood_Project_Nucleus_2026-07-15.md`
2. `docs/canon/CAPRM_Flood_Current_Status.md`
3. `docs/canon/CAPRM_Flood_Roadmap.md`
4. `docs/scoring_methodology.md`
5. `docs/crs_policy.md`
6. `docs/data_sources.md`
7. `docs/Professor_Milestone_Requirements.txt`
8. the current GitHub repository

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

CAPRM-Flood is a reproducible C++/Python geospatial evidence-extraction
framework for large-batch property-to-hazard spatial joins, demonstrated
through a property-level relative flood-exposure indexing workload for Monroe
County, New York. The system ingests property coordinates and public hazard
data, derives validated FEMA flood-zone, nearest-water, and terrain evidence,
preserves source provenance and deterministic behavior, compares independent
Python and C++ spatial implementations for correctness and performance, and
feeds validated evidence into an explicit four-component scoring layer that
produces relative exposure scores and regional rankings. The project's central
engineering values are correct spatial computation, CRS discipline,
deterministic outputs, source-family evidence separation, independent
validation, manifests that can reproduce the results they describe,
benchmarkable implementations, and reproducible workflows. As of July 28, 2026,
Milestones 1 through 3 are complete and frozen: three evidence families
spanning three different data topologies produce one evidence contract for
267,362 properties, the exposure index is characterized as moderately sensitive
to weight choice with immovable extremes, the test suite passes at 257 tests,
and the product audit reports no failures. Milestone 4 concentrates the
project's computer-science contribution on a question the project's own
Milestone 2 benchmark raised: the Feature BVH examines only 5.498 candidate
features per property yet still performs 70,771 segment checks, because it
indexes features rather than geometry and the largest water features are near
everything in the county. Rebuilding the index at segment granularity leads
somewhere the literature has not been, because learned spatial indexes are
evaluated almost exclusively on point data and several return approximate
results, whereas this project's data is extended objects and its query is exact
nearest neighbour. Milestone 4 therefore asks whether learned indexing extends
to exact nearest-neighbour search over line segments and polygon boundaries,
and as of B6d its answer on this workload is a measured negative that is
CONDITIONAL and now fully characterized — the ported model reproduces its
control's evidence byte for byte and runs the countywide query 7.2 percent slower
at the shipped operating point, because the value of an exact seed position here
is the quality of the search bound it yields rather than the lookups it saves,
but that penalty falls to 0.002 percent by seed window 2048 and reverses outright
under split-geometry verification, where the learned rung is 0.125 percent
FASTER; the transferable claim is therefore not that learning failed but that the
reported benefit of a learned spatial index depends on parameters this literature
holds fixed and does not report —
characterizes the search-radius inflation that representative-point ordering
imposes on extended objects, isolates the contribution of learning from the
contribution of dimensionality reduction using a binary-search control, and
verifies exactness field-by-field against an independent implementation rather
than assuming it. Precipitation remains a gated stretch goal behind that depth.