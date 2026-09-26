# 다음에 할 일 — 배포와 마무리 안내

개발은 끝났고, 여기 남은 건 **계정이 필요한 일**과 **직접 몸으로 해야 하는 측정**뿐이다.
순서대로 따라 하면 된다. 각 단계에 걸리는 시간과 비용을 적어 두었다. 전부 무료 요금제로 된다.

> 막히면 그 단계 번호와 화면에 나온 문구를 그대로 알려 주면 된다.

---

## 0. 지금 상태

| 무엇 | 어디에 | 상태 |
| --- | --- | --- |
| 앱·서버·문서 전체 | `~/projects/crack-watch` | 커밋 10개, GitHub 연결 **아직 없음** |
| 포트폴리오 케이스 | `~/projects/portfolio`의 `main` (다른 작업자가 병합 완료) | **푸시만 남음** |
| 배포 설정 파일 | `render.yaml`, `web/vercel.json`, `.github/workflows/ci.yml` | 준비 완료 |

포트폴리오 저장소는 **다른 작업자가 맡고 있다.** 2026-09-26 기준으로 균열 감시 케이스는 이미 `main`에 병합됐고
(충돌 없음), SKAVOCA 케이스 갱신 2건과 함께 **푸시만 남아 있다.** 이 저장소(crack-watch) 쪽에서는 포트폴리오 파일을 직접 고치지 않는다.

공개해도 되는지 미리 확인한 것: 올라갈 파일은 170개(8.9MB)이고, `PROMPT.md`·검사어 목록(`.privacy-terms`)·데이터셋·학습 데이터는 **빠져 있다**.
샘플 사진은 전부 합성 이미지라 실제 건물이 찍힌 사진은 한 장도 없다.

---

## 1. GitHub에 저장소 만들기 (10분)

### 1-1. 공개로 할지 먼저 정한다

- **공개(Public)**: 포트폴리오에서 코드 링크를 보여 줄 수 있다. 채용 담당자가 실제 코드를 본다.
- **비공개(Private)**: 나중에 언제든 공개로 바꿀 수 있다. 다만 포트폴리오에 링크를 걸어도 남이 못 연다.

추천은 공개다. 이 저장소에는 비공개 정보가 들어가지 않도록 처음부터 걸러 두었다.

### 1-2. 저장소 만들기

브라우저에서 <https://github.com/new> 에 들어가:

- Repository name: `crack-watch`
- Public / Private 중 선택
- **Add a README file 체크 해제** (이미 있다)
- Create repository

### 1-3. 올리기

터미널에서 아래를 차례로 실행한다(`<사용자이름>`은 본인 GitHub 아이디).

```bash
cd ~/projects/crack-watch && git remote add origin https://github.com/<사용자이름>/crack-watch.git
```

```bash
cd ~/projects/crack-watch && git branch -M main && git push -u origin main
```

**확인**: GitHub 저장소 페이지를 새로고침하면 README가 보이고, 화면 상단에 파일 목록이 나온다.

### 1-4. 자동 검사에 쓸 비밀값 등록 (5분)

빌드할 때마다 "공개하면 안 되는 단어"가 섞여 들어갔는지 검사하는 장치가 있다. 검사어 목록 자체가 비공개라 GitHub에 비밀값으로 넣어야 한다.

1. 저장소 페이지 → **Settings** → 왼쪽 **Secrets and variables** → **Actions**
2. **New repository secret** 클릭
3. Name: `PRIVACY_TERMS`
4. Secret: 아래 명령으로 나온 내용을 복사해 붙여넣기

```bash
cat ~/projects/crack-watch/.privacy-terms
```

5. Add secret

이걸 안 넣으면 GitHub의 자동 검사가 실패로 표시된다(코드에는 문제 없음).

---

## 2. 웹 배포 — Vercel (15분, 무료)

