# Draft follow-up to Mateo — 2026-07-05

Status: DRAFT, not sent. Tight delta on the message already sent on
July 3; send once comfortable with the content. All claims below are
in the repository (tag `delivery-2026-07-05` and later commits).

---

Subject: Re: Observations on Transcription Gaps

Dear Mateo,

A quick update while I wait for the documents and your notes — I went
through the two anomalies you reported and both are now root-caused,
and the first one is fixed.

**The omission in La Longue Marche (140-3, pages 105–175).** The April
run of the higher-quality transcription died mid-volume on an API
daily-quota limit, and a later run that filled those pages was never
published — my mistake in the delivery process, not a model error. The
file on GitHub now contains 503 of 696 pages for 140-3 and 236 of 280
for 140-4, including the whole range you flagged. More importantly,
every file in `tex_output/` now ships with a coverage manifest
(`tex_output/COVERAGE.md`) that states exactly which pages carry a real
transcription, so a gap can never again be something you have to
discover by scrolling.

**The unusual gaps in the Préschémas.** These turned out to be a
structural defect of the "whole document at once" mode I used for that
typescript: it silently skipped about 70 of the 437 pages and numbered
the rest by the page numbers printed on the typescript itself (which
restart per chapter), so the file cannot be navigated against the
scans. The full analysis is in `experiments/bourbaki/GAPS.md`. I will
re-run it page-by-page — the mode used for La Longue Marche, which
cannot skip pages silently — and deliver a page-aligned replacement.

**Filing anomalies.** The repository now has a structured issue form —
"Transcription anomaly" under
https://github.com/ivan-gentile/la-longue-marche/issues/new/choose —
with exactly the fields we discussed (error type, page, line, what the
manuscript says vs what the transcription says). If you prefer working
offline, `evaluation/section-49/anomalies_template.csv` has the same
columns and a filled CSV by email works just as well; both feed the
evaluation directly.

**Section 49.** I extended the evaluation beyond LaTeX style to
content fidelity (omissions, rewordings, insertions, measured by
alignment against your corrected 49.1). The numbers confirm your
impressions quantitatively: the fast model used for the full draft
omits or rewrites roughly half of the content on that section, while
Gemini Pro is markedly more faithful — so the Pro re-run will cover
Section 49 (pages 495–696 of 140-3) as its next priority, and that is
the version we should use for the research track. The working notes
for this are in `evaluation/section-49/`.

None of this replaces your line-by-line verification, of course — it
is all aimed at making that verification less painful and at never
wasting your time on gaps of my making.

Best,
Ivan
