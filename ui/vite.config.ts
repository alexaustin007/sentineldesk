import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    // /dev/states imports ../contracts/triage_response.example.json to type-check the contract.
    fs: { allow: [".."] },
    proxy: { "/api": "http://localhost:8000" },
  },
});
