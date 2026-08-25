# PHASE B benchmark results

Generated 2026-07-30T13:51:24.309216+00:00 by `python/scripts/analyze_b6_results.py` from the artifacts listed in `outputs/validation/b6_analysis.json`. Do not hand-edit.


## Three adjacent comparisons, per workload and per verification mode

Never 5 v 3: that confounds the dimensionality reduction with the learning. Rung 1 is in no adjacent comparison; it carries a 31.71 percent spread at n=3 and is listed separately below as context.

Segment-check counts are comparable WITHIN a verification mode and not across modes (Nucleus, B2), so the count column is never used to infer the clock column. **Option A dilutes 4 v 3**: rungs 3 and 4 share the verification term, so the Option A ratio divides two numbers that mostly consist of the same work. Option B is the correct column for it (Nucleus 18.27).

| workload | mode | comparison | meaning | wall clock | us/property | segment checks | n | resolvable |
|---|---|---|---|---:|---:|---:|---|---|
| 10000 | original | 3 v 2 | granularity: feature -> segment | 15.690x faster | 108.645 | 26.795x fewer | 7/7 | yes |
| 10000 | original (diluted) | 4 v 3 | dimensionality: 2D -> 1D | 4.735x slower | 27.626 | 1.171x more | 7/7 | yes |
| 10000 | original | 5 v 4 | machine learning: search -> model | 1.143x slower | 5.006 | 1.000x fewer | 7/7 | yes |
| 10000 | original | 3 v 2 | granularity: feature -> segment | 15.314x faster | 108.464 | 26.795x fewer | 7/7 | yes |
| 10000 | original (diluted) | 4 v 3 | dimensionality: 2D -> 1D | 4.767x slower | 28.540 | 1.171x more | 7/7 | yes |
| 10000 | original | 5 v 4 | machine learning: search -> model | 1.164x slower | 5.939 | 1.000x fewer | 7/7 | yes |
| 10000 | split | 3 v 2 | granularity: feature -> segment | 31.402x faster | 112.346 | 40.123x fewer | 7/7 | yes |
| 10000 | split | 4 v 3 | dimensionality: 2D -> 1D | 8.488x slower | 27.670 | 1.178x more | 7/7 | yes |
| 10000 | split | 5 v 4 | machine learning: search -> model | 1.179x slower | 5.626 | 1.000x fewer | 7/7 | yes |
| 100000 | original | 3 v 2 | granularity: feature -> segment | 14.928x faster | 350.370 | 16.900x fewer | 7/7 | yes |
| 100000 | original (diluted) | 4 v 3 | dimensionality: 2D -> 1D | 2.138x slower | 28.618 | 1.203x more | 7/7 | yes |
| 100000 | original | 5 v 4 | machine learning: search -> model | 1.098x slower | 5.271 | 1.000x fewer | 7/7 | **NOT RESOLVED** |
| 100000 | original | 3 v 2 | granularity: feature -> segment | 13.901x faster | 348.511 | 16.900x fewer | 7/7 | yes |
| 100000 | original (diluted) | 4 v 3 | dimensionality: 2D -> 1D | 2.248x slower | 33.716 | 1.203x more | 7/7 | yes |
| 100000 | original | 5 v 4 | machine learning: search -> model | 1.059x slower | 3.590 | 1.000x fewer | 7/7 | **NOT RESOLVED** |
| 100000 | split | 3 v 2 | granularity: feature -> segment | 67.121x faster | 369.931 | 24.180x fewer | 7/7 | yes |
| 100000 | split | 4 v 3 | dimensionality: 2D -> 1D | 5.747x slower | 26.556 | 1.195x more | 7/7 | yes |
| 100000 | split | 5 v 4 | machine learning: search -> model | 1.192x slower | 6.188 | 1.000x fewer | 7/7 | yes |
| countywide | original | 3 v 2 | granularity: feature -> segment | 6.540x faster | 199.445 | 7.523x fewer | 7/7 | yes |
| countywide | original (diluted) | 4 v 3 | dimensionality: 2D -> 1D | 1.954x slower | 34.357 | 1.172x more | 7/7 | yes |
| countywide | original | 5 v 4 | machine learning: search -> model | 1.072x slower | 5.076 | 1.000x fewer | 7/7 | yes |
| countywide | original | 3 v 2 | granularity: feature -> segment | 6.905x faster | 201.350 | 7.523x fewer | 7/7 | yes |
| countywide | original (diluted) | 4 v 3 | dimensionality: 2D -> 1D | 1.947x slower | 32.291 | 1.172x more | 7/7 | yes |
| countywide | original | 5 v 4 | machine learning: search -> model | 1.065x slower | 4.302 | 1.000x fewer | 7/7 | yes |
| countywide | original | 3 v 2 | granularity: feature -> segment | 6.220x faster | 197.592 | 7.523x fewer | 7/7 | yes |
| countywide | original (diluted) | 4 v 3 | dimensionality: 2D -> 1D | 1.959x slower | 36.301 | 1.172x more | 7/7 | yes |
| countywide | original | 5 v 4 | machine learning: search -> model | 1.057x slower | 4.243 | 1.000x fewer | 7/7 | yes |
| countywide | split | 3 v 2 | granularity: feature -> segment | 38.301x faster | 229.301 | 10.966x fewer | 7/7 | yes |
| countywide | split | 4 v 3 | dimensionality: 2D -> 1D | 5.774x slower | 29.346 | 1.180x more | 7/7 | yes |
| countywide | split | 5 v 4 | machine learning: search -> model | 1.125x slower | 4.442 | 1.000x fewer | 7/7 | yes |
| countywide | split | 3 v 2 | granularity: feature -> segment | 36.562x faster | 229.009 | 10.966x fewer | 7/7 | yes |
| countywide | split | 4 v 3 | dimensionality: 2D -> 1D | 5.723x slower | 30.417 | 1.180x more | 7/7 | yes |
| countywide | split | 5 v 4 | machine learning: search -> model | 1.122x slower | 4.482 | 1.000x fewer | 7/7 | yes |

