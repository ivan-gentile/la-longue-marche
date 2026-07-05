# Page coverage of the tex_output deliverables

Generated 2026-07-05 by `experiments/pilot/make_coverage.py`.

A page is counted only when the model returned a non-trivial
transcription. Untranscribed pages keep their `%% ===== Page N =====`
marker in the tex file with a one-line reason, so page alignment with
the scans is preserved. Machine-readable version: `coverage.json`.

## Variant `flash-lite-mateo` — complete corpus, shipped April 2026

| Volume | Tex file | Model | Pages transcribed | Missing | Missing ranges |
|---|---|---|---|---|---|
| 140-3 | `la_longue_marche_140-3_flash-lite-mateo.tex` | gemini-3.1-flash-lite-preview | **696/696** | 0 | — |
| 140-4 | `la_longue_marche_140-4_flash-lite-mateo.tex` | gemini-3.1-flash-lite-preview | **280/280** | 0 | — |

## Variant `mateo-canonical` — higher-effort Gemini Pro re-run, in progress (free-tier daily quota)

| Volume | Tex file | Model | Pages transcribed | Missing | Missing ranges |
|---|---|---|---|---|---|
| 140-3 | `la_longue_marche_140-3_mateo-canonical.tex` | gemini-3.1-pro-preview | **503/696** | 193 | 390, 409, 451, 454-481, 483-504, 507-516, 521, 523, 527-532, 534-535, 537-542, 544-549, 551-552, 554, 558, 564-569, 571-572, 575-600, 602-61… (full list in coverage.json) |
| 140-4 | `la_longue_marche_140-4_mateo-canonical.tex` | gemini-3.1-pro-preview | **236/280** | 44 | 144, 221, 225-226, 228-235, 237-240, 242-249, 252, 254, 257-261, 263-264, 266, 268, 270, 272-277, 279-280 |

## Reading guide

- `flash-lite-mateo` is the complete working draft of both volumes.
- `mateo-canonical` is the higher-effort Gemini Pro re-run of the same
  pages; it is being filled in as API quota allows and its gaps are
  listed above. Where it covers a page, prefer it over `flash-lite-mateo`.
- Section 49 begins at PDF page 495 of 140-3.
- The Bourbaki *Schémas* typescript transcription
  (`bourbaki_schemes_full_flash-lite.tex`, 437 pages) is complete.
