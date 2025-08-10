/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: { typedRoutes: true },
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**.kaspi.kz' },
      { protocol: 'https', hostname: 'kaspi.kz' },
    ]
  }
}

module.exports = nextConfig


