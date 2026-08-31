import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server bundle for slim production containers.
  output: "standalone",
};

export default nextConfig;
