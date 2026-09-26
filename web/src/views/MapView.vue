<script setup lang="ts">
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import pipeline from '@shared/pipeline.json'
import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { API_URL, api, type Site, type SiteDetail } from '../lib/api'
import Disclaimer from '../report/Disclaimer.vue'
import HistoryChart from './HistoryChart.vue'

const el = ref<HTMLDivElement>()
const map = shallowRef<L.Map>()
const sites = ref<Site[]>([])
const selected = ref<SiteDetail | null>(null)
const error = ref('')
const loading = ref(true)
const slow = ref(false)
const color = (g: string) => (g === '전문가 점검 권장' ? '#b3261e' : g === '관찰 필요' ? '#2e6b3a' : '#6b6b6b')

async function select(id: number) {
  try { selected.value = await api.site(id) } catch (e) { error.value = (e as Error).message }
}

onMounted(async () => {
  map.value = L.map(el.value!, { zoomControl: true }).setView([37.5665, 126.978], 13)
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap contributors' }).addTo(map.value)
  if (!API_URL) {
    error.value = '데모 모드(서버 없음)라 지도에 올릴 신고가 없습니다.'
    loading.value = false
    return
  }
  // 무료 서버는 잠들어 있으면 깨는 데 1분쯤 걸린다. 기다리는 이유를 화면에 알린다.
  const slowTimer = setTimeout(() => (slow.value = true), 3000)
  try {
    sites.value = await api.sites()
    const bounds: [number, number][] = []
    for (const s of sites.value) {
      L.circleMarker([s.lat, s.lon], { radius: 9, color: color(s.guidance), fillOpacity: 0.7, weight: 2 })
        .addTo(map.value).on('click', () => select(s.id))
        .bindTooltip(`${s.guidance} · 신고 ${s.report_count}건${s.trend === 'widening' ? ' · 넓어지는 중' : ''}`)
      bounds.push([s.lat, s.lon])
    }
    if (bounds.length) map.value.fitBounds(bounds, { padding: [40, 40], maxZoom: 17 })
  } catch (e) {
    error.value = `지점을 불러오지 못했습니다: ${(e as Error).message}. 잠시 뒤 새로고침해 보세요.`
  } finally {
    clearTimeout(slowTimer)
    loading.value = false
    slow.value = false
  }
})
onBeforeUnmount(() => map.value?.remove())
</script>

<template>
  <section>
    <h1>지도와 이력</h1>
    <p class="muted">같은 지점의 신고를 묶어 폭 변화를 봅니다. 점을 누르면 이력이 나옵니다.</p>
    <div v-if="error" class="warn">{{ error }}</div>
    <p v-else-if="loading" class="muted" aria-live="polite" data-testid="map-loading">
      신고를 불러오는 중…<span v-if="slow"> 무료 서버가 잠들어 있으면 깨어나는 데 1분쯤 걸립니다.</span>
    </p>
    <div ref="el" style="height: 360px; border-radius: 12px; border: 1px solid var(--line)" data-testid="map" />
    <div class="row muted" style="margin-top: 6px; font-size: 0.85rem">
      <span><span style="color: #b3261e">●</span> 전문가 점검 권장</span><span><span style="color: #2e6b3a">●</span> 관찰 필요</span><span><span style="color: #6b6b6b">●</span> 판정 보류</span>
    </div>
    <div v-if="selected" class="card" data-testid="site-detail">
      <div class="row" style="justify-content: space-between">
        <strong>지점 #{{ selected.id }}</strong>
        <span :class="['badge', selected.guidance === '전문가 점검 권장' ? 'expert' : selected.guidance === '관찰 필요' ? 'observe' : 'hold']">{{ selected.guidance }}</span>
      </div>
      <p>{{ selected.trend_detail }}</p>
      <HistoryChart :points="selected.history" :expert-mm="pipeline.measure.guidance.expertReviewMm" />
      <p class="muted">세로 막대는 오차 범위입니다. 두 시점의 범위가 겹치면 '넓어졌다'고 말할 수 없습니다.</p>
    </div>
    <Disclaimer />
  </section>
</template>
