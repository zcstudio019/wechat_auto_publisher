"""Lightweight JSON store for AI Runtime cognitive memory."""

import json
from datetime import datetime, timezone
from pathlib import Path


class AIRuntimeMemoryStore:
    """Append/read/search Runtime memories with safe JSON fallback."""

    MEMORY_FILE_PATH = Path(__file__).resolve().parents[1] / "data" / "ai_runtime_memory.json"
    MAX_MEMORIES = 1000

    def __init__(self, memory_file_path: str | Path | None = None):
        self.memory_file_path = Path(memory_file_path) if memory_file_path else self.MEMORY_FILE_PATH

    def append_memory(self, memory: dict) -> dict:
        item = self._normalize_memory(memory or {})
        memories = self.read_memories()
        memories.append(item)
        memories = memories[-self.MAX_MEMORIES:]
        self._write_memories(memories)
        return item

    def read_memories(self) -> list[dict]:
        try:
            if not self.memory_file_path.exists():
                return []
            with self.memory_file_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict):
                data = data.get("memories") or []
            if not isinstance(data, list):
                return []
            return [item for item in data if isinstance(item, dict)]
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return []

    def recent_memories(self, limit=50) -> list[dict]:
        safe_limit = max(0, int(limit or 0))
        if safe_limit <= 0:
            return []
        return list(reversed(self.read_memories()[-safe_limit:]))

    def search_memories(self, query: str, limit=50) -> list[dict]:
        text = str(query or "").strip().lower()
        if not text:
            return self.recent_memories(limit)
        matches = []
        for item in reversed(self.read_memories()):
            searchable = " ".join([
                str(item.get("memory_type") or ""),
                str(item.get("layer") or ""),
                str(item.get("title") or ""),
                str(item.get("summary") or ""),
                " ".join(str(value) for value in item.get("signals") or []),
                " ".join(str(value) for value in item.get("risks") or []),
                " ".join(str(value) for value in item.get("actions") or []),
                str(item.get("outcome") or ""),
                str(item.get("confidence") or ""),
            ]).lower()
            if text in searchable:
                matches.append(item)
            if len(matches) >= max(0, int(limit or 0)):
                break
        return matches

    def _write_memories(self, memories: list[dict]) -> None:
        try:
            self.memory_file_path.parent.mkdir(parents=True, exist_ok=True)
            with self.memory_file_path.open("w", encoding="utf-8") as file:
                json.dump(list(memories or []), file, ensure_ascii=False, indent=2)
        except OSError:
            return

    @staticmethod
    def _normalize_memory(memory: dict) -> dict:
        return {
            "timestamp": memory.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            "memory_type": memory.get("memory_type") or "runtime_observation",
            "layer": memory.get("layer") or "Runtime Memory Layer",
            "title": memory.get("title") or "",
            "summary": memory.get("summary") or "",
            "signals": list(memory.get("signals") or []),
            "risks": list(memory.get("risks") or []),
            "actions": list(memory.get("actions") or []),
            "outcome": memory.get("outcome") or "",
            "confidence": memory.get("confidence") or "medium",
        }
