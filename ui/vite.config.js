import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: {
    rollupOptions: {
      output: {
        // Keep the heavy graph/chart libraries out of the app chunk so they cache separately.
        manualChunks: {
          "vendor-vis": ["vis-network/peer", "vis-data/peer"],
          "vendor-charts": ["apexcharts", "react-apexcharts"],
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
});