### Context, not an adjacent comparison

| workload | mode | comparison | wall clock | segment checks | n | resolvable |
|---|---|---|---:|---:|---|---|
| 10000 | original | 2 v 1 | 33.578x faster | 31.259x fewer | 3/7 | yes |
| 10000 | original | 2 v 1 | 33.578x faster | 31.259x fewer | 3/7 | yes |
| 10000 | split | 2 v 1 | 33.578x faster | 31.259x fewer | 3/7 | yes |
| 100000 | original | 2 v 1 | 11.301x faster | 9.392x fewer | 3/7 | yes |
| 100000 | original | 2 v 1 | 11.301x faster | 9.392x fewer | 3/7 | yes |
| 100000 | split | 2 v 1 | 11.301x faster | 9.392x fewer | 3/7 | yes |
| countywide | original | 2 v 1 | 16.963x faster | 15.023x fewer | 3/7 | yes |
| countywide | original | 2 v 1 | 16.963x faster | 15.023x fewer | 3/7 | yes |
| countywide | original | 2 v 1 | 16.963x faster | 15.023x fewer | 3/7 | yes |
| countywide | split | 2 v 1 | 16.963x faster | 15.023x fewer | 3/7 | yes |
| countywide | split | 2 v 1 | 16.963x faster | 15.023x fewer | 3/7 | yes |

## Search and verification, as separate columns

Per-check cost is calibrated from rung 3 only, assuming its search is 0.6 percent of its query time. B1 counted ~35 box and node operations per property against 9,407.62 segment checks (~0.4 percent); B6c-2 reached ~0.6 percent independently. The larger figure is used so the verification term is not overstated.

- 10000 `original`: **5.7918 ns/check** from `segment_bvh@10000`
- 10000 `original`: **5.9340 ns/check** from `segment_bvh@10000`
- 10000 `split`: **4.3332 ns/check** from `segment_bvh@10000@split`, ratio 1.3694x
- 100000 `original`: **3.7333 ns/check** from `segment_bvh@100000`
- 100000 `original`: **4.0092 ns/check** from `segment_bvh@100000`
- 100000 `split`: **1.1880 ns/check** from `segment_bvh@100000@split`, ratio 3.3749x
- countywide `original`: **3.8041 ns/check** from `segment_bvh@countywide`
- countywide `split`: **0.9468 ns/check** from `segment_bvh@countywide@split`, ratio 4.0179x
- countywide `original`: **3.6029 ns/check** from `segment_bvh@countywide`
- countywide `original`: **3.9998 ns/check** from `segment_bvh@countywide`
- countywide `split`: **0.9918 ns/check** from `segment_bvh@countywide@split`, ratio 4.0328x

