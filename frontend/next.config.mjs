/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone', // smaller Docker image; copies only needed files
  async rewrites() {
    // In dev, proxy /api to the backend directly. In prod, Nginx handles this,
    // but keeping it here means `next dev` works standalone too.
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.BACKEND_URL || 'http://localhost:8000'}/:path*`,
      },
    ];
  },
};
export default nextConfig;
