# Benchmark split changelog

## Revision 2 — 2026-11-14

The initial 20-question set was run and its five test traces were inspected while improving the structure-aware chunker. To avoid reporting those viewed examples as an untouched holdout, questions `q16`–`q20` were moved to `dev`. Five new test questions (`q21`–`q25`) were written from previously unused evidence pages (PDF pages 45–48 and 51), their evidence was verified against the normalized corpus, and the chunker/configuration was then frozen before the final run.

Final split: 20 dev / 5 test. The replacement test is still small and follows the same corpus/model, so it supports only a limited within-corpus comparison. Do not treat the original q16–q20 results as final test results.
