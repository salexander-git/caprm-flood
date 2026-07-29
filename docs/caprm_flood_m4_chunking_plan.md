# CAPRM-Flood — Milestone 4 Conversation Chunking & Execution Plan

Purpose: complete Milestone 4 (and with it the project) across many conversations
without losing continuity, and with clear task boundaries that map onto cowork.

## How to use this

- **One chunk ≈ one conversation.** Open a new conversation per chunk. Start it by
  pasting (a) that chunk's block from this file and (b) the files listed under
  "Inputs to paste." That reproduces the working context without relying on chat
  history.
- Each chunk closes only when its **Acceptance** items pass and its **Doc updates**
  are written. That is the same completion gate the project methodology already uses.
- When a chunk finishes, update this file's status line for it before moving on.

## Cowork / Claude Code compatibility

Severing the GitHub connection only detached this chat project's context feed. A
desktop **Claude Code** or **Cowork** session pointed at the local `caprm-flood`
folder reads and writes it directly. It does **not** load the whole folder into
context — it lists, greps, and reads files on demand — so large data and generated
directories are excluded via `.claudeignore` (below) to keep the session focused,
not because they would otherwise be "ingested."

- **Build / compile / run chunks (B1b/c, B3, B5, B6) → Claude Code (desktop).** It
  runs scripts and the C++ build against the local data. Opening a file to *read* it
  costs context; running a script that *processes* a large file does not, and the
  session won't read multi-hundred-MB data wholesale.
- **Analysis / writing chunks (C3, D5, E1) → Cowork.**

Each chunk still has an authoring half (write code/tests/docs) and a validation half
(compile + run countywide + measure). Both can run in a desktop session with folder
access; you review the plan and confirm design choices at the start. The
"paste results back" loop is a fallback for surfaces without folder access, not the
only path.

### Keep the massive folder out of scope

The raw data and virtual environment dominate the folder's size. Add a
`.claudeignore` at the repo root so the session doesn't traverse them:

    .venv/
    data/
    **/__pycache__/
    cpp/**/build/
    *.exe

Ignored paths stay on disk and remain readable on explicit request; they are just
not auto-loaded during exploration. `outputs/` is left in scope because several
chunks read manifests under `outputs/validation/`; if its size becomes a problem,
also ignore `outputs/cpp_input/` and `outputs/cpp/` and keep `outputs/validation/`.
When a chunk needs one specific generated file, name it in the prompt so the session
reads it directly.

---

## Locked result — B1a (measure L). STATUS: DONE

- Segments countywide: **1,063,159** (matches `data_sources.md` — reconstruction is
  faithful).
- Distribution (EPSG:26918 m): min 0.03, median 5.52, mean 9.84, p90 21.7, p95 32.1,
  p99 69.0, p99.9 168.7, **max L = 5,748.24**.
- Longest segment: feature_index 7445 = `waterbody:L1E1P`, **Lake Ontario**, polygon
  boundary chord.
- Naive inflation L/2 = **2,874 m** applied to all ~267k queries — untenable.
- **Design decision:** split segments longer than a cap (target 100 m) before
  indexing. Distance-exact (min over the two halves = original point-to-segment
  distance). p99.9 = 169 m, so < ~0.1% of segments are touched; capped L/2 ~ 50 m.
- Still to grab locally (optional, non-blocking): the tail counts `>200/>500/>1000 m`
  to quantify exactly how many segments splitting touches.

---

## Phase B — learned indexing (the contribution)

