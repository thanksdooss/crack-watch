<script setup lang="ts">
import { ref } from 'vue'
import Disclaimer from '../report/Disclaimer.vue'

const emit = defineEmits<{ pick: [src: File | string, label: string] }>()
const base = import.meta.env.BASE_URL
const samples = ref<{ file: string; title: string; lighting: string }[]>([])
fetch(`${base}samples/samples.json`).then((r) => r.json()).then((s) => (samples.value = s)).catch(() => {})

function onFile(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) emit('pick', f, f.name)
}
</script>

<template>
  <section>
    <h1>균열 감시</h1>
    <p>벽면 사진에서 균열을 찾아 폭을 mm로 추정하고, 믿을 만한 신고만 모읍니다.</p>
    <p class="muted">사진은 이 기기 안에서만 분석됩니다. 서버로는 폭·위치 같은 숫자만 보냅니다.</p>

    <div class="card">
      <h2 style="margin-top: 0">1. 기준 카드 준비</h2>
      <p>
        <a :href="`${base}reference-card.pdf`" target="_blank" rel="noopener">기준 카드(PDF)</a>를
        <strong>100% 배율</strong>로 인쇄해, 균열 바로 옆 <strong>같은 벽면</strong>에 평평하게 붙이세요.
        카드가 있어야 폭(mm)과 색을 믿을 수 있습니다.
      </p>
      <p class="muted">카드의 60mm 막대를 자로 재서 정확히 60mm인지 확인하세요. 인쇄가 줄어들면 모든 폭이 틀어집니다.</p>
    </div>

    <div class="card">
      <h2 style="margin-top: 0">2. 사진 찍기</h2>
      <p class="muted">균열과 카드 전체가 한 장에 들어오게, 벽을 정면에서 찍어 주세요.</p>
      <label class="button primary" style="margin-top: 8px">
        사진 찍기 / 고르기
        <input type="file" accept="image/*" capture="environment" hidden data-testid="file-input" @change="onFile" />
      </label>
    </div>

    <div class="card">
      <h2 style="margin-top: 0">샘플로 체험하기</h2>
      <p class="muted">로그인 없이 바로 결과 화면을 볼 수 있습니다. 샘플은 <strong>합성 이미지</strong>입니다(실제 건물 사진 아님).</p>
      <div class="samples">
        <button v-for="s in samples" :key="s.file" :data-testid="`sample-${s.file}`" @click="emit('pick', `${base}samples/${s.file}`, s.title)">
          <img :src="`${base}samples/${s.file}`" :alt="s.title" loading="lazy" />
          <span>{{ s.title }}</span>
        </button>
      </div>
    </div>

    <Disclaimer />
  </section>
</template>
