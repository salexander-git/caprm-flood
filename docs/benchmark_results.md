# Milestone 2 Benchmark Results

## Purpose

The nearest-water benchmark evaluates whether a feature-level bounding-volume hierarchy reduces the work and runtime of the independent C++ geometry implementation relative to exhaustive brute-force search while preserving identical property-level results.

## Algorithms

### Brute force

For every property, examine every water feature and every required segment or polygon ring until the exact nearest feature is known.

### Feature BVH

Build an axis-aligned bounding-volume hierarchy over feature bounding boxes. Traverse nodes in lower-bound distance order, prune nodes and features that cannot improve or tie the current best result, and run the same exact geometry kernel only for surviving candidates.

The indexed algorithm changes search strategy, not distance semantics.

## Harness

`python/scripts/benchmark_water_cpp.py` calls the two executables as subprocesses and produces:

```text
outputs/benchmark/water_cpp_benchmark*_runs.csv
outputs/validation/water_cpp_benchmark*_summary.json
```

The harness:

- supports warmups and measured repetitions;
- alternates measured algorithm order when repetitions allow;
- records executable and input paths plus executable SHA-256 values;
- measures total subprocess wall-clock duration;
- parses input loading, index construction, computation, throughput, node visits, candidate checks, and segment checks;
- verifies invariant property, feature, vertex, and segment counts;
- reports distributions and median speedups.

## Timing definitions

- **Input loading:** executable-reported parsing and geometry reconstruction time.
- **Index construction:** executable-reported BVH build time; brute force has no index-construction phase.
- **Computation:** executable timer around the property loop. It includes exact nearest-feature calculation, CSV row writing, and progress logging.
- **Total process:** harness-measured subprocess wall-clock duration, including startup, loading, index construction, computation/output, and termination.

Output writing is not independently timed, and `computation` must not be described as query-only time.

## Results

| Workload | Water features | Segments | Repetitions | Warmups | Brute computation | BVH computation | Computation speedup | Brute total | BVH total | Total speedup |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 4,159 | 695,820 | 7 | 1 | 2.333 s | 0.101 s | 23.11x | 3.190 s | 0.968 s | 3.29x |
| 10,000 | 8,572 | 1,063,159 | 7 | 1 | 48.945 s | 1.024 s | 47.80x | 50.285 s | 2.337 s | 21.52x |
| 100,000 | 8,572 | 1,063,159 | 1 | 0 | 395.093 s | 31.231 s | 12.65x | 396.580 s | 32.633 s | 12.15x |
| 267,362 | 8,572 | 1,063,159 | 1 | 0 | 1,139.744 s | 55.892 s | 20.39x | 1,141.386 s | 57.567 s | 19.83x |

Median values are shown. With one repetition, the minimum, median, mean, and maximum are identical.

### Search-work reduction

| Workload | Brute segment checks | BVH segment checks | Reduction | Segment-check factor | Candidate features/property | Candidate fraction |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 695,820,000 | 33,315,374 | 95.21% | 20.89x | 6.965 | 0.1675% |
| 10,000 | 10,631,590,000 | 340,112,139 | 96.80% | 31.26x | 7.815 | 0.0912% |
| 100,000 | 106,315,900,000 | 11,319,486,859 | 89.35% | 9.39x | 6.514 | 0.0760% |
| 267,362 | 284,248,316,558 | 18,921,369,157 | 93.34% | 15.02x | 5.498 | 0.0641% |

### Indexed throughput and traversal

| Workload | BVH throughput | Node visits/property | Segment checks/property |
|---:|---:|---:|---:|
| 1,000 | 9,907.0 properties/s | 25.468 | 33,315.374 |
| 10,000 | 9,766.3 properties/s | 27.873 | 34,011.214 |
| 100,000 | 3,202.0 properties/s | 27.507 | 113,194.869 |
| 267,362 | 4,783.6 properties/s | 25.012 | 70,770.600 |

## Correctness prerequisite

Performance results are accepted only after strict comparison against the Python reference. Both brute-force and indexed outputs achieved 100% all-field agreement at every scale.

| Workload | Validated rows | Maximum absolute distance error |
|---:|---:|---:|
| 1,000 | 1,000 | `4.386e-10 m` |
| 10,000 | 10,000 | `4.637e-10 m` |
| 100,000 | 100,000 | `4.656e-10 m` |
| 267,362 | 267,362 | `4.658e-10 m` |

The `1e-6 m` acceptance tolerance is therefore much larger than the observed floating-point differences.

