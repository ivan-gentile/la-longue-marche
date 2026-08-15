# Compile check

Generated 2026-08-15 by `experiments/pilot/compile_check.py` with `tex_output/preamble.tex`.

`audit_corpus.py` checks that pages are structurally sound. This is the separate question of whether the LaTeX actually compiles: a transcription of handwritten mathematics can be well-formed as text and still carry a missing `$` or an unbalanced brace. Errors are attributed to the page whose `%% ===== Page N =====` marker precedes them.

A compiler that stops early has not certified the pages it never read: the **Verified through** column says how far it got, and **Compile clean** counts only within that range.

| Document | Pages | Verified through | Compile clean | With errors | Total errors | PDF pages |
|---|---|---|---|---|---|---|
| La Longue Marche 140-3 (canonical) | 696 | all | **679** | 17 | 68 | 699 |
| La Longue Marche 140-4 (canonical) | 280 | all | **278** | 2 | 5 | 280 |
| La Longue Marche 140-3 (flash-lite) | 696 | all | **673** | 23 | 143 | 700 |
| La Longue Marche 140-4 (flash-lite) | 280 | page 145 only | **139** | 6 | 106 | — (aborted) |
| Préschémas (Bourbaki Schémas) | 437 | all | **436** | 1 | 4 | 437 |
| Catégories de variétés (U46) | 100 | all | **100** | 0 | 0 | 100 |

### La Longue Marche 140-3 (canonical)

17 page(s) produce LaTeX errors. Most common:

- 57x `! Package pgf Error: No shape named `tikz@f@N-N-N' is known.`
- 4x `! Undefined control sequence.`
- 2x `! You can't use `macro parameter character #' in vertical mo`
- 2x `! Missing $ inserted.`
- 2x `! You can't use `\leqno' in horizontal mode.`
- 1x `! You can't use `\leqno' in math mode.`


Pages (error count): 92 (2), 298 (1), 320 (2), 368 (1), 424 (2), 429 (1), 431 (1), 441 (2), 448 (12), 557 (2), 561 (10), 563 (4), 619 (2), 637 (8), 666 (6), 667 (8), 669 (4)

### La Longue Marche 140-4 (canonical)

2 page(s) produce LaTeX errors. Most common:

- 4x `! Package pgf Error: No shape named `tikz@f@N-N-N' is known.`
- 1x `! Misplaced alignment tab character &.`


Pages (error count): 131 (1), 175 (4)

### La Longue Marche 140-3 (flash-lite)

23 page(s) produce LaTeX errors. Most common:

- 57x `! Package pgf Error: No shape named `tikz@f@N-N-N' is known.`
- 20x `! Missing $ inserted.`
- 18x `! Missing } inserted.`
- 13x `! Extra }, or forgotten $.`
- 8x `! Extra alignment tab has been changed to \cr.`
- 6x `! Undefined control sequence.`


Pages (error count): 33 (1), 84 (4), 87 (8), 92 (2), 98 (14), 127 (4), 230 (1), 431 (1), 441 (2), 448 (12), 465 (1), 490 (1), 502 (1), 557 (2), 561 (6), 563 (4), 619 (2), 637 (8), 638 (2), 639 (49), 666 (6), 667 (8), 669 (4)

### La Longue Marche 140-4 (flash-lite)

6 page(s) produce LaTeX errors. Most common:

- 45x `! Missing $ inserted.`
- 39x `! Extra }, or forgotten $.`
- 13x `! Missing } inserted.`
- 2x `! Missing { inserted.`
- 1x `! You can't use `\leqno' in horizontal mode.`
- 1x `! Double superscript.`


Pages (error count): 32 (1), 94 (1), 98 (1), 115 (2), 131 (1), 145 (100)

### Préschémas (Bourbaki Schémas)

1 page(s) produce LaTeX errors. Most common:

- 1x `! You can't use `\/' in vertical mode.`
- 1x `! You can't use `\raise' in vertical mode.`
- 1x `! Missing number, treated as zero.`
- 1x `! Illegal unit of measure (pt inserted).`


Pages (error count): 54 (4)

