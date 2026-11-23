import { defineConfig } from 'vitest/config'
import tailwind from '@tailwindcss/vite'
export default defineConfig({ plugins: [tailwind()], server: {port: 5173, strictPort: true}, test: {environment: 'jsdom'} })
