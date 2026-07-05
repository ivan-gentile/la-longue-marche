# Roadmap

State of the project and prioritized next steps, following the
two-track plan agreed with Mateo (June 2026). Updated 2026-07-05.

## Where things stand

- **La Longue Marche working draft** (`flash-lite-mateo`): complete,
  976/976 pages, ~$1.4 recorded API cost. Content fidelity on hard
  sections is draft-grade: on Section 49.1 roughly half the content
  tokens are omitted or reworded (`experiments/pilot/fidelity_49_1.md`).
- **La Longue Marche canonical re-run** (`mateo-canonical`, Gemini 3.1
  Pro — most faithful model on our ground truth): 503/696 + 236/280
  pages; the gap Mateo reported on 2026-04-30 (140-3 pages 105–175) is
  closed as of `delivery-2026-07-05`. Remaining: 193 + 44 pages,
  limited by the free-tier daily quota (250 requests/day).
- **Préschémas / Bourbaki Schémas**: the whole-document transcription
  has no reliable page alignment and silently dropped ~70 of 437 pages
  (`experiments/bourbaki/GAPS.md`) — this is the root cause of the
  "unusual gaps" Mateo reported. Needs a page-by-page re-run (<$1).
- **Coverage transparency**: every deliverable's page-level coverage is
  declared in `tex_output/COVERAGE.md` (regenerate with
  `experiments/pilot/make_coverage.py`).
- **Anomaly intake**: GitHub issue form ("Transcription anomaly") +
  offline CSV (`evaluation/section-49/anomalies_template.csv`).
- **Evaluation**: style conformance (`diagnose_49_1.py`) + content
  fidelity (`evaluate_fidelity.py`) — a change ships only if it
  improves Section 49 numbers on both dimensions
  (`evaluation/section-49/README.md`).

## Track 1 — preliminary drafts for legible typescripts

1. **Re-run Bourbaki Schémas page-by-page** — *done 2026-07-05*:
   `tex_output/bourbaki_schemes_pages_flash-lite.tex`, 437/437 pages,
   0 errors, ~$0.67 (`experiments/bourbaki/run_bourbaki_pages.py`).
   Census verified: every PDF page has a pipeline-written marker.
2. Apply the same census gate to any future typescript Mateo sends
   (waiting on his Préschémas source scans to confirm we work from the
   same material).

## Track 2 — Section 49 research loop

3. **Backfill the canonical (Pro) run over Section 49 first** — 140-3
   pages 495–696, then the remaining 140-3/140-4 holes. One to two
   free-tier quota days, or minutes on a paid tier.
4. When Mateo's Section 49 corrections and anomaly notes arrive:
   ingest into `reference/validation/`, extend
   `evaluate_fidelity.py --preset` beyond 49.1, and profile the error
   classes per model.
5. Prompt v3 experiments driven by the fidelity numbers: verbatim
   fidelity contract (no silent normalisation of punctuation or
   wording), margin-note role marking, per-page completeness
   self-check, long-range notation consistency.

## Tooling

6. Side-by-side review interface (scan ↔ transcription, page-synced,
   "report anomaly" button pre-filling the issue form) shipped inside
   delivery zips — scans stay out of the public repo.
7. Bring-your-own-API-key: keys already come from `.env`
   (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`); document a reviewer path to
   re-run a single page with a private key.
8. Quota-aware runner: schedule daily batches under the free-tier cap,
   alarm on consecutive-page failure blocks instead of dying silently
   (the April failure mode).

## Publication

9. Methods note (draft exists in `notes/2026-03-05_scientific_article_draft_vlm_math_ocr.md`):
   Section 49 error taxonomy + the style/fidelity evaluation pair as
   the empirical core, as discussed with Mateo.

## Waiting on Mateo

- Source scans for Préschémas and Section 49 (to confirm the exact
  material he reviews).
- His collected anomalies, in any digital form (issue form or CSV
  preferred).
- Preference on public vs private for the next phase (current
  recommendation: keep this public repo, scans stay out of git).
