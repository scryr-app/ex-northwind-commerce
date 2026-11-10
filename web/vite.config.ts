/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "node",
    globals: true,
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary", "lcov", "html"],
      reportsDirectory: "test-results/coverage",
      include: ["src/**/*.ts", "src/**/*.tsx"],
      exclude: ["src/main.tsx", "src/**/*.d.ts"]
    }
  }
});