| cell | mode | total us/p | search us/p | verification us/p | search share | physical |
|---|---|---:|---:|---:|---:|---|
| segment_bvh@10000 | original | 7.396 | 0.044 | 7.352 | 0.60% | yes |
| hilbert_binary@10000@w64 | original | 35.022 | 26.414 | 8.607 | 75.42% | yes |
| hilbert_rmi@10000@w64 | original | 40.027 | 31.420 | 8.607 | 78.50% | yes |
| segment_bvh@10000 | original | 7.577 | 0.045 | 7.532 | 0.60% | yes |
| hilbert_binary@10000@w64 | original | 36.118 | 27.299 | 8.819 | 75.58% | yes |
| hilbert_rmi@10000@w64 | original | 42.057 | 33.238 | 8.819 | 79.03% | yes |
| segment_bvh@10000@split | split | 3.695 | 0.022 | 3.673 | 0.60% | yes |
| hilbert_binary@10000@split@w64 | split | 31.366 | 27.038 | 4.328 | 86.20% | yes |
| hilbert_rmi@10000@split@w64 | split | 36.992 | 32.664 | 4.328 | 88.30% | yes |
| segment_bvh@100000 | original | 25.156 | 0.151 | 25.005 | 0.60% | yes |
| hilbert_binary@100000@w64 | original | 53.774 | 23.698 | 30.076 | 44.07% | yes |
| hilbert_rmi@100000@w64 | original | 59.045 | 28.970 | 30.076 | 49.06% | yes |
| segment_bvh@100000 | original | 27.015 | 0.162 | 26.853 | 0.60% | yes |
| hilbert_binary@100000@w64 | original | 60.731 | 28.433 | 32.298 | 46.82% | yes |
| hilbert_rmi@100000@w64 | original | 64.321 | 32.023 | 32.298 | 49.79% | yes |
| segment_bvh@100000@split | split | 5.595 | 0.034 | 5.561 | 0.60% | yes |
| hilbert_binary@100000@split@w64 | split | 32.150 | 25.506 | 6.645 | 79.33% | yes |
| hilbert_rmi@100000@split@w64 | split | 38.338 | 31.693 | 6.645 | 82.67% | yes |
| segment_bvh@countywide | original | 36.004 | 0.216 | 35.788 | 0.60% | yes |
| hilbert_binary@countywide@w64 | original | 70.361 | 28.433 | 41.929 | 40.41% | yes |
| hilbert_rmi@countywide@w64 | original | 75.437 | 33.509 | 41.929 | 44.42% | yes |
| segment_bvh@countywide@split | split | 6.147 | 0.037 | 6.110 | 0.60% | yes |
| hilbert_binary@countywide@split@w64 | split | 35.493 | 28.282 | 7.211 | 79.68% | yes |
| hilbert_rmi@countywide@split@w64 | split | 39.935 | 32.724 | 7.211 | 81.94% | yes |
| segment_bvh@countywide | original | 34.099 | 0.205 | 33.894 | 0.60% | yes |
| hilbert_binary@countywide@w64 | original | 66.389 | 26.679 | 39.710 | 40.19% | yes |
| hilbert_rmi@countywide@w64 | original | 70.692 | 30.982 | 39.710 | 43.83% | yes |
| segment_bvh@countywide | original | 37.856 | 0.227 | 37.629 | 0.60% | yes |
| hilbert_binary@countywide@w64 | original | 74.157 | 30.072 | 44.086 | 40.55% | yes |
| hilbert_rmi@countywide@w64 | original | 78.401 | 34.315 | 44.086 | 43.77% | yes |
| segment_bvh@countywide@split | split | 6.440 | 0.039 | 6.401 | 0.60% | yes |
| hilbert_binary@countywide@split@w64 | split | 36.857 | 29.302 | 7.554 | 79.50% | yes |
| hilbert_rmi@countywide@split@w64 | split | 41.338 | 33.784 | 7.554 | 81.73% | yes |

Out-of-sample check. Rungs 4 and 5 never entered the calibration, and search cost must be mode-invariant because the traversal does not know which geometry the kernel will rescan:

- 10000 hilbert_binary: modes disagree by **0.958 percent**
- 10000 hilbert_rmi: modes disagree by **1.727 percent**
- 100000 hilbert_binary: modes disagree by **10.296 percent**
- 100000 hilbert_rmi: modes disagree by **1.030 percent**
- countywide hilbert_binary: modes disagree by **0.531 percent**
- countywide hilbert_rmi: modes disagree by **2.343 percent**
- countywide hilbert_binary: modes disagree by **2.559 percent**
- countywide hilbert_rmi: modes disagree by **1.548 percent**

Recorded failure. Solving for both per-check costs with no assumed search fraction is exactly determined at two rungs times two modes, and it is unusable: the two check-count ratios are 1.4974 and 1.4879, so the system is nearly singular and it implies a rung-3 search cost of **31.503 us/property**. This is why the calibration is anchored instead.

Recorded failure. Solving for both per-check costs with no assumed search fraction is exactly determined at two rungs times two modes, and it is unusable: the two check-count ratios are 1.4308 and 1.4403, so the system is nearly singular and it implies a rung-3 search cost of **-348.866 us/property**. This is why the calibration is anchored instead.

Recorded failure. Solving for both per-check costs with no assumed search fraction is exactly determined at two rungs times two modes, and it is unusable: the two check-count ratios are 1.4577 and 1.4471, so the system is nearly singular and it implies a rung-3 search cost of **-6.816 us/property**. This is why the calibration is anchored instead.