### B1b/B1c — Segment BVH + splitting. STATUS: DONE (2026-07-22, commit 998c859)
**Objective:** build an exact nearest-water index over ~1.06M individual segments
(with the long-segment split applied), reusing the exact kernel, matching the Python
oracle field-for-field.
**Inputs to paste:** `water_distance_bruteforce.cpp`, `water_distance_indexed.cpp`
(both already seen), `water_export.py` (seen), plus `water_validate.py`,
`export_water_cpp_inputs.py`, `compare_python_cpp_water.py`, and the C++ build
command/CMake or your compile line.
**Design decisions:** (1) split cap value (100 m proposed) and where splitting lives
— in the vertex export vs a new pre-index pass; (2) each segment leaf carries its
parent `water_feature_id` for tie-breaking; (3) **preserve polygon-interior → 0**:
for polygon features, a point inside the ring is distance 0 regardless of nearest
boundary segment, so the segment path must retain a per-polygon membership test.
**Deliverables [authoring: cowork]:** segment-splitting code + a `segment_bvh` C++
program (same `#include`-the-kernel pattern as the Feature BVH); unit tests for the
split (distance-invariance) and for interior-zero behavior.
**Acceptance [validation: local]:** countywide segment-BVH output agrees with the
Python `nearest_water` reference at the current tolerance (max error ~1e-9 m class);
the ~266 zero-distance properties stay zero; row count 267,362; unique property IDs.
**Artifacts:** `cpp_nearest_water_segment_bvh_countywide.csv`, a segment-count +
split manifest, an agreement report.
**Doc updates:** Current Status (B1 done, numbers), Roadmap (mark B1, refine B2),
Nucleus (segment index + splitting as durable method); `data_sources.md` unaffected.
**Conversation budget:** fits one conversation if the build compiles cleanly; if the
interior-zero handling gets fiddly, split acceptance into a second short conversation.

### B2 — run-size sweep. STATUS: DONE (2026-07-23, cap 25 m chosen)
**Objective:** sweep segment "run size" {1,2,4,8,…} and produce the
pruning-vs-inflation tradeoff curve; pick and justify an operating point.
**Inputs to paste:** B1 outputs + `water_benchmark.py` (seen),
`benchmark_water_cpp.py`.
**Cowork fit:** authoring the sweep harness is cowork-friendly; the runs are local.
**Acceptance [local]:** curve produced; operating point chosen with a stated reason.
**Budget:** one conversation.

### B3 — Hilbert + inflation + binary-search control. STATUS: DONE
(B3a fixture 2026-07-28; B3b countywide 2026-07-28)
**Objective:** replace the 2D box hierarchy with a 1D Hilbert ordering of segment
midpoints; implement the `r + L/2` inflated-disk search; validate exactness with a
**binary-search** query (the control — non-optional, or B6 can't attribute a win/loss
to learning vs dimensionality reduction).
**Design decisions:** Hilbert curve resolution + coordinate normalization (both into
the manifest); confirm the capped L feeds the inflation radius.
**Cowork fit:** authoring is cowork-friendly; this is the hardest geometry, so expect
**two conversations** (B3a: keys + sort + inflation + query; B3b: validation + edge
cases). Documented fallback if the disk→curve-range decomposition overruns: expand the
candidate window to cover the inflated disk's bounding box — cruder, still exact.
**Acceptance [local]:** MET 2026-07-28. Hilbert + binary search reproduces the
reference field-for-field countywide (267,362/267,362, three configurations, exit
0, max abs error 4.658e-10 m original / 9.157e-10 m split). Inflation measured
6.397x capped versus 3,493.3x uncapped — splitting bought 546x. Box-vs-disk gate:
enable (1.875x phase-1, 7.55% phase-2). Control characterized at 20.2376 probes
mean / 21 max. The uninflated-disk denominator named in the original acceptance
line was degenerate and was replaced by `n_true_r` before measurement; see
Current Status, B3b.

### B4 — train RMI (the ML index). STATUS: next  [authoring: cowork]
Two-stage recursive model index, linear models, numpy least-squares, no framework.
Emit weights + seed + training-array checksum + manifest. **Acceptance:** predicted
position + recorded per-model error bound provably contains the true position for
**every** key — exhaustive over all 1,189,589, not sampled, reported per
second-stage model. 79 keys are exact duplicates, so the position mapping is not
injective: state the convention (first or last position of the run) and make the
bound valid under it. Control to beat: 20.2376 probes mean, 21 max. Ceiling: the
model replaces ~20 probes out of ~11,922 phase-2 segment checks per property, so
judge it on search-side metrics, not on an end-to-end speedup the workload cannot
deliver. Python trains. One conversation.

