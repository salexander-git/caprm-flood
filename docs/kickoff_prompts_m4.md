# CAPRM-Flood — Milestone 4 Kickoff Prompts (B2 onward)

Revised 2026-07-22, after B1 completed and was validated countywide.

Splice this over the B2-and-later sections of the existing prompts file. The B1
prompt is obsolete and may be retained as a historical record or deleted.

---

## Phase status

```text
B1  Segment BVH + distance-exact splitting     COMPLETE, committed 998c859
B2  Entry-extent sweep                         next
B3a Hilbert ordering + inflation + query       blocked on B2 operating point
B3b Binary-search control + validation         blocked on B3a
B4  Train the RMI                              blocked on B3b
B5  Port RMI inference to C++                  blocked on B4
B6  Benchmark the ladder                       blocked on B5
C   Neural surrogate                           scoped, runs alongside B4-B6
```

---

## THE B1 FINDING THAT RESHAPES EVERYTHING AFTER IT

Read this before any remaining Phase B prompt. It is the most important result B1
produced, and it is not what B1 was expected to produce.

B1 measured, countywide, per property:

```text
phase 1  search        28.29 node visits  +  6.49 segment box tests  ~= 35 operations
phase 2  verification  9,716.87 segment checks
```

Search is roughly 0.4 percent of query work. Verification dominates, because B1
computes the reported distance with the unchanged exact kernel over each candidate
feature's *entire original geometry* — about 6,490 segments per candidate — in order to
guarantee output byte-identical to the reference.

### The ceiling, stated correctly

Verification is not a fixed cost. It is:

```text
verification = candidate_features x avg_segments_per_candidate_feature
```

Candidate count is itself a search-quality metric, so better search reduces
verification indirectly. That is exactly how B1 earned its 7.28x:

```text
Feature BVH   5.498 candidates x 12,872 segments  =  70,771 checks
Segment BVH   1.497 candidates x  6,490 segments  =   9,717 checks
floor         1.000 candidate  x  6,490 segments  =   6,490 checks
```

At least one feature must be verified. So under Option A the remaining headroom for
every later search-side improvement combined is:

```text
(9,717 + 35) / 6,490  =  ~1.50x
```

**Not 1.003x.** An earlier draft of this document computed the ceiling by holding
verification constant while varying search, which is incoherent — one drives the other.
1.50x is a real and measurable range, though a modest one, and it is a bound on B3, B4,
and B5 *combined* rather than on any one of them.

### Hilbert ordering will probably make candidate count worse

Best-first BVH traversal with tight bounds is already close to optimal at candidate
selection. Flattening to one dimension and searching an inflated range is strictly
lossier, so expect implementation 4 to admit MORE candidates than implementation 3, and
therefore to verify more.

This is not a failure. It is the measurement. Phase B's stated question is what
flattening two-dimensional extended objects into one dimension costs, and the answer is
denominated in precisely this inflation-induced candidate growth. Report the regression
as a quantitative result.

### The design fork this creates

```text
Option A  Verify over ORIGINAL feature geometry     (what B1 does)
          exact to 4.658e-10 m, byte-identical to the reference
          verification ~9,717 segment checks/property, floor ~6,490
          combined search-side headroom ~1.50x

Option B  Verify over SPLIT SEGMENT geometry
          the traversal already reaches the nearest sub-segment; report that distance
          instead of rescanning the parent feature
          verification collapses to tens of segment distance evaluations
          expected agreement ~1e-9 m rather than ~4.7e-10 m, because split endpoints are
          interpolated and differ from the original segment's endpoints by a few ULPs
          (B1 unit tests measured worst case 1.18e-9 m)
          still passes the harness: the tolerance is 1e-6 m
          tie-breaking remains stable: the 1e-6 m tie tolerance is ~1000x the
          perturbation, so a near-tie resolves as a tie on water_feature_id either way
```

**Do not choose one and discard the other.** The A-versus-B difference is the phase's
answer to "what does exactness cost?" — measured on real data at ~1M entries. Both paths
share the same code behind one flag, so preserving both costs a branch, not a second
implementation. B6 reports the cross-product.

