import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'
import { defineConfig } from 'vitest/config'
import { pwaManifest } from './src/pwa/manifest.ts'

const dashboardRoot = dirname(fileURLToPath(import.meta.url))
const publicUrlRules = resolve(dashboardRoot, '../shared/public-url-rules.json')

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxy = env.VITE_API_PROXY_TARGET
    ? {
        '/api': {
          target: env.VITE_API_PROXY_TARGET,
          changeOrigin: true,
          ws: true,
        },
      }
    : undefined

  return {
    plugins: [
      react(),
      VitePWA({
        strategies: 'injectManifest',
        srcDir: 'src',
        filename: 'sw.ts',
        registerType: 'prompt',
        injectRegister: false,
        manifestFilename: 'manifest.webmanifest',
        includeAssets: [
          'favicon.svg',
          'apple-touch-icon.png',
          'offline.html',
          'offline.css',
          'icons/icon-32.png',
          'icons/icon-192.png',
          'icons/icon-512.png',
          'icons/icon-maskable-192.png',
          'icons/icon-maskable-512.png',
        ],
        manifest: pwaManifest,
        injectManifest: {
          globPatterns: ['**/*.{js,css,html,ico,png,svg,woff,woff2,webp}'],
        },
        devOptions: {
          enabled: false,
        },
      }),
    ],
    resolve: {
      alias: {
        '@homelab/public-url-rules': publicUrlRules,
      },
    },
    server: {
      proxy,
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      env: {
        VITE_API_BASE_URL: '/api/v1',
      },
    },
  }
})
