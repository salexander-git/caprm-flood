# CAPRM-Flood — Milestone 4 Kickoff Prompts (B2 onward)

Revised 2026-07-22, after B1 completed and was validated countywide.
Revised 2026-07-29, after B6a-B6c: the ladder measured, the nine-window sweep run,
and the phase's contribution recorded as Nucleus 18.27. The canonical documents now
live under `docs/canon/`.

Splice this over the B2-and-later sections of the existing prompts file. The B1
prompt is obsolete and may be retained as a historical record or deleted.

---

## Phase status

```text
B1    Segment BVH + distance-exact splitting   COMPLETE, 998c859
B2    Entry-extent sweep + verification fork   COMPLETE, 27031d9
B3a   Hilbert ordering + inflation + query     COMPLETE, 97bfb1e
B3b   Binary-search control + validation      COMPLETE, 97bfb1e
B4    Train the RMI                            COMPLETE, 97bfb1e
B5    Port RMI inference to C++                COMPLETE, f2e2e00
B5c   Instrument the resolve descent           COMPLETE, ff8121f
B6a   Ladder harness + protocol                COMPLETE, 664a431
B6b   SEED_WINDOW as a build parameter         COMPLETE, 664a431
B6c   Ladder + nine-window sweep, countywide   COMPLETE, 664a431
B6c-2 Option A / Option B cross-product        IN PROGRESS
B6d   Benchmark close-out + document pass      blocked on B6c-2
B7    Learned radius                           stretch, after PHASE C
C     Neural surrogate                         next after B6d
```

---

## THE B1 FINDING THAT RESHAPES EVERYTHING AFTER IT

Read this before any remaining Phase B prompt. It is the most important result B1
produced, and it is not what B1 was expected to produce.

B1 measured, countywide, per property:

```text
phase 1  search        28.29 node visits  +  6.49 segment box tests  ~= 35 operations
phase 2  verification  9,716.87 segment checks     <- B1, at a 100 m entry cap
```

Search is roughly 0.4 percent of query work. Verification dominates, because B1
computes the reported distance with the unchanged exact kernel over each candidate
feature's *entire original geometry* — about 6,490 segments per candidate — in order to
guarantee output byte-identical to the reference.

OPERATING POINT, since B2. B1 measured at a 100 m cap. B2 swept the cap and chose
25 m, where the same quantities are 9,407.6 checks over 1.466 candidate features,
about 6,417 segments each. B6c confirmed it countywide at 9,407.617649. Both figures
are correct; they are different operating points, and every later comparison uses the
25 m one. Do not quote 9,716.87 as the segment BVH's cost in the ladder.

### The ceiling, stated correctly

Verification is not a fixed cost. It is:

```text
verification = candidate_features x avg_segments_per_candidate_feature
```

Candidate count is itself a search-quality metric, so better search reduces
verification indirectly. That is exactly how B1 earned its 7.28x:

