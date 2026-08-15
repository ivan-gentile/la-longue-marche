import { notFound } from "next/navigation";
import { getDocMeta, getPage } from "../../../lib/data";
import ReviewClient from "./review-client";

// Never prerendered: the data files are generated out of band and must
// not be required at build time.
export const dynamic = "force-dynamic";

function buildReportUrl(docId: string, page: number, issueFile: string): string {
  const params = new URLSearchParams({
    template: "transcription-anomaly.yml",
    labels: "anomaly",
    title: `[anomaly] ${docId} p.${page}: `,
    file: issueFile,
    page: String(page),
  });
  return `https://github.com/ivan-gentile/la-longue-marche/issues/new?${params.toString()}`;
}

export default async function ReviewPage({
  params,
}: {
  params: Promise<{ doc: string; page: string }>;
}) {
  const { doc, page: pageParam } = await params;

  const meta = getDocMeta(doc);
  if (!meta) notFound();

  const pageNum = Number(pageParam);
  if (
    !/^\d+$/.test(pageParam) ||
    !Number.isInteger(pageNum) ||
    pageNum < 1 ||
    pageNum > meta.totalPages
  ) {
    notFound();
  }

  const entry = getPage(doc, pageNum);
  const warnings = entry?.warnings ?? [];
  const alt = meta.hasAlt && typeof entry?.alt === "string" ? entry.alt : null;
  const sim = alt !== null && typeof entry?.sim === "number" ? entry.sim : null;

  return (
    <ReviewClient
      docId={meta.id}
      docTitle={meta.title}
      page={pageNum}
      totalPages={meta.totalPages}
      text={entry?.text ?? null}
      alt={alt}
      sim={sim}
      warnings={warnings}
      reportUrl={buildReportUrl(meta.id, pageNum, meta.issueFile)}
    />
  );
}