브라우저에서 보이는 앱을 올린다. GitHub에 올린 코드를 Vercel이 가져가 자동으로 빌드한다.

### 2-1. 계정 연결

1. <https://vercel.com> 접속 → **Sign Up**(또는 Log In) → **Continue with GitHub** 선택
2. GitHub가 권한을 물으면 **Authorize Vercel** 클릭
3. 개인 용도이므로 Hobby(무료) 플랜을 고르고, 이름은 아무거나 적어도 된다

### 2-2. 프로젝트 가져오기

1. 화면 오른쪽 위 **Add New…** → **Project**
2. `crack-watch` 저장소 줄의 **Import** 클릭
   - 목록에 없으면: **Adjust GitHub App Permissions** → 저장소 접근 허용 → 돌아와서 새로고침
3. **Configure Project** 화면이 뜬다. 여기서 **딱 하나만** 바꾼다:

| 항목 | 값 | 설명 |
| --- | --- | --- |
| Framework Preset | Vite | 자동으로 잡힌다. 그대로 |
| **Root Directory** | **`web`** | ← **이것만 바꾼다.** Edit 버튼 → 목록에서 `web` 폴더 선택 → Continue |
| Build Command | `npm run build` | 그대로 |
| Output Directory | `dist` | 그대로 |
| Environment Variables | 비워 둠 | 4단계에서 넣는다 |

4. **Deploy** 클릭 → 1~3분 기다린다

### 2-3. 주소 확인

배포가 끝나면 축하 화면과 함께 주소가 나온다(예: `https://crack-watch-abc123.vercel.app`).
이 주소를 **적어 둔다** — 3단계에서 쓴다.

열어서 확인:

- [ ] "균열 감시" 제목과 샘플 3장이 보인다
- [ ] 샘플을 누르면 몇 초 뒤 결과가 나온다(처음 한 번은 모델 6.2MB를 받느라 느리다)
- [ ] 결과에 "전문가 진단이 아닙니다" 안내가 있다

> 이 단계에서 지도·관리자 화면이 비어 있는 건 **정상**이다. 서버가 아직 없다.

**Root Directory를 잘못 지정해 빌드가 실패했다면**: 프로젝트 → Settings → General → Root Directory를 `web`으로 고치고
Deployments 탭에서 **Redeploy**.

---

## 3. 데이터베이스와 서버 배포 (30분, 무료)

신고를 저장할 **데이터베이스(Neon)** 를 먼저 만들고, 그다음 **서버(Render)** 를 올린다.

> Render에도 무료 PostgreSQL이 있지만 **만든 지 30일이면 만료**된다. 포트폴리오 데모가 한 달 뒤 조용히 죽기 때문에
> 만료가 없는 **Neon** 무료 PostgreSQL을 쓴다. SKAVOCA도 같은 이유로 Neon을 쓰고 있다.

### 3-1. Neon에서 데이터베이스 만들기 (10분)

1. <https://neon.com> → **Sign up** → GitHub 계정으로 로그인
2. 프로젝트 만들기 화면에서:
   - Project name: `crack-watch`
   - Postgres version: 기본값 그대로
   - Region: **Asia Pacific (Singapore)** 처럼 가까운 곳 (Render도 싱가포르로 맞춘다)
3. **Create** → 잠시 뒤 **Connection string**(연결 문자열)이 화면에 나온다
4. `postgresql://` 로 시작하는 그 문자열을 **통째로 복사**해 둔다
   - 예: `postgresql://user:비밀번호@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`
   - **비밀번호가 들어 있으니 남에게 보여 주지 않는다.** 저장소에도 넣지 않는다(Render에만 입력한다)
   - 화면을 닫아 버렸으면: 프로젝트 → **Connect**(또는 Dashboard의 Connection Details)에서 다시 볼 수 있다

### 3-2. Render에 서버 올리기 (20분)

