import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue()],
  server: {
    // In development the API runs separately: uvicorn analyst.bootstrap:build_app --factory
    proxy: { '/api': process.env.API_URL ?? 'http://localhost:8000' },
  },
})
