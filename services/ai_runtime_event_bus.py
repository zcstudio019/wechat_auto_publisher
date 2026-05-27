"""Lightweight JSON event bus for the AI Runtime OS event layer."""

import json
from datetime import datetime, timezone
from pathlib import Path

from services.ai_runtime_event_registry import get_runtime_event_registry


class AIRuntimeEventBus:
    """Append-only read/write event bus with safe JSON fallback."""

    EVENT_FILE_PATH = Path(__file__).resolve().parents[1] / "data" / "ai_runtime_events.json"
    MAX_EVENTS = 500

    def __init__(self, event_file_path: str | Path | None = None):
        self.event_file_path = Path(event_file_path) if event_file_path else self.EVENT_FILE_PATH
        self.registry = get_runtime_event_registry()

    def publish(self, event_key, payload=None):
        definition = self.registry.get(event_key)
        if not definition:
            definition = {
                "event_key": event_key,
                "severity": "warning",
                "layer": "unknown",
                "description": "Unregistered runtime event.",
            }
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_key": event_key,
            "severity": definition.get("severity") or "warning",
            "layer": definition.get("layer") or "unknown",
            "description": definition.get("description") or "",
            "payload": dict(payload or {}),
        }
        events = self._read_events()
        events.append(event)
        events = events[-self.MAX_EVENTS:]
        self._write_events(events)
        return event

    def get_recent_events(self, limit=50):
        events = self._read_events()
        safe_limit = max(0, int(limit or 0))
        if safe_limit <= 0:
            return []
        return list(reversed(events[-safe_limit:]))

    def get_events_by_severity(self, severity):
        return [event for event in self._read_events() if event.get("severity") == severity]

    def get_events_by_layer(self, layer):
        return [event for event in self._read_events() if event.get("layer") == layer]

    def clear_old_events(self, max_keep=500):
        safe_keep = max(0, int(max_keep or 0))
        events = self._read_events()
        kept = events[-safe_keep:] if safe_keep else []
        self._write_events(kept)
        return kept

    def _read_events(self):
        try:
            if not self.event_file_path.exists():
                return []
            with self.event_file_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict):
                data = data.get("events") or []
            if not isinstance(data, list):
                return []
            return [event for event in data if isinstance(event, dict)]
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return []

    def _write_events(self, events):
        try:
            self.event_file_path.parent.mkdir(parents=True, exist_ok=True)
            with self.event_file_path.open("w", encoding="utf-8") as file:
                json.dump(list(events or []), file, ensure_ascii=False, indent=2)
        except OSError:
            return
