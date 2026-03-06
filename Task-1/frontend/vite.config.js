import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    hmr: {
      clientPort: 80,   // HMR websocket goes through nginx on port 80
    },
    watch: {
      usePolling: true, // needed for file watching inside Docker on Mac
    }
  }
})