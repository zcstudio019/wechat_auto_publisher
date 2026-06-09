"""Read-only one-page console for AI Runtime OS."""


class AIRuntimeOnePageConsoleService:
    """Compress Runtime OS dashboard into a short operational console."""

    @classmethod
    def build_one_page_console(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        entry_router = dashboard.get("ai_runtime_entry_router") or {}
        practical = dashboard.get("ai_runtime_practical_console") or {}
        primary_entry = entry_router.get("primary_entry") or cls._default_primary_entry()
        status = cls._console_status(dashboard, entry_router, practical)

        return {
            "console_status": status,
            "headline": cls._headline(status, dashboard, entry_router, practical),
            "primary_entry": primary_entry,
            "today_must_do": cls._limit(practical.get("must_handle_today"), 5),
            "today_watch": cls._limit(practical.get("observe_today"), 5),
            "never_do": cls._limit(practical.get("never_automate"), 5),
            "system_health": cls._system_health(dashboard),
            "weekly_focus": cls._weekly_focus(dashboard, practical),
            "recommended_actions": cls._recommended_actions(status, primary_entry),
        }

    @classmethod
    def build_one_page_console_text(cls, console: dict | None = None) -> str:
        console = console or {}
        primary = console.get("primary_entry") or {}
        lines = [
            "【AI Runtime OS 单页总控台】",
            f"状态：{console.get('console_status') or 'normal'}",
            f"Headline：{console.get('headline') or ''}",
            f"主入口：{primary.get('title') or ''} / {primary.get('route') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"{label}：")
            items = console.get(key) or []
            if items:
                for item in items:
                    lines.append(f"- {cls._title(item)} / {cls._status(item)} / {cls._route(item)} / {cls._reason(item)}")
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_one_page_console_markdown(cls, console: dict | None = None) -> str:
        console = console or {}
        primary = console.get("primary_entry") or {}
        lines = [
            "# AI Runtime OS 单页总控台",
            "",
            f"- 状态：{console.get('console_status') or 'normal'}",
            f"- Headline：{console.get('headline') or ''}",
            f"- 主入口：[{primary.get('title') or ''}]({primary.get('route') or ''})",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"## {label}")
            items = console.get(key) or []
            if items:
                for item in items:
                    lines.append(f"- `{cls._title(item)}` {cls._status(item)} / {cls._reason(item)} ({cls._route(item)})")
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_one_page_console_rows(cls, console: dict | None = None) -> list[dict]:
        console = console or {}
        rows = []
        primary = console.get("primary_entry") or {}
        if primary:
            rows.append({
                "分类": "主入口",
                "事项": primary.get("title") or "",
                "状态": primary.get("priority") or "",
                "Route": primary.get("route") or "",
                "说明": primary.get("reason") or "",
            })
        for label, key in cls._sections():
            for item in console.get(key) or []:
                rows.append({
                    "分类": label,
                    "事项": cls._title(item),
                    "状态": cls._status(item),
                    "Route": cls._route(item),
                    "说明": cls._reason(item),
                })
        return rows

    @staticmethod
    def _console_status(dashboard: dict, entry_router: dict, practical: dict) -> str:
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        immune = dashboard.get("ai_runtime_immune_center") or {}
        integrity = dashboard.get("ai_runtime_integrity_center") or {}
        if (
            entry_router.get("router_status") == "urgent"
            or practical.get("console_status") == "urgent"
            or release.get("release_status") == "blocked"
            or immune.get("immune_status") == "critical"
            or int(integrity.get("integrity_score") or 100) < 50
        ):
            return "urgent"
        if entry_router.get("router_status") == "attention" or practical.get("console_status") == "attention":
            return "attention"
        return "normal"

    @staticmethod
    def _headline(status: str, dashboard: dict, entry_router: dict, practical: dict) -> str:
        if status == "urgent":
            text = "Runtime OS 有紧急入口建议，先看主入口和今日必须处理事项。"
        elif status == "attention":
            text = "Runtime OS 有关注信号，保持只读观察并按入口路由查看。"
        else:
            text = "Runtime OS 当前无明显阻塞，从管理首页和分层首页开始即可。"
        summary = (entry_router.get("summary") or practical.get("summary") or "").strip()
        if summary and len(text) < 45:
            text = f"{text} {summary}"
        return text[:80]

    @classmethod
    def _system_health(cls, dashboard: dict) -> list[dict]:
        executive = dashboard.get("ai_runtime_executive_digest_center") or {}
        practical = dashboard.get("ai_runtime_practical_console") or {}
        kernel = dashboard.get("ai_runtime_os_kernel") or {}
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        integrity = dashboard.get("ai_runtime_integrity_center") or {}
        immune = dashboard.get("ai_runtime_immune_center") or {}
        resilience = dashboard.get("ai_runtime_resilience_center") or {}
        return [
            cls._health("Executive Digest", executive.get("digest_status") or "stable", executive.get("one_line_summary") or executive.get("summary") or "", "/ai-dashboard/executive-digest"),
            cls._health("Practical Console", practical.get("console_status") or "normal", practical.get("summary") or "", "/ai-dashboard#ai-runtime-practical-console"),
            cls._health("OS Kernel", kernel.get("kernel_status") or "unknown", kernel.get("summary") or "", "/ai-dashboard"),
            cls._health("Ops Health", ops.get("ops_status") or "healthy", ops.get("summary") or "", "/ai-dashboard/ops-health"),
            cls._health("Release Readiness", release.get("release_status") or "conditional", release.get("summary") or "", "/ai-dashboard/release-readiness"),
            cls._health("Integrity", integrity.get("integrity_status") or integrity.get("integrity_score") or "stable", integrity.get("integrity_summary") or "", "/ai-dashboard#advanced-runtime-analysis-archive"),
            cls._health("Immune", immune.get("immune_status") or "stable", immune.get("immune_summary") or "", "/ai-dashboard#advanced-runtime-analysis-archive"),
            cls._health("Resilience", resilience.get("resilience_status") or "stable", resilience.get("long_term_resilience_outlook") or "", "/ai-dashboard#advanced-runtime-analysis-archive"),
        ]

    @classmethod
    def _weekly_focus(cls, dashboard: dict, practical: dict) -> list[dict]:
        items = []
        items.extend(practical.get("weekly_improvement_focus") or [])
        strategy = dashboard.get("ai_runtime_strategy_center") or {}
        maintenance = dashboard.get("ai_dashboard_ops_maintenance_center") or {}
        for key in ["stability_roadmap", "governance_roadmap", "capability_priorities"]:
            items.extend(strategy.get(key) or [])
        for action in maintenance.get("recommended_actions") or []:
            items.append({"title": action, "priority": "medium", "source": "Ops Maintenance", "reason": "weekly maintenance focus", "route": "/ai-dashboard/ops-health"})
        return cls._limit(items, 5)

    @staticmethod
    def _recommended_actions(status: str, primary_entry: dict) -> list[str]:
        actions = [f"先进入：{primary_entry.get('title') or 'AI Dashboard 管理首页中心'}。"]
        if status == "urgent":
            actions.append("只读查看今日必须处理事项，保持人工复核。")
        elif status == "attention":
            actions.append("只读观察今日关注项和系统健康。")
        else:
            actions.append("按需查看分层首页和高级 Runtime 分析归档区。")
        return actions

    @staticmethod
    def _default_primary_entry() -> dict:
        return {
            "title": "AI Dashboard 管理首页中心",
            "route": "/ai-dashboard/home",
            "reason": "默认进入管理首页总览。",
            "priority": "normal",
        }

    @staticmethod
    def _health(title: str, status: object, reason: str, route: str) -> dict:
        return {
            "title": title,
            "status": str(status),
            "reason": reason,
            "route": route,
        }

    @staticmethod
    def _limit(items: object, limit: int) -> list:
        if not isinstance(items, list):
            return []
        return items[:limit]

    @staticmethod
    def _title(item: object) -> str:
        if isinstance(item, dict):
            return str(item.get("title") or item.get("name") or item.get("signal_key") or item.get("event_key") or item.get("summary") or "")
        return str(item or "")

    @staticmethod
    def _status(item: object) -> str:
        if isinstance(item, dict):
            return str(item.get("status") or item.get("priority") or item.get("severity") or item.get("risk") or "")
        return ""

    @staticmethod
    def _route(item: object) -> str:
        if isinstance(item, dict):
            return str(item.get("route") or item.get("entry_route") or "")
        return ""

    @staticmethod
    def _reason(item: object) -> str:
        if isinstance(item, dict):
            return str(item.get("reason") or item.get("summary") or item.get("source") or "")
        return ""

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("今日必须处理", "today_must_do"),
            ("今日观察", "today_watch"),
            ("禁止自动化", "never_do"),
            ("系统健康", "system_health"),
            ("本周重点", "weekly_focus"),
        ]