```text
Feature BVH   5.498 candidates x 12,872 segments  =  70,771 checks
Segment BVH   1.497 candidates x  6,490 segments  =   9,717 checks   <- cap 100 m
floor         1.000 candidate  x  6,490 segments  =   6,490 checks

at the cap-25 operating point the ladder actually runs (B2's choice, B6c measured):

Segment BVH   1.466 candidates x  6,417 segments  =   9,407.6 checks
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

                              Option A (byte-identical)  Option B (~1e-9 m)
  brute force                1,063,159 chk  1067.82 s        n/a
  Feature BVH                 70,770.6 chk    62.95 s          n/a
  Segment BVH                  9,407.6 chk     9.1167 s        ?   1.705 s  <- B2
  Hilbert + binary search     11,021.8 chk    17.7500 s        ?         ?
  Hilbert + RMI               11,021.8 chk    18.9003 s        ?         ?
  columns: checks, wall clock, index bytes, candidates/property, inflation cost

  index bytes    Segment BVH 119,768,836   Hilbert keys 9,516,712
                 + RMI model 4,194,400  =  13,711,112   (8.74x smaller)
  candidates/p   Feature BVH 5.498   Segment BVH 1.466
  inflation      capped geometric N_disk_infl / N_true_r = 6.397 countywide

  Option A measured at B6c, 2026-07-29, 7 reps + 1 warm-up, blocked, countywide.
  Segment BVH Option B wall clock from B2 (cap 25, 7 reps); its check count is
  not in B2's recorded table and is a B6c-2 deliverable. Option B for rungs 4
  and 5 is unmeasured and is the reason B6 is not closed.
  A check count is NOT comparable across the two columns (Nucleus 18.19, B2).

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

MEASURED, 2026-07-29. Record of how the framing above fared. The predictions are left
unedited on purpose (Nucleus 18.12); this is the outcome beside them.

HELD. Implementation 4 admits more work than implementation 3: 11,021.83 checks per
property against 9,407.62, +17.2 percent countywide and +17.1 percent at _10000 against
baselines that differ 7.4-fold. The regression 4-vs-3 exists to produce was produced.

HELD. 5-vs-4 is small in wall clock and does sit near noise: +6.48 percent countywide
against cell spreads of 4.6 to 14.2 percent. It was resolved anyway, by counting rather
than by timing. B5c's independently isolated 20.40 ns per resolve-descent entry predicts
the measured gap to within 0.2 percent, and a least-squares slope over twelve matched
pairs returns 20.33 ns/entry.

DID NOT HOLD. 4-vs-3 is not small: 1.947x slower countywide, 4.732x at _10000. The ~1.50x
headroom argument bounds how much FASTER an implementation can get by improving search; it
does not bound how much slower one can get by admitting more verification. Implementation
4 lost on the phase-2 side, about which the headroom figure says nothing.

INCOMPLETE. "Clean in both columns" is untested, because only Option A was run. Lines
124-126 of this document predict Option B is where the comparison becomes visible in wall
clock; B6c's inability to resolve either seeder's optimal window is the predicted
consequence of measuring only in the diluted column. B6c-2 tests it.

NOT FRAMED AT ALL, and the phase's actual contribution. 5-vs-4 has no fixed sign. It moves
from +11.6 percent at a +/-8 seed window to +0.001 percent at +/-2048, monotone across
nine points, and is predicted to roughly double under split verification. The seed window
was treated here as an implementation detail; it is the parameter that determines the
answer. See Nucleus 18.26 and 18.27.

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

## PROMPT — B6c-2 · The Option A / Option B cross-product

The B6 prompt above is retained as the historical record. It was answered in three
chunks — B6a (harness and protocol), B6b (SEED_WINDOW as a build parameter), B6c
(the ladder and a nine-window sweep) — which together overshot its task list and
undershot its headline table by one column. B6c-2 closes that column.

```text
CAPRM-Flood, Milestone 4 chunk B6c-2. Read Nucleus sections 14b, 18.16, 18.18, 18.19,
18.22, 18.24, 18.25, 18.26 and 18.27; docs/canon/CAPRM_Flood_Current_Status.md sections 2,
19b and 21 including the B2, B3b, B5c, B6a, B6b and B6c subsections; the B2 and B6 prompts
in this document. Confirm section 2's commit against `git log -1 --oneline` before
continuing.

OBJECTIVE
Measure the Option B column for rungs 4 and 5 and publish the cross-product. This is B6's
primary deliverable per the B6 prompt above, and the conversation-level prompt that ran
B6a-B6c restricted the ladder to Option A.

It is not a cosmetic gap. Lines 124-126 of this document state that under Option B the
verification ceiling lifts and the learned rung's advantage or disadvantage becomes visible
in WALL CLOCK rather than only in component metrics. B6c measured 5-vs-4 at +6.48 percent
against cell spreads of 4.6 to 14.2 percent and could not resolve either seeder's optimal
window. That is the predicted consequence of measuring only in the diluted column.

ALREADY MEASURED — do not re-run
  rung 3 under both modes, 7 caps, 7 reps + 1 warmup, countywide (B2)
    cap 25:  checks/property A 9,407.6   sec A 9.596   sec B 1.705   5.63x
    the 5.63x decomposes as 1.43x fewer checks x 4.21x cheaper per check, because an
    Option A check is projection plus parity and an Option B check is parity only
  Option B exactness for rungs 3, 4 and 5 (B3b: 267,362 field agreements, split included)
  the boundary hazard, closed (B2: minimum nonzero distance 0.002166405818047 m, about
    1.8e6 times the 1e-9 m snapping band, so no property is classified differently)

RUN
Rungs 3, 4 and 5 under BOTH verification modes, countywide, W=64, in ONE invocation, so the
column comparison carries no between-invocation term. B6c measured that term at ~1 percent,
negligible against a predicted ~5x column effect but not to be left implicit.

Verification mode is a third cell dimension in python/scripts/benchmark_water_ladder.py as
of B6c-2. The cell key omits `@original`, so B6c's recorded keys stay comparable. Rungs 1
and 2 have no verification-mode argument and are skipped under `split` with a note; they
verify over original geometry by construction.

