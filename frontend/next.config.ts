import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    // In production the API URL is set via NEXT_PUBLIC_API_URL.
    // In development, proxy /api/* to the Django server so we avoid CORS issues.
    if (process.env.NODE_ENV === "development") {
      return [
        {
          source: "/api/:path*",
          destination: "http://localhost:8000/api/:path*",
        },
      ];
    }
    return [];
  },
};

export default nextConfig;
