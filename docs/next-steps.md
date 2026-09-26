# 다음에 할 일 — 배포와 마무리 안내

개발은 끝났다. 남은 건 **계정이 필요한 일**과 **직접 몸으로 해야 하는 측정**뿐이다.
순서대로 따라 하면 된다. 전부 무료로 된다.

> 막히면 그 단계 번호와 화면에 나온 문구를 그대로 알려 주면 된다.

---

## 0. 지금 상태

| 무엇 | 어디에 | 상태 |
| --- | --- | --- |
| 앱·서버·문서 전체 | `~/projects/crack-watch` | 커밋 완료, GitHub 연결 **아직 없음** |
| 포트폴리오 케이스 | 포트폴리오 저장소 `main` | **이미 공개됨.** 데모·저장소 링크만 비어 있다 |
| 배포 설정 파일 | `vercel.json`(서버), `web/vercel.json`(웹), `render.yaml`(대안) | 준비 완료 |

공개해도 되는지 미리 확인한 것: 올라갈 파일은 170개 남짓(8.9MB)이고
`PROMPT.md`·검사어 목록(`.privacy-terms`)·데이터셋·학습 산출물은 **빠져 있다**.
샘플 사진은 전부 합성 이미지라 실제 건물이 찍힌 사진은 한 장도 없다.

### 배포 구조

```
[사람] → Vercel (웹: 화면·분석)  ──→  Vercel (서버: 신고 접수·지도)  ──→  Neon (데이터베이스)
         같은 저장소의 web/ 폴더        같은 저장소를 한 번 더 가져옴        무료, 만료 없음
```

서버를 Vercel 함수로 올리면 **잠들지 않는다**(요청이 올 때만 실행된다).
Render 무료 서버는 15분 뒤 잠들어 첫 접속이 1분씩 걸려서 쓰지 않는다 — 그래도 쓰고 싶다면 부록 A.

---

## 1. GitHub에 저장소 만들기 (15분)

### 1-1. 공개로 할지 먼저 정한다

- **공개(Public)**: 포트폴리오에서 코드 링크를 보여 줄 수 있다. 채용 담당자가 실제 코드를 본다.
- **비공개(Private)**: 나중에 공개로 바꿀 수 있지만, 포트폴리오에 링크를 걸어도 남이 못 연다.

추천은 공개다. 비공개 정보가 들어가지 않도록 처음부터 걸러 두었다.

### 1-2. 저장소 만들기

<https://github.com/new> 에서:

- Repository name: `crack-watch`
- Public / Private 선택
- **Add a README file 체크 해제** (이미 있다)
- Create repository

### 1-3. 올리기

```bash
cd ~/projects/crack-watch && git remote add origin https://github.com/thanksdooss/crack-watch.git
```

```bash
cd ~/projects/crack-watch && git push -u origin main
```

**확인**: GitHub 저장소 페이지를 새로고침하면 README가 보인다.

### 1-4. 자동 검사용 비밀값 등록

빌드할 때마다 "공개하면 안 되는 단어"가 섞였는지 검사하는 장치가 있다. 검사어 목록 자체가 비공개라 비밀값으로 넣는다.

1. 저장소 → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret**
3. Name: `PRIVACY_TERMS`
4. Secret: 아래 명령 결과를 복사해 붙여넣기

```bash
cat ~/projects/crack-watch/.privacy-terms
```

5. Add secret

안 넣으면 자동 검사가 빨간 X로 뜬다(코드 문제는 아니다).

---

## 2. 웹 올리기 — Vercel (15분)

### 2-1. 계정 연결

1. <https://vercel.com> → **Sign Up**(또는 Log In) → **Continue with GitHub** → **Authorize**
2. 개인 용도이므로 **Hobby(무료)** 플랜

### 2-2. 프로젝트 가져오기

1. 오른쪽 위 **Add New…** → **Project**
2. `crack-watch` 줄의 **Import**
   - 목록에 없으면 **Adjust GitHub App Permissions** → 저장소 접근 허용
