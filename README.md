# 통계 기반 복권번호 생성기

과거 당첨번호 통계를 분석해 로또 6/45와 연금복권 720+ 번호를 추천해주는 웹 서비스입니다.

🔗 **서비스 주소**: https://lottery-number-generator.onrender.com

## 기능

- **로또 6/45**: 전체 회차 당첨번호 빈도 분석 → 자주 나온 번호 / 덜 나온 번호 각각 추천
- **연금복권 720+**: 자리별 독립 빈도 분석 → 자주 나온 번호 / 덜 나온 번호 각각 추천

## 기술 스택

- **Backend**: FastAPI, httpx
- **Frontend**: HTML / CSS / JavaScript (프레임워크 없음)
- **데이터**: [lotto-haru.kr API](https://api.lotto-haru.kr) (로또), 동행복권 API (연금복권)
- **배포**: Render

## 로컬 실행

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

## 연금복권 데이터 갱신

신규 회차가 추가되면 아래 스크립트를 실행 후 재배포합니다.

```bash
python collect_pension.py
```

## 개발

이종호 (jongho1972@gmail.com)