### What this does NOT mean

It does not mean the machine learning is bloat, and nothing is being cut from the
Milestone 4 pivot. Three points hold regardless of the ceiling:

1. **Implementations 4 and 5 share an identical candidate set and identical verification
   cost by construction** — same Hilbert order, same inflated range, same decomposition,
   same kernel. The only difference is whether a binary search or a model finds the
   starting position. Verification appears on both sides of the 5-vs-4 comparison and
   cancels. The learned-versus-control comparison is therefore *already isolated* from
   the ceiling and is measurable directly in probes, window size, position error, and
   search-phase time.
2. **Index size is ceiling-immune.** The canonical learned-index claim is that a model
   replaces a structure: a sorted array plus a few linear coefficients versus a BVH's
   node arrays. That is measured in bytes and verification never enters it. Report it as
   a first-class column.
3. **Under Option B the ceiling largely lifts.** Verification collapses, search becomes a
   large fraction of query time, and the RMI's advantage or disadvantage over binary
   search becomes visible in wall clock rather than only in component metrics.

Only **B7 (learned radius)** is a genuine cut candidate, and the Roadmap already lists it
as stretch and not required. B3b's binary-search control stays regardless: without it,
5-vs-4 is confounded, and that is a methodology requirement rather than a performance bet.

What changed is framing and reporting discipline. State the ceiling in advance, report
search-side effects explicitly, and never present a noise-level wall-clock delta as a win.

## PROMPT — B2 · Entry-extent sweep (formerly "run-size sweep")

