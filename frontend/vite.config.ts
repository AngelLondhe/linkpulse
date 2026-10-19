import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
  build: {
    rollupOptions: {
      output: {
        // Keep the heavy charting libraries out of the main chunk (the map is lazy-loaded).
        manualChunks(id: string) {
          if (/node_modules\/(recharts|d3-|victory-vendor)/.test(id)) return 'charts'
          return undefined
        },
      },
    },
  },
})