Recorded failure. Solving for both per-check costs with no assumed search fraction is exactly determined at two rungs times two modes, and it is unusable: the two check-count ratios are 1.4577 and 1.4471, so the system is nearly singular and it implies a rung-3 search cost of **63.890 us/property**. This is why the calibration is anchored instead.

## Cost model: counted entries predict wall clock

Constant: **20.4 ns per resolve-descent entry**, measured independently. Current Status B5c: marginal cost of one resolve-descent entry, measured in isolation before any B6 timing existed.

The population is part of the number. A slope over the window sweep and a slope over the sweep plus other workloads are different quantities:

- `all_points` (n=29): **20.50 ns/entry** -- every matched binary/RMI pair present, mixing the window sweep with single-window workloads
- `window_sweep_only` (n=18): **21.10 ns/entry** -- only workloads measured at more than one seed window, which is the population Current Status B6c reports
- `resolvable_only` (n=15): **21.34 ns/entry** -- points whose gap exceeds both cells' full range. Reported for completeness; at small counts this is not a fit and must not be quoted as one

| workload | W | delta entries | predicted us | measured us | m/p | resolvable |
|---|---:|---:|---:|---:|---:|---|
| 10000 | 64 | 272.675 | 5.563 | 5.006 | 0.900 | yes |
| 10000 | 64 | 272.675 | 5.563 | 5.939 | 1.068 | yes |
| 10000 | 64 | 272.675 | 5.563 | 5.626 | 1.011 | yes |
| 100000 | 64 | 279.542 | 5.703 | 5.271 | 0.924 | NO |
| 100000 | 64 | 279.542 | 5.703 | 3.590 | 0.630 | NO |
| 100000 | 64 | 279.542 | 5.703 | 6.188 | 1.085 | yes |
| countywide | 8 | 355.071 | 7.243 | 7.879 | 1.088 | yes |
| countywide | 16 | 319.139 | 6.510 | 6.871 | 1.055 | NO |
| countywide | 32 | 271.394 | 5.536 | 5.658 | 1.022 | NO |
| countywide | 64 | 211.341 | 4.311 | 5.076 | 1.177 | yes |
| countywide | 64 | 211.341 | 4.311 | 4.302 | 0.998 | yes |
| countywide | 64 | 211.341 | 4.311 | 4.243 | 0.984 | yes |
| countywide | 64 | 211.341 | 4.311 | 4.269 | 0.990 | NO |
| countywide | 128 | 152.359 | 3.108 | 2.795 | 0.899 | NO |
| countywide | 256 | 97.939 | 1.998 | 1.649 | 0.825 | NO |
| countywide | 512 | 62.153 | 1.268 | 0.829 | 0.654 | NO |
| countywide | 1024 | 31.224 | 0.637 | 0.227 | 0.356 | NO |
| countywide | 2048 | 16.725 | 0.341 | 0.001 | 0.004 | NO |
| countywide | 8 | 355.071 | 7.243 | 7.981 | 1.102 | yes |
| countywide | 16 | 319.139 | 6.510 | 6.975 | 1.071 | yes |
| countywide | 32 | 271.394 | 5.536 | 5.268 | 0.951 | yes |
| countywide | 64 | 211.341 | 4.311 | 4.442 | 1.030 | yes |
| countywide | 64 | 211.341 | 4.311 | 4.482 | 1.040 | yes |
| countywide | 64 | 211.341 | 4.311 | 4.776 | 1.108 | yes |
| countywide | 128 | 152.359 | 3.108 | 2.986 | 0.961 | yes |
| countywide | 256 | 97.939 | 1.998 | 1.620 | 0.811 | NO |
| countywide | 512 | 62.153 | 1.268 | 0.538 | 0.425 | NO |
| countywide | 1024 | 31.224 | 0.637 | -0.194 | -0.304 | NO |
| countywide | 2048 | 16.725 | 0.341 | -0.061 | -0.178 | NO |

## Query-count curve

Varies QUERY COUNT at a fixed 1,189,589-entry index. NOT the index-size axis the learned-index literature argues over.