GATING
Option B output is NOT byte-identical to Option A. B2 measured 8.82e-10 to 9.17e-10 m under
split against 4.658e-10 under original, so the Option B cells gate on
compare_python_cpp_water.py at 1e-6 m and these runs ESTABLISH the canonical Option B
digests. Confirm specifically that no feature_id disagreements appear. If one does, that is
the most important finding of the chunk; stop and report it rather than proceeding.
The Option A cells gate on the digests B6c recorded.

PREDICTIONS, DECLARED BEFORE RUNNING (Nucleus 18.12)
From B2's decomposition — verification work falls ~6.02x while search is untouched —
applied to B6c's Option A countywide medians:

                        A measured    B predicted
  segment_bvh              9.1167 s       ~1.62 s
  hilbert_binary          17.7500 s       ~8.97 s
  hilbert_rmi             18.9003 s      ~10.12 s

  4 v 3   1.947x slower  ->  ~5.5x slower
  5 v 4   +6.48%         ->  ~+12.8%

If these hold, two things follow. The cost of dimensionality reduction is currently
under-reported by ~2.8x, because implementation 4's search overhead is masked by a
verification cost it shares with implementation 3. And 5-vs-4 becomes resolvable on the
clock at countywide scale for the first time. If they do not hold, report the discrepancy
and explain it; do not adjust the prediction afterwards.

Watch the counter, not only the clock: rung 3's segment checks should fall roughly 30
percent under split, NOT 6x. The 6x is wall clock. Confusing the two is precisely the error
B2 warned about.

REPORT search and verification as SEPARATE columns, using this document's taxonomy
  TRAVERSAL      node visits/property and segment box tests/property (rungs 2-3);
                 seed probes, resolve-descent entries and nodes, range nodes, and the
                 uncounted 2W window scan (rungs 4-5)
  VERIFICATION   candidate features/property and segment checks/property
A segment check is NOT comparable across the two columns. The COLUMN difference is the cost
of exactness; the ROW difference is index quality.

OPTIONAL, only if the prediction holds
Repeat the nine-window sweep under Option B at countywide. Under B, search is a large
fraction of query time, so the window curve and the rmi/binary ratio are both sharpest
there. About 30 minutes; 18 cells.

ACCEPTANCE
  six cells complete in one invocation, one output digest per cell, no counter drift
  three Option A cells reproduce the digests B6c recorded
  three Option B cells exit 0 against the countywide reference with zero feature_id
    disagreements, and their digests are recorded as canonical
  every run's self-reported verification_mode matches the cell that claims it
  the cross-product published with wall clock beside counts in BOTH columns
```

---

## PROMPT — B6d · Close out the benchmark

```text
CAPRM-Flood, Milestone 4 chunk B6d. Read Nucleus 14b and 18.18-18.27,
docs/canon/CAPRM_Flood_Current_Status.md sections 2, 19b and 21, and
docs/canon/CAPRM_Flood_Roadmap.md PHASE B. Confirm section 2's commit against
`git log -1 --oneline`.

B6d writes no new measurements. Every derived number in the benchmark tables is computed by
python/scripts/analyze_b6_results.py and nowhere else; if an analysis is performed in
conversation it must land in that script with a test before it is quoted.

INPUTS, all generated
  outputs/benchmark/water_ladder_runs_{ladder,sweep,b6c2}.csv and .jsonl
  outputs/validation/water_ladder_summary_{ladder,sweep,b6c2}.json
  outputs/validation/b6_analysis.json, b6_benchmark_tables.md
  outputs/validation/b6*_counters*.csv
  outputs/validation/ladder_summary_*.json  (exactness, every cell)

PRODUCE
1. The benchmark table as THREE ADJACENT COMPARISONS — 3v2, 4v3, 5v4 — per workload and per
   verification mode. Never one global 5v3: that confounds the dimensionality reduction
   with the learning. Wall clock beside counts on every row, n beside every figure, and any
   comparison whose gap sits inside its cells' range marked NOT RESOLVED rather than
   printed as though it carried a claim.
2. Search and verification as separate columns throughout.
3. The seed-window result. 5-vs-4 has no fixed sign; any statement of it names its window,
   its verification mode and its workload (Nucleus 18.27).
4. Inflation as a first-class axis, including that the capped geometric inflation RISES on
   the near-water _10000 subset (6.92x) against countywide (6.40x) while phase-2 checks
   FALL 7.4x, and that the 2W window scan is an uncounted additive term whose per-entry
   cost differs from a resolve-descent entry's by ~7.8x.
