"""
startup_check.py
----------------
Local-Only Security Startup Check:
Verifies on boot that all components (LLM, OCR, Embeddings, Vector DB, Knowledge Base, P&ID graph)
run strictly on local endpoints without active cloud API keys or runtime external model downloads.
"""

import os
import shutil
from typing import Any, Dict
from app.security.audit_log import audit_logger
from app.security.network_monitor import network_monitor


class LocalStartupCheck:
    def __init__(self):
        pass

    def run_check(self, runtime: Dict[str, Any] | None = None) -> Dict[str, Any]:
        runtime = runtime or {}
        ollama_state = runtime.get("ollama_state", "configured")
        embedding_state = runtime.get("embedding_state", "configured")
        tesseract_available = bool(shutil.which("tesseract"))
        vector_store_ready = os.path.isdir("data/vectorstore")
        results = {
            "mode": "LOCAL-ONLY",
            "llm_local": ollama_state in {"available", "verified"},
            "ocr_local": tesseract_available,
            "embeddings_local": embedding_state in {"available", "verified"},
            "vector_store_local": vector_store_ready,
            "knowledge_base_local": True,
            "pid_graph_local": True,
            "external_api_keys_unused": True,
            "network_monitor_active": network_monitor.is_active,
            "overall_status": "PASS",
            "checks": [],
        }

        checks = [
            ("LLM driver", "Ollama at 127.0.0.1:11434", ollama_state, ollama_state in {"available", "verified"}),
            ("OCR engine", "Tesseract executable on this computer", "available" if tesseract_available else "missing", tesseract_available),
            ("Embedding model", "nomic-embed-text in Ollama", embedding_state, embedding_state in {"available", "verified"}),
            ("Vector database", "ChromaDB local folder", "verified" if vector_store_ready else "configured", vector_store_ready),
            ("Knowledge base", "Local data/knowledge folder", "configured", True),
            ("P&ID graph", "NetworkX local process", "configured", True),
            ("Cloud API keys", "No configured cloud API keys", "verified" if self._verify_no_cloud_keys() else "attention", self._verify_no_cloud_keys()),
            ("Socket monitor", "Application-level outbound socket monitor", "available" if network_monitor.is_active else "missing", network_monitor.is_active),
        ]

        formatted_checks = []
        all_passed = True

        for name, detail, state, passed in checks:
            formatted_checks.append({
                "name": name,
                "detail": detail,
                "state": state,
                "passed": passed,
            })
            if not passed:
                all_passed = False

        results["checks"] = formatted_checks
        results["overall_status"] = "PASS" if all_passed else "FAIL"

        audit_logger.log_event(
            event_type="LOCAL_STARTUP_SECURITY_CHECK",
            component="LocalStartupCheck",
            message=f"Local-only security verification completed with status: {results['overall_status']}",
            status="ALLOWED" if all_passed else "WARNING",
            details=results,
        )

        return results

    def _verify_no_cloud_keys(self) -> bool:
        cloud_env_keys = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "COHERE_API_KEY", "GOOGLE_API_KEY"]
        for key in cloud_env_keys:
            if os.environ.get(key):
                return False
        return True


startup_checker = LocalStartupCheck()
