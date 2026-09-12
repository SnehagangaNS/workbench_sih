"""
audit_log.py
------------
Persistent local security audit log:
Saves security events, local component startup checks, network monitoring logs,
and blocked connection attempts to data/security_audit.log.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

SECURITY_LOG_DIR = Path(__file__).parent.parent.parent / "data"
SECURITY_LOG_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG_FILE = SECURITY_LOG_DIR / "security_audit.log"


class SecurityAuditLogger:
    def __init__(self, log_path: Path = AUDIT_LOG_FILE):
        self.log_path = log_path

    def log_event(
        self,
        event_type: str,
        component: str,
        message: str,
        status: str = "ALLOWED",
        details: Dict[str, Any] | None = None,
    ):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "component": component,
            "message": message,
            "status": status,
            "details": details or {},
        }

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        logs = []
        if not self.log_path.exists():
            return logs

        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in reversed(lines):
                    line = line.strip()
                    if line:
                        try:
                            logs.append(json.loads(line))
                            if len(logs) >= limit:
                                break
                        except Exception:
                            continue
        except Exception:
            pass
        return logs


audit_logger = SecurityAuditLogger()
