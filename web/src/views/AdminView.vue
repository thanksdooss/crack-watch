<script setup lang="ts">
// 관리자: 신고 목록 · 상태 변경(사유 필수) · 지점 병합 · 걸러 낸 비율.
// 자동 보류는 '삭제'가 아니다. 여기서 사람이 되돌리거나 확정한다. 모든 조치는 사유와 함께 기록된다.
import { computed, ref } from 'vue'
import { API_URL, api, type AdminReport, type Stats } from '../lib/api'

const token = ref(sessionStorage.getItem('cw-admin') ?? '')
const reports = ref<AdminReport[]>([])
const stats = ref<Stats | null>(null)
const filter = ref('held')
const error = ref('')
const mergeKeep = ref<number | null>(null)
const mergeDrop = ref<number | null>(null)
const pct = (v: number | null) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`)

async function load() {
  error.value = ''
  sessionStorage.setItem('cw-admin', token.value)
  try {
    ;[reports.value, stats.value] = await Promise.all([api.adminReports(token.value, filter.value || undefined), api.stats(token.value)])
  } catch (e) {
    error.value = (e as Error).message
  }
}

async function act(r: AdminReport, action: string) {
  const reason = prompt(`신고 #${r.id}를 '${action}' 처리하는 사유를 적어 주세요 (필수)`)
  if (!reason || reason.trim().length < 2) return
  try { await api.adminAct(token.value, r.id, action, reason.trim()); await load() } catch (e) { error.value = (e as Error).message }
}

async function merge() {
  if (!mergeKeep.value || !mergeDrop.value) return
  try { await api.adminMerge(token.value, mergeKeep.value, mergeDrop.value); mergeKeep.value = mergeDrop.value = null; await load() } catch (e) { error.value = (e as Error).message }
}

const topReasons = computed(() => Object.entries(stats.value?.reason_counts ?? {}).sort((a, b) => b[1] - a[1]).slice(0, 8))
</script>

<template>
  <section>
    <h1>관리자</h1>
    <p v-if="!API_URL" class="warn">데모 모드(서버 없음)에서는 관리자 화면을 쓸 수 없습니다.</p>
    <div class="row">
      <input v-model="token" type="text" placeholder="관리자 토큰" style="max-width: 240px" data-testid="admin-token" />
      <select v-model="filter" style="min-height: 44px"><option value="held">자동 보류</option><option value="pending">접수</option><option value="merged">중복 병합</option><option value="accepted">확인</option><option value="rejected">반려</option><option value="">전체</option></select>
      <button class="primary" @click="load">불러오기</button>
    </div>
    <div v-if="error" class="warn">{{ error }}</div>

    <div v-if="stats" class="card" data-testid="stats">
      <h2 style="margin-top: 0">걸러 낸 비율</h2>
      <dl class="kv">
        <dt>전체 신고</dt><dd>{{ stats.total }}</dd>
        <dt>자동 보류율</dt><dd>{{ pct(stats.auto_held_rate) }}</dd>
        <dt>중복 병합률</dt><dd>{{ pct(stats.duplicate_rate) }}</dd>
        <dt>검토한 신고</dt><dd>{{ stats.reviewed }}</dd>
        <dt>오탐(반려) 비율</dt><dd>{{ pct(stats.false_report_rate) }} <span class="muted">검토한 것 중 반려</span></dd>
        <dt>보류 적중률</dt><dd>{{ pct(stats.held_precision) }} <span class="muted">자동 보류 → 사람도 반려</span></dd>
        <dt>통과 누수율</dt><dd>{{ pct(stats.pending_leak) }} <span class="muted">자동 통과 → 사람은 반려</span></dd>
      </dl>
      <p class="muted">많이 걸린 사유: {{ topReasons.map(([k, v]) => `${k} ${v}`).join(' · ') || '—' }}</p>
    </div>

    <div v-if="stats" class="card">
      <h2 style="margin-top: 0">지점 합치기</h2>
      <p class="muted">GPS가 크게 튀어 같은 균열이 두 지점으로 나뉜 경우.</p>
      <div class="row"><input v-model.number="mergeKeep" type="text" placeholder="남길 지점 번호" style="max-width: 140px" /><input v-model.number="mergeDrop" type="text" placeholder="합쳐 없앨 지점 번호" style="max-width: 160px" /><button @click="merge">합치기</button></div>
    </div>

    <div v-for="r in reports" :key="r.id" class="card" data-testid="admin-report">
      <div class="row" style="justify-content: space-between">
        <strong>#{{ r.id }} · {{ r.state }}</strong>
        <span class="muted">신뢰도 {{ r.trust_score.toFixed(2) }} · 지점 {{ r.site_id ?? '—' }}{{ r.duplicate_of ? ` · #${r.duplicate_of}의 중복` : '' }}</span>
      </div>
      <p class="muted">{{ new Date(r.captured_at).toLocaleString('ko-KR') }} · 폭 {{ r.max_width_mm?.toFixed(2) ?? '—' }}mm · {{ r.engine }} · 기기 {{ r.device }}</p>
      <ul v-if="r.trust_reasons.length" style="margin: 4px 0 8px 18px; padding: 0">
        <li v-for="x in r.trust_reasons" :key="x.code"><code>{{ x.code }}</code> {{ x.delta ? `(${x.delta > 0 ? '+' : ''}${x.delta})` : '' }} {{ x.detail }}</li>
      </ul>
      <p v-if="r.note">메모: {{ r.note }}</p>
      <div class="row">
        <button @click="act(r, 'accept')">확인</button><button @click="act(r, 'reject')">반려</button><button @click="act(r, 'close')">종료</button><button v-if="r.state !== 'pending'" @click="act(r, 'reopen')">되돌리기</button>
      </div>
    </div>
  </section>
</template>
