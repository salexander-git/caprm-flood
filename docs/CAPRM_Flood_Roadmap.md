# CAPRM-Flood Roadmap — 2026-07-16

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

As of July 16, 2026:

```text
Milestone 1: complete and validated
Milestone 2: complete and validated
Milestone 3: complete and frozen
Milestone 4: index structure and learned approximation — starting
```

Current countywide workload:

```text
267,362 unique property IDs
```

Implemented evidence families, spanning three data topologies:

```text
1. FEMA flood-hazard evidence      vector polygons
2. nearest-water / hydrography     vector lines and areas
3. terrain / elevation             raster grid
```

Derived layer, frozen and no longer under active work:

```text
exposure index, scoring policy preliminary_exposure_index_v2
verdict: moderately sensitive to component weights
```

Next priority:

```text
B1. Measure the maximum segment length, then rebuild the index at
    segment granularity
```

**Why the roadmap changed.** Milestone 3's feedback was that the project's
statistics were sound and its computer-science contribution had stalled after
Milestone 2's Feature BVH. That is correct: terrain sampling is array reads,
the scoring layer is a dot product, and the sensitivity sweep is forty dot
products. The Milestone 2 benchmark contains an unexploited algorithmic result
— see `CAPRM_Flood_Current_Status.md` section 19b — and Milestone 4 pursues it
rather than adding a fourth data source that would add no algorithmic content.

Precipitation is retained as a gated stretch goal. See section 8b.

---

# 2. Roadmap Overview

```text
PHASE A   Finish Milestone 3                                COMPLETE
PHASE B   Learned indexing of extended spatial objects      current
PHASE C   Neural surrogate
PHASE D   Engineering hardening
PHASE E   Final academic deliverables
PHASE S   Precipitation — gated stretch goal
```

Phases B and C are Milestone 4. Together they answer one question:

> The exact geometric computation is expensive. What are the ways to make it
> cheap, what does each cost, and how do you know?

```text
B   learn where to look   -> a learned spatial index.  Still exact. Faster.
C   learn the answer      -> a neural surrogate.       Approximate. Fastest.
                                                       The error is structured.
```

Pursuing B leads somewhere the literature has not been. Learned spatial indexes
are evaluated almost exclusively on point data, and several return approximate
results. This project's data is extended objects and its query is exact nearest
neighbour. See Nucleus section 14b.

Both are measured against an exact baseline whose correctness is already proven
field-by-field against an independent implementation. That combination — an
approximate method, and infrastructure that can prove exactly how wrong it is —
is what the project has and the literature generally does not.

B7 closes the loop: the surrogate's distance field can seed the exact query's
search radius, which makes C load-bearing for B rather than parallel to it.

Phases D and E are unchanged in intent. Phase S is gated behind B, C, and their
documentation.

---

# 3. PHASE A — Finish Milestone 3

Milestone 3 should end with a stable, validated terrain evidence product and a defensible preliminary multi-component relative exposure index.

The goal is not simply to confirm that a score can be computed. The goal is to make the scoring implementation explicit, testable, interpretable, and robust enough to support later expansion.

---

## A1. Reconstruct and Audit Current Scoring Behavior — COMPLETE

Delivered `docs/scoring_methodology.md` at commit `683af3f`, reconstructed
from source and confirmed against measured artifacts via
`python/scripts/summarize_scoring_inputs.py`.

The reconstruction registered nine defects, of which two blocked A3.

---

## A2. Harden Scoring Methodology — COMPLETE

### Delivered

Scoring policy bumped to `preliminary_exposure_index_v2`. 44 tests.

**Flattened the terrain sub-weights.** The v1 terrain component applied
`0.60 * absolute + 0.40 * relative` as literals in the function body. They
were absent from `DEFAULT_WEIGHTS`, unchecked by `validate_weights`, and
absent from every manifest. Scoring is linear, so the nesting was
algebraically pointless: `0.25 * 0.60 = 0.15` and `0.25 * 0.40 = 0.10`
produce an identical composite, verified across the countywide workload at a
maximum absolute difference of `5.0e-13`. The cost was not cosmetic: **the
manifest could not reproduce the score.** Now four components, four declared
weights.

**Threaded weights through the pipeline.** `build_exposure_index.py` gained
`--weights`; the manifest records the weights actually applied plus
`weights_are_default`; `summarize_exposure_index` requires weights as an
argument rather than defaulting. Under v1, every sensitivity scenario would
have reported the baseline configuration. This unblocked A3.

**Unrecognized FEMA zones raise.** A matched property in a zone absent from
`FEMA_ZONE_SCORES` previously fell to the unmatched default of 0.0, below
zone X's 10.0, inverting the severity ordering with no error. Latent rather
than active: all five occurring zones are enumerated. A future NFHL vintage
would activate it.

**Removed the SFHA override.** `is_sfha & score < 80 -> 90` was unreachable:
all 5,061 SFHA properties already score 80 or above from zone alone. `is_sfha`
is retained as a validation cross-check enforcing that a property cannot be
SFHA without matching a polygon.

**Dropped slope from the required columns.** Slope is extracted and preserved
as terrain evidence but does not enter any component, so requiring it would
reject a terrain table over a column scoring never reads.

**Added measured influence reporting.** `component_influence` reports each
component's weight, standard deviation, exact variance share by covariance
decomposition, and Spearman correlation with the composite.

**Rounded the composite before ranking.** See the design decision in section
8. Discovered by A4's audit: recomputing the percentile from the stored index
disagreed by up to `1.066e-02` percentile points.

