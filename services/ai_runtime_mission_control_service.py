"""Read-only AI Runtime mission control center."""

from __future__ import annotations

from services.ai_dashboard_workspace_service import AIDashboardWorkspaceService


class AIRuntimeMissionControlService:
    """Build prioritized Runtime missions from existing Dashboard centers."""

    @classmethod
    def build_mission_control_center(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        workspace = dashboard.get("ai_dashboard_workspace_center") or AIDashboardWorkspaceService.build_workspace_center(dashboard)

        today_missions = cls._build_today_missions(dashboard, workspace)
        critical_missions = cls._build_critical_missions(today_missions, dashboard)
        blocked_missions = cls._build_blocked_missions(today_missions, dashboard)
        observation_missions = cls._build_observation_missions(today_missions, dashboard)
        mission_status = cls._resolve_mission_status(dashboard, today_missions, critical_missions, blocked_missions)
        task_command_status = cls._normalize_task_status(mission_status)
        manual_confirm_tasks = cls._build_manual_confirm_tasks(dashboard, today_missions)
        runtime_dependencies = cls._build_runtime_dependencies(dashboard)
        execution_order = cls._build_execution_order(critical_missions, blocked_missions, today_missions, observation_missions)

        return {
            "task_command_status": task_command_status,
            "mission_status": mission_status,
            "summary": cls._build_summary(mission_status, today_missions, critical_missions, blocked_missions),
            "today_command": {
                "title": "今日 Runtime 任务指挥",
                "status": task_command_status,
                "target": "按优先级只读复核 Runtime 任务，不自动执行。",
                "summary": cls._build_summary(mission_status, today_missions, critical_missions, blocked_missions),
            },
            "task_groups": cls._build_task_groups(today_missions, critical_missions, blocked_missions, observation_missions),
            "priority_tasks": critical_missions or [item for item in today_missions if item.get("priority") in {"P0", "P1"}][:8],
            "manual_confirm_tasks": manual_confirm_tasks,
            "blocked_tasks": blocked_missions,
            "runtime_dependencies": runtime_dependencies,
            "execution_order": execution_order,
            "risk_tasks": critical_missions + blocked_missions,
            "today_missions": today_missions,
            "critical_missions": critical_missions,
            "blocked_missions": blocked_missions,
            "observation_missions": observation_missions,
            "recommended_execution_order": execution_order,
            "recommended_workspaces": cls._build_recommended_workspaces(workspace, dashboard, critical_missions, blocked_missions),
            "recommended_exports": cls._build_recommended_exports(),
            "recommended_governance_actions": cls._build_governance_actions(dashboard, critical_missions, blocked_missions),
            "recommended_paths": cls._build_recommended_paths(),
            "recommended_actions": cls._build_recommended_actions(mission_status),
        }

    @classmethod
    def build_task_command_center(cls, dashboard: dict | None = None) -> dict:
        return cls.build_mission_control_center(dashboard)

    @classmethod
    def _build_today_missions(cls, dashboard: dict, workspace: dict) -> list[dict]:
        missions = []
        forecast = dashboard.get("ai_runtime_forecast_center") or {}
        predictive = dashboard.get("ai_runtime_predictive_action_center") or {}
        improvement = dashboard.get("ai_runtime_continuous_improvement_center") or {}
        maintenance = dashboard.get("ai_dashboard_ops_maintenance_center") or dashboard.get("ai_dashboard_ops_maintenance_plan_center") or {}
        export_ops = dashboard.get("ai_dashboard_export_operations_center") or {}
        alert = dashboard.get("ai_runtime_alert_center") or {}
        governance = dashboard.get("ai_runtime_policy_gate_center") or dashboard.get("ai_governance_center") or {}

        for item in cls._items_from(forecast, ["key_risk_alerts", "potential_risks", "recommended_actions"]):
            missions.append(cls._mission(item, "P1", "Forecast", "runtime_workspace", "/ai-dashboard"))
        for item in cls._items_from(predictive, ["priority_actions", "potential_blockers", "predictive_tasks", "preventive_actions"]):
            priority = "P0" if cls._looks_blocked(item) else "P1"
            missions.append(cls._mission(item, priority, "Predictive Action", "runtime_workspace", "/ai-dashboard"))
        for item in cls._items_from(improvement, ["improvement_priorities", "recommended_actions", "potential_risks_and_blockers", "continuous_improvement_items"]):
            missions.append(cls._mission(item, "P2", "Continuous Improvement", "runtime_workspace", "/ai-dashboard"))
        for item in cls._items_from(maintenance, ["today_tasks", "recommended_actions", "risk_handling_sequence"]):
            missions.append(cls._mission(item, "P1", "Ops Maintenance", "ops_workspace", "/ai-dashboard/ops-maintenance"))
        for item in cls._items_from(export_ops, ["failed_items", "warnings", "recommended_actions"]):
            priority = "P0" if cls._looks_failed(item) else "P2"
            missions.append(cls._mission(item, priority, "Export Operations", "export_workspace", "/ai-dashboard/export-operations"))
        for item in cls._items_from(alert, ["critical_alerts", "warning_alerts", "active_alerts", "recommended_actions"]):
            priority = "P0" if cls._looks_critical(item) else "P1"
            missions.append(cls._mission(item, priority, "Runtime Alert", "ops_workspace", "/ai-dashboard"))
        for item in cls._items_from(governance, ["blocked_actions", "forbidden_actions", "policy_conflicts", "recommended_actions"]):
            missions.append(cls._mission(item, "P1", "Governance", "governance_workspace", "/ai-dashboard"))

        if not missions:
            recommended = (workspace or {}).get("recommended_workspace") or {}
            missions.append({
                "title": "复核 AI Dashboard 今日状态",
                "priority": "P2",
                "source_module": "Workspace",
                "summary": recommended.get("reason") or recommended.get("summary") or "当前无高风险任务，保持只读巡检。",
                "recommended_workspace": recommended.get("title") or "管理者工作台",
                "recommended_route": "/ai-dashboard/workspace",
            })
        return missions[:24]

    @staticmethod
    def _items_from(source: dict, keys: list[str]) -> list:
        items = []
        for key in keys:
            value = (source or {}).get(key)
            if isinstance(value, list):
                items.extend(value)
            elif value:
                items.append(value)
        return items

    @classmethod
    def _mission(cls, raw, priority: str, source_module: str, workspace: str, route: str) -> dict:
        if isinstance(raw, dict):
            title = raw.get("title") or raw.get("task") or raw.get("name") or raw.get("risk") or raw.get("action") or source_module
            summary = raw.get("summary") or raw.get("reason") or raw.get("message") or raw.get("description") or raw.get("suggestion") or ""
            raw_priority = raw.get("priority") or raw.get("level") or raw.get("status")
            if raw_priority:
                priority = cls._normalize_priority(str(raw_priority), priority)
        else:
            title = str(raw)
            summary = str(raw)
        return {
            "title": title,
            "priority": priority,
            "source_module": source_module,
            "summary": summary or f"来自 {source_module} 的只读任务建议。",
            "recommended_workspace": workspace,
            "recommended_route": route,
        }

    @staticmethod
    def _normalize_priority(value: str, fallback: str) -> str:
        value = (value or "").lower()
        if value in {"critical", "p0", "danger", "high"}:
            return "P0" if value in {"critical", "p0", "danger"} else "P1"
        if value in {"warning", "medium", "p1"}:
            return "P1"
        if value in {"low", "info", "p2", "normal"}:
            return "P2"
        return fallback

    @classmethod
    def _build_critical_missions(cls, missions: list[dict], dashboard: dict) -> list[dict]:
        critical = [
            item for item in missions
            if item.get("priority") == "P0" or cls._text_has_any(item, {"critical", "重大", "严重", "高风险", "阻塞"})
        ]
        incident = dashboard.get("ai_runtime_incident_center") or {}
        for item in incident.get("critical_incidents") or []:
            critical.append(cls._mission(item, "P0", "Runtime Incident", "ops_workspace", "/ai-dashboard"))
        return critical[:12]

    @classmethod
    def _build_blocked_missions(cls, missions: list[dict], dashboard: dict) -> list[dict]:
        blocked = [
            item for item in missions
            if cls._text_has_any(item, {"blocked", "blocker", "阻塞", "失败", "failed", "degraded", "退化", "conflict", "冲突"})
        ]
        predictive = dashboard.get("ai_runtime_predictive_action_center") or {}
        for item in predictive.get("potential_blockers") or []:
            blocked.append(cls._mission(item, "P0", "Predictive Action", "runtime_workspace", "/ai-dashboard"))
        return blocked[:12]

    @classmethod
    def _build_observation_missions(cls, missions: list[dict], dashboard: dict) -> list[dict]:
        observation = [
            item for item in missions
            if item.get("priority") == "P2" or cls._text_has_any(item, {"观察", "watch", "trend", "趋势", "early warning", "预警"})
        ]
        forecast = dashboard.get("ai_runtime_forecast_center") or {}
        for item in forecast.get("future_trends") or []:
            observation.append(cls._mission(item, "P2", "Forecast", "runtime_workspace", "/ai-dashboard"))
        return observation[:12]

    @classmethod
    def _resolve_mission_status(cls, dashboard: dict, today: list[dict], critical: list[dict], blocked: list[dict]) -> str:
        incident = dashboard.get("ai_runtime_incident_center") or {}
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        forecast = dashboard.get("ai_runtime_forecast_center") or {}
        if (
            cls._status_in(incident.get("incident_status"), {"critical"})
            or cls._status_in(ops.get("ops_status") or ops.get("health_status"), {"critical", "failed"})
            or cls._forecast_high_risk(forecast)
        ):
            return "critical"
        if len(blocked) >= 5 or len(critical) >= 4:
            return "overloaded"
        if len(today) >= 5:
            return "active"
        return "calm"

    @staticmethod
    def _normalize_task_status(status: str) -> str:
        return {
            "calm": "normal",
            "active": "active",
            "overloaded": "warning",
            "critical": "critical",
        }.get(status or "", status or "unknown")

    @staticmethod
    def _task_item(item: dict, item_type: str = "command") -> dict:
        return {
            "type": item_type,
            "title": item.get("title") or "",
            "status": "blocked" if item_type == "blocked" else ("warning" if item_type in {"risk", "manual_confirm"} else "normal"),
            "priority": item.get("priority") or "medium",
            "target": item.get("source_module") or item.get("recommended_workspace") or "",
            "reason": item.get("summary") or "",
            "recommended_action": "人工复核后再处理，不自动执行。",
            "route": item.get("recommended_route") or "/ai-dashboard",
        }

    @classmethod
    def _build_task_groups(cls, today: list[dict], critical: list[dict], blocked: list[dict], observation: list[dict]) -> list[dict]:
        return [
            {"title": "优先任务", "status": "warning" if critical else "normal", "items": [cls._task_item(item, "priority") for item in critical]},
            {"title": "待人工确认任务", "status": "attention", "items": [cls._task_item(item, "manual_confirm") for item in today if item.get("priority") in {"P0", "P1"}][:8]},
            {"title": "阻塞任务", "status": "blocked" if blocked else "normal", "items": [cls._task_item(item, "blocked") for item in blocked]},
            {"title": "观察任务", "status": "normal", "items": [cls._task_item(item, "command") for item in observation]},
        ]

    @classmethod
    def _build_manual_confirm_tasks(cls, dashboard: dict, today: list[dict]) -> list[dict]:
        tasks = [cls._task_item(item, "manual_confirm") for item in today if item.get("priority") in {"P0", "P1"}]
        approval = dashboard.get("ai_approval_pipeline_center") or {}
        for item in approval.get("pending") or []:
            if isinstance(item, dict):
                tasks.append({
                    "type": "manual_confirm",
                    "title": item.get("title") or item.get("action") or "待批准动作",
                    "status": "attention",
                    "priority": item.get("priority") or "high",
                    "target": item.get("target") or "approval_pipeline",
                    "reason": item.get("summary") or item.get("reason") or "批准流中存在待确认动作。",
                    "recommended_action": "保持人工批准，不自动确认。",
                    "route": "/ai-dashboard",
                })
        return tasks[:10]

    @staticmethod
    def _build_runtime_dependencies(dashboard: dict) -> list[dict]:
        dependencies = [
            ("工作台", "ai_dashboard_workspace_center"),
            ("策略闸门", "ai_runtime_policy_gate_center"),
            ("控制策略", "ai_runtime_control_policy_center"),
            ("AutoOps 控制塔", "ai_autoops_control_tower"),
            ("动作复核", "ai_autoops_action_review_center"),
            ("执行沙箱", "ai_execution_sandbox_center"),
            ("批准流", "ai_approval_pipeline_center"),
            ("批准审计", "ai_approval_audit_center"),
        ]
        return [
            {
                "type": "dependency",
                "title": title,
                "status": "normal" if dashboard.get(key) else "missing",
                "priority": "high" if not dashboard.get(key) else "low",
                "target": key,
                "reason": "已挂载" if dashboard.get(key) else "依赖数据未挂载",
                "recommended_action": "缺失时只读检查上游挂载。",
            }
            for title, key in dependencies
        ]

    @staticmethod
    def _forecast_high_risk(forecast: dict) -> bool:
        status = (forecast or {}).get("forecast_status") or (forecast or {}).get("status") or ""
        return str(status).lower() in {"critical", "high_risk", "risk"} or len((forecast or {}).get("key_risk_alerts") or []) >= 3

    @staticmethod
    def _status_in(status: str | None, values: set[str]) -> bool:
        return (status or "").strip().lower() in values

    @staticmethod
    def _text_has_any(item: dict, needles: set[str]) -> bool:
        text = " ".join(str(item.get(key) or "") for key in ("title", "summary", "priority", "source_module")).lower()
        return any(needle.lower() in text for needle in needles)

    @staticmethod
    def _looks_blocked(item) -> bool:
        return AIRuntimeMissionControlService._text_has_any(AIRuntimeMissionControlService._mission(item, "P1", "", "", ""), {"blocked", "阻塞", "blocker"})

    @staticmethod
    def _looks_failed(item) -> bool:
        return AIRuntimeMissionControlService._text_has_any(AIRuntimeMissionControlService._mission(item, "P1", "", "", ""), {"failed", "失败", "error"})

    @staticmethod
    def _looks_critical(item) -> bool:
        return AIRuntimeMissionControlService._text_has_any(AIRuntimeMissionControlService._mission(item, "P1", "", "", ""), {"critical", "严重", "重大"})

    @staticmethod
    def _build_execution_order(critical: list[dict], blocked: list[dict], today: list[dict], observation: list[dict]) -> list[dict]:
        ordered = []
        for label, items in [
            ("先处理 Critical / P0 任务", critical),
            ("再处理阻塞与失败任务", blocked),
            ("随后处理今日 P1 任务", [item for item in today if item.get("priority") == "P1"]),
            ("最后处理观察任务", observation),
        ]:
            ordered.append({
                "step": len(ordered) + 1,
                "title": label,
                "missions": [item.get("title") for item in items[:5]],
                "summary": f"{label}，共 {len(items)} 项。",
            })
        return ordered

    @staticmethod
    def _build_recommended_workspaces(workspace: dict, dashboard: dict, critical: list[dict], blocked: list[dict]) -> list[dict]:
        recommended = []
        current = (workspace or {}).get("recommended_workspace") or {}
        if current:
            recommended.append({"workspace": current.get("title") or "recommended_workspace", "reason": current.get("reason") or current.get("summary") or "当前推荐工作台。"})
        if critical or blocked:
            recommended.extend([
                {"workspace": "ops_workspace", "reason": "存在关键或阻塞任务。"},
                {"workspace": "runtime_workspace", "reason": "需要复核 Runtime 预测与行动建议。"},
                {"workspace": "governance_workspace", "reason": "需要复核边界、授权和治理动作。"},
            ])
        else:
            recommended.append({"workspace": "manager_workspace", "reason": "系统稳定时优先保持管理者总览。"})
        return recommended[:5]

    @staticmethod
    def _build_recommended_exports() -> list[dict]:
        return [
            {"title": "Weekly Review Export", "route": "/ai-dashboard/runtime-weekly-review-export?format=txt", "summary": "导出周复盘任务背景。"},
            {"title": "Documentation Export", "route": "/ai-dashboard/documentation-export?format=md", "summary": "导出文档中心。"},
            {"title": "Navigation Export", "route": "/ai-dashboard/navigation-index-export?format=csv", "summary": "导出导航索引。"},
            {"title": "Runtime Timeline Export", "route": "/ai-dashboard/runtime-timeline-export?format=txt", "summary": "导出 Runtime 时间线。"},
            {"title": "Runtime Forecast Export", "route": "/ai-dashboard/runtime-forecast-export?format=txt", "summary": "导出 Runtime 预测。"},
        ]

    @staticmethod
    def _build_governance_actions(dashboard: dict, critical: list[dict], blocked: list[dict]) -> list[str]:
        actions = [
            "增强 Runtime 观察",
            "提高人工复核",
            "保持 Boundary 约束",
            "暂缓扩大自动化",
        ]
        if critical:
            actions.insert(0, "优先强化 Boundary")
        if blocked:
            actions.insert(0, "收紧 Delegation")
        return actions[:8]

    @staticmethod
    def _build_recommended_paths() -> list[dict]:
        return [
            {"name": "运维处理路径", "steps": ["Ops Health", "Mission", "Maintenance", "Export Operations"], "summary": "先定位运维健康，再处理任务、维护和导出。"},
            {"name": "Runtime 路径", "steps": ["Forecast", "Predictive Action", "Mission", "Continuous Improvement"], "summary": "先看预测，再转任务和持续改进。"},
            {"name": "治理路径", "steps": ["Policy Gate", "Boundary", "Mission", "Constitution"], "summary": "先复核策略边界，再执行只读任务排序。"},
        ]

    @staticmethod
    def _build_recommended_actions(status: str) -> list[str]:
        actions = [
            "先处理 P0 / critical 任务",
            "再处理 blocked / failed 任务",
            "把观察任务保持为只读跟踪",
            "任务执行前先进入推荐工作台",
            "必要时导出 Timeline 和 Forecast 做复盘",
            "治理风险出现时提高人工复核",
            "不要从 Mission Control 自动执行任务",
            "不要把 Mission 建议写入业务状态",
        ]
        if status in {"critical", "overloaded"}:
            actions.insert(0, "先收敛关键风险和阻塞任务")
        return actions[:8]

    @staticmethod
    def _build_summary(status: str, today: list[dict], critical: list[dict], blocked: list[dict]) -> str:
        if status == "critical":
            return f"AI Runtime 任务指挥中心检测到关键风险，今日任务 {len(today)} 项，关键任务 {len(critical)} 项，阻塞任务 {len(blocked)} 项。"
        if status == "overloaded":
            return f"AI Runtime 今日任务负载较高，建议先处理 {len(critical)} 个关键任务和 {len(blocked)} 个阻塞任务。"
        if status == "active":
            return f"AI Runtime 今日有 {len(today)} 个任务建议，按推荐执行顺序只读复核。"
        return "AI Runtime 当前较平稳，保持观察任务和常规巡检。"

    @staticmethod
    def build_mission_control_text(center: dict | None = None) -> str:
        center = center or AIRuntimeMissionControlService.build_mission_control_center({})
        lines = [
            "【AI Runtime 任务指挥中心】",
            "",
            f"任务状态：{center.get('mission_status') or '-'}",
            f"摘要：{center.get('summary') or '-'}",
            "",
            "今日任务：",
        ]
        for item in center.get("today_missions") or []:
            lines.append(f"- [{item.get('priority')}] {item.get('title')} / {item.get('source_module')}")
        return "\n".join(lines)

    @staticmethod
    def build_mission_control_markdown(center: dict | None = None) -> str:
        center = center or AIRuntimeMissionControlService.build_mission_control_center({})
        lines = [
            "# AI Runtime 任务指挥中心",
            "",
            f"- 任务状态：{center.get('mission_status') or '-'}",
            f"- 摘要：{center.get('summary') or '-'}",
            "",
            "## 今日任务",
        ]
        for item in center.get("today_missions") or []:
            lines.append(f"- **{item.get('title')}**：{item.get('priority')} / {item.get('source_module')}")
        for title, key in [
            ("高优先级任务", "critical_missions"),
            ("阻塞任务", "blocked_missions"),
            ("观察任务", "observation_missions"),
            ("推荐执行顺序", "recommended_execution_order"),
            ("推荐工作台", "recommended_workspaces"),
        ]:
            lines.extend(["", f"## {title}"])
            for item in center.get(key) or []:
                label = item.get("title") or item.get("workspace") or item.get("summary") or str(item)
                lines.append(f"- {label}")
        return "\n".join(lines)

    @staticmethod
    def build_mission_control_rows(center: dict | None = None) -> list[dict]:
        center = center or AIRuntimeMissionControlService.build_mission_control_center({})
        rows = []
        for category, key in [
            ("优先任务", "priority_tasks"),
            ("人工确认", "manual_confirm_tasks"),
            ("阻塞任务", "blocked_tasks"),
            ("风险任务", "risk_tasks"),
            ("依赖关系", "runtime_dependencies"),
            ("执行顺序", "execution_order"),
        ]:
            for item in center.get(key) or []:
                if key == "execution_order":
                    rows.append({
                        "分类": category,
                        "标题": item.get("title") or "",
                        "状态": "normal",
                        "优先级": str(item.get("step") or ""),
                        "目标": " / ".join(item.get("missions") or []),
                        "原因": item.get("summary") or "",
                        "建议动作": "按顺序只读复核。",
                    })
                    continue
                rows.append({
                    "分类": category,
                    "标题": item.get("title") or "",
                    "状态": item.get("status") or "",
                    "优先级": item.get("priority") or "",
                    "目标": item.get("target") or item.get("source_module") or item.get("recommended_workspace") or "",
                    "原因": item.get("reason") or item.get("summary") or "",
                    "建议动作": item.get("recommended_action") or "人工复核后再处理，不自动执行。",
                })
        return rows
