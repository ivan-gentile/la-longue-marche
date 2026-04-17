# Pilot Results — 2026-03-05

## Setup
- **10 benchmark pages** from 140-2 (Grothendieck pages 1-5, 50-54)
- **4 experiments**: A) full page no context, B) full page with context, C) strips no context, D) strips with context
- **2 models**: Gemini 3.1 Flash-Lite, Gemini 3.1 Pro
- **Total**: 160 API calls

## Timing & Cost
| Model | Time | Est. Cost |
|-------|------|-----------|
| Flash-Lite (80 calls) | 8.1 min | ~$0.15 |
| Pro (80 calls) | ~48 min | ~$2.50 |

Pro is **~6x slower** than Flash-Lite (thinking_level=medium vs low).

## Quantitative Results (Similarity to G103d Reference)

**Important caveat**: The SequenceMatcher-based similarity scores are LOW across the board (12-16%) because:
1. Page alignment between handwritten (575 pages) and typeset (305 pages) is NOT 1:1
2. Text normalization strips LaTeX that differs between handwritten OCR and typeset PDF extraction
3. The benchmark compares against ALL reference pages, not aligned ones

These scores are useful for **relative** comparison between conditions, not absolute quality.

### Flash-Lite
| Experiment | Avg Similarity | Avg Length | Unclear markers |
|------------|---------------|------------|-----------------|
| A) Full page, no context | **16.2%** | 1,262 | 31 |
| B) Full page, with context | 16.0% | 1,200 | 54 |
| C) Strips, no context | 13.7% | 1,705 | 29 |
| D) Strips, with context | 16.0% | 1,611 | 41 |

**Best**: Experiment A (full page, no context) — simplest approach wins.

### Pro
| Experiment | Avg Similarity | Avg Length | Unclear markers |
|------------|---------------|------------|-----------------|
| A) Full page, no context | 13.2% | 1,337 | 39 |
| B) Full page, with context | **15.1%** | 1,409 | 23 |
| C) Strips, no context | 14.5% | 1,610 | 48 |
| D) Strips, with context | 12.8% | 1,719 | 34 |

**Best**: Experiment B (full page, with context) — context helps Pro.

## Qualitative Analysis (the real findings)

### Model Comparison on Page 5 (§1, Proposition 1.1)

Both models correctly transcribe the core mathematical content:
- Proposition numbering preserved ✓
- Category theory notation ($\mathcal{E}$, $\hat{C}$, groupoid) ✓
- French mathematical prose preserved ✓
- Displayed equations with correct LaTeX ✓

**Pro advantages:**
- Catches **marginal notes** that Flash-Lite misses (`[MARGIN: ...]`)
- Better handling of **abbreviations** ("loc^t" for "localement")
- More careful `[unclear]` marking (23 vs 54 in Exp B — fewer but more precise)
- Better structure preservation

**Flash-Lite advantages:**
- 6x faster
- 15x cheaper
- Comparable core transcription quality

### Key Finding: Strips Don't Help (and May Hurt)

Counter to initial hypothesis:
- Strips produced **longer** output (more text) but **lower similarity** to reference
- Strips lose page-level context (marginal notes reference distant content)
- The overlap/dedup adds noise without quality gain
- Full-page images give the model enough resolution for Grothendieck's handwriting

### Key Finding: Context Helps Pro, Neutral for Flash-Lite

- For Pro: +1.9% similarity AND fewer [unclear] markers (23 vs 39)
- For Flash-Lite: essentially neutral (-0.2%)
- Interpretation: Pro's deeper reasoning can actually USE the context; Flash-Lite mostly ignores it

### Key Finding: Token Usage is Modest

| Condition | Prompt tokens | Output tokens |
|-----------|---------------|---------------|
| Flash-Lite page | ~1,400 | ~500 |
| Pro page | ~1,800 | ~600 |
| Pro with context | ~2,000 | ~600 |

At these token counts, full-archive cost (976 pages) would be:
- Flash-Lite: ~$0.50
- Pro with context: ~$25

## Recommendations

### For Production Pipeline
1. **Use full pages, not strips** — simpler, better quality, fewer API calls
2. **Use sequential context** (previous page transcription) — helps Pro, doesn't hurt Flash-Lite
3. **Two-tier approach**:
   - Flash-Lite for first pass (fast, cheap, decent quality)
   - Pro for verification/refinement on flagged pages (dense, many [unclear])

### Cost Projection for Full Archive (976 pages)
| Approach | API Calls | Est. Cost | Est. Time |
|----------|-----------|-----------|-----------|
| Flash-Lite only | 976 | ~$0.50 | ~1.5 hours |
| Pro only | 976 | ~$25 | ~8 hours |
| Flash-Lite + Pro on 20% worst | 1,171 | ~$6 | ~3 hours |

### Immediate Next Steps
1. **Ask Mateo for .tex source** of G103d → enables proper page-aligned evaluation
2. **Scale Flash-Lite** to full 140-3 + 140-4 (976 pages, ~$0.50)
3. **Identify worst pages** (most [unclear] markers) → re-run with Pro
4. **Build proper evaluation** once we have aligned LaTeX reference

## Raw Data
- Flash-Lite results: `results/run_20260305_114637_gemini-3.1-flash-lite-preview/`
- Pro results: `results/run_20260305_114642_gemini-3.1-pro-preview/`
- Human-readable: `transcriptions_*.txt` files in each directory
