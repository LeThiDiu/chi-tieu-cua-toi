import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Khi chạy `npm run dev`, mọi lời gọi /api được chuyển tiếp sang FastAPI (cổng 8000)
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
});
