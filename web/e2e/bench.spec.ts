// 처리 시간 측정 — `npm run bench`. 보통 E2E(`npm run e2e`)에서는 빠진다(@bench).
// 데스크톱 브라우저 실측만 한다. 처음엔 CPU 4배 감속(크롬 CPU 스로틀링)으로 휴대폰을 근사하려
// 했는데, 감속은 메인 스레드에만 걸리고 웹 워커(분석이 도는 곳)에는 걸리지 않았다 — 감속했는데
// 오히려 빨라진 측정값이 나왔다. 휴대폰 시간은 실기기에서 재야 한다.
import { expect, test } from '@playwright/test'
import { writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const SAMPLES = ['wall-daylight.jpg', 'wall-fluorescent.jpg', 'wall-tungsten.jpg']
const RUNS = 3

function parseTimings(text: string): Record<string, number> {
  const out: Record<string, number> = {}
  for (const m of text.matchAll(/(\w[\w+]*) (\d+)/g)) out[m[1]] = Number(m[2])
  return out
}

test('@bench 처리 시간', async ({ page, browserName }, info) => {
  test.setTimeout(900_000)
  const rows: Record<string, unknown>[] = []
  for (const throttle of [1]) {
    for (const useModel of [false, true]) {
      await page.goto('/')
      const cdp = await page.context().newCDPSession(page)
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: throttle })
      const box = page.locator('footer input[type=checkbox]')
      if ((await box.isChecked()) !== useModel) await box.click()
      for (const s of SAMPLES) {
        for (let r = 0; r < RUNS; r++) {
          await page.getByTestId(`sample-${s}`).click()
          await expect(page.getByTestId('summary')).toBeVisible({ timeout: 300_000 })
          const dd = await page.locator('dl.kv dd').last().innerText()
          const total = Number(dd.match(/^(\d+) ms/)?.[1])
          rows.push({ throttle, engine: useModel ? 'model' : 'classic', sample: s, run: r, total, ...parseTimings(dd.split('(')[1] ?? '') })
          await page.getByRole('button', { name: '← 처음으로' }).click()
        }
      }
    }
  }
  const out = { browser: `${browserName} ${page.context().browser()?.version()}`, project: info.project.name, runs: RUNS, rows }
  writeFileSync(resolve(import.meta.dirname, '../../docs/results/perf-browser.json'), JSON.stringify(out, null, 1) + '\n')
})