3. **Configure Project** 화면에서 **딱 하나만** 바꾼다:

| 항목 | 값 |
| --- | --- |
| Project Name | `crack-watch` (그대로) |
| Framework Preset | Vite (자동) — 그대로 |
| **Root Directory** | **`web`** ← Edit → `web` 폴더 선택 → Continue |
| Build / Output | 그대로 |
| Environment Variables | 비워 둔다 (5단계에서 넣는다) |

4. **Deploy** → 1~3분

### 2-3. 주소 확인

`https://crack-watch-xxxx.vercel.app` 같은 주소가 나온다. **적어 둔다.**

열어서 확인:

- [ ] "균열 감시" 제목과 샘플 3장이 보인다
- [ ] 샘플을 누르면 몇 초 뒤 결과가 나온다(처음 한 번은 모델 6.2MB를 받느라 느리다)
- [ ] 결과에 "전문가 진단이 아닙니다" 안내가 있다

> 지금은 지도·관리자 화면이 비어 있는 게 **정상**이다. 서버가 아직 없다.

빌드가 실패했다면 Root Directory가 `web`인지 확인한다(Settings → General → Root Directory → 고친 뒤 Redeploy).

---

## 3. 데이터베이스 만들기 — Neon (15분)

신고를 저장할 곳이다. Render의 무료 데이터베이스는 **30일이면 만료**되어 데모가 조용히 죽으므로,
만료가 없는 Neon을 쓴다(SKAVOCA도 같은 이유로 Neon을 쓴다).

### 3-1. 데이터베이스 만들기

1. <https://neon.com> → **Sign up** → GitHub 로그인
2. Project name `crack-watch`, Region은 **Singapore** 같은 가까운 곳
3. **Create** → **Connection string**(연결 문자열)이 나온다
4. `postgresql://` 로 시작하는 문자열을 **통째로 복사**해 둔다
   - **비밀번호가 들어 있다.** 저장소·메신저에 붙여넣지 않는다(Vercel 설정에만 넣는다)
   - 창을 닫았으면 프로젝트 → **Connect**에서 다시 볼 수 있다
   - 선택지가 있으면 **Pooled connection**(주소에 `-pooler`가 들어간 것)을 고른다 — 서버리스에 맞다

### 3-2. 데모 데이터 한 번 넣기

지도·관리자 화면을 체험하려면 합성 신고가 필요하다. 내 컴퓨터에서 한 번만 넣으면 된다.
아래 명령의 `<연결문자열>` 자리에 3-1에서 복사한 값을 붙여넣는다(따옴표 유지).

```bash
cd ~/projects/crack-watch && DATABASE_URL='<연결문자열>' .venv/bin/python -m api.sim.seed_demo
```

`226건 넣음`이 나오면 성공이다(이미 들어 있으면 `이미 데이터가 있어 건너뛴다`라고 나온다).

---

## 4. 서버 올리기 — Vercel 함수 (15분)

웹과 **같은 저장소**를 두 번째 프로젝트로 한 번 더 가져온다. 이번엔 파이썬 서버로 인식된다.

### 4-1. 관리자 열쇠 만들기

관리자 화면에 들어갈 때 쓸 비밀번호다. 아래 명령으로 무작위 값을 만들어 **복사해 둔다**.

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

### 4-2. 두 번째 프로젝트 만들기

1. Vercel → **Add New…** → **Project** → 같은 `crack-watch` 저장소 **Import**
2. **Project Name**: `crack-watch-api` (웹 프로젝트와 이름이 달라야 한다)
3. **Root Directory**: **저장소 루트 그대로 둔다**(`web`으로 바꾸지 않는다)
4. Framework Preset: 자동 감지에 맡긴다(Other로 나와도 된다)
5. **Environment Variables**에 세 개를 넣는다:

| Key | Value |
| --- | --- |
| `DATABASE_URL` | 3-1에서 복사한 Neon 연결 문자열 |
| `ADMIN_TOKEN` | 4-1에서 만든 무작위 값 |
| `CORS_ORIGINS` | 2-3의 웹 주소 (예: `https://crack-watch-xxxx.vercel.app`, **끝에 `/` 없이**) |

