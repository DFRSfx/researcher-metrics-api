from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from scholarly import scholarly, ProxyGenerator
from pybliometrics.scopus import AuthorRetrieval
import os
import threading
import time
import requests

_scholarly_lock = threading.Lock()
_cache: dict = {}
_CACHE_TTL = 86400  # 24 hours


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data: dict):
    _cache[key] = {"data": data, "ts": time.time()}


def _fetch_scholar_openalex(scholar_id: str) -> dict | None:
    url = "https://api.openalex.org/authors"
    profile_url = f"https://scholar.google.com/citations?user={scholar_id}"
    try:
        resp = requests.get(
            url,
            params={"filter": f"ids.google_scholar:{profile_url}", "select": "display_name,summary_stats,cited_by_count,works_count"},
            headers={"User-Agent": "researcher-metrics-api/1.0 (mailto:dariofrsoares@gmail.com)"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None
        author = results[0]
        stats = author.get("summary_stats", {})
        h_index = stats.get("h_index")
        if not h_index:
            return None
        return {
            "name": author.get("display_name"),
            "h_index": h_index,
            "citations": author.get("cited_by_count"),
            "i10_index": stats.get("i10_index"),
            "source": "openalex",
        }
    except Exception:
        return None


def _fetch_scholar_scholarly(scholar_id: str) -> dict:
    with _scholarly_lock:
        author = scholarly.fill(scholarly.search_author_id(scholar_id), sections=["basics", "indices"])
    return {
        "name": author.get("name"),
        "h_index": author.get("hindex"),
        "citations": author.get("citedby"),
        "i10_index": author.get("i10index"),
        "source": "google_scholar",
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Write pybliometrics config from env var (no persistent filesystem on Vercel)
    scopus_key = "9f09f1bdd9719456decd316ef59a4d70"
    config_dir = "/tmp/pybliometrics/Scopus"
    os.makedirs(config_dir, exist_ok=True)
    config_path = "/tmp/pybliometrics/pybliometrics.cfg"
    os.environ["PYB_CONFIG_FILE"] = config_path
    with open(config_path, "w") as f:
        f.write(f"[Authentication]\nAPIKey = {scopus_key}\n")

    pg = ProxyGenerator()
    pg.ScraperAPI("3a70ca2369ad3945c2e46ff97ec0b571")
    scholarly.use_proxy(pg)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/metrics")
def get_metrics(
    scholar_id: str = Query(None),
    scopus_id: str = Query(None)
):
    result = {}

    if scholar_id:
        cached = _cache_get(f"scholar:{scholar_id}")
        if cached:
            result["scholar"] = cached
        else:
            try:
                data = _fetch_scholar_openalex(scholar_id)
                if data is None:
                    data = _fetch_scholar_scholarly(scholar_id)
                _cache_set(f"scholar:{scholar_id}", data)
                result["scholar"] = data
            except Exception as e:
                result["scholar"] = {"error": str(e)}

    if scopus_id:
        cached = _cache_get(f"scopus:{scopus_id}")
        if cached:
            result["scopus"] = cached
        else:
            try:
                au = AuthorRetrieval(scopus_id)
                data = {
                    "name": au.indexed_name,
                    "h_index": au.h_index,
                    "citations": au.cited_by_count,
                    "documents": au.document_count,
                }
                _cache_set(f"scopus:{scopus_id}", data)
                result["scopus"] = data
            except Exception as e:
                result["scopus"] = {"error": str(e)}

    return result