1. <https://render.com> → **Get Started**(또는 Sign In) → **GitHub**로 로그인 → **Authorize Render**
2. 대시보드 오른쪽 위 **New +** → **Blueprint**
3. 저장소 목록에서 `crack-watch` → **Connect**
   - 목록에 없으면 **Configure account**(또는 Install Render) → 저장소 접근 허용
4. Render가 `render.yaml`을 읽어 **crack-watch-api** 서비스 하나를 보여 준다. Blueprint Name은 아무거나(예: `crack-watch`)
5. 값을 물어보는 칸 두 개를 채운다:

| 칸 | 넣을 값 |
| --- | --- |
| `DATABASE_URL` | 3-1에서 복사한 Neon 연결 문자열 (그대로 붙여넣기) |
| `CORS_ORIGINS` | 2-3에서 적어 둔 Vercel 주소 (예: `https://crack-watch-abc123.vercel.app`, **끝에 `/` 없이**) |

6. **Apply**(또는 Create Resources) → 첫 빌드 5~10분(파이썬 라이브러리 설치)

### 3-3. 주소와 관리자 열쇠 확인

1. 빌드가 끝나면 서비스 페이지 위쪽 주소를 **적어 둔다**(예: `https://crack-watch-api-xxxx.onrender.com`)
2. 왼쪽 **Environment** 탭 → `ADMIN_TOKEN` 줄의 눈 모양 아이콘 → 값을 **복사해 안전한 곳에** 둔다
   (관리자 화면 열쇠다. 남에게 주지 않는다)
3. 브라우저에서 `https://<서버주소>/health` → `{"status":"ok"}` 가 나오면 성공
4. `https://<서버주소>/sites` 를 열면 데모 지점 목록(JSON)이 보인다 — 서버가 처음 켜질 때 합성 신고 226건을 자동으로 넣는다

### 3-4. 무료 요금제에서 알아 둘 것

- **15분 동안 접속이 없으면 서버가 잠든다.** 다음 접속 때 깨어나는 데 1분쯤 걸린다(면접 전에 미리 열어 두면 좋다).
- 데이터는 Neon에 남으므로 **서버가 잠들거나 재배포돼도 신고가 사라지지 않는다.**
- 데모 데이터는 **비어 있을 때 한 번만** 들어간다. 재시작해도 중복으로 쌓이지 않는다(확인함).
- 실제 운영으로 전환하려면 Render의 `SEED_DEMO`를 `false`로 바꾸고, Neon에서 데모 데이터를 지우면 된다.
- Neon 무료는 만료가 없지만, 오래 접속이 없으면 데이터베이스도 잠깐 잠든다(첫 요청이 몇 초 느려진다).

## 4. 웹과 서버 연결 (5분)

웹은 아직 서버 주소를 모른다. 알려 주고 다시 배포하면 지도·관리자 화면이 살아난다.

1. Vercel 대시보드 → `crack-watch` 프로젝트 → 위쪽 **Settings** 탭
2. 왼쪽 메뉴 **Environment Variables**
3. 입력:

| 칸 | 넣을 값 |
| --- | --- |
| Key | `VITE_API_URL` |
| Value | 3-3에서 적어 둔 Render 주소 (예: `https://crack-watch-api-xxxx.onrender.com`, **끝에 `/` 없이**) |
| Environments | 전부 체크(Production·Preview·Development) |

4. **Save**
5. 위쪽 **Deployments** 탭 → 맨 위 배포 오른쪽 **⋯** → **Redeploy**
   - "Use existing Build Cache" 체크는 **해제**하는 편이 확실하다
   - 다시 1~3분

> 환경 변수는 **빌드할 때** 앱에 박히기 때문에, 저장만 하고 다시 배포하지 않으면 반영되지 않는다.

### 4-1. 최종 확인 (5분)

웹 주소를 새로 열어서:

