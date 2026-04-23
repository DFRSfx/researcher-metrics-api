from fastapi import FastAPI, Query
from scholarly import scholarly
from pybliometrics.scopus import AuthorRetrieval
import os

app = FastAPI()

@app.get("/metrics")
def get_metrics(
    scopus_id: str = Query(None),
    scholar_id: str = Query(None)
):
    result = {}

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

    if scholar_id:
        try:
            author = scholarly.fill(scholarly.search_author_id(scholar_id))
            result["scholar"] = {
                "name": author["name"],
                "h_index": author["hindex"],
                "citations": author["citedby"],
                "i10_index": author["i10index"],
            }
        except Exception as e:
            result["scholar"] = {"error": str(e)}

    return result