6. **Deploy** → 2~4분

### 4-3. 확인

배포가 끝나면 `https://crack-watch-api-xxxx.vercel.app` 같은 주소가 나온다. **적어 둔다.**

- `https://<서버주소>/health` → `{"status":"ok"}`
- `https://<서버주소>/sites` → 지점 목록(JSON)이 쭉 나온다 (3-2에서 넣은 데모 데이터)

둘 다 되면 서버가 살아 있는 것이다. **잠들지 않으므로 깨울 필요도 없다.**

---

## 5. 웹과 서버 연결 (10분)

웹이 아직 서버 주소를 모른다.

1. Vercel → **웹** 프로젝트(`crack-watch`) → **Settings** → **Environment Variables**
2. 입력:

| 칸 | 값 |
| --- | --- |
| Key | `VITE_API_URL` |
| Value | 4-3의 서버 주소 (**끝에 `/` 없이**) |
| Environments | 전부 체크 |

3. **Save**
4. **Deployments** 탭 → 맨 위 배포 **⋯** → **Redeploy** (Build Cache 체크 해제 권장) → 1~3분

> 환경 변수는 **빌드할 때** 앱에 박힌다. 저장만 하고 재배포하지 않으면 반영되지 않는다.

### 5-1. 최종 확인

웹 주소를 새로 열어서:

- [ ] **분석**: 샘플 → 결과가 나오고 균열이 주황색으로 표시된다
- [ ] **지도·이력**: 빨간 점들이 보인다
- [ ] 점을 누르면 아래에 폭 변화 그래프가 나온다
- [ ] **관리자**: 4-1의 토큰 입력 → 불러오기 → 보류된 신고와 "걸러 낸 비율"이 보인다
- [ ] 샘플 분석 → **신고하기** → 위치 동의 → 접수된다

---

## 6. 링크 채우기

주소 세 개(웹·서버·GitHub)를 알려 주면 내가 다음을 정리한다.

- 이 저장소 `README.md`의 "데모" 항목 — 내가 직접 고친다
- 포트폴리오 케이스의 `links`와 note의 "데모와 저장소 링크는 배포 후 추가합니다." 문장 —
  포트폴리오 저장소는 다른 작업자가 맡고 있으므로 **바꿀 내용만 만들어 전달**한다

직접 넣으려면 포트폴리오의 `src/data/projects/crack-watch.js`에서:

```js
links: [
  { label: '데모', url: 'https://crack-watch-xxxx.vercel.app' },
  { label: 'GitHub', url: 'https://github.com/thanksdooss/crack-watch' },
],
```

---

## 7. 직접 재야 채워지는 숫자 (선택, 40분)

문서에 "미측정"으로 비워 둔 칸이다. 채우면 "합성 실험" 대신 "실제 측정"이라고 쓸 수 있다.
안 해도 앱은 동작한다. 다만 면접에서 "실제로 재 봤나요?"에 답이 생긴다.

### 7-1. 휴대폰 처리 시간 (5분 — 제일 쉽다)

1. 휴대폰으로 배포한 웹 주소를 연다
2. 샘플 하나를 눌러 분석한다
3. 결과 화면의 **측정 근거 → 처리 시간** 숫자(예: `6144 ms (…)`)와 **기종**을 알려 준다

### 7-2. 색 보정 실측 (30분 — 제일 값어치 있다)

준비물: 프린터, 자, 무늬 없는 콘크리트 벽(주차장·옥상·담장이면 충분)

1. `web/public/reference-card.pdf`를 **배율 100%**(‘페이지에 맞춤’ 끄기)로 인쇄
2. 자로 카드의 가로 막대가 **정확히 60mm**인지 확인. 다르면 인쇄 설정을 고쳐 다시 뽑는다
3. 카드를 벽에 평평하게 붙인다(휘지 않게, 그늘 없이)
4. **같은 자리**에서 세 번 촬영 — ① 낮 야외 ② 실내 형광등 ③ 해질 무렵이나 백열등
5. 사진 3장을 주면 보정 전후 색 오차 표를 채운다

