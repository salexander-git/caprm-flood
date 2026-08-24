# Evidence index

Every number this project publishes, the file that establishes it, and the
field within that file. Nothing here requires running anything.

`outputs/` is otherwise excluded from version control because the per-property
tables are 30–90 MB each. The manifests, summaries, and timing-run tables that
carry the claims are kilobytes and are tracked. What is not tracked is listed at
the end, with the command that regenerates it.

Read a manifest before quoting a number from it. Every one records its own
inputs by SHA-256, so a figure can be traced back to the bytes it came from.

---

## 1. The workload

| Claim | File | Field |
| --- | --- | --- |
| 267,362 properties, all IDs unique | `outputs/validation/property_cache_countywide_manifest.json` | `property_count`, `unique_property_ids` |
| 8,572 water features (5,600 line, 2,972 polygon) | `outputs/validation/water_cpp_input_countywide_manifest.json` | `water_feature_count`, `line_feature_count`, `polygon_feature_count` |
| 1,072,254 vertices → 1,063,159 segments | same | `vertex_count`, `segment_count` |
| 1,189,589 index entries at the 25 m cap | `outputs/validation/water_segment_split_cap_25m_manifest.json` | `split_segment_count` |
| The split is distance-exact | same | `split_rule` |
| Longest original segment: 5,748.2396 m | same | `max_original_segment_length_m` |
| Source datasets and their digests | `outputs/validation/hydrography_cache_manifest.json`, `terrain_raster_prepare_manifest.json` | `*_sha256` |

The 25 m cap adds 126,430 entries to 1,063,159 originals. It is chosen for its
only downstream consumer — the `L/2` inflation radius — not as a performance
dial; `outputs/validation/water_segment_bvh_cap_sweep_summary.json` and
`outputs/validation/segment_bvh_cap_sweep/` hold the sweep that establishes
this across a 575-fold range of cap values.

## 2. Cross-implementation agreement

Five independent C++ implementations reproduce the frozen Python reference on
all ten fields of the nearest-water record, for all 267,362 properties.

| Rung | Summary file |
| --- | --- |
| 1 brute force | `outputs/validation/ladder_summary_brute_force_countywide.json` |
| 2 feature BVH | `outputs/validation/ladder_summary_feature_bvh_countywide.json` |
| 3 segment BVH | `outputs/validation/ladder_summary_segment_bvh_countywide.json` |
| 4 Hilbert + binary search | `outputs/validation/ladder_summary_hilbert_binary_countywide_split_w64.json` |
| 5 Hilbert + RMI | `outputs/validation/ladder_summary_hilbert_rmi_countywide_split_w64.json` |

FEMA point-in-polygon agreement is in
`outputs/validation/fema_pip_countywide_summary.json`.

Maximum absolute distance error, brute force and hierarchical rungs:
`4.657998431412125e-10` m, recorded in
`outputs/validation/property_flood_evidence_countywide_manifest.json` under
`water_validation.maximum_absolute_error_m`, against an applied tolerance of
`1e-6` m.

Coverage is computed over the union of the two property-ID sets rather than an
inner join, so a rung that silently dropped rows fails coverage instead of
scoring perfectly on the rows it kept.

The per-property agreement CSVs are not tracked. See §7.

## 3. Evidence products

Three products, kept separate from scoring:

| Product | Manifest |
| --- | --- |
| FEMA + nearest-water evidence | `outputs/validation/property_flood_evidence_countywide_manifest.json` |
| Terrain evidence | `outputs/validation/property_terrain_evidence_countywide_manifest.json` |
| Preliminary exposure index | `outputs/validation/property_exposure_index_countywide_manifest.json` |

The evidence manifest carries `scoring_included: false`. The boundary between
evidence and scoring is enforced in the artifact, not only in prose.

**The evidence table was produced under `water_validation.algorithm:
feature_bvh`**, recorded in that manifest. The segment BVH is equally exact and
6.90× faster (§4), and is not what produced the shipped evidence. Adopting it
would require regenerating and revalidating every downstream product. That was
not undertaken, and the manifest says which implementation ran.

## 4. Performance

| Claim | File |
| --- | --- |
| Full five-rung ladder, three workloads, two verification modes | `outputs/validation/b6_benchmark_tables.md` |
| Every timed run behind those tables | `outputs/benchmark/water_ladder_runs_*.{csv,jsonl}` |
| Derived comparisons and invariants | `outputs/validation/b6_analysis.json` |
| Nine-window seed sweep with the interval resolution rule applied | `outputs/validation/b6_window_resolution.{csv,json}` |
| Per-property counter tables | `outputs/validation/*_counters.csv` |

Countywide, original-geometry verification, from
`b6_benchmark_tables.md`:

```text
rung 2  feature BVH   235.449 us/property   70,770.60 segment checks
rung 3  segment BVH    34.099 us/property    9,407.62 segment checks
```

A ratio of 6.90×. Absolutes move about 1 percent between invocations while
adjacent ratios agree to 0.116 percentage points, so ratios are quoted within
an invocation and absolutes with their invocation named. The tables carry both.

