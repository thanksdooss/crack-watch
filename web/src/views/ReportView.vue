<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Analysis } from '../vision/analyze'
import { encode } from '../lib/geohash'
import { API_URL, flush, put } from '../lib/queue'

const props = defineProps<{ result: Analysis }>()
const emit = defineEmits<{ done: []; back: [] }>()

const consentLocation = ref(false)
const note = ref('')
const status = ref<'idle' | 'locating' | 'saved' | 'sent' | 'error'>('idle')
const message = ref('')
const r = computed(() => props.result)

function locate(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) =>
    navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 15000 }))
}

async function submit() {
  if (!consentLocation.value) return
  status.value = 'locating'
  let pos: GeolocationPosition
  try {
    pos = await locate()
  } catch {
    status.value = 'error'
    message.value = '위치를 가져오지 못했습니다. 위치 권한을 확인해 주세요.'
    return
  }
  const { latitude: lat, longitude: lon, accuracy } = pos.coords
  const client_uuid = crypto.randomUUID()
  // 서버 계약: api/app/schemas.py ReportIn. 사진은 넣지 않는다.
  const payload = {
    schema_version: 1,
    client_uuid,
    captured_at: new Date().toISOString(),
    location: { lat, lon, accuracy_m: accuracy, geohash: encode(lat, lon, 8) },
    calibration: {
      patch_found: !!r.value.card,
      delta_e_after: r.value.correction?.residualDeltaE ?? null,
      quality: r.value.correction?.quality ?? 'poor',
    },
    detection: {
      engine: r.value.engine,
      cracks: r.value.cracks
        .filter((c) => Number.isFinite(c.width.representativeMm))
        .slice(0, 16)
        .map((c) => ({
          width_mm: c.width.representativeMm,
          width_ci_mm: c.width.ciMm,
          length_mm: r.value.card ? c.lengthPx / r.value.card.pxPerMm : 0,
          orientation_deg: orientation(c.polyline),
          polyline: c.polyline,
          confidence: r.value.card ? 0.7 : 0.3,
        })),
    },
    image_meta: { w: r.value.w, h: r.value.h, blur_score: r.value.blurScore, exif_stripped: true },
    phash: r.value.phash,
    note: note.value.slice(0, 500),
    consent_image_upload: false,
  }
  await put({ client_uuid, payload, state: 'queued', createdAt: new Date().toISOString() })
  const sent = await flush()
  status.value = sent ? 'sent' : 'saved'
  message.value = sent
    ? '신고를 보냈습니다. 검토 결과는 신고 목록에서 확인할 수 있습니다.'
    : API_URL ? '기기에 저장했습니다. 인터넷이 연결되면 자동으로 보냅니다.' : '데모 모드: 서버 없이 이 기기에만 저장했습니다.'
}

function orientation(poly: [number, number][]): number {
  if (poly.length < 2) return 0
  const [a, b] = [poly[0], poly[poly.length - 1]]
  return ((Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI + 180) % 180
}
</script>

<template>
  <section>
    <div class="row"><button @click="emit('back')">← 결과로</button></div>
    <h1>신고하기</h1>
    <div class="card">
      <h2 style="margin-top: 0">보내는 것</h2>
      <p>균열 폭·길이·모양(선), 기준 카드와 색 보정 상태, 사진의 지각 해시(중복 확인용), 위치, 메모.</p>
      <h2>보내지 않는 것</h2>
      <p><strong>사진 원본.</strong> 사진은 이 기기에만 남습니다. 지각 해시로 사진을 되살릴 수는 없지만, 같은 장면인지는 알아볼 수 있습니다.</p>
    </div>

    <label class="check">
      <input v-model="consentLocation" type="checkbox" data-testid="consent-location" />
      <span>현재 위치를 함께 보내는 데 동의합니다. <span class="muted">같은 곳의 신고를 묶고 시간에 따른 변화를 보려면 위치가 필요합니다. 위치 없이는 신고할 수 없습니다.</span></span>
    </label>
    <label>메모 (선택)
      <textarea v-model="note" rows="3" maxlength="500" placeholder="예: 1층 외벽 모서리, 지난달보다 길어진 것 같음" />
    </label>
    <p class="muted">주소·이름·전화번호 같은 개인정보는 적지 말아 주세요.</p>

    <div class="row" style="margin-top: 12px">
      <button class="primary" :disabled="!consentLocation || status === 'locating'" data-testid="submit-report" @click="submit">
        {{ status === 'locating' ? '위치 확인 중…' : '신고 보내기' }}
      </button>
    </div>
    <div v-if="message" :class="status === 'error' ? 'warn' : 'card'" data-testid="report-status">
      {{ message }}
      <div v-if="status === 'sent' || status === 'saved'" class="row" style="margin-top: 8px"><button @click="emit('done')">처음으로</button></div>
    </div>
  </section>
</template>