### B5 — port RMI inference to C++. STATUS: pending B4
~50 lines: normalize → root model → leaf model → predicted position → clamp →
bounded-window search, reusing the B3 query path. C++ infers only. **Acceptance
[local]:** byte-identical evidence to the B3 binary-search control. One conversation.

### B6 — benchmark the ladder. STATUS: pending B5
Extend `water_benchmark.py` (currently hard-codes only `brute_force`/`feature_bvh`)
to accept `segment_bvh`, `hilbert_binary`, `hilbert_rmi`. Report three adjacent
comparisons (granularity 3vs2, dimensionality 4vs3, learning 5vs4); inflation and
memory as first-class columns. **State the negative-result possibility before running
— a clean "learning doesn't help at ~1M keys/2D, here is the inflation cost" is a
valid result.** One conversation (authoring) + local runs.

### B7 — learned radius (stretch). STATUS: optional, after C2
Uses the Phase C surrogate's coordinate→distance mapping to seed the exact query's
radius. Needs a related-work check before any novelty claim. Defer unless time allows.

---

## Phase C — neural surrogate (the counterpoint)

- **C1 — spatial-block split.** Grid blocks ~km-scale; whole blocks to train/val/test;
  verify no test property within one block of a training property. [authoring: cowork]
- **C2 — train surrogate.** Small MLP on normalized coords (Fourier features worth
  trying); target the pipeline's own deterministic output, not flood outcomes; never
  replace the scoring layer. [authoring: cowork; training local if data is large]
- **C3 — error analysis (the real result).** Residuals should spike along FEMA-zone
  boundaries (a smooth net can't represent a 34-point step) and be small elsewhere;
  map residuals in space and confirm/refute on the record.
- **C4 — benchmark surrogate.** Inference time vs exact pipeline, model size, accuracy
  vs distance-to-discontinuity. Frame value honestly (differentiable; evaluable
  anywhere) — neither is a production claim.

Phase C can run in parallel with B4–B6 once the index semantics are frozen, since it
only consumes the frozen index CSV.

---

## Phase D — engineering hardening

- **D1** end-to-end reproducibility from clean state.
- **D2** runtime instrumentation of the whole Python pipeline (currently only the C++
  query is timed — a real gap).
- **D3** consolidate validation across all evidence families.
- **D4** cleanup (tracked 21 MB `.gpkg`, silent `expected_paths` check, empty M1
  files, untracked course docs).
- **D5** figures for specific claims — home for `explain_property.py` (coordinates →
  evidence → component contributions → rank), the strongest demo, still unbuilt.
- **D6** release-quality freeze.

`data_sources.md` already exists and is thorough, so D-phase provenance work is
verification/spot-check, not authoring.

---

## Phase E — academic deliverables

- **E1** report. **E2** ~8-minute presentation + the single-property trace demo.
  **E3** portfolio polish.
- **Blocker to confirm:** `Professor_Milestone_Requirements.txt` (in the repo, not yet
  read this cycle) governs the final-milestone format and deadlines. Read it before
  scoping E and before committing to B7/Phase S stretch.

---

## Phase S — precipitation (gated stretch, optional)

Only after B and C are complete **and documented**. Not required for completion. If
it happens: cache script with recorded retrieval date from the start, config
declaration, property-level evidence + validation + manifest, integration as a fifth
index component at v3.

---

## Critical path

B1b/c → B2 → B3(a,b) → B4 → B5 → B6, then D → E. C runs alongside B4–B6. B1, B2
and B3 are complete as of 2026-07-28; B4 is next. E is gated on reading the
professor requirements file.

## Canonical-doc update status

B1a, B1b/c, B2, B3a and B3b are all written into Current Status §21, Roadmap
PHASE B, and Nucleus 18.19 / 18.22 as of 2026-07-28. No canonical-doc updates are
outstanding.

Commit status: B1 is committed at 998c859. **B2, B3a and B3b are validated and
commit-pending.**