import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      '/health': 'http://localhost:8000',
      '/forecast': 'http://localhost:8000',
      '/routes': 'http://localhost:8000',
      '/geocode': 'http://localhost:8000',
      '/analyze': 'http://localhost:8000',
    },
  },
})
