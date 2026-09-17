import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'https://localhost:8340',
        changeOrigin: true,
        secure: false
      },
      '/internal': {
        target: 'https://localhost:8340',
        changeOrigin: true,
        secure: false
      },
      '/ws': {
        target: 'wss://localhost:8340',
        ws: true,
        secure: false
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  }
})