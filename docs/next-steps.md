# 다음에 할 일 — 배포와 마무리 안내

개발은 끝났고, 여기 남은 건 **계정이 필요한 일**과 **직접 몸으로 해야 하는 측정**뿐이다.
순서대로 따라 하면 된다. 각 단계에 걸리는 시간과 비용을 적어 두었다. 전부 무료 요금제로 된다.

> 막히면 그 단계 번호와 화면에 나온 문구를 그대로 알려 주면 된다.

---

## 0. 지금 상태

| 무엇 | 어디에 | 상태 |
| --- | --- | --- |
| 앱·서버·문서 전체 | `~/projects/crack-watch` | 커밋 10개, GitHub 연결 **아직 없음** |
| 포트폴리오 케이스 | `~/projects/portfolio`의 `content/crack-watch` 가지 | 커밋됨, `main`에 **아직 안 합침**, 푸시 안 함 |
| 배포 설정 파일 | `render.yaml`, `web/vercel.json`, `.github/workflows/ci.yml` | 준비 완료 |

포트폴리오 저장소에서는 지금 클린 팩토리 작업이 진행 중이다. 케이스 커밋이 건드리는 파일은 `crack-watch` 관련 9개뿐이라
**겹치는 파일은 없지만**, 같은 저장소를 두 곳에서 동시에 만지면 헷갈리니 6단계는 클린 팩토리 작업이 일단락된 뒤에 한다.

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

### 2-1. 프로젝트 연결

1. <https://vercel.com> 로그인 (GitHub 계정으로 로그인하면 편하다)
2. **Add New… → Project**
3. 방금 만든 `crack-watch` 저장소 옆 **Import**
4. 설정 화면에서 **Root Directory**를 `web`으로 바꾼다 ← **이것만 꼭 확인**
   (Edit 버튼을 눌러 `web` 폴더 선택)
5. Framework Preset은 Vite로 자동 인식된다. 나머지는 그대로 두고 **Deploy**

2~3분 뒤 배포가 끝나고 `https://crack-watch-xxxx.vercel.app` 같은 주소가 나온다.

### 2-2. 잘 되는지 확인

그 주소를 열어서:

- [ ] 첫 화면에 "균열 감시"와 샘플 3장이 보인다
- [ ] 샘플 하나를 누르면 몇 초 뒤 결과가 나오고, 균열이 주황색으로 표시된다
- [ ] 결과에 "전문가 진단이 아닙니다" 안내가 보인다
- [ ] 기준 카드(PDF) 링크가 열린다

이 단계에서는 **서버가 아직 없어서** 지도와 관리자 화면은 비어 있다. 정상이다.

---

## 3. 서버 배포 — Render (20분, 무료)

신고를 저장하고 지도·관리자 화면에 쓸 서버다.

1. <https://render.com> 로그인 (GitHub 계정 권장)
2. **New → Blueprint**
3. `crack-watch` 저장소 선택 → Render가 `render.yaml`을 읽어 **서버 1개 + 데이터베이스 1개**를 자동으로 잡아 준다
4. `CORS_ORIGINS` 값을 물어보면, **2단계에서 받은 Vercel 주소**를 그대로 넣는다
   (예: `https://crack-watch-xxxx.vercel.app` — 끝에 `/` 붙이지 않는다)
5. Apply / Create

첫 배포는 5~10분 걸린다. 끝나면 `https://crack-watch-api-xxxx.onrender.com` 같은 주소가 나온다.

### 3-1. 관리자 비밀번호 확인해 두기

Render 대시보드에서 `crack-watch-api` → **Environment** → `ADMIN_TOKEN` 값을 눈 모양 아이콘으로 확인해 복사해 둔다. 관리자 화면에 들어갈 때 쓴다. (남에게 알려주지 않는다)

### 3-2. 서버가 살아 있는지 확인

브라우저에서 `https://<서버주소>/health` 를 연다. `{"status":"ok"}` 가 나오면 성공이다.

> **무료 요금제 주의**: 15분 동안 아무도 안 쓰면 서버가 잠든다. 다음 접속 때 깨어나느라 30~60초 걸린다. 면접 전에 미리 한 번 열어 두면 좋다.

---

## 4. 웹과 서버 연결하기 (5분)

