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
