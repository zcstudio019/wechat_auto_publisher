from __future__ import annotations

from datetime import datetime

from services.ai_dashboard_release_runbook_service import AIDashboardReleaseRunbookService


class AIDashboardLaunchRunbookService:
    """Compatibility layer for the AI Dashboard launch runbook center."""

    @classmethod
    def build_launch_runbook_center(cls) -> dict:
        release_center = AIDashboardReleaseRunbookService.build_release_runbook_center()
        status = cls._normalize_status(release_center.get("runbook_status"))
        return {
            "runbook_status": status,
            "runbook_version": cls._build_runbook_version(),
            "summary": release_center.get("summary") or "",
            "launch_scope": cls._build_launch_scope(release_center),
            "pre_launch_steps": release_center.get("pre_release_steps", []),
            "launch_steps": release_center.get("release_steps", []),
            "post_launch_steps": release_center.get("post_release_validation", []),
            "rollback_steps": release_center.get("rollback_steps", []),
            "verification_steps": release_center.get("verification_commands", []),
            "manual_confirmation_items": cls._build_manual_confirmation_items(release_center),
            "owner_checklist": release_center.get("responsibility_matrix", []),
            "risk_checklist": release_center.get("risk_playbooks", []),
            "emergency_contacts": cls._build_emergency_contacts(),
            "recommended_actions": release_center.get("recommended_actions", []),
            "release_runbook_source": release_center,
        }

    @staticmethod
    def _normalize_status(status: str | None) -> str:
        value = (status or "").strip().lower()
        if value == "needs_review":
            return "draft"
        if value in {
            "ready",
            "draft",
            "healthy",
            "normal",
            "active",
            "attention",
            "warning",
            "critical",
            "blocked",
            "not_ready",
            "missing",
            "idle",
        }:
            return value
        return "unknown"

    @staticmethod
    def _build_runbook_version() -> str:
        return f"ai-dashboard-runbook-{datetime.now().strftime('%Y%m%d')}"

    @staticmethod
    def _build_launch_scope(center: dict) -> dict:
        return {
            "title": "AI Dashboard 上线执行范围",
            "status": center.get("runbook_status") or "unknown",
            "summary": center.get("summary") or "当前暂无 Dashboard 上线执行手册数据。",
            "included_areas": [
                "AI Dashboard 主页面",
                "上线准备度中心",
                "上线包中心",
                "生产级加固中心",
                "运维健康中心",
                "Runtime 安全验证",
            ],
        }

    @staticmethod
    def _build_manual_confirmation_items(center: dict) -> list[dict]:
        items = []
        for item in center.get("completion_checklist", [])[:4]:
            items.append({
                "step": item.get("item") or "人工确认项",
                "owner": "人工确认负责人",
                "status": item.get("status") or "manual_required",
                "notes": item.get("summary") or "",
            })
        if not items:
            items.append({
                "step": "确认上线窗口与回滚窗口",
                "owner": "上线负责人",
                "status": "manual_required",
                "notes": "上线前必须人工确认，不自动执行部署。",
            })
        return items

    @staticmethod
    def _build_emergency_contacts() -> list[dict]:
        return [
            {"role": "开发负责人", "contact": "按团队值班表确认", "status": "manual_required", "notes": "负责代码、测试和 Dashboard 页面异常定位。"},
            {"role": "运维负责人", "contact": "按团队值班表确认", "status": "manual_required", "notes": "负责服务、Nginx、systemd、日志和回滚窗口。"},
            {"role": "业务验收负责人", "contact": "按团队值班表确认", "status": "manual_required", "notes": "负责上线后页面和业务入口验收。"},
        ]

    @classmethod
    def build_launch_runbook_text(cls, center: dict | None = None) -> str:
        center = center or cls.build_launch_runbook_center()
        lines = [
            "【AI Dashboard 上线执行手册中心】",
            f"当前执行手册状态：{center.get('runbook_status') or 'unknown'}",
            f"执行手册版本：{center.get('runbook_version') or ''}",
            center.get("summary") or "",
            "",
            "上线范围：",
        ]
        scope = center.get("launch_scope") or {}
        lines.append(f"- {scope.get('title') or '上线范围'}：{scope.get('summary') or ''}")
        for item in scope.get("included_areas", []):
            lines.append(f"  - {item}")
        for title, key in [
            ("上线前检查步骤", "pre_launch_steps"),
            ("上线执行步骤", "launch_steps"),
            ("上线后验证步骤", "post_launch_steps"),
            ("验证步骤", "verification_steps"),
            ("回滚步骤", "rollback_steps"),
            ("人工确认事项", "manual_confirmation_items"),
            ("负责人清单", "owner_checklist"),
            ("风险检查清单", "risk_checklist"),
            ("应急联系人", "emergency_contacts"),
        ]:
            lines.append("")
            lines.append(f"{title}：")
            for item in center.get(key, []):
                lines.append(f"- {item.get('step') or item.get('role') or item.get('risk') or item.get('command') or item.get('item') or '事项'}：{item.get('owner') or item.get('responsibility') or item.get('response') or item.get('purpose') or item.get('notes') or item.get('summary') or ''}")
        lines.append("")
        lines.append("推荐动作：")
        for item in center.get("recommended_actions", []):
            lines.append(f"- {item}")
        return "\n".join(lines)

    @classmethod
    def build_launch_runbook_rows(cls, center: dict | None = None) -> list[dict]:
        center = center or cls.build_launch_runbook_center()
        rows = []

        def add(stage: str, item: dict, title_key: str = "step") -> None:
            status = item.get("status") or "pending"
            rows.append({
                "阶段": stage,
                "步骤": item.get(title_key) or item.get("role") or item.get("risk") or item.get("command") or item.get("item") or "",
                "负责人": item.get("owner") or item.get("role") or "",
                "是否需要人工确认": "是" if status in {"manual", "manual_required", "blocking"} else "否",
                "风险等级": item.get("risk_level") or ("高" if status == "blocking" else "中" if status in {"warning", "manual_required"} else "低"),
                "状态": status,
                "说明": item.get("verification") or item.get("notes") or item.get("summary") or item.get("response") or item.get("purpose") or item.get("responsibility") or "",
                "建议动作": item.get("recommended_action") or item.get("handling") or "",
            })

        for stage, key in [
            ("pre_launch", "pre_launch_steps"),
            ("launch", "launch_steps"),
            ("post_launch", "post_launch_steps"),
            ("verification", "verification_steps"),
            ("rollback", "rollback_steps"),
            ("pre_launch", "manual_confirmation_items"),
            ("pre_launch", "owner_checklist"),
            ("emergency", "risk_checklist"),
            ("emergency", "emergency_contacts"),
        ]:
            for item in center.get(key, []):
                add(stage, item)
        for item in center.get("recommended_actions", []):
            add("post_launch", {"step": item, "status": "manual_required", "notes": item})
        return rows
