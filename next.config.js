/** @type {import('next').NextConfig} */
const nextConfig = {
  trailingSlash: true,
  async rewrites() {
    return [
      {
        source: '/api/transactional/:path*/',
        destination: `${process.env.TRANSACTIONAL_API_ORIGIN || 'http://127.0.0.1:8000'}/api/transactional/:path*/`,
      },
    ]
  },
}
module.exports = nextConfig
