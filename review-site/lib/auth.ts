/**
 * Session helpers shared by the middleware (edge runtime) and the
 * API routes (node runtime). Everything here must stay edge-compatible:
 * jose + Web Crypto only, no node:crypto.
 */
// Granular imports keep JWE (and its DecompressionStream dependency)
// out of the edge middleware bundle.
import { SignJWT } from "jose/jwt/sign";
import { jwtVerify } from "jose/jwt/verify";

export const SESSION_COOKIE = "lm_session";

/** 90 days, in seconds. */
export const SESSION_MAX_AGE = 90 * 24 * 60 * 60;

function secretKey(): Uint8Array | null {
  const secret = process.env.SESSION_SECRET;
  if (!secret) return null;
  return new TextEncoder().encode(secret);
}

/** Sign a fresh session JWT. Throws if SESSION_SECRET is unset. */
export async function signSession(): Promise<string> {
  const key = secretKey();
  if (!key) throw new Error("SESSION_SECRET is not configured");
  return await new SignJWT({ scope: "review" })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(`${SESSION_MAX_AGE}s`)
    .sign(key);
}

/** True when the token is a valid, unexpired session JWT. Never throws. */
export async function verifySession(
  token: string | undefined | null,
): Promise<boolean> {
  if (!token) return false;
  const key = secretKey();
  if (!key) return false;
  try {
    await jwtVerify(token, key, { algorithms: ["HS256"] });
    return true;
  } catch {
    return false;
  }
}

/** Cookie attributes for the session cookie, per the shared contract. */
export function sessionCookieOptions() {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_MAX_AGE,
  };
}

/**
 * Constant-time string comparison. Both inputs are SHA-256 hashed first
 * (fixed length, hides length differences), then compared byte by byte
 * without early exit. Uses Web Crypto so it runs on edge and node alike.
 */
export async function constantTimeEqual(a: string, b: string): Promise<boolean> {
  const enc = new TextEncoder();
  const [da, db] = await Promise.all([
    crypto.subtle.digest("SHA-256", enc.encode(a)),
    crypto.subtle.digest("SHA-256", enc.encode(b)),
  ]);
  const ua = new Uint8Array(da);
  const ub = new Uint8Array(db);
  let diff = 0;
  for (let i = 0; i < ua.length; i++) diff |= ua[i] ^ ub[i];
  return diff === 0;
}