| rung | workload | us/property | checks/property | candidates | checks per candidate |
|---|---|---:|---:|---:|---:|
| brute_force | 10000 | 3896.457 | 1063159.00 | -- | -- |
| brute_force | 100000 | 4243.636 | 1063159.00 | -- | -- |
| brute_force | countywide | 3993.925 | 1063159.00 | -- | -- |
| feature_bvh | 10000 | 116.041 | 34011.21 | 7.815 | 4,352 |
| feature_bvh | 100000 | 375.526 | 113194.87 | 6.514 | 17,377 |
| feature_bvh | countywide | 235.449 | 70770.60 | 5.498 | 12,873 |
| segment_bvh | 10000 | 7.396 | 1269.29 | 1.403 | 905 |
| segment_bvh | 10000 | 7.577 | 1269.29 | 1.403 | 905 |
| segment_bvh | 10000 | 3.695 | 847.68 | 1.403 | 604 |
| segment_bvh | 100000 | 25.156 | 6697.86 | 1.446 | 4,630 |
| segment_bvh | 100000 | 27.015 | 6697.86 | 1.446 | 4,630 |
| segment_bvh | 100000 | 5.595 | 4681.29 | 1.446 | 3,236 |
| segment_bvh | countywide | 34.099 | 9407.62 | 1.466 | 6,416 |
| segment_bvh | countywide | 36.004 | 9407.62 | 1.466 | 6,416 |
| segment_bvh | countywide | 6.147 | 6453.70 | 1.466 | 4,402 |
| segment_bvh | countywide | 37.856 | 9407.62 | 1.466 | 6,416 |
| segment_bvh | countywide | 6.440 | 6453.70 | 1.466 | 4,402 |
| hilbert_binary | 10000 | 35.022 | 1486.11 | -- | -- |
| hilbert_binary | 10000 | 36.118 | 1486.11 | -- | -- |
| hilbert_binary | 10000 | 31.366 | 998.78 | -- | -- |
| hilbert_binary | 100000 | 53.774 | 8056.00 | -- | -- |
| hilbert_binary | 100000 | 60.731 | 8056.00 | -- | -- |
| hilbert_binary | 100000 | 32.150 | 5593.32 | -- | -- |
| hilbert_binary | countywide | 66.389 | 11021.83 | -- | -- |
| hilbert_binary | countywide | 70.361 | 11021.83 | -- | -- |
| hilbert_binary | countywide | 35.493 | 7616.52 | -- | -- |
| hilbert_binary | countywide | 74.157 | 11021.83 | -- | -- |
| hilbert_binary | countywide | 36.857 | 7616.52 | -- | -- |
| hilbert_rmi | 10000 | 40.027 | 1486.11 | -- | -- |
| hilbert_rmi | 10000 | 42.057 | 1486.11 | -- | -- |
| hilbert_rmi | 10000 | 36.992 | 998.78 | -- | -- |
| hilbert_rmi | 100000 | 59.045 | 8056.00 | -- | -- |
| hilbert_rmi | 100000 | 64.321 | 8056.00 | -- | -- |
| hilbert_rmi | 100000 | 38.338 | 5593.32 | -- | -- |
| hilbert_rmi | countywide | 70.692 | 11021.83 | -- | -- |
| hilbert_rmi | countywide | 75.437 | 11021.83 | -- | -- |
| hilbert_rmi | countywide | 39.935 | 7616.52 | -- | -- |
| hilbert_rmi | countywide | 78.401 | 11021.83 | -- | -- |
| hilbert_rmi | countywide | 41.338 | 7616.52 | -- | -- |

## Seed-window curve

| workload | W | binary s | rmi s | rmi/binary | binary missed | rmi missed | exchange rate | uncounted 2W |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| countywide | 8 | 18.1273 | 20.2337 | 1.11620 | 0.6988 | 0.7915 | 17.55:1 | 16 |
| countywide | 16 | 18.0951 | 19.9322 | 1.10153 | 0.6076 | 0.6896 | 15.77:1 | 32 |
| countywide | 32 | 18.0237 | 19.5364 | 1.08393 | 0.4993 | 0.5767 | 13.41:1 | 64 |
| countywide | 64 | 17.9349 | 19.0764 | 1.06365 | 0.3862 | 0.4601 | 10.44:1 | 128 |
| countywide | 128 | 17.9517 | 18.6991 | 1.04163 | 0.2851 | 0.3419 | 7.53:1 | 256 |
| countywide | 256 | 17.9756 | 18.4165 | 1.02453 | 0.2314 | 0.2632 | 4.84:1 | 512 |
| countywide | 512 | 18.3422 | 18.5639 | 1.01209 | 0.1713 | 0.1860 | 3.07:1 | 1024 |
| countywide | 1024 | 19.1631 | 19.2238 | 1.00317 | 0.1427 | 0.1485 | 1.54:1 | 2048 |
| countywide | 2048 | 20.8680 | 20.8683 | 1.00002 | 0.1184 | 0.1216 | 0.83:1 | 4096 |
| 10000 | 64 | 0.3502 | 0.4003 | 1.14293 | 0.4997 | 0.5918 | 13.48:1 | 128 |
| 100000 | 64 | 5.3774 | 5.9045 | 1.09803 | 0.3506 | 0.4358 | 13.83:1 | 128 |
| countywide | 64 | 17.7500 | 18.9003 | 1.06480 | 0.3862 | 0.4601 | 10.44:1 | 128 |
| countywide | 8 | 9.9705 | 12.1044 | 1.21402 | 0.6988 | 0.7915 | 17.55:1 | 16 |
| countywide | 16 | 9.7669 | 11.6318 | 1.19093 | 0.6076 | 0.6896 | 15.77:1 | 32 |
| countywide | 32 | 9.9326 | 11.3410 | 1.14180 | 0.4993 | 0.5767 | 13.41:1 | 64 |
| countywide | 64 | 9.7276 | 11.0044 | 1.13125 | 0.3862 | 0.4601 | 10.44:1 | 128 |
| countywide | 128 | 9.6819 | 10.4803 | 1.08246 | 0.2851 | 0.3419 | 7.53:1 | 256 |
| countywide | 256 | 9.8204 | 10.2534 | 1.04409 | 0.2314 | 0.2632 | 4.84:1 | 512 |
| countywide | 512 | 10.1172 | 10.2612 | 1.01423 | 0.1713 | 0.1860 | 3.07:1 | 1024 |
| countywide | 1024 | 11.0801 | 11.0283 | 0.99533 | 0.1427 | 0.1485 | 1.54:1 | 2048 |
| countywide | 2048 | 12.9506 | 12.9344 | 0.99875 | 0.1184 | 0.1216 | 0.83:1 | 4096 |
| 10000 | 64 | 0.3612 | 0.4206 | 1.16443 | 0.4997 | 0.5918 | 13.48:1 | 128 |
| 10000 | 64 | 0.3137 | 0.3699 | 1.17938 | 0.4997 | 0.5918 | 13.48:1 | 128 |
| 100000 | 64 | 6.0731 | 6.4321 | 1.05911 | 0.3506 | 0.4358 | 13.83:1 | 128 |
| 100000 | 64 | 3.2150 | 3.8338 | 1.19246 | 0.3506 | 0.4358 | 13.83:1 | 128 |
| countywide | 64 | 19.8269 | 20.9614 | 1.05722 | 0.3862 | 0.4601 | 10.44:1 | 128 |
| countywide | 64 | 9.8541 | 11.0523 | 1.12160 | 0.3862 | 0.4601 | 10.44:1 | 128 |

