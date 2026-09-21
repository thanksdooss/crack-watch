import { expect, type Page, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const samples = JSON.parse(readFileSync(resolve(import.meta.dirname, '../public/samples/samples.json'), 'utf8'))
const TUNGSTEN = samples.find((s: { file: string }) => s.file === 'wall-tungsten.jpg')

async function setModel(page: Page, on: boolean) {
  const box = page.locator('footer input[type=checkbox]')
  if ((await box.isChecked()) !== on) await box.click()
}

test.describe('사진 → 결과', () => {
  test('샘플(고전 CV): 카드 찾기·색 보정·안내 문구·고지', async ({ page }) => {
    await page.goto('/')
    await setModel(page, false)
    await page.getByTestId('sample-wall-tungsten.jpg').click()
    await expect(page.getByTestId('summary')).toBeVisible({ timeout: 60_000 })
    await expect(page.getByTestId('engine')).toHaveText(/^classic@/)
    await expect(page.getByTestId('guidance')).toHaveText(/관찰 필요|전문가 점검 권장|판정 보류/)
    await expect(page.getByTestId('disclaimer').first()).toContainText('전문가 진단이 아닙니다')
    await expect(page.getByText(/찾음 · [\d.]+ px\/mm/)).toBeVisible()
    await expect(page.getByText(/^good/)).toBeVisible()
    // 안전을 단정하는 문장이 없어야 한다
    const body = await page.locator('main').innerText()
    expect(body).not.toMatch(/안전합니다|위험합니다|붕괴 위험/)
  })

  test('샘플(모델): 폭 추정 범위가 정답 근처', async ({ page }) => {
    await page.goto('/')
    await setModel(page, true)
    await page.getByTestId('sample-wall-tungsten.jpg').click()
    await expect(page.getByTestId('summary')).toBeVisible({ timeout: 80_000 })
    await expect(page.getByTestId('engine')).toHaveText(/^model@/)
    const text = await page.getByTestId('width').innerText()
    const [lo, hi] = [...text.matchAll(/([\d.]+) ~ ([\d.]+)/g)][0].slice(1).map(Number)
    // 합성 샘플의 폭은 평균 2.2mm에 ±20% 흔들림 → 대표값(상위 90%)은 약 2.2~2.7mm
    expect(lo).toBeLessThan(TUNGSTEN.trueWidthMm * 1.25)
    expect(hi).toBeGreaterThan(TUNGSTEN.trueWidthMm)
  })

  test('파일 올리기로도 분석된다', async ({ page }) => {
    await page.goto('/')
    await setModel(page, false)
    await page.getByTestId('file-input').setInputFiles(resolve(import.meta.dirname, '../public/samples/wall-daylight.jpg'))
    await expect(page.getByTestId('summary')).toBeVisible({ timeout: 60_000 })
  })
})

test('분석하는 동안 사진이 네트워크로 나가지 않는다', async ({ page }) => {
  const outgoing: string[] = []
  page.on('request', (r) => {
    if (r.method() !== 'GET') outgoing.push(`${r.method()} ${r.url()} ${r.postData()?.length ?? 0}`)
  })
  await page.goto('/')
  await setModel(page, true)
  await page.getByTestId('file-input').setInputFiles(resolve(import.meta.dirname, '../public/samples/wall-fluorescent.jpg'))
  await expect(page.getByTestId('summary')).toBeVisible({ timeout: 80_000 })
  expect(outgoing).toEqual([])
})

test('신고: 위치 동의 없이는 보낼 수 없고, 데모 모드는 기기에만 저장', async ({ page, context }) => {
  await context.grantPermissions(['geolocation'])
  await context.setGeolocation({ latitude: 37.5665, longitude: 126.978, accuracy: 10 })
  await page.goto('/')
  await setModel(page, false)
  await page.getByTestId('sample-wall-fluorescent.jpg').click()
  await expect(page.getByTestId('summary')).toBeVisible({ timeout: 60_000 })
  await page.getByTestId('report-button').click()
  await expect(page.getByTestId('submit-report')).toBeDisabled()
  await page.getByTestId('consent-location').check()
  await page.getByTestId('submit-report').click()
  await expect(page.getByTestId('report-status')).toContainText('데모 모드')
})
