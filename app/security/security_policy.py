"""
security_policy.py
------------------
Security Policy enforcement engine:
- Configures LOCAL-ONLY mode allowlist/denylist
- Validates network endpoints
- Emits prominent security alerts on unauthorized connection attempts
"""

from typing import Dict, Tuple
from app.security.audit_log import audit_logger


class SecurityPolicy:
    def __init__(self, mode: str = "LOCAL-ONLY"):
        self.mode = mode
        self.allowed_hosts = {
            "localhost",
            "127.0.0.1",
            "::1",
            "0.0.0.0",
        }
        self.allowed_subnets = ["127.", "192.168.", "10.", "172.16."]

    def is_destination_allowed(self, host: str, port: int = 80) -> Tuple[bool, str]:
        host_clean = host.lower().strip()
        if host_clean in self.allowed_hosts:
            return True, "Allowed: Localhost address"

        for subnet in self.allowed_subnets:
            if host_clean.startswith(subnet):
                return True, f"Allowed: Local private network subnet {subnet}"

        reason = f"BLOCKED: Destination '{host}:{port}' violates LOCAL-ONLY security policy. Public internet and cloud APIs are prohibited."
        return False, reason

    def log_and_raise_if_denied(self, host: str, port: int, component: str = "Unknown"):
        allowed, reason = self.is_destination_allowed(host, port)
        if not allowed:
            audit_logger.log_event(
                event_type="SECURITY_POLICY_VIOLATION",
                component=component,
                message=reason,
                status="BLOCKED",
                details={"host": host, "port": port},
            )
            raise PermissionError(f"[EXTERNAL NETWORK ATTEMPT DETECTED] Component: '{component}' -> Destination: {host}:{port} | Action: BLOCKED (Reason: LOCAL-ONLY MODE)")


security_policy = SecurityPolicy()
