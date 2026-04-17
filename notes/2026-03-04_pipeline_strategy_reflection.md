# Pipeline Strategy Reflection — 2026-03-04

## State of Play

**What exists:**
- `grothendieck-ocr/`: Working pipeline, tested on ~16 pages, single-pass full-page approach. Good for blog post demos.
- `la_longe_marche/`: Well-designed 3-pass spec in CLAUDE.md, but **nothing implemented** — all `scripts/`, `prompts/`, `images/`, `transcriptions/` folders are empty.
- **Raw material**: 140-3 (696 pages) + 140-4 (280 pages) = **976 pages** to transcribe. 976 single-page PDFs already extracted from 140-3.
- **Mateo's reference**: `G103d.pdf` — his LaTeX transcription of Part 1 (Cote 140-2), but we have the **compiled PDF, not the .tex source**.

---

## Assessment

### 1. Strips vs Full Pages — benchmark first

The intuition is sound: a smaller image means the model focuses better on fewer lines of dense handwriting. But there's a trade-off:
- **Pro strips**: Less visual noise, model allocates more attention per line, fewer hallucinations
- **Con strips**: Loses page-level context (a marginal note might refer to something across the page), adds complexity (overlap dedup, edge artifacts), and **3-4x the API calls**

The cost difference is negligible (even 4x Gemini Flash for 976 pages is ~$8). But **quality is what matters**, and this is an empirical question you can answer fast.

**Concrete proposal**: Pick 10 pages of varying density (sparse, medium, packed+diagrams). Transcribe each both ways. Compare against Mateo's PDF for the pages where we have overlap, or manually spot-check. This gives you data instead of speculation.

### 2. Using Mateo's PDF (without LaTeX source)

Two uses:

**a) As benchmark/golden set**: OCR Mateo's compiled PDF (clean typeset) to get clean text. Then compare your handwriting OCR output against it for the same pages. This gives you a rough quality metric.

**b) As context for few-shot prompting**: Extract pages from Mateo's PDF alongside the corresponding handwritten scans. Show the model: "here's a handwritten page, here's what the correct transcription looks like" — literally as image pairs in the prompt.

**Action: Ask Mateo for the .tex source.** One email, high return.

### 3. Sequential context (preceding text)

Almost certainly useful and cheap to test. Mathematical writing is heavily sequential — notation introduced on page N used without redefinition on page N+1. Passing the previous page's transcription as text context:
- Helps resolve ambiguous symbols
- Costs almost nothing (text tokens are cheap vs image tokens)
- Easy to A/B test

### 4. 3-pass architecture is over-engineered for now

**Start with 1 pass, then add complexity only if needed:**
1. Full page → Gemini with good prompt + sequential context
2. Evaluate quality on benchmark pages
3. **Only if** quality is insufficient on dense pages, add the strip approach
4. **Only if** strip merging is problematic, add Pass 1 structure detection

### 5. Translation — not yet

- It doubles cost and complexity
- Translation from correct French LaTeX is a much easier downstream task (text-to-text, no vision)
- Mixing transcription and translation in one pass risks contaminating both

Transcribe first. Translate later. Separate concerns.

---

## Pilot Plan

1. **Pick 10 benchmark pages** from 140-2 where we have Mateo's transcription as ground truth
2. **Run 4 experiments** on those 10 pages:
   - Full page, no context
   - Full page, with previous page text context
   - Strips (3 per page), no context
   - Strips, with context
3. **Compare outputs** against Mateo's PDF
4. **Result**: empirical data on which approach to scale

Cost: <$1 with Gemini Flash. Produces concrete result to send Mateo.
