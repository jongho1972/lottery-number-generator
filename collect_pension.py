"""
연금복권 720+ 과거 당첨번호 수집 스크립트
- 동행복권 API에서 전체 회차 데이터 수집 → data/pension.json 저장
- 배포 전 실행하거나 신규 회차 추가 시 재실행하세요.
- 실행: python collect_pension.py
"""

import json
import urllib.request
from pathlib import Path

API_URL = "https://www.dhlottery.co.kr/pt720/selectPstPt720WnList.do"
OUTPUT_FILE = Path(__file__).parent / "data" / "pension.json"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)


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
    with urllib.request.urlopen(req, timeout=15) as r:
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
