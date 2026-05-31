"""
로또 6/45 과거 당첨번호 수집 스크립트
- 동행복권 공식 ajax 엔드포인트(/lt645/selectPstLt645InfoNew.do) 호출 → data/lotto.json 저장
- 배포 전 실행하거나 GitHub Actions가 매주 일요일 자동 실행
- 실행: python collect_lotto.py
"""

import json
import re
import socket
import time
import urllib.error
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
TIMEOUT = 30  # 단일 요청 타임아웃(초). GitHub Actions 러너에서 동행복권 응답이 느릴 때 대비
MAX_RETRIES = 4  # 타임아웃·일시적 연결 오류 시 최대 시도 횟수 (지수 백오프)


def open_with_retry(opener: urllib.request.OpenerDirector, url: str):
    """타임아웃·일시적 연결 오류를 지수 백오프로 재시도하며 응답을 반환한다."""
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return opener.open(url, timeout=TIMEOUT)
        except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
            last_err = e
            if attempt < MAX_RETRIES:
                wait = 2 ** attempt
                print(f"  요청 실패({e}) — {wait}s 후 재시도 ({attempt}/{MAX_RETRIES - 1})")
                time.sleep(wait)
    raise RuntimeError(f"{MAX_RETRIES}회 시도 후에도 요청 실패: {last_err}")


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
    with open_with_retry(opener, REFERER) as r:
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
    with open_with_retry(opener, url) as r:
        return json.loads(r.read())


def load_existing() -> dict[int, dict]:
    """기존 lotto.json을 {회차: 레코드} 로 읽는다.

    파일이 없거나 손상됐거나 회차가 1~max로 연속이지 않으면 빈 dict를 반환해
    전체 재수집으로 강등한다(증분 수집은 stop_at 아래 갭을 메우지 못하므로).
    """
    if not OUTPUT_FILE.exists():
        return {}
    try:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            existing = {rec["round"]: rec for rec in json.load(f)}
    except (json.JSONDecodeError, KeyError, OSError):
        return {}
    if existing and set(existing) != set(range(1, max(existing) + 1)):
        print("기존 데이터에 누락 회차 발견 — 전체 재수집으로 강등")
        return {}
    return existing


def normalize(item: dict) -> dict:
    numbers = [item[f"tm{i}WnNo"] for i in range(1, 7)]
    ymd = str(item.get("ltRflYmd", ""))
    date = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}" if len(ymd) == 8 else ymd
    return {
        "round": item["ltEpsd"],
        "date": date,
        "numbers": numbers,
        "bonus": item.get("bnsWnNo"),
    }


def fetch_lotto_data() -> list[dict]:
    """기존 데이터를 보존하고 새 회차만 증분 수집한다.

    매번 1회차부터 전량 재수집(~123 요청)하면 GitHub Actions 러너에서 한 요청만
    타임아웃돼도 작업 전체가 실패한다. 그래서 이미 가진 최대 회차(stop_at)까지만
    older 페이지네이션을 돌고, 그 이전은 기존 데이터를 재사용한다.
    """
    existing = load_existing()
    stop_at = max(existing) if existing else 0

    opener, html = build_opener()
    latest = parse_latest_round(html)

    if existing and latest <= stop_at:
        print(f"이미 최신 회차({stop_at}회)까지 보유 — 신규 데이터 없음")
        return [existing[ep] for ep in sorted(existing)]

    if existing:
        print(f"증분 수집: 기존 {stop_at}회 → 최신 {latest}회 ({latest - stop_at}건)")
    else:
        print(f"전체 수집: 1~{latest}회")

    collected: dict[int, dict] = dict(existing)

    initial = get_json(opener, {"srchDir": "center", "srchLtEpsd": str(latest)})
    initial_list = initial.get("data", {}).get("list", []) or []
    if not initial_list:
        raise RuntimeError("최신 회차 데이터를 받지 못했습니다.")
    for item in initial_list:
        collected[item["ltEpsd"]] = normalize(item)

    # older 페이지네이션: 이미 가진 회차(stop_at)에 도달하면 중단
    cursor = min(item["ltEpsd"] for item in initial_list)
    while cursor > max(stop_at, 1):
        data = get_json(opener, {"srchDir": "older", "srchCursorLtEpsd": cursor})
        items = data.get("data", {}).get("list", []) or []
        if not items:
            break
        for item in items:
            collected[item["ltEpsd"]] = normalize(item)
        new_cursor = min(item["ltEpsd"] for item in items)
        if new_cursor >= cursor:
            break  # 진행이 없으면 중단
        cursor = new_cursor

    return [collected[ep] for ep in sorted(collected)]


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
