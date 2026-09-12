# Local Workbench

An air-gapped AI workbench: a router that picks the right local model per
task, an agent loop that plans and calls tools (files, sandboxed code,
spreadsheets, document search) iteratively, multimodal ingestion (OCR +
vision model for scans/handwriting/drawings), retrieval-grounded answers
against your own documents, and real deliverables (Word / Excel / PowerPoint
/ code) as output — not chat replies.

Runs entirely on-device via [Ollama](https://ollama.com). No API keys, no
cloud calls, works fully offline once models are pulled.

---

## 1. One-time setup (needs internet)

```powershell
# from the project root, in PowerShell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

This creates a Python venv and installs dependencies. It will tell you if
you're missing:
- **Ollama** — https://ollama.com/download/windows
- **Tesseract OCR** — https://github.com/UB-Mannheim/tesseract/wiki (add to PATH)
- **Poppler** — https://github.com/oschwartz10612/poppler-windows/releases (add `Library\bin` to PATH)

Install whichever are missing, then check/pull models:

```powershell
ollama list                                              # see what you already have
powershell -ExecutionPolicy Bypass -File scripts\pull_models.ps1   # pulls anything missing
```

This project currently expects: `qwen2.5-coder:7b-instruct-q4_K_M` (coding),
`qwen2.5:3b-instruct-q4_K_M` (general/document/routing), `moondream:latest`
(vision/OCR), `nomic-embed-text` (embeddings) — all four are small enough to
have likely already downloaded quickly. **After this step you can
disconnect from the internet — everything below runs fully air-gapped.**

## 2. Running it

```powershell
# terminal 1: start Ollama (skip if it's already running as a service)
ollama serve

# terminal 2: start the workbench
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000** in a browser. That's the whole app — one
page, three panels: models on the left, task + live agent trace in the
centre, documents/outputs on the right.

## 3. Suggested demo script

1. **Show the model roster** (left panel) — point out it's reading
   `config/models.yaml`, and that adding a new model is a config edit, not
   a code change.
2. **Ingest a real document** (right panel — upload a scanned manual or a
   photo of a handwritten note). Watch the trace show which path it took
   (PDF text layer vs. Tesseract OCR vs. vision model) — this demonstrates
   the multimodal ingestion requirement directly.
3. **Ask a grounded question** about that document in the task box, e.g.
   *"What does the manual say about the maintenance interval? Summarise it
   into a Word report with sources."* Watch the trace: routing decision →
   `search_documents` call → retrieved passages → `generate_word_report`
   call → download link appears. This is the full pipeline in one task.
4. **Run a spreadsheet task**: *"Read data/uploads/budget.csv, calculate
   the total and average per category, and produce an Excel workbook with
   live formulas."* Open the resulting .xlsx and click a formula cell live
   — judges can see it's a real formula, not a pasted number.
5. **Run a coding task**: *"Write a Python function that validates IPv4
   addresses, test it against 5 cases in the sandbox, and save it as a
   file."* Shows routing to the coding model and the sandboxed execution
   tool.

Keeping to these 3-4 flows well-rehearsed beats improvising — know the
exact filenames/paths you'll type before you're on stage.

## 4. Architecture

```
Router (config/models.yaml)          Agent loop (app/agent.py)
  rule-based + LLM classifier   -->    plan -> tool call -> observe -> repeat
  picks model per task type            (ReAct-style, max 8 steps)
        |                                        |
        v                                        v
   Ollama (localhost:11434)              Tools (app/tools/*)
   hot-swaps models, manages VRAM         file I/O, sandboxed code exec,
                                           spreadsheet ops, document search,
                                           Word/Excel/PPT generation
        ^                                        |
        |                                        v
Ingestion (app/ingestion/ocr.py)      RAG (app/rag/*)
  PDF text layer / Tesseract OCR /      ChromaDB vector store,
  vision model (handwriting,            Ollama embeddings (nomic-embed-text)
  drawings, photos)
```

Why these specific choices:
- **Ollama does the model-holding/hot-swapping**, not custom code — it
  already manages VRAM and loads/unloads models on demand with a
  `keep_alive` window. Reinventing that on a 6GB card would be wasted
  effort; the router's job is purely *which* model, not memory management.
- **The agent loop is a plain, visible ReAct loop**, not a framework
  (no LangChain agent executor) — every tool call streams to the UI, so
  the "iterating rather than answering once" requirement is something
  judges watch happen, not something you have to claim.
- **Excel output uses live formulas** (`=SUM(...)`, `=B2*C2`), not
  precomputed values, so "calculations with steps shown" is auditable by
  clicking a cell, not just asserted in a report.

## 5. Known limitations (worth being upfront about with judges)

- **Code sandboxing is process-isolation + timeout, not a security
  boundary.** Good enough for a prototype; a production version would run
  each execution in a container with `--network=none`.
- **6GB VRAM is tight** for an 8B model with a large context window. We
  default to a 4096-token context (`app/ollama_client.py`) and quantized
  models throughout; if you hit an OOM live, the fallback is switching
  `task_routing` in `config/models.yaml` to route `document`/`general`
  tasks to the 3B model instead of the 8B one.
- **Moondream (vision) is small/fast but not the strongest OCR model** —
  test it against your real scanned handwriting/drawings before the demo.
  If it struggles, `ollama pull qwen2.5vl:3b` and swap the vision entry in
  `config/models.yaml` (commented instructions are right there).
- **The agent loop caps at 8 steps** — deliberately, so a demo task can't
  spiral. Complex multi-file tasks may need that raised (`MAX_STEPS` in
  `app/agent.py`).
- **Single-user prototype** — no auth, no multi-session isolation. Fine for
  a demo, not for deployment as-is.

## 6. Adding a new model (no code changes)

Edit `config/models.yaml`:

```yaml
models:
  - name: "your-new-model:tag"
    role: chat            # chat | vision | embedding
    capabilities: [coding, general, ...]
    vram_gb: 5.0
    display_name: "Friendly Name"
```

Then `ollama pull your-new-model:tag` and restart the server (or call the
`router.reload()` hot-reload path). It's immediately available for routing.

## 7. Moving to the college GPU server later

The architecture doesn't change — Ollama runs the same way on Linux with a
real GPU, just point `OLLAMA_BASE_URL` in `app/ollama_client.py` (or set it
via environment variable) at the server's address, and you can load larger,
unquantized models by editing `config/models.yaml`. No other code changes
needed — that's the point of keeping the model layer behind one interface.
