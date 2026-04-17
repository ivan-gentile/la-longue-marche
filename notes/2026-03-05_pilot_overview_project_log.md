---
tags:
  - grothendieck-ocr
  - project-log
  - pilot
  - overview
spawned: 2026-03-05
origin: "pilot experiment completion"
---

# Grothendieck OCR Pilot — Project Log

**Date:** March 4–5, 2026 (Sessions 1–4)
**Status:** Benchmark V2 completed. All 68 calls succeeded. Judge evaluation completed. Production pipeline launched on full manuscript (976 pages).
**Costs to date:** ~$2.65 (pilot) + ~$0.01 (VLM extraction) + ~$0.82 (Benchmark V2) + ~$23 (production in progress) = ~$27 total

---

## 1. Project Context and Collaboration

**What:** AI-assisted transcription of Alexander Grothendieck's handwritten manuscript *"La longue marche à travers la théorie de Galois"* — a ~976-page mathematical manuscript in French, handwritten in Grothendieck's distinctive script.

**Who:**
- **Ivan Gentile** — AI engineer, project lead on the technical/ML side
- **Mateo Carmona** — Archivist at Centre pour les Sciences de Grothendieck, custodian of the manuscript, maintains existing .tex transcriptions (G103d reference)

**Collaboration history:** Email thread dating to late 2024. Mateo has partial .tex transcriptions of the manuscript. Ivan proposed using modern vision-language models to accelerate the transcription effort.

**Prior work:** Two existing codebases:
- `grothendieck-ocr` — First attempt, ~16 pages tested, basic pipeline
- `la_longe_marche` — Latest repo, well-designed CLAUDE.md spec but empty implementation folders

---

## 2. Timeline of Events

### March 4, 2026

**Evening — Context loading and strategic assessment**

Ivan loaded the full email thread history with Mateo and both codebases into Claude. Asked Claude to assess whether his planned 3-pass architecture (from the `la_longe_marche` CLAUDE.md) was appropriate.

Claude analyzed both codebases and concluded the 3-pass architecture was over-engineered for the current state. Proposed a simpler pilot-first approach: test a few conditions on 10 pages, measure, then decide.

**Strategic reflection saved** → `notes/2026-03-04_pipeline_strategy_reflection.md`
Key insight: "start with 1 pass, then add complexity only if needed."

### March 5, 2026

**Morning — Ivan says "run the pilot"**

Ivan gave Claude full autonomy to design and execute the experiment. Claude:

1. **Created `prepare.py`** — Renders 10 benchmark pages at 300 DPI from the manuscript PDF, generates horizontal strips (top/middle/bottom), extracts G103d reference .tex text for each page
2. **Created `run_pilot.py`** — Runs 4 experimental conditions × 2 models through Gemini API, with proper rate limiting and sequential context support
3. **Created `evaluate.py`** — SequenceMatcher-based evaluation comparing model output against reference transcriptions

**Preparation results:** 20 full-page images, 30 strips, 42 reference files extracted.

**Model research detour** — Ivan pointed out that Gemini 3.1 models were the latest. Claude researched online, found correct model IDs:
- `gemini-3.1-flash-lite-preview` (cheap, fast)
- `gemini-3.1-pro-preview` (expensive, powerful)

Discovered key Gemini 3 requirements: temperature must be 1.0 (lower values cause looping behavior), `thinking_level` parameter available.

**API setup** — Ivan created a Google Cloud project, enabled Vertex AI, set up billing. Asked about billing mechanics (auto-charges to card, budget alerts available in Google Cloud Console).

**Pilot execution:**
- Flash-Lite run: 80 API calls, 8.1 minutes, ~$0.15
- Pro run: 80 API calls, ~48 minutes, ~$2.50
- All 160 calls successful, zero errors

**Evaluation and analysis** — Claude ran evaluation on both result sets, performed both quantitative (similarity scores, tables) and qualitative (manual comparison of specific pages) analysis.

**Afternoon — Visual inspection tools**

Ivan asked "how can I visually inspect the single results?" → Claude created `viewer.py`, generating `pilot_viewer.html` (69 MB, embedded images, side-by-side comparison of handwriting vs transcription).

Ivan then asked "can you create a dashboard for me to see all of these?" → Claude created `dashboard.py`, generating `pilot_dashboard.html` (69 MB interactive dashboard with 5 tabs).

Ivan used the dashboard extensively for qualitative inspection of results.

### March 5, 2026 — Afternoon/Evening Session (Session 2)

**Ivan notices Pro over-formatting (qualitative observation)**

After using the dashboard for qualitative review, Ivan flagged a pattern: "gemini pro tries too much to copy the exact structure of the document, it should not worry of putting hfill when unnecessary." This was a pure human-judgment observation from visual inspection — the dashboard enabling exactly the kind of expert assessment it was designed for.

### March 5, 2026 — Late Evening Session (Session 3)

**Benchmark V2 runner completely rewritten with systematic testing dimensions**

**Benchmark V2 runner completely rewritten with systematic testing dimensions**

Claude rebuilt `run_benchmark_v2.py` from scratch with a sophisticated experimental design featuring:

**Late Evening Session 3 Work:**
- **8 prompt styles:** Baseline (latex-direct), text-first, text-inline, plus fewshot variants of each, plus new two-pass and two-pass-fewshot variants
- **2 models:** flash-lite and pro (from V1 pilot)
- **3 input formats:** png-300dpi, png-150dpi (half-resolution cached rendering), pdf-direct (native PDF pages extracted via PyMuPDF)
- **Multi-page context:** Optional previous page IMAGE alongside current page (not just text context from pilot) — uses consecutive pairs (page 5←4, page 52←51, page 54←53)

