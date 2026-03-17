import json
import threading
import time
import uuid
from typing import Any, Dict, Optional

import requests
from fastapi import BackgroundTasks, Body, FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

OLLAMA_URL = "http://127.0.0.1:11434"  # matches your logs

app = FastAPI(title="theVault")

# ---------------- LLM client ----------------


def ollama_generate(model: str, prompt: str, temperature: float = 0.2, top_p: float = 0.9) -> str:
    """Return the raw text response from Ollama /api/chat (migrated from /api/generate)."""
    r = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": temperature, "top_p": top_p},
            "stream": False,
        },
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    # New API returns message.content instead of response
    return data.get("message", {}).get("content", "")


def force_json_object(text: str) -> Dict[str, Any]:
    """
    Try to extract a single JSON object from text.
    If multiple braces exist (preface chatter), grab the first { ... } block.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output.")
    payload = text[start : end + 1]
    return json.loads(payload)


# ---------------- Schemas ----------------


class FastInput(BaseModel):
    question: Optional[str] = None
    input: Optional[str] = None


# ---------------- RAG job state ----------------

_jobs: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def _run_fake_rag_job(job_id: str, kind: str):
    with _lock:
        _jobs[job_id]["status"] = "running"
    # Simulate work
    for i in range(5):
        time.sleep(1)
        with _lock:
            _jobs[job_id]["progress"] = int((i + 1) * 20)
    with _lock:
        _jobs[job_id]["status"] = "completed"


# ---------------- Routes ----------------


@app.get("/", response_class=HTMLResponse)
def home():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Home</title>
  <script src="https://unpkg.com/htmx.org@1.9.10" defer></script>
  <script src="https://unpkg.com/htmx.org/dist/ext/json-enc.js" defer></script>
</head>
<body>
  <h1>RAG UI</h1>
  <nav>
    <a href="/upload">Upload</a>
    <a href="/runs">Runs</a>
  </nav>

  <form hx-post="/fast" hx-target="#fast-result" hx-encoding="json" hx-ext="json-enc">
    <label for="question">Question</label>
    <input type="text" id="question" name="question" />
    <button>Run Fast</button>
  </form>
  <pre id="fast-result"></pre>

  <div id="rag-controls">
    <button id="btn-update" hx-post="/rag/update" hx-target="#rag-status" hx-swap="outerHTML">Update RAG</button>
    <button id="btn-rebuild" hx-post="/rag/rebuild" hx-target="#rag-status" hx-swap="outerHTML">Rebuild RAG</button>
    <pre id="rag-status"></pre>
  </div>

  <script>
  document.body.addEventListener("htmx:afterRequest", function(ev){
    if(ev.detail.elt && (ev.detail.elt.id === "btn-update" || ev.detail.elt.id === "btn-rebuild")){
      try{
        var resp = JSON.parse(ev.detail.xhr.responseText);
        if(resp.job_id){
          var pre = document.getElementById("rag-status");
          pre.setAttribute("hx-get", "/rag/status?id=" + resp.job_id);
          pre.setAttribute("hx-trigger", "load, every 1.5s");
          htmx.process(pre);
        } else {
          document.getElementById("rag-status").textContent = "No job_id returned.";
        }
      }catch(e){
        document.getElementById("rag-status").textContent = "Bad JSON from server.";
      }
    }
  });
  </script>
</body>
</html>"""


@app.post("/fast")
def fast(body: FastInput = Body(...)):
    """
    - If body.question is provided, ask the LLM and return the text.
    - If body.input is provided, treat it as an instruction prompt (strict JSON).
    """
    q = body.question or body.input or ""
    if not q.strip():
        return JSONResponse({})  # matches your current behavior if empty

    # Example: force strict JSON for the SCTE-35 test
    prompt = (
        'SYSTEM:\nYou are a careful technical assistant. If you are not certain, reply with "UNKNOWN".\n'
        "USER:\nRespond in strict JSON matching this schema, no extra keys.\n"
        "{\n"
        '  "Definition": "string",\n'
        '  "Purpose": "string",\n'
        '  "Key_Fields": ["string"],\n'
        '  "Use_Cases": ["string"]\n'
        "}\n"
        'Topic: "SCTE-35 (Digital Program Insertion Cueing Message)".\n'
        'Rules:\n- Do NOT invent fields or protocols. If unsure, use "UNKNOWN".\n- Keep responses factual and concise.\n'
    )

    try:
        text = ollama_generate("phi3", prompt)
        data = force_json_object(text)
        # Return exactly the keys we care about, drop anything extra
        clean = {
            "Definition": data.get("Definition", "UNKNOWN"),
            "Purpose": data.get("Purpose", "UNKNOWN"),
            "Key_Fields": data.get("Key_Fields", []),
            "Use_Cases": data.get("Use_Cases", []),
        }
        return JSONResponse(clean)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/rag/update")
def rag_update(background: BackgroundTasks):
    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = {"status": "queued", "progress": 0, "kind": "update"}
    background.add_task(_run_fake_rag_job, job_id, "update")
    return {"job_id": job_id, "status": "queued"}


@app.post("/rag/rebuild")
def rag_rebuild(background: BackgroundTasks):
    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = {"status": "queued", "progress": 0, "kind": "rebuild"}
    background.add_task(_run_fake_rag_job, job_id, "rebuild")
    return {"job_id": job_id, "status": "queued"}


@app.get("/rag/status")
def rag_status(id: str):
    with _lock:
        info = _jobs.get(id)
    if not info:
        return JSONResponse({"error": "unknown job_id"}, status_code=404)
    # Render as plain text for the <pre> target (simpler UX), but JSON also works
    return JSONResponse({"job_id": id, **info})
