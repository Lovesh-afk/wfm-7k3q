import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, forward /api/* calls to the FastAPI server so the frontend
// can use relative URLs everywhere (same as in production on Vercel).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": process.env.VITE_API_PROXY || "http://localhost:8000",
    },
  },
});
