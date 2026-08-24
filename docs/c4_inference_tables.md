# C4 item 1 — surrogate inference cost

## Batch sweep at 8 threads, against the shipped default batch (65536)

| batch | n batches | prop/s | us/prop | spread | interval vs default | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 267,362 | 56,326 | 17.754 | 0.019 | 8.596-9.119 | b faster |
| 64 | 4,178 | 385,091 | 2.597 | 0.117 | 1.246-1.451 | b faster |
| 4096 | 66 | 499,410 | 2.002 | 0.083 | 0.966-1.090 | NOT RESOLVED |
| 65536 | 5 | 505,400 | 1.979 | 0.041 | - | reference |
| full | 1 | 508,168 | 1.968 | 0.028 | 0.957-1.024 | NOT RESOLVED |

## Threading: 1 thread against 8 threads

| batch | us/prop @1 | us/prop @8 | speedup | interval | verdict |
| --- | --- | --- | --- | --- | --- |
| 1 | 17.708 | 17.754 | 0.997x | 0.973-1.049 | NOT RESOLVED |
| 64 | 2.278 | 2.597 | 0.877x | 0.725-1.022 | NOT RESOLVED |
| 4096 | 2.440 | 2.002 | 1.219x | 1.107-1.244 | b faster |
| 65536 | 2.482 | 1.979 | 1.254x | 1.200-1.278 | b faster |
| full | 2.465 | 1.968 | 1.253x | 1.214-1.269 | b faster |

## Where the time goes

| stage | threading speedup | interval | verdict |
| --- | --- | --- | --- |
| fourier_encoding | 1.043x | 1.013-1.084 | b faster |
| mlp_forward | 2.019x | 1.940-2.122 | b faster |
| full_predict | 1.223x | 1.148-1.341 | b faster |

The surrogate emits one scalar. It does not produce the four components,
their provenance, or the source-feature identifiers the pipeline produces,
and no figure above should be read without that sentence beside it.

## C4 item 2 — the exact pipeline's own cost

Warm caches. Setup and compute are separate columns because the shipped
CLI digests a 21.2 MB GeoPackage on every invocation and that cost
belongs to the tool rather than to the algorithm. Boundary declared in
`caprm.pipeline_cost.TIMING_BOUNDARY` before the first run.

| stage | workload | N | setup s | compute s | us/prop | spread | n |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fema_point_in_polygon | 10000 | 10,000 | 3.761 | 0.224 | 22.355 | 0.104 | 5 |
| fema_point_in_polygon | 100000 | 100,000 | 4.810 | 1.068 | 10.677 | 0.018 | 3 |
| fema_point_in_polygon | countywide | 267,362 | 9.283 | 2.973 | 11.118 | 0.054 | 3 |
| nearest_water_python | 10000 | 10,000 | 0.552 | 7.809 | 780.945 | 0.022 | 5 |
| nearest_water_python | 100000 | 100,000 | 1.755 | 123.419 | 1234.189 | 0.045 | 3 |
| nearest_water_python | countywide | 267,362 | 5.160 | 329.572 | 1232.680 | 0.021 | 3 |
| terrain_sampling | 10000 | 10,000 | 0.027 | 1.149 | 114.893 | 0.057 | 5 |
| terrain_sampling | 100000 | 100,000 | 0.220 | 11.138 | 111.384 | 0.029 | 3 |
| terrain_sampling | countywide | 267,362 | 0.625 | 32.508 | 121.587 | 0.011 | 3 |
| scoring | 10000 | 10,000 | 0.034 | 0.036 | 3.562 | 0.039 | 5 |
| scoring | 100000 | 100,000 | 0.252 | 0.335 | 3.352 | 0.054 | 3 |
| scoring | countywide | 267,362 | 0.751 | 1.134 | 4.243 | 0.054 | 3 |

### Marginal cost, `a + b*N` over the measured workloads

| stage | a (s) | b (us/property) | points | max residual |
| --- | ---: | ---: | ---: | ---: |
| fema_point_in_polygon | 0.0665 | 10.770 | 3 | 0.2207 |
| nearest_water_python | -3.3697 | 1247.898 | 3 | 0.1664 |
| terrain_sampling | -0.4880 | 122.585 | 3 | 0.3578 |
| scoring | -0.0433 | 4.333 | 3 | 1.0003 |

### Per-property cost is not constant across workload size

| stage | 10,000 | 100,000 | countywide |
| --- | ---: | ---: | ---: |
| fema_point_in_polygon | 22.4 | 10.7 | 11.1 |
| nearest_water_python | 780.9 | 1234.2 | 1232.7 |
| terrain_sampling | 114.9 | 111.4 | 121.6 |
| scoring | 3.6 | 3.4 | 4.2 |

Units are us/property. If cost were linear in N these rows would be flat.
They are not, and the fits say so from the other direction: 3 of 4 stages fit a NEGATIVE fixed cost (nearest_water_python, terrain_sampling, scoring), which is not physical. A negative intercept is what a straight line does when it is asked to reach points whose per-unit cost is still rising.

**`b` above is therefore not a marginal cost that can be quoted alone.**
It is the slope of a line through three points that do not lie on one.
The `scoring` stage makes this plainest: its worst residual is 100.0
percent of the observed value.

Three points fit two parameters. The residual qualifies the linearity
claim; it does not confirm it. No R^2 is published: with three points it
is trivially near 1.0 for almost any monotone data and would read as
corroboration it cannot supply.

The C++ nearest-water query is cited from B6 at 34.099 us/property (segment BVH, 25 m cap, original verification, disk predicate, invocation `ladder`) and is not re-measured here.

