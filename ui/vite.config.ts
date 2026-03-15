import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
// https://vite.dev/config/
export default defineConfig(async () => {
  const plugins = [react()]

  if (process.env.VITE_USE_MOCKS === '1') {
    const { default: devProxy } = await import('./devProxy')
    plugins.push(devProxy())
  }

  return {
    root: fileURLToPath(new URL('./', import.meta.url)),
    plugins,
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    test: {
      environment: 'jsdom',
      include: ['src/**/*.{test,spec}.{js,ts,tsx}'],
      // Run tests in a single thread to avoid CI/sandbox worker issues
      pool: 'threads',
      poolOptions: {
        threads: { singleThread: true },
      },
    },
  }
})