## Interpretation

The experiment supports the algorithmic claim that the BVH avoids examining every water feature and substantially reduces exact segment checks. The countywide run reduced candidate consideration to approximately 5.5 of 8,572 features per property and achieved a measured `20.39x` computation speedup.

Runtime is not a function of property count alone. Property spatial distribution changes which feature bounds survive pruning and how geometrically complex those candidates are. This explains why throughput and speedup are not monotonic across nested workloads.

The 10K workload produced the largest measured speedup. The 100K workload required more exact segment work per property despite a similar number of candidate features, indicating that its surviving features were more segment-dense. The countywide extension lowered average segment work and improved indexed throughput relative to 100K.

## Comparability caveat

The 1K benchmark used an earlier hydrography fixture containing 4,159 features and 695,820 segments. The 10K, 100K, and countywide benchmarks use the final 8,572-feature, 1,063,159-segment cache. The 1K row establishes small-workload behavior and repeated-run stability but is not a clean final-cache scaling point.

The 10K result uses seven repetitions and one warmup per algorithm. The 100K and countywide results use one repetition and no warmup to keep exhaustive brute-force evaluation tractable. Their exact speedup values should be presented as single measured comparisons, not stable distribution estimates.

## Unmeasured dimensions

- Peak or resident memory was not measured.
- Output-writing time was not isolated from the property loop.
- Hardware metadata was not embedded in the benchmark summaries.
- Compiler identity and flags are not embedded; executable checksums identify the exact binaries.
- No parallel implementation was evaluated.
- No one-million-query workload was run.

Future benchmark refinement should add reproducible memory measurement, query/output timer separation, compiler metadata, and repeated large-scale indexed trials. Those additions are not required to support the present correctness and search-pruning claims.

---

# Milestone 4 PHASE B — the five-rung ladder

The numbers in this section are NOT maintained here. Every derived quantity is
computed by `python/scripts/analyze_b6_results.py` from
`python/caprm/ladder_analysis.py` and written to
`outputs/validation/b6_benchmark_tables.md`, which is regenerated and must not be
hand-edited. This section states the method, the reading rules and the durable
findings; the generated file is authoritative for every figure.

```powershell
.\.venv\Scripts\python.exe python\scripts\analyze_b6_results.py
```

## The ladder

Five implementations over the same geometry kernel, the same tie rule and one
validation standard, so that adjacent rungs isolate one variable each.

```text
1. brute force              no index                    Milestone 2
2. Feature BVH              2D,  8,572 features         Milestone 2
3. Segment BVH              2D, ~1.19M entries          B1, B2
4. Hilbert + binary search  1D, ~1.19M entries          B3   control
5. Hilbert + RMI            1D, ~1.19M entries          B4, B5   learned
```

## Reading rules

These are not presentational preferences. Each one exists because ignoring it
produced a wrong number during PHASE B.

- **Three adjacent comparisons, never one global 5-v-3.** A single comparison
  across rungs 3 and 5 confounds the dimensionality reduction with the learning,
  which is the entire reason the ladder has five rungs rather than three.
- **Rung 1 is in no adjacent comparison.** `brute_force@countywide` carries a
  31.71 percent spread at n=3, five times any other cell. Its figure is an
  order-of-magnitude statement and appears separately as context.
- **Every comparison names its workload, its verification mode and its seed
  window.** All three move the result; see Nucleus 18.27 and 18.30.
- **The absolute gap is published beside every ratio.** Across the six
  cross-product cells the 5-v-4 absolute gap holds between 4.442 and 6.188
  us/property while the percentage ranges 7.2 to 19.2. The counted quantity is
  the invariant; the percentage is an artifact of the denominator.
- **A comparison whose gap sits inside its cells' own range is marked NOT
  RESOLVED** rather than printed as though it carried a claim.
- **Segment-check counts are comparable within a verification mode and not
  across modes**, and not across implementations that verify differently.
- **Ratios are reported within an invocation, absolutes with their invocation
  named.** Absolutes move about 1 percent between invocations while adjacent
  ratios agree to 0.116 percentage points. A comparison that must cross an
  invocation is flagged, not suppressed.
- **Option A dilutes 4 v 3.** Rungs 3 and 4 share the verification term, so the
  Option A ratio divides two numbers that mostly consist of the same work.
  Option B is the correct column for that comparison.
- **No memory instrument may be quoted alone.** Persistent structure, peak
  resident and peak committed disagree in direction (Nucleus 18.24).

## Protocol