```text
CAPRM-Flood, Milestone 4 chunk B2. B1 is complete, validated, and committed at 998c859.

Read first: docs/caprm_flood_m4_chunking_plan.md; CAPRM_Flood_Current_Status.md sections
19b and 21; CAPRM_Flood_Roadmap.md PHASE B and B2; cpp/spatial_core/src/
water_distance_segment_bvh.cpp; python/caprm/water_benchmark.py; python/scripts/
benchmark_water_cpp.py; python/scripts/build_property_evidence.py. State each file's
current behavior from source before proposing changes.

B1 BASELINE (cap 100 m, countywide, 267,362 properties) — any deviation is a regression:
  field agreement      267,362 / 267,362,  max abs error 4.658e-10 m
  segment checks/prop  9,716.87        candidate features/prop  1.497
  node visits/prop        28.29        segment box tests/prop   6.49
  wall clock          10.135 s (single run, not a benchmark)
  split at 100 m cap  1,063,159 -> 1,068,510 entries (+0.50%), max extent 5,748.24 -> 100 m
  266 exact-zero distances, all class = waterbody

OBJECTIVE
Sweep the entry-extent parameter, produce the entries-vs-extent tradeoff curve, and
choose and justify an operating point for B3.

The axis is entry extent, not "run size." B1 implements a SPLIT CAP (smaller extent, more
entries). Run grouping (larger extent, fewer entries) is UNWRITTEN. Decide explicitly
whether to implement grouping or sweep the cap alone, and justify it. Sweeping the cap
alone is defensible if grouping cannot be shown to buy anything.

Suggested cap sweep: 10, 25, 50, 100, 200, 500, unlimited. The 100 m point costs only
+0.50% entries, so the informative region is at TIGHTER caps where entry count grows
materially. If run grouping is implemented, sweep 1, 2, 4, 8, 16, 32, 64, 128 alongside it.

SECOND OBJECTIVE — implement BOTH verification modes behind one flag
B1 measured search at ~35 operations/property against verification at 9,716.87 segment
checks/property. Verification = candidate_features x segments_per_candidate, and the
verification floor is one candidate x ~6,490 segments, so the combined search-side
headroom for B3+B4+B5 under the current design is (9,717+35)/6,490 ~= 1.50x.

Implement the fork rather than deciding it (see "THE B1 FINDING" in this document):
  A  verify over ORIGINAL feature geometry  -> byte-identical, 4.658e-10 m
  B  verify over SPLIT SEGMENT geometry     -> verification collapses, expect ~1e-9 m
Both are one flag on the same code path; do not fork the implementation. Every later
chunk inherits the flag, and B6 reports the A/B cross-product. That difference is the
phase's measured answer to "what does exactness cost over extended objects," which is the
second half of the Nucleus section 14b research question and currently unanswered in the
literature.

MEASURE the Option B agreement on the fixture AND countywide; do not assert it from the
1.18e-9 m unit-test bound. Confirm specifically that no feature_id disagreements appear —
the tie tolerance is ~1000x the perturbation, so none are expected, but expected is not
measured. If Option B produces any field disagreement, report it and keep A as default.

CRITICAL COMPATIBILITY CONSTRAINT
python/scripts/build_property_evidence.py asserts that the benchmark summary's algorithm
set EQUALS {brute_force, feature_bvh} and raises ValueError otherwise. Do NOT add
segment_bvh to outputs/validation/water_cpp_benchmark_summary.json — that breaks the
frozen Milestone 2/3 evidence build. Write sweep results to a separate path. Do not modify
frozen Milestone 3 code to accommodate B2.

MEASURE, PER PARAMETER VALUE — report search and verification separately
  build time; index entries; index bytes; max entry extent
  TRAVERSAL:    node visits/property, segment box tests/property
  VERIFICATION: candidate features/property, segment checks/property
  wall clock via the existing repetition protocol (7 reps, 1 warmup), not single runs
  exact agreement — must hold at EVERY value

PREDICTION TO TEST, STATED IN ADVANCE
Under Option A, wall clock may be nearly INSENSITIVE to this parameter, because
verification dominates and the cap moves mainly traversal cost. Under Option B the curve
should become live. If either curve is flat, report it as the finding and explain why. Do
not tune until a preferred shape appears. A negative result is a result (Nucleus 18.18).

WHAT B2 CANNOT CLAIM
B1's index is a 2D BVH with no midpoint ordering, so search-radius inflation does not
exist in it yet; inflation arrives with Hilbert ordering in B3. Report max entry extent
and the L/2 inflation it WOULD imply for B3. Do not report inflation as measured.

INVARIANTS
Exact kernel, 1e-6 m tie tolerance, lexicographic tie-breaking on water_feature_id, and
the evidence fields do not change. An index may change what is examined, never what is
computed. Ask before changing any agreement tolerance.

ACCEPTANCE (local runs)
  curve produced across all swept values
  compare_python_cpp_water.py exits 0 at EVERY value: all_fields_agree == 267,362
  chosen operating point additionally passes artifact checks: 267,362 unique property_ids,
    266 exact zeros all class=waterbody, no nulls in required columns, distances in
    [0, 20000), single distance_crs and algorithm values
  property_count constant at 267,362 across runs
  (entry count MUST vary across runs — that is the independent variable)

DELIVERABLES
  sweep CSV; summary JSON at a NEW path; the figure; chosen operating point with reasons;
  both verification modes implemented behind one flag, with measured A/B agreement and
  cost at the chosen operating point
  Confirm matplotlib is installed in .venv BEFORE the figure step. If a dependency is
  missing, add it to requirements.txt deliberately in the same change — do not pip install
  ad hoc (see the scipy/spatial_split gap in Current Status section 16).

ON COMPLETION
  Update CAPRM_Flood_Current_Status.md, CAPRM_Flood_Roadmap.md, and the Nucleus if the
  result changes durable methodology. Report exact test commands and results. Label
  anything unrun as expected, not completed.
```

---

## PROMPT — B3a · Hilbert ordering, inflation, and the exact query

