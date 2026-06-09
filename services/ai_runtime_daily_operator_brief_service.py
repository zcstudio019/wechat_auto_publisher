"""Read-only Daily Operator Brief for AI Runtime OS."""

from datetime import date


class AIRuntimeDailyOperatorBriefService:
    """Compress Runtime OS signals into a daily operator brief."""

    @classmethod
    def build_daily_operator_brief(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        status = cls._brief_status(dashboard)
        pages = cls._recommended_pages(dashboard)
        must_do = cls._must_do_today(dashboard)
        watch = cls._watch_today(dashboard)
        never_do = cls._never_do_today(dashboard)
        human_review = cls._human_review_today(dashboard)
        governance_risks = cls._governance_risks_today(dashboard)
        exports = cls._recommended_exports()

        return {
            "brief_status": status,
            "brief_date": date.today().isoformat(),
            "headline": cls._headline(status, dashboard)[:80],
            "today_status": cls._today_status(status),
            "must_do_today": must_do[:8],
            "watch_today": watch[:8],
            "never_do_today": never_do[:10],
            "human_review_today": human_review[:10],
            "governance_risks_today": governance_risks[:10],
            "recommended_pages": pages[:8],
            "recommended_exports": exports[:8],
            "brief_summary": cls._brief_summary(status, must_do, governance_risks, pages, human_review)[:120],
            "recommended_actions": cls._recommended_actions(status, must_do, human_review, never_do)[:8],
        }

    @classmethod
    def build_daily_operator_brief_text(cls, brief: dict | None = None) -> str:
        brief = brief or {}
        lines = [
            "【AI Runtime OS 每日操作简报】",
            f"日期：{brief.get('brief_date') or ''}",
            f"状态：{brief.get('brief_status') or 'normal'}",
            f"Headline：{brief.get('headline') or ''}",
            f"摘要：{brief.get('brief_summary') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"{label}：")
            items = brief.get(key) or []
            if items:
                for item in items:
                    lines.append(cls._format_item(item))
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_daily_operator_brief_markdown(cls, brief: dict | None = None) -> str:
        brief = brief or {}
        lines = [
            "# AI Runtime OS 每日操作简报",
            "",
            f"- 日期：{brief.get('brief_date') or ''}",
            f"- 状态：{brief.get('brief_status') or 'normal'}",
            f"- Headline：{brief.get('headline') or ''}",
            f"- 摘要：{brief.get('brief_summary') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"## {label}")
            items = brief.get(key) or []
            if items:
                for item in items:
                    row = cls._row_item(item)
                    lines.append(f"- `{row.get('title')}` {row.get('priority')} / {row.get('source')} / {row.get('reason')} ({row.get('route')})")
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_daily_operator_brief_rows(cls, brief: dict | None = None) -> list[dict]:
        rows = []
        for label, key in cls._sections():
            for item in (brief or {}).get(key) or []:
                row = cls._row_item(item)
                rows.append({
                    "分类": label,
                    "事项": row.get("title") or "",
                    "优先级": row.get("priority") or "",
                    "来源": row.get("source") or "",
                    "Route": row.get("route") or "",
                    "原因": row.get("reason") or "",
                })
        return rows

    @classmethod
    def _brief_status(cls, dashboard: dict) -> str:
        one_page = dashboard.get("ai_runtime_one_page_console") or {}
        practical = dashboard.get("ai_runtime_practical_console") or {}
        governance = dashboard.get("ai_runtime_governance_summary") or {}
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        linter = dashboard.get("ai_runtime_policy_linter") or {}
        command = dashboard.get("ai_runtime_command_layer") or {}
        capability_governance = dashboard.get("ai_runtime_capability_governance") or {}
        mission = dashboard.get("ai_runtime_mission_control_center") or {}

        delegation_risks = capability_governance.get("delegation_risks") or []
        critical_delegation = any(cls._priority(item) in {"critical", "high"} for item in delegation_risks)
        if (
            one_page.get("console_status") == "urgent"
            or practical.get("console_status") == "urgent"
            or governance.get("summary_status") == "critical"
            or release.get("release_status") == "blocked"
            or cls._status(ops, "ops_status", "health_status") in {"critical", "failed", "risky"}
            or linter.get("linter_status") == "critical"
            or bool(command.get("blocked_commands"))
            or bool(capability_governance.get("forbidden_capabilities"))
            or critical_delegation
        ):
            return "urgent"

        if (
            governance.get("summary_status") == "attention"
            or practical.get("console_status") == "attention"
            or mission.get("mission_status") in {"active", "overloaded", "attention", "warning"}
            or cls._status(ops, "ops_status", "health_status") == "warning"
            or release.get("release_status") == "conditional"
            or linter.get("linter_status") == "warning"
            or bool(capability_governance.get("approval_required_capabilities"))
        ):
            return "attention"
        return "normal"

    @staticmethod
    def _headline(status: str, dashboard: dict) -> str:
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        governance = dashboard.get("ai_runtime_governance_summary") or {}
        command = dashboard.get("ai_runtime_command_layer") or {}
        if release.get("release_status") == "blocked":
            return "今日上线准备受阻，建议先查看 Release Readiness 与 Ops Health。"
        if governance.get("summary_status") == "critical":
            return "今日存在治理风险，优先复核高风险能力与禁止自动化事项。"
        if command.get("blocked_commands"):
            return "今日存在人工复核事项，请优先查看 Command Layer 与 Capability Governance。"
        if status == "urgent":
            return "今日 Runtime 存在紧急风险，先处理必须事项并保持人工复核。"
        if status == "attention":
            return "今日 Runtime 有关注信号，建议按简报入口逐项只读查看。"
        return "今日 Runtime 状态稳定，建议按常规巡检执行。"

    @staticmethod
    def _today_status(status: str) -> str:
        return {
            "urgent": "紧急",
            "attention": "关注",
            "normal": "正常",
        }.get(status, "正常")

    @classmethod
    def _must_do_today(cls, dashboard: dict) -> list[dict]:
        items = []
        practical = dashboard.get("ai_runtime_practical_console") or {}
        items.extend(cls._entries(practical.get("must_handle_today"), "Practical Console", "/ai-dashboard#ai-runtime-practical-console", "今日必须处理"))
        mission = dashboard.get("ai_runtime_mission_control_center") or {}
        items.extend(cls._entries(mission.get("critical_missions"), "Mission Control", "/ai-dashboard/mission-control", "critical mission"))
        governance = dashboard.get("ai_runtime_governance_summary") or {}
        items.extend(cls._entries(governance.get("high_risk_capabilities"), "Governance Summary", "/ai-dashboard", "high risk capability"))
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        items.extend(cls._entries(release.get("must_fix_before_release"), "Release Readiness", "/ai-dashboard/release-readiness", "must fix before release"))
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        items.extend(cls._entries(ops.get("risk_items") or ops.get("ops_risks"), "Ops Health", "/ai-dashboard/ops-health", "critical ops risk"))
        linter = dashboard.get("ai_runtime_policy_linter") or {}
        items.extend(cls._entries(linter.get("critical_issues"), "Policy Linter", "/ai-dashboard", "critical policy issue"))
        return cls._dedupe(items)

    @classmethod
    def _watch_today(cls, dashboard: dict) -> list[dict]:
        items = []
        practical = dashboard.get("ai_runtime_practical_console") or {}
        items.extend(cls._entries(practical.get("observe_today"), "Practical Console", "/ai-dashboard#ai-runtime-practical-console", "今日观察"))
        signal = dashboard.get("ai_runtime_signal_intelligence") or {}
        items.extend(cls._entries(signal.get("warning_signals"), "Signal Intelligence", "/ai-dashboard#advanced-runtime-analysis-archive", "signal warning"))
        forecast = dashboard.get("ai_runtime_forecast_center") or {}
        items.extend(cls._entries(forecast.get("potential_risks"), "Forecast", "/ai-dashboard", "forecast risk"))
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        items.extend(cls._entries(ops.get("warning_items"), "Ops Health", "/ai-dashboard/ops-health", "ops warning"))
        adaptive = dashboard.get("ai_runtime_adaptive_center") or {}
        if adaptive.get("adaptive_status") in {"rigid", "attention", "critical"}:
            items.extend(cls._entries(adaptive.get("environment_change_signals"), "Adaptive System", "/ai-dashboard#advanced-runtime-analysis-archive", "adaptive attention"))
        resilience = dashboard.get("ai_runtime_resilience_center") or {}
        if resilience.get("resilience_status") in {"fragile", "warning", "critical"}:
            items.extend(cls._entries(resilience.get("stress_response_patterns"), "Resilience System", "/ai-dashboard#advanced-runtime-analysis-archive", "resilience attention"))
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        if release.get("release_status") == "conditional":
            items.extend(cls._entries(release.get("warning_checks"), "Release Readiness", "/ai-dashboard/release-readiness", "release conditional"))
        return cls._dedupe(items)

    @classmethod
    def _never_do_today(cls, dashboard: dict) -> list[dict]:
        items = []
        practical = dashboard.get("ai_runtime_practical_console") or {}
        items.extend(cls._entries(practical.get("never_automate"), "Practical Console", "/ai-dashboard#ai-runtime-practical-console", "never automate"))
        governance = dashboard.get("ai_runtime_governance_summary") or {}
        items.extend(cls._entries(governance.get("forbidden_capabilities"), "Governance Summary", "/ai-dashboard", "forbidden capability"))
        compiler = dashboard.get("ai_runtime_policy_compiler") or {}
        items.extend(cls._entries(compiler.get("blocked_policies"), "Policy Compiler", "/ai-dashboard", "blocked or forbidden policy"))
        judgment = dashboard.get("ai_runtime_judgment_center") or {}
        items.extend(cls._entries(judgment.get("dangerous_automations"), "Judgment Center", "/ai-dashboard#advanced-runtime-analysis-archive", "dangerous automation"))
        court = dashboard.get("ai_runtime_governance_court_center") or {}
        items.extend(cls._entries(court.get("forbidden_domains"), "Governance Court", "/ai-dashboard#advanced-runtime-analysis-archive", "forbidden domain"))
        capability = dashboard.get("ai_runtime_capability_governance") or {}
        items.extend(cls._entries(capability.get("forbidden_capabilities"), "Capability Governance", "/ai-dashboard", "forbidden capability"))
        return cls._dedupe(items)

    @classmethod
    def _human_review_today(cls, dashboard: dict) -> list[dict]:
        items = []
        command = dashboard.get("ai_runtime_command_layer") or {}
        items.extend(cls._entries(command.get("human_review_commands"), "Command Layer", "/ai-dashboard", "human review command"))
        capability = dashboard.get("ai_runtime_capability_governance") or {}
        items.extend(cls._entries(capability.get("approval_required_capabilities"), "Capability Governance", "/ai-dashboard", "approval required capability"))
        governance = dashboard.get("ai_runtime_governance_summary") or {}
        items.extend(cls._entries(governance.get("human_only_capabilities"), "Governance Summary", "/ai-dashboard", "human only capability"))
        linter = dashboard.get("ai_runtime_policy_linter") or {}
        items.extend(cls._entries(linter.get("human_review_gaps"), "Policy Linter", "/ai-dashboard", "human review gap"))
        compiler = dashboard.get("ai_runtime_policy_compiler") or {}
        items.extend(cls._entries(compiler.get("human_only_policies"), "Policy Compiler", "/ai-dashboard", "human only policy"))
        return cls._dedupe(items)

    @classmethod
    def _governance_risks_today(cls, dashboard: dict) -> list[dict]:
        items = []
        governance = dashboard.get("ai_runtime_governance_summary") or {}
        items.extend(cls._entries(governance.get("delegation_risks"), "Governance Summary", "/ai-dashboard", "delegation risk"))
        linter = dashboard.get("ai_runtime_policy_linter") or {}
        items.extend(cls._entries(linter.get("critical_issues"), "Policy Linter", "/ai-dashboard", "critical policy issue"))
        items.extend(cls._entries(linter.get("warning_issues"), "Policy Linter", "/ai-dashboard", "warning policy issue"))
        capability = dashboard.get("ai_runtime_capability_governance") or {}
        items.extend(cls._entries(capability.get("delegation_risks"), "Capability Governance", "/ai-dashboard", "delegation risk"))
        integrity = dashboard.get("ai_runtime_integrity_center") or {}
        items.extend(cls._entries(integrity.get("governance_conflicts"), "Integrity Center", "/ai-dashboard#advanced-runtime-analysis-archive", "governance conflict"))
        immune = dashboard.get("ai_runtime_immune_center") or {}
        items.extend(cls._entries(immune.get("governance_corruption_risks"), "Immune System", "/ai-dashboard#advanced-runtime-analysis-archive", "governance corruption risk"))
        compiler = dashboard.get("ai_runtime_policy_compiler") or {}
        items.extend(cls._entries(compiler.get("policy_conflicts"), "Policy Compiler", "/ai-dashboard", "policy conflict"))
        return cls._dedupe(items)

    @classmethod
    def _recommended_pages(cls, dashboard: dict) -> list[dict]:
        pages = []
        entry_router = dashboard.get("ai_runtime_entry_router") or {}
        one_page = dashboard.get("ai_runtime_one_page_console") or {}
        primary_entry = entry_router.get("primary_entry") or one_page.get("primary_entry") or {}
        if primary_entry:
            pages.append(cls._page(primary_entry.get("title") or "推荐入口", primary_entry.get("route") or "/ai-dashboard/home", primary_entry.get("reason") or "Entry Router primary entry."))
        pages.extend([
            cls._page("AI Dashboard 管理首页中心", "/ai-dashboard/home", "兜底管理首页。"),
            cls._page("AI Runtime 任务指挥中心", "/ai-dashboard/mission-control", "兜底任务指挥。"),
            cls._page("AI Dashboard 运维健康中心", "/ai-dashboard/ops-health", "兜底运维健康。"),
            cls._page("AI Dashboard 上线准备度中心", "/ai-dashboard/release-readiness", "兜底上线准备度。"),
            cls._page("AI Runtime Governance Summary", "/ai-dashboard", "查看治理汇总。"),
            cls._page("AI Runtime Policy Linter", "/ai-dashboard", "查看策略静态检查。"),
            cls._page("AI Runtime Capability Governance", "/ai-dashboard", "查看能力治理。"),
        ])
        return cls._dedupe_pages(pages)[:8]

    @staticmethod
    def _recommended_exports() -> list[dict]:
        return [
            {"title": "Daily Operator Brief", "route": "/ai-dashboard/runtime-daily-operator-brief-export?format=md", "reason": "导出每日操作简报。"},
            {"title": "Governance Summary", "route": "/ai-dashboard/governance-summary-export?format=md", "reason": "导出治理汇总。"},
            {"title": "One-Page Console", "route": "/ai-dashboard/runtime-one-page-console-export?format=md", "reason": "导出单页总控台。"},
            {"title": "Practical Console", "route": "/ai-dashboard/runtime-practical-console-export?format=md", "reason": "导出实用控制台。"},
            {"title": "Release Readiness", "route": "/ai-dashboard/release-readiness-export?format=md", "reason": "导出上线准备度。"},
            {"title": "Ops Health", "route": "/ai-dashboard/ops-health-export?format=md", "reason": "导出运维健康。"},
            {"title": "Policy Compiler", "route": "/ai-dashboard/runtime-policy-compiler-export?format=md", "reason": "导出策略编译器。"},
            {"title": "Policy Linter", "route": "/ai-dashboard/runtime-policy-linter-export?format=md", "reason": "导出策略静态检查器。"},
        ]

    @classmethod
    def _brief_summary(cls, status: str, must_do: list[dict], risks: list[dict], pages: list[dict], human_review: list[dict]) -> str:
        first_risk = (risks[0].get("title") if risks else "") or (must_do[0].get("title") if must_do else "暂无明显风险")
        first_page = pages[0].get("title") if pages else "AI Dashboard 管理首页中心"
        review_text = f"{len(human_review)} 项人工复核" if human_review else "暂无新增人工复核"
        return f"今日状态 {status}；首要风险：{first_risk}；首要入口：{first_page}；{review_text}，保持只读查看。"

    @staticmethod
    def _recommended_actions(status: str, must_do: list[dict], human_review: list[dict], never_do: list[dict]) -> list[str]:
        actions = []
        if must_do:
            actions.append("先处理 must_do_today。")
        if human_review:
            actions.append("再查看 human_review_today。")
        if never_do:
            actions.append("保持 never_do_today 不自动化。")
        actions.append("导出每日操作简报。")
        actions.append("需要时查看 Ops Health / Release Readiness。")
        if status == "normal":
            actions.insert(0, "按常规巡检查看推荐页面。")
        return actions[:8]

    @classmethod
    def _entries(cls, items: object, source: str, route: str, reason: str) -> list[dict]:
        if not isinstance(items, list):
            return []
        return [cls._entry(item, source, route, reason) for item in items]

    @classmethod
    def _entry(cls, item: object, source: str, route: str, reason: str) -> dict:
        if isinstance(item, dict):
            item_route = item.get("route") or item.get("recommended_route") or item.get("entry_route") or route
            return {
                "title": cls._title(item),
                "priority": cls._priority(item) or "medium",
                "source": source,
                "route": item_route,
                "reason": item.get("reason") or item.get("summary") or item.get("recommendation") or reason,
            }
        return {
            "title": str(item or ""),
            "priority": "medium",
            "source": source,
            "route": route,
            "reason": reason,
        }

    @staticmethod
    def _page(title: str, route: str, reason: str) -> dict:
        return {"title": title, "route": route, "reason": reason}

    @staticmethod
    def _status(data: dict, *keys: str) -> str:
        for key in keys:
            if data.get(key):
                return str(data.get(key))
        return ""

    @staticmethod
    def _title(item: dict) -> str:
        return str(
            item.get("title")
            or item.get("name")
            or item.get("item")
            or item.get("risk")
            or item.get("risk_key")
            or item.get("policy")
            or item.get("issue")
            or item.get("command_key")
            or item.get("summary")
            or item
        )

    @staticmethod
    def _priority(item: object) -> str:
        if isinstance(item, dict):
            return str(item.get("priority") or item.get("risk_level") or item.get("severity") or item.get("status") or item.get("risk") or "")
        return ""

    @staticmethod
    def _format_item(item: object) -> str:
        row = AIRuntimeDailyOperatorBriefService._row_item(item)
        return f"- {row.get('title') or ''} / {row.get('priority') or ''} / {row.get('source') or ''} / {row.get('route') or ''} / {row.get('reason') or ''}"

    @staticmethod
    def _row_item(item: object) -> dict:
        if isinstance(item, dict):
            return {
                "title": item.get("title") or item.get("summary") or item.get("reason") or "",
                "priority": item.get("priority") or item.get("risk_level") or item.get("severity") or item.get("status") or "",
                "source": item.get("source") or "",
                "route": item.get("route") or item.get("recommended_route") or "",
                "reason": item.get("reason") or item.get("summary") or item.get("recommendation") or "",
            }
        return {
            "title": str(item or ""),
            "priority": "",
            "source": "",
            "route": "",
            "reason": str(item or ""),
        }

    @staticmethod
    def _dedupe(items: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for item in items:
            key = (item.get("title"), item.get("source"), item.get("route"))
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    @staticmethod
    def _dedupe_pages(items: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for item in items:
            key = item.get("route")
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("今日必须处理", "must_do_today"),
            ("今日观察", "watch_today"),
            ("绝不能做", "never_do_today"),
            ("人工复核", "human_review_today"),
            ("治理风险", "governance_risks_today"),
            ("推荐页面", "recommended_pages"),
            ("推荐导出", "recommended_exports"),
            ("建议动作", "recommended_actions"),
        ]
