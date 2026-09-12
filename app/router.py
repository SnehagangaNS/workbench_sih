"""
router.py
---------
Picks which local model handles a given task based on capability tags and
local Ollama model availability.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.ollama_client import ollama

CONFIG_PATH = Path(__file__).parent.parent / "config" / "models.yaml"


@dataclass
class ModelInfo:
    name: str
    role: str
    capabilities: list[str]
    vram_gb: float
    display_name: str


class Router:
    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self._load()

    def _load(self):
        with open(self.config_path, "r") as f:
            cfg = yaml.safe_load(f)
        self.router_model = cfg["router_model"]
        self.models = [ModelInfo(**m) for m in cfg["models"]]
        self.task_routing = cfg["task_routing"]

    def reload(self):
        """Hot-reload the registry (e.g. after editing models.yaml)."""
        self._load()

    def _by_capability(self, capability: str) -> ModelInfo | None:
        for m in self.models:
            if capability in m.capabilities and m.role == "chat":
                return m
        return None

    _CLASSIFY_PATTERNS = {
        "code": r"\b(code|coding|script|function|bug|debug|python|refactor|programming|program)\b",
        "spreadsheet": r"\b(spreadsheet|excel|xlsx|csv|calculate|calculation|formula|budget|sum|total)\b",
        "image": r"\b(scan|scanned|photo|image|handwritten|handwriting|drawing|ocr|picture)\b",
        "document": r"\b(summarize|summarise|summary|report|document|pdf|manual|extract)\b",
    }

    def _rule_based_task_type(self, task_text: str) -> str | None:
        t = task_text.lower()
        for task_type, pattern in self._CLASSIFY_PATTERNS.items():
            if re.search(pattern, t):
                return task_type
        return None

    async def _llm_classify(self, task_text: str) -> str:
        task_types = list(self.task_routing.keys())
        prompt = (
            f"Classify this task into exactly one category: {task_types}.\n"
            f"Task: \"{task_text}\"\n"
            f"Reply with ONLY the category word, nothing else."
        )
        try:
            resp = await ollama.chat(
                model=self.router_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            answer = resp["message"]["content"].strip().lower()
            for t in task_types:
                if t in answer:
                    return t
        except Exception:
            pass
        return "general"

    async def route(self, task_text: str) -> tuple[ModelInfo, str]:
        """Returns (chosen ModelInfo, task_type) for the given task description."""
        task_type = self._rule_based_task_type(task_text)
        if task_type is None:
            task_type = await self._llm_classify(task_text)

        try:
            local_pulled = await ollama.list_local_models()
        except Exception:
            local_pulled = []

        capabilities = self.task_routing.get(task_type, ["general"])

        # 1. Try to find a model matching capability that IS PULLED
        for cap in capabilities:
            for m in self.models:
                if cap in m.capabilities and m.role == "chat":
                    if not local_pulled or any(m.name in p or p.startswith(m.name) for p in local_pulled):
                        return m, task_type

        # 2. Try general fallback that IS PULLED
        for m in self.models:
            if "general" in m.capabilities and m.role == "chat":
                if not local_pulled or any(m.name in p or p.startswith(m.name) for p in local_pulled):
                    return m, task_type

        # 3. Try any chat model in models.yaml
        chat_models = [m for m in self.models if m.role == "chat"]
        if chat_models:
            return chat_models[0], task_type

        # 4. Emergency fallback: if local_pulled has ANY model, build dynamic ModelInfo
        if local_pulled:
            chosen = local_pulled[0]
            return ModelInfo(
                name=chosen,
                role="chat",
                capabilities=["general"],
                vram_gb=4.0,
                display_name=chosen.split(":")[0].title(),
            ), task_type

        return self.models[0], task_type

    def vision_model(self) -> ModelInfo:
        vision_models = [m for m in self.models if m.role == "vision"]
        return vision_models[0] if vision_models else self.models[0]

    def embedding_model(self) -> ModelInfo:
        embed_models = [m for m in self.models if m.role == "embedding"]
        return embed_models[0] if embed_models else self.models[0]

    def estimated_vram_gb(self, model: ModelInfo) -> float:
        return model.vram_gb


router = Router()
