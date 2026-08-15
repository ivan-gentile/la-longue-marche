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
| [`tex_output/la_longue_marche_140-3_mateo-canonical.tex`](tex_output/la_longue_marche_140-3_mateo-canonical.tex) | **Recommended.** Higher-effort Gemini 3.1 Pro re-run, **696/696 pages**, Section 49 included. |
| [`tex_output/la_longue_marche_140-4_mateo-canonical.tex`](tex_output/la_longue_marche_140-4_mateo-canonical.tex) | **Recommended.** Higher-effort Gemini 3.1 Pro re-run, **280/280 pages**. |
| [`tex_output/COVERAGE.md`](tex_output/COVERAGE.md) | **Page-level coverage manifest** of every deliverable (machine-readable twin: `coverage.json`). |
| [`tex_output/bourbaki_schemes_pages_flash-lite.tex`](tex_output/bourbaki_schemes_pages_flash-lite.tex) | **Préschémas (Bourbaki *Schémas*), page-by-page: 437/437 pages, PDF-indexed markers.** Source scans: U86u1 (pages 1–210) + U86u2 (pages 211–437). |
| [`tex_output/varietes_categories_U46.tex`](tex_output/varietes_categories_U46.tex) | ***Catégories de variétés* (n° 262), 100 pages**, page-by-page on Gemini 3.1 Pro. Source scans: U46. |
| [`experiments/pilot/CORPUS_AUDIT.md`](experiments/pilot/CORPUS_AUDIT.md) | **Silent-defect audit** of every corpus: context echoes, empty successes, distant duplicates. |
| [`experiments/pilot/COSTS.md`](experiments/pilot/COSTS.md) | **True API cost of every run**, thinking tokens included. |
| [`tex_output/bourbaki_schemes_full_flash-lite.tex`](tex_output/bourbaki_schemes_full_flash-lite.tex) | Superseded whole-doc transcription — ~70 of 437 pages silently missing, no page alignment ([`GAPS.md`](experiments/bourbaki/GAPS.md)). Kept for comparison. |
| [`tex_output/bourbaki_schemes_gemini_whole_p1-5.tex`](tex_output/bourbaki_schemes_gemini_whole_p1-5.tex) | Bourbaki 5-page control benchmark, Gemini 3.1 Pro (whole-doc mode). |
| [`tex_output/bourbaki_schemes_opus_p1-5.tex`](tex_output/bourbaki_schemes_opus_p1-5.tex) | Bourbaki 5-page control benchmark, Claude Opus 4.7. |
| [`reference/part1_sections_19_36/`](reference/part1_sections_19_36) | Mateo's corrected Part I sections (few-shot style reference). |
| [`reference/validation/49.1old.tex`](reference/validation/49.1old.tex), [`49.1new.tex`](reference/validation/49.1new.tex) | Paired ground truth for Section 49.I (our output vs Mateo's corrected). |
| [`experiments/pilot/`](experiments/pilot) | All scripts (transcription runner, diagram re-run, notation normalization, build scripts). |
| [`experiments/pilot/production-flash-lite-mateo/*/transcriptions.json`](experiments/pilot/production-flash-lite-mateo) | Per-page JSON output from the full Flash-Lite production run. |
| [`experiments/pilot/49_1_error_profile.md`](experiments/pilot/49_1_error_profile.md) | Categorized diff between our pipeline and Mateo's corrected version. |
| [`experiments/pilot/bench_opus_vs_gemini/summary.md`](experiments/pilot/bench_opus_vs_gemini/summary.md) | Gemini 3.1 Pro vs Claude Opus 4.7 benchmark. |
| [`experiments/pilot/bench_mateo_gemini/summary.md`](experiments/pilot/bench_mateo_gemini/summary.md) | Prompt refresh validation on Gemini 3.1 Pro (composite quality 0.113 → 0.742). |

## Headline numbers

- **976 pages** of handwritten French mathematical manuscript transcribed **completely twice**: as a Gemini 3.1 Pro corpus (696/696 and 280/280 — the recommended one) and as a cheaper Flash-Lite draft. Exact page-level coverage of every file in [`tex_output/COVERAGE.md`](tex_output/COVERAGE.md).
- **537 further pages** of typescript: Préschémas (437) and *Catégories de variétés* (100), both page-by-page with markers written from the PDF index.
- **~$93** total API cost across every run, thinking tokens included ([`experiments/pilot/COSTS.md`](experiments/pilot/COSTS.md)): $81 for the two Pro corpora, $5.56 for the Flash-Lite draft, $5.82 for *Variétés*, $0.66 for Préschémas.
- Every corpus passes a **silent-defect audit** across seven classes — a page carrying its predecessor's text, leaked model reasoning, truncation, unbalanced LaTeX, escaping artifacts, empty successes, distant duplicates ([`experiments/pilot/CORPUS_AUDIT.md`](experiments/pilot/CORPUS_AUDIT.md)). Building a deliverable now runs that audit as a release gate. The August sweep found and repaired 22 pages of Préschémas carrying the previous page's text, 1,246 malformed `\\operatorname`, and ~40 pages of the La Longue Marche corpora that were truncated, carried the model's English reasoning, or would not compile; see [`experiments/bourbaki/GAPS.md`](experiments/bourbaki/GAPS.md) and [`PIPELINE.md` §10](PIPELINE.md).
- **Gemini 3.1 Flash-Lite** + `mateo-canonical` prompt reaches composite *style* quality **0.67** on the full Section 49.1 ground truth — **6× better than the shipped baseline (0.113)** — at a small fraction of Claude Opus 4.7's cost. On *content fidelity*, however, Gemini 3.1 Pro is the more faithful model, which is why the Pro corpus is the recommended one ([`experiments/pilot/fidelity_49_1.md`](experiments/pilot/fidelity_49_1.md)).
- Model comparison on 5-page Section 49.1 ground truth:

| Model | Composite quality | Cost / 5 pages | Latency |
|-------|------------------|----------------|---------|
| Shipped baseline (`text-first-fewshot`) | 0.113 | — | — |
| Claude Opus 4.7 + `mateo-canonical` | 0.661 | $1.173 | 28.6 s |
| Gemini 3.1 Pro + `mateo-canonical` | 0.742 | $0.074 | 67.8 s |
| **Gemini 3.1 Flash-Lite + `mateo-canonical`** | **0.777** | **$0.008** | **7.4 s** |

> **Caveat on the cost column:** these per-page costs come from
> `bench_*/results.json`, which never recorded thinking tokens. Gemini
> bills thinking at the output rate, so the two Gemini rows understate
> real spend (on the production corpora the true figure is several
> times the naive one), while the Claude row does not — Anthropic counts
> thinking inside its output tokens. The cost gap between the models is
> therefore narrower than the table suggests. Run-level costs computed
> correctly are in [`experiments/pilot/COSTS.md`](experiments/pilot/COSTS.md).

> **How to read "composite quality":** it is a *style-conformance* score —
> LaTeX scaffolding, canonical notation, absence of pipeline residue,
> measured against the 5-page Section 49.1 ground truth. It does **not**
> measure textual fidelity. The March 2026 LLM-judge evaluation
> (`experiments/pilot/judge_results_combined.json`), which does rate
> fidelity, ranked Gemini 3.1 Pro above Flash-Lite and flagged page
> completeness as the dominant failure mode — that is why the Pro
> `mateo-canonical` re-run exists alongside the Flash-Lite draft.

- Diagram rollout complete: 140-3 (114 pages) and 140-4 (58 pages) re-transcribed with `diagram-tikzcd` prompt, producing `\begin{tikzcd}` blocks.
- **August 2026 model refresh** ([`experiments/pilot/bench_models_2026_08/summary.md`](experiments/pilot/bench_models_2026_08/summary.md)): `gemini-3.7-flash` (released 2026-08-13) reaches **0.562** word-level fidelity on Section 49.1 against Gemini 3.1 Pro's **0.573**, at **a sixth of the cost** and a quarter of the latency — it replaces Flash-Lite as the draft model. The *newest* Flash-Lite (`gemini-3.5-flash-lite`) measured markedly **worse** than the older one it would replace (0.313, omitting 244 of 763 reference tokens) and was not adopted: bumping every model id to the latest would have quietly degraded quality. Model ids and prices now live in one table, [`experiments/pilot/models.py`](experiments/pilot/models.py).

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

# Quality gates — no API calls, run before sharing anything
python experiments/pilot/audit_corpus.py        # silent defects → CORPUS_AUDIT.md
python experiments/pilot/make_coverage.py       # page coverage → COVERAGE.md
python experiments/pilot/recompute_costs.py     # true costs → COSTS.md

# Typescripts, page-by-page (markers written from the PDF index)
GEMINI_API_KEY=... python experiments/bourbaki/run_bourbaki_pages.py
GEMINI_API_KEY=... python experiments/varietes/run_varietes_pages.py

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
