"""Practical read-only console that compresses advanced Runtime layers."""


class AIRuntimePracticalConsoleService:
    """Aggregate advanced Runtime centers into five operational views."""

    @classmethod
    def build_practical_console(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        must_handle = cls._must_handle_today(dashboard)
        observe = cls._observe_today(dashboard)
        never_automate = cls._never_automate(dashboard)
        governance_risks = cls._long_term_governance_risks(dashboard)
        weekly_focus = cls._weekly_improvement_focus(dashboard)
        status = cls._console_status(dashboard)

        return {
            "console_status": status,
            "summary": cls._summary(status, must_handle, observe, governance_risks),
            "must_handle_today": must_handle[:8],
            "observe_today": observe[:8],
            "never_automate": never_automate[:10],
            "long_term_governance_risks": governance_risks[:10],
            "weekly_improvement_focus": weekly_focus[:8],
            "recommended_workspace": cls._recommended_workspace(status),
            "recommended_page": cls._recommended_page(status),
            "recommended_actions": cls._recommended_actions(status),
        }

    @classmethod
    def build_practical_console_text(cls, console: dict | None = None) -> str:
        console = console or {}
        lines = [
            "【AI Runtime 实用控制台】",
            f"状态：{console.get('console_status') or 'normal'}",
            f"摘要：{console.get('summary') or ''}",
            f"推荐工作台：{console.get('recommended_workspace') or ''}",
            f"推荐页面：{console.get('recommended_page') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"{label}：")
            items = console.get(key) or []
            if items:
                for item in items:
                    lines.append(
                        f"- {item.get('title')} / {item.get('priority')} / "
                        f"{item.get('source')} / {item.get('reason')} / {item.get('route')}"
                    )
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_practical_console_markdown(cls, console: dict | None = None) -> str:
        console = console or {}
        lines = [
            "# AI Runtime 实用控制台",
            "",
            f"- 状态：{console.get('console_status') or 'normal'}",
            f"- 摘要：{console.get('summary') or ''}",
            f"- 推荐工作台：{console.get('recommended_workspace') or ''}",
            f"- 推荐页面：{console.get('recommended_page') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"## {label}")
            items = console.get(key) or []
            if items:
                for item in items:
                    lines.append(
                        f"- `{item.get('title')}` {item.get('priority')} / "
                        f"{item.get('source')}: {item.get('reason')} ({item.get('route')})"
                    )
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_practical_console_rows(cls, console: dict | None = None) -> list[dict]:
        rows = []
        for label, key in cls._sections():
            for item in (console or {}).get(key) or []:
                rows.append({
                    "分类": label,
                    "事项": item.get("title") or "",
                    "优先级": item.get("priority") or "",
                    "来源": item.get("source") or "",
                    "原因": item.get("reason") or "",
                    "Route": item.get("route") or "",
                })
        return rows

    @staticmethod
    def _console_status(dashboard: dict) -> str:
        decision = dashboard.get("ai_runtime_decision_center") or {}
        court = dashboard.get("ai_runtime_governance_court_center") or {}
        immune = dashboard.get("ai_runtime_immune_center") or {}
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        integrity = dashboard.get("ai_runtime_integrity_center") or {}
        signal = dashboard.get("ai_runtime_signal_intelligence") or {}
        correlation = dashboard.get("ai_runtime_correlation_center") or {}
        adaptive = dashboard.get("ai_runtime_adaptive_center") or {}
        resilience = dashboard.get("ai_runtime_resilience_center") or {}
        fitness = dashboard.get("ai_runtime_evolutionary_fitness_center") or {}

        if (
            decision.get("decision_status") == "critical"
            or court.get("court_status") == "critical"
            or immune.get("immune_status") == "critical"
            or release.get("release_status") == "blocked"
            or int(integrity.get("integrity_score") or 100) < 50
        ):
            return "urgent"
        if (
            signal.get("signal_status") == "warning"
            or correlation.get("correlation_status") == "attention"
            or adaptive.get("adaptive_status") == "rigid"
            or resilience.get("resilience_status") == "fragile"
            or fitness.get("fitness_status") == "unstable evolution"
        ):
            return "attention"
        return "normal"

    @classmethod
    def _must_handle_today(cls, dashboard: dict) -> list[dict]:
        items = []
        decision = dashboard.get("ai_runtime_decision_center") or {}
        for item in (decision.get("blocked_decisions") or []) + (decision.get("high_risk_decisions") or []):
            items.append(cls._entry(item, "critical", "Decision Center", "blocked or high-risk decision", "/ai-dashboard"))
        intervention = dashboard.get("ai_runtime_intervention_center") or {}
        for item in (intervention.get("blocking_interventions") or []) + (intervention.get("root_cause_interventions") or []):
            items.append(cls._entry(item, item.get("priority") or "high", "Intervention Center", "blocking or root-cause intervention plan", "/ai-dashboard"))
        causal = dashboard.get("ai_runtime_causal_graph_center") or {}
        for item in causal.get("critical_paths") or []:
            items.append(cls._entry(item, "critical", "Causal Graph", "critical causal path", "/ai-dashboard"))
        immune = dashboard.get("ai_runtime_immune_center") or {}
        for item in immune.get("systemic_risks") or []:
            items.append(cls._entry(item, item.get("risk") or "critical", "Immune System", "systemic Runtime risk", "/ai-dashboard"))
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        if release.get("release_status") == "blocked":
            items.append(cls._entry(release, "critical", "Release Readiness", "release readiness is blocked", "/ai-dashboard"))
        return items[:8]

    @classmethod
    def _observe_today(cls, dashboard: dict) -> list[dict]:
        items = []
        signal = dashboard.get("ai_runtime_signal_intelligence") or {}
        for item in signal.get("warning_signals") or []:
            items.append(cls._entry(item, "medium", "Signal Intelligence", "warning signal", "/ai-dashboard"))
        correlation = dashboard.get("ai_runtime_correlation_center") or {}
        for item in correlation.get("correlations") or []:
            if item.get("confidence") == "medium":
                items.append(cls._entry(item, "medium", "Correlation Center", "medium-confidence correlation", "/ai-dashboard"))
        forecast = dashboard.get("ai_runtime_forecast_center") or {}
        for item in forecast.get("potential_risks") or []:
            items.append(cls._entry(item, item.get("risk") or "medium", "Runtime Forecast", "forecast risk", "/ai-dashboard/runtime-forecast-export"))
        adaptive = dashboard.get("ai_runtime_adaptive_center") or {}
        for item in adaptive.get("environment_change_signals") or []:
            items.append(cls._entry(item, item.get("risk") or "medium", "Adaptive System", "environment change signal", "/ai-dashboard"))
        resilience = dashboard.get("ai_runtime_resilience_center") or {}
        for item in resilience.get("stress_response_patterns") or []:
            items.append(cls._entry(item, item.get("risk") or "medium", "Resilience System", "stress response pattern", "/ai-dashboard"))
        return items[:8]

    @classmethod
    def _never_automate(cls, dashboard: dict) -> list[dict]:
        items = []
        judgment = dashboard.get("ai_runtime_judgment_center") or {}
        for item in judgment.get("dangerous_automations") or []:
            items.append(cls._entry(item, item.get("risk") or "critical", "Judgment Center", "dangerous automation", "/ai-dashboard"))
        court = dashboard.get("ai_runtime_governance_court_center") or {}
        for item in court.get("forbidden_domains") or []:
            items.append(cls._entry(item, item.get("risk") or "critical", "Governance Court", "forbidden domain", "/ai-dashboard"))
        civilization = dashboard.get("ai_runtime_civilization_center") or {}
        for item in civilization.get("forbidden_civilization_paths") or []:
            items.append(cls._entry(item, item.get("risk") or "critical", "Civilization Center", "forbidden civilization path", "/ai-dashboard"))
        boundary = dashboard.get("ai_runtime_boundary_center") or {}
        for item in (boundary.get("constraints") or boundary.get("boundary_constraints") or boundary.get("boundary_rules") or []):
            items.append(cls._entry(item, "critical", "Boundary Center", "boundary constraint", "/ai-dashboard/runtime-boundary-export"))
        constitution = dashboard.get("ai_runtime_constitution_center") or {}
        for item in (constitution.get("constraints") or constitution.get("constitution_constraints") or constitution.get("principles") or []):
            items.append(cls._entry(item, "critical", "Constitution Center", "constitution constraint", "/ai-dashboard/runtime-constitution-export"))
        return cls._dedupe(items)[:10]

    @classmethod
    def _long_term_governance_risks(cls, dashboard: dict) -> list[dict]:
        items = []
        civilization = dashboard.get("ai_runtime_civilization_center") or {}
        for item in civilization.get("civilization_conflicts") or []:
            items.append(cls._entry(item, item.get("risk") or "high", "Civilization Center", "civilization conflict", "/ai-dashboard"))
        integrity = dashboard.get("ai_runtime_integrity_center") or {}
        for key, reason in [
            ("governance_conflicts", "governance integrity conflict"),
            ("civilization_conflicts", "civilization integrity conflict"),
            ("strategy_conflicts", "strategy integrity conflict"),
            ("value_fragmentations", "value fragmentation"),
        ]:
            for item in integrity.get(key) or []:
                items.append(cls._entry(item, item.get("risk") or "high", "Integrity Center", reason, "/ai-dashboard"))
        immune = dashboard.get("ai_runtime_immune_center") or {}
        for item in immune.get("governance_corruption_risks") or []:
            items.append(cls._entry(item, item.get("risk") or "critical", "Immune System", "governance corruption risk", "/ai-dashboard"))
        adaptive = dashboard.get("ai_runtime_adaptive_center") or {}
        for item in adaptive.get("aging_governance_patterns") or []:
            items.append(cls._entry(item, item.get("risk") or "high", "Adaptive System", "aging governance pattern", "/ai-dashboard"))
        fitness = dashboard.get("ai_runtime_evolutionary_fitness_center") or {}
        for item in fitness.get("extinction_risks") or []:
            items.append(cls._entry(item, item.get("risk") or "critical", "Evolutionary Fitness", "extinction risk", "/ai-dashboard"))
        return items[:10]

    @classmethod
    def _weekly_improvement_focus(cls, dashboard: dict) -> list[dict]:
        items = []
        strategy = dashboard.get("ai_runtime_strategy_center") or {}
        for key in ["stability_roadmap", "automation_roadmap", "governance_roadmap", "capability_priorities"]:
            for item in strategy.get(key) or []:
                items.append(cls._entry(item, item.get("priority") or item.get("risk") or "medium", "Strategy Center", key, "/ai-dashboard"))
        memory = dashboard.get("ai_runtime_memory_center") or {}
        for key in ["governance_lessons", "stability_lessons", "strategic_lessons"]:
            for item in memory.get(key) or []:
                items.append(cls._entry(item, item.get("risk") or "medium", "Memory Center", key, "/ai-dashboard"))
        resilience = dashboard.get("ai_runtime_resilience_center") or {}
        for action in resilience.get("recommended_actions") or []:
            items.append(cls._entry({"title": action}, "medium", "Resilience System", "resilience recommendation", "/ai-dashboard"))
        fitness = dashboard.get("ai_runtime_evolutionary_fitness_center") or {}
        for action in fitness.get("recommended_actions") or []:
            items.append(cls._entry({"title": action}, "medium", "Evolutionary Fitness", "fitness recommendation", "/ai-dashboard"))
        maintenance = dashboard.get("ai_dashboard_ops_maintenance_center") or dashboard.get("ai_dashboard_ops_maintenance_plan_center") or {}
        for item in (maintenance.get("weekly_focus") or maintenance.get("maintenance_tasks") or maintenance.get("recommended_actions") or []):
            items.append(cls._entry(item, "medium", "Ops Maintenance", "ops maintenance focus", "/ai-dashboard"))
        return items[:8]

    @staticmethod
    def _entry(item, priority: str, source: str, reason: str, route: str) -> dict:
        if not isinstance(item, dict):
            item = {"title": str(item)}
        title = (
            item.get("title")
            or item.get("decision")
            or item.get("candidate")
            or item.get("node_id")
            or item.get("signal_key")
            or item.get("event_key")
            or item.get("summary")
            or item.get("release_status")
            or "Runtime item"
        )
        return {
            "title": str(title),
            "priority": str(priority or item.get("priority") or item.get("risk") or "medium"),
            "source": source,
            "reason": str(item.get("reason") or item.get("summary") or reason),
            "route": item.get("route") or route,
        }

    @staticmethod
    def _dedupe(items: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for item in items:
            marker = (item.get("title"), item.get("source"))
            if marker in seen:
                continue
            seen.add(marker)
            result.append(item)
        return result

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("今日必须处理", "must_handle_today"),
            ("今日只需观察", "observe_today"),
            ("禁止自动化事项", "never_automate"),
            ("长期治理风险", "long_term_governance_risks"),
            ("本周改进重点", "weekly_improvement_focus"),
        ]

    @staticmethod
    def _summary(status: str, must_handle: list, observe: list, governance_risks: list) -> str:
        return (
            f"Practical Console status is {status}; "
            f"{len(must_handle)} item(s) require handling today, "
            f"{len(observe)} item(s) need observation, and "
            f"{len(governance_risks)} long-term governance risk(s) are visible."
        )

    @staticmethod
    def _recommended_workspace(status: str) -> str:
        if status == "urgent":
            return "manager_workspace"
        if status == "attention":
            return "operator_workspace"
        return "admin_home"

    @staticmethod
    def _recommended_page(status: str) -> str:
        if status == "urgent":
            return "/ai-dashboard/home"
        if status == "attention":
            return "/ai-dashboard"
        return "/ai-dashboard/home"

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        actions = [
            "Keep Practical Console read-only; do not automatically repair, recover, publish, approve, deploy, or execute agents.",
            "Use the five operational views to decide manual review order.",
        ]
        if status == "urgent":
            actions.append("Start with '今日必须处理' and keep all automation-expansion decisions manual.")
        elif status == "attention":
            actions.append("Review observation items and weekly improvement focus before changing Runtime plans.")
        return actions
