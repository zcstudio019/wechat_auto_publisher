"""Read-only Runtime OS command layer recommendations."""

from services.ai_runtime_command_registry import get_runtime_command_registry


class AIRuntimeCommandLayerService:
    """Build suggested Runtime commands without executing anything."""

    @classmethod
    def build_command_layer(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        commands = {command["command_key"]: command for command in get_runtime_command_registry()}
        recommended = cls._recommended_commands(dashboard, commands)
        high_priority = [
            command for command in recommended
            if command.get("risk_level") in {"high", "critical"}
        ]
        human_review = [
            command for command in recommended
            if command.get("human_required")
        ]
        blocked = cls._blocked_from_automation(recommended)
        categories = cls._command_categories(commands.values())
        status = cls._status(high_priority, blocked)

        return {
            "command_layer_status": status,
            "summary": cls._summary(status, recommended, human_review),
            "recommended_commands": recommended,
            "high_priority_commands": high_priority,
            "human_review_commands": human_review,
            "blocked_commands": blocked,
            "command_categories": categories,
            "recommended_actions": cls._recommended_actions(status),
        }

    @classmethod
    def build_command_layer_text(cls, command_layer: dict | None = None) -> str:
        command_layer = command_layer or {}
        lines = [
            "【AI Runtime 命令层】",
            f"状态：{command_layer.get('command_layer_status') or 'normal'}",
            f"摘要：{command_layer.get('summary') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"{label}：")
            commands = command_layer.get(key) or []
            if commands:
                for command in commands:
                    lines.append(
                        f"- {command.get('title')} / {command.get('category')} / "
                        f"{command.get('risk_level')} / {command.get('recommended_route')}"
                    )
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_command_layer_markdown(cls, command_layer: dict | None = None) -> str:
        command_layer = command_layer or {}
        lines = [
            "# AI Runtime 命令层",
            "",
            f"- 状态：{command_layer.get('command_layer_status') or 'normal'}",
            f"- 摘要：{command_layer.get('summary') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"## {label}")
            commands = command_layer.get(key) or []
            if commands:
                for command in commands:
                    lines.append(
                        f"- `{command.get('command_key')}` {command.get('title')} / "
                        f"{command.get('risk_level')} / {command.get('recommended_route')}"
                    )
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @staticmethod
    def build_command_layer_rows(command_layer: dict | None = None) -> list[dict]:
        rows = []
        seen = set()
        for key in [
            "recommended_commands",
            "high_priority_commands",
            "human_review_commands",
            "blocked_commands",
        ]:
            for command in (command_layer or {}).get(key) or []:
                command_key = command.get("command_key")
                row_key = (key, command_key)
                if row_key in seen:
                    continue
                seen.add(row_key)
                rows.append({
                    "命令": command.get("title") or "",
                    "分类": command.get("category") or "",
                    "风险": command.get("risk_level") or "",
                    "HumanReview": str(bool(command.get("human_required"))),
                    "Route": command.get("recommended_route") or "",
                    "摘要": command.get("description") or "",
                })
        return rows

    @classmethod
    def _recommended_commands(cls, dashboard: dict, commands: dict[str, dict]) -> list[dict]:
        selected = []
        entry_router = dashboard.get("ai_runtime_entry_router") or {}
        primary_entry = entry_router.get("primary_entry") or {}
        practical = dashboard.get("ai_runtime_practical_console") or {}
        mission = dashboard.get("ai_runtime_mission_control_center") or {}
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        export_ops = dashboard.get("ai_dashboard_export_operations_center") or {}
        immune = dashboard.get("ai_runtime_immune_center") or {}
        integrity = dashboard.get("ai_runtime_integrity_center") or {}
        judgment = dashboard.get("ai_runtime_judgment_center") or {}

        cls._append_by_route(selected, commands, primary_entry.get("route"))
        if not selected:
            cls._append(selected, commands, "COMMAND_OPEN_HOME")

        if practical.get("console_status") == "urgent":
            cls._append(selected, commands, "COMMAND_OPEN_PRACTICAL_CONSOLE")
        if mission.get("mission_status") == "critical":
            cls._append(selected, commands, "COMMAND_OPEN_MISSION_CONTROL")
        if ops.get("ops_status") in {"warning", "critical", "risky"}:
            cls._append(selected, commands, "COMMAND_OPEN_OPS_HEALTH")
            cls._append(selected, commands, "COMMAND_RUN_SMOKE_TEST_CHECKLIST")
        if release.get("release_status") == "blocked":
            cls._append(selected, commands, "COMMAND_OPEN_RELEASE_READINESS")
            cls._append(selected, commands, "COMMAND_VIEW_RELEASE_RUNBOOK")
            cls._append(selected, commands, "COMMAND_VIEW_RELEASE_PACKAGE")
        if export_ops.get("operations_status") in {"warning", "critical", "attention"}:
            cls._append(selected, commands, "COMMAND_OPEN_EXPORT_OPERATIONS")
            cls._append(selected, commands, "COMMAND_EXPORT_RUNTIME_REPORTS")
        if immune.get("immune_status") == "critical" or immune.get("immune_alerts"):
            cls._append(selected, commands, "COMMAND_REVIEW_IMMUNE_ALERT")
        if integrity.get("integrity_status") == "critical" or int(integrity.get("integrity_score") or 100) < 50:
            cls._append(selected, commands, "COMMAND_REVIEW_INTEGRITY_RISK")
        if judgment.get("judgment_status") == "critical" or judgment.get("dangerous_automations"):
            cls._append(selected, commands, "COMMAND_REVIEW_HIGH_RISK_AUTOMATION")
        if judgment.get("governance_violations") or judgment.get("unacceptable_risks"):
            cls._append(selected, commands, "COMMAND_REVIEW_GOVERNANCE_CONFLICT")

        cls._append(selected, commands, "COMMAND_OPEN_RUNTIME_ARCHIVE")
        return cls._dedupe(selected)[:12]

    @staticmethod
    def _append(selected: list[dict], commands: dict[str, dict], command_key: str) -> None:
        command = commands.get(command_key)
        if command:
            selected.append(dict(command))

    @classmethod
    def _append_by_route(cls, selected: list[dict], commands: dict[str, dict], route: str | None) -> None:
        if not route:
            return
        for command in commands.values():
            if command.get("recommended_route") == route:
                selected.append(dict(command))
                return
        if route == "/ai-dashboard":
            cls._append(selected, commands, "COMMAND_OPEN_PRACTICAL_CONSOLE")

    @staticmethod
    def _blocked_from_automation(commands: list[dict]) -> list[dict]:
        return [
            dict(command)
            for command in commands
            if command.get("human_required") or command.get("risk_level") in {"high", "critical"}
        ]

    @staticmethod
    def _command_categories(commands) -> list[dict]:
        counts = {}
        for command in commands:
            category = command.get("category") or "other"
            counts[category] = counts.get(category, 0) + 1
        return [
            {"category": category, "count": count}
            for category, count in sorted(counts.items())
        ]

    @staticmethod
    def _status(high_priority: list[dict], blocked: list[dict]) -> str:
        if any(command.get("risk_level") == "critical" for command in high_priority):
            return "urgent"
        if high_priority or blocked:
            return "attention"
        return "normal"

    @staticmethod
    def _summary(status: str, recommended: list[dict], human_review: list[dict]) -> str:
        if status == "urgent":
            return f"命令层建议 {len(recommended)} 条只读命令，其中 {len(human_review)} 条需要人工复核。"
        if status == "attention":
            return f"命令层存在关注命令，建议人工查看 {len(recommended)} 条入口。"
        return "命令层当前建议从常规入口查看 Runtime OS。"

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        if status == "urgent":
            return [
                "只展示命令建议，不自动执行任何命令。",
                "优先人工复核 high_priority_commands 和 human_review_commands。",
            ]
        return [
            "按 recommended_commands 查看建议入口。",
            "保持命令层只读，不触发自动化动作。",
        ]

    @staticmethod
    def _dedupe(commands: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for command in commands:
            command_key = command.get("command_key")
            if command_key in seen:
                continue
            seen.add(command_key)
            result.append(command)
        return result

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("推荐命令", "recommended_commands"),
            ("高优先级命令", "high_priority_commands"),
            ("人工复核命令", "human_review_commands"),
            ("禁止自动化命令", "blocked_commands"),
        ]
