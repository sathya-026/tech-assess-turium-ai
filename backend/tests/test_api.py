"""End-to-end test of the wired pipeline. Keyless — uses stub providers."""
import os, sys, time

os.environ.update(
    INFERENCE_PROVIDER="stub", EMBEDDING_PROVIDER="stub",
    DATABASE_URL="sqlite+aiosqlite:////tmp/t2.db",
    RAG_MIN_SIMILARITY="0.0",   # stub vectors have no semantics; don't filter
)
if os.path.exists("/tmp/t2.db"): os.remove("/tmp/t2.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging; logging.disable(logging.INFO)
from fastapi.testclient import TestClient
from app.main import app

doc = open('/mnt/project/RAG_Foundations.md', 'rb').read()

with TestClient(app) as c:
    print("health:", {k: v for k, v in c.get("/health").json().items() if k != "status"})

    # Includes a deliberately short note (25 chars) — the min_chunk_chars
    # fragment filter must not reject an entire short document — and an invalid
    # URL, which must be rejected synchronously without creating an item.
    r = c.post("/ingest",
        data={"text": "Refund window is 30 days.", "urls": ["ftp://bad.example/x"]},
        files=[("files", ("rag_notes.md", doc, "text/markdown"))])
    print("\n/ingest ->", r.status_code, "| skipped:", r.json()["skipped"])
    assert len(r.json()["skipped"]) == 1, "bad-scheme URL should be skipped"
    assert len(r.json()["items"]) == 2, "bad URL must not create an item"

    for _ in range(60):
        items = c.get("/items").json()
        if all(i["status"] in ("indexed", "failed") for i in items["items"]): break
        time.sleep(0.1)
    for i in items["items"]:
        print(f"   {i['status']:<8} chunks={i['chunk_count']:<3} {i['title'][:34]}")
        assert i["status"] == "indexed", i["error"]
    print("   indexed_chunks:", items["indexed_chunks"])
    assert c.get("/items?status=indexed").json()["total"] == 2, "status filter broken"
    short = [i for i in items["items"] if i["source_type"] == "text"][0]
    assert short["chunk_count"] == 1, "short pasted note must still produce a chunk"

    print("\n-- stateless query --")
    d = c.post("/query", json={"question": "how does HyDE work", "top_k": 3}).json()
    print("   conversation_id:", d["conversation_id"], "| rag_hit:", d["rag_hit"])
    print("   answer:", d["answer"][:100])
    for s in d["sources"]:
        print(f"   [{s['rank']}] sim={s['similarity']:.4f} rrf={s['score']:.5f} "
              f"[{s['char_start']}:{s['char_end']}] {s['section_path'][:34]}")
    assert d["sources"] and d["conversation_id"] is None

    print("\n-- conversational --")
    q1 = c.post("/query", json={"question": "what is the refund window?", "session_id": "s1"}).json()
    q2 = c.post("/query", json={"question": "and who do I contact?", "session_id": "s1"}).json()
    print("   turn1:", q1["answer"][:78])
    print("   turn2:", q2["answer"][:78])
    assert q1["conversation_id"] == q2["conversation_id"], "session not reused"
    t1 = int(q1["answer"].split("history_turns=")[1].split()[0])
    t2 = int(q2["answer"].split("history_turns=")[1].split()[0])
    print(f"   history grew across turns: {t1} -> {t2}")
    assert t2 > t1, "memory not replayed into turn 2"

    src = d["sources"][0]
    raw = c.get(f"/items/{src['item_id']}").json()["raw_text"]
    ok = raw[src["char_start"]:src["char_end"]] == src["snippet"]
    print("\noffset round-trip:", ok); assert ok

    fid = [i["id"] for i in items["items"] if i["source_type"] == "text"][0]
    q3 = c.post("/query", json={"question": "HyDE", "item_ids": [fid], "top_k": 3}).json()
    scoped = all(s["item_id"] == fid for s in q3["sources"])
    print("item_ids filter respected:", scoped); assert scoped

    assert c.delete(f"/items/{fid}").status_code == 204
    print("delete -> chunks now:", c.get("/items").json()["indexed_chunks"])
    print("\nALL CHECKS PASSED")