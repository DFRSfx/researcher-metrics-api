from fastapi import FastAPI, Query
from scholarly import scholarly, ProxyGenerator
from pybliometrics.scopus import AuthorRetrieval
import os

app = FastAPI()

# Inicializa o proxy ScraperAPI uma vez ao arrancar
pg = ProxyGenerator()
pg.ScraperAPI(os.environ["SCRAPERAPI_KEY"])  # ← a tua key
scholarly.use_proxy(pg)

@app.get("/metrics")
def get_metrics(
    scholar_id: str = Query(None),
    scopus_id: str = Query(None)
):
    result = {}

    if scholar_id:
        try:
            author = scholarly.fill(scholarly.search_author_id(scholar_id))
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