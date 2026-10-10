import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Build output tự chứa (standalone) để chạy trong Docker —
  // `next build` sinh server.js tối giản + các file đã trace.
  output: "standalone",
};

export default nextConfig;
