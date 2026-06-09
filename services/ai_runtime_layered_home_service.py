"""Read-only layered home aggregation for AI Runtime OS."""


class AIRuntimeLayeredHomeService:
    """Compress dashboard centers into seven operational layers."""

    @classmethod
    def build_layered_home(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        layers = cls._build_layers(dashboard)
        status = cls._layered_home_status(dashboard)

        return {
            "layered_home_status": status,
            "summary": cls._summary(status, layers),
            "layers": layers,
            "primary_recommendation": cls._primary_recommendation(status),
            "recommended_entry": cls._recommended_entry(status),
            "recommended_actions": cls._recommended_actions(status),
        }

    @classmethod
    def build_layered_home_text(cls, layered_home: dict | None = None) -> str:
        layered_home = layered_home or {}
        lines = [
            "【AI Runtime OS 分层首页】",
            f"状态：{layered_home.get('layered_home_status') or 'normal'}",
            f"摘要：{layered_home.get('summary') or ''}",
            f"推荐入口：{layered_home.get('recommended_entry') or ''}",
            f"首要建议：{layered_home.get('primary_recommendation') or ''}",
            "",
        ]
        for layer in layered_home.get("layers") or []:
            lines.append(
                f"{layer.get('layer')} {layer.get('title')} / "
                f"{layer.get('status')} / {layer.get('entry_route')}"
            )
            lines.append(f"- 模块：{', '.join(layer.get('modules') or [])}")
            lines.append(f"- 建议：{layer.get('summary') or ''}")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_layered_home_markdown(cls, layered_home: dict | None = None) -> str:
        layered_home = layered_home or {}
        lines = [
            "# AI Runtime OS 分层首页",
            "",
            f"- 状态：{layered_home.get('layered_home_status') or 'normal'}",
            f"- 摘要：{layered_home.get('summary') or ''}",
            f"- 推荐入口：{layered_home.get('recommended_entry') or ''}",
            f"- 首要建议：{layered_home.get('primary_recommendation') or ''}",
            "",
        ]
        for layer in layered_home.get("layers") or []:
            lines.append(f"## {layer.get('layer')} {layer.get('title')}")
            lines.append(f"- 状态：{layer.get('status') or ''}")
            lines.append(f"- 入口：{layer.get('entry_route') or ''}")
            lines.append(f"- 优先级：{layer.get('priority') or ''}")
            lines.append(f"- 模块：{', '.join(layer.get('modules') or [])}")
            lines.append(f"- 说明：{layer.get('summary') or ''}")
            lines.append("")
        return "\n".join(lines).rstrip()

    @staticmethod
    def build_layered_home_rows(layered_home: dict | None = None) -> list[dict]:
        rows = []
        for layer in (layered_home or {}).get("layers") or []:
            rows.append({
                "层级": f"{layer.get('layer')} {layer.get('title')}",
                "状态": layer.get("status") or "",
                "模块": " / ".join(layer.get("modules") or []),
                "入口": layer.get("entry_route") or "",
                "建议": layer.get("summary") or "",
            })
        return rows

    @classmethod
    def _build_layers(cls, dashboard: dict) -> list[dict]:
        return [
            cls._layer(
                "L1",
                "总览决策层",
                ["Executive Digest", "Practical Console", "Admin Home"],
                "/ai-dashboard/home",
                cls._status_from_sources([
                    (dashboard.get("ai_runtime_practical_console") or {}).get("console_status"),
                    (dashboard.get("ai_runtime_executive_digest_center") or {}).get("digest_status"),
                    (dashboard.get("ai_dashboard_admin_home_center") or {}).get("admin_home_status"),
                ]),
                "汇总今日决策、实用控制台和管理首页入口。",
                "P0",
            ),
            cls._layer(
                "L2",
                "任务执行层",
                ["Mission Control", "Action Launcher", "Workspace"],
                "/ai-dashboard/mission-control",
                cls._status_from_sources([
                    (dashboard.get("ai_runtime_mission_control_center") or {}).get("mission_status"),
                    (dashboard.get("ai_dashboard_action_launchpad_center") or {}).get("launchpad_status"),
                    (dashboard.get("ai_dashboard_workspace_center") or {}).get("workspace_status"),
                ]),
                "聚合任务指挥、动作启动台和角色工作台。",
                "P0",
            ),
            cls._layer(
                "L3",
                "运维安全层",
                ["OS Kernel", "Ops Health", "Production Hardening", "Release Readiness"],
                "/ai-dashboard/ops-health",
                cls._status_from_sources([
                    (dashboard.get("ai_runtime_os_kernel") or {}).get("kernel_status"),
                    (dashboard.get("ai_dashboard_ops_health_center") or {}).get("ops_status"),
                    (dashboard.get("ai_dashboard_production_hardening_center") or {}).get("hardening_status"),
                    (dashboard.get("ai_dashboard_release_readiness_center") or {}).get("release_status"),
                ]),
                "检查内核完整性、运维健康、生产加固和上线准备度。",
                "P0",
            ),
            cls._layer(
                "L4",
                "Runtime 智能层",
                ["Event", "Signal", "Correlation", "Causal", "Decision", "Simulation", "Strategy"],
                "/ai-dashboard#advanced-runtime-analysis-archive",
                cls._status_from_sources([
                    (dashboard.get("ai_runtime_event_timeline") or {}).get("timeline_status"),
                    (dashboard.get("ai_runtime_signal_intelligence") or {}).get("signal_status"),
                    (dashboard.get("ai_runtime_correlation_center") or {}).get("correlation_status"),
                    (dashboard.get("ai_runtime_causal_graph_center") or {}).get("causal_status"),
                    (dashboard.get("ai_runtime_decision_center") or {}).get("decision_status"),
                    (dashboard.get("ai_runtime_simulation_center") or {}).get("simulation_status"),
                    (dashboard.get("ai_runtime_strategy_center") or {}).get("strategy_status"),
                ]),
                "归档深度诊断、因果推断、决策推演和战略分析。",
                "P1",
            ),
            cls._layer(
                "L5",
                "治理文明层",
                [
                    "Judgment",
                    "Governance Court",
                    "Civilization",
                    "Integrity",
                    "Immune",
                    "Adaptive",
                    "Resilience",
                    "Evolutionary Fitness",
                ],
                "/ai-dashboard#advanced-runtime-analysis-archive",
                cls._status_from_sources([
                    (dashboard.get("ai_runtime_judgment_center") or {}).get("judgment_status"),
                    (dashboard.get("ai_runtime_governance_court_center") or {}).get("court_status"),
                    (dashboard.get("ai_runtime_civilization_center") or {}).get("civilization_status"),
                    (dashboard.get("ai_runtime_integrity_center") or {}).get("integrity_status"),
                    (dashboard.get("ai_runtime_immune_center") or {}).get("immune_status"),
                    (dashboard.get("ai_runtime_adaptive_center") or {}).get("adaptive_status"),
                    (dashboard.get("ai_runtime_resilience_center") or {}).get("resilience_status"),
                    (dashboard.get("ai_runtime_evolutionary_fitness_center") or {}).get("fitness_status"),
                ]),
                "归档治理裁决、文明原则、完整性、免疫和长期适应度。",
                "P1",
            ),
            cls._layer(
                "L6",
                "上线交付层",
                ["Release Package", "Release Runbook", "Export Operations"],
                "/ai-dashboard/export-operations",
                cls._status_from_sources([
                    (dashboard.get("ai_dashboard_release_package_center") or {}).get("package_status"),
                    (dashboard.get("ai_dashboard_release_runbook_center") or {}).get("runbook_status"),
                    (dashboard.get("ai_dashboard_export_operations_center") or {}).get("operations_status"),
                ]),
                "聚合发布包、发布 Runbook 和导出运营能力。",
                "P2",
            ),
            cls._layer(
                "L7",
                "文档导航层",
                ["Documentation", "Navigation", "Module Search", "Architecture Map"],
                "/ai-dashboard/navigation",
                cls._status_from_sources([
                    (dashboard.get("ai_dashboard_documentation_center") or {}).get("documentation_status"),
                    (dashboard.get("ai_dashboard_navigation_center") or {}).get("navigation_status"),
                    (dashboard.get("ai_dashboard_module_search_center") or {}).get("module_search_status"),
                    (dashboard.get("ai_dashboard_architecture_map_center") or {}).get("architecture_status"),
                ]),
                "提供文档、导航、模块搜索和系统架构地图。",
                "P2",
            ),
        ]

    @staticmethod
    def _layer(layer: str, title: str, modules: list[str], entry_route: str, status: str, summary: str, priority: str) -> dict:
        return {
            "layer": layer,
            "title": title,
            "status": status,
            "summary": summary,
            "modules": modules,
            "entry_route": entry_route,
            "priority": priority,
        }

    @staticmethod
    def _layered_home_status(dashboard: dict) -> str:
        practical = dashboard.get("ai_runtime_practical_console") or {}
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        immune = dashboard.get("ai_runtime_immune_center") or {}
        integrity = dashboard.get("ai_runtime_integrity_center") or {}
        signal = dashboard.get("ai_runtime_signal_intelligence") or {}
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        adaptive = dashboard.get("ai_runtime_adaptive_center") or {}
        resilience = dashboard.get("ai_runtime_resilience_center") or {}

        if (
            practical.get("console_status") == "urgent"
            or release.get("release_status") == "blocked"
            or immune.get("immune_status") == "critical"
            or int(integrity.get("integrity_score") or 100) < 50
        ):
            return "urgent"
        if (
            signal.get("signal_status") == "warning"
            or ops.get("ops_status") == "warning"
            or release.get("release_status") == "conditional"
            or adaptive.get("adaptive_status") == "rigid"
            or resilience.get("resilience_status") == "fragile"
        ):
            return "attention"
        return "normal"

    @staticmethod
    def _status_from_sources(values: list[str | None]) -> str:
        normalized = {str(value).lower().strip() for value in values if value}
        if normalized & {"urgent", "critical", "blocked", "risky"}:
            return "urgent"
        if normalized & {"attention", "warning", "conditional", "fragile", "rigid"}:
            return "attention"
        return "normal"

    @staticmethod
    def _summary(status: str, layers: list[dict]) -> str:
        attention_count = len([layer for layer in layers if layer.get("status") == "attention"])
        urgent_count = len([layer for layer in layers if layer.get("status") == "urgent"])
        if status == "urgent":
            return f"Runtime OS 分层首页发现 {urgent_count} 个紧急层级，建议优先进入实用控制台和运维安全层。"
        if status == "attention":
            return f"Runtime OS 当前有 {attention_count} 个关注层级，建议保持只读观察并按入口分层处理。"
        return "Runtime OS 分层首页状态正常，建议从高层摘要和实用控制台开始浏览。"

    @staticmethod
    def _primary_recommendation(status: str) -> str:
        if status == "urgent":
            return "优先查看 Practical Console 的今日必须处理和 L3 运维安全层。"
        if status == "attention":
            return "优先观察 L4 Runtime 智能层和 L5 治理文明层的关注信号。"
        return "从 L1 总览决策层进入，按需展开高级 Runtime 分析归档区。"

    @staticmethod
    def _recommended_entry(status: str) -> str:
        if status == "urgent":
            return "/ai-dashboard#ai-runtime-practical-console"
        if status == "attention":
            return "/ai-dashboard#advanced-runtime-analysis-archive"
        return "/ai-dashboard/home"

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        if status == "urgent":
            return [
                "先查看实用控制台的今日必须处理事项。",
                "再检查运维安全层的 OS Kernel、Ops Health 和 Release Readiness。",
                "保持只读分析，不触发自动审核、发布或恢复动作。",
            ]
        if status == "attention":
            return [
                "观察 Runtime 智能层的 warning 信号和归档分析。",
                "查看治理文明层是否存在长期风险。",
                "保持人工复核，不执行自动化处置。",
            ]
        return [
            "从分层首页进入对应层级。",
            "需要深度诊断时再展开高级 Runtime 分析归档区。",
        ]