- [ ] **분석**: 샘플 → 결과가 나오고 균열이 주황색으로 표시된다
- [ ] **지도·이력**: 빨간 점들이 보인다(서버가 잠들어 있으면 1분 뒤 새로고침)
- [ ] 점을 누르면 아래에 폭 변화 그래프가 나온다
- [ ] **관리자**: 3-3에서 복사한 토큰 입력 → 불러오기 → 보류된 신고와 "걸러 낸 비율"이 보인다
- [ ] 샘플 분석 → **신고하기** → 위치 동의 → 접수된다

다 되면 주소 두 개(웹·서버)와 GitHub 주소를 알려 달라. README와 포트폴리오 케이스에 넣을 링크를 정리해 주겠다.

## 5. 링크를 문서와 포트폴리오에 넣기 (내가 대신 할 수 있음)

주소 두 개(웹·서버)와 GitHub 주소를 알려 주면 내가 다음을 수정한다.

- `README.md`의 "데모" 항목
- 포트폴리오 케이스의 `links` (지금은 비어 있음)와 note의 "데모와 저장소 링크는 배포 후 추가합니다." 문장

포트폴리오 저장소는 다른 작업자가 맡고 있으므로, 나는 **바꿀 내용만 아래처럼 만들어 전달**한다.
직접 넣으려면 `~/projects/portfolio/src/data/projects/crack-watch.js`의 `links: []` 를 이렇게 바꾸고,
`note`의 마지막 줄("데모와 저장소 링크는 배포 후 추가합니다.")을 지우면 된다.

```js
links: [
  { label: '데모', url: 'https://crack-watch-xxxx.vercel.app' },
  { label: 'GitHub', url: 'https://github.com/<사용자이름>/crack-watch' },
],
```

---

## 6. 포트폴리오에 케이스 올리기 (5분)

**병합은 이미 끝났다**(다른 작업자가 처리). `~/projects/portfolio`의 `main`이 GitHub보다 커밋 4개 앞서 있다.

| 커밋 | 내용 |
| --- | --- |
| `5566891` | SKAVOCA 케이스 Spring Boot 버전 정정 |
| `f6e0f3a` | 균열 감시 케이스 병합 |
| `56bb476` | SKAVOCA 케이스 지표를 측정값으로 교체 |
| `ff08d05` | 균열 감시 케이스 추가 |

### 6-1. 올리기 전 확인

```bash
cd ~/projects/portfolio && npm run dev
```

`http://localhost:5173/portfolio/#/p/crack-watch` 에서 세 가지를 봐 달라:

- 경력·역할 표현이 사실과 맞는지 (기획 3인 팀의 **팀원**, 구현은 단독)
- 수상 표기가 없는지 (이 대회는 본인 이름 상장이 없어 일부러 뺐다)
- 문장 톤이 본인 것 같은지

### 6-2. 올리기 — 이걸 하면 공개 사이트에 뜬다

```bash
cd ~/projects/portfolio && git push
```

### 6-3. 되돌리기 (푸시 전에만)

균열 감시 케이스만 빼고 SKAVOCA 작업은 남기려면:

```bash
cd ~/projects/portfolio && git reset --hard 5566891
```

`git reset --hard origin/main`은 쓰지 않는다 — 다른 작업자의 SKAVOCA 갱신까지 함께 사라진다.

## 7. 직접 재야 채워지는 숫자 (선택, 40분)

문서에 "미측정"으로 비워 둔 칸들이다. 채우면 "합성 실험" 대신 "실제 측정"이라고 쓸 수 있다.
안 해도 앱은 동작한다. 다만 면접에서 "실제로 재 봤나요?"라는 질문에 답이 생긴다.

### 7-1. 색 보정 실측 (제일 값어치 있음)

준비물: 프린터, 자, 무늬 없는 콘크리트·시멘트 벽(주차장·옥상·담장이면 충분하다)