5. Memory: persistent structure, peak resident, peak committed. They disagree in direction
   and none may be quoted alone.
6. docs/benchmark_results.md updated, and the three canonical documents updated. Verify
   README.md does not contradict them.

ACCEPTANCE
  the cross-product published, both columns, wall clock beside counts
  no number in any table computed outside analyze_b6_results.py
  the three canonical documents current, committed, and pushed, with the commit hash
  recorded in Current Status section 2 in a follow-up commit
```

---

## PROMPT — B7 · Learned radius (stretch)

```text
CAPRM-Flood, Milestone 4 chunk B7. STRETCH. Read docs/canon/CAPRM_Flood_Roadmap.md B7 and
Nucleus 14b, 18.26 and 18.27. Do NOT open this chunk before PHASE C is complete: it depends
on C's distance-field machinery and competes with C for the same remaining time. The
Roadmap lists it as not required.

BEFORE ANY IMPLEMENTATION — the literature check
Learned cost and cardinality estimation is established. Whether a learned RADIUS has been
applied to EXACT nearest-neighbour search over EXTENDED objects is the open question, and
it must be answered from primary sources before any novelty claim is written. If it has
been done, B7 becomes a replication; scope it as one or drop it.

THE DESIGN, if it proceeds
Predict r_hat; search disk(r_hat + L/2). A candidate at d <= r_hat proves disk(d) was fully
covered, so d is correct. Nothing found means double r_hat and retry. Overestimating is safe
and merely slower; underestimating costs a retry. Bias the model to overestimate and it is
admissible. The exact kernel still decides, and the tie rule does not change.

THE CONSTRAINT B6 IMPOSES
The seed seam's value is the QUALITY of the region it produces, and a wide-enough window
makes any seed irrelevant (Nucleus 18.26). A learned radius is the same bet at a different
seam. It must therefore be compared against a NON-LEARNED radius rule at matched
configuration, reported as an adjacent comparison, and stated with its window, its
verification mode and its workload named (Nucleus 18.27). A learned-radius result reported
at one operating point is one point on a curve.

ACCEPTANCE
  exact agreement countywide under both verification modes
  a measured retry rate, not an assumed one
  a comparison against implementation 5 that isolates the radius model's own contribution
  rather than the region size it happens to produce
```

---

## PROMPTS — C1..C4 · Neural surrogate

Finalize when Phase B outputs exist. Compact briefs, updated for B1:

C1 · Training data and a spatial-block split

```text
CAPRM-Flood, Milestone 4 chunk C1. Read Nucleus 14b and 18.25, and 18.18-18.27
for the defect shape named below; docs/canon/CAPRM_Flood_Current_Status.md
sections 2, 19b and 21; docs/canon/CAPRM_Flood_Roadmap.md PHASE C. Confirm
section 2's commit against `git log -1 --oneline`.

PHASE C abandons exactness deliberately. The error is the point. C1 builds no
model — it builds the dataset and the split, and the split is the whole chunk.

THE DEFECT SHAPE THIS CHUNK IS EXPOSED TO
  PHASE B spent B6d on one recurring failure: a dimension the code does not know
  is a dimension. `by_algorithm[row["algorithm"]] = row` kept the last write and
  silently dropped an entire verification mode; the same shape then appeared for
  invocation in four more functions. Each time the code produced a plausible
  number and no error.

  A random train/test split is that shape exactly. Adjacent parcels share a FEMA
  polygon, sit metres apart on the same DEM cells, and frequently select the same
  nearest water feature. A random split places near-identical records on both
  sides and reports memorization as generalization — plausibly, silently, with a
  good score. The target makes this worse, not better: water carries 65 percent
  of the index variance and 98.1 percent of properties are tied at the same FEMA
  component, so the label is dominated by distance-to-water, which is about as
  spatially autocorrelated as a field gets.

  Therefore: block membership is part of the partition key from the start, not a
  filter applied afterwards, and the gate is MEASURED rather than asserted.

INPUTS, all generated, none to be modified
  outputs/index/property_exposure_index_countywide.csv
      the frozen v2 index. Label column `exposure_index_0_100`, key
      `property_id`, and every row carries `scoring_policy_version` — assert it
      reads `preliminary_exposure_index_v2` rather than trusting the path.
  outputs/validation/property_exposure_index_countywide_manifest.json
      policy, weights, checksums. Verify the CSV against it before using either.
  outputs/cpp_input/water_properties_projected_countywide.csv
      x, y in EPSG:26918. The join to the index is on `property_id` and is NOT
      assumed to be clean: verify the key matches, verify both sides carry
      267,362 rows, and report any asymmetry rather than dropping it with an
      inner join.
  python/caprm/scoring.py                    read only; scoring stays frozen
