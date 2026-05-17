"""
로또 6/45 과거 당첨번호 수집 스크립트
- 동행복권 공식 ajax 엔드포인트(/lt645/selectPstLt645InfoNew.do) 호출 → data/lotto.json 저장
- 배포 전 실행하거나 GitHub Actions가 매주 일요일 자동 실행
- 실행: python collect_lotto.py
"""

import json
import re
import urllib.parse
import urllib.request
import http.cookiejar
from pathlib import Path

BASE = "https://www.dhlottery.co.kr"
REFERER = f"{BASE}/lt645/result"
AJAX_URL = f"{BASE}/lt645/selectPstLt645InfoNew.do"
OUTPUT_FILE = Path(__file__).parent / "data" / "lotto.json"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

PAGE_SIZE = 10  # 엔드포인트가 한 번에 반환하는 회차 수 (고정)


def build_opener() -> tuple[urllib.request.OpenerDirector, str]:
    """세션 쿠키 확보 + 결과 페이지 HTML 반환 (최신 회차 추출용)."""
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [
        ("User-Agent", USER_AGENT),
        ("Referer", REFERER),
        ("X-Requested-With", "XMLHttpRequest"),
        ("Accept", "application/json, text/javascript, */*; q=0.01"),
    ]
    with opener.open(REFERER, timeout=15) as r:
        html = r.read().decode("utf-8", errors="ignore")
    return opener, html


def parse_latest_round(html: str) -> int:
    # 페이지 JS에서 최신 회차를 변수로 세팅 — '...text("1224" + '회')'
    m = re.search(r'\$\("#d-trigger_txt"\)\.text\("(\d+)"\s*\+\s*\'회\'\)', html)
    if m:
        return int(m.group(1))
    # 백업: 회차 셀렉트박스 옵션에서 가장 큰 숫자
    rounds = [int(n) for n in re.findall(r'(\d{3,5})회', html)]
    if rounds:
        return max(rounds)
    raise RuntimeError("최신 회차를 HTML에서 찾을 수 없습니다.")


def get_json(opener, params: dict) -> dict:
    url = f"{AJAX_URL}?{urllib.parse.urlencode(params)}"
    with opener.open(url, timeout=15) as r:
        return json.loads(r.read())


def fetch_lotto_data() -> list[dict]:
    opener, html = build_opener()
    latest = parse_latest_round(html)
    print(f"로또 데이터 수집 중 (1~{latest}회)...")

    initial = get_json(opener, {"srchDir": "center", "srchLtEpsd": str(latest)})
    initial_list = initial.get("data", {}).get("list", []) or []
    if not initial_list:
        raise RuntimeError("최신 회차 데이터를 받지 못했습니다.")

    collected: dict[int, dict] = {item["ltEpsd"]: item for item in initial_list}

    # older 페이지네이션: 가장 작은 회차를 cursor로 다음 10건 반복
    cursor = min(item["ltEpsd"] for item in initial_list)
    while cursor > 1:
        data = get_json(opener, {"srchDir": "older", "srchCursorLtEpsd": cursor})
        items = data.get("data", {}).get("list", []) or []
        if not items:
            break
        for item in items:
            collected[item["ltEpsd"]] = item
        new_cursor = min(item["ltEpsd"] for item in items)
        if new_cursor >= cursor:
            break  # 진행이 없으면 중단
        cursor = new_cursor

    data = []
    for ep in sorted(collected.keys()):
        item = collected[ep]
        numbers = [item[f"tm{i}WnNo"] for i in range(1, 7)]
        ymd = str(item.get("ltRflYmd", ""))
        date = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}" if len(ymd) == 8 else ymd
        data.append({
            "round": item["ltEpsd"],
            "date": date,
            "numbers": numbers,
            "bonus": item.get("bnsWnNo"),
        })

    return data


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    data = fetch_lotto_data()
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