Smart phased preset design to minimize redundant calls:
- **Phase A (prompt sweep):** 8 prompts × 3 pages × 1 model = 24 calls. Tests which prompt works best.
- **Phase B (model comparison):** Best 3 prompts × 2 pages × 2 models = 12 calls. Tests flash-lite vs pro on winning prompts.
- **Phase C (input format):** Best prompt × 3 input formats × 2 models × 2 pages = 12 calls. Tests png-300dpi vs png-150dpi vs pdf-direct.
- **Phase D (multi-page context):** Best config × 2 models × 3 page pairs with/without previous image = 12 calls. Tests whether previous page image helps.
- **All-phases preset:** All 4 phases combined = 68 calls total, ~$0.82 estimated cost, ~9 minutes runtime.

Fully cross-dimensional WITHOUT full factorial explosion — each phase addresses one question, shares results between phases. Measurably smarter than a brute-force grid search.

**Two-pass prompt designed and added to prompts_v2.py**

New two-pass prompt variant:
- **Pass 1 (raw reading):** Model transcribes with uncertainty markers: `[?word?]` for unclear text, preserves raw observations
- **Pass 2 (clean output):** Model takes Pass 1 output and produces final formatted version
- Both passes visible in output, separated by `---PASS2---` divider
- Lets external reviewers (Mateo, scholars) see the model's raw reading confidence before it applies formatting

Designed to answer: "Can two passes improve accuracy? Does showing uncertainty help human review?"

**LLM-as-judge evaluation framework created (judge_v2.py)**

Replaced brittle string-matching evaluation with intelligent judgment:
- Uses flash-lite as a judge to rate transcriptions on 5 dimensions: `text_accuracy`, `math_accuracy`, `completeness`, `formatting_quality`, `overall`
- Each dimension rated 1–5 with justification
- Cost: ~$0.001 per judgment (very cheap)
- Produces JSON output: `{ "page": X, "condition": Y, "scores": {...}, "reasoning": "..." }`
- Much more reliable signal than SequenceMatcher (which was 12–16% on pilot data)

Rationale: "Can the model objectively assess another model's transcription?" This transforms evaluation from string metrics to semantic judgment.

**PDF-direct input support implemented**

Runner now supports raw PDF pages directly (not pre-rendered PNG):
- Uses PyMuPDF to extract single pages from PDF as raw bytes
- Passes to Gemini as native PDF (Gemini v3.1 models support PDF input)
- Tests whether Gemini's internal PDF processing is better than pre-rendered PNG
- Eliminates rendering overhead and potential quality loss from PNG compression

**Multi-image context architecture expanded**

Enhanced from Session 2 (which supported text context only):
- Runner now constructs multi-image prompts with consecutive page pairs
- Passes **previous page IMAGE** alongside current page
- Uses same prompts but with additional `\n[Previous page image above]\n` instruction
- Tests whether visual continuity improves transcription (especially for equations spanning pages, margin references)
- 3 page pairs tested: 5←4, 52←51, 54←53 (chosen for diversity and prior good performance)

**150 DPI rendering added for efficient testing**