1. Vercel 대시보드 → `crack-watch` 프로젝트 → **Settings → Environment Variables**
2. Name: `VITE_API_URL` / Value: 3단계의 서버 주소(`https://...onrender.com`, 끝에 `/` 없이)
3. Save
4. **Deployments** 탭 → 맨 위 배포의 **⋯ → Redeploy** (환경 변수는 다시 배포해야 반영된다)

### 확인 체크리스트

웹 주소를 다시 열어서:

- [ ] 위쪽 **지도·이력** 탭에 빨간 점들이 보인다 (데모용 합성 신고 226건이 자동으로 들어 있다)
- [ ] 점 하나를 누르면 아래에 폭 변화 그래프가 나온다
- [ ] **관리자** 탭 → 3-1에서 복사한 토큰 입력 → **불러오기** → 보류된 신고 목록과 "걸러 낸 비율"이 보인다
- [ ] 샘플 분석 후 **신고하기** → 위치 동의 → 신고가 접수된다

> 지도에 있는 신고는 **합성 데모 데이터**다(메모에 `[합성 데모]`라고 적혀 있다). 실제 신고가 아니다.

---

## 5. 링크를 문서와 포트폴리오에 넣기 (내가 대신 할 수 있음)

주소 두 개(웹·서버)와 GitHub 주소를 알려 주면 내가 다음을 수정한다.

- `README.md`의 "데모" 항목
- 포트폴리오 케이스의 `links` (지금은 비어 있음)와 note의 "데모와 저장소 링크는 배포 후 추가합니다." 문장

직접 하고 싶으면 `~/projects/portfolio`(가지: `content/crack-watch`)의 `src/data/projects/crack-watch.js`에서 `links: []` 를 아래처럼 바꾸면 된다.

```js
links: [
  { label: '데모', url: 'https://crack-watch-xxxx.vercel.app' },
  { label: 'GitHub', url: 'https://github.com/<사용자이름>/crack-watch' },
],
```

---

## 6. 포트폴리오에 케이스 올리기 (10분)

케이스는 `~/projects/portfolio`의 `content/crack-watch` 가지에 커밋되어 있다(파일 9개, 전부 새 파일).
**푸시하는 순간 공개 사이트에 뜬다.** 클린 팩토리 작업이 일단락된 뒤에 하는 게 좋다.

### 6-1. 저장 안 된 수정부터 정리

```bash
cd ~/projects/portfolio && git status --short
```

지금은 `skavoca.js`가 수정 상태다. 먼저 커밋하거나 되돌린 뒤 다음으로 넘어간다.

### 6-2. main에 합치고 눈으로 확인

```bash
cd ~/projects/portfolio && git merge content/crack-watch
```

충돌 없이 합쳐진다(겹치는 파일이 없다). 그다음 미리보기로 케이스를 읽어 본다.

```bash
cd ~/projects/portfolio && npm run dev
```

`http://localhost:5173/portfolio/#/p/crack-watch` 를 열어 세 가지를 봐 달라:

- 경력·역할 표현이 사실과 맞는지 (기획 3인 팀의 **팀원**, 구현은 단독)
- 수상 표기가 없는지 (이 대회는 본인 이름 상장이 없어 일부러 뺐다)
- 문장 톤이 본인 것 같은지

고칠 부분이 있으면 알려 주면 내가 고친다. 마음에 안 들어 **통째로 되돌리려면** 푸시 전에:

```bash
cd ~/projects/portfolio && git reset --hard origin/main
```

### 6-3. 올리기

```bash
cd ~/projects/portfolio && npm run build && npm run check:privacy dist
```

`0건`이 나오면:

```bash
cd ~/projects/portfolio && git push
```

푸시 뒤 `content/crack-watch` 가지는 역할이 끝나므로 `git branch -d content/crack-watch`로 지워도 된다.

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

---

## 9. 내가 할 수 있는 일 / 직접 하셔야 하는 일

| 내가 할 수 있음 | 직접 하셔야 함 |
| --- | --- |
| 링크를 README·포트폴리오 케이스에 넣기 | GitHub·Vercel·Render **계정 로그인과 생성** |
| 사진을 주면 색 오차 표 채우기 | 배포 버튼 누르기(공개 행위라 본인 확인이 필요) |
| 문구·내용 수정, 기능 추가 | 카드 인쇄와 벽 촬영, 자로 재기 |
| 오류 메시지를 주면 원인 찾기 | 휴대폰에서 처리 시간 확인 |
