"""
연금복권 720+ 과거 당첨번호 수집 스크립트
- 동행복권 API에서 전체 회차 데이터 수집 → data/pension.json 저장
- 배포 전 실행하거나 신규 회차 추가 시 재실행하세요.
- 실행: python collect_pension.py
"""

import json
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://www.dhlottery.co.kr/pt720/selectPstPt720WnList.do"
OUTPUT_FILE = Path(__file__).parent / "data" / "pension.json"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

TIMEOUT = 30  # 단일 요청 타임아웃(초). GitHub Actions 러너에서 동행복권 응답이 느릴 때 대비
MAX_RETRIES = 4  # 타임아웃·일시적 연결 오류 시 최대 시도 횟수 (지수 백오프)


def urlopen_with_retry(req: urllib.request.Request):
    """타임아웃·일시적 연결 오류를 지수 백오프로 재시도하며 응답을 반환한다."""
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return urllib.request.urlopen(req, timeout=TIMEOUT)
        except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
            last_err = e
            if attempt < MAX_RETRIES:
                wait = 2 ** attempt
                print(f"  요청 실패({e}) — {wait}s 후 재시도 ({attempt}/{MAX_RETRIES - 1})")
                time.sleep(wait)
    raise RuntimeError(f"{MAX_RETRIES}회 시도 후에도 요청 실패: {last_err}")


def fetch_pension_data() -> list[dict]:
    print("연금복권 데이터 수집 중...")
    req = urllib.request.Request(
        API_URL,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://www.dhlottery.co.kr/pt720/result",
            "Accept": "application/json, text/plain, */*",
        },
    )
    with urlopen_with_retry(req) as r:
        raw = json.loads(r.read())

    results = raw["data"]["result"]
    data = []
    for item in results:
        numbers = list(str(item["wnRnkVl"]).zfill(6))
        data.append({
            "round": item["psltEpsd"],
            "date": item["psltRflYmd"],
            "numbers": numbers,
        })

    return sorted(data, key=lambda x: x["round"])


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    data = fetch_pension_data()
    if not data:
        print("수집된 데이터가 없습니다.")
        return

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"완료: {len(data)}회차 저장 → {OUTPUT_FILE}")
    print(f"  1회차:  {data[0]}")
    print(f"  최신회차: {data[-1]}")


if __name__ == "__main__":
    main()