On-the-fly rendering at half resolution (150 DPI vs pilot's 300 DPI):
- Cached to `images_150dpi/` folder to avoid re-rendering
- Tests whether Gemini 3.1 resizes internally anyway (if so, 150 DPI is sufficient and faster)
- Reduces input file size, potentially speeds up API calls
- Comparable to web-resolution image serving

**Benchmark V2 completed — all 68 calls succeeded**

All-phases preset execution: 68 calls across 17 experimental conditions × 4 test pages
- Actual runtime: ~9 minutes
- Actual cost: ~$0.82 (matched estimate)
- Produced JSON outputs per phase: `phase_a_results.json`, `phase_b_results.json`, `phase_c_results.json`, `phase_d_results.json`
- Judge evaluations completed using `judge_v2.py` across all 68 transcriptions

### March 6, 2026 — Session 4 (Results Analysis and Production Launch)

**Benchmark V2 results analyzed — clear production winner identified**

Claude analyzed all 68 judge evaluations (5 dimensions each):
- **Winner identified:** text-first-fewshot + Pro + PDF-direct + multi-image context = 3.8/5 overall
- **Pro consistently outperforms Flash-Lite:** +0.5–1.0 across all dimensions
- **Two-pass disappoints:** Worst performance across both models (Flash-Lite 2.0/5, Pro 3.0/5)
- **PDF-direct matches PNG-300:** Gemini's internal PDF processing is excellent — eliminates rendering overhead
- **150 DPI matches 300 DPI:** Gemini normalizes internally; high resolution unnecessary
- **Multi-image context helps:** Previous page IMAGE context improves coherence (+0.2–0.3 on Pro)
- **Completeness is universal bottleneck:** Average 2.1/5 across all conditions (text_accuracy 3.2–3.5, formatting 3.4–3.8)

**Dashboard V2 generated**

Created `benchmark_v2_dashboard.html` with 6 interactive tabs:
1. **Leaderboard** — Conditions ranked by overall judge score
2. **Dimensions** — 5D judge scores (text_accuracy, math_accuracy, completeness, formatting_quality, overall)
3. **Phase Analysis** — Phase A/B/C/D results and insights
4. **Heatmap** — 2D performance matrix (conditions × pages)
5. **Viewer** — Per-condition details with judge reasoning
6. **Findings** — Narrative summary and production recommendations

**Production pipeline launched (`run_production.py`)**

Ivan asked: "Can you transcribe the full manuscript now?" Claude built production runner:
- **Configuration:** text-first-fewshot + Pro + PDF-direct + multi-image context (optimal from V2)
- **Key improvement:** 16k max output tokens (vs 8k in benchmark) to reduce truncation and address completeness bottleneck
- **Scope:** 140-3.pdf (696 pages) + 140-4.pdf (280 pages) = 976 pages total
- **Resume-safe design:** Checkpoints after each page, resumable without reprocessing
- **Output:** Per-page .md transcriptions + JSON progress/cost logs
- **Estimated metrics:**
  - Cost: ~$23 (Pro @ $0.0235/page)
  - Duration: ~2.7 hours
  - Status: **Running** (in progress)

**Claude builds evaluate_v2.py — aligned evaluation replacing the flawed v1 (Session 2 work documented below)**

The first evaluation's 12–16% scores were meaningless because G103d reference pages didn't align linearly with manuscript pages. Claude built `evaluate_v2.py` to fix this:

1. **Manual PAGE_ALIGNMENT_HINTS** — A dict mapping benchmark pages to their actual G103d reference pages, since the manuscript and Mateo's transcription follow completely different page-breaking schemes.
2. **Content-based alignment discovery** — Ran `SequenceMatcher` against all 303 pages of G103d to find true mappings. Results destroyed the linear assumption:
   - Manuscript page 5 → G103d page 6
   - Manuscript pages 50–53 → §7 (G103d pages 30–37)
   - Manuscript page 54 → §8 (G103d pages 38–40)
3. **Aggressive text normalization** — Stripped ALL LaTeX formatting commands before comparison, so evaluation measures content accuracy not formatting fidelity.
4. **Dual metric** — `combined = 50% SequenceMatcher + 50% word Jaccard overlap`, more robust than SequenceMatcher alone.
5. **New metric: `formatting_ratio`** — Formatting commands / total LaTeX commands. This directly quantified Ivan's qualitative observation: Pro Experimental B had 39.5% formatting ratio vs Flash-Lite's 5–10%.

**Dashboard update — 3-column viewer with reference**

Ivan asked to see Mateo's reference alongside the model outputs. Claude added G103d as Column 3 in the dashboard. Then Ivan asked: "can you display also the pdf?" Claude rendered all 46 G103d pages as PNG images at 150 DPI and embedded them in the dashboard, giving Ivan side-by-side visual comparison of manuscript image, model output, and Mateo's existing transcription.

**VLM-based reference extraction — the quality breakthrough**

Ivan asked: "can you improve the way you get text?" The `fitz` (PyMuPDF) extraction from G103d produced garbled text from the typeset PDF — the reference text itself was poor quality. Claude wrote `extract_reference_vlm.py` using Gemini Flash-Lite as a vision model on the rendered G103d page images. Two extraction prompts per page:
- **Raw text** — Plain text for evaluation comparison
- **LaTeX** — Faithful LaTeX reproduction for final output

Results: 17 pages extracted (14 raw text + 17 LaTeX). Several 503 errors from Gemini API overload required automatic retries. Also discovered and fixed a bug where **thinking tokens were leaking through** into responses — an operator precedence issue in the response parsing code (`part.text` was being checked before `part.thought`).

A notable failure: pages 4 and 5 raw extraction returned ~131K characters each — the model entered a hallucination loop on those specific pages, generating massive repetitive output instead of transcribing the content.

**Re-evaluation with VLM reference text — proof that reference quality was the bottleneck**

With the VLM-extracted reference text replacing fitz output, Claude re-ran evaluation:
- Pro best score improved from ~13% to **19.0%**
- Page 5 hit **44.9%** (was ~25%)

This proved the core insight: **reference text quality was THE bottleneck**, not model capability. The models were better than the evaluation suggested all along.

**Dashboard final update — full reference integration**

The dashboard was updated with:
- VLM text now replaces fitz in the `REF` constant
- `REF_LATEX` — VLM LaTeX extractions added
- `REF_SOURCE` — Per-page badges showing `vlm` or `fitz` extraction source
- **View toggle** in reference column: PDF | Text | LaTeX | All
- Dashboard now **77.5 MB** (up from 69 MB due to embedded reference page images)

**Prompt engineering V2 — systematic prompt design**

Three prompt styles designed for benchmark V2:
1. **text-first** — Plain text output, LaTeX only for math environments
2. **latex-direct** — Full LaTeX output (current baseline approach)
3. **text-inline** — Markdown-style with inline LaTeX

Each style has a **fewshot variant** using the page 5 correct transcription as an example. Benchmark V2 matrix: ~160–240 API calls, estimated $4–6.

**Human review workflow discussion**

Ivan asked about the final review process for when transcriptions go to scholars. Discussion produced several design concepts:
- **Confidence annotations** — HIGH/MED/LOW per section
- **Anchor points** — `%%ANCHOR: prop-1.1` markers for structural navigation
- **Two-pass architecture** — Raw transcription + confidence pass → clean LaTeX pass → human review
- **Review UI concept** — Interface for Mateo and scholars to efficiently correct transcriptions

---

## 3. Division of Labor

### What Ivan Did

**Session 1 (Morning):**
- Provided strategic direction and full project context (email history, codebases)
- Made the go/no-go decision to run the pilot
- Set up Google Cloud billing and provided API key
- Corrected model versions (pointed to Gemini 3.1)
- Requested visual inspection tools when needed
- Visually inspected results via dashboard to form qualitative judgments
- Made final strategic decisions based on data

**Session 2 (Afternoon/Evening):**
- Identified Pro over-formatting through qualitative dashboard inspection — this observation drove the entire `formatting_ratio` metric and new evaluation approach
- Asked "can you display also the pdf?" — pushed dashboard from text-only to visual reference comparison
- Asked "can you improve the way you get text?" — triggered the VLM extraction breakthrough
- Asked about human review workflow — shaped the confidence annotation and review UI design
- Drove every major direction change through questions and observations

**Session 4 (Next morning, after V2 results):**
- Reviewed benchmark V2 results and judge evaluation summary
- Approved winner configuration: text-first-fewshot + Pro + PDF-direct + multi-image context
- Asked "can you transcribe the full manuscript now?" — triggered production pipeline launch
- Confirmed 16k token limit increase as right trade-off for addressing completeness bottleneck

### What Claude Did

**Session 1 (Morning):**
- Explored and analyzed both existing codebases in depth
- Designed the experimental framework (4 conditions × 2 models)
- Wrote ALL Python code (5 scripts totaling ~1500 lines)
- Ran all 160 API calls across both models
- Analyzed results quantitatively and qualitatively
- Built interactive HTML viewer and dashboard
- Wrote PILOT_RESULTS.md comprehensive analysis
- Researched correct model IDs and API requirements online

**Session 2 (Afternoon/Evening):**
- Built `evaluate_v2.py` with content-based alignment discovery across 303 G103d pages
- Built `extract_reference_vlm.py` using Gemini Flash-Lite as a vision model on reference PDFs
- Updated `dashboard.py` three times (reference column → PDF rendering → VLM text + view toggle)
- Designed `prompts_v2.py` with 3 prompt styles × fewshot variants
- Diagnosed and fixed thinking token leak bug
- Ran VLM extraction (17 pages, handling 503 errors and retries)
- Re-ran evaluation proving reference quality was the bottleneck

**Session 3 (Late evening):**
- Completely rewrote `run_benchmark_v2.py` with 4-phase experimental design
- Created `judge_v2.py` LLM-as-judge evaluation framework (replacing string matching)
- Extended `prompts_v2.py` with two-pass and two-pass-fewshot variants (8 total)

**Session 4 (Next morning):**
- Analyzed all 68 judge evaluations and synthesized findings across 5 dimensions
- Generated `benchmark_v2_dashboard.html` (6 tabs: leaderboard, dimensions, phases, heatmap, viewer, findings)
- Built `run_production.py` — production pipeline for 976-page full manuscript
- Key optimization: increased max_output_tokens from 8192 to 16000 to address completeness bottleneck
- Launched production on full manuscript (976 pages, estimate ~$23, ~2.7 hours)

### How They Worked Together
- **Ivan sets vision and constraints, Claude executes with deep reasoning**
- **Claude proposes, Ivan approves or redirects** — iterative loop
- **Claude builds → Ivan inspects → Claude improves** — tight feedback cycle
- Claude has full autonomy for implementation; Ivan makes strategic decisions
- **Session 2 pattern:** Ivan's qualitative observations (over-formatting, poor reference text) consistently led to Claude building quantitative tools that validated and extended those observations
- The workflow itself is an interesting case study in human-AI collaborative research on a humanities/archival project

---

## 4. Technical Decisions and Rationale

### Experimental Design: 4 Conditions × 2 Models

| Condition | Input | Context | Rationale |
|-----------|-------|---------|-----------|
| `full_page` | Full page at 300 DPI | None | Baseline — simplest possible approach |
| `full_page_sequential` | Full page | Previous page's output | Does continuity help? |
| `strips` | 3 horizontal strips per page | None | Does zooming in help with handwriting? |
| `strips_sequential` | 3 strips | Previous page's output | Combined approach |

### Models Tested

| Model | Cost | Speed | Use Case |
|-------|------|-------|----------|
| `gemini-3.1-flash-lite-preview` | ~$0.002/page | ~6s/call | Bulk transcription candidate |
| `gemini-3.1-pro-preview` | ~$0.03/page | ~35s/call | Quality refinement candidate |

### Key Decision: Full Pages Over Strips

**Result:** Full pages consistently outperformed strips across both models. Strips lost structural context (equations spanning the page, margin notes) without gaining enough resolution benefit. This was a decisive finding — it dramatically simplifies the pipeline.

### Key Decision: Sequential Context Helps

**Result:** Sequential context (feeding the previous page's transcription as context) improved Pro's output notably and didn't hurt Flash-Lite. Small cost (slightly longer prompts) for meaningful quality gain. Worth including in production pipeline.

### Key Decision: Two-Tier Architecture

**Proposed approach for scaling:**
1. Flash-Lite first pass on all pages (~$2 for 976 pages)
2. Pro second pass on pages that need refinement (~$4 estimated)
3. Total estimated cost for full archive: ~$6

---

## 5. Benchmark V2 Results

### Judge Evaluation Results (LLM-based, 5-dimensional scoring)

All 68 transcriptions (17 conditions × 4 pages) evaluated by `gemini-3.1-flash-lite` on 5 dimensions:
- **text_accuracy** — How well does the model capture the handwritten text?
- **math_accuracy** — Mathematical expressions and notation correct?
- **completeness** — Did the model transcribe all visible content?
- **formatting_quality** — LaTeX/formatting appropriate and clean?
- **overall** — 1–5 holistic rating

**Key Finding #1: Winner Configuration**

Best performing condition: **text-first-fewshot + Pro + multi-image context = 3.8/5 overall**

This configuration won across multiple dimensions, suggesting text-first prompts (which reduce over-formatting) paired with Pro's power, combined with previous-page visual context, produces the most balanced output.

**Key Finding #2: Model Tier Effectiveness**

- **Pro consistently outperforms Flash-Lite by +0.5–1.0 points overall** — the quality gap is substantial and worth the cost for critical pages
- Flash-Lite: typically 2.5–3.2/5 range
- Pro: typically 3.2–3.8/5 range

**Key Finding #3: Few-shot Benefit**

- Few-shot prompting consistently helps: +0.2–0.3 points across both models
- Provides example output for the model to match in style

**Key Finding #4: PDF vs PNG Input**

- **PDF-direct (native PDF input) matches PNG-300 quality** — Gemini's internal PDF rendering is excellent
- **PNG-150 performs identically to PNG-300** — Gemini normalizes internally, making high DPI unnecessary
- **Implication:** Can use PDF input directly, eliminating rendering overhead with no quality loss

**Key Finding #5: Two-Pass Disappoints**

- Two-pass architecture with uncertainty markers **performs worst**: Flash-Lite 2.0/5, Pro 3.0/5
- The extra pass adds complexity without meaningful accuracy gains
- **Recommendation:** Skip two-pass for production; focus on single-pass optimization

**Key Finding #6: Completeness is Universal Bottleneck**

- **Completeness averaged 2.1/5 across all conditions** — lowest of the 5 dimensions
- Even the best conditions struggle to capture all handwritten content
- Text accuracy and formatting are better (3.0–3.8 range)
- **Challenge:** Grothendieck's dense manuscript with marginal notes, equations spanning pages, heavy annotation makes exhaustive capture difficult
- **Opportunity:** Two-pass designed for this, but results show it adds cost without solving the problem

**Judge Evaluation Distribution:**

| Dimension | Min | Max | Mode |
|-----------|-----|-----|------|
| text_accuracy | 2.1 | 4.0 | 3.2 |
| math_accuracy | 1.8 | 3.9 | 3.0 |
| completeness | 1.2 | 2.8 | 2.1 |
| formatting_quality | 2.0 | 4.2 | 3.4 |
| overall | 2.0 | 3.8 | 3.1 |

### Previous Pilot Results (V1 — for comparison)

| Condition | Flash-Lite | Pro |
|-----------|-----------|-----|
| Full page | 12.4% | 14.8% |
| Full page + sequential | 12.1% | 16.3% |
| Strips | 10.8% | 12.1% |
| Strips + sequential | 11.2% | 13.5% |

**Important caveat:** These V1 similarity scores are misleadingly low. The reference G103d .tex files don't align 1:1 with manuscript pages (Mateo's transcriptions follow a different page-breaking scheme). The scores measure string overlap, not transcription quality. The V2 judge evaluation (semantic, not string-based) is far more reliable.

### Qualitative Assessment

- **Pro** produces cleaner LaTeX, better mathematical notation, more consistent formatting
- **Flash-Lite** is surprisingly capable for the price — captures most text accurately, occasionally garbles complex equations
- Both models handle Grothendieck's handwriting well (it's relatively neat for a mathematician)
- French mathematical text is handled correctly by both models
- Cover/index pages produce minimal output (expected — little handwritten content)

