# La Longue Marche — Grothendieck OCR

AI-assisted transcription of Alexander Grothendieck's handwritten
manuscript *La longue marche à travers la théorie de Galois* (Part II,
Cote 140-3 and 140-4, ~976 pages) into LaTeX, in collaboration with
Mateo Carmona (Centre pour les Sciences de Grothendieck) and Olivia
Caramello (Istituto Grothendieck).

**The introductory blog post, for non-specialists:**
[thinkgentile.com — Transcribing Grothendieck's Handwriting with AI](https://thinkgentile.com/posts/grothendieck-ocr).

## What's in this repo

| Path | What |
|------|------|
| [`PIPELINE.md`](PIPELINE.md) | Full pipeline description written for Mateo — data flow, prompts, post-processing, evaluation. |
| [`CLAUDE.md`](CLAUDE.md) | Original project spec (for agents working in this repo). |
| [`tex_output/la_longue_marche_140-3.tex`](tex_output/la_longue_marche_140-3.tex) | 696-page transcription, ~1.0 MB. |
| [`tex_output/la_longue_marche_140-4.tex`](tex_output/la_longue_marche_140-4.tex) | 280-page transcription, ~0.35 MB. |
| [`tex_output/bourbaki_schemes_opus_p1-5.tex`](tex_output/bourbaki_schemes_opus_p1-5.tex) | Typed-text control benchmark (EGA-era schemes), Claude Opus 4.7, first 5 pages. |
| [`reference/part1_sections_19_36/`](reference/part1_sections_19_36) | Mateo's corrected Part I sections (few-shot style reference). |
| [`reference/validation/49.1old.tex`](reference/validation/49.1old.tex), [`49.1new.tex`](reference/validation/49.1new.tex) | Paired ground truth for Section 49.I (our output vs Mateo's corrected). |
| [`experiments/pilot/`](experiments/pilot) | All scripts (transcription runner, diagram re-run, notation normalization, build scripts). |
| [`experiments/pilot/production/*/transcriptions.json`](experiments/pilot/production) | Per-page JSON output from the production run. |
| [`experiments/pilot/49_1_error_profile.md`](experiments/pilot/49_1_error_profile.md) | Categorized diff between our pipeline and Mateo's corrected version. |
| [`experiments/pilot/bench_opus_vs_gemini/summary.md`](experiments/pilot/bench_opus_vs_gemini/summary.md) | Gemini 3.1 Pro vs Claude Opus 4.7 benchmark. |
| [`experiments/pilot/bench_mateo_canonical/summary.md`](experiments/pilot/bench_mateo_canonical/summary.md) | Prompt refresh validation (composite quality 0.113 → 0.743). |

## Headline numbers

- **976 pages** of handwritten French mathematical manuscript transcribed.
- **~€10** total API cost for the production run.
- **Gemini 3.1 Pro** (medium thinking) is the production model; **Claude
  Opus 4.7** is 15× more expensive for modest notation-drift gains.
- Current corpus composite quality on Section 49.1: **0.13**. With the
  April 2026 `mateo-canonical` prompt (not yet re-run across the full
  corpus): **0.74**.

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

- Mateo Carmona, Centre pour les Sciences de Grothendieck
- Olivia Caramello, Istituto Grothendieck
- Ivan Gentile (IFAB), AI pipeline and evaluation

## License

Code under MIT. Transcription outputs follow the license of the
Montpellier archives ([grothendieck.umontpellier.fr](https://grothendieck.umontpellier.fr/archives-grothendieck/)).
