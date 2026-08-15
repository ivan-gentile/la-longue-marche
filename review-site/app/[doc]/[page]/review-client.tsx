"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type Zoom = "fit" | "150" | "200";

export interface ReviewClientProps {
  docId: string;
  docTitle: string;
  page: number;
  totalPages: number;
  /** Canonical LaTeX, or null when this page has no transcription. */
  text: string | null;
  /** Flash-Lite alternate reading, when present. */
  alt: string | null;
  /** Word-level similarity between the two readings, when alt is present. */
  sim: number | null;
  warnings: string[];
  reportUrl: string;
}

export default function ReviewClient(props: ReviewClientProps) {
  const router = useRouter();
  const [zoom, setZoom] = useState<Zoom>("fit");
  const [showAlt, setShowAlt] = useState(false);
  const [gotoValue, setGotoValue] = useState("");

  const { docId, page, totalPages } = props;

  const navigateTo = useCallback(
    (target: number) => {
      if (target >= 1 && target <= totalPages) {
        router.push(`/${docId}/${target}`);
      }
    },
    [router, docId, totalPages],
  );

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const el = e.target as HTMLElement | null;
      if (
        el &&
        (el.tagName === "INPUT" ||
          el.tagName === "TEXTAREA" ||
          el.tagName === "SELECT" ||
          el.isContentEditable)
      ) {
        return; // never steal keys from form fields (e.g. the go-to input)
      }
      if (e.key === "ArrowLeft") {
        navigateTo(page - 1);
      } else if (e.key === "ArrowRight") {
        navigateTo(page + 1);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [navigateTo, page]);

  const hasAlt = props.alt !== null;
  const divergent = hasAlt && props.sim !== null && props.sim < 0.6;

  return (
    <>
      <div className="review-subheader">
        <a className="review-doc-title" href="/" title="Back to document list">
          {props.docTitle}
        </a>

        <span className="review-pageno">
          page {page} / {totalPages}
        </span>

        <span className="review-nav">
          <button
            type="button"
            onClick={() => navigateTo(page - 1)}
            disabled={page <= 1}
            title="Previous page (←)"
          >
            ← Prev
          </button>
          <button
            type="button"
            onClick={() => navigateTo(page + 1)}
            disabled={page >= totalPages}
            title="Next page (→)"
          >
            Next →
          </button>
        </span>

        <form
          className="goto-form"
          onSubmit={(e) => {
            e.preventDefault();
            const n = parseInt(gotoValue, 10);
            if (!Number.isNaN(n)) {
              navigateTo(n);
              setGotoValue("");
            }
          }}
        >
          <input
            type="number"
            min={1}
            max={totalPages}
            value={gotoValue}
            onChange={(e) => setGotoValue(e.target.value)}
            placeholder="p."
            aria-label="Go to page"
          />
          <button type="submit">Go</button>
        </form>

        <span className="zoom-group" role="group" aria-label="Scan zoom">
          <span className="zoom-label">Zoom:</span>
          {(
            [
              ["fit", "Fit"],
              ["150", "150%"],
              ["200", "200%"],
            ] as Array<[Zoom, string]>
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={zoom === value ? "active" : ""}
              onClick={() => setZoom(value)}
            >
              {label}
            </button>
          ))}
        </span>

        {hasAlt && (
          <label className="alt-toggle">
            <input
              type="checkbox"
              checked={showAlt}
              onChange={(e) => setShowAlt(e.target.checked)}
            />
            Second reading
          </label>
        )}

        {divergent && (
          <span className="sim-badge">
            The two models read this page differently — worth a close look.
          </span>
        )}

        <a
          className="report-link"
          href={props.reportUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          Report anomaly ↗
        </a>
      </div>

      <div className="review-panes">
        <div className="pane scan-pane">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`/api/scan/${docId}/${page}`}
            alt={`scan of page ${page}`}
            loading="lazy"
            className={`zoom-${zoom}`}
          />
        </div>

        <div className="pane text-pane">
          {props.text === null ? (
            <p className="no-transcription">
              This page has no transcription yet.
            </p>
          ) : (
            <>
              {props.warnings.length > 0 && (
                <div className="warnings-banner">
                  <strong>Transcription warnings</strong>
                  <ul>
                    {props.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
              <pre>{props.text}</pre>
              {hasAlt && showAlt && (
                <div className="alt-reading">
                  <p className="alt-reading-label">
                    Second reading — Flash-Lite draft
                  </p>
                  <pre>{props.alt}</pre>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