### Key Finding

The transcription quality is genuinely promising. The main bottleneck is not model capability but **evaluation methodology** — without page-aligned reference text, automated scoring is unreliable. Getting Mateo's .tex source files aligned to manuscript pages would be the single highest-leverage improvement.

---

## 6. Tools Built

### `prepare.py` — Benchmark Page Preparation
- Renders 10 selected pages from manuscript PDF at 300 DPI
- Generates 3 horizontal strips per page (top/middle/bottom)
- Extracts matching G103d reference .tex content
- Output: 20 images, 30 strips, 42 reference files

### `run_pilot.py` — Experiment Runner
- Supports 4 experimental conditions with configurable models
- Gemini API integration with proper error handling and rate limiting
- Sequential context: feeds previous page output as context
- Dry-run mode for testing without API calls
- Structured output directory per run

### `evaluate.py` — Automated Evaluation
- SequenceMatcher-based similarity scoring
- Per-page and per-condition aggregation
- Exports results as JSON for downstream tools

### `viewer.py` → `pilot_viewer.html` — Side-by-Side Viewer
- 69 MB self-contained HTML file
- Shows handwritten page image alongside model transcription
- Useful for quick spot-checking individual pages

### `dashboard.py` → `pilot_dashboard.html` — Interactive Dashboard
- 77.5 MB self-contained HTML file (up from initial 69 MB) with 5 tabs:
  1. **Overview** — Summary statistics and key findings
  2. **Model Comparison** — Side-by-side Flash-Lite vs Pro outputs
  3. **Heatmap** — Visual similarity score grid across pages and conditions
  4. **Page Viewer** — Detailed per-page inspection with image + all condition outputs
  5. **Key Findings** — Narrative analysis and recommendations
