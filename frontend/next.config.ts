import type { NextConfig } from "next";

// The backend serves routes at its root (e.g. /user/, /session/start/). The
// frontend calls /api/miniapp/* and /api/loud/* — these rewrites proxy those
// to the backend, stripping the /api/miniapp and /api/loud prefixes. Set
// BACKEND_ORIGIN in the environment (defaults to the local dev backend).
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN || "http://localhost:8000";

const nextConfig: NextConfig = {
  output: 'standalone', // Required for Docker deployment
  reactCompiler: true,
  // Allow external images for avatars
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'pbs.twimg.com' },
      { protocol: 'https', hostname: '*.twimg.com' },
    ],
  },
  async rewrites() {
    return [
      { source: '/api/miniapp/:path*', destination: `${BACKEND_ORIGIN}/:path*` },
      { source: '/api/loud/:path*', destination: `${BACKEND_ORIGIN}/:path*` },
      // OAuth callback lives at the backend root path
      { source: '/api/auth/:path*', destination: `${BACKEND_ORIGIN}/api/auth/:path*` },
    ];
  },
};

export default nextConfig;
