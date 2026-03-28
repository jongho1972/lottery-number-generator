from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import httpx
import asyncio
import random
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta, date
from collections import Counter
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_DIR = Path("cache")
LOTTO_CACHE = CACHE_DIR / "lotto.json"
PENSION_CACHE = CACHE_DIR / "pension.json"
CACHE_TTL_HOURS = 24


def is_cache_valid(path: Path) -> bool:
    if not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age < timedelta(hours=CACHE_TTL_HOURS)


LOTTO_HARU_API = "https://api.lotto-haru.kr/win/analysis.json"
PENSION_DATA_FILE = Path("data/pension.json")
BATCH_SIZE = 50  # 한 번에 요청할 회차 수 (파이프로 구분)


async def fetch_latest_round(client: httpx.AsyncClient) -> int:
    r = await client.get(LOTTO_HARU_API, timeout=10)
    return r.json()[0]["chasu"]


async def fetch_lotto_batch(client: httpx.AsyncClient, sem: asyncio.Semaphore, rounds: list[int]):
    async with sem:
        try:
            chasu = "|".join(str(n) for n in rounds)
            r = await client.get(LOTTO_HARU_API, params={"chasu": chasu}, timeout=20)
            return [item["ball"] for item in r.json()]
        except Exception:
            return []


async def fetch_lotto_data() -> list:
    if is_cache_valid(LOTTO_CACHE):
        with open(LOTTO_CACHE) as f:
            return json.load(f)

    async with httpx.AsyncClient() as client:
        latest = await fetch_latest_round(client)
        logger.info(f"로또 데이터 수집 시작 (1~{latest}회)")

        batches = [list(range(i, min(i + BATCH_SIZE, latest + 1))) for i in range(1, latest + 1, BATCH_SIZE)]
        sem = asyncio.Semaphore(5)
        tasks = [fetch_lotto_batch(client, sem, b) for b in batches]
        results = await asyncio.gather(*tasks)

    all_data = [nums for batch in results for nums in batch]

    CACHE_DIR.mkdir(exist_ok=True)
    with open(LOTTO_CACHE, "w") as f:
        json.dump(all_data, f)

    logger.info(f"로또 데이터 수집 완료: {len(all_data)}회차")
    return all_data


def load_pension_data() -> list:
    """배포 시 포함된 data/pension.json 을 읽어 반환"""
    if not PENSION_DATA_FILE.exists():
        logger.warning("data/pension.json 없음 — collect_pension.py 를 먼저 실행하세요")
        return []
    with open(PENSION_DATA_FILE, encoding="utf-8") as f:
        records = json.load(f)
    return [r["numbers"] for r in records]


def generate_lotto(all_numbers: list) -> dict:
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

    cache_updated = None
    if LOTTO_CACHE.exists():
        cache_updated = datetime.fromtimestamp(LOTTO_CACHE.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

    return {
        "high_freq": result1,
        "low_freq": result2,
        "total_rounds": len(all_numbers),
        "round_range": {"start": 1, "end": len(all_numbers)},
        "top5": top5,
        "bottom5": bottom5,
        "cache_updated": cache_updated,
    }


def generate_pension(all_numbers: list) -> dict:
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
        position_stats.append({
            "pos": pos + 1,
            "top_digit": top,
            "top_count": counter[top],
        })

    cache_updated = None
    if PENSION_DATA_FILE.exists():
        cache_updated = datetime.fromtimestamp(PENSION_DATA_FILE.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

    return {
        "high_freq": high_freq,
        "low_freq": low_freq,
        "total_rounds": len(all_numbers),
        "round_range": {"start": 1, "end": len(all_numbers)},
        "position_stats": position_stats,
        "cache_updated": cache_updated,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 백그라운드에서 데이터 미리 수집
    CACHE_DIR.mkdir(exist_ok=True)
    asyncio.create_task(fetch_lotto_data())
    yield


app = FastAPI(title="복권번호생성기", lifespan=lifespan)


@app.get("/api/lotto")
async def api_lotto():
    try:
        data = await fetch_lotto_data()
        return generate_lotto(data)
    except Exception as e:
        logger.error(f"로또 생성 오류: {e}")
        return JSONResponse({"error": "데이터 로드에 실패했습니다. 잠시 후 다시 시도해주세요."}, status_code=500)


@app.get("/api/pension")
async def api_pension():
    try:
        data = load_pension_data()
        return generate_pension(data)
    except Exception as e:
        logger.error(f"연금복권 생성 오류: {e}")
        return JSONResponse({"error": "데이터 로드에 실패했습니다."}, status_code=500)


@app.get("/api/status")
async def api_status():
    lotto_rounds = 0
    if LOTTO_CACHE.exists():
        with open(LOTTO_CACHE) as f:
            lotto_rounds = len(json.load(f))
    return {
        "lotto_cached": is_cache_valid(LOTTO_CACHE),
        "lotto_rounds": lotto_rounds,
        "pension_cached": is_cache_valid(PENSION_CACHE),
    }


app.mount("/", StaticFiles(directory="static", html=True), name="static")
