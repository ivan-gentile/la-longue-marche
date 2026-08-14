# Roadmap

State of the project and prioritized next steps, following the
two-track plan agreed with Mateo (June 2026) and his reply of
2026-08-09. Updated 2026-08-14.

## Where things stand

- **La Longue Marche canonical corpus** (`mateo-canonical`, Gemini 3.1
  Pro — the most faithful model on our ground truth): **complete**,
  696/696 (140-3) and 280/280 (140-4). All of Section 49 (140-3 pages
  495–696) is covered. This is the file Mateo should draft from.
- **La Longue Marche working draft** (`flash-lite-mateo`): complete,
  976/976 pages, superseded by the canonical corpus wherever both
  cover a page. Content fidelity on hard sections is draft-grade: on
  Section 49.1 roughly half the content tokens are omitted or reworded
  (`experiments/pilot/fidelity_49_1.md`).
- **Préschémas / Bourbaki Schémas**: 437/437 pages, page-by-page,
  markers written from the PDF index. Verified to be transcribed from
  exactly the scans Mateo works from (U86u1 = pages 1–210, U86u2 =
  pages 211–437). 19 context-echo pages found and repaired in August
  (`experiments/bourbaki/GAPS.md`).
- **Catégories de variétés (U46)**: 100 pages, page-by-page on Gemini
  Pro — the new document Mateo asked for on 2026-08-09.
- **Coverage transparency**: `tex_output/COVERAGE.md` declares
  page-level coverage of every deliverable, standalone documents
  included (`experiments/pilot/make_coverage.py`).
- **Silent-defect audit**: `experiments/pilot/audit_corpus.py` scans
  every corpus for context echoes, empty successes and distant
  duplicates → `experiments/pilot/CORPUS_AUDIT.md`.
- **Honest cost accounting**: thinking tokens are billed at the output
  rate but were left out of every runner's arithmetic, understating
  published figures several-fold. Fixed at the source and recomputed
  for all runs (`experiments/pilot/COSTS.md`).
- **Anomaly intake**: GitHub issue form ("Transcription anomaly") +
  offline CSV (`evaluation/section-49/anomalies_template.csv`).
- **Evaluation**: style conformance (`diagnose_49_1.py`) + content
  fidelity (`evaluate_fidelity.py`) — a change ships only if it
  improves Section 49 numbers on both dimensions
  (`evaluation/section-49/README.md`).

## Track 1 — preliminary drafts for legible typescripts

1. ~~Re-run Bourbaki Schémas page-by-page~~ — done, and repaired again
   in August after the echo audit.
2. ~~Transcribe *Catégories de variétés* (U46)~~ — done August 2026.
3. Run `audit_corpus.py` as a release gate on every future document
   before it is shared, and re-run flagged pages to convergence.

## Track 2 — Section 49 research loop

4. ~~Backfill the canonical (Pro) run over Section 49~~ — done; the
   canonical corpus now covers both volumes completely.
5. When Mateo's Section 49 draft and anomaly notes arrive: ingest into
   `reference/validation/`, extend `evaluate_fidelity.py --preset`
   beyond 49.1, and profile the error classes per model. Agree the page
   convention first — he cites 140-3 pp. 494–695, our PDF indices are
   495–696.
6. Prompt v3 experiments driven by the fidelity numbers: verbatim
   fidelity contract (no silent normalisation of punctuation or
   wording), margin-note role marking, per-page completeness
   self-check, long-range notation consistency.

## Tooling

7. Side-by-side review interface (scan ↔ transcription, page-synced,
   "report anomaly" button pre-filling the issue form) shipped inside
   delivery zips — scans stay out of the public repo.
8. Bring-your-own-API-key: keys already come from `.env`; document a
   reviewer path to re-run a single page with a private key.
9. Quota-aware runner: the page-by-page runners now abort loudly after
   5 consecutive quota errors and exit non-zero on an incomplete run,
   instead of grinding silently to a "Done" (the April failure mode).
   `run_production.py` still needs the same treatment.

## Publication

10. Methods note (draft in
    `notes/2026-03-05_scientific_article_draft_vlm_math_ocr.md`):
    Section 49 error taxonomy plus the style/fidelity evaluation pair as
    the empirical core. The silent failure classes (context echo,
    quota death, empty successes) and the audit that catches them are
    worth a section of their own. Coordinate with the CSG before
    publishing anything that implies their involvement.

## Framework

11. Decide on Mateo's offer of a formal CSG volunteer collaboration
    (form + CV + project description; draft description ready in
    `share/CSG_VOLUNTEER_PROJECT_DESCRIPTION.md`). This is what would
    unlock working directly on the private main repository.

## Waiting on Mateo

- His Section 49 first draft, "as soon as it reaches a useful stage".
- His anomalies, filed as issues once that draft exists.
- Confirmation of the page-numbering convention for Section 49.