```text
CAPRM-Flood, Milestone 4 chunk B3a. B1 is complete at 998c859; B2 has chosen the operating
point and resolved the verification-strategy fork.

Read first: docs/caprm_flood_m4_chunking_plan.md; docs/crs_policy.md;
CAPRM_Flood_Current_Status.md section 21; the B2 sweep summary and chosen operating point;
cpp/spatial_core/src/water_distance_bruteforce.cpp (the frozen kernel);
cpp/spatial_core/src/water_distance_segment_bvh.cpp (the B1 two-phase query pattern to
mirror). This is the hardest geometry chunk in the phase. State current behavior from
source before proposing anything.

OBJECTIVE
Replace the 2D box hierarchy with a 1D Hilbert ordering of split-segment midpoints, and
implement an exact query using the inflated-disk bound. No model yet — that is B4/B5.

WHAT B1 CHANGED ABOUT THIS CHUNK
1. L IS NO LONGER 5,748 m. B1 splits every segment to a maximum length (100 m at B1's
   default; use B2's chosen cap). The inflation term is therefore L_capped/2 = 50 m at a
   100 m cap, NOT 2,874 m. Against a 325 m median nearest-water distance, inflation is a
   small correction rather than the dominant cost. The roadmap and Nucleus 18.19 were
   written before this was known; the phase's expected "entire cost of treating extended
   objects as points" turned out to be purchasable for +0.50% index entries.
   Use the CAPPED L. Using the uncapped L would be incorrect AND catastrophically slow.
2. MIRROR B1'S TWO-PHASE STRUCTURE and inherit B2's verification flag. Phase 1 selects
   candidates by Hilbert range; phase 2 verifies under Option A (original feature
   geometry, byte-identical) or Option B (split segment geometry, ~1e-9 m), selected by
   the same flag B2 introduced. Do not hard-code either. This keeps 4-vs-3 isolated to the
   dimensionality reduction with everything else held constant.
3. VERIFICATION DOMINATES. B1 measured search at ~35 operations/property against
   verification at 9,716.87 segment checks/property. This chunk changes phase 1 only.
   Expect little or no wall-clock movement under Option A. Do not treat that as failure.

TASKS
1. Compute a Hilbert key per split-segment midpoint. Document curve order (bits) and the
   coordinate normalization mapping the projected EPSG:26918 extent to the integer grid.
   Both are parameters; both go in the manifest.
2. Sort segments by Hilbert key. Each entry retains its parent water_feature_id, because
   the tie rule resolves on it and the tie rule does not change.
3. Implement the exact query: to find every segment within r, search midpoints within
   r + L_capped/2. Write the completeness argument out explicitly — why no segment whose
   nearest point lies inside disk(r) can have a midpoint outside disk(r + L_capped/2).
4. If the disk-to-curve-range decomposition proves expensive, use the documented fallback:
   expand the candidate window until its bounding box covers the inflated disk. Cruder,
   more candidates, still exact. Record which approach was used and why.
5. Preserve polygon-interior -> 0. B1 achieves this without a containment index, relying
   on the USGS 3DHP non-overlap invariant (Nucleus, segment index method). Verify that the
   same argument survives the change to 1D candidate selection; if it does not, say so and
   propose a containment check rather than accepting silently wrong zeros.

MEASURE
  candidates admitted by disk(r + L/2) vs disk(r)  ->  the inflation cost, as a ratio
  Hilbert build time; key array bytes; curve order; normalization constants
  node/range operations per property, kept separate from verification segment checks

ACCEPTANCE (this chunk)
  Small-fixture exactness first: tests/fixture_crosscheck.py extended to cover the Hilbert
  path, 0 field mismatches against the brute-force oracle. Full countywide validation is
  B3b, but do NOT scale up before the fixture passes.
  The 266-property interior-zero behavior must be represented in the fixture.

DELIVERABLES
  Hilbert key builder + query; manifest recording curve order, normalization, cap, CRS,
  and input SHA-256s; the completeness argument in prose fit for the report.

INVARIANTS
Exact kernel, 1e-6 m tie tolerance, lexicographic tie-breaking on water_feature_id, and
evidence fields do not change. Ask before changing L, the cap, the kernel, or any
tolerance.
```

---

## PROMPT — B3b · Binary-search control and countywide validation

