import { defineConfig } from "vite-plus";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Benchmark results hold hundreds of thousands of run artifacts; the app
  // fetches them with no-store, so watching them only exhausts the server.
  server: { watch: { ignored: ["**/experiments/**"] } },
});
