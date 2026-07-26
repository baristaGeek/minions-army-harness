import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Pin the file-tracing root to this app so a lockfile in a parent directory
  // doesn't confuse Next's workspace-root inference.
  outputFileTracingRoot: __dirname,
};

export default nextConfig;
