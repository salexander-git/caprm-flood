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

Read this before any remaining Phase B prompt. It is the single most important
result B1 produced, and it is not what B1 was expected to produce.

B1 measured, countywide, per property:

```text
phase 1  search        28.29 node visits  +  6.49 segment box tests  ~= 35 operations
phase 2  verification  9,716.87 segment checks
```

**Over 99 percent of remaining query work is verification, not search.** Search
is already nearly free. This follows directly from B1's design decision: to
guarantee output byte-identical to the reference, the final distance is computed
by the unchanged exact kernel over each candidate feature's *entire original
geometry*, which rescans about 6,490 segments per candidate feature.

The consequence is an Amdahl ceiling. Any further improvement confined to
*search* — Hilbert ordering, a learned position model, a better tree — can at
best remove that ~35-operation term. If verification stays at 9,716.87 segment
checks, the total achievable speedup from B3, B4, and B5 combined is on the
order of one part in three hundred, which will be indistinguishable from timing
noise.

This does not invalidate the phase. It sharpens what the phase is measuring, and
it must be stated in advance rather than discovered in B6.

### The design fork this creates

```text
Option A  Verify over ORIGINAL feature geometry     (what B1 does)
          exact to 4.658e-10 m, byte-identical to the reference
          verification cost ~9,717 segment checks/property
          index improvements are capped by Amdahl at ~1.003x

Option B  Verify over SPLIT SEGMENT geometry
          the traversal already reaches the nearest sub-segment; report that
          distance instead of rescanning the parent feature
          verification cost collapses to tens of segment distance evaluations
          expected agreement ~1e-9 m rather than ~4.7e-10 m, because split
          endpoints are interpolated and differ from the original segment's
          endpoints in the last few ULPs (measured worst case in B1's unit
          tests: 1.18e-9 m)
          still passes the harness: the tolerance is 1e-6 m
          tie-breaking remains stable: the 1e-6 m tie tolerance is roughly
          three orders of magnitude larger than the perturbation, so a
          near-tie is resolved as a tie by water_feature_id either way
```

**Do not choose Option B silently, and do not choose it by default.** It trades
a provable property (byte-identical output) for a measurable one (search
improvements become visible). It is a project-level decision, it belongs to B2,
and whichever way it goes it must be recorded in the Nucleus with its reasoning.

If Option A is kept, Phase B's honest framing is: *a segment-granularity index
reduces the geometric work by 7.28x and drives search cost to near zero; the
remaining cost is exact verification, which no index can remove.* That is a
legitimate and defensible result. It is also a narrower claim than "learned
indexing beats a segment BVH," and the report must not overstate it.

---

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

DECISION TO RESOLVE IN THIS CHUNK — verification strategy
B1 measured search at ~35 operations/property against verification at 9,716.87 segment
checks/property. Search is therefore ~0.4% of query work and an Amdahl ceiling of roughly
1.003x applies to every later search-side improvement (B3, B4, B5).

Present the Option A / Option B fork (see "THE B1 FINDING" section of this document) with
measured evidence, and get an explicit decision before B3a is written:
  A  keep verification over original feature geometry: byte-identical output preserved,
     later index work cannot show a wall-clock win
  B  verify over split segment geometry: verification collapses, agreement moves from
     ~4.7e-10 m to ~1e-9 m, still far inside the 1e-6 m harness tolerance
Prototype Option B on the 1,000-property fixture and MEASURE the resulting agreement
before recommending either. Do not adopt Option B on argument alone.

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
Because verification dominates, wall clock may be nearly INSENSITIVE to this parameter.
If the curve is flat, report it as the finding and explain why. Do not tune until a
preferred shape appears. A negative result is a result (Nucleus 18.18).

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
  a recorded decision on the verification-strategy fork
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
2. MIRROR B1'S TWO-PHASE STRUCTURE unless B2 selected Option B. Phase 1 selects candidates
   by Hilbert range; phase 2 runs the unchanged kernel and tie rule over candidate
   features. This is what makes byte-identical output achievable, and it lets 4-vs-3
   isolate the dimensionality reduction with everything else held constant.
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
  Expected max abs error depends on the B2 verification decision:
    Option A (verify over original geometry)  -> 4.658e-10 m, matching B1 and the Feature
                                                 BVH exactly
    Option B (verify over split geometry)     -> ~1e-9 m; state the measured value and
                                                 confirm no feature_id disagreements
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
checks). Under B2 Option A, a perfect position predictor cannot produce a measurable
end-to-end speedup. The RMI is therefore being evaluated on SEARCH-side metrics —
predicted-position error, search-window size, key throughput — and any wall-clock claim
must be reported against that ceiling. Frame this before training, not after benchmarking.

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

WHAT B5 CANNOT CLAIM
Under B2 Option A the end-to-end speedup is capped near 1.003x by verification cost. Report
the search-side improvement separately from wall clock, and do not present a wall-clock
difference inside timing noise as a win.

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

FRAME THE RESULT BEFORE INTERPRETING IT
B1 measured search at ~0.4% of query work. Under B2 Option A, comparisons 4-vs-3 and 5-vs-4
are expected to be flat in wall clock by construction, and the honest headline is:
  segment granularity produced a 7.28x reduction in geometric work and drove search cost to
  near zero; beyond that point exact verification dominates, and no index — learned or
  otherwise — can remove it.
That is a real finding and it is the one the data supports. Do not tune to force a learned
win. A negative result, stated in advance and measured against an exact baseline, is a
result (Nucleus 18.18). If B2 selected Option B, the comparisons become live and should be
reported straight, whichever way they fall.

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