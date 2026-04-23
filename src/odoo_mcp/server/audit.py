from __future__ import annotations

import base64
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    """Append-only JSONL audit log for MCP tool/resource calls."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def write_event(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.write("\n")


_AUDIT_LOGGER: AuditLogger | None = None
_AUDIT_PATH: Path | None = None


def get_audit_log_path() -> Path:
    raw_path = os.environ.get("MCP_AUDIT_LOG_PATH", "logs/odoo_audit.jsonl")
    return Path(raw_path)


def get_audit_logger() -> AuditLogger:
    path = get_audit_log_path()
    global _AUDIT_LOGGER, _AUDIT_PATH
    if _AUDIT_LOGGER is None or _AUDIT_PATH != path:
        _AUDIT_LOGGER = AuditLogger(path)
        _AUDIT_PATH = path
    return _AUDIT_LOGGER


def reset_audit_logger() -> None:
    global _AUDIT_LOGGER, _AUDIT_PATH
    _AUDIT_LOGGER = None
    _AUDIT_PATH = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_export_metadata(payload: dict[str, Any]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = [payload]
    nested_result = payload.get("result")
    if isinstance(nested_result, dict):
        candidates.append(nested_result)

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        has_export_hint = any(
            key in candidate
            for key in (
                "file_name",
                "file_path",
                "saved_file_name",
                "file_content",
                "file_content_base64",
                "file_type",
            )
        )
        if not has_export_hint:
            continue

        export: dict[str, Any] = {}
        for key in (
            "file_name",
            "saved_file_name",
            "file_path",
            "file_type",
            "file_size_bytes",
            "run_id",
            "company_id",
            "stage",
            "page",
            "records_per_page",
            "delivery",
        ):
            value = candidate.get(key)
            if value is not None:
                export[key] = value

        if "file_size_bytes" not in export:
            export["file_size_bytes"] = _extract_file_size(candidate)

        if export.get("file_size_bytes") is None:
            export.pop("file_size_bytes", None)

        return export or None

    return None


def _extract_file_size(candidate: dict[str, Any]) -> int | None:
    for key in ("file_content_base64", "file_content"):
        raw_value = candidate.get(key)
        if not isinstance(raw_value, str):
            continue
        try:
            return len(base64.b64decode(raw_value))
        except Exception:
            return None
    return None