### 7-3. 폭 실측

균열이 있는 벽이 있으면 카드를 옆에 붙여 찍고, **자나 균열 게이지로 같은 자리의 폭**을 재서 알려 주면
앱 추정값과 실제 값을 비교한 표를 만든다.

---

## 8. 문제가 생기면

| 증상 | 원인과 해결 |
| --- | --- |
| 웹 빌드 실패 "No such file" | Root Directory가 `web`이 아니다(2-2) |
| 서버 배포 실패 | 서버 프로젝트의 Root Directory는 **저장소 루트**여야 한다(4-2). `web`으로 두면 파이썬을 못 찾는다 |
| `/health`가 404 | 서버가 아니라 웹 주소를 열었다. 주소 두 개를 헷갈리기 쉽다 |
| 지도·관리자가 비어 있다 | 5단계(환경 변수 + 재배포)를 안 했다 |
| 신고가 "데모 모드"로만 저장된다 | 같은 원인. `VITE_API_URL` 확인 후 재배포 |
| 지도는 뜨는데 신고가 안 들어간다 | `CORS_ORIGINS`(서버)에 적은 웹 주소가 실제와 다르거나 끝에 `/`가 붙었다 |
| 서버 로그에 `could not connect` | Neon 연결 문자열이 잘렸거나 `?sslmode=require`가 빠졌다. Neon에서 다시 복사 |
| 서버 로그에 `psycopg2` 오류 | Neon에서 복사한 주소를 그대로 넣었는지 확인(형식 변환은 코드가 알아서 한다) |
| 관리자 화면 "401" | `ADMIN_TOKEN` 값이 다르다. Vercel 서버 프로젝트의 환경 변수와 맞춰 본다 |
| GitHub 자동 검사가 빨간 X | `PRIVACY_TERMS` 비밀값이 없다(1-4). 코드 문제가 아니다 |
| 첫 분석이 오래 걸린다 | 처음 한 번만 모델 6.2MB를 받는다. 두 번째부터 빠르다 |

---

## 9. 누가 무엇을 하나

| 내가 할 수 있음 | 직접 하셔야 함 |
| --- | --- |
| README 링크 넣기, 케이스 수정안 만들기 | GitHub·Vercel·Neon **계정 로그인과 생성** |
| 사진을 주면 색 오차 표 채우기 | **배포 버튼 누르기**(공개 행위라 본인 확인이 필요) |
| 문구·기능 수정, 오류 원인 찾기 | 카드 인쇄와 벽 촬영, 자로 재기 |
| — | 휴대폰에서 처리 시간 확인 |

---

## 부록 A. Render로 올리는 방법 (대안)

Vercel 대신 Render에 서버를 올릴 수도 있다. `render.yaml`이 준비돼 있어 **New + → Blueprint**로 한 번에 만들어진다.
다만 무료 요금제에는 두 가지 제약이 있다.

1. **15분간 접속이 없으면 잠든다.** 다음 접속 때 깨는 데 1분쯤 걸린다.
   - 앱이 열릴 때 서버를 미리 깨우는 장치는 이미 들어 있다(`web/src/lib/api.ts`의 `warmUp`).
   - `.github/workflows/keep-warm.yml`이 평일 09~20시(KST) 14분마다 깨운다. 저장소 **Variables**에
     `API_URL`(서버 주소)을 등록해야 동작한다.
2. **무료 시간은 계정당 월 750시간**이다(서비스별이 아니다). 같은 계정의 SKAVOCA가 하루 16시간을 깨워 두면
   월 약 480시간을 쓴다. 그래서 이 프로젝트의 깨우기는 평일 낮(월 약 220시간)으로 좁혀 두었다.
   합계 약 700시간으로 한도 안이다.

Vercel 함수로 올리면 이 제약이 둘 다 없어진다(요청이 올 때만 실행되고, 깨울 필요가 없다).
그래서 본문은 Vercel 기준으로 적었다.
