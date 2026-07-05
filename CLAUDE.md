# La Longue Marche — Grothendieck Archives OCR Project

## Project Overview

Transcription of Alexander Grothendieck's handwritten manuscript *"La longue marche à travers la théorie de Galois"* (Cote 140) from the Montpellier archives into LaTeX. Collaboration with Mateo Carmona (archivist, Centre for Grothendieckian Studies (Centro di Studi Grothendieckiani)) and Olivia Caramello (Istituto Grothendieck).

**Scope**: ~1,000 pages of handwritten mathematics (Part 2 of the manuscript). Part 1 (~90% transcribed by Mateo in LaTeX) serves as training/alignment data.

**Source material**: 2 PDFs (140-3.pdf: 696 pages, 140-4.pdf: 280 pages) containing scanned pages at ~200 DPI (1680x2360 native). Pages rendered at 300 DPI produce 2481x3508 images.

## Handwriting Characteristics

- Density varies enormously: sparse pages (~15 lines) to packed pages with commutative diagrams, marginal annotations, and insertions
- Heavy mathematical notation: hat/tilde/wedge decorators (π̂, Ĝ T), subscripts, category-theory arrows, Greek letters
- Frequent abbreviations: "hom" for homomorphisme, "autom." for automorphismes, etc.
- Marginal notes and insertion marks
- Archive headers/footers (Université de Montpellier) should be stripped from transcription

## Pipeline Architecture

> **As implemented (April 2026):** production sends whole PDF pages
> directly to the API (no rasterization, no strips — strips were
> benchmarked and lost to full pages), with the previous page attached
> as visual context. Prompt `mateo-canonical`
> (`experiments/pilot/prompts_v2.py`), then a `diagram-tikzcd` re-run
> pass, regex notation normalization, and tex build
> (`finalize_*.py` → `tex_output/`, coverage in
> `tex_output/COVERAGE.md`). The subsections below are the original
> design sketch, kept for history; see `PIPELINE.md` for the current
> pipeline.

### Image Preparation
- PDFs split into single pages in `raw_pdf/single_pages/`
- Pages rendered to PNG at 300 DPI using pymupdf (fitz)
- Archive headers (~top 3%) and footers (~bottom 5%) cropped
- Each page split into 3-4 horizontal strips with ~20% vertical overlap

### Transcription Strategy (two-pass)

**Pass 1 — Structure (full page, fast/cheap model)**:
- Rough structure: line count, equation vs prose regions, diagrams
- Page number and section identification
- Model: Gemini 2.0 Flash or similar

**Pass 2 — Detail (strips, high-quality model)**:
- 3-4 horizontal strips per page, each transcribed separately
- Prompt context includes:
  - Symbol glossary (Grothendieck's notation in this manuscript)
  - Previous page's transcription (text, not image) for continuity
  - Pass 1 structure as scaffold
- Model: Claude Opus / Sonnet or Gemini with vision

**Pass 3 — Merge + Validate**:
- Stitch strips, deduplicate overlapping lines
- Model-assisted reconciliation of conflicts
- Cross-reference with known notation from Part 1

### Prompt Design Principles
- Include few-shot examples from Part 1 (Mateo's verified transcription aligned with scan crops)
- Provide a symbol glossary of manuscript-specific notation
- Give mathematical context (what section we're in, what objects are being discussed)
- Output format: LaTeX with `\section`, `\begin{equation}`, etc.
- Mark uncertain readings with `[?]` or `[unclear: ...]`

## Open Research Questions

1. **Full-page vs strips**: Quality delta for handwriting OCR on VLMs?
2. **Few-shot in-context learning**: Do example pairs (crop → LaTeX) from Part 1 improve transcription of Part 2?
3. **Symbol glossary**: Does a notation reference in the prompt help or add noise?
4. **Sequential context**: Does previous-page transcription improve current-page accuracy?
5. **Two-image input**: Does passing two page images together help (continuity) or hurt (resolution)?
6. **Model comparison**: Claude Opus vs Sonnet vs Gemini Flash — quality/cost Pareto frontier for this task

## Project Structure

```
la_longe_marche/
├── CLAUDE.md                   # This file
├── README.md                   # Collaborator-facing overview + headline numbers
├── PIPELINE.md                 # Pipeline documentation written for Mateo
├── raw_pdf/                    # Original scanned PDFs (gitignored)
│   ├── 140-3.pdf               # Pages 1-696
│   └── 140-4.pdf               # Pages 1-280
├── tex_output/                 # Final LaTeX deliverables + COVERAGE.md manifest
├── reference/
│   ├── part1_sections_19_36/   # Mateo's corrected Part I sections (few-shot pool)
│   └── validation/             # 49.1old.tex / 49.1new.tex ground-truth pair
├── experiments/
│   ├── pilot/                  # ALL pipeline code: runners, prompts_v2.py,
│   │                           #   bench_* comparisons, production-* run data,
│   │                           #   finalize_*.py, make_coverage.py, viewers
│   └── bourbaki/               # Typed-text control (Bourbaki Schémas, G103d.pdf)
├── share/                      # Dated delivery packages + email drafts
└── notes/                      # Project logs, blog/article drafts
```

Note: `scripts/`, `prompts/`, `costs/`, and `transcriptions/` exist but
are empty — the original design placed code there, the pilot in
`experiments/pilot/` became production in place. API keys come from
`.env` (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`), untracked.

## Key Dependencies

- `pymupdf` (fitz): PDF rendering
- `PyPDF2`: PDF splitting
- `Pillow`: Image processing
- API clients: `anthropic`, `google-generativeai` (or similar)

## Workflow Commands

```bash
# Production transcription (resume-aware: only untranscribed pages run)
GEMINI_API_KEY=... python experiments/pilot/run_production.py --volume 140-3 --resume

# Diagram re-run, then merge into the main JSON
GEMINI_API_KEY=... python experiments/pilot/retranscribe_diagrams.py
python experiments/pilot/retranscribe_diagrams.py --merge

# Rebuild deliverables from the run JSONs (no API calls)
python experiments/pilot/finalize_mateo_canonical.py   # Gemini Pro variant
python experiments/pilot/finalize_flash_lite.py        # Flash-Lite variant

# Regenerate the page-coverage manifest (no API calls)
python experiments/pilot/make_coverage.py
```

## Conventions

- Page numbering follows Grothendieck's own pagination (handwritten numbers), not PDF page indices
- File naming: `140-3_page_NNNN` where NNNN is the PDF page index (1-indexed, zero-padded)
- All LaTeX output uses UTF-8
- Uncertain readings: `\uncertain{text}` macro (defined in preamble)
- Editorial notes: `\editnote{text}` macro
