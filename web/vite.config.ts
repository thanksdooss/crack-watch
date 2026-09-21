import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import { fileURLToPath, URL } from 'node:url'
import { readFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'

// 개발 서버는 /public 안의 .mjs를 모듈로 불러오는 걸 막는다(배포 빌드는 괜찮다).
// ONNX Runtime Web은 실행 시점에 /ort/ort-wasm-simd-threaded.mjs를 import하므로,
// 개발 서버에서만 이 요청을 먼저 가로채 node_modules의 파일을 그대로 내준다.
function serveOrtInDev(): Plugin {
  const dist = fileURLToPath(new URL('./node_modules/onnxruntime-web/dist/', import.meta.url))
  return {
    name: 'serve-ort-in-dev',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/ort', (req, res, next) => {
        const file = resolve(dist, (req.url ?? '').split('?')[0].replace(/^\//, ''))
        if (!file.startsWith(dist) || !existsSync(file)) return next()
        res.setHeader('Content-Type', file.endsWith('.wasm') ? 'application/wasm' : 'text/javascript')
        res.end(readFileSync(file))
      })
    },
  }
}

export default defineConfig({
  plugins: [
    serveOrtInDev(),
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