```text
CAPRM-Flood, Milestone 4 chunk B3b. Read docs/caprm_flood_m4_chunking_plan.md, the B3a
outputs and manifest, and CAPRM_Flood_Current_Status.md section 21.

OBJECTIVE
Complete the Hilbert path with a BINARY-SEARCH query over the sorted keys, and validate
exactness countywide. This control is non-optional: without it, B6 cannot separate the
effect of 1D dimensionality reduction from the effect of learning, and a loss could not be
attributed to either.

TASKS
1. Candidate lookup by binary search over the sorted Hilbert keys within the inflated
   range. Reuse the B3a query path unchanged; the only difference from B5 must be how the
   starting position is found.
2. Run countywide (267,362 properties).
3. Measure inflation cost: candidates admitted under disk(r + L_capped/2) as a fraction of
   those admitted under disk(r). Report as a ratio, and report what it would have been at
   the UNCAPPED L = 5,748.24 m. That contrast is a result: it quantifies what the B1 split
   bought, and it is the phase's answer to "what does exactness cost over extended
   objects."

ACCEPTANCE (local runs)
  compare_python_cpp_water.py exits 0 against outputs/baseline/
  python_nearest_water_countywide.csv: all_fields_agree == 267,362
  Run and report BOTH verification modes:
    Option A (verify over original geometry)  -> expect 4.658e-10 m, matching B1 and the
                                                 Feature BVH exactly
    Option B (verify over split geometry)     -> expect ~1e-9 m; state the measured value
                                                 and confirm no feature_id disagreements
  266 exact-zero distances, all class = waterbody
  267,362 rows, 267,362 unique property_ids, no nulls in required columns,
  distances in [0, 20000), single distance_crs and algorithm values
  inflation cost reported, capped and uncapped

DELIVERABLES
  hilbert_binary program; agreement summary JSON at its own path; inflation summary;
  extended tests/fixture_crosscheck.py coverage.

ON COMPLETION
  Patch-ready Current Status and Roadmap updates. If the inflation result changes the
  durable methodology recorded in Nucleus 18.19 — and the capped-L result probably does —
  update the Nucleus too.

INVARIANTS
Kernel, tie tolerance, tie-breaking, and evidence fields frozen. Ask before loosening any
tolerance. If agreement fails, investigate the disagreement; do not widen the tolerance to
make it pass.
```

---

## PROMPT — B4 · Train the recursive model index

```text
CAPRM-Flood, Milestone 4 chunk B4. Read docs/caprm_flood_m4_chunking_plan.md and the B3b
outputs and manifest. Python only. No ML framework — numpy least squares.

OBJECTIVE
Train a two-stage RMI mapping a segment's Hilbert key to its position in the sorted array,
after Kraska et al., The Case for Learned Index Structures, SIGMOD 2018. Linear models at
both stages. Inference must be a handful of multiply-adds or the speed argument evaporates.

CONTEXT FROM B1 — read before interpreting any result
Search is ~0.4% of query work (about 35 operations against 9,716.87 verification segment
checks), and under Option A the combined search-side headroom for B3+B4+B5 is ~1.50x. A
perfect position predictor therefore cannot produce a large end-to-end speedup in that
mode; under Option B it can. Either way the RMI's own quality is measured on SEARCH-side
metrics — predicted-position error, search-window size, key throughput — plus index size
in bytes, which the ceiling does not touch at all and which is the canonical learned-index
claim (a model replacing a structure). Frame this before training, not after benchmarking.

ACCEPTANCE
  EXHAUSTIVE error bound, not sampled: for every one of the ~1.07M keys, the predicted
  position plus or minus the recorded per-model error bound provably contains the true
  position. Verify over the entire array and report the maximum error per second-stage
  model, not just the global maximum.
  Duplicate keys must be handled explicitly: two segments with the same midpoint cell
  receive the same key, so the position mapping is not injective. State the convention
  (first or last position of the run) and make the bound valid under it.

DELIVERABLES
  Training script; model artifact carrying weights, random seed, training-array SHA-256,
  key count, curve order and normalization copied from the B3a manifest; a manifest.
  A model is an artifact and is held to the same provenance standard as a CSV
  (Nucleus 18.20).

ON COMPLETION
  Patch-ready Current Status and Roadmap updates. Ask before introducing any nonlinear
  stage, any framework, or any change to the error-bound contract.
```

