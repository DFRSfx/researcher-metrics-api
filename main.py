from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from scholarly import scholarly, ProxyGenerator
from pybliometrics.scopus import AuthorRetrieval
import os
import threading

_scholarly_lock = threading.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    pg = ProxyGenerator()
    pg.ScraperAPI(os.environ["SCRAPERAPI_KEY"])
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
        try:
            with _scholarly_lock:
                author = scholarly.fill(scholarly.search_author_id(scholar_id), sections=["basics", "indices"])
            result["scholar"] = {
                "name": author.get("name"),
                "h_index": author.get("hindex"),
                "citations": author.get("citedby"),
                "i10_index": author.get("i10index"),
            }
        except Exception as e:
            result["scholar"] = {"error": str(e)}

    if scopus_id:
        try:
            au = AuthorRetrieval(scopus_id)
            result["scopus"] = {
                "name": au.indexed_name,
                "h_index": au.h_index,
                "citations": au.cited_by_count,
                "documents": au.document_count,
            }
        except Exception as e:
            result["scopus"] = {"error": str(e)}

    return result