### Component redundancy, measured

`python/scripts/summarize_component_correlation.py` was written before any
weight decision, because choosing weights without knowing whether components
are redundant is guessing.

```text
maximum pairwise Spearman: 0.152 (fema <-> water)
water <-> terrain_absolute: 0.102
terrain_absolute <-> terrain_relative: -0.006
```

The components are near-orthogonal. The specific hypothesis tested and
rejected: that low absolute elevation was shadowing water distance, since the
county's elevation floor is 75.0 m and Lake Ontario sits at ~74.2 m. Water
distance is local, so it does not track regional elevation.

---

## A3. Implement Sensitivity Analysis — COMPLETE

### Verdict

```text
moderately sensitive
```

40 scenarios: 1 baseline, 1 equal, 8 single-component emphasized or
deemphasized, 2 terrain-family, 24 seeded Dirichlet perturbations, 4
reference corners. 38 tests.

```text
minimum Spearman:              0.875  (equal weighting)
median Spearman:               0.996
minimum top-decile overlap:    0.761  (equal weighting)
median top-decile overlap:     0.946
reference corner Spearman:     0.167 - 0.893
```

Thresholds were declared in `caprm.sensitivity` before any result was
measured. A threshold chosen to fit the result it judges makes the verdict
unfalsifiable.

### The metrics discriminate

Three of four components are percentile ranks, and reweighting a linear sum of
rank variables tends to preserve order, so a high correlation could have been
an artifact of the design rather than a finding. The reference corners
establish the floor: they span 0.167 to 0.893, so the metric can tell
configurations apart and the plausible-scenario results can be interpreted.

Without that calibration the analysis would have been uninformative, and the
honest report would have been "our sensitivity metric cannot discriminate"
rather than "our index is stable."

### Framing — resolved by measurement

The question of whether the index "surfaces exposure FEMA's maps miss" or is
"a water-proximity ranking with a FEMA bonus" was deferred to A3 rather than
decided in advance.

Measured: `water_only` correlates 0.893 with the baseline; `equal` correlates
0.875. Putting all weight on water alone reproduces the baseline ranking
better than weighting all four components equally. The second framing is
closer to the truth. The index is a water-proximity ranking with a decisive
FEMA correction on the 1.9% of properties FEMA has information about,
adjusted by terrain.

This follows from water's 65% variance share. Equal weighting cuts water to
25% and promotes `terrain_relative`, which correlates 0.167 with the baseline
ranking, from 0.10 to 0.25.

### The verdict hinges on one scenario

Every other plausible scenario sits near 0.996. `equal` alone falls below the
stable bar. This is not general instability; it is one specific sensitivity:
the index is stable unless you stop privileging water.

`equal` stays in the family. "Weight everything the same because I don't want
to assume" is the most obvious default a reviewer would reach for.

### Extremes versus middle

```text
top-ranked properties:     0.0004 percentile range across 36 scenarios
median property:           18.0
77.6% of properties:       > 10 points
25.8% of properties:       > 25 points
```

All 20 most-unstable properties have a baseline percentile between 59 and 66.
The index reliably identifies the extremes; the middle ordering depends on
weighting assumptions.

### Outputs

```text
python/caprm/sensitivity.py
python/scripts/analyze_scoring_sensitivity.py
tests/test_sensitivity.py
outputs/analysis/scoring_sensitivity_summary.csv
outputs/analysis/scoring_sensitivity_property_shifts.csv
outputs/validation/scoring_sensitivity_manifest.json
outputs/validation/scoring_sensitivity_summary.md
```

---

## A4. Audit Terrain and Index Evidence Products — COMPLETE

### Result

```text
pass 49   warn 1   fail 0
```

The single warning is the manifest schema divergence recorded below. Exits
nonzero on any failure. 38 tests.

### Design principle

The audit checks what nothing else checks. `build_exposure_index` already
raises on row loss, duplicate IDs, CRS mismatch, and out-of-range values;
re-testing those would be theater. The audit reads the **stored artifacts**
rather than the code that produced them, so it catches drift the unit tests
cannot see.

Its highest-value check is the **manifest checksum**. Each manifest records
`output_sha256`, and nothing else in the pipeline verifies that hash still
matches the file on disk. If an artifact is regenerated without its manifest,
the two diverge silently and every provenance claim about the artifact
becomes false.

It also recomputes derived fields from their inputs: relative elevation from
elevation minus local mean, and the composite from the manifest's weights
applied to the component columns. And it compares **property-ID sets** across
the product chain, not just counts: two products can hold the same number of
rows and disagree about which properties they describe.

### What it found

Recomputing the percentile from the stored index disagreed by up to
`1.066e-02` percentile points. Diagnosed as float noise splitting
mathematically identical composites; resolved by the composite rounding
described in section 8. Nothing else in the project would have caught this.

### Manifest schema divergence — documented, not unified

```text
property_flood_evidence_countywide_manifest.json   evidence_summary / output_csv
property_terrain_evidence_countywide_manifest.json summary / output
property_exposure_index_countywide_manifest.json   summary / output
```

The Milestone 2 evidence manifest predates the convention used by the
Milestone 3 manifests. Unifying would require regenerating a validated
upstream product, rerunning the FEMA baseline, water baseline, and both C++
comparisons, for a cosmetic gain. Deliberate decision:
`caprm.audit.manifest_field` reads both and records which convention each
artifact uses.

### Outputs

```text
python/caprm/audit.py
python/scripts/audit_milestone3_products.py
tests/test_audit.py
outputs/validation/milestone3_audit.json
```

