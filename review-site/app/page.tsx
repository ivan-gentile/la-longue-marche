import { listDocs } from "../lib/data";

export const dynamic = "force-dynamic";

export default function HomePage() {
  const docs = listDocs();

  return (
    <div className="doc-list">
      <h1>Documents</h1>
      <p className="doc-list-intro">
        Side-by-side review of machine transcriptions against the archive
        scans. Pick a volume to begin.{" "}
        <a href="/api/logout">Log out</a>
      </p>

      {docs.map((doc) => (
        <a
          key={doc.id}
          className="doc-card"
          href={`/${doc.id}/${doc.firstPage}`}
        >
          <h2>{doc.title}</h2>
          <p className="doc-subtitle">{doc.subtitle}</p>
          <p className="doc-coverage">
            {doc.hasData ? (
              <>
                {doc.transcribed} of {doc.totalPages} pages transcribed
              </>
            ) : (
              <span className="doc-note">
                {doc.totalPages} pages — transcription data not yet loaded
              </span>
            )}
          </p>
        </a>
      ))}
    </div>
  );
}
