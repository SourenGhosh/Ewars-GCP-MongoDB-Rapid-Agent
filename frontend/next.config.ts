// next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // MapLibre GL works with Next.js App Router without special webpack config.
  // The only thing needed is "use client" on the Map component (already done).
};

export default nextConfig;