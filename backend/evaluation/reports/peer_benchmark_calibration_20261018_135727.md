# UC-16 Synthetic Threshold Calibration

- Dataset: `peer-benchmark-synthetic-v1`
- Model: `sentence-transformers/all-MiniLM-L6-v2`
- Covered: distance <= 0.40
- Partially covered: distance <= 0.68
- Macro F1: 0.719
- Status: provisional; pending faculty-labelled UAT calibration

| Segment | Expected | Predicted | Distance | Nearest synthetic staff |
|---|---|---|---:|---|
| covered-cloud | covered | covered | 0.284 | staff-cloud |
| covered-nlp | covered | partially_covered | 0.550 | staff-ai |
| covered-database | covered | covered | 0.267 | staff-data |
| covered-security | covered | covered | 0.391 | staff-security |
| covered-software | covered | covered | 0.347 | staff-software |
| partial-robotics | partially_covered | partially_covered | 0.663 | staff-ai |
| partial-vision | partially_covered | candidate_gap | 0.744 | staff-ai |
| partial-governance | partially_covered | partially_covered | 0.556 | staff-security |
| partial-iot | partially_covered | partially_covered | 0.674 | staff-security |
| gap-quantum | candidate_gap | candidate_gap | 0.714 | staff-security |
| gap-biology | candidate_gap | partially_covered | 0.631 | staff-theory |
| gap-graphics | candidate_gap | candidate_gap | 0.706 | staff-theory |
| gap-neuroscience | candidate_gap | partially_covered | 0.669 | staff-ai |
| gap-hardware | candidate_gap | candidate_gap | 0.718 | staff-theory |
