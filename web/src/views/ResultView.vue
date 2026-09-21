<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import type { Analysis } from '../vision/analyze'
import { judgeSignColor } from '../vision/sign'
import { applyToImage } from '../vision/preprocess/color'
import type { SignJudgement } from '../vision/sign'
import Disclaimer from '../report/Disclaimer.vue'

const props = defineProps<{ result: Analysis; label: string }>()
const emit = defineEmits<{ back: []; report: [] }>()

const canvas = ref<HTMLCanvasElement>()
const showMask = ref(true)
const corrected = ref(true)
const display = computed(() => (corrected.value && props.result.correction ? applyToImage(props.result.correction, props.result.rgb) : props.result.rgb))
const signMode = ref(false)
const sign = ref<SignJudgement | null>(null)

const r = computed(() => props.result)
const o = computed(() => r.value.overall)
const badgeClass = computed(() => ({ '전문가 점검 권장': 'expert', '관찰 필요': 'observe', '판정 보류': 'hold' })[o.value.guidance])
const fmt = (v: number, d = 2) => (Number.isFinite(v) ? v.toFixed(d) : '—')

function draw() {
  const c = canvas.value
  if (!c) return
  const { w, h, mask, card } = r.value
  c.width = w
  c.height = h
  const ctx = c.getContext('2d')!
  const img = ctx.createImageData(w, h)
  const [cr, cg, cb] = getComputedStyle(document.documentElement).getPropertyValue('--crack').split(',').map(Number)
  const px = display.value
  for (let i = 0, j = 0; i < w * h; i++, j += 4) {
    let R = px[i * 3], G = px[i * 3 + 1], B = px[i * 3 + 2]
    if (showMask.value && mask.data[i]) { R = R * 0.25 + cr * 0.75; G = G * 0.25 + cg * 0.75; B = B * 0.25 + cb * 0.75 }
    img.data[j] = R; img.data[j + 1] = G; img.data[j + 2] = B; img.data[j + 3] = 255
  }
  ctx.putImageData(img, 0, 0)
  if (card) {
    const H = card.H
    const P = (x: number, y: number) => { const z = H[6] * x + H[7] * y + H[8]; return [(H[0] * x + H[1] * y + H[2]) / z, (H[3] * x + H[4] * y + H[5]) / z] }
    ctx.strokeStyle = '#1f9d55'
    ctx.lineWidth = Math.max(2, w / 400)
    ctx.beginPath()
    for (const [x, y] of [[0, 0], [90, 0], [90, 56], [0, 56], [0, 0]]) { const [px, py] = P(x, y); ctx.lineTo(px, py) }
    ctx.stroke()
  }
}

function onTap(e: MouseEvent) {
  if (!signMode.value || !canvas.value) return
  const rect = canvas.value.getBoundingClientRect()
  const x = Math.round(((e.clientX - rect.left) / rect.width) * r.value.w)
  const y = Math.round(((e.clientY - rect.top) / rect.height) * r.value.h)
  // 원본 픽셀에서 읽고 보정은 판정 함수가 한다 — 화면의 색은 이미 보정된 것이므로
  sign.value = judgeSignColor(r.value.rgb, r.value.w, r.value.h, x, y, r.value.correction, Math.max(3, Math.round(r.value.w / 200)))
}

onMounted(draw)
watch([showMask, corrected, () => props.result], draw)
</script>

