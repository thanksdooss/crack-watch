<script setup lang="ts">
// 같은 지점의 폭 변화. 점 하나가 아니라 오차 범위(세로 막대)를 같이 그린다 —
// 범위가 겹치면 '변화 없음'으로 읽어야 한다는 걸 눈으로 보이게.
import { computed } from 'vue'
import type { HistoryPoint } from '../lib/api'

const props = defineProps<{ points: HistoryPoint[]; expertMm: number }>()
const W = 560, H = 200, P = { l: 44, r: 12, t: 12, b: 28 }

const pts = computed(() => props.points.filter((p) => p.max_width_mm != null && p.max_width_ci_mm))
const tRange = computed(() => {
  const ts = pts.value.map((p) => +new Date(p.captured_at))
  const lo = Math.min(...ts), hi = Math.max(...ts)
  return [lo, hi === lo ? lo + 86400000 : hi]
})
const yMax = computed(() => Math.max(props.expertMm * 1.5, ...pts.value.map((p) => p.max_width_ci_mm![1])) * 1.1)
const x = (t: string) => P.l + ((+new Date(t) - tRange.value[0]) / (tRange.value[1] - tRange.value[0])) * (W - P.l - P.r)
const y = (v: number) => H - P.b - (v / yMax.value) * (H - P.t - P.b)
const fmtDate = (t: string) => new Date(t).toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' })
</script>

<template>
  <svg :viewBox="`0 0 ${W} ${H}`" role="img" aria-label="폭 변화 추이" style="width: 100%; height: auto">
    <line :x1="P.l" :x2="W - P.r" :y1="y(expertMm)" :y2="y(expertMm)" stroke="var(--expert)" stroke-dasharray="4 4" />
    <text :x="W - P.r" :y="y(expertMm) - 4" text-anchor="end" font-size="11" fill="var(--expert)">{{ expertMm }}mm 안내 기준</text>
    <line :x1="P.l" :x2="P.l" :y1="P.t" :y2="H - P.b" stroke="var(--line)" />
    <line :x1="P.l" :x2="W - P.r" :y1="H - P.b" :y2="H - P.b" stroke="var(--line)" />
    <text v-for="v in [0, yMax / 2, yMax]" :key="v" :x="P.l - 6" :y="y(v) + 4" text-anchor="end" font-size="11" fill="var(--muted)">{{ v.toFixed(1) }}</text>
    <polyline :points="pts.map((p) => `${x(p.captured_at)},${y(p.max_width_mm!)}`).join(' ')" fill="none" stroke="var(--accent)" stroke-width="1.5" />
    <g v-for="p in pts" :key="p.report_id">
      <line :x1="x(p.captured_at)" :x2="x(p.captured_at)" :y1="y(p.max_width_ci_mm![0])" :y2="y(p.max_width_ci_mm![1])" stroke="var(--accent)" stroke-width="6" stroke-opacity="0.25" stroke-linecap="round" />
      <circle :cx="x(p.captured_at)" :cy="y(p.max_width_mm!)" r="4" fill="var(--accent)" />
      <text :x="x(p.captured_at)" :y="H - 8" text-anchor="middle" font-size="11" fill="var(--muted)">{{ fmtDate(p.captured_at) }}</text>
    </g>
  </svg>
</template>