`brute_force@countywide` carries a 31.71 percent spread at n=3, five times any
other cell. Its figure is an order-of-magnitude statement and rung 1 appears in
no adjacent comparison.

The learned rung's measured cost is in
`outputs/validation/water_hilbert_query_stats_b5c_{binary,rmi}.json`, and its
seed-error distribution in `water_hilbert_seed_error_b5_{binary,rmi}.json`.

## 5. Scoring, sensitivity, and audit

| Claim | File | Field |
| --- | --- | --- |
| Policy `preliminary_exposure_index_v2`; weights 0.40 / 0.35 / 0.15 / 0.10 | `outputs/validation/property_exposure_index_countywide_manifest.json` | `weights`, `schema_version` |
| Water carries 35% of weight and 65.3% of variance; FEMA 40% and 16.8% | same | `summary.component_influence.components.*.variance_share` |
| Verdict `moderately_sensitive` across 40 scenarios | `outputs/validation/scoring_sensitivity_manifest.json` | `stability.verdict` |
| Worst case is `equal` weighting: Spearman 0.875, top-decile overlap 0.761 | same | `stability.worst_spearman_scenario`, `minimum_spearman_with_baseline` |
| Thresholds declared before measurement | same | `stability.thresholds_note` |
| Audit: 49 pass, 1 warn, 0 fail | `outputs/validation/milestone3_audit.json` | `status_counts` |
| The warning: two manifest key conventions coexist | same | `checks[0].detail` |

The variance decomposition is exact — `Cov(w_i C_i, I) / Var(I)`, shares summing
to 1.0 by linearity of covariance, assuming nothing about component
independence. The method string is stored beside the numbers.

Slope is extracted and does not score. `python/caprm/scoring.py:89` records the
omission as deliberate; the four scored components are exactly those in
`DEFAULT_WEIGHTS` at `scoring.py:30`.

## 6. Surrogate (Phase C)

| Claim | File | Field |
| --- | --- | --- |
| Partition: blocked K-fold, b = 10,000 m, w = 2,125 m, K = 5, 5 seeds | `outputs/validation/c1_kfold_manifest.json` | — |
| Buffer width derived from measured spatial correlation | `outputs/validation/spatial_correlation_v2.json` | — |
| Surrogate not separable from a constant predictor | `outputs/validation/c2_surrogate_manifest.json` | `comparison_to_floor.constant_baseline.surrogate_beats_constant_as_a_range` = `false` |
| Blocked RMSE [12.299, 16.062] vs constant [13.391, 15.922] | same | `summary.blocked_kfold`, `summary_constant_baseline.blocked_kfold` |
| The declared floor is itself beaten by a constant | same | `comparison_to_floor.constant_baseline.why_this_rung_exists` |
| Registered prediction refuted | `outputs/validation/c3_error_analysis.json` | `results.blocked_kfold.verdict.verdict` = `"REFUTED"` |
| …mechanism confirmed, spatial claim not | same | `verdict.mechanism_confirmed`, `verdict.spatial_prediction_confirmed` |
| Inference cost and thread/batch sweep | `docs/c4_inference_tables.md`, `outputs/validation/c4_inference_benchmark_threads{1,8}.json` | — |
| Pipeline-cost timing boundary, declared before any run | `outputs/validation/c4_pipeline_boundary.json` | `timing_boundary` |

The prediction in `c2_surrogate_manifest.json` under
`declared_prediction_for_c3` was written before C3 ran and is stored in the C2
artifact, so the order is verifiable rather than asserted.

## 7. What is not tracked, and how to regenerate it

| Not tracked | Size | Regenerate with |
| --- | --- | --- |
| Per-property agreement CSVs (`*_agreement*.csv`, countywide) | 30–90 MB each | `python/scripts/compare_python_cpp_water.py`, `compare_python_cpp_fema.py` |
| Evidence, terrain, and index tables (`outputs/{evidence,index}/`) | ~100 MB | `python/scripts/build_property_evidence.py`, `build_terrain_evidence.py`, `build_exposure_index.py` |
| Python and C++ per-property outputs (`outputs/{baseline,cpp}/`, countywide) | ~250 MB | `python/scripts/run_fema_baseline.py`, `run_water_baseline.py`, then the C++ binaries |
| Projected C++ input tables (`outputs/cpp_input/`) | ~75 MB | `python/scripts/export_cpp_inputs.py`, `export_water_cpp_inputs.py` |
| `diag_seed_error_w2048.csv` | 46 MB | `benchmark_water_ladder.py --seed-error-stats` |
| Source rasters and parcels (`data/raw/`, `data/processed/`) | ~200 MB | See `docs/data_sources.md` |

Every manifest listed above records the SHA-256 of the file it describes, so a
regenerated table can be checked against the run that produced the published
numbers rather than merely resembling it.

`models/water_hilbert_rmi.bin` (4,194,400 bytes) *is* tracked, deliberately:
the C++ query path loads the model at run time, so the repository would not
build a working rung 5 without it.
