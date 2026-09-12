"""
chunker.py
----------
Simple sliding-window chunker. Keeps source filename + chunk index in
metadata so the agent can cite "manual.pdf, section 3" style sources back
to the user - important for the "grounded, not hallucinated" requirement.
"""

import hashlib


def chunk_text(
    text: str,
    source_name: str,
    chunk_size: int = 800,
    overlap: int = 150,
) -> tuple[list[str], list[dict], list[str]]:
    words = text.split()
    chunks, metadatas, ids = [], [], []

    step = max(chunk_size - overlap, 1)
    idx = 0
    chunk_num = 0
    while idx < len(words):
        window = words[idx: idx + chunk_size]
        if not window:
            break
        chunk = " ".join(window)
        chunk_id = hashlib.sha256(f"{source_name}-{chunk_num}-{chunk[:50]}".encode()).hexdigest()[:16]

        chunks.append(chunk)
        metadatas.append({"source": source_name, "chunk_index": chunk_num})
        ids.append(chunk_id)

        chunk_num += 1
        idx += step

    return chunks, metadatas, ids
