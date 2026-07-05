# La Longue Marche — Grothendieck OCR

AI-assisted transcription of Alexander Grothendieck's handwritten
manuscript *La longue marche à travers la théorie de Galois* (Part II,
Cote 140-3 and 140-4, ~976 pages) into LaTeX, in collaboration with
Mateo Carmona (Centre for Grothendieckian Studies (Centro di Studi Grothendieckiani)) and Olivia
Caramello (Istituto Grothendieck).

**The introductory blog post, for non-specialists:**
[thinkgentile.com — Transcribing Grothendieck's Handwriting with AI](https://thinkgentile.com/posts/grothendieck-ocr).

## What's in this repo

| Path | What |
|------|------|
| [`PIPELINE.md`](PIPELINE.md) | Full pipeline description written for Mateo — data flow, prompts, post-processing, evaluation. |
| [`CLAUDE.md`](CLAUDE.md) | Original project spec (for agents working in this repo). |
| [`tex_output/la_longue_marche_140-3_flash-lite-mateo.tex`](tex_output/la_longue_marche_140-3_flash-lite-mateo.tex) | 696-page transcription, `mateo-canonical` prompt, Gemini 3.1 Flash-Lite, ~1.0 MB. |
| [`tex_output/la_longue_marche_140-4_flash-lite-mateo.tex`](tex_output/la_longue_marche_140-4_flash-lite-mateo.tex) | 280-page transcription, `mateo-canonical` prompt, Gemini 3.1 Flash-Lite, ~0.34 MB. |
| [`tex_output/la_longue_marche_140-3_mateo-canonical.tex`](tex_output/la_longue_marche_140-3_mateo-canonical.tex) | Higher-effort Gemini 3.1 Pro re-run, **503/696 pages so far** (untranscribed pages carry an in-file marker). |
| [`tex_output/la_longue_marche_140-4_mateo-canonical.tex`](tex_output/la_longue_marche_140-4_mateo-canonical.tex) | Higher-effort Gemini 3.1 Pro re-run, **236/280 pages so far**. |
| [`tex_output/COVERAGE.md`](tex_output/COVERAGE.md) | **Page-level coverage manifest** of every deliverable (machine-readable twin: `coverage.json`). |
| [`tex_output/bourbaki_schemes_full_flash-lite.tex`](tex_output/bourbaki_schemes_full_flash-lite.tex) | Full 437-page Bourbaki *Schémas* typed-text transcription, Flash-Lite, ~1.0 MB. |
| [`tex_output/bourbaki_schemes_gemini_whole_p1-5.tex`](tex_output/bourbaki_schemes_gemini_whole_p1-5.tex) | Bourbaki 5-page control benchmark, Gemini 3.1 Pro (whole-doc mode). |
| [`tex_output/bourbaki_schemes_opus_p1-5.tex`](tex_output/bourbaki_schemes_opus_p1-5.tex) | Bourbaki 5-page control benchmark, Claude Opus 4.7. |
| [`reference/part1_sections_19_36/`](reference/part1_sections_19_36) | Mateo's corrected Part I sections (few-shot style reference). |
| [`reference/validation/49.1old.tex`](reference/validation/49.1old.tex), [`49.1new.tex`](reference/validation/49.1new.tex) | Paired ground truth for Section 49.I (our output vs Mateo's corrected). |
| [`experiments/pilot/`](experiments/pilot) | All scripts (transcription runner, diagram re-run, notation normalization, build scripts). |
| [`experiments/pilot/production-flash-lite-mateo/*/transcriptions.json`](experiments/pilot/production-flash-lite-mateo) | Per-page JSON output from the full Flash-Lite production run. |
| [`experiments/pilot/49_1_error_profile.md`](experiments/pilot/49_1_error_profile.md) | Categorized diff between our pipeline and Mateo's corrected version. |
| [`experiments/pilot/bench_opus_vs_gemini/summary.md`](experiments/pilot/bench_opus_vs_gemini/summary.md) | Gemini 3.1 Pro vs Claude Opus 4.7 benchmark. |
| [`experiments/pilot/bench_mateo_canonical/summary.md`](experiments/pilot/bench_mateo_canonical/summary.md) | Prompt refresh validation (composite quality 0.113 → 0.742). |

## Headline numbers

- **976 pages** of handwritten French mathematical manuscript transcribed in full as a Flash-Lite working draft (April 2026). The higher-effort Gemini 3.1 Pro re-run covers **503/696** (140-3) and **236/280** (140-4) pages so far — exact page-level coverage of every file in [`tex_output/COVERAGE.md`](tex_output/COVERAGE.md).
- **~$1.4** total recorded API cost for the full Flash-Lite production run ($1.05 + $0.38 in the run `summary.json` files).
- **Gemini 3.1 Flash-Lite** + `mateo-canonical` prompt produced the full working draft. It reaches composite quality **0.67** on the full Section 49.1 ground truth — **6× better than the shipped baseline (0.113)** — at **150× lower cost** than Claude Opus 4.7.
- Model comparison on 5-page Section 49.1 ground truth:

| Model | Composite quality | Cost / 5 pages | Latency |
|-------|------------------|----------------|---------|
| Shipped baseline (`text-first-fewshot`) | 0.113 | — | — |
| Claude Opus 4.7 + `mateo-canonical` | 0.661 | $1.173 | 28.6 s |
| Gemini 3.1 Pro + `mateo-canonical` | 0.742 | $0.074 | 67.8 s |
| **Gemini 3.1 Flash-Lite + `mateo-canonical`** | **0.777** | **$0.008** | **7.4 s** |

> **How to read "composite quality":** it is a *style-conformance* score —
> LaTeX scaffolding, canonical notation, absence of pipeline residue,
> measured against the 5-page Section 49.1 ground truth. It does **not**
> measure textual fidelity. The March 2026 LLM-judge evaluation
> (`experiments/pilot/judge_results_combined.json`), which does rate
> fidelity, ranked Gemini 3.1 Pro above Flash-Lite and flagged page
> completeness as the dominant failure mode — that is why the Pro
> `mateo-canonical` re-run exists alongside the Flash-Lite draft.

- Diagram rollout complete: 140-3 (114 pages) and 140-4 (58 pages) re-transcribed with `diagram-tikzcd` prompt, producing `\begin{tikzcd}` blocks.
- Bourbaki typed-text benchmark: full 437-page transcription available (`tex_output/bourbaki_schemes_full_flash-lite.tex`).

## Reproducing

```bash
pip install -r requirements.txt  # google-genai, anthropic, pymupdf, python-dotenv
cp .env.example .env             # fill in ANTHROPIC_API_KEY, GEMINI_API_KEY

# Production transcription
GEMINI_API_KEY=... python experiments/pilot/run_production.py --volume 140-3

# Diagram re-run, then merge
GEMINI_API_KEY=... python experiments/pilot/retranscribe_diagrams.py
python experiments/pilot/retranscribe_diagrams.py --merge

# Regex notation pass
python experiments/pilot/normalize_notation.py --mode regex

# Rebuild tex_output/*.tex from the JSON
python experiments/pilot/build_tex.py

# Opus 4.7 vs Gemini 3.1 Pro benchmark
ANTHROPIC_API_KEY=... python experiments/pilot/run_opus_vs_gemini.py \
    --gemini-source cached --skip-whole-doc

# Section 49.1 categorized diff
python experiments/pilot/diagnose_49_1.py
```

## Collaboration

This project exists because Mateo Carmona (CSG) shared the Part I
typeset source and ground truth. Please cite:

- Mateo Carmona, Centre for Grothendieckian Studies (Centro di Studi Grothendieckiani)
- Olivia Caramello, Istituto Grothendieck
- Ivan Gentile (IFAB), AI pipeline and evaluation

## License

Code under MIT. Transcription outputs follow the license of the
Montpellier archives ([grothendieck.umontpellier.fr](https://grothendieck.umontpellier.fr/archives-grothendieck/)).
