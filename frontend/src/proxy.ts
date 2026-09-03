import { NextRequest, NextResponse } from "next/server";

/**
 * Edge proxy (Next.js 16 renamed middleware -> proxy).
 *
 * Forwards same-origin `/api/*` requests to the FastAPI backend by
 * streaming them through this handler, injecting the operator API key
 * from server env. The browser never receives or transmits the key.
 *
 * An explicit fetch (rather than NextResponse.rewrite) lets this layer
 * catch backend connection failures and answer with a structured JSON
 * 502, so the dashboard degrades gracefully instead of a raw 500.
 *
 * Env (server-side only):
 *   BACKEND_INTERNAL_URL  e.g. http://backend:8000 (Docker) or
 *                         http://localhost:8000 (dev). Default: localhost.
 *   KAIROS_API_KEY        shared operator key. When unset (dev), requests
 *                         pass through unauthenticated so local flows work
 *                         while the backend has auth disabled.
 */

const BACKEND =
  process.env.BACKEND_INTERNAL_URL || process.env.BACKEND_URL || "http://localhost:8000";

const API_KEY = process.env.KAIROS_API_KEY || process.env.API_KEY || "";

// Hop-by-hop headers that must not be forwarded verbatim.
const HOP_BY_HOP = new Set([
  "host",
  "connection",
  "keep-alive",
  "transfer-encoding",
  "upgrade",
  "content-length",
]);

// Mirror the backend's 1MB MaxBodySizeMiddleware. Next 16's proxy buffers
// request bodies in memory (up to 10MB by default) BEFORE the backend
// answers, so the memory cost is already paid when FastAPI rejects. The
// proxyClientMaxBodySize flag caps the buffering but does NOT reject —
// the hard 413 must happen here. Client-supplied Content-Length is a
// fast-fail guard; chunked bodies still meet the backend's middleware.
const MAX_BODY_BYTES = 1_048_576;

export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  // Only the API namespace is proxied; everything else is Next's own routing.
  if (!pathname.startsWith("/api")) {
    return NextResponse.next();
  }

  const contentLength = Number(request.headers.get("content-length"));
  if (!Number.isNaN(contentLength) && contentLength > MAX_BODY_BYTES) {
    return NextResponse.json(
      { detail: "Request body too large." },
      { status: 413 }
    );
  }

  const target = `${BACKEND}${pathname}${search}`;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });
  // Always overwrite (not append) the key header: a client-supplied
  // value must never survive, and in keyless dev mode we strip it so the
  // backend's own auth decision is the only one that matters.
  headers.delete("X-API-Key");
  if (API_KEY) {
    headers.set("X-API-Key", API_KEY);
  }

  const hasBody = !["GET", "HEAD"].includes(request.method);

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      // @ts-expect-error duplex is required when streaming a body
      duplex: hasBody ? "half" : undefined,
    });

    const responseHeaders = new Headers();
    upstream.headers.forEach((value, key) => {
      if (!HOP_BY_HOP.has(key.toLowerCase())) {
        responseHeaders.set(key, value);
      }
    });

    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      { detail: "Backend service is unreachable. Verify the API is running." },
      { status: 502 }
    );
  }
}

export const config = {
  matcher: ["/api/:path*"],
};
