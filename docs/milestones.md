# Milestone history

CAPRM-Flood was built as a four-milestone capstone. This document records what
each milestone delivered and what it validated, in the order the work happened.
The README describes the finished system; this describes how it got there.

All four milestones are complete. Phase C of Milestone 4 closed the project's
research question; the surrogate result was negative and is reported as such.

---

### Milestone 1 — complete and validated

Milestone 1 established the FEMA point-in-polygon validation foundation:

- deterministic 1,000-property regression fixture;
- Python GeoPandas/Shapely reference computation;
- independent C++ FEMA point-in-polygon implementation;
- canonical FEMA feature identity using `FLD_AR_ID`;
- explicit Python/C++ comparison;
- **1,000 / 1,000 validated property agreement**.

### Milestone 2 — complete and validated

Milestone 2 added nearest-water evidence and countywide scaling:

- deterministic 1K, 10K, 100K, and countywide property workloads;
- USGS hydrography ingestion and caching;
- Python STRtree nearest-water reference implementation;
- independent C++ brute-force nearest-water implementation;
- independent C++ indexed nearest-water implementation;
- deterministic nearest-feature tie resolution;
- strict Python/C++ validation at increasing scales;
- reproducible benchmark harness and summaries;
- integrated FEMA-plus-water property evidence;
- countywide application to **267,362 unique property identifiers**.

The countywide indexed nearest-water implementation reproduced all 267,362 Python results within a maximum absolute distance error of `4.658e-10 m`. In the canonical one-run countywide benchmark, the indexed implementation was `20.39x` faster in reported computation time and `19.83x` faster in total process time than brute force.

### Milestone 3 — complete and frozen

Milestone 3 implemented:

- projected DEM preparation;
- countywide terrain evidence extraction;
- elevation, local mean elevation, relative elevation, and slope features;
- terrain provenance/manifest generation;
- deterministic exposure-index generation at scoring policy `preliminary_exposure_index_v2`;
- index manifest generation;
- measured component influence by exact variance decomposition;
- rank-based sensitivity analysis across 40 weighting scenarios;
- an automated product audit that verifies stored artifacts against their own manifests;
- Milestone 3 result summarization;
- terrain, scoring, sensitivity, and audit tests.

Current countywide terrain results:

```text
properties: 267,362
unique property IDs: 267,362
missing slope values: 0
elevation range: approximately 75.000–296.309 m
```

Frozen preliminary exposure-index results:

```text
properties:                267,362
unique property IDs:       267,362
index minimum:             7.914598933
index maximum:             99.929084911
index mean:                34.63218408001099
index median:              33.7284299935
index standard deviation:  13.063711939924076
weights:                   fema 0.40, water 0.35,
                           terrain_absolute 0.15, terrain_relative 0.10
```

Nominal weight is not influence. Water carries 35 percent of the weight and 65 percent of the variance; FEMA carries 40 percent and 17 percent, because 98.1 percent of properties are tied at the same FEMA component value and constants do not affect ranking.

Measured rank stability:

```text
verdict                      moderately sensitive
minimum Spearman             0.875   (equal weighting)
median Spearman              0.996
minimum top-decile overlap   0.761   (equal weighting)
median top-decile overlap    0.946
```

Thresholds were declared before any result was measured. The verdict hinges on one scenario: every other plausible configuration sits near 0.996, and `equal` alone falls below the stable bar. This is not general instability — the index is stable unless you stop privileging water.

The index is frozen and remains **preliminary**. It is no longer the subject of active work.

### Milestone 4 — current phase, learned indexing of extended spatial objects

Milestone 4 builds a five-rung ladder of nearest-water implementations over the same geometry kernel, the same tie rule, and one validation standard, so that adjacent rungs isolate one variable each.

```text
1. brute force              no index                    Milestone 2
2. Feature BVH              2D,  8,572 features         Milestone 2
3. Segment BVH              2D, ~1.19M entries          B1, B2
4. Hilbert + binary search  1D, ~1.19M entries          B3   control
5. Hilbert + RMI            1D, ~1.19M entries          B4, B5   learned
6. + learned radius         seeds the search disk       B7   stretch
```

The path was forced by the project's own measurement rather than chosen to accommodate machine learning. The Feature BVH examines only 5.498 candidate features per property yet still performs 70,771 segment checks, because it indexes features rather than geometry and the largest water features are near almost everything in the county — the selected features are roughly 104 times larger than the average water feature. Rebuilding at segment granularity is what makes a learned index possible at all, and ~1.19M entries is squarely learned-index scale.

Complete and validated countywide through chunk B6c-2:

