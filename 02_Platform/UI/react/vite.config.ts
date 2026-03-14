import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/workout': 'http://localhost:8011',
      '/api':         'http://localhost:8010',
    },
  },
})