---

## A5. Regenerate and Freeze Final Milestone 3 Artifacts — COMPLETE

All Milestone 3 artifacts regenerated under
`preliminary_exposure_index_v2` on 2026-07-16.

```text
python -m pytest -q
181 passed
```

```text
tests/test_scoring.py       44
tests/test_sensitivity.py   38
tests/test_audit.py         38
pre-existing modules        61
```

Frozen artifacts and checksums:

```text
outputs/evidence/property_terrain_evidence_countywide.csv
  sha256 e7768c538b41639032af176bd789bec76137c29348bc9be931ca7b4c44e5d3de

outputs/index/property_exposure_index_countywide.csv
  sha256 3cae2e830a5867bee4d51a36f1c5c04f05ee0a6a26d64dace27da75d3c4911b0
```

Final statistics are recorded in `CAPRM_Flood_Current_Status.md` sections 12,
14, 14b, 14c, and 14d.

Terrain preparation and terrain evidence were not regenerated: `terrain.py`
and `prepare_terrain_raster.py` were unchanged by A2 through A4, and the
terrain artifact's manifest checksum verifies against the file on disk.

---

## A6. Complete Milestone 3 Reproducibility / Runbook Documentation — COMPLETE

### Delivered

```text
docs/milestone_3.md            Runbook: prerequisites, environment, source
                               acquisition, nine pipeline steps with exact
                               commands, validation criteria, and the known
                               asymmetries a reproducer will hit
docs/data_sources.md           Terrain section added; scope corrected from
                               four sources to five
docs/crs_policy.md             Terrain, vertical datum, and distortion
                               sections added
.gitignore                     Editor state and regenerable scratch excluded
inventory_repository.py        EXPECTED_PATHS refreshed
```

### What the terrain documentation established

The DEM source is confirmed as USGS 3DEP seamless 1/3 arc-second by
arithmetic rather than by filename: the manifest's pixel size of
`9.259260e-05` degrees times 3600 is `0.3333` arc-seconds.

Facts that were previously unrecorded anywhere:

- the cached DEM is a **clipped extract**, roughly 0.68 by 0.50 degrees, not
  a standard 1x1 degree tile;
- the projected pixel is **8.601124 m**, chosen by
  `calculate_default_transform` rather than specified, because a 1/3
  arc-second cell is not square on the ground at 43 degrees latitude;
- therefore the 90 m sampling radius is **11 pixels**, and the local
  neighborhood is a **23 x 23 box roughly 198 m across**, not a 90 m circle;
- resampling was **bilinear**, which smooths and makes slope and
  relative-elevation magnitudes marginally conservative;
- elevations are **NAVD88 meters**. The project had no vertical datum
  recorded before terrain existed.

### Corrections this chunk forced

**The lake-level plausibility claim was overstated.** Lake Ontario's
low-water datum of ~74.2 m is published in IGLD85, not NAVD88. The two differ
by up to roughly a meter in the Great Lakes basin, so the 75.0 m elevation
floor is an approximate consistency check, not the tight agreement previously
implied.

**Monroe County sits near the western edge of UTM zone 18N.** The zone spans
78W to 72W with its central meridian at 75W; the terrain raster's western
bound is 78.020W. The scale factor runs about 1.00003 to 1.00033 across the
county, so planar distances are overstated by up to roughly 0.3 m per
kilometre. Negligible for this work, but it is the honest counterpoint to the
project's `4.658e-10 m` Python/C++ agreement: that figure measures
implementation agreement, not accuracy. The projection alone contributes
roughly 0.9 m to the 2.63 km maximum observed water distance.

**Two limitations were promoted from unknown to recorded**, not solved:

- the DEM has no download script and no recorded retrieval date, and USGS
  updates the seamless layer continually, so the checksum is the only thing
  pinning which elevation data produced the results. FEMA shares this;
- a property within 11 pixels of the raster edge has its local mean computed
  over fewer cells. Zero missing slope values prove no property lies within
  one pixel of the edge; they do not prove none lies within eleven.

### Encoding

Verified: `Select-String -Encoding UTF8` for mojibake sequences across
`docs/*.md` and `README.md` returned no matches. The repository's Markdown is
correct UTF-8. Earlier apparent corruption was PowerShell 5.1 defaulting to
cp1252 on `Get-Content`, a display artefact only. Use `-Encoding UTF8` when
inspecting these files.

### Completion gate

Met. `docs/milestone_3.md` documents required external datasets, expected
local paths, environment setup, dependency installation, exact script order
with arguments, expected inputs and outputs with checksums, the work each step
performs, Git-ignored outputs, success validation, manifest regeneration, and
known limitations.

---

# 4. PHASE B — Learned Indexing of Extended Spatial Objects

## The research question

> Learned spatial indexes are evaluated almost exclusively on **point** data
> with range and kNN queries, and several return **approximate** results. Does
> the approach extend to **exact nearest-neighbour queries over extended
> objects** — line segments and polygon boundaries — and what does exactness
> cost?

Nucleus section 14b records the evidence that the gap is real, the chain of
measurements that led the project into it, and the risks stated in advance.
`CAPRM_Flood_Current_Status.md` section 19b records the motivating arithmetic.

## Phase invariant

The exact distance kernel, the 1e-6 m tie tolerance, lexicographic tie-breaking
on `water_feature_id`, and the evidence fields do not change. Every
implementation that claims exactness must reproduce the existing Python
reference field-for-field through the existing comparison harness.

**An index may change what is examined. It may never change what is computed.**

