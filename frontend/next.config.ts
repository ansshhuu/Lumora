import type { NextConfig } from "next";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        // Proxy /api/:path* → backend/:path*
        // Browser always talks to localhost:3000 — no CORS needed.
        source: "/api/:path*",
        destination: `${API_URL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
