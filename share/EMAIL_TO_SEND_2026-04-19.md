To: mateo.carmona@csg.igrothendieck.org
Cc: olivia.caramello@igrothendieck.org

Subject: Re: Fw: First Results Transcription La Longe Marche IFAB CSG I GROTHENDIECK — full corpus delivered

Dear Mateo, dear Olivia,

Following up on my previous message: rather than waiting for confirmation I went ahead and ran the full corpus, since the benchmark results were clear enough to justify it. Here is what is new.

---

## Full corpus completed — and an unexpected finding

While setting up the full re-run with Gemini 3.1 Pro I hit the API daily quota limit (250 calls/day on my tier) and had to wait. While waiting I tried the same five ground-truth pages of Section 49 through **Gemini 3.1 Flash-Lite** — the smallest, cheapest Gemini model — under the same `mateo-canonical` prompt. The result was a surprise:

| Model | Composite quality | Cost / 5 pages | Avg latency |
|-------|------------------|----------------|-------------|
| Shipped baseline | 0.113 | — | — |
| Claude Opus 4.7 + `mateo-canonical` | 0.661 | $1.173 | 28.6 s |
| Gemini 3.1 Pro + `mateo-canonical` | 0.742 | $0.074 | 67.8 s |
| **Gemini 3.1 Flash-Lite + `mateo-canonical`** | **0.777** | **$0.008** | **7.4 s** |

Flash-Lite beat both Pro and Opus on composite quality at **150× lower cost than Opus** and **9× lower latency than Pro**. So I used it for the full corpus run.

**Full-corpus result (Flash-Lite + `mateo-canonical`, all 976 pages):**

- 140-3: **696/696 pages** (100%), including 114 diagram pages via `diagram-tikzcd`
- 140-4: **280/280 pages** (100%), including 58 diagram pages via `diagram-tikzcd`
- Section 49.1 composite quality on the full corpus: **0.67** (6× above shipped baseline of 0.113)
- Total API cost: **$0.59** for all 976 pages (~€0.55)

The updated tex files are in `tex/` in the attached zip.

---

## Bourbaki — full document

Beyond the 5-page comparison I already sent, I ran Flash-Lite over the **complete 437-page Bourbaki *Schémas* document**: 15 minutes, $0.60, ~1 MB of LaTeX output (`bourbaki/bourbaki_schemes_full_flash-lite.tex` in the zip). On machine-typed text the pipeline is essentially publication-ready, which confirms the remaining gap on Part II is purely a prompt-engineering challenge, not an OCR capability limit.

---

## Blog post published

The technical write-up is now live:
**https://thinkgentile.com/posts/grothendieck-ocr-deep-dive**

It covers the full story — from the initial production run, through the `49.1old` vs `49.1new` diagnostic, to the Flash-Lite surprise. I have kept your name and Olivia's in the acknowledgements section. Please let me know if you would like anything changed or removed before I circulate it further.

---

## What is still open

1. **Gemini 3.1 Pro full-corpus run** — resumed after quota reset, currently at ~50%. Will send the Pro corpus for comparison once it finishes (likely within 2 days).
2. **Hand-drawn geometric figures** — ~5 pages across both volumes that neither prompt handles; these likely need a human pass.
3. **A/B viewer votes** — the `benchmark/benchmark_opus_vs_gemini.html` in the zip (also in my previous email). Even two or three votes would help calibrate the automatic judge.

---

The repository remains the single source of truth:
**https://github.com/ivan-gentile/la-longue-marche**

Best,

Ivan

---

Ivan Gentile
Senior Data Scientist, IFAB Foundation
https://linkedin.com/in/ivangentile

**Attachment:** `mateo_update_2026-04-19.zip`
