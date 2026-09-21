# 01. 아키텍처

작성 2026-09-21. 2단계 결과물. 앞 단계: [`00-approach.md`](00-approach.md).

## 1. 한 장 그림

```
[시민 스마트폰 — 브라우저(PWA)]
  사진 → 기준 패치 검출 → 색 보정 → 원근 보정
       → 균열 검출 (고전 CV | ONNX 모델)
       → 중심선 + 단면 폭(px) → 기준 물체 스케일 → 폭(mm ± 오차)
       → 지표만 추출 (이미지는 기기에 남음)
                    │
                    │  HTTPS  (기본 모드: 이미지 없음)
                    ▼
[API — FastAPI]
  신고 접수 → 검증 파이프라인(중복·정합성·신뢰도) → 보류/접수
                    │
                    ▼
[PostgreSQL (+PostGIS 선택)]
  지점(site) · 신고(report) · 관측(observation) · 검토 이력
                    │
                    ▼
[관리자 화면]  목록 · 중복 병합 · 상태 전이 · 오탐 비율
```

**기기 안에서 끝나는 것**: 색 보정, 검출, 폭 추정, 품질 판단, 지각 해시 계산.
**서버로 가는 것**: 숫자와 해시. 기본 모드에서 원본 사진은 전송하지 않는다.

## 2. 디렉터리

```
web/                  Vue 3 + TypeScript + Vite (PWA)
  src/
    vision/
      preprocess/     기준 패치 검출, 화이트밸런스 정규화, 원근 보정
      classic/        OpenCV.js 기준선 파이프라인
      model/          ONNX Runtime Web 세션, 타일링, 폴백 전략
      worker/         Web Worker 진입점 (UI 스레드 차단 방지)
    measure/          스켈레톤, 단면 폭 추정, px→mm 환산, 오차 전파
    report/           제보 작성 폼, 지도, 이력 비교
    lib/              IndexedDB 큐, 지각 해시, 위치 처리
api/                  FastAPI + SQLAlchemy + Alembic
  app/
    routers/          reports, sites, admin
    verify/           검증 규칙 (중복·정합성·신뢰도 점수)
    models/           ORM
ml/                   학습·평가 스크립트 (노트북 아님)
  datasets/           다운로드·전처리 (이미지 자체는 저장소에 없음)
  train/              학습
  eval/               IoU·P/R/F1, 기준선 대비 비교
  export/             ONNX 변환·양자화·검증
shared/
  pipeline.json       전처리 파라미터 단일 정의 (웹·파이썬 공용)
  fixtures/           골든 테스트용 고정 입력·기대 출력
docs/
```

## 3. 핵심 결정 1 — 서버는 이미지를 받지 않는 것이 기본값

### 보내는 것 (기본 모드 페이로드)

```jsonc
{
  "schemaVersion": 1,
  "capturedAt": "2026-09-21T04:12:33Z",
  "location": { "lat": 37.5665, "lon": 126.9780, "accuracyM": 12, "geohash": "wydm9qy8" },
  "calibration": {
    "patchFound": true,        // 기준 패치를 찾았는가
    "deltaEAfter": 2.4,        // 보정 후 잔차 색차
    "quality": "good"          // good | fair | poor
  },
  "detection": {
    "engine": "model@0.3.1-int8",   // 또는 classic@0.3.1
    "cracks": [
      {
        "widthMm": 0.84, "widthCiMm": [0.62, 1.10],  // 오차 범위를 항상 같이
        "lengthMm": 312, "orientationDeg": 71,
        "polyline": [[0.12,0.33],[0.14,0.41]],        // 정규화 좌표, 최대 32점
        "confidence": 0.78
      }
    ]
  },
  "imageMeta": { "w": 4032, "h": 3024, "blurScore": 0.31, "exifStripped": true },
  "phash": "9f3c1a7b52d6e084",   // 지각 해시 — 중복 판정용
  "note": "1층 외벽 모서리",
  "consentImageUpload": false
}
```

### 그러면 "같은 지점의 과거 사진과 비교"는 어떻게 하나

이 설계에서 제일 먼저 부딪힌 모순이다. 검증하려면 과거와 비교해야 하고, 비교하려면 뭔가를 남겨야 한다. 그래서 **원본 대신 비교에 필요한 최소 표현만** 남긴다.

- **같은 지점인가** → 위치 근접(geohash 접두 + 거리) + **지각 해시 해밍 거리**. 사진 없이 "비슷한 벽면인가"를 판정한다.
- **넓어졌는가** → 균열 중심선 폴리라인과 폭 값의 시계열. 형상 자체가 비교 대상이므로 이미지가 필요 없다.
- **이미지가 꼭 필요한 경우** → 사용자가 명시적으로 동의(`consentImageUpload: true`)한 건만 업로드. 이때도 EXIF(GPS 포함)를 기기에서 제거한 뒤 보내고, 접근은 관리자 화면으로 제한한다.

