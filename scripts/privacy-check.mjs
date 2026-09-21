// 빌드 결과물(dist)에 공개하면 안 되는 단어가 있는지 검사한다.
// 검사어 목록 자체가 비공개 정보이므로 저장소에 두지 않고
//   - 로컬: .privacy-terms 파일 (한 줄에 하나, .gitignore 처리)
//   - CI:   PRIVACY_TERMS 시크릿 (줄바꿈 또는 | 로 구분)
// '='로 시작하는 검사어는 대소문자를 구분하는 단어 단위 검사(짧은 약칭용)다. 예: =ABC
// 에서 읽는다. 텍스트 파일은 그대로, PDF는 텍스트 레이어를, 이미지는 메타데이터(EXIF 등)를 검사한다.
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs'
import { join, extname } from 'node:path'
import { inflateSync } from 'node:zlib'

const root = process.argv[2] || 'dist'
const raw = process.env.PRIVACY_TERMS || (existsSync('.privacy-terms') ? readFileSync('.privacy-terms', 'utf8') : '')
const terms = raw.split(/[\n|]/).map((s) => s.trim()).filter((s) => s && !s.startsWith('#'))

if (!terms.length) {
  const msg = '검사어가 없습니다(.privacy-terms 또는 PRIVACY_TERMS).'
  if (process.env.CI) { console.error('✗ ' + msg); process.exit(1) }
  console.warn('! ' + msg + ' 검사를 건너뜁니다.'); process.exit(0)
}

const walk = (d) => readdirSync(d).flatMap((f) => (statSync(join(d, f)).isDirectory() ? walk(join(d, f)) : [join(d, f)]))
const textExt = new Set(['.html', '.js', '.css', '.json', '.txt', '.svg', '.xml', '.webmanifest', '.map', '.md'])
const imgExt = new Set(['.webp', '.png', '.jpg', '.jpeg', '.gif'])

// PDF 스트림을 풀어 텍스트 후보를 만든다(FlateDecode만 처리, 나머지는 원문 그대로).
function pdfText(buf) {
  const s = buf.toString('latin1'); let out = s
  const re = /stream\r?\n/g; let m
  while ((m = re.exec(s))) {
    const start = m.index + m[0].length
    const end = s.indexOf('endstream', start)
    if (end < 0) break
    try { out += inflateSync(buf.subarray(start, end)).toString('latin1') } catch {}
  }
  return out
}
const variants = (t) => {
  const utf8 = Buffer.from(t, 'utf8')
  const u16be = Buffer.from(t, 'utf16le').swap16()
  const hex = u16be.toString('hex')
  return [utf8.toString('latin1'), utf8.toString('latin1').toLowerCase(), u16be.toString('latin1'), hex, hex.toUpperCase()]
}

let hits = 0, files = 0
for (const f of walk(root)) {
  const ext = extname(f).toLowerCase(); files++
  const buf = readFileSync(f)
  let hay
  if (textExt.has(ext)) hay = buf.toString('utf8')
  else if (ext === '.pdf') hay = pdfText(buf)
  else if (imgExt.has(ext)) hay = buf.toString('latin1')
  else continue
  for (const t of terms) {
    if (t.startsWith('=')) {
      if (!textExt.has(ext)) continue // 짧은 약칭은 이미지·PDF 바이너리에서 우연히 일치하므로 텍스트 파일만 검사
      const w = t.slice(1).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      if (new RegExp(`(^|[^A-Za-z0-9_])${w}([^A-Za-z0-9_]|$)`).test(hay)) {
        console.error(`✗ ${f}: 검사어 #${terms.indexOf(t) + 1} 발견`); hits++
      }
      continue
    }
    const probes = textExt.has(ext) ? [t, t.toLowerCase()] : variants(t)
    const low = hay.toLowerCase()
    if (probes.some((p) => hay.includes(p) || low.includes(p.toLowerCase()))) {
      console.error(`✗ ${f}: 검사어 #${terms.indexOf(t) + 1} 발견`); hits++
    }
  }
  if (imgExt.has(ext) && /Exif\0\0|<x:xmpmeta|GPS/.test(buf.subarray(0, 4096).toString('latin1'))) {
    console.error(`✗ ${f}: 이미지 메타데이터(EXIF/XMP) 남아 있음`); hits++
  }
}
console.log(`${files}개 파일, 검사어 ${terms.length}개 → ${hits ? hits + '건 발견' : '0건'}`)
process.exit(hits ? 1 : 0)
