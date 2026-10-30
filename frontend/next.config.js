/** @type {import('next').NextConfig} */
const apiServer = process.env.KAZIKASI_API_SERVER_URL?.replace(/\/$/, '')

const nextConfig = {
  images: { unoptimized: true },
  allowedDevOrigins: ['*.e2b.app'],
  async rewrites() {
    if (!apiServer) return []
    return [{ source: '/api/:path*', destination: `${apiServer}/api/:path*` }]
  },
}
module.exports = nextConfig
