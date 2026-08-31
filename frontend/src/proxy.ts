import { NextRequest, NextResponse } from "next/server";

/**
 * Edge proxy (Next.js 16 renamed middleware -> proxy).
 *
 * Forwards same-origin `/api/*` requests to the FastAPI backend and
 * injects the operator API key from server env. The browser never
 * receives or transmits the key; CORS on the backend becomes a second
 * line of defense rather than the only one.
 *
 * Env (server-side only):
 *   BACKEND_INTERNAL_URL  e.g. http://backend:8000 (Docker) or
 *                         http://localhost:8000 (dev). Default: localhost.
 *   KAIROS_API_KEY        shared operator key. When unset (dev), requests
 *                         pass through untouched so local flows work while
 *                         the backend has auth disabled.
 */

const BACKEND =
  process.env.BACKEND_INTERNAL_URL || process.env.BACKEND_URL || "http://localhost:8000";

const API_KEY = process.env.KAIROS_API_KEY || process.env.API_KEY || "";

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  // Only the API namespace is proxied; everything else is Next's own routing.
  if (!pathname.startsWith("/api")) {
    return NextResponse.next();
  }

  const target = `${BACKEND}${pathname}${search}`;
  const headers = new Headers(request.headers);
  headers.set("Host", new URL(BACKEND).host);

  if (API_KEY) {
    headers.set("X-API-Key", API_KEY);
  }

  return NextResponse.rewrite(new URL(target), { request: { headers } });
}

export const config = {
  matcher: ["/api/:path*"],
};
