"""
component_registry.py
--------------------
Registry of all application components, services, and their execution locations.
Proves that every system dependency runs locally/on-premise.
"""

from typing import Dict, List


class ComponentRegistry:
    def __init__(self):
        self.components = [
            {
                "name": "Local LLM Driver",
                "component_id": "ollama_llm",
                "type": "Inference Engine",
                "location": "localhost:11434",
                "status": "LOCAL-ONLY",
                "details": "Ollama local server (Qwen 2.5 3B/7B, Llama 3.2)",
            },
            {
                "name": "Local Embeddings",
                "component_id": "ollama_embed",
                "type": "Embedding Generator",
                "location": "localhost:11434",
                "status": "LOCAL-ONLY",
                "details": "Ollama local nomic-embed-text model",
            },
            {
                "name": "Local OCR Engine",
                "component_id": "tesseract_ocr",
                "type": "Text Extraction",
                "location": "local process",
                "status": "LOCAL-ONLY",
                "details": "Pytesseract / OpenCV on-device OCR",
            },
            {
                "name": "P&ID Symbol Detector",
                "component_id": "yolo_sahi",
                "type": "Visual Object Detector",
                "location": "local process",
                "status": "LOCAL-ONLY",
                "details": "OpenCV geometric contour & local YOLO inference",
            },
            {
                "name": "P&ID Knowledge Graph",
                "component_id": "networkx_pid",
                "type": "Graph Engine",
                "location": "local process",
                "status": "LOCAL-ONLY",
                "details": "NetworkX directed engineering graph",
            },
            {
                "name": "Local Vector Store",
                "component_id": "chromadb_local",
                "type": "Vector Database",
                "location": "localhost (data/vectorstore)",
                "status": "LOCAL-ONLY",
                "details": "ChromaDB local persistent client",
            },
            {
                "name": "Organizational Knowledge Connector",
                "component_id": "local_knowledge_connector",
                "type": "Knowledge Index",
                "location": "local/on-premise (data/knowledge)",
                "status": "LOCAL-ONLY",
                "details": "Local file shares, manuals, SOPs, past correspondence",
            },
            {
                "name": "Frontend & Web UI",
                "component_id": "fastapi_frontend",
                "type": "User Interface",
                "location": "localhost:8000",
                "status": "LOCAL-ONLY",
                "details": "FastAPI static template server",
            },
            {
                "name": "Backend Orchestrator",
                "component_id": "fastapi_backend",
                "type": "REST & WS API Server",
                "location": "localhost:8000",
                "status": "LOCAL-ONLY",
                "details": "FastAPI local app server",
            },
        ]

    def list_components(self) -> List[Dict[str, str]]:
        return self.components


component_registry = ComponentRegistry()
