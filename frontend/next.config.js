/**
 * In production (Coolify), this Next.js app and the FastAPI backend run in the
 * same container. We expose only Next.js on port 3000 and proxy /api/* to
 * uvicorn on 127.0.0.1:8000 server-side, so the browser only ever sees one
 * origin (orange-demo.vrlai.in) and no CORS preflight is needed.
 *
 * INTERNAL_API_URL is the in-container backend address; default is what the
 * bundled start.sh launches.
 */
const INTERNAL_API_URL = process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${INTERNAL_API_URL}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
