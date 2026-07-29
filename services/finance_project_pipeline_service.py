"""Phase 6 financing-project pipeline without lead-table changes."""
from __future__ import annotations

from datetime import datetime
from typing import Any


class FinanceProjectPipelineService:
    """Create and advance an independent financing-project state object."""

    STAGES = (
        "线索进入",
        "初步沟通",
        "资料收集",
        "融资诊断",
        "方案确认",
        "银行申请",
        "审批",
        "放款",
        "转介绍",
    )

    LEAD_STATUS_STAGE = {
        "new": "线索进入",
        "assigned": "初步沟通",
        "contacted": "资料收集",
        "converted": "放款",
        "lost": "线索进入",
    }

    @classmethod
    def create(
        cls,
        customer: dict[str, Any] | None,
        diagnosis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = customer or {}
        requested_stage = str(
            data.get("finance_stage")
            or data.get("project_stage")
            or cls.LEAD_STATUS_STAGE.get(str(data.get("status") or ""), "线索进入")
        )
        current_stage = requested_stage if requested_stage in cls.STAGES else "线索进入"
        index = cls.STAGES.index(current_stage)
        return {
            "project_id": str(data.get("project_id") or f"FIN-{data.get('id') or 'NEW'}"),
            "customer_id": data.get("id") or data.get("customer_id") or 0,
            "customer_name": str(data.get("name") or data.get("customer_name") or "未命名客户"),
            "level": str((diagnosis or {}).get("level") or data.get("level") or "D"),
            "current_stage": current_stage,
            "stage_index": index,
            "next_stage": cls.STAGES[index + 1] if index + 1 < len(cls.STAGES) else "",
            "progress_percent": round((index + 1) / len(cls.STAGES) * 100, 1),
            "history": list(data.get("finance_project_history") or []),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

    @classmethod
    def advance(
        cls,
        project: dict[str, Any] | None,
        target_stage: str | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        state = dict(project or {})
        current = str(state.get("current_stage") or "线索进入")
        if current not in cls.STAGES:
            return {"ok": False, "error": "无效的当前融资阶段", **state}
        current_index = cls.STAGES.index(current)
        expected = cls.STAGES[current_index + 1] if current_index + 1 < len(cls.STAGES) else ""
        target = str(target_stage or expected)
        if not expected:
            return {"ok": False, "error": "融资项目已处于最终阶段", **state}
        if target != expected:
            return {
                "ok": False,
                "error": f"项目只能从“{current}”推进到“{expected}”",
                **state,
            }
        history = list(state.get("history") or [])
        changed_at = datetime.now().isoformat(timespec="seconds")
        history.append({"from": current, "to": target, "note": str(note or ""), "at": changed_at})
        target_index = cls.STAGES.index(target)
        state.update({
            "ok": True,
            "current_stage": target,
            "stage_index": target_index,
            "next_stage": (
                cls.STAGES[target_index + 1] if target_index + 1 < len(cls.STAGES) else ""
            ),
            "progress_percent": round((target_index + 1) / len(cls.STAGES) * 100, 1),
            "history": history,
            "updated_at": changed_at,
        })
        return state
