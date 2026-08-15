# Compile check

Generated 2026-08-15 by `experiments/pilot/compile_check.py` with `tex_output/preamble.tex`.

`audit_corpus.py` checks that pages are structurally sound. This is the separate question of whether the LaTeX actually compiles: a transcription of handwritten mathematics can be well-formed as text and still carry a missing `$` or an unbalanced brace. Errors are attributed to the page whose `%% ===== Page N =====` marker precedes them.

| Document | Pages | Compile clean | With errors | Total errors | PDF pages |
|---|---|---|---|---|---|
| La Longue Marche 140-3 (canonical) | 696 | **661** | 35 | 483 | 699 |
| La Longue Marche 140-4 (canonical) | 280 | **275** | 5 | 107 | — (aborted) |
| La Longue Marche 140-3 (flash-lite) | 696 | **667** | 29 | 419 | 700 |
| La Longue Marche 140-4 (flash-lite) | 280 | **277** | 3 | 3 | — (pdflatex hung) |
| Préschémas (Bourbaki Schémas) | 437 | **430** | 7 | 65 | 437 |
| Catégories de variétés (U46) | 100 | **100** | 0 | 0 | 100 |

### La Longue Marche 140-3 (canonical)

35 page(s) produce LaTeX errors. Most common:

- 147x `! Missing \endcsname inserted.`
- 55x `! Package pgf Error: No shape named `tikz@f@N-N-N' is known.`
- 50x `! Missing $ inserted.`
- 47x `! Missing } inserted.`
- 39x `! Missing \endgroup inserted.`
- 30x `! Extra }, or forgotten $.`


Pages (error count): 27 (2), 53 (43), 67 (2), 92 (2), 109 (2), 185 (43), 207 (2), 222 (1), 223 (1), 283 (6), 284 (2), 320 (2), 335 (72), 423 (49), 424 (25), 431 (1), 432 (1), 441 (2), 448 (12), 492 (1), 523 (3), 538 (8), 557 (2), 561 (10), 563 (4), 586 (43), 619 (71), 637 (8), 642 (2), 644 (35), 666 (6), 667 (8), 669 (4), 683 (6), 692 (1)

### La Longue Marche 140-4 (canonical)

5 page(s) produce LaTeX errors. Most common:

- 50x `! Extra }, or forgotten $.`
- 48x `! Missing } inserted.`
- 4x `! Missing $ inserted.`
- 2x `! Missing number, treated as zero.`
- 2x `! Illegal unit of measure (pt inserted).`
- 1x `! LaTeX Error: Unicode character ́ (U+N)`


Pages (error count): 1 (1), 10 (2), 34 (2), 43 (2), 91 (100)

### La Longue Marche 140-3 (flash-lite)

29 page(s) produce LaTeX errors. Most common:

- 131x `! Missing \endcsname inserted.`
- 57x `! Package pgf Error: No shape named `tikz@f@N-N-N' is known.`
- 38x `! Missing \endgroup inserted.`
- 30x `! Missing } inserted.`
- 27x `! Missing $ inserted.`
- 25x `! Extra }, or forgotten \endgroup.`


Pages (error count): 33 (1), 84 (4), 87 (8), 92 (2), 98 (14), 110 (4), 127 (4), 185 (43), 230 (1), 335 (72), 423 (49), 431 (1), 432 (3), 441 (2), 448 (12), 465 (1), 490 (1), 502 (1), 557 (2), 561 (6), 563 (4), 619 (71), 637 (8), 638 (2), 639 (49), 644 (35), 666 (6), 667 (8), 669 (4)

### La Longue Marche 140-4 (flash-lite)

3 page(s) produce LaTeX errors. Most common:

- 1x `! LaTeX Error: Unicode character ́ (U+N)`
- 1x `! You can't use `\leqno' in horizontal mode.`
- 1x `! Illegal unit of measure (pt inserted).`


Pages (error count): 1 (1), 32 (1), 33 (1)

### Préschémas (Bourbaki Schémas)

7 page(s) produce LaTeX errors. Most common:

- 19x `! Missing $ inserted.`
- 12x `! Missing \endgroup inserted.`
- 8x `! Extra }, or forgotten \endgroup.`
- 6x `! Argument of \tikz@quote@@parser has an extra }.`
- 6x `! Paragraph ended before \tikz@quote@@parser was complete.`
- 2x `! You can't use `\/' in vertical mode.`


Pages (error count): 53 (4), 54 (8), 75 (38), 149 (3), 309 (6), 396 (4), 421 (2)