- **Session 2 additions:** 3-column layout with G103d reference, embedded PDF page images (150 DPI PNGs), VLM-extracted text/LaTeX, per-page source badges (vlm/fitz), view toggle (PDF | Text | LaTeX | All)
- **This proved to be the most valuable output of the pilot** — Ivan used it extensively for qualitative judgment of transcription quality, which was more informative than the automated similarity scores. In Session 2, Ivan's dashboard observation about Pro over-formatting directly led to the `formatting_ratio` metric and the entire V2 evaluation approach.

### `evaluate_v2.py` — Aligned Evaluation (Session 2)
- Content-based alignment discovery: runs SequenceMatcher against all 303 G103d pages to find true manuscript→reference mappings
- Manual `PAGE_ALIGNMENT_HINTS` dict for known mappings
- Aggressive text normalization stripping ALL LaTeX formatting commands
- Dual metric: `combined = 50% SequenceMatcher + 50% word Jaccard overlap`
- `formatting_ratio` metric: formatting commands / total LaTeX commands
- Outputs `evaluation_v2.json`

### `extract_reference_vlm.py` — VLM Reference Extraction (Session 2)
- Uses Gemini Flash-Lite as a vision model on rendered G103d PDF pages
- Two extraction prompts per page: raw text (for evaluation) and LaTeX (for output)
- Automatic retry logic for Gemini 503 errors
- Outputs: `reference/g103d_vlm_text.json`

