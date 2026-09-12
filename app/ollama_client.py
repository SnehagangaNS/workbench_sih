"""
ollama_client.py
-----------------
Thin wrapper around the local Ollama HTTP API (http://localhost:11434).
Everything here is fully offline once models are pulled - no external calls.

Ollama already does dynamic model load/unload and VRAM management for us
(models are loaded on first request and evicted after `keep_alive` idles
out), so the "router holds several models" requirement is satisfied by
Ollama's own scheduler - our router just decides WHICH model name to call.
"""

import base64
import json
from typing import Any, AsyncGenerator, Optional

import httpx

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_KEEP_ALIVE = "5m"  # unload idle models after 5 min to free VRAM

# On a 6GB card, context window size matters as much as model size: KV cache
# grows with num_ctx and can push an 8B Q4 model past available VRAM. Keep
# this modest for the demo; raise it only if your GPU has headroom. Also set
# OLLAMA_KV_CACHE_TYPE=q8_0 as an environment variable before starting
# `ollama serve` to roughly halve KV cache memory with minimal quality loss.
DEFAULT_NUM_CTX = 8192


class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL, timeout: float = 300.0):
        self.base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def health(self) -> bool:
        try:
            r = await self._client.get("/api/tags")
            return r.status_code == 200
        except Exception:
            return False

    async def list_local_models(self) -> list[str]:
        r = await self._client.get("/api/tags")
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]

    async def chat(
        self,
        model: str,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        stream: bool = False,
        temperature: float = 0.2,
    ) -> dict:
        """Single-shot (non-streaming) chat call. Returns the full response dict."""
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": DEFAULT_KEEP_ALIVE,
            "options": {"temperature": temperature, "num_ctx": DEFAULT_NUM_CTX},
        }
        if tools:
            payload["tools"] = tools
        r = await self._client.post("/api/chat", json=payload)
        r.raise_for_status()
        return r.json()

    async def chat_stream(
        self,
        model: str,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.2,
    ) -> AsyncGenerator[dict, None]:
        """Streaming chat call. Yields each JSON chunk as it arrives."""
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "keep_alive": DEFAULT_KEEP_ALIVE,
            "options": {"temperature": temperature},
        }
        if tools:
            payload["tools"] = tools
        async with self._client.stream("POST", "/api/chat", json=payload) as resp:
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                yield json.loads(line)

    async def vision_chat(self, model: str, prompt: str, image_path: str) -> str:
        """Send a single image + prompt to a vision model. Returns the text response."""
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt, "images": [img_b64]}],
            "stream": False,
            "keep_alive": DEFAULT_KEEP_ALIVE,
        }
        r = await self._client.post("/api/chat", json=payload)
        r.raise_for_status()
        return r.json()["message"]["content"]

    async def embed(self, model: str, text: str) -> list[float]:
        payload = {"model": model, "prompt": text}
        r = await self._client.post("/api/embeddings", json=payload)
        r.raise_for_status()
        return r.json()["embedding"]

    async def embed_batch(self, model: str, texts: list[str], max_concurrency: int = 4) -> list[list[float]]:
        """Batch embeddings with concurrency throttling to prevent Ollama server 500 errors."""
        import asyncio

        sem = asyncio.Semaphore(max_concurrency)

        async def _bounded_embed(t: str) -> list[float]:
            async with sem:
                try:
                    return await self.embed(model, t)
                except Exception:
                    await asyncio.sleep(0.5)
                    return await self.embed(model, t)

        return list(await asyncio.gather(*[_bounded_embed(t) for t in texts]))

    async def close(self):
        await self._client.aclose()


ollama = OllamaClient()
