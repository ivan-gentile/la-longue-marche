import { NextRequest, NextResponse } from "next/server";
import {
  SESSION_COOKIE,
  constantTimeEqual,
  sessionCookieOptions,
  signSession,
} from "../../../lib/auth";

/** Only allow same-origin relative redirect targets. */
function safeNextPath(raw: unknown): string {
  if (
    typeof raw === "string" &&
    raw.startsWith("/") &&
    !raw.startsWith("//") &&
    !raw.includes("\\")
  ) {
    return raw;
  }
  return "/";
}

export async function POST(req: NextRequest) {
  const form = await req.formData().catch(() => null);
  const nextPath = safeNextPath(form?.get("next"));
  const supplied = form?.get("password");
  const password = typeof supplied === "string" ? supplied : "";
  const expected = process.env.REVIEW_PASSWORD;

  if (!expected || !process.env.SESSION_SECRET) {
    return new NextResponse(
      "Server not configured (REVIEW_PASSWORD / SESSION_SECRET missing).",
      { status: 503, headers: { "content-type": "text/plain; charset=utf-8" } },
    );
  }

  if (!(await constantTimeEqual(password, expected))) {
    const url = new URL("/login", req.url);
    url.searchParams.set("error", "1");
    if (nextPath !== "/") url.searchParams.set("next", nextPath);
    return NextResponse.redirect(url, 303);
  }

  const token = await signSession();
  const res = NextResponse.redirect(new URL(nextPath, req.url), 303);
  res.cookies.set(SESSION_COOKIE, token, sessionCookieOptions());
  return res;
}
