import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8001/api/:path*",
      },
      {
        source: "/presentation",
        destination: "http://localhost:8001/presentation/",
      },
      {
        source: "/presentation/:path*",
        destination: "http://localhost:8001/presentation/:path*",
      },
    ];
  },
};

export default nextConfig;
