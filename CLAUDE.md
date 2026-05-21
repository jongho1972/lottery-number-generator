# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# 의존성 설치
pip install -r requirements.txt

# 서버 실행 (http://localhost:8000)
uvicorn app:app --host 0.0.0.0 --port 8000

# 로또 데이터 수집 (수동, 보통은 GitHub Actions가 매주 일요일 자동 실행)
python collect_lotto.py

# 연금복권 데이터 수집 (수동, 보통은 GitHub Actions가 매주 금요일 자동 실행)
python collect_pension.py
```

## Architecture

**백엔드**: `app.py` — FastAPI 단일 파일 서버
**프론트엔드**: `static/` — 순수 HTML/CSS/JS (프레임워크 없음)

**디자인 토큰** (`static/style.css`): ETF 대시보드와 동일한 톤앤매너
- 배경: `#f0f2f6` / 강조색: `#ff4b4b` / 텍스트: `#31333f` / 테두리: `#e0e0e0`
- 헤더: 흰 배경 + `#ff4b4b` 하단 3px 보더
- 카드: 흰 배경 + 좌측 컬러 보더 (로또 노랑, 연금복권 빨강), 그라디언트 없음
- 버튼: 로또·연금복권 모두 `#ff4b4b` 통일
**데이터**: 두 종목 모두 정적 JSON 파일을 GitHub Actions cron으로 자동 갱신하는 동일한 패턴

| 복권 종류 | 데이터 소스 | 정적 파일 | 자동 갱신 (KST) |
|-----------|------------|------|------|
| 로또 6/45 | `www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do` (동행복권 공식 ajax) | `data/lotto.json` | 매주 일요일 09:00 |
| 연금복권 720+ | `www.dhlottery.co.kr/pt720/selectPstPt720WnList.do` (동행복권 공식 API) | `data/pension.json` | 매주 금요일 09:00 |

### 데이터 흐름

- **로또**: `collect_lotto.py`가 `/lt645/result` 페이지로 세션 쿠키 확보 + 최신 회차 파싱 → `selectPstLt645InfoNew.do?srchDir=older&srchCursorLtEpsd=N` 으로 10건씩 페이지네이션해 전체 수집 → `data/lotto.json` 저장. 앱은 이 파일을 정적으로 읽음(`load_lotto_data()`).
- **연금복권**: `collect_pension.py`가 `/pt720/selectPstPt720WnList.do`로 전체 회차 수집 → `data/pension.json` 저장. 앱은 이 파일을 정적으로 읽음(`load_pension_data()`).
- 두 종목 모두 GitHub Actions(.github/workflows/collect-{lotto,pension}.yml)가 추첨 다음 날 KST 09:00에 cron 실행 → 변경 사항이 있을 경우 `data/*.json`을 자동 커밋·푸시 → **이어서 같은 잡이 `gh workflow run deploy.yml`로 배포를 명시 트리거** → VPS 반영.
- ⚠️ 데이터 자동 반영의 핵심 주의점: `deploy.yml`은 `paths-ignore: data/**` 라서 데이터 푸시 자체로는 배포가 걸리지 않고, `Dockerfile`이 `COPY . .`로 데이터를 이미지에 굽기 때문에 반영하려면 반드시 재빌드(=배포)가 필요하다. 또한 GitHub 정책상 `GITHUB_TOKEN`이 만든 push는 다른 워크플로우를 트리거하지 못한다(`workflow_dispatch`·`repository_dispatch`만 예외). 그래서 수집 잡이 `actions: write` 권한으로 `deploy.yml`을 `workflow_dispatch`로 직접 호출하는 구조다. 이 트리거 스텝을 제거하면 cron이 GitHub엔 데이터를 올려도 라이브 사이트엔 반영되지 않으니 주의.

### 번호 생성 알고리즘

두 복권 모두 고빈도/저빈도 두 가지 전략으로 번호를 추천한다.