## Inflation, as a first-class axis

Ordering extended objects by a representative point requires searching `disk(r + L/2)` to stay exact. That inflation is the price of treating extended objects as points and is the reason the learned-index literature has stayed on point data.

The capped inflation and the phase-2 check count move in OPPOSITE directions across workloads, so no inflation figure is meaningful without its workload. The `2W` seed-window scan appears in NO emitted counter and is reported beside the counted work, never summed with it.

| cell | mode | W | entries in range | midpoints admitted | inflation | phase-2 checks | admitted/checks | uncounted 2W | 2W/counted |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hilbert_binary@10000@w64 | original | 64 | 1.6906 | 11.7066 | 6.9245x | 1,486.11 | 7.88e-03 | 128 | 1.1322 |
| hilbert_binary@10000@w64 | original | 64 | 1.6906 | 11.7066 | 6.9245x | 1,486.11 | 7.88e-03 | 128 | 1.1322 |
| hilbert_rmi@10000@w64 | original | 64 | 1.6906 | 11.7066 | 6.9245x | 1,486.11 | 7.88e-03 | 128 | 0.3318 |
| hilbert_rmi@10000@w64 | original | 64 | 1.6906 | 11.7066 | 6.9245x | 1,486.11 | 7.88e-03 | 128 | 0.3318 |
| hilbert_binary@10000@split@w64 | split | 64 | 1.6906 | 11.7066 | 6.9245x | 998.78 | 1.17e-02 | 128 | 1.1322 |
| hilbert_rmi@10000@split@w64 | split | 64 | 1.6906 | 11.7066 | 6.9245x | 998.78 | 1.17e-02 | 128 | 0.3318 |
| hilbert_binary@100000@w64 | original | 64 | 1.5887 | 9.5768 | 6.0282x | 8,056.00 | 1.19e-03 | 128 | 1.5507 |
| hilbert_binary@100000@w64 | original | 64 | 1.5887 | 9.5768 | 6.0282x | 8,056.00 | 1.19e-03 | 128 | 1.5507 |
| hilbert_rmi@100000@w64 | original | 64 | 1.5887 | 9.5768 | 6.0282x | 8,056.00 | 1.19e-03 | 128 | 0.3535 |
| hilbert_rmi@100000@w64 | original | 64 | 1.5887 | 9.5768 | 6.0282x | 8,056.00 | 1.19e-03 | 128 | 0.3535 |
| hilbert_binary@100000@split@w64 | split | 64 | 1.5887 | 9.5768 | 6.0282x | 5,593.32 | 1.71e-03 | 128 | 1.5507 |
| hilbert_rmi@100000@split@w64 | split | 64 | 1.5887 | 9.5768 | 6.0282x | 5,593.32 | 1.71e-03 | 128 | 0.3535 |
| hilbert_binary@countywide@w64 | original | 64 | 1.6067 | 10.2783 | 6.3972x | 11,021.83 | 9.33e-04 | 128 | 0.9067 |
| hilbert_binary@countywide@w64 | original | 64 | 1.6067 | 10.2783 | 6.3972x | 11,021.83 | 9.33e-04 | 128 | 0.9067 |
| hilbert_binary@countywide@w64 | original | 64 | 1.6067 | 10.2783 | 6.3972x | 11,021.83 | 9.33e-04 | 128 | 0.9067 |
| hilbert_rmi@countywide@w64 | original | 64 | 1.6067 | 10.2783 | 6.3972x | 11,021.83 | 9.33e-04 | 128 | 0.3631 |
| hilbert_rmi@countywide@w64 | original | 64 | 1.6067 | 10.2783 | 6.3972x | 11,021.83 | 9.33e-04 | 128 | 0.3631 |
| hilbert_rmi@countywide@w64 | original | 64 | 1.6067 | 10.2783 | 6.3972x | 11,021.83 | 9.33e-04 | 128 | 0.3631 |
| hilbert_binary@countywide@split@w64 | split | 64 | 1.6067 | 10.2783 | 6.3972x | 7,616.52 | 1.35e-03 | 128 | 0.9067 |
| hilbert_binary@countywide@split@w64 | split | 64 | 1.6067 | 10.2783 | 6.3972x | 7,616.52 | 1.35e-03 | 128 | 0.9067 |
| hilbert_rmi@countywide@split@w64 | split | 64 | 1.6067 | 10.2783 | 6.3972x | 7,616.52 | 1.35e-03 | 128 | 0.3631 |
| hilbert_rmi@countywide@split@w64 | split | 64 | 1.6067 | 10.2783 | 6.3972x | 7,616.52 | 1.35e-03 | 128 | 0.3631 |

