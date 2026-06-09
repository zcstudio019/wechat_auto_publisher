"""Read-only weekly executive report for AI Runtime OS."""

from datetime import date, timedelta


class AIRuntimeWeeklyExecutiveReportService:
    """Build a weekly management-facing Runtime OS report without actions."""

    @classmethod
    def build_weekly_executive_report(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        status = cls._report_status(dashboard)
        health = cls._weekly_health(dashboard)
        top_risks = cls._top_risks(dashboard)
        governance = cls._governance_review(dashboard)
        ops = cls._ops_review(dashboard)
        release = cls._release_review(dashboard)
        export = cls._export_review(dashboard)
        capability = cls._capability_review(dashboard)
        wins = cls._wins_this_week(dashboard)
        priorities = cls._next_week_priorities(status, top_risks, governance, ops, release, capability)

        return {
            "report_status": status,
            "week_range": cls._week_range(),
            "headline": cls._headline(status, dashboard)[:80],
            "executive_summary": cls._executive_summary(status, top_risks, health, priorities)[:150],
            "weekly_health": health,
            "top_risks": top_risks[:8],
            "governance_review": governance[:8],
            "ops_review": ops[:8],
            "release_review": release[:8],
            "export_review": export[:8],
            "capability_review": capability[:8],
            "wins_this_week": wins[:8],
            "next_week_priorities": priorities[:5],
            "recommended_actions": cls._recommended_actions(status, priorities)[:8],
        }

    @classmethod
    def build_weekly_executive_report_text(cls, report: dict | None = None) -> str:
        report = report or {}
        lines = [
            "【AI Runtime OS 每周高管报告】",
            f"周期：{report.get('week_range') or ''}",
            f"状态：{report.get('report_status') or 'stable'}",
            f"Headline：{report.get('headline') or ''}",
            f"摘要：{report.get('executive_summary') or ''}",
            "",
        ]
        lines.append("健康概览：")
        for key, value in (report.get("weekly_health") or {}).items():
            lines.append(f"- {key}: {value}")
        lines.append("")
        for label, key in cls._sections():
            lines.append(f"{label}：")
            items = report.get(key) or []
            if items:
                for item in items:
                    lines.append(cls._format_item(item))
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_weekly_executive_report_markdown(cls, report: dict | None = None) -> str:
        report = report or {}
        lines = [
            "# AI Runtime OS 每周高管报告",
            "",
            f"- 周期：{report.get('week_range') or ''}",
            f"- 状态：{report.get('report_status') or 'stable'}",
            f"- Headline：{report.get('headline') or ''}",
            f"- 摘要：{report.get('executive_summary') or ''}",
            "",
            "## 健康概览",
        ]
        for key, value in (report.get("weekly_health") or {}).items():
            lines.append(f"- {key}: {value}")
        lines.append("")
        for label, key in cls._sections():
            lines.append(f"## {label}")
            items = report.get(key) or []
            if items:
                for item in items:
                    row = cls._row_item(item)
                    lines.append(f"- `{row.get('title')}` {row.get('status')} / {row.get('source')}: {row.get('suggestion')}")
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_weekly_executive_report_rows(cls, report: dict | None = None) -> list[dict]:
        rows = []
        for label, key in cls._sections():
            for item in (report or {}).get(key) or []:
                row = cls._row_item(item)
                rows.append({
                    "分类": label,
                    "事项": row.get("title") or "",
                    "状态": row.get("status") or "",
                    "来源": row.get("source") or "",
                    "建议": row.get("suggestion") or "",
                })
        return rows

    @staticmethod
    def _week_range() -> str:
        today = date.today()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return f"{start.isoformat()} ~ {end.isoformat()}"

    @classmethod
    def _report_status(cls, dashboard: dict) -> str:
        daily = dashboard.get("ai_runtime_daily_operator_brief") or {}
        governance = dashboard.get("ai_runtime_governance_summary") or {}
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        linter = dashboard.get("ai_runtime_policy_linter") or {}
        capability_governance = dashboard.get("ai_runtime_capability_governance") or {}
        export_ops = dashboard.get("ai_dashboard_export_operations_center") or {}

        delegation_risks = capability_governance.get("delegation_risks") or []
        critical_delegation = any(cls._status(item) in {"critical", "high"} for item in delegation_risks)
        if (
            daily.get("brief_status") == "urgent"
            or governance.get("summary_status") == "critical"
            or release.get("release_status") == "blocked"
            or cls._first_status(ops, "ops_status", "health_status") in {"critical", "failed", "risky"}
            or linter.get("linter_status") == "critical"
            or bool(capability_governance.get("forbidden_capabilities"))
            or critical_delegation
        ):
            return "critical"
        if (
            daily.get("brief_status") == "attention"
            or governance.get("summary_status") == "attention"
            or release.get("release_status") == "conditional"
            or cls._first_status(ops, "ops_status", "health_status") == "warning"
            or cls._first_status(export_ops, "operations_status", "operation_status") in {"warning", "attention", "failed"}
            or linter.get("linter_status") == "warning"
        ):
            return "attention"
        return "stable"

    @staticmethod
    def _headline(status: str, dashboard: dict) -> str:
        governance = dashboard.get("ai_runtime_governance_summary") or {}
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        capability = dashboard.get("ai_runtime_capability_governance") or {}
        if release.get("release_status") == "blocked" or governance.get("summary_status") == "critical":
            return "本周存在上线阻塞与治理风险，下周应优先修复。"
        if capability.get("approval_required_capabilities") or capability.get("delegation_risks"):
            return "本周高风险能力与人工复核事项较多，建议收紧自动化边界。"
        if status == "attention":
            return "本周 Runtime OS 存在关注项，建议下周优先治理与运维复核。"
        return "本周 Runtime OS 整体稳定，治理与运维风险可控。"

    @classmethod
    def _executive_summary(cls, status: str, risks: list[dict], health: dict, priorities: list[dict]) -> str:
        max_risk = risks[0].get("title") if risks else "暂无明显风险"
        governance = health.get("governance") or "stable"
        priority = priorities[0].get("title") if priorities else "保持常规巡检"
        return f"本周总体状态为 {status}；最大风险是 {max_risk}；治理状态为 {governance}；下周重点是 {priority}。"

    @classmethod
    def _weekly_health(cls, dashboard: dict) -> dict:
        daily = dashboard.get("ai_runtime_daily_operator_brief") or {}
        one_page = dashboard.get("ai_runtime_one_page_console") or {}
        practical = dashboard.get("ai_runtime_practical_console") or {}
        governance = dashboard.get("ai_runtime_governance_summary") or {}
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        export_ops = dashboard.get("ai_dashboard_export_operations_center") or {}
        linter = dashboard.get("ai_runtime_policy_linter") or {}
        capability = dashboard.get("ai_runtime_capability_governance") or {}
        runtime = daily.get("brief_status") or one_page.get("console_status") or practical.get("console_status") or "normal"
        return {
            "runtime": runtime,
            "governance": governance.get("summary_status") or linter.get("linter_status") or "stable",
            "ops": cls._first_status(ops, "ops_status", "health_status") or "healthy",
            "release": release.get("release_status") or "ready",
            "export": cls._first_status(export_ops, "operations_status", "operation_status") or "normal",
            "capability": capability.get("governance_status") or "stable",
        }

    @classmethod
    def _top_risks(cls, dashboard: dict) -> list[dict]:
        items = []
        daily = dashboard.get("ai_runtime_daily_operator_brief") or {}
        items.extend(cls._entries(daily.get("governance_risks_today"), "Daily Operator Brief", "governance risk"))
        governance = dashboard.get("ai_runtime_governance_summary") or {}
        items.extend(cls._entries(governance.get("delegation_risks"), "Governance Summary", "delegation risk"))
        linter = dashboard.get("ai_runtime_policy_linter") or {}
        items.extend(cls._entries(linter.get("critical_issues"), "Policy Linter", "critical policy issue"))
        items.extend(cls._entries(linter.get("warning_issues"), "Policy Linter", "warning policy issue"))
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        items.extend(cls._entries(ops.get("risk_items") or ops.get("ops_risks"), "Ops Health", "ops risk"))
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        items.extend(cls._entries(release.get("blocking_checks") or release.get("must_fix_before_release"), "Release Readiness", "release blocker"))
        capability = dashboard.get("ai_runtime_capability_governance") or {}
        items.extend(cls._entries(capability.get("delegation_risks"), "Capability Governance", "capability risk"))
        return cls._dedupe(items)

    @classmethod
    def _governance_review(cls, dashboard: dict) -> list[dict]:
        items = []
        governance = dashboard.get("ai_runtime_governance_summary") or {}
        items.extend(cls._entries(governance.get("high_risk_capabilities"), "Governance Summary", "high risk capability"))
        items.extend(cls._entries(governance.get("human_only_capabilities"), "Governance Summary", "human-only capability"))
        compiler = dashboard.get("ai_runtime_policy_compiler") or {}
        items.extend(cls._entries(compiler.get("policy_conflicts") or compiler.get("warning_policies"), "Policy Compiler", "policy review"))
        linter = dashboard.get("ai_runtime_policy_linter") or {}
        items.extend(cls._entries(linter.get("critical_issues") or linter.get("warning_issues"), "Policy Linter", "policy lint"))
        capability = dashboard.get("ai_runtime_capability_governance") or {}
        items.extend(cls._entries(capability.get("delegation_risks"), "Capability Governance", "delegation review"))
        judgment = dashboard.get("ai_runtime_judgment_center") or {}
        items.extend(cls._entries(judgment.get("governance_violations") or judgment.get("unacceptable_risks"), "Judgment Center", "judgment review"))
        court = dashboard.get("ai_runtime_governance_court_center") or {}
        items.extend(cls._entries(court.get("constitutional_conflicts") or court.get("court_rulings"), "Governance Court", "court review"))
        return cls._dedupe(items)

    @classmethod
    def _ops_review(cls, dashboard: dict) -> list[dict]:
        items = []
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        items.extend(cls._entries(ops.get("risk_items") or ops.get("warning_items"), "Ops Health", "ops health review"))
        export_ops = dashboard.get("ai_dashboard_export_operations_center") or {}
        items.extend(cls._entries(export_ops.get("warnings") or export_ops.get("failed_items"), "Export Operations", "export ops review"))
        smoke = dashboard.get("ai_dashboard_smoke_test_center") or {}
        items.extend(cls._entries(smoke.get("failed_checks") or smoke.get("warning_checks"), "Smoke Test", "smoke test review"))
        maintenance = dashboard.get("ai_dashboard_ops_maintenance_center") or {}
        items.extend(cls._entries(maintenance.get("today_tasks") or maintenance.get("recommended_actions"), "Maintenance Plan", "maintenance review"))
        return cls._dedupe(items)

    @classmethod
    def _release_review(cls, dashboard: dict) -> list[dict]:
        items = []
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        items.extend(cls._entries(release.get("blocking_checks") or release.get("warning_checks") or release.get("passed_checks"), "Release Readiness", "release readiness"))
        package = dashboard.get("ai_dashboard_release_package_center") or {}
        items.extend(cls._entries(package.get("package_items") or package.get("recommended_actions"), "Release Package", "release package"))
        runbook = dashboard.get("ai_dashboard_release_runbook_center") or {}
        items.extend(cls._entries(runbook.get("runbook_steps") or runbook.get("recommended_actions"), "Release Runbook", "release runbook"))
        return cls._dedupe(items)

    @classmethod
    def _export_review(cls, dashboard: dict) -> list[dict]:
        items = []
        export_ops = dashboard.get("ai_dashboard_export_operations_center") or {}
        items.extend(cls._entries(export_ops.get("failed_items") or export_ops.get("warnings") or export_ops.get("recommended_actions"), "Export Operations", "export operations"))
        export_schedule_status = export_ops.get("schedule_status") or export_ops.get("export_schedule_status") or {}
        if export_schedule_status:
            items.append(cls._entry(export_schedule_status, "Export Schedule", "export schedule"))
        automation = dashboard.get("ai_dashboard_export_automation_center") or {}
        items.extend(cls._entries(automation.get("warnings") or automation.get("recommended_actions"), "Export Automation", "export automation"))
        return cls._dedupe(items)

    @classmethod
    def _capability_review(cls, dashboard: dict) -> list[dict]:
        items = []
        matrix = dashboard.get("ai_runtime_capability_matrix") or {}
        items.extend(cls._entries(matrix.get("unstable_capabilities") or matrix.get("forbidden_capabilities") or matrix.get("capability_gaps"), "Capability Matrix", "capability matrix"))
        governance = dashboard.get("ai_runtime_capability_governance") or {}
        items.extend(cls._entries(governance.get("approval_required_capabilities") or governance.get("delegation_risks"), "Capability Governance", "capability governance"))
        command = dashboard.get("ai_runtime_command_layer") or {}
        items.extend(cls._entries(command.get("high_priority_commands") or command.get("human_review_commands"), "Command Layer", "command review"))
        return cls._dedupe(items)

    @classmethod
    def _wins_this_week(cls, dashboard: dict) -> list[dict]:
        wins = []
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        linter = dashboard.get("ai_runtime_policy_linter") or {}
        export_ops = dashboard.get("ai_dashboard_export_operations_center") or {}
        if cls._first_status(ops, "ops_status", "health_status") in {"healthy", "normal", "ok"}:
            wins.append(cls._static("Ops Health 健康", "healthy", "Ops Health", "继续保持运维观察。"))
        if release.get("release_status") == "ready":
            wins.append(cls._static("Release Readiness ready", "ready", "Release Readiness", "上线准备度保持可用。"))
        if linter.get("linter_status") == "clean":
            wins.append(cls._static("Policy Linter clean", "clean", "Policy Linter", "策略静态检查无明显问题。"))
        if cls._first_status(export_ops, "operations_status", "operation_status") in {"normal", "healthy", "ok", "completed"}:
            wins.append(cls._static("Export Operations 正常", "normal", "Export Operations", "导出运营保持正常。"))
        for item in release.get("passed_checks") or []:
            wins.append(cls._entry(item, "Release Readiness", "passed check"))
        return wins[:8]

    @classmethod
    def _next_week_priorities(cls, status: str, risks: list[dict], governance: list[dict], ops: list[dict], release: list[dict], capability: list[dict]) -> list[dict]:
        priorities = []
        if governance or status == "critical":
            priorities.append(cls._static("收敛治理风险", "high", "Governance", "优先复核策略冲突、人工复核与 forbidden 能力。"))
        if ops:
            priorities.append(cls._static("复核运维风险", "high", "Ops Health", "复查 Ops Health、Smoke Test 与维护计划。"))
        if release:
            priorities.append(cls._static("推进上线准备", "high", "Release Readiness", "处理 blocking/warning checks。"))
        if capability:
            priorities.append(cls._static("收紧能力治理", "high", "Capability Governance", "检查高风险能力、审批要求与委托边界。"))
        priorities.append(cls._static("整理导出归档", "medium", "Export Operations", "导出周报、治理汇总与运维报告，保持人工归档。"))
        if not risks and status == "stable":
            priorities.insert(0, cls._static("保持常规巡检", "medium", "Runtime OS", "维持每日简报、运维健康和上线准备度观察。"))
        return cls._dedupe(priorities)[:5]

    @staticmethod
    def _recommended_actions(status: str, priorities: list[dict]) -> list[str]:
        actions = ["导出每周高管报告。", "下周先看 Daily Operator Brief 与 Governance Summary。"]
        if status == "critical":
            actions.insert(0, "优先处理 critical top_risks。")
        elif status == "attention":
            actions.insert(0, "跟进 attention 风险并保持人工复核。")
        else:
            actions.insert(0, "保持稳定巡检节奏。")
        if priorities:
            actions.append(f"首要优先级：{priorities[0].get('title')}。")
        return actions[:8]

    @classmethod
    def _entries(cls, items: object, source: str, suggestion: str) -> list[dict]:
        if not isinstance(items, list):
            return []
        return [cls._entry(item, source, suggestion) for item in items]

    @classmethod
    def _entry(cls, item: object, source: str, suggestion: str) -> dict:
        if isinstance(item, dict):
            return {
                "title": cls._title(item),
                "status": cls._status(item) or "attention",
                "source": source,
                "suggestion": item.get("suggestion") or item.get("recommendation") or item.get("reason") or item.get("summary") or suggestion,
            }
        return {
            "title": str(item or ""),
            "status": "attention",
            "source": source,
            "suggestion": suggestion,
        }

    @staticmethod
    def _static(title: str, status: str, source: str, suggestion: str) -> dict:
        return {"title": title, "status": status, "source": source, "suggestion": suggestion}

    @staticmethod
    def _first_status(data: dict, *keys: str) -> str:
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
            or item.get("issue")
            or item.get("policy")
            or item.get("command_key")
            or item.get("summary")
            or item
        )

    @staticmethod
    def _status(item: object) -> str:
        if isinstance(item, dict):
            return str(item.get("status") or item.get("risk_level") or item.get("severity") or item.get("priority") or item.get("risk") or "")
        return ""

    @staticmethod
    def _row_item(item: object) -> dict:
        if isinstance(item, dict):
            return {
                "title": item.get("title") or item.get("summary") or "",
                "status": item.get("status") or item.get("risk_level") or item.get("severity") or item.get("priority") or "",
                "source": item.get("source") or "",
                "suggestion": item.get("suggestion") or item.get("summary") or item.get("reason") or "",
            }
        return {"title": str(item or ""), "status": "", "source": "", "suggestion": str(item or "")}

    @staticmethod
    def _format_item(item: object) -> str:
        row = AIRuntimeWeeklyExecutiveReportService._row_item(item)
        return f"- {row.get('title')} / {row.get('status')} / {row.get('source')} / {row.get('suggestion')}"

    @staticmethod
    def _dedupe(items: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for item in items:
            key = (item.get("title"), item.get("source"))
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("Top Risks", "top_risks"),
            ("Governance Review", "governance_review"),
            ("Ops Review", "ops_review"),
            ("Release Review", "release_review"),
            ("Export Review", "export_review"),
            ("Capability Review", "capability_review"),
            ("Wins This Week", "wins_this_week"),
            ("Next Week Priorities", "next_week_priorities"),
        ]