## The implementations

```text
1. brute force              no index                    existing
2. Feature BVH              2D,  8,572 features         existing
3. Segment BVH              2D, ~1M segments            B1
4. Hilbert + binary search  1D, ~1M segments            B3   control
5. Hilbert + RMI            1D, ~1M segments            B4/B5
6. + learned radius         seeds the search disk       B7   stretch
```

## Effort

```text
B1  measure L, segment BVH            2-3 days
B2  run-size sweep                    1 day
B3  Hilbert, inflation, control       3-4 days   <- the hard one
B4  train the RMI                     2 days
B5  port inference                    1 day
B6  benchmark                         1 day
B7  learned radius                    2 days     stretch
```

Phase B is the two weeks. Phase C is roughly three to four days after it.

---

## B1. Measure L, Then Rebuild at Segment Granularity

### Measure L first

Before any index code, measure the **maximum segment length** in the cached
hydrography. One pass over `data/raw/usgs_3dhp_monroe.gpkg`.

`L` determines whether search-radius inflation is a footnote or the entire
story. Ordering extended objects by a representative point requires searching
`disk(r + L/2)` to remain exact, so one long segment inflates **every** query in
the index. A straight canal reach represented as a single segment would do it.

```text
if L is small relative to the 325 m median nearest-water distance:
    inflation is cheap; proceed as planned

if L is large:
    splitting long segments at a maximum length becomes a parameter with a
    cost. That is a finding, not an inconvenience.
```

**Do not design around this number before measuring it.** Report the full
distribution of segment lengths, not only the maximum — the tail shape decides
whether splitting is worth it.

### Then rebuild the index

Index roughly 1,063,159 segments rather than 8,572 features.

**Why.** The Feature BVH examines only 5.498 candidate features per property
and still performs 70,771 segment checks, because a candidate feature averages
12,872 segments — about 104 times the average feature size. Lake Ontario, the
Genesee, and the Erie Canal are each one feature, each enormous, and each near
almost everything. Once traversal descends into one, it checks every segment
inside. The tree stops discriminating exactly where the work is.

**Run size.** An index entry may hold one segment or a run of consecutive
segments sharing a bounding box. Run size 1 is the finest granularity. Start
there; B2 sweeps it.

Each entry must retain the parent feature's `water_feature_id`, because the tie
rule resolves on it and the tie rule does not change.

### Acceptance

The existing comparison harness reports the same exact agreement it reports
today. Nothing about the semantics changed, so nothing about the agreement may
change. If agreement degrades, the kernel was touched and the change is wrong.

### Expected result

A substantial improvement over the Feature BVH, and the honest baseline the
learned index must beat. Racing a learned index against the Feature BVH rather
than against a segment index would be a rigged comparison, and an examiner
would see it immediately.

---

## B2. Sweep the Run-Size Parameter

### Goal

The tradeoff curve. **No theory predicts its shape.**

```text
run size    entries     extent per entry    inflation    pruning
1           ~1M         tiny                small        best
8           ~133K       larger              bigger       worse
64          ~17K        large               large        much worse
```

Larger runs mean fewer entries, a smaller tree, and faster traversal — but each
entry's bounding box grows, which costs pruning quality and enlarges the
inflation radius. This is a bias-variance-shaped tradeoff on real data, and the
shape of the curve is the finding.

### Implementation

Sweep `1, 2, 4, 8, 16, 32, 64, 128`. One loop over the B1 builder.

### Measure per run size

```text
build time
index size in bytes
query time
segment checks per property
candidate entries per property
maximum entry extent  ->  the inflation radius it implies
exact agreement       ->  must hold at every run size
```

### Completion gate

A curve, a chosen operating point, and a stated reason for choosing it. Carry
the winner into B3.

### Note

This is cheap and it lands early. It is also the first result in Milestone 4
that no prior milestone could have produced, so it is worth having in hand
before the harder work begins.

---

## B3. Hilbert Ordering, Inflation, and the Binary-Search Control

### Goal

Impose a locality-preserving one-dimensional order on two-dimensional extended
objects, handle the inflation exactness requires, and **prove the query path is
exact before any model exists**.

### This step is not machine learning

Hilbert ordering, the inflation radius, and the range decomposition are
required by *any* approach that places 2D data in a 1D sorted array — a B-tree,
a binary search, or a learned model alike. They are the price of leaving the
tree, not part of the learning.

### Hilbert ordering

Hilbert order on entry midpoints. Hilbert preserves locality better than
Z-order, and the transform is roughly fifty lines of bit manipulation.

Document the curve resolution and the coordinate normalization. Both are
parameters, both affect the result, and both belong in the manifest.

### The inflation radius

**This is the technical core of the phase.**

A segment's midpoint can lie outside a query disk while its nearest point lies
inside it. Searching `disk(r)` by midpoint therefore misses that segment. To
remain exact:

```text
search disk(r + L/2)     where L is the longest entry in the index
```

That inflation is the entire cost of treating extended objects as points. It is
why the learned-index literature has stayed on point data. It is tunable
through run size, and it must be reported as a first-class result rather than
buried as an implementation detail.

Record the measured inflation cost: how many additional entries the inflated
disk admits, as a fraction of the uninflated disk.

### The range decomposition

Given a query point and a radius, determine every curve interval intersecting
the disk of that radius. This is the hardest geometry in the phase and the
likeliest place to lose a week. It is a solved problem in the spatial-index
literature; it is simply not solved in this repository yet.

