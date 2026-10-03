import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// In dev, /api is proxied to the API: the local Django server by default, or any
// other deployment with VITE_API_TARGET (e.g. the live API). In production the
// Vercel rewrite in vercel.json does the same, so the app is always same-origin.
export default defineConfig(({ mode }) => {
  const target = loadEnv(mode, process.cwd(), '').VITE_API_TARGET || 'http://127.0.0.1:8000'
  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': { target, changeOrigin: true },
      },
    },
    test: {
      include: ['src/**/*.test.ts'],
    },
  }
})
