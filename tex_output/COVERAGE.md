# Page coverage of the tex_output deliverables

Generated 2026-08-15 by `experiments/pilot/make_coverage.py`.

A page is counted only when the model returned a non-trivial
transcription. Untranscribed pages keep their `%% ===== Page N =====`
marker in the tex file with a one-line reason, so page alignment with
the scans is preserved. Machine-readable version: `coverage.json`.

## Variant `february-original` — superseded February 2026 run (`text-first-fewshot` prompt) — still published because it was delivered in April; prefer `mateo-canonical`

| Volume | Tex file | Model | Pages transcribed | Missing | Missing ranges |
|---|---|---|---|---|---|
| 140-3 | `la_longue_marche_140-3.tex` | gemini-3.1-pro-preview | **696/696** | 0 | — |
| 140-4 | `la_longue_marche_140-4.tex` | gemini-3.1-pro-preview | **280/280** | 0 | — |

## Variant `flash-lite-mateo` — complete corpus, shipped April 2026

| Volume | Tex file | Model | Pages transcribed | Missing | Missing ranges |
|---|---|---|---|---|---|
| 140-3 | `la_longue_marche_140-3_flash-lite-mateo.tex` | gemini-3.1-flash-lite-preview | **696/696** | 0 | — |
| 140-4 | `la_longue_marche_140-4_flash-lite-mateo.tex` | gemini-3.1-flash-lite-preview | **280/280** | 0 | — |

## Variant `mateo-canonical` — higher-effort Gemini Pro re-run (canonical — prefer where it covers a page)

| Volume | Tex file | Model | Pages transcribed | Missing | Missing ranges |
|---|---|---|---|---|---|
| 140-3 | `la_longue_marche_140-3_mateo-canonical.tex` | gemini-3.1-pro-preview | **696/696** | 0 | — |
| 140-4 | `la_longue_marche_140-4_mateo-canonical.tex` | gemini-3.1-pro-preview | **280/280** | 0 | — |

## Standalone documents (page-by-page, census-gated)

| Document | Tex file | Model | Pages transcribed | Missing | Missing ranges |
|---|---|---|---|---|---|
| Préschémas (Bourbaki Schémas typescript) | `bourbaki_schemes_pages_flash-lite.tex` | gemini-3.1-flash-lite-preview | **437/437** | 0 | — |
| Catégories de variétés (typescript n° 262) | `varietes_categories_U46.tex` | gemini-3.1-pro-preview | **100/100** | 0 | — |

- Source of *Préschémas (Bourbaki Schémas typescript)*: U86u1.pdf + U86u2.pdf (CSG): tex pages 1-210 = U86u1, tex pages 211-437 = U86u2 pages 1-227.
- Source of *Catégories de variétés (typescript n° 262)*: U46.pdf (CSG).

## Reading guide

- `flash-lite-mateo` is the complete working draft of both volumes.
- `mateo-canonical` is the higher-effort Gemini Pro re-run of the same
  pages; where it covers a page, prefer it over `flash-lite-mateo`.
- Section 49 begins at PDF page 495 of 140-3 (pages 495-696).
- The Bourbaki *Schémas* whole-document transcription
  (`bourbaki_schemes_full_flash-lite.tex`) silently lacks ~70 of its
  437 source pages and its page markers are not PDF positions (see
  `experiments/bourbaki/GAPS.md`); the page-by-page replacement is
  `bourbaki_schemes_pages_flash-lite.tex`.
