import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE, verifySession } from "../../../../../lib/auth";
import { getDocMeta } from "../../../../../lib/data";

/**
 * Authenticated proxy for the page scans stored in Vercel Blob.
 * The browser only ever sees /api/scan/<doc>/<page>; the Blob URL
 * (SCAN_BASE_URL) stays server-side.
 *
 * Middleware already guards this path, but this is the route that
 * protects the scans, so the session is verified again here
 * (defense in depth).
 */
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ doc: string; page: string }> },
) {
  const token = req.cookies.get(SESSION_COOKIE)?.value;
  if (!(await verifySession(token))) {
    return NextResponse.json(
      { error: "Authentication required" },
      { status: 401 },
    );
  }

  const { doc, page } = await params;

  const meta = getDocMeta(doc);
  if (!meta) {
    return new NextResponse("Unknown document", { status: 404 });
  }

  if (!/^\d+$/.test(page)) {
    return new NextResponse("Invalid page number", { status: 400 });
  }
  const pageNum = Number(page);
  if (!Number.isInteger(pageNum) || pageNum < 1 || pageNum > meta.totalPages) {
    return new NextResponse("Page out of range", { status: 404 });
  }

  const base = process.env.SCAN_BASE_URL;
  if (!base) {
    return new NextResponse("Scan storage not configured.", {
      status: 503,
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  }

  const padded = String(pageNum).padStart(4, "0");
  const upstreamUrl = `${base}/scans/${meta.id}/${padded}.jpg`;

  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl, { cache: "no-store" });
  } catch {
    return new NextResponse("Scan storage unreachable.", { status: 502 });
  }

  if (upstream.status === 404) {
    return new NextResponse("Scan not found", { status: 404 });
  }
  if (!upstream.ok || !upstream.body) {
    return new NextResponse("Upstream error", { status: 502 });
  }

  return new NextResponse(upstream.body, {
    status: 200,
    headers: {
      "content-type": "image/jpeg",
      "cache-control": "private, max-age=3600",
    },
  });
}
