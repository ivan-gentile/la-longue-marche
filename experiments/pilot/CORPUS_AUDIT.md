# Corpus audit — silent defects

Generated 2026-08-14 by `experiments/pilot/audit_corpus.py` (no API calls). Echo threshold: 0.75.

Checks each corpus for pages that were recorded as successful but may carry wrong content: a page echoing its predecessor (the model transcribing its context page instead of its target), a success with no real text, or identical text at two distant positions.

| Corpus | Pages with text | Echoes | Empty successes | Duplicate groups |
|---|---|---|---|---|
| La Longue Marche 140-3 — mateo-canonical (Pro) | 696 | 0 | 0 | 0 |
| La Longue Marche 140-4 — mateo-canonical (Pro) | 280 | 0 | 0 | 0 |
| La Longue Marche 140-3 — flash-lite-mateo | 696 | 0 | 0 | 0 |
| La Longue Marche 140-4 — flash-lite-mateo | 280 | 0 | 0 | 0 |
| Préschémas (Bourbaki Schémas) — page-by-page | 437 | 0 | 0 | 0 |
| Catégories de variétés (U46) — page-by-page | 23 | 0 | 0 | 0 |

No defects of any of the three classes were found.