Uncapped, one Lake Ontario boundary chord of 5,748.2396 m would set `L` for the entire index. Capping is what makes the inflation a modest constant rather than a barrier.

### The two access patterns

**EXPLORATORY, not a validated prediction.** An uncounted window-scan entry and a counted resolve-descent entry are not the same unit of cost, which is why the two are never summed. The intercept is free and absorbs verification.

| workload | mode | invocation | n | W | window-scan ns | resolve ns | premium | R^2 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| countywide | original | sweep_runs | 18 | 9 | 3.0574 | 22.4496 | 7.343x | 0.98986 |
| countywide | split | sweep_split_runs | 18 | 9 | 3.3142 | 23.0054 | 6.941x | 0.98254 |

## Memory

Three instruments, and they disagree in direction. None may be quoted alone (Nucleus 18.24).

| cell | invocation | structure bytes | peak RSS | peak commit | RSS above rung 1 | commit above rung 1 |
|---|---|---:|---:|---:|---:|---:|
| brute_force@10000 | ladder_runs | -- | 33,906,688 | 34,160,640 | -- | -- |
| feature_bvh@10000 | ladder_runs | -- | 33,931,264 | 35,115,008 | 24,576 | 954,368 |
| hilbert_binary@10000@split@w64 | mode_grid_runs | 9,516,712 | 200,073,216 | 237,264,896 | 166,166,528 | 203,104,256 |
| hilbert_binary@10000@w64 | ladder_runs | 9,516,712 | 200,069,120 | 237,236,224 | 166,162,432 | 203,075,584 |
| hilbert_binary@10000@w64 | mode_grid_runs | 9,516,712 | 199,917,568 | 237,207,552 | 166,010,880 | 203,046,912 |
| hilbert_rmi@10000@split@w64 | mode_grid_runs | 13,711,112 | 200,056,832 | 237,264,896 | 166,150,144 | 203,104,256 |
| hilbert_rmi@10000@w64 | ladder_runs | 13,711,112 | 200,126,464 | 237,268,992 | 166,219,776 | 203,108,352 |
| hilbert_rmi@10000@w64 | mode_grid_runs | 13,711,112 | 200,077,312 | 237,236,224 | 166,170,624 | 203,075,584 |
| segment_bvh@10000 | ladder_runs | 119,768,836 | 153,661,440 | 294,473,728 | 119,754,752 | 260,313,088 |
| segment_bvh@10000 | mode_grid_runs | 119,768,836 | 153,620,480 | 294,522,880 | 119,713,792 | 260,362,240 |
| segment_bvh@10000@split | mode_grid_runs | 119,768,836 | 153,559,040 | 294,469,632 | 119,652,352 | 260,308,992 |
| brute_force@100000 | ladder_runs | -- | 45,051,904 | 47,050,752 | -- | -- |
| feature_bvh@100000 | ladder_runs | -- | 44,982,272 | 47,972,352 | -69,632 | 921,600 |
| hilbert_binary@100000@split@w64 | mode_grid_runs | 9,516,712 | 211,206,144 | 250,306,560 | 166,154,240 | 203,255,808 |
| hilbert_binary@100000@w64 | ladder_runs | 9,516,712 | 211,169,280 | 250,138,624 | 166,117,376 | 203,087,872 |
| hilbert_binary@100000@w64 | mode_grid_runs | 9,516,712 | 211,214,336 | 250,306,560 | 166,162,432 | 203,255,808 |
| hilbert_rmi@100000@split@w64 | mode_grid_runs | 13,711,112 | 211,275,776 | 250,302,464 | 166,223,872 | 203,251,712 |
| hilbert_rmi@100000@w64 | ladder_runs | 13,711,112 | 211,210,240 | 250,114,048 | 166,158,336 | 203,063,296 |
| hilbert_rmi@100000@w64 | mode_grid_runs | 13,711,112 | 211,054,592 | 250,068,992 | 166,002,688 | 203,018,240 |
| segment_bvh@100000 | ladder_runs | 119,768,836 | 164,786,176 | 307,408,896 | 119,734,272 | 260,358,144 |
| segment_bvh@100000 | mode_grid_runs | 119,768,836 | 164,671,488 | 307,400,704 | 119,619,584 | 260,349,952 |
| segment_bvh@100000@split | mode_grid_runs | 119,768,836 | 164,679,680 | 307,400,704 | 119,627,776 | 260,349,952 |
| brute_force@countywide | ladder_runs | -- | 72,503,296 | 85,061,632 | -- | -- |
| feature_bvh@countywide | ladder_runs | -- | 72,527,872 | 85,086,208 | 24,576 | 24,576 |
| hilbert_binary@countywide@split@w64 | cross_product_runs | 9,516,712 | 232,419,328 | 285,175,808 | 159,916,032 | 200,114,176 |
| hilbert_binary@countywide@split@w64 | mode_grid_runs | 9,516,712 | 232,394,752 | 285,171,712 | 159,891,456 | 200,110,080 |
| hilbert_binary@countywide@split@w64 | sweep_split_runs | 9,516,712 | 232,341,504 | 285,167,616 | 159,838,208 | 200,105,984 |
| hilbert_binary@countywide@w64 | cross_product_runs | 9,516,712 | 232,357,888 | 285,175,808 | 159,854,592 | 200,114,176 |
| hilbert_binary@countywide@w64 | ladder_runs | 9,516,712 | 232,542,208 | 285,212,672 | 160,038,912 | 200,151,040 |
| hilbert_binary@countywide@w64 | mode_grid_runs | 9,516,712 | 232,325,120 | 285,167,616 | 159,821,824 | 200,105,984 |
| hilbert_binary@countywide@w64 | sweep_runs | 9,516,712 | 232,476,672 | 285,212,672 | 159,973,376 | 200,151,040 |
| hilbert_rmi@countywide@split@w64 | cross_product_runs | 13,711,112 | 232,390,656 | 285,175,808 | 159,887,360 | 200,114,176 |
| hilbert_rmi@countywide@split@w64 | mode_grid_runs | 13,711,112 | 232,370,176 | 285,175,808 | 159,866,880 | 200,114,176 |
| hilbert_rmi@countywide@split@w64 | sweep_split_runs | 13,711,112 | 232,407,040 | 285,171,712 | 159,903,744 | 200,110,080 |
| hilbert_rmi@countywide@w64 | cross_product_runs | 13,711,112 | 232,370,176 | 285,171,712 | 159,866,880 | 200,110,080 |
| hilbert_rmi@countywide@w64 | ladder_runs | 13,711,112 | 232,501,248 | 285,212,672 | 159,997,952 | 200,151,040 |
| hilbert_rmi@countywide@w64 | mode_grid_runs | 13,711,112 | 232,353,792 | 285,175,808 | 159,850,496 | 200,114,176 |
| hilbert_rmi@countywide@w64 | sweep_runs | 13,711,112 | 232,435,712 | 285,216,768 | 159,932,416 | 200,155,136 |
| segment_bvh@countywide | cross_product_runs | 119,768,836 | 185,843,712 | 342,319,104 | 113,340,416 | 257,257,472 |
| segment_bvh@countywide | ladder_runs | 119,768,836 | 185,831,424 | 342,327,296 | 113,328,128 | 257,265,664 |
| segment_bvh@countywide | mode_grid_runs | 119,768,836 | 185,839,616 | 342,315,008 | 113,336,320 | 257,253,376 |
| segment_bvh@countywide@split | cross_product_runs | 119,768,836 | 185,761,792 | 342,315,008 | 113,258,496 | 257,253,376 |
| segment_bvh@countywide@split | mode_grid_runs | 119,768,836 | 185,753,600 | 342,323,200 | 113,250,304 | 257,261,568 |

## Invariants

137 of 137 re-derived checks passed.

