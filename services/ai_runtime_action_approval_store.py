"""Lightweight JSON store for Runtime action approval records."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


class AIRuntimeActionApprovalStore:
    """Store approval state only; never performs the approved action."""

    APPROVAL_FILE_PATH = Path(__file__).resolve().parents[1] / "data" / "ai_runtime_action_approvals.json"
    MAX_APPROVALS = 500

    def __init__(self, approval_file_path: str | Path | None = None):
        self.approval_file_path = Path(approval_file_path) if approval_file_path else self.APPROVAL_FILE_PATH

    def read_approvals(self) -> list[dict]:
        try:
            if not self.approval_file_path.exists():
                return []
            with self.approval_file_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict):
                data = data.get("approvals") or []
            if not isinstance(data, list):
                return []
            return [item for item in data if isinstance(item, dict)]
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return []

    def write_approvals(self, items: list[dict]) -> list[dict]:
        approvals = [self._normalize_existing(item) for item in list(items or []) if isinstance(item, dict)]
        approvals = approvals[-self.MAX_APPROVALS:]
        try:
            self.approval_file_path.parent.mkdir(parents=True, exist_ok=True)
            with self.approval_file_path.open("w", encoding="utf-8") as file:
                json.dump(approvals, file, ensure_ascii=False, indent=2)
        except OSError:
            return approvals
        return approvals

    def append_pending_action(self, action: dict) -> dict:
        item = self._new_pending_action(action or {})
        approvals = self.read_approvals()
        for existing in approvals:
            if (
                existing.get("status") == "pending"
                and existing.get("action_key") == item.get("action_key")
                and existing.get("source") == item.get("source")
            ):
                return existing
        approvals.append(item)
        self.write_approvals(approvals)
        return item

    def approve_action(self, approval_id: str, approved_by: str = "", note: str = "") -> dict | None:
        return self._transition_action(
            approval_id=approval_id,
            status="approved",
            actor_key="approved_by",
            actor=approved_by,
            note=note,
        )

    def reject_action(self, approval_id: str, rejected_by: str = "", note: str = "") -> dict | None:
        return self._transition_action(
            approval_id=approval_id,
            status="rejected",
            actor_key="rejected_by",
            actor=rejected_by,
            note=note,
        )

    def expire_old_actions(self, max_age_days: int = 7) -> list[dict]:
        approvals = self.read_approvals()
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(0, int(max_age_days or 0)))
        changed = False
        for item in approvals:
            if item.get("status") != "pending":
                continue
            created_at = self._parse_time(item.get("created_at"))
            if created_at and created_at < cutoff:
                item["status"] = "expired"
                item["updated_at"] = datetime.now(timezone.utc).isoformat()
                item["decision_note"] = item.get("decision_note") or "Expired by approval store retention rule."
                changed = True
        if changed:
            self.write_approvals(approvals)
        return approvals

    def _transition_action(self, approval_id: str, status: str, actor_key: str, actor: str, note: str) -> dict | None:
        approvals = self.read_approvals()
        matched = None
        for item in approvals:
            if item.get("approval_id") == approval_id:
                item["status"] = status
                item["updated_at"] = datetime.now(timezone.utc).isoformat()
                item[actor_key] = actor or ""
                item["decision_note"] = note or ""
                matched = item
                break
        if matched:
            self.write_approvals(approvals)
        return matched

    @classmethod
    def _new_pending_action(cls, action: dict) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        action_key = str(action.get("action_key") or action.get("command_key") or action.get("risk_key") or action.get("title") or "ACTION_PENDING")
        return {
            "approval_id": action.get("approval_id") or f"approval_{uuid4().hex}",
            "created_at": action.get("created_at") or now,
            "updated_at": action.get("updated_at") or now,
            "action_key": action_key,
            "title": action.get("title") or action.get("capability") or action.get("policy") or action_key,
            "source": action.get("source") or "Runtime OS",
            "risk_level": action.get("risk_level") or action.get("risk") or action.get("priority") or "medium",
            "status": "pending",
            "human_required": bool(action.get("human_required", True)),
            "reason": action.get("reason") or action.get("summary") or action.get("description") or "",
            "recommended_route": action.get("recommended_route") or action.get("route") or "/ai-dashboard",
            "approved_by": "",
            "rejected_by": "",
            "decision_note": "",
        }

    @classmethod
    def _normalize_existing(cls, item: dict) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        normalized = cls._new_pending_action(item)
        normalized.update({
            "approval_id": item.get("approval_id") or normalized["approval_id"],
            "created_at": item.get("created_at") or now,
            "updated_at": item.get("updated_at") or item.get("created_at") or now,
            "status": item.get("status") or "pending",
            "approved_by": item.get("approved_by") or "",
            "rejected_by": item.get("rejected_by") or "",
            "decision_note": item.get("decision_note") or "",
        })
        return normalized

    @staticmethod
    def _parse_time(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return None
