import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: '균열 감시',
        short_name: '균열감시',
        description: '시민이 찍은 벽면 사진에서 균열을 찾아 폭을 추정한다. 전문가 진단이 아니다.',
        theme_color: '#1f2937',
        background_color: '#ffffff',
        display: 'standalone',
        start_url: '/',
        icons: [],
      },
      workbox: {
        // 모델·OpenCV 같은 큰 정적 자산까지 캐시한다(오프라인에서 검출이 돌아야 한다).
        globPatterns: ['**/*.{js,css,html,wasm,onnx}'],
        maximumFileSizeToCacheInBytes: 30 * 1024 * 1024,
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@shared': fileURLToPath(new URL('../shared', import.meta.url)),
    },
  },
  worker: { format: 'es' },
})
