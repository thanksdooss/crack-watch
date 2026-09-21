// README용 화면 캡처 — `npx playwright test --grep @shots`. 합성 샘플만 쓴다(실제 건물 사진 아님).
import { expect, test } from '@playwright/test'
import { resolve } from 'node:path'

const OUT = resolve(import.meta.dirname, '../../docs/assets')

test('@shots 결과 화면', async ({ page }, info) => {
  await page.goto('/')
  await page.screenshot({ path: `${OUT}/home-${info.project.name}.png`, fullPage: false })
  await page.getByTestId('sample-wall-tungsten.jpg').click()
  await expect(page.getByTestId('summary')).toBeVisible({ timeout: 80_000 })
  await expect(page.getByTestId('engine')).toHaveText(/^model@/)
  await page.screenshot({ path: `${OUT}/result-${info.project.name}.png`, fullPage: false })
  await page.getByTestId('toggle-corrected').uncheck()
  await page.getByTestId('result-canvas').screenshot({ path: `${OUT}/before-correction.png` })
  await page.getByTestId('toggle-corrected').check()
  await page.getByTestId('result-canvas').screenshot({ path: `${OUT}/after-correction.png` })
})
