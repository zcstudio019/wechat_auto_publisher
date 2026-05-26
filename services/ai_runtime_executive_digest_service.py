from __future__ import annotations


class AIRuntimeExecutiveDigestService:
    """Build a compressed, read-only executive digest for Runtime OS."""

    @classmethod
    def build_executive_digest(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        mission = dashboard.get("ai_runtime_mission_control_center") or dashboard.get("ai_runtime_task_command_center") or {}
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        forecast = dashboard.get("ai_runtime_forecast_center") or {}
        alert = dashboard.get("ai_runtime_alert_center") or {}
        incident = dashboard.get("ai_runtime_incident_center") or {}
        export_ops = dashboard.get("ai_dashboard_export_operations_center") or {}

        digest_status = cls._resolve_status(mission, ops, forecast, alert, incident, export_ops)
        digest_level = {"stable": "L1", "attention": "L2", "warning": "L3", "critical": "L4"}[digest_status]
        blocked_items = cls._build_blocked_items(mission, export_ops, incident)
        must_watch_items = cls._build_must_watch_items(mission, ops, forecast, alert, export_ops)
        profile = cls._profile_for_status(digest_status, mission, ops, forecast, alert, incident, export_ops)

        one_line_summary = cls._trim_one_line(profile["one_line_summary"])
        return {
            "digest_status": digest_status,
            "digest_level": digest_level,
            "one_line_summary": one_line_summary,
            "core_problem": profile["core_problem"],
            "highest_priority": profile["highest_priority"],
            "biggest_risk": profile["biggest_risk"],
            "best_path": profile["best_path"],
            "recommended_workspace": profile["recommended_workspace"],
            "recommended_page": profile["recommended_page"],
            "recommended_module": profile["recommended_module"],
            "recommended_action": profile["recommended_action"],
            "must_watch_items": must_watch_items[:5],
            "blocked_items": blocked_items[:5],
            "summary": f"{digest_level} / {digest_status}: {one_line_summary}",
            "recommended_actions": cls._recommended_actions(digest_status, profile),
        }

    @classmethod
    def _resolve_status(cls, mission: dict, ops: dict, forecast: dict, alert: dict, incident: dict, export_ops: dict) -> str:
        if cls._status_in(incident.get("incident_status"), {"critical"}) or cls._status_in(mission.get("mission_status"), {"critical"}):
            return "critical"
        if cls._status_in(ops.get("ops_status"), {"critical", "failed"}) or cls._forecast_high_risk(forecast):
            return "critical"
        if cls._status_in(mission.get("mission_status"), {"overloaded"}) or cls._status_in(alert.get("alert_status"), {"critical"}):
            return "warning"
        if cls._status_in(ops.get("ops_status"), {"warning", "attention"}) or cls._status_in(export_ops.get("operations_status"), {"warning", "failed"}):
            return "warning"
        if cls._status_in(forecast.get("forecast_status"), {"warning", "attention", "high"}):
            return "warning"
        if cls._status_in(mission.get("mission_status"), {"active"}) or (mission.get("today_missions") or []):
            return "attention"
        return "stable"

    @staticmethod
    def _status_in(value, statuses: set[str]) -> bool:
        return str(value or "").strip().lower() in statuses

    @staticmethod
    def _forecast_high_risk(forecast: dict) -> bool:
        if str((forecast or {}).get("forecast_status") or "").lower() in {"critical", "high_risk", "high"}:
            return True
        risks = (forecast or {}).get("potential_risks") or (forecast or {}).get("key_risk_alerts") or []
        return any(str(item).lower().find("critical") >= 0 for item in risks)

    @classmethod
    def _profile_for_status(cls, status: str, mission: dict, ops: dict, forecast: dict, alert: dict, incident: dict, export_ops: dict) -> dict:
        if status == "critical":
            return {
                "one_line_summary": "Runtime 处于高风险运行态，建议先进入 Mission Control。",
                "core_problem": cls._first_problem(incident, ["critical_incidents"], "Runtime 关键事件或恢复阻塞"),
                "highest_priority": "先处理 Runtime Incident 与阻塞任务",
                "biggest_risk": "关键风险继续扩散，影响信任与治理边界",
                "best_path": "Admin Home → Mission Control → Ops Health → Forecast → Predictive Action",
                "recommended_workspace": "ops_workspace",
                "recommended_page": "/ai-dashboard/mission-control",
                "recommended_module": "AI Runtime Mission Control Center",
                "recommended_action": "优先检查关键事件、阻塞项和 Ops Health",
            }
        if status == "warning":
            if cls._status_in(ops.get("ops_status"), {"warning", "attention", "critical"}):
                core_problem = "Ops Health 降级"
                page = "/ai-dashboard/ops-health"
                module = "AI Dashboard Ops Health Center"
                workspace = "ops_workspace"
                action = "进入 Ops Health 检查运维风险"
            elif cls._status_in(export_ops.get("operations_status"), {"warning", "failed"}):
                core_problem = "Export 调度或导出结果存在异常"
                page = "/ai-dashboard/export-operations"
                module = "AI Dashboard Export Operations Center"
                workspace = "export_workspace"
                action = "进入 Export Operations 检查失败项"
            else:
                core_problem = "Forecast 风险升高"
                page = "/ai-dashboard/mission-control"
                module = "AI Runtime Forecast Center"
                workspace = "runtime_workspace"
                action = "优先检查 Forecast 与 Predictive Action"
            return {
                "one_line_summary": "Runtime 风险升高，建议优先检查 Mission Control。",
                "core_problem": core_problem,
                "highest_priority": "先复核 P0/P1 任务和风险预测",
                "biggest_risk": "预测风险或运维风险转为阻塞",
                "best_path": "Admin Home → Mission Control → Forecast → Predictive Action → Continuous Improvement",
                "recommended_workspace": workspace,
                "recommended_page": page,
                "recommended_module": module,
                "recommended_action": action,
            }
        if status == "attention":
            return {
                "one_line_summary": "Runtime 有任务需关注，建议进入工作台快速分流。",
                "core_problem": "今日任务较多但未达到高风险",
                "highest_priority": "按 Mission Control 优先级复核任务",
                "biggest_risk": "低优先级任务累积为阻塞",
                "best_path": "Admin Home → Workspace → Mission Control → Action Launcher",
                "recommended_workspace": "manager_workspace",
                "recommended_page": "/ai-dashboard/workspace",
                "recommended_module": "AI Dashboard Workspace Center",
                "recommended_action": "进入 Workspace 分流今日任务",
            }
        return {
            "one_line_summary": "Runtime 总体稳定，建议保持例行观察。",
            "core_problem": "暂无核心阻塞问题",
            "highest_priority": "保持 Runtime 观察和例行复盘",
            "biggest_risk": "低频风险未及时进入观察清单",
            "best_path": "Admin Home → Executive Dashboard → Navigation → Documentation",
            "recommended_workspace": "manager_workspace",
            "recommended_page": "/ai-dashboard/home",
            "recommended_module": "AI Runtime Executive Dashboard Center",
            "recommended_action": "查看高管仪表盘并保持观察",
        }

    @staticmethod
    def _first_problem(source: dict, keys: list[str], fallback: str) -> str:
        for key in keys:
            items = source.get(key) or []
            if items:
                first = items[0]
                if isinstance(first, dict):
                    return first.get("title") or first.get("summary") or fallback
                return str(first)
        return fallback

    @classmethod
    def _build_must_watch_items(cls, mission: dict, ops: dict, forecast: dict, alert: dict, export_ops: dict) -> list[dict]:
        items = []
        for raw in (mission.get("critical_missions") or mission.get("priority_tasks") or [])[:3]:
            items.append(cls._watch_item(raw, "Mission Control"))
        for raw in (forecast.get("potential_risks") or forecast.get("key_risk_alerts") or [])[:2]:
            items.append(cls._watch_item(raw, "Forecast"))
        if ops.get("ops_status") and str(ops.get("ops_status")).lower() not in {"healthy", "normal"}:
            items.append({"title": "Ops Health", "source": "Ops Health", "summary": ops.get("summary") or "运维健康需关注"})
        if export_ops.get("operations_status") and str(export_ops.get("operations_status")).lower() not in {"normal", "success"}:
            items.append({"title": "Export Operations", "source": "Export Operations", "summary": export_ops.get("summary") or "导出运营需关注"})
        for raw in (alert.get("warning_alerts") or alert.get("critical_alerts") or [])[:2]:
            items.append(cls._watch_item(raw, "Runtime Alert"))
        if not items:
            items.append({"title": "Runtime 例行观察", "source": "Executive Digest", "summary": "当前无高风险观察项"})
        return items[:5]

    @classmethod
    def _build_blocked_items(cls, mission: dict, export_ops: dict, incident: dict) -> list[dict]:
        items = []
        for raw in (mission.get("blocked_missions") or mission.get("blocked_tasks") or [])[:4]:
            items.append(cls._watch_item(raw, "Mission Control"))
        for raw in (export_ops.get("failed_items") or [])[:2]:
            items.append(cls._watch_item(raw, "Export Operations"))
        for raw in (incident.get("critical_incidents") or [])[:2]:
            items.append(cls._watch_item(raw, "Runtime Incident"))
        return items[:5]

    @staticmethod
    def _watch_item(raw, source: str) -> dict:
        if isinstance(raw, dict):
            return {
                "title": raw.get("title") or raw.get("task") or raw.get("name") or source,
                "source": raw.get("source_module") or source,
                "summary": raw.get("summary") or raw.get("reason") or raw.get("message") or raw.get("description") or "",
            }
        return {"title": str(raw), "source": source, "summary": str(raw)}

    @staticmethod
    def _trim_one_line(text: str) -> str:
        text = " ".join(str(text or "").split())
        return text if len(text) <= 80 else text[:77] + "..."

    @staticmethod
    def _recommended_actions(status: str, profile: dict) -> list[str]:
        if status == "critical":
            return ["先看 Mission Control", "再看 Ops Health", "暂停推进高风险自动化建议", "人工复核阻塞项"]
        if status == "warning":
            return [profile["recommended_action"], "复核 Forecast 与 Predictive Action", "检查导出与运维异常"]
        if status == "attention":
            return ["进入 Workspace 分流任务", "按优先级处理 Mission Control", "保持 Runtime 观察"]
        return ["查看 Executive Dashboard", "保持例行观察", "每周复盘 Runtime 报告"]

    @classmethod
    def build_executive_digest_text(cls, center: dict | None = None) -> str:
        center = center or cls.build_executive_digest()
        return "\n".join([
            "【AI Runtime 高层摘要中心】",
            f"状态：{center.get('digest_status')} / {center.get('digest_level')}",
            f"一句话：{center.get('one_line_summary')}",
            f"核心问题：{center.get('core_problem')}",
            f"最高优先级：{center.get('highest_priority')}",
            f"最大风险：{center.get('biggest_risk')}",
            f"最佳路径：{center.get('best_path')}",
            f"建议入口：{center.get('recommended_page')}",
            f"建议动作：{center.get('recommended_action')}",
        ])

    @classmethod
    def build_executive_digest_markdown(cls, center: dict | None = None) -> str:
        center = center or cls.build_executive_digest()
        return "\n".join([
            "# AI Runtime 高层摘要中心",
            "",
            f"- 状态：{center.get('digest_status')} / {center.get('digest_level')}",
            f"- 一句话：{center.get('one_line_summary')}",
            f"- 核心问题：{center.get('core_problem')}",
            f"- 最高优先级：{center.get('highest_priority')}",
            f"- 最大风险：{center.get('biggest_risk')}",
            f"- 最佳路径：{center.get('best_path')}",
            f"- 建议工作台：{center.get('recommended_workspace')}",
            f"- 建议页面：{center.get('recommended_page')}",
            f"- 建议动作：{center.get('recommended_action')}",
        ])

    @classmethod
    def build_executive_digest_rows(cls, center: dict | None = None) -> list[dict]:
        center = center or cls.build_executive_digest()
        return [
            {"项目": "状态", "状态": center.get("digest_status"), "摘要": center.get("digest_level"), "建议": center.get("recommended_action")},
            {"项目": "一句话状态", "状态": center.get("digest_status"), "摘要": center.get("one_line_summary"), "建议": center.get("recommended_page")},
            {"项目": "核心问题", "状态": center.get("digest_status"), "摘要": center.get("core_problem"), "建议": center.get("highest_priority")},
            {"项目": "最大风险", "状态": center.get("digest_status"), "摘要": center.get("biggest_risk"), "建议": center.get("best_path")},
            {"项目": "推荐入口", "状态": center.get("recommended_workspace"), "摘要": center.get("recommended_module"), "建议": center.get("recommended_page")},
        ]