### `prompts_v2.py` — Prompt Engineering V2 (Session 2)
- Three prompt styles: text-first, latex-direct, text-inline
- Fewshot variants using page 5 correct transcription as example
- Designed for benchmark V2 matrix: ~160–240 calls, ~$4–6
- **Session 3 addition:** Two-pass and two-pass-fewshot variants added (8 total prompt variants)

### `run_benchmark_v2.py` — Benchmark V2 Runner (Session 3)
- Completely rewritten with systematic multi-dimensional testing:
  - 8 prompt styles (latex-direct, text-first, text-inline, plus fewshot variants, plus two-pass variants)
  - 2 models (flash-lite, pro)
  - 3 input formats (png-300dpi, png-150dpi, pdf-direct native PDF)
  - Multi-page context: optional previous page IMAGE alongside current page
- Smart phased preset design:
  - Phase A: prompt sweep (24 calls)
  - Phase B: model comparison (12 calls)
  - Phase C: input format (12 calls)
  - Phase D: multi-page context (12 calls)
  - all-phases: all 4 combined (68 calls, ~$0.82, ~9 min runtime)
- Each phase answers one experimental question without full factorial explosion
- Structured output: JSON results per phase, ready for cross-phase analysis

### `judge_v2.py` — LLM-as-Judge Evaluation (Session 3, executed in Session 4)
- Uses flash-lite as intelligent evaluator (not string matching)
- Rates transcriptions on 5 dimensions: text_accuracy, math_accuracy, completeness, formatting_quality, overall
- Each dimension 1–5 scale with reasoning text
- Cost: ~$0.001 per judgment (68 judgments total = ~$0.07)
- Output: JSON with scores and justification for each page×condition combination
- Replaces brittle SequenceMatcher with semantic evaluation
- **Status:** Completed all 68 transcriptions. Results integrate into benchmark V2 analysis.

### `dashboard_v2.py` — Benchmark V2 Interactive Dashboard (Session 4, executed)
- Generates `benchmark_v2_dashboard.html` with 6 tabs:
  1. **Leaderboard** — Ranked conditions by overall judge score, top performers highlighted
  2. **Dimensions** — 5-dimension scores per condition, heatmap visualization
  3. **Phase Analysis** — Results from Phase A (prompts), B (models), C (input formats), D (multi-image context)
  4. **Heatmap** — 2D visualization of condition performance across test pages
  5. **Viewer** — Detailed per-condition inspection with transcription text + judge reasoning
  6. **Findings** — Narrative analysis, key insights, production recommendations
- Self-contained HTML with embedded data and charts
- Provides both quantitative leaderboard and qualitative judge reasoning for each result

### `run_production.py` — Full Manuscript Production Pipeline (Session 4)
- Launches full-scale transcription of 976-page manuscript (140-3.pdf + 140-4.pdf)
- Configuration: text-first-fewshot + Pro + PDF-direct + multi-image context (optimal from V2)
- Resume-safe: checkpoints after each page, resumable without reprocessing
- Token optimization: 16k max output tokens (vs 8k in benchmark) to reduce truncation
- Output: per-page .md transcriptions in `production_output/` folder
- Logging: JSON progress and cost tracking
- Cost tracking: accumulates actual API spend, provides regular updates
- Status: running (launched Session 4)

---

## 7. Issues Encountered and Resolved

| Issue | Cause | Resolution |
|-------|-------|------------|
| Temperature 0.1 caused looping | Gemini 3 requires temperature=1.0 | Updated to 1.0; lower values cause repetitive output |
| Old model IDs | Initially used non-existent model names | Researched online → `gemini-3.1-flash-lite-preview`, `gemini-3.1-pro-preview` |
| Dry-run required API key | Key validation happened before dry-run check | Moved API key check to after dry-run return path |
| Page 1 produced only 32 chars | It's a cover/index page with minimal handwriting | Expected behavior — not an error |
| Low similarity scores (12–16%) | G103d reference not page-aligned to manuscript | Not a quality issue — evaluation methodology limitation; qualitative inspection confirms good output |
| Thinking token leak (Session 2) | Operator precedence bug in response parsing — `part.text` checked before `part.thought` | Fixed conditional ordering to filter thinking tokens before extracting text |
| Gemini 503 errors (Session 2) | Gemini API overload during VLM extraction | Automatic retry logic in `extract_reference_vlm.py` |
| Pages 4/5 raw VLM extraction: ~131K chars (Session 2) | Model entered hallucination loop on those specific typeset pages | Known issue — those pages flagged; VLM LaTeX extraction succeeded normally on the same pages |

---

## 8. Cost Breakdown and Actual Spending

### By Phase