지각 해시는 원본 복원이 불가능한 축약이지만 **동일 장면 식별은 가능하다**. 즉 "프라이버시가 전혀 없다"가 아니라 "원본보다 훨씬 덜 민감한 표현"이다. 이 차이를 README에 정확히 쓴다. 과장하지 않는다.

## 4. 핵심 결정 2 — 전처리를 두 번 구현하면 조용히 무너진다

파이썬(학습)과 타입스크립트(브라우저 추론)가 각자 전처리를 구현하면, 리사이즈 보간 방식 하나만 달라도 현장 성능이 떨어진다. 그런데 **평가는 파이썬에서 하므로 그 손실이 지표에 안 잡힌다.** 조용히 무너지는 종류의 버그다.

대응:

1. **파라미터 단일 정의** — `shared/pipeline.json`에 입력 크기, 타일·겹침, 보간 방식, 정규화 상수, 색 변환 행렬을 적는다. 양쪽이 이 파일을 읽는다. 하드코딩 금지.
2. **골든 테스트** — `shared/fixtures/`에 고정 입력 이미지와 기대 텐서를 둔다. 파이썬 `pytest`와 웹 `vitest`가 같은 fixture로 각자 전처리를 돌려, 허용 오차 안에 드는지 검사한다. CI에서 둘 다 돌린다.
3. 파라미터를 바꾸면 fixture를 다시 생성해야 하고, 그러면 PR에서 변경이 눈에 보인다.

## 5. 웹 — 모듈 경계와 실행 모델

| 모듈 | 책임 | 의존 |
| --- | --- | --- |
| `vision/preprocess` | 기준 패치 찾기, 화이트밸런스 정규화, 원근 보정 | OpenCV.js |
| `vision/classic` | 기준선 검출 → 이진 마스크 | OpenCV.js |
| `vision/model` | ONNX 세션 로드, 타일 추론, 실패 시 classic으로 폴백 | ORT Web |
| `measure` | 스켈레톤 → 단면 폭(서브픽셀) → px/mm → 오차 범위 | 순수 TS(테스트 쉬움) |
| `report` | 폼, 지도, 이력, 오프라인 큐 | Vue |

- **모든 CV 작업은 Web Worker에서.** 4000×3000 사진 처리 중 UI가 멈추면 사용자는 앱이 죽은 줄 안다.
- **엔진 선택 순서**: WebGPU 가능 → 모델(WebGPU) / 아니면 모델(WASM SIMD) / 모델 로드 실패·저메모리 → **classic**. 어느 경로로 돌았는지 결과에 `engine`으로 남기고 화면에도 표시한다.
- `measure`는 OpenCV 의존이 없는 순수 함수로 유지한다. 환산 로직은 Vitest로 단위 테스트할 값이다(4단계).

## 6. API — FastAPI를 고른다

| 후보 | 판단 |
| --- | --- |
| **FastAPI** | **선택.** `ml/`이 이미 파이썬이고, 검증 규칙(지각 해시 거리, 기하 비교)이 학습·평가 코드와 같은 유틸을 쓴다. 한 언어로 끝난다 |
| Spring Boot | 기각. 여기서 얻는 게 없다. ML 유틸을 다시 구현하거나 파이썬 프로세스를 따로 띄워야 한다 |

- ORM: SQLAlchemy 2.x + Alembic 마이그레이션
- **PostGIS는 선택 사항.** 기본은 `lat/lon` 컬럼 + geohash 접두 인덱스로 동작한다. 무료 티어 배포에서 PostGIS 확장을 못 켜는 경우가 있어서, 확장 유무에 따라 근접 질의 구현만 갈아끼우게 둔다.
- 인증: 시민 신고는 **익명 기기 토큰**(기기에서 생성한 무작위 ID). 관리자만 로그인. 개인 식별 정보를 처음부터 받지 않는다.

## 7. 데이터 모델 (초안)

```
site            지점. 근접 신고를 묶은 단위
  id, centroid(lat,lon), geohash, first_seen, last_seen, status

report          신고 1건
  id, site_id(nullable), device_token, captured_at, received_at,
  lat, lon, accuracy_m, phash, engine, calibration_quality,
  blur_score, note, trust_score, trust_reasons(jsonb),
  state: pending|accepted|held|merged|rejected|closed

observation     신고에 들어 있던 균열 1개
  id, report_id, width_mm, width_ci_low, width_ci_high,
  length_mm, orientation_deg, polyline(jsonb), confidence

review_action   관리자 조치 이력 (누가·언제·무엇을·왜)
  id, report_id, actor, action, reason, created_at

image_asset     동의한 경우에만 존재
  id, report_id, storage_key, exif_stripped, uploaded_at
```

`review_action`을 따로 두는 이유: 신고가 보류·반려됐을 때 **왜 그랬는지 나중에 설명할 수 있어야** 한다. 상태 컬럼만 있으면 이유가 사라진다.

## 8. 신고 검증 — 규칙 기반, 설명 가능하게

ML 분류기로 신뢰도를 내지 않는다. 신고를 반려하면 사람에게 사유를 말해야 하고, 지자체가 쓰려면 근거가 감사 가능해야 한다.

