"""Scan every transcription corpus for defects that no error count reveals.

A page can be recorded as a perfectly ordinary success and still be
unusable. These are the classes seen in this project, each of which put
wrong text in a shipped file at least once:

1. **Context echo** — the model transcribed the previous page (attached
   as visual context) instead of its target, producing a corpus silently
   shifted by one. Compared at *word* level: the first version of this
   check compared raw characters and missed four real echoes whose text
   had merely been re-wrapped (character similarity 0.21-0.71, word
   similarity 0.75-0.96).
2. **Reasoning leakage** — the model's English deliberation ("Let's
   reconsider…", "Ah! It must be…", a stray ``` fence) reaching the
   output instead of, or on top of, the French transcription.
3. **Truncation** — a page ending mid-token, or with unbalanced `$$`,
   leaving math open across a page boundary.
4. **Unbalanced environments** — `\begin{array}` closed by
   `\end{matrix}`, a missing `\end{tikzcd}`: LaTeX that will not compile.
5. **Escaping artifacts** — a literal `\\operatorname` (double
   backslash), which in math mode is a line break followed by the bare
   word "operatorname".
6. **Empty successes** and **distant duplicates**.

Reports only; never modifies a corpus. Pages flagged here are the ones
to re-run or check against the scan.

Usage:
    python experiments/pilot/audit_corpus.py
    python experiments/pilot/audit_corpus.py --threshold 0.8
    python experiments/pilot/audit_corpus.py --json      # machine-readable
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

CORPORA = [
    # The February run is superseded but still published in tex_output/, so it
    # is audited too: a shipped file that nothing checks is exactly how the
    # earlier defects survived.
    ("La Longue Marche 140-3 — february-original (superseded, published)",
     HERE / "production" / "140-3", 696),
    ("La Longue Marche 140-4 — february-original (superseded, published)",
     HERE / "production" / "140-4", 280),
    ("La Longue Marche 140-3 — mateo-canonical (Pro)",
     HERE / "production-mateo-canonical" / "140-3", 696),
    ("La Longue Marche 140-4 — mateo-canonical (Pro)",
     HERE / "production-mateo-canonical" / "140-4", 280),
    ("La Longue Marche 140-3 — flash-lite-mateo",
     HERE / "production-flash-lite-mateo" / "140-3", 696),
    ("La Longue Marche 140-4 — flash-lite-mateo",
     HERE / "production-flash-lite-mateo" / "140-4", 280),
    ("Préschémas (Bourbaki Schémas) — page-by-page",
     REPO / "experiments" / "bourbaki" / "production-pages", 437),
    ("Catégories de variétés (U46) — page-by-page",
     REPO / "experiments" / "varietes" / "production-pages", 100),
]

MIN_CHARS = 30
DEFAULT_ECHO_THRESHOLD = 0.75

# Pages whose high similarity to their predecessor is real: the *source*
# repeats the page. Each entry has been checked against the scan, and the
# reason is recorded so the exemption can be re-checked rather than trusted.
# Keyed by corpus label.
KNOWN_DUPLICATE_PAGES = {
    "Préschémas (Bourbaki Schémas) — page-by-page": {
        130: "PDF pages 129 and 130 are both typescript page '- 94 -' — a "
             "second impression of the same sheet, verified against the scans "
             "on 2026-08-14. The transcriptions agree because the pages do.",
    },
}

COMMENT_RE = re.compile(r"(?m)^\s*%.*$")
WORD_RE = re.compile(r"[a-zà-öø-ÿœ0-9]+", re.IGNORECASE)

# English deliberation that has no place in a French transcription. Matched
# case-sensitively where capitalisation matters, to avoid flagging French
# prose that happens to contain these letters.
LEAK_PATTERNS = [
    r"```",
    r"\bLet's\b", r"\bLet me\b", r"\bI will\b", r"\bI'll\b", r"\bI think\b",
    r"\bWait,", r"\bAh!", r"\bHmm\b", r"\bActually,",
    r"\bCould it be\b", r"\bThis matches\b", r"\bLooking at\b",
    r"\bIt must be\b", r"\bMaybe\b", r"\bProbably\b",
    r"\bOne last look\b", r"\bReading again\b", r"\bLet's reconsider\b",
    r"\bthe user\b", r"\bAs an AI\b", r"\bHere is the transcription\b",
    r"\bI cannot\b", r"\bI'm not sure\b",
]
LEAK_RE = re.compile("|".join(LEAK_PATTERNS))

ENV_BEGIN_RE = re.compile(r"\\begin\{([a-zA-Z*]+)\}")
ENV_END_RE = re.compile(r"\\end\{([a-zA-Z*]+)\}")
ENV_ANY_RE = re.compile(r"\\(begin|end)\{([a-zA-Z*]+)\}")
# Only \\operatorname: a "\\\\" before \\mathbb, \\mathcal etc. is normally a
# legitimate row break inside a matrix or subarray, not an escaping bug.
BAD_ESCAPE_RE = re.compile(r"\\\\operatorname\b")


def strip_comments(text: str) -> str:
    return COMMENT_RE.sub(" ", text)


def words(text: str) -> list[str]:
    """Lowercased word tokens, insensitive to line wrapping and hyphenation."""
    s = strip_comments(text)
    s = re.sub(r"-\s*\n\s*", "", s)      # de-hyphenate across line breaks
    s = re.sub(r"\s+", " ", s)
    return [w.lower() for w in WORD_RE.findall(s)]


def echo_similarity(text: str, prev_text: str) -> float:
    """Word-level similarity — insensitive to re-wrapping and hyphenation."""
    a, b = words(prev_text or ""), words(text or "")
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def find_leaks(text: str) -> list[str]:
    return sorted({m.group(0) for m in LEAK_RE.finditer(text)})


def unbalanced_envs(text: str) -> list[str]:
    """Stack-match \\begin/\\end; report mismatched or unclosed pairs."""
    stack: list[str] = []
    problems: list[str] = []
    for m in ENV_ANY_RE.finditer(text):
        kind, name = m.group(1), m.group(2)
        if kind == "begin":
            stack.append(name)
        else:
            if not stack:
                problems.append(f"\\end{{{name}}} with no matching \\begin")
            elif stack[-1] != name:
                problems.append(f"\\begin{{{stack[-1]}}} closed by \\end{{{name}}}")
                stack.pop()
            else:
                stack.pop()
    problems += [f"\\begin{{{n}}} never closed" for n in stack]
    return problems


# Commands that legitimately end a page. Grothendieck's own text trails off
# in ellipses constantly, so a page ending "\dots" is finished, not cut off.
TERMINAL_COMMANDS = {
    "dots", "ldots", "cdots", "vdots", "ddots", "hfill", "par", "noindent",
    "bigskip", "medskip", "smallskip", "newline", "qed", "blacksquare",
}


def truncation_signals(text: str) -> list[str]:
    body = strip_comments(text).strip()
    out = []
    if body.count("$$") % 2:
        out.append("odd number of $$ (math left open)")
    # Inline math parity. Checking only $$ missed pages that end on a
    # dangling single "$" — the math then runs on into the next page and
    # errors there, so the damage shows up somewhere other than its cause.
    without_display = body.replace("$$", "")
    inline = len(re.findall(r"(?<!\\)\$", without_display))
    if inline % 2:
        out.append("odd number of single $ (inline math left open)")
    tail = body.rstrip()
    m = re.search(r"\\([a-zA-Z]*)$", tail)
    if m and m.group(1) not in TERMINAL_COMMANDS:
        out.append("ends mid-command")
    if re.search(r"\\leqno\{\(\d*$", tail):
        out.append("ends inside an equation number")
    if re.search(r"\{\s*$", tail) or tail.endswith("\\"):
        out.append("ends on an open brace or backslash")
    return out


def audit(path: Path, total: int, threshold: float,
          known_duplicates: dict | None = None) -> dict | None:
    tpath = path / "transcriptions.json"
    if not tpath.exists():
        return None
    data = json.loads(tpath.read_text(encoding="utf-8"))

    texts: dict[int, str] = {}
    empties: list[int] = []
    for page in range(1, total + 1):
        entry = data.get(str(page), {})
        if entry.get("status") != "success":
            continue
        raw = entry.get("transcription", "") or ""
        if len(raw.strip()) < MIN_CHARS:
            empties.append(page)
            continue
        texts[page] = raw

    known = known_duplicates or {}
    echoes, leaks, truncs, envs, escapes = [], [], [], [], []
    known_hits = []
    for page, raw in texts.items():
        prev = texts.get(page - 1)
        if prev:
            ratio = echo_similarity(raw, prev)
            if ratio >= threshold:
                if page in known:
                    known_hits.append((page, round(ratio, 3), known[page]))
                else:
                    echoes.append((page, round(ratio, 3)))
        found = find_leaks(raw)
        if found:
            leaks.append((page, found[:6]))
        t = truncation_signals(raw)
        if t:
            truncs.append((page, t))
        e = unbalanced_envs(raw)
        if e:
            envs.append((page, e[:4]))
        n_esc = len(BAD_ESCAPE_RE.findall(raw))
        if n_esc:
            escapes.append((page, n_esc))

    by_words: dict[str, list[int]] = {}
    for page, raw in texts.items():
        key = " ".join(words(raw))
        if key:
            by_words.setdefault(key, []).append(page)
    duplicates = [p for p in by_words.values() if len(p) > 1 and max(p) - min(p) > 1]

    return {
        "pages_with_text": len(texts),
        "echoes": echoes,
        "known_duplicates": known_hits,
        "reasoning_leaks": leaks,
        "truncations": truncs,
        "unbalanced_envs": envs,
        "escape_artifacts": escapes,
        "empty_successes": empties,
        "duplicate_groups": duplicates,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threshold", type=float, default=DEFAULT_ECHO_THRESHOLD,
                    help="Word-level similarity at or above which a page counts as an echo")
    ap.add_argument("--json", action="store_true",
                    help="Print the machine-readable report to stdout")
    args = ap.parse_args()

    report = {"generated": date.today().isoformat(),
              "echo_threshold": args.threshold, "corpora": {}}

    lines = [
        "# Corpus audit — defects no error count reveals",
        "",
        f"Generated {report['generated']} by "
        "`experiments/pilot/audit_corpus.py` (no API calls). Echo threshold "
        f"(word-level): {args.threshold}.",
        "",
        "Each column is a class of page that was recorded as a successful "
        "transcription but may carry wrong or unusable content. See the "
        "module docstring for what each one means and why it is checked.",
        "",
        "| Corpus | Pages with text | Echoes | Reasoning leaks | Truncated | Unbalanced env | Escape artifacts | Empty | Dup groups |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    details: list[str] = []
    clean = True

    for name, path, total in CORPORA:
        res = audit(path, total, args.threshold,
                    KNOWN_DUPLICATE_PAGES.get(name))
        if res is None:
            continue
        report["corpora"][name] = res
        counts = [len(res["echoes"]), len(res["reasoning_leaks"]),
                  len(res["truncations"]), len(res["unbalanced_envs"]),
                  len(res["escape_artifacts"]), len(res["empty_successes"]),
                  len(res["duplicate_groups"])]
        if any(counts):
            clean = False
        lines.append(f"| {name} | {res['pages_with_text']} | "
                     + " | ".join(str(c) for c in counts) + " |")

        def section(title: str, rows: list[str]) -> None:
            if rows:
                details.append(f"### {title} — {name}\n")
                details.append("\n".join(rows) + "\n")

        section("Context echoes",
                [f"- page {p}: {r} word-level similarity to page {p - 1}"
                 for p, r in res["echoes"]])
        section("Reasoning leaks",
                [f"- page {p}: {', '.join(repr(x) for x in pats)}"
                 for p, pats in res["reasoning_leaks"]])
        section("Truncated pages",
                [f"- page {p}: {'; '.join(t)}" for p, t in res["truncations"]])
        section("Unbalanced environments",
                [f"- page {p}: {'; '.join(e)}" for p, e in res["unbalanced_envs"]])
        section("Escape artifacts (literal double backslash)",
                [f"- page {p}: {n} occurrence(s)" for p, n in res["escape_artifacts"]])
        section("Empty successes",
                ["- pages: " + ", ".join(str(p) for p in res["empty_successes"])]
                if res["empty_successes"] else [])
        section("Duplicate groups",
                ["- pages " + ", ".join(str(p) for p in sorted(g))
                 for g in res["duplicate_groups"]])
        section("Known genuine duplicates (exempted, verified against the scans)",
                [f"- page {p}: {r} similarity to page {p - 1} — {why}"
                 for p, r, why in res.get("known_duplicates", [])])

    lines.append("")
    if clean:
        lines += ["No defects of any of these classes were found.", ""]
    else:
        lines += ["", *details]

    (HERE / "CORPUS_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")
    (HERE / "corpus_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("\n".join(lines[:30]))
        print(f"\nwrote {(HERE / 'CORPUS_AUDIT.md').relative_to(REPO)}")


if __name__ == "__main__":
    main()
