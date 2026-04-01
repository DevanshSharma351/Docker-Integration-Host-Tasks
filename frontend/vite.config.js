import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backendHttp = process.env.VITE_BACKEND_HTTP || 'http://127.0.0.1:8001';
const backendWs = process.env.VITE_BACKEND_WS || 'ws://127.0.0.1:8001';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: backendHttp,
        changeOrigin: true,
      },
      '/ws': {
        target: backendWs,
        ws: true,
      },
    },
  },
});