1. `web/public/reference-card.pdf`를 **배율 100%**(‘페이지에 맞춤’ 끄기)로 인쇄한다
2. 자로 카드의 가로 막대가 **정확히 60mm**인지 잰다. 다르면 인쇄 설정을 고쳐 다시 뽑는다
3. 카드를 벽에 평평하게 붙인다(휘지 않게, 그늘지지 않게)
4. **같은 자리**에서 세 번 찍는다 — ① 낮 야외 ② 실내 형광등 ③ 해질 무렵이나 백열등
5. 사진 3장을 주면 내가 보정 전후 색 오차를 계산해 표를 채운다

### 7-2. 폭 실측

균열이 있는 벽이 있다면, 카드를 옆에 붙이고 찍은 뒤 **자(또는 균열 게이지)로 같은 자리의 폭**을 재서 알려 주면, 앱 추정값과 실제 값을 비교한 표를 만든다. 균열을 못 찾으면 이 항목은 건너뛴다.

### 7-3. 휴대폰 처리 시간 (5분, 제일 쉬움)

1. 휴대폰으로 배포한 웹 주소를 연다
2. 샘플 하나를 눌러 분석한다
3. 결과 화면의 **측정 근거 → 처리 시간**에 나오는 숫자(예: `6144 ms (…)`)를 알려 준다
4. 기종(예: 갤럭시 S22, 아이폰 13)도 함께 알려 주면 표에 기기명을 넣는다

---

## 8. 자주 묻는 상황

| 증상 | 원인과 해결 |
| --- | --- |
| 지도·관리자 화면이 비어 있다 | 4단계(환경 변수 + 재배포)를 안 했거나, 서버가 잠들어 있다. 서버 주소 `/health`를 먼저 열어 깨운다 |
| 관리자 화면에서 "401" | 토큰이 틀렸다. Render의 `ADMIN_TOKEN` 값을 다시 복사한다 |
| 신고가 "데모 모드"로만 저장된다 | 웹이 서버 주소를 모른다. Vercel 환경 변수 확인 후 재배포 |
| GitHub의 자동 검사가 빨간 X | `PRIVACY_TERMS` 비밀값이 없을 때 그렇다(1-4단계). 코드 문제가 아니다 |
| 첫 분석이 오래 걸린다 | 처음 한 번은 모델 파일(6.2MB)을 받는다. 두 번째부터는 빠르다 |
| 지도는 되는데 신고가 안 들어간다 | `CORS_ORIGINS`(Render)에 적은 웹 주소가 실제 주소와 다르거나 끝에 `/`가 붙었다 |
| Render 로그에 `psycopg2` 오류 | `DATABASE_URL`을 Neon에서 복사한 그대로 넣었는지 확인(형식 변환은 코드가 알아서 한다) |
| Render 로그에 `could not connect` | Neon 연결 문자열이 잘렸거나 `?sslmode=require`가 빠졌다. Neon에서 다시 복사 |
| Vercel 빌드 실패 "No such file" | Root Directory가 `web`이 아니다. Settings → General에서 고치고 Redeploy |
| Render 배포가 빨간색 | 서비스 → Logs에서 마지막 줄을 복사해 알려 달라 |
| 며칠 뒤 지도가 비었다 | 서버가 잠들어 있다. 1분 뒤 새로고침. 데이터는 Neon에 남아 있다 |

---

## 9. 내가 할 수 있는 일 / 직접 하셔야 하는 일

| 내가 할 수 있음 | 직접 하셔야 함 |
| --- | --- |
| 이 저장소 README에 링크 넣기 · 케이스 수정안 만들기 | GitHub·Vercel·Render **계정 로그인과 생성** |
| 사진을 주면 색 오차 표 채우기 | 배포 버튼 누르기(공개 행위라 본인 확인이 필요) |
| 문구·내용 수정, 기능 추가 | 카드 인쇄와 벽 촬영, 자로 재기 |
| 오류 메시지를 주면 원인 찾기 | 휴대폰에서 처리 시간 확인 |
