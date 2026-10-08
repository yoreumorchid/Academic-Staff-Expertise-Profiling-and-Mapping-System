# BENCH-01 Internal Expertise Parameter Evaluation

Generated: 2026-10-08T03:31:48.466585+00:00

## Scope and limitation

This DB-independent sensitivity run uses two deterministic synthetic faculties
with three and six known expertise groups. It checks parameter behaviour,
coverage, vector/input alignment, and reproducibility. It does **not** establish
that clusters found in real faculty data are externally valid; representative
real profiles and peer documents remain a BENCH-03 requirement.

## Fixed selection rule

`score = 0.45 * ARI + 0.25 * coverage + 0.20 * normalized silhouette + 0.10 * stability`

ARI is agreement with the fixture's known groups. Coverage prevents a setting
from looking accurate by excluding uncertain staff. Stability is ARI between
the baseline result and five input permutations. Ties prefer lower threshold,
smaller cluster cap, then fewer initializations.

| tau | K_max | n_init | mean ARI | mean silhouette | coverage | stability | score |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.70 | 6 | 10 | 1.0000 | 0.9921 | 1.0000 | 1.0000 | 0.9992 |
| 0.70 | 6 | 20 | 1.0000 | 0.9921 | 1.0000 | 1.0000 | 0.9992 |
| 0.80 | 6 | 10 | 1.0000 | 0.9899 | 1.0000 | 1.0000 | 0.9990 |
| 0.80 | 6 | 20 | 1.0000 | 0.9899 | 1.0000 | 1.0000 | 0.9990 |
| 0.50 | 6 | 10 | 1.0000 | 0.9892 | 1.0000 | 1.0000 | 0.9989 |
| 0.50 | 6 | 20 | 1.0000 | 0.9892 | 1.0000 | 1.0000 | 0.9989 |
| 0.60 | 6 | 10 | 1.0000 | 0.9568 | 1.0000 | 1.0000 | 0.9957 |
| 0.60 | 6 | 20 | 1.0000 | 0.9568 | 1.0000 | 1.0000 | 0.9957 |
| 0.50 | 5 | 10 | 0.9000 | 0.9024 | 1.0000 | 1.0000 | 0.9452 |
| 0.50 | 5 | 20 | 0.9000 | 0.9024 | 1.0000 | 1.0000 | 0.9452 |
| 0.70 | 5 | 10 | 0.9000 | 0.9022 | 1.0000 | 1.0000 | 0.9452 |
| 0.70 | 5 | 20 | 0.9000 | 0.9022 | 1.0000 | 1.0000 | 0.9452 |
| 0.80 | 5 | 10 | 0.9000 | 0.9008 | 1.0000 | 1.0000 | 0.9451 |
| 0.80 | 5 | 20 | 0.9000 | 0.9008 | 1.0000 | 1.0000 | 0.9451 |
| 0.60 | 5 | 10 | 0.9000 | 0.8707 | 1.0000 | 1.0000 | 0.9421 |
| 0.60 | 5 | 20 | 0.9000 | 0.8707 | 1.0000 | 1.0000 | 0.9421 |
| 0.50 | 4 | 10 | 0.8250 | 0.8294 | 1.0000 | 1.0000 | 0.9042 |
| 0.50 | 4 | 20 | 0.8250 | 0.8294 | 1.0000 | 1.0000 | 0.9042 |
| 0.70 | 4 | 20 | 0.8250 | 0.8136 | 1.0000 | 1.0000 | 0.9026 |
| 0.80 | 4 | 20 | 0.8250 | 0.8124 | 1.0000 | 1.0000 | 0.9025 |
| 0.70 | 4 | 10 | 0.8250 | 0.8113 | 1.0000 | 1.0000 | 0.9024 |
| 0.80 | 4 | 10 | 0.8250 | 0.8083 | 1.0000 | 1.0000 | 0.9021 |
| 0.60 | 4 | 10 | 0.8250 | 0.7892 | 1.0000 | 1.0000 | 0.9002 |
| 0.60 | 4 | 20 | 0.8250 | 0.7892 | 1.0000 | 1.0000 | 0.9002 |
| 0.50 | 3 | 10 | 0.7667 | 0.7661 | 1.0000 | 1.0000 | 0.8716 |
| 0.50 | 3 | 20 | 0.7667 | 0.7661 | 1.0000 | 1.0000 | 0.8716 |
| 0.60 | 3 | 20 | 0.7667 | 0.7073 | 1.0000 | 1.0000 | 0.8657 |
| 0.70 | 3 | 10 | 0.7200 | 0.7309 | 1.0000 | 1.0000 | 0.8471 |
| 0.70 | 3 | 20 | 0.7200 | 0.7309 | 1.0000 | 1.0000 | 0.8471 |
| 0.80 | 3 | 10 | 0.7200 | 0.7304 | 1.0000 | 1.0000 | 0.8470 |
| 0.80 | 3 | 20 | 0.7200 | 0.7304 | 1.0000 | 1.0000 | 0.8470 |
| 0.60 | 3 | 10 | 0.7200 | 0.7097 | 1.0000 | 1.0000 | 0.8450 |

## Selected parameters

- `tau = 0.7`
- `K_max = 6`
- `n_init = 10`
- selection score = `0.9992`

The companion JSON contains per-scenario metrics for every tested setting.