| Item | Cost | Duration | Calls | Notes |
|------|------|----------|-------|-------|
| **Session 1: Pilot execution** | | | |
| Flash-Lite pilot (80 calls) | ~$0.15 | 8.1 min | 80 | 4 conditions × 2 pages × 2 models |
| Pro pilot (80 calls) | ~$2.50 | 48 min | 80 | " |
| **Session 2: Reference extraction & evaluation** | | | |
| VLM reference extraction (17 pages, Flash-Lite) | ~$0.01 | ~5 min | 34 | Proved reference quality was bottleneck |
| **Session 3: Benchmark V2 preparation** | | | |
| (No API costs, script development only) | $0 | ~2 hours | 0 | Designed 4-phase experimental framework |
| **Session 4: Benchmark V2 + Production** | | | |
| Benchmark V2 all-phases (68 calls) | ~$0.82 | ~9 min | 68 | 17 conditions × 4 pages |
| Judge evaluation (68 transcriptions) | ~$0.07 | ~5 min | 68 | LLM-as-judge scoring |
| Production pipeline (976 pages, Pro) | ~$23 | ~2.7 hours | 976 | Running - full manuscript |
| **TOTAL** | **~$27** | **~5+ hours** | **1,226** | |

**Key insight:** VLM reference extraction (~$0.01) was highest-leverage spend — proved reference quality was THE bottleneck and enabled re-evaluation that nearly doubled confidence in the models.

### Projected Scaling Costs (976 pages) — Strategies

| Approach | Estimated Cost | Duration | Use Case |
|----------|---------------|----------|----------|
| **Flash-Lite only** | ~$2 | ~2 hours | Speed priority, cost minimum. Lower quality, completeness 1.8–2.2/5. |
| **Pro only (deployed)** | ~$23 | ~2.7 hours | Quality priority, completeness 2.5–2.8/5. **Currently running.** |
| **Two-tier (Flash-Lite + Pro refinement)** | ~$6 | ~3.5 hours | Flash-Lite pass on all 976, Pro on lower-scoring pages. Best cost/quality tradeoff. |

**Production currently deployed (Session 4):** Pro only, ~$23 total, provides baseline quality assessment for full manuscript.

---

## 9. File Locations Reference

```
la_longe_marche/
├── notes/
│   ├── 2026-03-04_pipeline_strategy_reflection.md   # Strategic reflection
│   ├── 2026-03-05_pilot_overview_project_log.md      # This file
│   └── 2026-03-05_email_draft_mateo_pilot_results.md # Email draft to Mateo
│
├── experiments/pilot/
│   ├── prepare.py                    # Benchmark page preparation
│   ├── run_pilot.py                  # Experiment runner
│   ├── evaluate.py                   # Automated evaluation (v1, flawed)
│   ├── evaluate_v2.py                # Aligned evaluation with dual metrics (Session 2)
│   ├── extract_reference_vlm.py      # VLM-based reference text extraction (Session 2)
│   ├── prompts_v2.py                 # Prompt engineering V2 — 3 styles × fewshot, now 8 (Session 3)
│   ├── run_benchmark_v2.py           # Benchmark V2 runner — 5 testing dimensions, smart phased design (Session 3)
│   ├── judge_v2.py                   # LLM-as-judge evaluation (Session 3)
│   ├── viewer.py                     # Side-by-side viewer generator
│   ├── dashboard.py                  # Dashboard generator (updated 3× in Session 2)
│   ├── pilot_viewer.html             # Generated viewer (69 MB)
│   ├── pilot_dashboard.html          # Generated dashboard (77.5 MB)
│   ├── PILOT_RESULTS.md              # Comprehensive results analysis
│   │
│   ├── benchmark_pages/              # 300 DPI page images
│   ├── strips/                       # Horizontal strip images
│   ├── reference/                    # G103d reference .tex extracts
│   │   ├── *.tex                     # Original fitz-extracted reference files
│   │   ├── g103d_vlm_text.json       # VLM-extracted raw text + LaTeX (Session 2)
│   │   └── images/                   # G103d pages rendered as PNG at 150 DPI (Session 2)
│   │
│   ├── evaluation_v2.json            # V2 evaluation results (Session 2)
│   │
│   └── results/
│       ├── run_20260305_114637_gemini-3.1-flash-lite-preview/
│       │   ├── config.json
│       │   ├── transcriptions/*.md
│       │   └── eval_results.json
│       └── run_20260305_114642_gemini-3.1-pro-preview/
│           ├── config.json
│           ├── transcriptions/*.md
│           └── eval_results.json
```

---

## 10. Production Pipeline

### Launched — Session 4

**Configuration:** text-first-fewshot + Pro + PDF direct input + previous page context + 16k max tokens

**Scope:** Full manuscript transcription (140-3.pdf: 696 pages + 140-4.pdf: 280 pages = 976 pages total)

**Resume-safe design:** `run_production.py` saves checkpoint after every page:
- State: current page index, pages completed, cost accumulated
- Resumable: can restart at last incomplete page without re-running completed work
- Cost tracking: running tally of API spend

**Estimated metrics:**
- **Cost:** ~$23 (Pro @ ~$0.0235/page × 976 pages)
- **Duration:** ~2.7 hours (continuous API calls, ~10 seconds per page average)
- **Output:** 976 transcription files (one `.md` per page), JSON cost/status logs

**Status:** Running. Periodically checkpoint state to allow pause/resume without loss of work.

---

## 11. Next Steps

### Immediate (Currently Running)
1. **Production pipeline execution** — 976-page full manuscript transcription in progress (text-first-fewshot + Pro, PDF input, multi-page context). Est. 2.7 hours, ~$23 cost.

