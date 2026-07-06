import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  async rewrites() {
    if (process.env.NODE_ENV === "development") {
      return [
        { source: "/api/extract-map", destination: "http://127.0.0.1:5328/api/extract-map" },
        { source: "/api/extract-logs", destination: "http://127.0.0.1:5328/api/extract-logs" },
        { source: "/api/build-query", destination: "http://127.0.0.1:5328/api/build-query" },
      ];
    }
    return [];
  },
};

export default nextConfig;
