import { defineConfig } from "vite";

// Relative base so the build works on GitHub Pages under /<repo>/ and from any static host.
export default defineConfig({
  base: "./",
  build: { outDir: "dist", chunkSizeWarningLimit: 800 },
  test: { environment: "node", testTimeout: 60000 },
} as any);