3+1 warm-up at rung 1 and 7+1 at rungs 2-5, blocked by repetition and cyclically
rotated by block index, dispersion always reported as min/median/max with
relative spread, stdout captured to a pipe on every run, crash-safe
append-and-fsync recording, and a session guard. The guard exists because two
sittings of an identical rung-1 configuration were measured 11.02 percent apart
on provably identical work.

Runs carrying `--verify-counts`, `--uncapped-half` or `--seed-error-stats` are
not benchmark-eligible; `--query-stats` is free and is eligible.

## Sources

Five invocations, 137 re-derived invariants, all passing.

```text
outputs/benchmark/water_ladder_runs_ladder.csv    15 cells  ladder, 3 workloads
outputs/benchmark/water_ladder_runs_sweep.csv     18 cells  9 windows, Option A
outputs/benchmark/water_ladder_runs_b6c2.csv       6 cells  cross-product probe
outputs/benchmark/water_ladder_runs_sweepB.csv    18 cells  9 windows, Option B
outputs/benchmark/water_ladder_runs_gridAB.csv    18 cells  mode x workload grid
```

## Findings

**The measured result is negative at the shipped configuration and CONDITIONAL.**
At countywide, seed window 64, original-geometry verification, the learned rung
produces byte-identical evidence and runs 7.2 percent slower. Across nine seed
windows that penalty falls to 0.002 percent, and under split-geometry
verification at window 2048 it reverses: the learned rung is 0.125 percent
faster. The sign is set by parameters the literature holds fixed.

**The mechanism is convexity, not miss frequency.** Search cost grows as the
square of the seed radius. The miss rate moves only 1.19x while the worst
overestimate moves from 32x to 517x the true radius. The mean prediction error is
the wrong summary statistic for a predictor that feeds a radius.

**A cost model built on a constant measured elsewhere predicts the wall clock.**
B5c isolated the marginal cost of one resolve-descent entry at 20.40 ns before
any B6 timing existed. Least-squares slopes through the origin over the B6 data
land at 20.50, 21.10 and 21.34 ns/entry depending on the population. The
population is part of the number and is named in the artifact; a slope over the
window sweep and a slope over the sweep plus other workloads are different
quantities, and reporting them under one label is how 20.33 and 21.02 came to
look like a contradiction.

**Search and verification separate cleanly.** Per-check cost is calibrated from
rung 3 alone per workload and mode; rungs 4 and 5 never enter the calibration and
their implied search costs agree between modes to 1.0-2.6 percent at five of six
cells, as mode-invariance requires. The exactly-determined alternative, which
needs no assumed search fraction, is ill-conditioned and returns a negative
search cost; it is retained in the artifact as a recorded failure. See Nucleus
18.31 for both of its boundaries.

**Inflation is a first-class axis and is not monotone.** Ordering extended
objects by a representative point requires searching `disk(r + L/2)` to stay
exact. Capped geometric inflation and phase-2 verification move in OPPOSITE
directions across workloads, so neither figure means anything without its
workload. The `2W` seed-window scan appears in no emitted counter and its
per-entry cost differs from a resolve-descent entry's by roughly 7x, so the two
are reported side by side and never summed.

**Memory has three instruments and they disagree in direction.** On persistent
structure the Hilbert path is far smaller than the segment BVH; on peak resident
memory the segment BVH is smaller; on peak committed memory the Hilbert path is
smaller again. Peak resident is the wrong instrument for a model's size cost
specifically, because the peak occurs during index construction before the model
is loaded.

## Exactness

Every implementation claiming exactness agrees field-for-field with the Python
reference at every workload in both verification modes.

```text
Option A  267,362/267,362 and both subsets, all fields   max 4.658e-10 m
Option B   10,000/10,000  all fields                     max 8.659526e-10 m
Option B  100,000/100,000 all fields                     max 9.066881e-10 m
```

The Option B bound is wider because split geometry introduces one additional
rounding in the split-point computation. Correctness is not a benchmark result
and is gated separately, by `compare_python_cpp_water.py`, before any timing is
reported.

## What this benchmark does NOT measure

The `_10000`, `_100000` and `_countywide` workloads vary QUERY COUNT at a fixed
index of 1,189,589 entries. The exporter writes the whole feature table
regardless of the property set, so all three build the identical index. **This is
not the index-size axis the learned-index literature argues over.** That axis
would need a defensible hydrography subsetting scheme, a reference recomputed at
each subset, and the model retrained at each N. It is not attempted here and no
claim in this document should be read as bearing on it.