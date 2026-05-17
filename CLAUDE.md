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
- 두 종목 모두 GitHub Actions(.github/workflows/collect-{lotto,pension}.yml)가 추첨 다음 날 KST 09:00에 cron 실행 → 변경 사항이 있을 경우 `data/*.json`을 자동 커밋·푸시 → VPS 자동 배포로 반영.

### 번호 생성 알고리즘

두 복권 모두 고빈도/저빈도 두 가지 전략으로 번호를 추천한다.

- **로또**: 전체 회차 번호별 출현 빈도로 확률 계산 → `확률 × random()`으로 고빈도 추천, `(1/확률) × random()`으로 저빈도 추천
- **연금복권**: 자리(0~5)별로 독립적으로 빈도 계산 → 동일한 두 전략을 각 자리에 적용해 고빈도/저빈도 6자리 각각 생성

### API 응답 구조

- **`/api/lotto`**: `high_freq`, `low_freq`, `total_rounds`, `round_range`, `top5`, `bottom5`, `cache_updated`
- **`/api/pension`**: `high_freq`, `low_freq`, `total_rounds`, `round_range`, `cache_updated`, `position_stats[]`
  - `position_stats` 각 항목: `pos`, `top_digit`, `top_count`, `bottom_digit`, `bottom_count`

### GitHub 푸시 전 체크리스트

GitHub Actions가 두 종목 모두 자동 갱신하므로 일반적으론 별도 작업 불필요.
- 추첨 직후 즉시 반영이 필요하면 GitHub Actions의 "Run workflow" 버튼 또는 로컬에서 `python collect_lotto.py` / `python collect_pension.py` 후 커밋
- `cache/` 디렉토리는 더 이상 사용하지 않음 (이전 런타임 캐시 잔여 폴더, `.gitignore`로 무시됨)

### 배포

- **플랫폼**: Render (무료 플랜)
- **저장소**: https://github.com/jongho1972/lottery-number-generator
- **서비스 URL**: https://lottery-number-generator.onrender.com
- GitHub `main` 브랜치 푸시 시 Render 자동 배포
- 무료 플랜은 비활성 시 스핀다운 → 첫 요청 약 50초 대기 발생

### 외부 API 주의사항

- 동행복권 사이트는 봇 차단(Tracer 솔루션)이 강함 — 구 엔드포인트(`common.do?method=getLottoNumber`, `/gameResult.do?method=byWin`, 모바일 도메인 `m.dhlottery.co.kr`)는 errorPage / error.html 로 리다이렉트되어 직접 호출 불가
- 정상 호출 가능한 엔드포인트(세션 쿠키 + UA + Referer + `X-Requested-With: XMLHttpRequest`):
  - 로또: `https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do?srchDir={center|older|latest}&srchLtEpsd=N` (또는 `srchCursorLtEpsd=N`) — 한 번에 10건씩, `tm1WnNo~tm6WnNo`, `bnsWnNo`, `ltRflYmd` 포함
  - 연금복권: `https://www.dhlottery.co.kr/pt720/selectPstPt720WnList.do` — 전체 회차를 한 번에 반환
- 최신 회차는 `https://www.dhlottery.co.kr/lt645/result` HTML의 `$("#d-trigger_txt").text("NNNN" + '회')` 패턴에서 추출 (서버사이드 렌더링됨)
