/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export so the dashboard can be bundled into the Python wheel and
  // served by the control plane with no Node.js at runtime.
  output: "export",
  reactStrictMode: true,
  images: { unoptimized: true },
};

export default nextConfig;
