# Benchmark: clickhouse

- sql2api 0.3.0, 2026-09-24T07:57:22.577565+00:00
- Linux-6.8.0-139-generic-x86_64-with-glibc2.39, 20 CPUs
- 1,000,000 rows, 5 repeats per scenario (median/min/max shown)

| Scenario | Latency (s) | Peak RSS delta (MB) | Rows | Bytes |
|---|---|---|---|---|
| narrow/buffered | 2.32 (2.26-2.54) | 348 (303-426) | 1,000,000 | 48,888,908 |
| narrow/streamed | 12.01 (11.94-12.12) | 0 (0-0) | 1,000,000 | 48,888,908 |
| wide/buffered | 9.58 (9.56-9.73) | 1233 (980-2039) | 1,000,000 | 488,888,908 |
| wide/streamed | 18.24 (18.10-18.32) | 0 (-6-0) | 1,000,000 | 488,888,908 |