**Simplification if it proves expensive.** Expand the candidate window until its
bounding box covers the inflated query disk. Cruder, still exact, far less code.
Take this path if the phase runs long; the exactness argument is unaffected.

### The control implementation

Query the Hilbert-ordered array with **binary search**, not a model.

This is implementation 4 and it is **not optional**. Without it, B6 is a
confounded experiment: comparing a segment BVH against a learned index changes
two variables at once — the dimensionality reduction and the learning — and a
loss could not be attributed to either.

```text
4 vs 3   isolates the dimensionality reduction
5 vs 4   isolates the machine learning
```

It also de-risks B5. The Hilbert transform, the inflation, the range
decomposition, the tie rule, and the exact kernel are all exercised here against
a search that cannot be wrong. Once this reports exact agreement, the plumbing
is known good, and swapping in a model is a small change against a trusted
baseline. If the RMI then fails, it is the RMI.

### Note on lossiness

Two entries with the same midpoint but different orientations receive the same
curve position. That is acceptable: the curve position selects candidates and
the exact kernel decides. Document it rather than working around it.

### Completion gate

Hilbert + binary search reproduces the Python reference field-for-field at
countywide scale, and the inflation cost is measured.

---

## B4. Train the Recursive Model Index

### This is the machine learning

Supervised regression: fit a function from key to array position, which is the
CDF of the key distribution.

### What this is

A hierarchy of simple regressions approximating that CDF — Kraska et al.,
*The Case for Learned Index Structures*, SIGMOD 2018. A two-stage RMI suffices:
a root model routes to a second-stage model, and the second-stage model
predicts a position.

Linear models at both stages. Resist anything larger. Inference must be a
handful of multiply-adds on the query path, or the speed argument evaporates.

### Required output

```text
the model parameters
a maximum prediction error per second-stage model
a recorded seed
a checksum of the training array
a manifest
```

The error bound is **not optional**. It defines the search window, and the
window is what makes the query exact. A model without a proven error bound
cannot be used, because there would be no principled window size.

### Implementation

Python, numpy. No framework. Training is least-squares on sorted keys, and
importing a framework to fit a line would obscure what is happening.

### Completion gate

Predicted position plus the recorded error bound provably contains the true
position for **every** key in the training array. Verify exhaustively — the
array is about a million entries, so there is no reason to sample.

---

## B5. Port RMI Inference to C++

### Goal

Replace B3's binary search with B4's model.

### Why this is now small

B3 already built and validated everything except position lookup. This step
swaps one function.

```text
normalize the key
evaluate the root model      -> select a second-stage model
evaluate that model          -> a predicted position
clamp to the array bounds
search the window defined by the recorded error bound
```

Roughly fifty lines. Python trains; C++ infers. This follows the existing
boundary rather than bending it.

### The full query, for reference

```text
1. predict a curve position for the property point            [B4/B5]
2. search the bounded window around it for a first candidate  [B5]
3. exact distance to that candidate -> an upper-bound radius  [existing]
4. inflate to r + L/2                                         [B3]
5. expand to every curve range intersecting that disk          [B3]
6. exact kernel on all entries in those ranges                 [existing]
7. resolve ties by water_feature_id                            [existing]
```

Only steps 1 and 2 are new here.

### Completion gate

The learned index returns byte-identical evidence to the B3 control. If it does
not, the model is being trusted somewhere it should not be. The model selects
candidates; it never decides.

---

## B6. Benchmark

### Goal

Five implementations, one table, one validation standard.

### The comparisons are adjacent, never global

```text
3 vs 2   granularity               does indexing geometry beat indexing features
4 vs 3   dimensionality reduction  what does flattening 2D to 1D cost
5 vs 4   machine learning          same data, order, inflation, decomposition,
                                   and kernel. The only difference is whether a
                                   model or a binary search finds the position.
```

Reporting only 5 vs 3 would confound the last two and is not acceptable.

### Measure

```text
build time
query time
peak memory
segment checks per property
candidate entries per property
exact agreement
model size in bytes                        implementations 5, 6
average search window                      implementations 5, 6
window expansion rate                      implementations 5, 6
inflation cost as a fraction of the disk   implementations 4, 5, 6
```

**Inflation is a first-class axis**, not a footnote. It is the cost of extended
objects, and it is the thing the literature has not measured because the
literature indexes points.

Report memory honestly. A segment index uses substantially more than a feature
index, and that trade is part of the result.

### The result may be negative

At roughly one million keys in two dimensions, a well-built segment index may
simply beat a learned index. State that possibility before running the
benchmark and report whichever way it falls.

This is unremarkable rather than embarrassing: the published record already
shows that ZM-index, ML-Index, and RSMI cannot systematically outperform
non-learned indexes. A negative result, measured against an exact baseline with
verified correctness, is a finding. The open question in this literature is
*when* learning helps, and a clean "not at this scale, and here is why" is an
answer.

### Completion gate

Exact agreement across all compared fields at countywide scale for every
implementation claiming exactness, and a benchmark table reported as the three
adjacent comparisons.

---

## B7. Learned Radius — Stretch

### The idea

The RLR-Tree authors note that kNN performance "largely depends on the size of
the region used." That region can be learned.

The Phase C surrogate trains a mapping from coordinates to the index. The water
component is a percentile of distance-to-nearest-water, so the same machinery
trains a mapping from coordinates to that distance — a **distance field**.

A predicted radius seeds the exact query:

```text
predict r_hat
search disk(r_hat + L/2)
  found a candidate at d <= r_hat  ->  disk(d) was fully covered, so d is
                                       provably correct
  found nothing                    ->  double r_hat and retry
```