---

## PROMPT — B5 · Port RMI inference to C++

```text
CAPRM-Flood, Milestone 4 chunk B5. Read docs/caprm_flood_m4_chunking_plan.md, the B3b
query path, and the B4 model artifact and manifest. C++ performs inference only; it never
trains.

OBJECTIVE
Replace the binary search with RMI inference: normalize key -> root model -> leaf model ->
predicted position -> clamp to the recorded error window -> bounded search, reusing the
B3a/B3b exact query path unchanged.

ACCEPTANCE (local runs)
  hilbert_rmi output is byte-identical to the B3b binary-search control countywide. Not
  "within tolerance" — identical. Both paths reach the same candidates and run the same
  kernel, so any difference means the error window is wrong and the model is silently
  losing candidates.
  Also run compare_python_cpp_water.py against the Python reference for the record.
  Report the search-window size distribution: min, median, p99, max, and the fraction of
  queries where the window collapses to a single position.

WHAT B5 CAN AND CANNOT CLAIM
CAN: implementations 4 and 5 share an identical candidate set and identical verification
cost, so the 5-vs-4 comparison is clean under BOTH verification modes. Probes per query,
search-window size, position error, index bytes, and search-phase time are all valid
measurements of the learned index and none of them are affected by the ceiling.
CANNOT: under Option A, combined search-side headroom is ~1.50x for B3+B4+B5 together, so
an end-to-end wall-clock delta may sit inside noise. Report search-side metrics separately
from wall clock and do not present a noise-level difference as a win. Under Option B the
end-to-end comparison becomes live; report it straight, whichever way it falls.

DELIVERABLES
  hilbert_rmi program; agreement report; window-size distribution.

ON COMPLETION
  Patch-ready docs. Ask before changing the model, the error-bound contract, or the query
  path shared with B3b.
```

---

## PROMPT — B6 · Benchmark the ladder

```text
CAPRM-Flood, Milestone 4 chunk B6. Read docs/caprm_flood_m4_chunking_plan.md, all B1-B5
outputs, python/caprm/water_benchmark.py (it hard-codes only brute_force and feature_bvh
in parse_cpp_benchmark_output and summarize_benchmark_runs), and
python/scripts/benchmark_water_cpp.py.

OBJECTIVE
Benchmark all five implementations on one workload and report honestly.

CRITICAL COMPATIBILITY CONSTRAINT
python/scripts/build_property_evidence.py asserts the benchmark summary's algorithm set
EQUALS {brute_force, feature_bvh}. Writing five algorithms into
outputs/validation/water_cpp_benchmark_summary.json will break the frozen Milestone 2/3
evidence build. Use a separate summary path. If the ladder summary is ever to replace the
Milestone 2 artifact, that is a deliberate migration with its own decision, not a side
effect of benchmarking.

TASKS
1. Extend the harness to accept segment_bvh, hilbert_binary, and hilbert_rmi.
2. Run warmups plus alternating-order repetitions for all five implementations.
3. Report the three ADJACENT comparisons, never a global one:
     3 vs 2   granularity                does indexing geometry beat indexing features
     4 vs 3   dimensionality reduction   what does flattening 2D to 1D cost
     5 vs 4   machine learning           same data, order, decomposition, and kernel;
                                         the only difference is how position is found
4. Report SEARCH cost and VERIFICATION cost as separate columns throughout. Reporting only
   total segment checks or only wall clock will hide the actual structure of the result.
5. Inflation cost and memory are first-class columns.

THE HEADLINE TABLE — run the full ladder under BOTH verification modes
This cross-product is B6's primary deliverable. The row difference is index quality; the
COLUMN difference is the cost of exactness, which is the half of the Nucleus section 14b
research question the literature has never measured.

                              Option A (byte-identical)   Option B (~1e-9 m)
  brute force                       n/a                        n/a
  Feature BVH                    70,771 checks                  -
  Segment BVH                     9,717 checks                  ?
  Hilbert + binary search             ?                         ?
  Hilbert + RMI                       ?                         ?
  columns: checks, wall clock, index bytes, candidates/property, inflation cost

FRAME THE RESULT BEFORE INTERPRETING IT
Under Option A the combined search-side headroom is ~1.50x (verification floor ~6,490
checks against B1's 9,717), so 4-vs-3 and 5-vs-4 will be small in wall clock and may sit
inside noise. Expect implementation 4 to admit MORE candidates than implementation 3:
flattening 2D to 1D and searching an inflated range is strictly lossier than best-first
traversal with tight bounds. That regression is the measurement 4-vs-3 exists to produce,
not a failure.

5-vs-4 is unaffected by any of this. Implementations 4 and 5 share an identical candidate
set and identical verification cost by construction, so verification cancels and the
learned-versus-control comparison is clean in both columns. Report it in probes per query,
search-window size, position error, index bytes, and search-phase time — not only in
end-to-end wall clock.

Do not tune to force a learned win. A negative result, stated in advance and measured
against an exact baseline, is a result (Nucleus 18.18).

ACCEPTANCE (local runs)
  one runs CSV and one summary JSON covering all five implementations
  every implementation still passes exact agreement at countywide scale
  the comparison table distinguishes computational correctness, methodological assumptions,
  and measured performance

DELIVERABLES
  Extended harness; results; comparison table; docs/benchmark_results.md update.

ON COMPLETION
  Patch-ready Current Status, Roadmap, and Nucleus updates.
```