- **B1** — segment-granularity BVH with distance-exact splitting. `L = 5,748.2396 m` measured before anything was built on it. 267,362/267,362 field-for-field agreement at `4.658e-10 m`. Phase-2 work fell from 70,771 to 9,716.87 segment checks per property, **7.28x**, at B1's uncapped-equivalent 100 m entry-extent cap. At the 25 m operating point B2 selected, the countywide figure is **9,407.62** checks per property under original-geometry verification and **6,453.70** under split; the B6 tables report both.
- **B2** — entry-extent sweep under both verification strategies, 14/14 points at full agreement. The cap is *not* a performance dial: across a 575-fold range of maximum entry extent, median query time varies under 10 percent. It is chosen for its only downstream consumer, the `L/2` inflation radius. Operating point: 25 m cap.
- **B3** — Hilbert ordering of entry midpoints, exact inflated-disk query by recursive quadrant decomposition, and a binary-search control. Capping at 25 m costs 11.89 percent more entries and returns a **546x** reduction in admitted entries per query.
- **B4** — a two-stage recursive model index after Kraska et al., SIGMOD 2018. 131,072 linear second-stage models, 4,194,400 bytes, with a per-model error bound verified exhaustively over all 1,189,589 keys. The finding is the equi-depth diagnostic: **the router binds, not the leaves.**
- **B5** — inference ported to C++. Output byte-identical to the control on 267,362 properties.
- **B5c** — resolve-descent instrumentation, so the learned rung's cost is counted rather than inferred.

**The measured result is negative, and it is reported because the phase said in advance that it would be.** At the shipped configuration — countywide, seed window W = 64, original-geometry verification — the learned rung produces identical evidence and runs the query 6.48 percent slower:

```text
                              binary        rmi
resolve entries / property   141.1742   352.5154     2.497x
window missed                103,242    123,011      38.62% -> 46.01%
mean d_seed / d_best          1.1717     1.5388
tight entries / property      47.5926    47.5926     identical
```

The model saves about 20 key probes per property and spends about 211 extra point-to-segment distance computations to do it — roughly ten to one in the wrong direction. The mechanism is convexity rather than miss frequency: search cost grows as the square of the seed radius, the miss *rate* moves only 1.19x, and the worst overestimate moves from 32x to 517x the true radius. **The mean prediction error is the wrong summary statistic for a predictor that feeds a radius.**

A second finding is not about the model at all: the exact binary-search control misses its ±64 seed window on 38.62 percent of queries, which makes the window a query-design parameter for both rungs.

**That percentage is conditional, and B6 measured the conditions.** Across nine seed windows the learned-to-control wall-clock ratio moves from 1.11620 at W = 8 to 1.00002 at W = 2048, so the sign of 5 vs 4 is set by the seed window rather than by the model. Under split-geometry verification the same countywide gap reads +12.52 percent — the absolute penalty per property is unchanged and the denominator shrank, so the counted quantity is the invariant and the percentage is the artifact. The durable finding is therefore not “learning did not help” but that the reported benefit of a learned spatial index depends on parameters the literature holds fixed and does not report. See Nucleus 18.26 and 18.27.

Also complete and validated:

- **B6a** — a measurement harness with a repetition and warm-up protocol declared before measuring, blocked and cyclically rotated ordering, session guards, and crash-safe append-and-fsync recording. Two sittings of an identical rung-1 configuration were measured 11.02 percent apart on provably identical work, which is the evidence behind the session guard.
- **B6b** — `SEED_WINDOW` as a compile-time parameter across nine windows, byte-neutral at every one. The first attempt built seven binaries against source that never referenced the macro and the neutrality gate passed on them; the rule extracted is that a neutrality gate requires a positive control (Nucleus 18.25).
- **B6c** — the five-rung ladder at three workloads and a nine-window seed sweep at two workloads. 252 timed runs, exactness closed for all fifteen ladder cells.
- **B6c-2** — the Option A / Option B verification cross-product. Both pre-declared predictions held: 4 vs 3 predicted ~5.5x and measured 5.774x countywide; 5 vs 4 predicted +12.8 percent and measured +12.52.

Remaining: **B6d** — the published tables and the canonical-document pass. No measurement remains.


---

## Milestone 4 Phase C — surrogate feasibility

Phase B asked whether a learned index could beat an exact hierarchy at the
nearest-water query. Phase C asked a different question: whether the pipeline's
output can be predicted from coordinates alone, which would make an approximate
answer available where the exact one is too expensive.

- **C1** — a blocked K-fold partition that does not leak. Block size 10,000 m,
  buffer 2,125 m taken as the lag at which the measured semivariogram reaches
  half its sill, K = 5, five seeds. Both negative controls fail the acceptance
  gate as required, which is what makes a pass meaningful.
- **C2** — a Fourier-feature network trained against that partition. It clears
  the declared nearest-neighbour floor and does not clear a constant predictor:
  blocked RMSE spans [12.299, 16.062] against the constant's [13.391, 15.922].
  The declared floor is itself beaten by a constant, so clearing the floor was
  never evidence of learned spatial structure, and the rung that shows this is
  reported beside it rather than left for a reader to derive.
- **C3** — the prediction registered in C2's own artifact, before C3 ran, was
  that residuals would spike along FEMA zone boundaries. **Refuted.** The class
  effect is confirmed; the spatial claim is not. Boundary proximity does not
  carry the sign the prediction required.
- **C4** — inference cost, batch and thread sweep, with the interval resolution
  rule applied to every comparison and unresolved cells labelled as such; and
  the exact pipeline's own cost, measured against a boundary declared in source
  before any run.

