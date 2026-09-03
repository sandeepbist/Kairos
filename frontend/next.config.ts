import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server bundle for slim production containers.
  output: "standalone",
  experimental: {
    // Cap proxy body buffering at the same 1MB the backend enforces
    // (Next's default is 10MB). This flag truncates buffering but does
    // NOT reject — the hard 413 lives in src/proxy.ts.
    proxyClientMaxBodySize: "1mb",
  },
};

export default nextConfig;