---

## PROMPTS — C1..C4 · Neural surrogate

Finalize when Phase B outputs exist. Compact briefs, updated for B1:

- **C1 (spatial-block split).** Grid roughly kilometre blocks; assign whole blocks to
  train/validation/test; record block size, seed, and counts; VERIFY that no test property
  lies within one block of a training property rather than assuming it. Deliverable: split
  file plus manifest. Note: `python/caprm/spatial_split.py`,
  `python/caprm/build_spatial_split.py`, and `tests/test_spatial_split.py` already exist
  untracked in the working tree and import `scipy.spatial.cKDTree`, which is not installed.
  Start by reading them rather than rewriting, and land scipy in `requirements.txt` in the
  same change that commits them.
- **C2 (train surrogate).** Small MLP on normalized coordinates, optionally with Fourier
  features. Target the pipeline's own deterministic output — nearest-water distance and/or
  the index — never flood outcomes. Do not replace the scoring layer. Record architecture,
  seed, split, loss curve, and weight checksum.
- **C3 (error analysis — the real result).** Map residuals in space; test the prediction
  that residuals spike along FEMA-zone boundaries and stay small elsewhere; inspect worst
  cases; confirm or refute on the record.
- **C4 (benchmark surrogate).** Inference time against the exact pipeline, model size, and
  accuracy against distance-to-discontinuity. Frame the value honestly — differentiable,
  evaluable at any coordinate — with no production claim. Given B1's verification-dominated
  profile, the surrogate is the only path in the project that removes verification cost
  rather than search cost, and that framing is worth stating explicitly.

---

## D / E / S prompts

Authored at the phase boundary, when their inputs exist. Their content depends on Phase B
and C results and on reading `Professor_Milestone_Requirements.txt`, which has not been
read this cycle. Writing them in detail now would be speculation.

Two items already queued for **D4 (repository cleanup)** from B1:

- `outputs/validation/*.json` summaries match the `outputs/` ignore rule and were excluded
  from commit 998c859, so the C++ artifacts of record live outside the repository. Decide
  the policy deliberately: force-add, add a `.gitignore` exception, or accept that the
  canonical documents carry the numbers.
- `docs/CAPRM_Flood_Current_Status.md` section 2 recorded commit `0dd85ab` while the remote
  had advanced to `b3ec90d`, so at least one commit went unrecorded. The staleness check in
  the document's own preamble did not catch it because nothing enforces it.