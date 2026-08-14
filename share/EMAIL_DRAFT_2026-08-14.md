# Draft reply to Mateo — 2026-08-14

Status: DRAFT, not sent. Reply to Mateo's email of 2026-08-09
("Re: Observations on Transcription Gaps"). Cc: Olivia Caramello.

This draft absorbs the never-sent 2026-07-05 delta (root cause of the
two anomalies, issue form, coverage manifests) — Mateo has seen none of
that content.

Open decision for Ivan: the volunteer paragraph has two variants (A =
apply to the CSG, B = stay informal). Pick one and delete the other
before sending. Everything else below is live on GitHub as of commit
`09513c7` and the Variétés commit that follows it.

---

Subject: Re: Observations on Transcription Gaps

Dear Mateo,

Thank you for the detailed reply — no apology needed for the timing. It
is very good news that Section 49 is advancing; a first draft from your
hand is exactly what the research side of this work has been waiting
for, and I am happy to treat the points we exchanged as a working
framework rather than a fixed organisation of the project.

[VARIANT A — formalise] On the framework: I would be glad to formalise
this as a CSG volunteer, and I will fill in the form on the
collaborations page this week with a description of the ongoing
project. I would join in a personal capacity, distinct from my
employer. And understood on the other point: nothing that implies CSG
involvement or representation will be published without discussing it
with you first.

[VARIANT B — stay informal] On the framework: for the moment I would
prefer to continue in the informal setting we have used so far, under
exactly the understanding you describe — anything that could imply CSG
involvement or representation will be discussed and confirmed with you
first. I remain glad to revisit the volunteer framework as the work
develops.

Since your message I have closed the open items on my side, so that
what you are working from is current and its limitations are stated.

**The canonical transcription is now complete.** The higher-fidelity
Gemini Pro run covers both volumes in full — 696/696 pages of 140-3 and
280/280 of 140-4, Section 49 included. Since you are drafting Section
49 now, `tex_output/la_longue_marche_140-3_mateo-canonical.tex` is the
file I would work from: measured against your corrected 49.1, it stays
markedly closer to the original wording than the fast-model draft
(word-level agreement 0.61 against 0.41, with far fewer silent
rewordings). Every deliverable also carries a page-level coverage
manifest, `tex_output/COVERAGE.md`, so a gap can never again be
something you discover by scrolling into it.

**The two anomalies you reported earlier are both resolved.** The
missing 140-3 pages 105–175 were a delivery failure of mine: a run died
on an API quota limit and the backfill that repaired it was never
published. The Préschémas gaps had a different cause — the
"whole document at once" mode silently skipped about 70 of the 437
pages and numbered the rest by the typescript's own chapter-restarting
page numbers, so the file could not be navigated against the scans.
That document has been re-transcribed page by page, with every marker
written by the pipeline from the PDF position:
`tex_output/bourbaki_schemes_pages_flash-lite.tex`, all 437 pages. I
also confirmed it was made from exactly the scans you linked — pages
1–210 correspond to U86u1 and 211–437 to U86u2 — and I can split it
into two files matching them if that helps your review.

**A defect I found while checking that file, which I want to report to
you directly.** Each page is transcribed with the previous page
attached as visual context, so words broken across a page break can be
resolved. In some cases the model transcribed that context page instead
of the intended one. The result is a page that looks perfectly normal —
no error, no gap, correct page marker — but carries the *previous*
page's text. In the Préschémas file this affected 19 of 437 pages;
for instance the page at PDF position 338 is an English errata sheet
("- II-xxi -", *P. II-104 ter, the cor.2 is incorrect*), but the file
contained a copy of page 337 instead. All 19 have been re-transcribed
and checked against the scans, and the file on GitHub is corrected.

I mention it in this much detail because it is precisely the class of
error your review is meant to catch and mine had not been catching: it
is invisible to any success count. Three things now guard against it —
the page attachments are labelled unambiguously, the pipeline compares
each page against its predecessor and retries when they are suspiciously
alike, and a new audit
(`experiments/pilot/audit_corpus.py` → `CORPUS_AUDIT.md`) scans every
corpus for this and two related silent failures before anything is
shared. All current files pass. La Longue Marche was not affected, and
I verified that specifically.

In the same spirit I corrected the project's cost figures, which were
understated several-fold because the model's internal "thinking" tokens
are billed but were left out of my arithmetic. The corrected figures
are in `experiments/pilot/COSTS.md`. It does not change anything for
you, but the published record should be accurate.

**Varieties.** Thank you for this suggestion — it is a good
intermediate case: typewritten body with the mathematical script
letters added by hand, harder than Préschémas and far easier than La
Longue Marche. It has been transcribed with the same page-by-page,
census-checked pipeline and is in the repository as
`tex_output/varietes_categories_U46.tex`, 100 pages, with its coverage
declared in the manifest. As always it is a working draft and every
line needs your verification.

**Filing anomalies.** The structured format you describe already exists
in the repository as the "Transcription anomaly" issue form — error
type, file, page, line, what the manuscript reads against what the
transcription reads, severity:
https://github.com/ivan-gentile/la-longue-marche/issues/new/choose —
with an equivalent CSV template in `evaluation/section-49/` if you
prefer to work offline. Both are ready whenever your Section 49 draft
reaches that stage, and whatever you file feeds directly into the
evaluation that drives the next round of changes.

One small practical point for when the draft arrives: I place the §49
heading at PDF page 495 of 140-3 and read the section through page 696,
while you cite pp. 494–695 — the same 202-page span, shifted by one, so
almost certainly a difference in counting convention. Worth pinning
down between us so that page references in anomaly reports line up
exactly.

Thank you again for the care in your reply. The distinction you draw
between facilitating access to the material and the research question
proper is one I will keep as the organising principle for this work.
I look forward to the Section 49 draft.

Best,
Ivan
