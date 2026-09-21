import { defineConfig, devices } from '@playwright/test'

// E2E는 배포 빌드를 미리보기 서버로 띄워 돈다. 개발 서버는 모델 라이브러리를 처음 만날 때
// 의존성을 다시 묶으며 페이지를 새로고침해서, 테스트가 중간에 날아갔다. 배포 조건이 더 의미 있기도 하다.
// 데모 모드(서버 없음): --mode e2e는 .env.development(개발용 API 주소)를 읽지 않는다.
export default defineConfig({
  testDir: 'e2e',
  timeout: 90_000,
  workers: 1,
  use: { baseURL: 'http://localhost:5179', trace: 'retain-on-failure' },
  webServer: {
    command: 'npm run build -- --mode e2e && npx vite preview --port 5179 --strictPort',
    url: 'http://localhost:5179',
    reuseExistingServer: false,
    timeout: 240_000,
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'phone', use: { ...devices['Pixel 7'] } },
  ],
})