| 검사 | 방법 | 결과 |
| --- | --- | --- |
| 중복 | 같은 `site` 후보(거리 임계) + 지각 해시 해밍 거리 + 시간 창 | 묶어서 `merged` |
| 위치 정합 | GPS 정확도, 건물 경계 밖 여부 | 감점 |
| 촬영 정합 | `capturedAt` vs 수신 시각 차이, 블러 점수 | 감점 |
| 색 신뢰 | 기준 패치 검출 실패 / 보정 후 ΔE 과대 | 감점 + "색 판정 불가" 표시 |
| 검출 타당성 | 폭·길이·신뢰도가 물리적으로 말이 되는 범위인가 | 감점 |
| 신고자 이력 | 같은 기기 토큰의 과거 반려율 | 감점 |

점수는 **가중합 + 사유 코드 목록**으로 낸다(`trust_reasons`). 임계 미만은 `held`(자동 보류)로 두고 삭제하지 않는다 — 오판일 수 있으므로 사람이 되돌릴 수 있어야 한다. 임계값은 상수가 아니라 설정값으로 빼고, 관리자 화면에서 **보류율·오탐 비율**을 보며 조정한다. 이 비율이 완료 기준의 "수치로 보고"에 해당한다.

## 9. 오프라인

- 앱 셸 + OpenCV.js + 모델 파일은 서비스 워커가 캐시(모델은 버전 태그 URL, 장기 캐시).
- 신고는 IndexedDB 큐에 먼저 쓰고 `state: queued`. 네트워크가 돌아오면 순차 전송, 서버는 클라이언트 생성 UUID로 멱등 처리한다.
- 지하·외진 곳에서 찍고 나중에 올리는 게 실제 사용 패턴이라 이 경로가 부가 기능이 아니다.

## 10. 배포

- `web/` → Vercel (정적 PWA). 모델 파일은 `immutable` 캐시 헤더.
- `api/` → Render (FastAPI + PostgreSQL). 데모는 로그인 없이 샘플 이미지 3장 체험.
- 빌드 산출물(`dist/`)에 `scripts/privacy-check.mjs`를 돌려 금칙어·EXIF 잔류를 막는다. CI에서도 동일.

## 11. 저장소 규칙 (계속 지킬 것)

- 데이터셋 이미지 0장. 실제 건물 주소·식별 가능한 사진 0장.
- 샘플은 본인 촬영 무특징 벽면만, EXIF 제거 후.
- 화면에는 항상 "전문가 진단이 아님" 고지. 표현은 `관찰 필요 / 전문가 점검 권장`까지.

## 12. 이 단계에서 일부러 미룬 것

- 모델 아키텍처 확정(3단계에서 실측 후), 타일 크기·겹침 수치
- 지도 라이브러리 선택(제보 흐름 붙일 때)
- 관리자 인증 방식 상세

---

## 13. 구현하며 바뀐 것 (2026-09-21)

설계와 달라진 부분. 이유는 [`decisions.md`](decisions.md)에 그때그때 적었다.

| 설계 | 실제 | 이유 |
| --- | --- | --- |
| 웹 영상처리에 OpenCV.js | 필요한 연산만 TS로 직접 구현 | OpenCV.js 약 10MB + 모델 실행기 11MB는 휴대폰 첫 방문에 과함. 파이썬과 같은 답인지는 골든 테스트로 확인 |
| 모델은 8비트 양자화(int8) | 32비트(6.2MB) 배포 | 양자화 7가지 설정 모두 가는 균열 출력이 무너짐(원본 대비 IoU ≤ 0.33) |
| ONNX Runtime Web: WebGPU 우선 | WASM 1스레드만 | 정적 호스팅(교차 출처 격리 없음)에서도 도는 경로를 기본으로. WebGPU용 파일(22MB)은 싣지 않음 |
| 서비스 워커가 모델까지 미리 받음 | 앱 껍데기만(340KB), 모델은 첫 분석 때 캐시 | 첫 방문 17MB는 과함 |
| 폭 = 단면 반치폭 | 폭 4px 미만은 넓이 기반, 이상은 균열 폭 비례 평활 후 반치폭 | 가는 균열은 흐림에, 넓은 균열은 바닥의 기공에 끌려감 |
| 근접 후보 = geohash 앞자리 같은 칸 | 위경도 범위 질의 | 칸 경계 너머 이웃을 못 봄(시뮬레이션에서 발견) |
| 같은 장면 = 지각 해시 해밍 ≤ 14 (가정) | 용도별: 묶기 ≤ 18, 중복 ≤ 8, 다른 위치 ≤ 12 | 실제 벽 사진으로 재 보니 재촬영 중앙값이 16비트 |
| 기준 물체 = 동전·자·패치 중 하나 | 기준 카드 한 장(색 칸 6 + 모서리 사각형 4 + 60mm 자) | 챙길 물건이 하나여야 실제로 챙긴다 |