<template>
  <section>
    <div class="row"><button @click="emit('back')">← 처음으로</button><span class="muted">{{ label }}</span></div>

    <div class="card" data-testid="summary">
      <div class="row" style="justify-content: space-between">
        <span :class="['badge', badgeClass]" data-testid="guidance">{{ o.guidance }}</span>
        <span class="muted">분석 엔진: <span data-testid="engine">{{ r.engine }}</span></span>
      </div>
      <p v-if="Number.isFinite(o.representativeMm)" style="font-size: 1.25rem; margin-top: 10px" data-testid="width">
        대표 폭 약 <strong>{{ fmt(o.representativeMm) }} mm</strong>
        <span class="muted">(추정 범위 {{ fmt(o.ciMm[0]) }} ~ {{ fmt(o.ciMm[1]) }} mm)</span>
      </p>
      <p v-else-if="r.mask.data.some((v) => v)" style="margin-top: 10px">균열로 보이는 부분은 표시했지만, 폭(mm)은 잴 수 없습니다.</p>
      <p v-else style="margin-top: 10px" data-testid="no-crack">이 사진에서는 균열을 찾지 못했습니다.</p>
      <ul style="margin: 6px 0 0 18px; padding: 0">
        <li v-for="(t, i) in o.reasons" :key="i">{{ t }}</li>
      </ul>
    </div>

    <div v-for="(w, i) in r.warnings" :key="i" class="warn" data-testid="warning">{{ w }}</div>

    <canvas ref="canvas" class="view" :style="{ cursor: signMode ? 'crosshair' : 'default' }" data-testid="result-canvas" @click="onTap" />
    <div class="row" style="margin-top: 8px">
      <label class="check" style="margin: 0"><input v-model="showMask" type="checkbox" /> 균열 표시</label>
      <label v-if="r.correction" class="check" style="margin: 0"><input v-model="corrected" type="checkbox" data-testid="toggle-corrected" /> 색 보정 적용</label>
      <button :class="{ primary: signMode }" data-testid="sign-mode" @click="signMode = !signMode; sign = null">
        {{ signMode ? '표지를 눌러 주세요' : '표지 색 확인' }}
      </button>
    </div>
    <div v-if="sign" class="card" data-testid="sign-result">
      <p><strong>{{ sign.towards }}</strong> <span class="muted">— {{ sign.note }}</span></p>
      <div class="row">
        <span :style="{ display: 'inline-block', width: '28px', height: '28px', borderRadius: '6px', border: '1px solid var(--line)', background: `rgb(${sign.corrected.map((v) => Math.round(v * 255)).join(',')})` }" />
        <span class="muted" v-if="Number.isFinite(sign.deltaERed)">빨강 기준과 색차 {{ fmt(sign.deltaERed, 1) }}, 파랑 기준과 {{ fmt(sign.deltaEBlue, 1) }}</span>
      </div>
      <p class="muted">기준 색은 가정한 값입니다. 표지(필름)의 실제 성능을 판정하지 않습니다.</p>
    </div>

    <div class="card">
      <h2 style="margin-top: 0">측정 근거</h2>
      <dl class="kv">
        <dt>기준 카드</dt>
        <dd>{{ r.card ? `찾음 · ${fmt(r.card.pxPerMm)} px/mm · 비스듬함 ${fmt(r.card.anisotropy * 100, 1)}%` : '못 찾음' }}</dd>
        <dt>색 보정</dt>
        <dd>{{ r.correction ? `${r.correction.quality} (보정 후 무채색 오차 ΔE ${fmt(r.correction.residualDeltaE, 1)})` : '안 함' }}</dd>
        <dt>균열 수</dt>
        <dd>{{ r.cracks.length }}</dd>
        <dt>흐림 점수</dt>
        <dd>{{ fmt(r.blurScore) }} <span class="muted">(0 선명 · 1 흐림)</span></dd>
        <dt>처리 시간</dt>
        <dd>{{ Object.values(r.timings).reduce((a, b) => a + b, 0) }} ms <span class="muted">({{ Object.entries(r.timings).map(([k, v]) => `${k} ${v}`).join(' · ') }})</span></dd>
      </dl>
      <details v-if="r.cracks.length">
        <summary>균열별 폭</summary>
        <ol>
          <li v-for="(c, i) in r.cracks.slice(0, 8)" :key="i">
            {{ Number.isFinite(c.width.representativeMm) ? `${fmt(c.width.representativeMm)} mm (${fmt(c.width.ciMm[0])}~${fmt(c.width.ciMm[1])})` : '폭 환산 불가' }}
            · 길이 {{ r.card ? `${fmt(c.lengthPx / r.card.pxPerMm, 0)} mm` : `${c.lengthPx} px` }}
          </li>
        </ol>
      </details>
    </div>

    <div class="row">
      <button class="primary" :disabled="!r.cracks.length" data-testid="report-button" @click="emit('report')">이 결과로 신고하기</button>
    </div>
    <Disclaimer />
  </section>
</template>
