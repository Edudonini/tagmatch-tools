import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  async rewrites() {
    // Clean URL for the static taxonomy reference doc (public/taxonomia.html).
    // Applies in every environment, unlike the dev-only API proxies below.
    const always = [{ source: "/taxonomia", destination: "/taxonomia.html" }];
    if (process.env.NODE_ENV === "development") {
      return [
        ...always,
        { source: "/api/extract-map", destination: "http://127.0.0.1:5328/api/extract-map" },
        { source: "/api/extract-logs", destination: "http://127.0.0.1:5328/api/extract-logs" },
        { source: "/api/build-query", destination: "http://127.0.0.1:5328/api/build-query" },
        { source: "/api/match", destination: "http://127.0.0.1:5328/api/match" },
      ];
    }
    return always;
  },
};

export default nextConfig;
