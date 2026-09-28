import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3100,
    proxy: {
      '/api': 'http://localhost:3100',
      '/health': 'http://localhost:3100',
      '/app': 'http://localhost:3100',
      '/figma-app': 'http://localhost:3100',
      '/sandbox': 'http://localhost:3100',
      '/static': 'http://localhost:3100',
    },
  },
  build: { outDir: 'dist' },
})