### Why this is safe

**Overestimating is safe and merely slower. Underestimating costs a retry.**
Bias the model to overestimate and it is an admissible heuristic. The exact
kernel still decides, so correctness never depends on the model being good.

### Why it matters

It makes the surrogate load-bearing rather than a curiosity: the approximate
answer is used to make the exact answer fast. The two halves of Milestone 4
stop being separate projects.

### Literature check required

Learned cost and cardinality estimation is an established area. Whether a
learned radius has been applied to exact nearest-neighbour search over extended
objects is a question for the related-work section, and it must be answered
before the contribution is described. Do not claim novelty without checking.

### Completion gate

Exact agreement, plus a measured retry rate and a comparison against
implementation 5 that isolates the radius model's contribution.

---

# 5. PHASE C — Neural Surrogate

This phase abandons exactness deliberately. The error is the point.

---

## C1. Prepare Training Data and a Spatial-Block Split

### Goal

A supervised dataset from the pipeline's own output.

```text
input:   property x, y in EPSG:26918
target:  exposure_index_0_100 at preliminary_exposure_index_v2
rows:    267,362, exactly labelled
```

The labels are exact because the project computed them. This is not a claim
about flooding; it is an approximation of the project's own deterministic
function.

### The split is the whole slide

**Partition by spatial block, never randomly.**

Adjacent parcels are near-duplicates: they share a FEMA polygon, sit metres
apart on the same DEM cells, and frequently select the same nearest water
feature. A random split places near-identical records on both sides and reports
a memorization score as a generalization score.

Use a grid of blocks — a few kilometres on a side — and assign whole blocks to
train, validation, or test. Record the block size, the seed, and the resulting
row counts.

### Completion gate

No test-set property lies within one block of a training property. Verify it;
do not assume it.

---

## C2. Train the Surrogate

### Goal

A model that maps coordinates to the index.

### Implementation

A small MLP. Coordinates normalized. A Fourier or random-feature encoding of
position is worth trying, because raw coordinates make it hard for a small
network to represent sharp spatial structure — and this target has sharp
structure by construction.

Record the architecture, the seed, the split, the loss curve, and a checksum of
the weights. A model is an artifact.

### Do not

- Do not train on flood outcomes. There are no labels, and the obvious source
  is poisoned: FEMA zone determines mandatory insurance purchase, which
  determines who can file a claim, so claims correlate with the FEMA component
  by construction. This is worth knowing about even though the project will
  never go near it.
- Do not replace the scoring layer with the surrogate. The scoring layer's only
  defensible property is that it is interpretable.

---

## C3. Error Analysis

### Goal

Not "what is the RMSE." Where does it fail, and why.

### The expected finding

**FEMA zones are discontinuities.** The index jumps by 34 points across a zone
boundary — a step function. A smooth network cannot represent a step; it can
only approximate it with a ramp.

So the residuals should spike along zone boundaries and be small elsewhere.
That is a mechanistic prediction, made in advance, and confirming or refuting
it is the phase's real result.

### Required outputs

- residuals mapped in space;
- residual distribution split by distance to the nearest zone boundary;
- residual distribution split by FEMA zone;
- the worst cases, inspected individually rather than summarized.

### Why this matters

The surrogate's failure is explained by the structure the rest of the project
built. The two halves of Milestone 4 are the same story from opposite ends: one
learns where to look and stays exact; the other learns the answer and reveals,
by failing, exactly where the exactness was load-bearing.

---

## C4. Benchmark and Document the Surrogate

### Measure

Inference time per property against the exact pipeline. Model size. Accuracy on
the held-out blocks. Accuracy as a function of distance to a discontinuity.

### Honest framing

The surrogate is not needed. The pipeline computes this exactly, and quickly.
The defensible motivations are narrow and should be stated as such:

- it is **differentiable**, which yields a gradient of exposure with respect to
  location that the geometry cannot provide;
- it scores **any coordinate**, not only the 267,362 parcels in the workload.

Neither is a production argument. Both are real.

### Ordering note

The surrogate targets `preliminary_exposure_index_v2`. If precipitation lands
as a stretch goal, the index becomes a five-component v3 and the surrogate
continues to describe v2. Document that; do not repair it. The surrogate's
claim is that it can approximate a deterministic geometric function, not that
it tracks whichever index is current.

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

### Concrete items, found by repository inventory 2026-07-16

**`data/raw/usgs_3dhp_monroe.gpkg` is tracked at 21 MB.** It matches `*.gpkg`
in `.gitignore` and was committed before the ignore rules landed. Every other
large file in the repository reports `ignored`; this is the only large tracked
file. Untracking it is a history decision, not a hygiene one: the hydrography
cache is checksummed in `docs/data_sources.md` and regenerable by
`cache_hydrography.py`, so the working copy is reproducible without it, but
the committed blob remains in history either way.

**`inventory_repository.py` computes `expected_paths` but never prints it.**
`main()` reports untracked, empty, and large files, and writes the full status
to JSON, but the expected-path check is silent on the console. The list exists
to alert someone when a canonical file goes missing, and it does not. A caller
must open the JSON to learn the answer.

**`python/caprm/__init__.py` is empty** and reported as such by the inventory.
This is normal for a package marker but shows up alongside genuinely stale
empty files.

**`outputs/validation/fema_pip_refresh_stderr.txt` and `_stdout.txt` are
empty** and tracked. Milestone 1 debris.

