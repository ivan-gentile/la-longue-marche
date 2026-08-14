# Draft reply to Mateo — 2026-08-14

Status: DRAFT, not sent. Reply to Mateo's email of 2026-08-09
("Re: Observations on Transcription Gaps"). Cc: Olivia Caramello.

This draft absorbs the never-sent 2026-07-05 delta (root-cause of the
two anomalies, issue form, coverage manifests) — Mateo has not seen any
of that content.

Pre-send checklist (every claim must be live before sending):
- [ ] Resume run finished: 140-3 → 696/696, 140-4 → 280/280
      (36 pages: 140-3 failed 571/611/652; 140-4 six failed + 27 never run)
- [ ] `finalize_mateo_canonical.py` + `make_coverage.py` re-run,
      committed AND pushed (Mateo reads GitHub, not our working tree)
- [ ] U46 Varieties run complete; tex filename below matches reality
- [ ] Volunteer paragraph: pick variant A or B — Ivan's decision
- [ ] Optional: split Bourbaki tex into two files matching U86u1/U86u2

---

Subject: Re: Observations on Transcription Gaps

Dear Mateo,

Thank you for the detailed reply — no apology at all needed for the
timing. It is very good news that Section 49 is moving; a first draft
from your hand is exactly what the research side of this work has been
waiting for, and I am happy to treat the points we exchanged as a
working framework rather than a fixed organisation.

[VARIANT A — formalise] On the framework: I would be glad to formalise
this as a CSG volunteer, and I will fill in the form on the
collaborations page this week, with a short description of the ongoing
project. To keep things clean I would join as an individual — my
involvement here is personal and distinct from my employer. And
understood, of course, on the other point: nothing public that implies
CSG involvement or representation without discussing it with you first.

[VARIANT B — stay informal] On the framework: for the moment I would
prefer to continue in the informal setting we have used so far, exactly
under the understanding you describe — anything that could imply CSG
involvement or representation will be discussed and confirmed with you
first. I remain open to the volunteer framework as the work matures.

While waiting for your draft I closed the pending items on my side, so
the material you are working from is current:

- The higher-fidelity "canonical" transcription (Gemini Pro) is now
  complete for both volumes — 696/696 pages of 140-3 and 280/280 of
  140-4 — including all of Section 49. Since you are drafting Section
  49 right now, `tex_output/la_longue_marche_140-3_mateo-canonical.tex`
  is the file I would draft from: on the corrected 49.1 sample you
  shared, it stays noticeably closer to the original wording than the
  fast-model draft (far fewer silent rewordings; measurements in
  `evaluation/section-49/`). Every file in `tex_output/` also carries a
  page-coverage manifest (`tex_output/COVERAGE.md`), so a gap can never
  again be something you have to discover by scrolling.

- Both anomalies you reported earlier are root-caused. The 140-3 pages
  105–175 omission was a delivery fault of mine: a run died on an API
  daily quota and the later backfill was never published — fixed, and
  the manifest now makes that class of accident visible immediately.
  The Préschémas gaps were a structural defect of the "whole document
  at once" mode, which silently skipped about 70 of the 437 pages and
  numbered the rest by the typescript's own chapter-restarting page
  numbers. I re-ran it page by page:
  `tex_output/bourbaki_schemes_pages_flash-lite.tex`, all 437 pages,
  each under a marker the pipeline writes from the PDF position. I also
  verified that the source I used is exactly the two files you linked —
  pages 1–210 correspond to U86u1 and 211–437 to U86u2 (the scans are
  identical) — and I can split the file in two to match them if that is
  more convenient for your review.

- The structured format you mention already exists in the repository as
  the "Transcription anomaly" issue form (error type, page, line,
  manuscript reading vs transcription reading, severity):
  https://github.com/ivan-gentile/la-longue-marche/issues/new/choose —
  plus an equivalent CSV template in `evaluation/section-49/` if you
  prefer working offline. Both are ready whenever your Section 49 draft
  is, and whatever you file will feed directly into the evaluation that
  drives the next round of pipeline changes.

Varieties is a very good idea — a nice intermediate case: typescript
body with the mathematical script letters written in by hand, harder
than Préschémas, far easier than La Longue Marche. I ran it through the
same page-by-page pipeline with the coverage census: the preliminary
draft of all 100 pages is in the repository as
`tex_output/varietes_categories_U46.tex`, with its coverage declared in
the manifest. As always, it is a working draft and every line needs
your verification.

One small practical point for when your draft arrives: I place the §49
heading on PDF page 495 of 140-3 and read the section through page 696,
while you wrote pp. 494–695 — almost certainly just a
counting-convention difference, but worth pinning down together so that
page references in anomaly reports line up exactly.

Thank you again for the care in your reply. The distinction you draw
between facilitating access and the research question proper is one I
will keep as the organising principle. Looking forward to the Section
49 draft.

Best,
Ivan