PRODUCE
1. A supervised dataset: input (x, y) in EPSG:26918, target
   exposure_index_0_100 at preliminary_exposure_index_v2, 267,362 rows, unique
   property IDs verified, no nulls. Row count and unique-ID count checked, not
   assumed. Scoring is frozen at v2 and C1 does not touch it; if a label cannot
   be produced without changing scoring.py, stop and say so.

2. A spatial-block partition. Whole blocks assigned to train / validation /
   test. Record block edge length in metres, the RNG seed, the block grid origin,
   the per-split row counts and the per-split block counts. The block size is a
   parameter with a defensible justification, not a magic constant — state what
   spatial correlation length it is chosen against and how that length was
   estimated from the data rather than assumed.

3. The gate, measured. For every test property, the metric distance to the
   nearest TRAINING property, and the block-grid Chebyshev separation. Report the
   minimum, the distribution, and the count of violations. Define "within one
   block" precisely and in one place; do not let a metric criterion and a grid
   criterion drift apart. Same for train/validation.

4. A POSITIVE CONTROL for the gate. Nucleus 18.25: a neutrality gate requires a
   positive control — B6b built seven binaries against source that never
   referenced the macro and the gate passed on all of them. So: build a random
   split as well, run the identical gate on it, and confirm the gate FAILS.
   A gate that passes on both partitions is not measuring anything, and its
   passing on the block split means nothing until the random split fails it.

5. Both splits persisted, with a manifest: seed, block size, grid origin, row
   and block counts per split, and a checksum of each assignment file. The random
   split is kept deliberately — C2 reports the memorization gap between the two,
   and that number is what the discipline bought.

6. Baseline for C2 to beat, declared NOW, before any model exists. A
   nearest-training-neighbour predictor: copy the index of the geometrically
   closest training property. On a target this autocorrelated it will score well,
   and it is the honest floor. Record its test error under the block split. A
   surrogate that does not beat it has learned nothing about the function, only
   about the neighbourhood.

7. All of the above computed in python/caprm/, called from a thin CLI in
   python/scripts/, with tests. No number reported in conversation is reportable
   until it lands in the module with a test — the rule
   analyze_b6_results.py exists to enforce.

ACCEPTANCE
  267,362 rows, unique IDs verified, no nulls in input or target
  block size justified against a measured correlation length, not asserted
  gate measured on the block split and PASSED
  gate measured on the random split and FAILED  (the positive control)
  both splits deterministic under a recorded seed, verified by rerun
  nearest-neighbour baseline error recorded before any model is trained
  scoring.py unmodified; the v2 index and its manifests unmodified
  the three canonical documents updated, committed, pushed, hash recorded in
    Current Status section 2 in a follow-up commit
```


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

- **RESOLVED at B6c; policy set.** `outputs/` is ignored wholesale, so the C++ artifacts of
  record lived outside the repository. The policy is now: force-add the measurement of
  record and the derived analysis — the ladder and sweep runs CSVs and JSONL (0.63 MB
  total), the summary JSONs, the counter CSVs, `b6_analysis.json` and
  `b6_benchmark_tables.md` — and keep out `outputs/benchmark/ladder_work/` (1.056 GB of
  regenerable per-cell CSVs) and the per-property agreement details. Anything a number in
  the canonical documents rests on is tracked; anything regenerable from it is not.
- **RECURRED, and is the reason the staleness check exists.** Current Status section 2 read
  `0dd85ab` while the remote was at `b3ec90d` after B1. It happened again at B5c: section 2
  read `f2e2e00` with "B5c pending" while HEAD was `86ff32b`, and it also had B2 at the
  wrong commit. Nothing enforces the check, so the mitigation is procedural and lives in
  the recommended first prompt: a new assistant diffs section 2 against
  `git log -1 --oneline` and says so before trusting anything else in the document. A
  pre-commit check is the real fix and is still unwritten.
- **NEW from B6c.** Two files carry a figure the ladder does not use. B1's 9,716.87 checks
  per property is its cap=100 measurement; the ladder runs at cap=25, where the value is
  9,407.6. Corrected in this document; verify `tests/test_ladder_benchmark.py`'s
  `SEGMENT_BVH_STDOUT` fixture and `docs/benchmark_results.md` before the report is
  written.