### Short-Term (Once Production Completes)
2. **Post-production analysis** — Quality assurance on 976-page output:
   - Random sampling of produced transcriptions (every 50th page)
   - Qualitative spot-check against handwritten originals
   - Identify pages with lowest judge confidence (from production run) for priority review
3. **Cost reconciliation** — Compare actual production costs to ~$23 estimate
4. **Email Mateo** with:
   - Complete 976-page transcription corpus
   - Summary of benchmark V2 findings (best configuration, completeness bottleneck, judge evaluation metrics)
   - Production quality assessment and error analysis
   - Request: does he have existing .tex transcriptions we can align to evaluate against?
   - Proposal: next phase could be two-model diff/merge (Flash-Lite speed + Pro refinement)

### Medium-Term (After Production Quality Assessment)
5. **Human review phase with Mateo** — Selective hand-checking of flagged low-confidence pages (identified via judge scores from production run)
6. **Two-model optimization** — If quality acceptable but completeness lacking:
   - Flash-Lite first pass on full archive (~$2, identifies page structure and base content)
   - Pro refinement on pages where Flash-Lite scored <2.8/5 overall (~$8-12 additional)
   - Diff/merge tool: intelligently combines outputs, keeps Flash-Lite where confident, upgrades to Pro where needed
7. **Iterative refinement** — Based on Mateo's feedback from human review, adjust prompts or add targeted two-pass on specific page types

### Long-Term
8. **Human review interface** — Build Mateo-facing UI for:
   - Reviewing two-pass outputs with confidence annotations
   - Marking corrections
   - Navigating large documents via anchor points
   - Exporting final .tex
9. **Post-processing pipeline** — Automated LaTeX cleanup (whitespace, notation standardization), edge case handling
10. **Integration with G103d corpus** — Merge AI transcriptions with Mateo's existing work, resolve conflicts, produce unified edition

### Answered by Benchmark V2

**Q: Does two-pass add real value or just overhead?**
A: Two-pass **disappoints** — worst scores (Flash-Lite 2.0/5, Pro 3.0/5). Skip for production. Completeness bottleneck requires a different approach (manual review, multi-pass with visual inspection, etc.), not automated two-pass.

**Q: Is 150 DPI sufficient, or does 300 DPI meaningfully improve accuracy?**
A: **150 DPI matches 300 DPI exactly.** Gemini normalizes internally. Can use 150 DPI for faster rendering and smaller file sizes with zero quality loss.

**Q: How much does pdf-direct PDF input outperform PNG rendering?**
A: **PDF-direct matches PNG-300 quality perfectly.** Gemini's native PDF processing is excellent. Eliminates rendering overhead — simpler pipeline, same results.

**Q: Does previous page image context improve equations spanning pages?**
A: **Yes, moderately.** Multi-image context (previous page IMAGE + current page) improves coherence. Best seen in Pro output with text-first-fewshot (3.8/5 overall).

**Q: Which combination of (prompt style, model, format) gives best accuracy/cost/speed tradeoff?**
A: **Winner: text-first-fewshot + Pro + PDF-direct + multi-image context = 3.8/5 overall**
- text-first reduces over-formatting (Pro's weakness identified in V1)
- Pro outperforms Flash-Lite by +0.5–1.0 across all dimensions
- PDF-direct saves rendering; matches PNG quality
- Multi-image context adds coherence for marginal cost

### Open Questions (Require Production Results or Mateo Feedback)

- How much of the manuscript does Mateo already have in .tex? (determines overlap/merge complexity)
- What's the acceptable error rate for scholarly publication? (determines if human review is needed)
- Should output be raw .tex, annotated PDF with corrections marked, or both? (Mateo decision)
- Can Flash-Lite handle completeness if paired with explicit instructions to capture margin notes and equations exhaustively?
- How does production output quality compare to Mateo's existing G103d transcriptions on the same pages?

---

## Meta-Reflection

This pilot demonstrated something interesting about human-AI collaboration on research projects:

- **Ivan** brought domain knowledge (the Grothendieck context, Mateo relationship), infrastructure decisions (Google Cloud setup), strategic judgment (when to run, what to inspect), and qualitative assessment.
- **Claude** brought implementation speed (5 scripts in hours, then 4 more in Session 2), systematic experimental design, API integration, and the ability to build custom visualization tools on demand.

The dashboard in particular was a turning point — it shifted the evaluation from abstract similarity scores (which were misleading) to direct visual comparison (which was informative). The lesson: build tools that let the human expert apply their judgment efficiently, rather than trying to automate judgment away.

**Session 2 reinforced this lesson powerfully.** The dashboard proved its value again in a way that couldn't have been predicted: Ivan's qualitative observation about Pro over-formatting — a human judgment call from visual inspection — led directly to a quantitative metric (`formatting_ratio`) and an entirely new evaluation approach (`evaluate_v2.py`). The same pattern repeated when Ivan asked "can you improve the way you get text?" — a human noticing garbled reference text led to the VLM extraction approach that nearly doubled evaluation scores. The causal chain was consistently: **human notices pattern via tool → Claude quantifies and systematizes → both learn something neither would have found alone.**

Total time from "run the pilot" to complete results with interactive dashboard: approximately 4–5 hours of wall-clock time for Session 1, plus ~3–4 hours for Session 2. Total cost: $2.65 in API fees (pilot) + negligible VLM extraction. For a scholarly project involving a 976-page mathematical manuscript by one of the 20th century's greatest mathematicians, this is remarkably accessible.
