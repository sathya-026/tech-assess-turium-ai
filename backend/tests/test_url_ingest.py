"""Live URL ingestion test. Requires network access — run separately from test_api.py."""
import os, sys, time
os.environ.update(INFERENCE_PROVIDER="stub", EMBEDDING_PROVIDER="stub",
                  DATABASE_URL="sqlite+aiosqlite:////tmp/turl.db", RAG_MIN_SIMILARITY="0.0")
if os.path.exists("/tmp/turl.db"): os.remove("/tmp/turl.db")
sys.path.insert(0,'.')
import logging; logging.disable(logging.INFO)
from fastapi.testclient import TestClient
from app.main import app
from app.common.url_fetcher import validate_url

print("-- validate_url --")
for u in ["example.com/docs", "https://a.io/x", "ftp://a.io/x", "javascript:alert(1)", "", "notahost"]:
    try: print(f"   {u!r:28} -> {validate_url(u)}")
    except ValueError as e: print(f"   {u!r:28} -> REJECTED: {e}")

with TestClient(app) as c:
    r = c.post("/ingest", data={
        "text": "Refund window is 30 days.",
        "urls": ["https://pypi.org/project/fastapi/",
                 "ftp://bad.example/x", "https://raw.githubusercontent.com/this-does-not/exist-404/main/a.md"],
    })
    print("\n/ingest ->", r.status_code)
    for s in r.json()["skipped"]: print("   skipped:", s)
    for i in r.json()["items"]: print(f"   accepted: {i['source_type']:<5} {i['title'][:58]}")

    for _ in range(80):
        items = c.get("/items").json()
        if all(i["status"] in ("indexed","failed") for i in items["items"]): break
        time.sleep(0.25)

    print("\n-- after pipeline --")
    for i in items["items"]:
        print(f"   {i['status']:<8} type={i['source_type']:<5} chunks={i['chunk_count']:<3} chars={i['char_count']:<6} {i['title'][:40]}")
        if i["source_url"]: print(f"            source_url: {i['source_url']}")
        if i["error"]:      print(f"            error: {i['error'][:90]}")

    url_item = [i for i in items["items"] if i["source_type"]=="url" and i["status"]=="indexed"]
    if url_item:
        det = c.get(f"/items/{url_item[0]['id']}").json()
        print("\n   fetched text preview:", repr(det["raw_text"][:110]))
        d = c.post("/query", json={"question":"what is fastapi","top_k":2}).json()
        for s in d["sources"]:
            ok = det["raw_text"][s["char_start"]:s["char_end"]]==s["snippet"] if s["item_id"]==url_item[0]["id"] else None
            print(f"   [{s['rank']}] {s['item_title'][:34]:<36} offsets_exact={ok}")