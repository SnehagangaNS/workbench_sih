"""
sessions.py
-----------
Manages persistent chat sessions saved as JSON files in data/sessions/.
Provides CRUD utilities for session listing, retrieval, saving, and deletion.
"""

import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SESSIONS_DIR = BASE_DIR / "data" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def list_sessions() -> list[dict]:
    """Returns a list of saved sessions sorted by updated_at descending."""
    sessions = []
    for p in SESSIONS_DIR.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                sessions.append({
                    "id": data.get("id", p.stem),
                    "title": data.get("title", "Untitled Chat"),
                    "task": data.get("task", ""),
                    "model": data.get("model", "auto"),
                    "created_at": data.get("created_at", int(p.stat().st_ctime)),
                    "updated_at": data.get("updated_at", int(p.stat().st_mtime)),
                })
        except Exception:
            continue
    sessions.sort(key=lambda s: s["updated_at"], reverse=True)
    return sessions


def get_session(session_id: str) -> dict | None:
    """Retrieves full session payload by ID."""
    p = SESSIONS_DIR / f"{session_id}.json"
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_session(session_id: str, data: dict) -> dict:
    """Saves or updates a session payload atomically."""
    p = SESSIONS_DIR / f"{session_id}.json"
    now = int(time.time())
    
    existing = get_session(session_id) or {}
    
    # Deriving clean short title from task prompt
    task_text = data.get("task") or existing.get("task") or "Untitled Task"
    title = data.get("title") or existing.get("title")
    if not title:
        title = task_text[:40].strip() + ("..." if len(task_text) > 40 else "")

    payload = {
        "id": session_id,
        "title": title,
        "task": data.get("task", existing.get("task", "")),
        "model": data.get("model", existing.get("model", "auto")),
        "output": data.get("output", existing.get("output", "")),
        "trace_logs": data.get("trace_logs", existing.get("trace_logs", [])),
        "deliverables": data.get("deliverables", existing.get("deliverables", [])),
        "created_at": existing.get("created_at", now),
        "updated_at": now,
    }

    tmp_path = p.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    tmp_path.replace(p)
    return payload


def delete_session(session_id: str) -> bool:
    """Removes session file from disk."""
    p = SESSIONS_DIR / f"{session_id}.json"
    if p.exists():
        try:
            p.unlink()
            return True
        except Exception:
            return False
    return False
