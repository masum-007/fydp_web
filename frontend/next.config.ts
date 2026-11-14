import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: { root: __dirname },
  // Forward browser /api calls through the frontend origin. An HttpOnly
  // session cookie then works for localhost, refreshes and new tabs without
  // exposing a persistent token to JavaScript or mixing localhost/127.0.0.1.
  async rewrites() {
    return [{
      source: "/api/:path*",
      destination: `${process.env.BACKEND_URL ?? "http://127.0.0.1:8000"}/api/:path*`,
    }];
  },
};

export default nextConfig;
