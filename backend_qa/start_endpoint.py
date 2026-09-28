import os
import json

from rdflib import Graph
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

script_dir = os.path.dirname(os.path.abspath(__file__))
ttl_path = os.path.join(script_dir, "calligraphy_kg.ttl")

g = Graph()
g.parse(ttl_path, format="turtle")

app = FastAPI()


def sparql_results_to_json(results):
    """将 rdflib SPARQL 查询结果转为标准 JSON 格式"""
    vars_list = results.vars
    head = {"vars": [str(v) for v in vars_list]}
    bindings = []
    for row in results:
        binding = {}
        for var in vars_list:
            val = row[var]
            if val is not None:
                binding[str(var)] = {
                    "type": "uri" if val.startswith("http") else "literal",
                    "value": str(val),
                }
        bindings.append(binding)
    return {"head": head, "results": {"bindings": bindings}}


@app.get("/sparql")
async def sparql_get(query: str = ""):
    if not query:
        return JSONResponse(
            {"error": "Missing 'query' parameter"}, status_code=400
        )
    try:
        results = g.query(query)
        return JSONResponse(sparql_results_to_json(results))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/sparql")
async def sparql_post(request: Request):
    form = await request.form()
    query = form.get("query", "")
    if not query:
        return JSONResponse(
            {"error": "Missing 'query' parameter"}, status_code=400
        )
    try:
        results = g.query(query)
        return JSONResponse(sparql_results_to_json(results))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
