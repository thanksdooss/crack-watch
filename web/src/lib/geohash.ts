// geohash — 위경도를 문자열로. 앞자리가 같을수록 가깝다. 서버가 근처 신고를 묶을 때 쓴다.
const BASE32 = '0123456789bcdefghjkmnpqrstuvwxyz'

export function encode(lat: number, lon: number, precision = 8): string {
  let latR = [-90, 90], lonR = [-180, 180]
  let hash = '', bit = 0, ch = 0, even = true
  while (hash.length < precision) {
    const r = even ? lonR : latR
    const v = even ? lon : lat
    const mid = (r[0] + r[1]) / 2
    if (v >= mid) { ch = (ch << 1) | 1; r[0] = mid } else { ch <<= 1; r[1] = mid }
    even = !even
    if (++bit === 5) { hash += BASE32[ch]; bit = 0; ch = 0 }
  }
  return hash
}
