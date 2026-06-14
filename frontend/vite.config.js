import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // Proxy /api calls to Flask so we never hit CORS in dev
      '/api': {
        target: 'http://backend:5000',
        changeOrigin: true,
      },
      // Proxy short alias redirects too
      '/[a-zA-Z0-9]{6}': {
        target: 'http://backend:5000',
        changeOrigin: true,
      },
    },
  },
})
