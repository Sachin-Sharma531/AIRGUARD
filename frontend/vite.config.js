import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = (env.VITE_API_BASE_URL || 'http://localhost:8000').trim().replace(/\/+$/, '')

  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: false,
      proxy: {
        '/health': proxyTarget,
        '/forecast': proxyTarget,
        '/routes': proxyTarget,
        '/geocode': proxyTarget,
        '/analyze': proxyTarget,
      },
    },
  }
})