- **로또**: 전체 회차 번호별 출현 빈도로 확률 계산 → `확률 × random()`으로 고빈도 추천, `(1/확률) × random()`으로 저빈도 추천
- **연금복권**: 자리(0~5)별로 독립적으로 빈도 계산 → 동일한 두 전략을 각 자리에 적용해 고빈도/저빈도 6자리 각각 생성

### API 응답 구조

- **`/api/lotto`**: `high_freq`, `low_freq`, `total_rounds`, `round_range`, `top5`, `bottom5`, `cache_updated`
- **`/api/pension`**: `high_freq`, `low_freq`, `total_rounds`, `round_range`, `cache_updated`, `position_stats[]`
  - `position_stats` 각 항목: `pos`, `top_digit`, `top_count`, `bottom_digit`, `bottom_count`

### GitHub 푸시 전 체크리스트

GitHub Actions가 두 종목 모두 자동 갱신·배포하므로 일반적으론 별도 작업 불필요.
- 추첨 직후 즉시 반영이 필요하면 GitHub Actions에서 collect 워크플로우의 "Run workflow" 버튼 실행 → 변경분 커밋·푸시 후 배포까지 자동 진행됨
- 로컬에서 `python collect_lotto.py` / `python collect_pension.py` 후 직접 커밋·푸시한 경우, 데이터만 바뀌었다면 `deploy.yml`이 `paths-ignore: data/**`로 안 걸리므로 `gh workflow run deploy.yml --ref main`으로 배포를 수동 트리거해야 라이브에 반영된다
- `cache/` 디렉토리는 더 이상 사용하지 않음 (이전 런타임 캐시 잔여 폴더, `.gitignore`로 무시됨)

### 배포

- **플랫폼**: j-hawk VPS (Hetzner CAX11 ARM · Docker Compose + Caddy)
- **저장소**: https://github.com/jongho1972/lottery-number-generator
- **서비스 URL**: https://lottery.jhawk.kr
- GitHub `main` 브랜치 푸시 시 `.github/workflows/deploy.yml`이 VPS에 SSH 접속 → `git reset --hard origin/main` → `docker compose build/up lottery` → `/healthz` 헬스체크
- 단, `deploy.yml`은 `paths-ignore: data/** · cache/** · *.md · *.ipynb` 로 코드 변경이 없는 푸시(데이터·문서만)는 배포하지 않는다. 데이터 갱신은 수집 워크플로우가 `workflow_dispatch`로 별도 트리거하고, 데이터·문서만 수동 반영할 때는 `gh workflow run deploy.yml --ref main` 사용
- 공통 인프라·롤백·트러블슈팅: 워크스페이스 루트 `deploy/README.md` 또는 `vps-deploy` 스킬

### 외부 API 주의사항

- 동행복권 사이트는 봇 차단(Tracer 솔루션)이 강함 — 구 엔드포인트(`common.do?method=getLottoNumber`, `/gameResult.do?method=byWin`, 모바일 도메인 `m.dhlottery.co.kr`)는 errorPage / error.html 로 리다이렉트되어 직접 호출 불가
- 정상 호출 가능한 엔드포인트(세션 쿠키 + UA + Referer + `X-Requested-With: XMLHttpRequest`):
  - 로또: `https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do?srchDir={center|older|latest}&srchLtEpsd=N` (또는 `srchCursorLtEpsd=N`) — 한 번에 10건씩, `tm1WnNo~tm6WnNo`, `bnsWnNo`, `ltRflYmd` 포함
  - 연금복권: `https://www.dhlottery.co.kr/pt720/selectPstPt720WnList.do` — 전체 회차를 한 번에 반환
- 최신 회차는 `https://www.dhlottery.co.kr/lt645/result` HTML의 `$("#d-trigger_txt").text("NNNN" + '회')` 패턴에서 추출 (서버사이드 렌더링됨)
