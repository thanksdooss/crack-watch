// 서버 호출. 주소(VITE_API_URL)가 없으면 데모 모드 — 서버 없이 기기 안에서만 동작한다.
export const API_URL: string | undefined = import.meta.env.VITE_API_URL

/** 익명 기기 토큰 — 이 기기에서 만든 무작위 값. 개인을 식별하지 않지만, 도배·반복 반려를 걸러 내는 데 쓴다. */
export function deviceToken(): string {
  try {
    let t = localStorage.getItem('cw-device')
    if (!t) { t = crypto.randomUUID(); localStorage.setItem('cw-device', t) }
    return t
  } catch {
    return 'anonymous'
  }
}

async function call<T>(path: string, init: RequestInit = {}, admin?: string): Promise<T> {
  if (!API_URL) throw new Error('서버 주소가 설정되지 않은 데모 모드입니다')
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(init.headers as Record<string, string>) }
  if (admin) headers.Authorization = `Bearer ${admin}`
  const res = await fetch(`${API_URL}${path}`, { ...init, headers })
  if (!res.ok) throw new Error(`${res.status} ${await res.text().catch(() => '')}`.slice(0, 200))
  return res.json() as Promise<T>
}

export type Guidance = '관찰 필요' | '전문가 점검 권장' | '판정 보류'
export interface Site { id: number; lat: number; lon: number; status: string; report_count: number; latest_width_mm: number | null; trend: 'widening' | 'stable' | 'unknown'; guidance: Guidance }
export interface HistoryPoint { report_id: number; captured_at: string; state: string; max_width_mm: number | null; max_width_ci_mm: [number, number] | null; engine: string }
export interface SiteDetail extends Site { history: HistoryPoint[]; trend_detail: string }
export interface Reason { code: string; delta: number; detail: string }
export interface AdminReport { id: number; site_id: number | null; duplicate_of: number | null; state: string; trust_score: number; trust_reasons: Reason[]; captured_at: string; lat: number; lon: number; max_width_mm: number | null; engine: string; note: string; device: string }
export interface Stats { total: number; by_state: Record<string, number>; auto_held_rate: number; duplicate_rate: number; reviewed: number; false_report_rate: number | null; held_precision: number | null; pending_leak: number | null; reason_counts: Record<string, number> }

export const api = {
  sites: () => call<Site[]>('/sites'),
  site: (id: number) => call<SiteDetail>(`/sites/${id}`),
  postReport: (payload: unknown) => call<{ id: number; state: string }>('/reports', { method: 'POST', body: JSON.stringify(payload), headers: { 'X-Device-Token': deviceToken() } }),
  adminReports: (token: string, state?: string) => call<AdminReport[]>(`/admin/reports${state ? `?state=${state}` : ''}`, {}, token),
  adminAct: (token: string, id: number, action: string, reason: string) => call<AdminReport>(`/admin/reports/${id}/action`, { method: 'POST', body: JSON.stringify({ action, reason }) }, token),
  adminMerge: (token: string, keep: number, drop: number) => call<{ moved_reports: number }>(`/admin/sites/${keep}/merge/${drop}`, { method: 'POST' }, token),
  stats: (token: string) => call<Stats>('/admin/stats', {}, token),
}
