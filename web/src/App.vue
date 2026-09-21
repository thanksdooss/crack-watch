<script setup lang="ts">
import { ref, shallowRef } from 'vue'
import { loadImage, runAnalysis } from './lib/analyzer'
import type { Analysis } from './vision/analyze'
import HomeView from './views/HomeView.vue'
import ReportView from './views/ReportView.vue'
import ResultView from './views/ResultView.vue'

type View = 'home' | 'analyzing' | 'result' | 'report'
const view = ref<View>('home')
const progress = ref('')
const error = ref('')
const label = ref('')
const result = shallowRef<Analysis | null>(null)
const useModel = ref(true)

async function pick(src: File | string, name: string) {
  error.value = ''
  label.value = name
  view.value = 'analyzing'
  progress.value = '사진 읽는 중'
  try {
    const img = await loadImage(src)
    result.value = await runAnalysis(img, useModel.value, (s) => (progress.value = s))
    view.value = 'result'
  } catch (e) {
    error.value = `분석하지 못했습니다: ${(e as Error).message}`
    view.value = 'home'
  }
}
</script>

<template>
  <main>
    <div v-if="error" class="warn" role="alert">{{ error }}</div>
    <HomeView v-if="view === 'home'" @pick="pick" />
    <section v-else-if="view === 'analyzing'" class="card" aria-live="polite" data-testid="analyzing">
      <p><strong>{{ progress }}…</strong></p>
      <p class="muted">기준 카드 찾기 → 색 보정 → 균열 찾기 → 폭 재기. 사진은 이 기기 밖으로 나가지 않습니다.</p>
    </section>
    <ResultView v-else-if="view === 'result' && result" :result="result" :label="label" @back="view = 'home'" @report="view = 'report'" />
    <ReportView v-else-if="view === 'report' && result" :result="result" @back="view = 'result'" @done="view = 'home'" />
    <footer class="muted" style="margin: 32px 0 8px; font-size: 0.85rem">
      <label class="check"><input v-model="useModel" type="checkbox" /> 학습 모델 사용 (끄면 고전 영상처리만)</label>
      전문가 진단을 대신하지 않습니다 · 데이터셋 출처와 한계는 저장소 README 참고
    </footer>
  </main>
</template>
