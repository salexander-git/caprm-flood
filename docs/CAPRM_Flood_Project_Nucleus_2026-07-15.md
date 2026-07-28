# CAPRM-Flood Project Nucleus — 2026-07-28

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

# 19. Repository Structure and Current Source Responsibilities

The repository is organized around code, configuration, documentation, tests,
data staging, and generated outputs.

```text
caprm-flood/
├── configs/                 Workload YAML (1K, 10K, 100K, countywide)
├── cpp/spatial_core/
│   └── src/                 fema_pip_dev, water_distance_bruteforce,
│                            water_distance_indexed
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
cpp/spatial_core/src/water_distance_bruteforce.cpp
cpp/spatial_core/src/water_distance_indexed.cpp
```

Current `docs/` contents:

```text
docs/benchmark_results.md      Nearest-water benchmark methodology and results
docs/crs_policy.md             Canonical operational CRS policy
docs/data_sources.md           Source provenance, vintages, inclusion rules, limits
docs/milestone_1.md            Milestone 1 method and results
docs/milestone_2.md            Milestone 2 method and results
docs/scoring_methodology.md    Scoring behavior, influence, sensitivity
docs/validation.md             Validation contract and agreement results
docs/report/                   In-progress report sections
```

There are no C++ unit tests. Every C++ correctness claim rests on
field-by-field comparison against the Python reference over the full
property-ID union. This is a deliberate consequence of the validation
architecture: comparison against an independent implementation is a stronger
check than self-authored unit assertions. It should be stated plainly rather
than implied.

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

As of July 16, 2026:

- Milestones 1, 2, and 3 are complete, validated, and frozen.
- Milestone 3 delivered countywide terrain evidence, a four-component exposure
  index at scoring policy `preliminary_exposure_index_v2`, measured component
  influence, rank-based sensitivity analysis, an automated product audit, and
  a reproducibility runbook. The measured sensitivity verdict is moderately
  sensitive. The suite passes at 181 tests.
- **Milestone 4 is index structure and learned approximation.** See section
  14b. It adds no evidence family.
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

1. `docs/CAPRM_Flood_Project_Nucleus_2026-07-15.md`
2. `docs/CAPRM_Flood_Current_Status.md`
3. `docs/CAPRM_Flood_Roadmap.md`
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
benchmarkable implementations, and reproducible workflows. As of July 16, 2026,
Milestones 1 through 3 are complete and frozen: three evidence families
spanning three different data topologies produce one evidence contract for
267,362 properties, the exposure index is characterized as moderately sensitive
to weight choice with immovable extremes, the test suite passes at 181 tests,
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
characterizes the search-radius inflation that representative-point ordering
imposes on extended objects, isolates the contribution of learning from the
contribution of dimensionality reduction using a binary-search control, and
verifies exactness field-by-field against an independent implementation rather
than assuming it. Precipitation remains a gated stretch goal behind that depth.