**Untracked local files awaiting triage:** `how-ref`,
`m2_presentation_script.docx`, `MILESTONE 2 PRESENTATION NOTES.docx`,
`report body .docx`, `presentation_assets/`. Decide whether course
deliverables belong in the repository.

**Directories previously believed empty do not exist.** `benchmarks/`,
`docker/`, `data/sample/`, and `cpp/spatial_core/include/` were recorded as
empty scaffolding on the basis of a stale editor tree. `Remove-Item` reported
all four absent. No action needed; the claim is retracted.

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

# 7b. PHASE S — Precipitation, Gated Stretch Goal

Precipitation was planned as the fourth evidence family and was presented to
the class as a Milestone 3 forward-looking goal. It is not cancelled. It is
outranked.

## Gate

```text
Permitted only after PHASE B and PHASE C are complete AND documented.
```

A stretch goal without an explicit precondition becomes roadmap noise. This is
the precondition.

## Why it is outranked rather than kept

A fourth family adds ingestion, provenance, and validation work, and adds no
algorithmic content. The identified weakness is that the project's
computer-science contribution stalled after Milestone 2; a fourth data source
would not address it.

## Why it is retained rather than cut

Its value is architectural, not evidentiary. Precipitation is the fourth data
topology — interpolated point statistics. The project claims the evidence
contract generalizes across topologies, and terrain demonstrated that for
raster. Precipitation would confirm the claim rather than restate it.

## If it happens

```text
S1. Select the source and define the derived evidence
S2. Build a cache script with recorded retrieval date and provenance
S3. Derive property-level evidence
S4. Validate and manifest
S5. Integrate into the scoring layer as a fifth component
```

Two lessons terrain taught, both recorded in `docs/data_sources.md`:

- **S2 is not optional.** Terrain has no download script and no recorded
  retrieval date, so its checksum is the only thing pinning which elevation
  data produced the results. Precipitation gets a cache script from the start.
- **Declare it in `configs/*.yaml`.** Terrain is the only source family whose
  paths and parameters live solely in CLI defaults.

## Ordering consequence

The surrogate targets `preliminary_exposure_index_v2`. If precipitation lands,
the index becomes a five-component v3 and the surrogate continues to describe
v2. Document that rather than retraining. The surrogate's claim is that it can
approximate a deterministic geometric function, not that it tracks the current
index.

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

## Manifests must reproduce the result

A manifest plus the input tables must be sufficient to recompute the output.
No scoring constant may live only in source. This is why the terrain
sub-weights were flattened in A2: the manifest recorded three weights while
the code applied five, so a reader with the manifest and both evidence tables
still had to open `scoring.py` to reproduce the index.

## Composite rounding

Round the composite to `caprm.scoring.COMPOSITE_DECIMALS` before ranking or
storing it.

The composite lies on a lattice. Each percentile component is
`rank * 100/n` with ranks in half steps, so under the default weights the
composite is `0.40 * C_fema` plus a multiple of `2.5/n`, about `9.4e-6`
countywide. Distinct rank triples collide on that lattice constantly: many
properties have mathematically identical composites.

Float arithmetic separates a colliding pair by around `1e-14` depending on
operation order. Ranking the unrounded value imposes an ordering sourced from
rounding order rather than evidence, and breaks reproducibility: the stored
percentile could not be recomputed from the stored index.

`caprm.sensitivity.score_scenarios` applies the same rounding, so every
scenario ranking is built on the same rule as the baseline and remains
comparable to it.

## Declare thresholds before measuring

Sensitivity thresholds are fixed in source before any result is produced. A
threshold chosen to fit the result it judges makes the verdict
unfalsifiable.

## Calibrate a stability metric before trusting it

Include reference configurations that are deliberately implausible. Without
knowing what a genuinely different weighting does to a metric, a high score
on that metric cannot be interpreted. Exclude them from the verdict; report
them alongside it.

## Do not manufacture spread

Never transform a component to give it variance the source data does not
contain. The FEMA component has 98.1% of properties tied at one value because
FEMA genuinely has nothing further to say about them. Percentile-ranking it
would smear 262,297 identical zone-X properties across ranks 0-98, inventing
distinctions that do not exist.

## Report measured influence, not just nominal weight

Influence scales with weight times spread, and the components do not have
equal spread. Water carries 35% of the weight and 65% of the variance; FEMA
carries 40% and 17%. A manifest that reports only the weights invites a
reader to assume FEMA dominates.

---

## An index may change what is examined, never what is computed

The Feature BVH established this: it changes search strategy, not distance
semantics. The rule extends to a learned index without modification, and it is
what makes learning safe here.

A model that predicts badly produces a wider candidate window and a slower
query. It cannot produce a wrong answer, because the exact kernel still
decides. **Correctness does not depend on the model being good.**

## An approximate method must be measured against an exact one

An approximation is only meaningful relative to the thing it approximates. The
project already has an exact baseline whose correctness is proven field-by-field
against an independent implementation, so any learned method can be measured
rather than asserted.

## Split spatially, not randomly

Adjacent parcels are near-duplicates. A random train/test split places
near-identical records on both sides and reports memorization as
generalization. Any held-out evaluation partitions by spatial block.

## A negative result is a result

The learned index may lose to a well-built segment index at this scale. Stated
in advance, measured against an exact baseline, and explained, that is a
finding. Tuning until the preferred method wins is not.

## A model is an artifact

Weights, a seed, a training-set checksum, and a manifest, or the result is not
reproducible. A model is held to the same provenance standard as a CSV.

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

## Milestone 3 — COMPLETE

