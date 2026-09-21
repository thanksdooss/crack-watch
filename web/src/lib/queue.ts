// 신고 대기열 — 먼저 기기(IndexedDB)에 쓰고, 네트워크가 되면 보낸다.
// 지하·외진 곳에서 찍고 나중에 올리는 게 실제 사용 패턴이라 부가 기능이 아니다.
// 서버는 client_uuid로 중복 전송을 걸러낸다(멱등).
export interface QueuedReport {
  client_uuid: string
  payload: Record<string, unknown>
  state: 'queued' | 'sent' | 'failed'
  response?: unknown
  createdAt: string
}

const DB = 'crack-watch'
const STORE = 'reports'

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1)
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'client_uuid' })
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function tx<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open()
  return new Promise((resolve, reject) => {
    const r = fn(db.transaction(STORE, mode).objectStore(STORE))
    r.onsuccess = () => resolve(r.result)
    r.onerror = () => reject(r.error)
  })
}

export const put = (r: QueuedReport) => tx('readwrite', (s) => s.put(r))
export const all = () => tx<QueuedReport[]>('readonly', (s) => s.getAll() as IDBRequest<QueuedReport[]>)

import { API_URL, api } from './api'
export { API_URL }

/** 대기 중인 신고를 보낸다. 서버 주소가 없으면(데모) 기기에만 남는다. */
export async function flush(): Promise<number> {
  if (!API_URL || !navigator.onLine) return 0
  let sent = 0
  for (const r of await all()) {
    if (r.state === 'sent') continue
    try {
      await put({ ...r, state: 'sent', response: await api.postReport(r.payload) })
      sent++
    } catch {
      await put({ ...r, state: 'failed' })
    }
  }
  return sent
}
