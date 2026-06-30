import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow the backend API to be proxied during development
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/:path*`,
      },
    ];
  },
  images: {
    remotePatterns: [],
  },
  // Turbopack for faster dev builds (Next.js 15 default)
  experimental: {
    turbo: {},
  },
};

export default nextConfig;
