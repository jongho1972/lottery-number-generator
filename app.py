from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import random
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import Counter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LOTTO_DATA_FILE = Path("data/lotto.json")
PENSION_DATA_FILE = Path("data/pension.json")


def load_lotto_data() -> list[dict]:
    """배포 시 포함된 data/lotto.json 을 읽어 회차 레코드 리스트 반환"""
    if not LOTTO_DATA_FILE.exists():
        logger.warning("data/lotto.json 없음 — collect_lotto.py 를 먼저 실행하세요")
        return []
    with open(LOTTO_DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_pension_data() -> list[dict]:
    """배포 시 포함된 data/pension.json 을 읽어 회차 레코드 리스트 반환"""
    if not PENSION_DATA_FILE.exists():
        logger.warning("data/pension.json 없음 — collect_pension.py 를 먼저 실행하세요")
        return []
    with open(PENSION_DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def file_mtime_str(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def normalize_date(s: str | None) -> str | None:
    """'YYYYMMDD' / 'YYYY-MM-DD' / 'YYYY.MM.DD' → 'YYYY-MM-DD'"""
    if not s:
        return None
    digits = s.replace("-", "").replace(".", "")
    if len(digits) == 8 and digits.isdigit():
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return s


def generate_lotto(records: list[dict]) -> dict:
    all_numbers = [r["numbers"] for r in records]
    latest_date = normalize_date(records[-1].get("date")) if records else None
    flat = [n for row in all_numbers for n in row]
    counter = Counter(flat)
    for n in range(1, 46):
        if n not in counter:
            counter[n] = 1
    total = sum(counter.values())
    probs = {k: v / total for k, v in counter.items()}

    scores1 = {k: random.random() * v for k, v in probs.items()}
    result1 = sorted(sorted(scores1, key=scores1.get, reverse=True)[:6])

    scores2 = {k: random.random() / v for k, v in probs.items()}
    result2 = sorted(sorted(scores2, key=scores2.get, reverse=True)[:6])

    sorted_by_freq = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    top5 = [{"number": n, "count": c} for n, c in sorted_by_freq[:5]]
    bottom5 = [{"number": n, "count": c} for n, c in sorted_by_freq[-5:]]

    return {
        "high_freq": result1,
        "low_freq": result2,
        "total_rounds": len(all_numbers),
        "round_range": {"start": 1, "end": len(all_numbers), "end_date": latest_date},
        "top5": top5,
        "bottom5": bottom5,
        "cache_updated": file_mtime_str(LOTTO_DATA_FILE),
    }


def generate_pension(records: list[dict]) -> dict:
    all_numbers = [r["numbers"] for r in records]
    latest_date = normalize_date(records[-1].get("date")) if records else None
    if not all_numbers:
        rand6 = [str(random.randint(0, 9)) for _ in range(6)]
        return {
            "high_freq": rand6,
            "low_freq": rand6,
            "total_rounds": 0,
            "position_stats": [],
            "cache_updated": None,
        }

    high_freq = []
    low_freq = []
    position_stats = []
    for pos in range(6):
        digits = [row[pos] for row in all_numbers]
        counter = Counter(digits)
        for d in "0123456789":
            if d not in counter:
                counter[d] = 1
        total = sum(counter.values())
        probs = {k: v / total for k, v in counter.items()}

        scores_high = {k: random.random() * v for k, v in probs.items()}
        high_freq.append(max(scores_high, key=scores_high.get))

        scores_low = {k: random.random() / v for k, v in probs.items()}
        low_freq.append(max(scores_low, key=scores_low.get))

        top = max(counter, key=counter.get)
        bottom = min(counter, key=counter.get)
        position_stats.append({
            "pos": pos + 1,
            "top_digit": top,
            "top_count": counter[top],
            "bottom_digit": bottom,
            "bottom_count": counter[bottom],
        })

    return {
        "high_freq": high_freq,
        "low_freq": low_freq,
        "total_rounds": len(all_numbers),
        "round_range": {"start": 1, "end": len(all_numbers), "end_date": latest_date},
        "position_stats": position_stats,
        "cache_updated": file_mtime_str(PENSION_DATA_FILE),
    }


KST = timezone(timedelta(hours=9))
DEPLOY_TIME = datetime.now(KST).strftime("%Y년 %m월 %d일 %H:%M")


app = FastAPI(title="복권번호생성기")


@app.middleware("http")
async def no_cache_for_static(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/api/lotto")
async def api_lotto():
    try:
        data = load_lotto_data()
        return generate_lotto(data)
    except Exception as e:
        logger.error(f"로또 생성 오류: {e}")
        return JSONResponse({"error": "데이터 로드에 실패했습니다."}, status_code=500)


@app.get("/api/pension")
async def api_pension():
    try:
        data = load_pension_data()
        return generate_pension(data)
    except Exception as e:
        logger.error(f"연금복권 생성 오류: {e}")
        return JSONResponse({"error": "데이터 로드에 실패했습니다."}, status_code=500)


@app.get("/api/deploy-time")
async def api_deploy_time():
    return {"deploy_time": DEPLOY_TIME}


@app.get("/healthz")
async def healthz():
    return {"ok": True}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
