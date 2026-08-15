# Corpus audit — defects no error count reveals

Generated 2026-08-15 by `experiments/pilot/audit_corpus.py` (no API calls). Echo threshold (word-level): 0.75.

Each column is a class of page that was recorded as a successful transcription but may carry wrong or unusable content. See the module docstring for what each one means and why it is checked.

| Corpus | Pages with text | Echoes | Reasoning leaks | Truncated | Unbalanced env | Escape artifacts | Empty | Dup groups |
|---|---|---|---|---|---|---|---|---|
| La Longue Marche 140-3 — february-original (superseded, published) | 696 | 0 | 0 | 2 | 4 | 1 | 0 | 0 |
| La Longue Marche 140-4 — february-original (superseded, published) | 280 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| La Longue Marche 140-3 — mateo-canonical (Pro) | 696 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| La Longue Marche 140-4 — mateo-canonical (Pro) | 280 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| La Longue Marche 140-3 — flash-lite-mateo | 696 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| La Longue Marche 140-4 — flash-lite-mateo | 280 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Préschémas (Bourbaki Schémas) — page-by-page | 437 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Catégories de variétés (U46) — page-by-page | 100 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |


### Truncated pages — La Longue Marche 140-3 — february-original (superseded, published)

- page 432: odd number of single $ (inline math left open)
- page 561: odd number of single $ (inline math left open); ends mid-command

### Unbalanced environments — La Longue Marche 140-3 — february-original (superseded, published)

- page 9: \begin{array} closed by \end{matrix}
- page 320: \begin{array} closed by \end{matrix}
- page 378: \begin{matrix} closed by \end{cases}
- page 638: \begin{tikzcd} never closed

### Escape artifacts (literal double backslash) — La Longue Marche 140-3 — february-original (superseded, published)

- page 19: 1 occurrence(s)

### Unbalanced environments — La Longue Marche 140-4 — february-original (superseded, published)

- page 56: \begin{array} closed by \end{matrix}; \begin{array} closed by \end{matrix}

### Known genuine duplicates (exempted, verified against the scans) — Préschémas (Bourbaki Schémas) — page-by-page

- page 130: 0.97 similarity to page 129 — PDF pages 129 and 130 are both typescript page '- 94 -' — a second impression of the same sheet, verified against the scans on 2026-08-14. The transcriptions agree because the pages do.