```text
current scoring behavior documented        DONE  docs/scoring_methodology.md
scoring methodology hardened               DONE  preliminary_exposure_index_v2
sensitivity analysis implemented           DONE  moderately sensitive
terrain/index audit passed                 DONE  49 pass, 1 warn, 0 fail
final artifacts regenerated                DONE  2026-07-16
full test suite passes                     DONE  181 passed
runbook complete                           DONE  docs/milestone_3.md
GitHub synchronized                        DONE
```

Milestone 3 is frozen.

## PHASE B complete when

```text
maximum segment length measured, distribution reported
segment-granularity index implemented
exact agreement unchanged from the Feature BVH baseline
run-size parameter swept, operating point chosen and justified
segments Hilbert-ordered, resolution and normalization documented
search-radius inflation implemented and its cost measured
disk-to-curve-range decomposition proven exact
Hilbert + binary search control reproduces the Python reference
RMI trained, with a proven per-model error bound
RMI inference ported to C++
five-implementation benchmark at countywide scale
reported as three adjacent comparisons, not one global one
inflation reported as a first-class axis
the result is reported whichever way it falls
```

Stretch, not required:

```text
learned radius implemented, retry rate measured
related-work check on learned radius completed before any novelty claim
```

## PHASE C complete when

```text
spatial-block split verified, not assumed
surrogate trained, weights checksummed, seed recorded
residuals mapped and analyzed by distance to a zone boundary
the discontinuity prediction confirmed or refuted, on the record
inference benchmarked against the exact pipeline
the surrogate's narrow motivation stated honestly
```

## PHASE D complete when

```text
full pipeline reproducible from a clean state
runtimes measured for every stage, not only the C++ query
validation results consolidated
repository free of stale expectations and untracked debt
```

## PHASE E complete when

```text
report submitted
poster presented
repository presentable to a stranger
```

## PHASE S complete when

```text
precipitation cached with a recorded retrieval date and a manifest
declared in configs/*.yaml
property-level evidence validated
integrated as a fifth component, index at v3
the surrogate's v2 target documented as such
```

---

# 11. Immediate Next Conversation

```text
B1. Measure the maximum segment length, then rebuild the index at
    segment granularity
```

Measure `L` before writing index code. It is one pass over the hydrography
cache and it determines whether search-radius inflation is a footnote or the
phase's central finding. Do not design around the number before measuring it.

Then rebuild at segment granularity. It lands in days, produces a result either
way, uses only infrastructure that exists, and is the honest baseline the
learned index must beat.

Suggested prompt:

> We are continuing CAPRM-Flood at Milestone 4, chunk B1. Read Nucleus section
> 14b, `CAPRM_Flood_Current_Status.md` sections 19b and 21, and this document's
> PHASE B before proposing anything.
>
> Confirm the commit recorded in Current Status section 2 matches
> `git log -1 --oneline`. If it does not, say so before continuing — you are
> reading a stale copy.
>
> Milestones 1 through 3 are frozen. The exposure index is not under active
> work and must not be modified.
>
> B1 has two parts. First, measure the maximum segment length in
> `data/raw/usgs_3dhp_monroe.gpkg` and report the full length distribution.
> Second, rebuild the water spatial index over segments rather than features.
>
> Inspect `cpp/spatial_core/src/water_distance_indexed.cpp` and
> `python/caprm/water_distance.py` and state their current behavior from source
> before proposing a change. The exact distance kernel, the 1e-6 m tie
> tolerance, and lexicographic tie-breaking on water_feature_id do not change.
> Acceptance is that the existing comparison harness reports the same exact
> agreement it reports today.

---

# 12. Canonical Roadmap Summary

CAPRM-Flood has completed and frozen Milestones 1 through 3. Three evidence
families spanning three data topologies produce one evidence contract for
267,362 properties with exact Python/C++ agreement at every scale, and the
exposure index is documented, hardened to four declared components,
characterized as moderately sensitive to weight choice, and audited against its
own manifests. Milestone 4 redirects the project toward the computer-science
question its own Milestone 2 benchmark raised and left unanswered: the Feature
BVH examines 5.498 candidate features per property yet still performs 70,771
segment checks, because it indexes features rather than geometry and the
largest water features are near everything in the county. Rebuilding at segment
granularity leads into a corner of the literature that has not been examined,
because learned spatial indexes are evaluated almost exclusively on point data
and several return approximate results, whereas this project's data is line
segments and polygon boundaries and its query is exact nearest neighbour. Phase
B therefore measures the maximum segment length before anything is built on it,
sweeps the run-size parameter that trades pruning against the search-radius
inflation that representative-point ordering imposes on extended objects,
orders the entries along a Hilbert curve, validates the resulting query path
with a binary-search control that isolates the contribution of learning from the
contribution of dimensionality reduction, trains a recursive model index with a
proven error bound, ports inference to C++, and benchmarks five implementations
under one exactness standard — an index may change what is examined, never what
is computed, which is what makes a learned index safe here. Phase C abandons
exactness deliberately and trains a neural surrogate of the pipeline's own
deterministic output, split by spatial block rather than randomly, where the
expected failure at FEMA zone discontinuities is the result rather than a
disappointment; B7 then closes the loop by using the surrogate's distance field
to seed the exact query's search radius, making the approximate answer
load-bearing for the exact one. Phase D consolidates reproducibility, runtime
measurement, and repository hygiene; Phase E delivers the report and poster;
and precipitation is retained as Phase S, gated behind the computational work,
valuable because it would confirm the architecture's generality across a fourth
topology rather than restate it.
