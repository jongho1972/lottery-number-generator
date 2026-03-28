# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# 의존성 설치
pip install -r requirements.txt

# 서버 실행 (http://localhost:8000)
uvicorn app:app --host 0.0.0.0 --port 8000

# 연금복권 데이터 수집 (배포 전 또는 신규 회차 추가 시)
python collect_pension.py
```

## Architecture

**백엔드**: `app.py` — FastAPI 단일 파일 서버
**프론트엔드**: `static/` — 순수 HTML/CSS/JS (프레임워크 없음)
**데이터**: 두 가지 방식으로 분리 운영

| 복권 종류 | 데이터 소스 | 캐시 |
|-----------|------------|------|
| 로또 6/45 | `api.lotto-haru.kr` (비공식 JSON API) | `cache/lotto.json` (24시간) |
| 연금복권 720+ | `data/pension.json` (배포 파일에 포함된 정적 파일) | 없음 |

### 데이터 흐름

- **로또**: 앱 시작 시 `lifespan`에서 백그라운드로 `fetch_lotto_data()` 실행 → `api.lotto-haru.kr`에서 50회차 단위 배치 요청 → `cache/lotto.json`에 저장. 24시간 캐시 유효 시 재수집 안 함.
- **연금복권**: `collect_pension.py`를 로컬에서 실행하면 `www.dhlottery.co.kr/pt720/selectPstPt720WnList.do` API로 전체 회차를 수집해 `data/pension.json`에 저장. 앱은 이 파일을 정적으로 읽음(`load_pension_data()`).

### 번호 생성 알고리즘

두 복권 모두 고빈도/저빈도 두 가지 전략으로 번호를 추천한다.

- **로또**: 전체 회차 번호별 출현 빈도로 확률 계산 → `확률 × random()`으로 고빈도 추천, `(1/확률) × random()`으로 저빈도 추천
- **연금복권**: 자리(0~5)별로 독립적으로 빈도 계산 → 동일한 두 전략을 각 자리에 적용해 고빈도/저빈도 6자리 각각 생성

### 배포

- **플랫폼**: Render (무료 플랜)
- **저장소**: https://github.com/jongho1972/lottery-number-generator
- **서비스 URL**: https://lottery-number-generator.onrender.com
- GitHub `main` 브랜치 푸시 시 Render 자동 배포
- 무료 플랜은 비활성 시 스핀다운 → 첫 요청 약 50초 대기 발생

### 외부 API 주의사항

- `dhlottery.co.kr` 공식 사이트는 봇 차단으로 직접 HTTP 요청 불가 (errorPage 리다이렉트)
- 로또 JSON API(`common.do?method=getLottoNumber`)도 동일하게 차단됨 → `api.lotto-haru.kr` 사용
- 연금복권 신규 페이지 URL: `https://www.dhlottery.co.kr/pt720/result` (구 URL `gameResult.do?method=win720`은 404)
- `collect_pension.py`가 사용하는 `selectPstPt720WnList.do`는 세션 없이 접근 가능
