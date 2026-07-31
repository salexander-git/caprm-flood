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
