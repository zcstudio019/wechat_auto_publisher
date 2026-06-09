"""Read-only monthly board report for AI Runtime OS."""

from datetime import date


class AIRuntimeMonthlyBoardReportService:
    """Build a board-facing monthly Runtime OS report without actions."""

    @classmethod
    def build_monthly_board_report(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        status = cls._board_status(dashboard)
        trends = cls._monthly_trends(dashboard)
        governance = cls._governance_trends(dashboard)
        risks = cls._risk_trends(dashboard)
        ops = cls._ops_trends(dashboard)
        release = cls._release_trends(dashboard)
        achievements = cls._major_achievements(dashboard)
        threats = cls._strategic_threats(dashboard, risks, governance, release, ops)
        quarter_focus = cls._quarter_focus(status, threats, governance, ops, release)
        investments = cls._investment_priorities(status, threats, governance, ops, release)

        return {
            "board_status": status,
            "month_range": cls._month_range(),
            "headline": cls._headline(status, dashboard)[:80],
            "board_summary": cls._board_summary(status, threats, achievements, quarter_focus)[:200],
            "monthly_trends": trends,
            "governance_trends": governance[:10],
            "risk_trends": risks[:10],
            "ops_trends": ops[:10],
            "release_trends": release[:10],
            "major_achievements": achievements[:10],
            "strategic_threats": threats[:10],
            "quarter_focus": quarter_focus[:5],
            "investment_priorities": investments[:5],
            "recommended_actions": cls._recommended_actions(status, quarter_focus)[:8],
        }

    @classmethod
    def build_monthly_board_report_text(cls, report: dict | None = None) -> str:
        report = report or {}
        lines = [
            "【AI Runtime OS 月度董事会报告】",
            f"周期：{report.get('month_range') or ''}",
            f"状态：{report.get('board_status') or 'healthy'}",
            f"Headline：{report.get('headline') or ''}",
            f"摘要：{report.get('board_summary') or ''}",
            "",
            "月度趋势：",
        ]
        for key, value in (report.get("monthly_trends") or {}).items():
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
    def build_monthly_board_report_markdown(cls, report: dict | None = None) -> str:
        report = report or {}
        lines = [
            "# AI Runtime OS 月度董事会报告",
            "",
            f"- 周期：{report.get('month_range') or ''}",
            f"- 状态：{report.get('board_status') or 'healthy'}",
            f"- Headline：{report.get('headline') or ''}",
            f"- 摘要：{report.get('board_summary') or ''}",
            "",
            "## 月度趋势",
        ]
        for key, value in (report.get("monthly_trends") or {}).items():
            lines.append(f"- {key}: {value}")
        lines.append("")
        for label, key in cls._sections():
            lines.append(f"## {label}")
            items = report.get(key) or []
            if items:
                for item in items:
                    row = cls._row_item(item)
                    lines.append(f"- `{row.get('title')}` {row.get('status')} / {row.get('risk')}: {row.get('suggestion')}")
            else:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_monthly_board_report_rows(cls, report: dict | None = None) -> list[dict]:
        rows = []
        for label, key in cls._sections():
            for item in (report or {}).get(key) or []:
                row = cls._row_item(item)
                rows.append({
                    "分类": label,
                    "项目": row.get("title") or "",
                    "状态": row.get("status") or "",
                    "风险": row.get("risk") or "",
                    "建议": row.get("suggestion") or "",
                })
        return rows

    @staticmethod
    def _month_range() -> str:
        today = date.today()
        start = today.replace(day=1)
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        end = next_month.fromordinal(next_month.toordinal() - 1)
        return f"{start.isoformat()} ~ {end.isoformat()}"

    @classmethod
    def _board_status(cls, dashboard: dict) -> str:
        weekly = dashboard.get("ai_runtime_weekly_executive_report") or {}
        governance = dashboard.get("ai_runtime_governance_summary") or {}
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        capability = dashboard.get("ai_runtime_capability_governance") or {}
        delegation_risks = capability.get("delegation_risks") or []
        critical_delegation = any(cls._risk(item) in {"critical", "high"} for item in delegation_risks)
        if (
            weekly.get("report_status") == "critical"
            or governance.get("summary_status") == "critical"
            or release.get("release_status") == "blocked"
            or cls._first_status(ops, "ops_status", "health_status") in {"critical", "failed", "risky"}
            or bool(capability.get("forbidden_capabilities"))
            or critical_delegation
        ):
            return "critical"
        export_ops = dashboard.get("ai_dashboard_export_operations_center") or {}
        if (
            weekly.get("report_status") == "attention"
            or governance.get("summary_status") == "attention"
            or release.get("release_status") == "conditional"
            or cls._first_status(ops, "ops_status", "health_status") == "warning"
            or cls._first_status(export_ops, "operations_status", "operation_status") in {"warning", "attention", "failed"}
        ):
            return "attention"
        return "healthy"

    @staticmethod
    def _headline(status: str, dashboard: dict) -> str:
        governance = dashboard.get("ai_runtime_governance_summary") or {}
        capability = dashboard.get("ai_runtime_capability_governance") or {}
        if status == "critical":
            return "本月治理风险有所上升，下季度应优先治理自动化边界。"
        if governance.get("summary_status") == "attention" or capability.get("approval_required_capabilities"):
            return "本月 Runtime OS 存在治理关注项，下季度应继续收紧能力边界。"
        return "本月 Runtime OS 保持稳定运行，治理能力持续提升。"

    @classmethod
    def _board_summary(cls, status: str, threats: list[dict], achievements: list[dict], quarter_focus: list[dict]) -> str:
        risk = threats[0].get("title") if threats else "暂无系统性风险"
        achievement = achievements[0].get("title") if achievements else "Runtime OS 分层治理持续运行"
        focus = quarter_focus[0].get("title") if quarter_focus else "保持治理、运维与上线体系巡检"
        return f"本月整体状态为 {status}；最大风险是 {risk}；最大成果是 {achievement}；下季度重点是 {focus}。本报告仅用于董事会只读决策参考。"

    @classmethod
    def _monthly_trends(cls, dashboard: dict) -> dict:
        weekly = dashboard.get("ai_runtime_weekly_executive_report") or {}
        weekly_health = weekly.get("weekly_health") or {}
        governance = dashboard.get("ai_runtime_governance_summary") or {}
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        capability = dashboard.get("ai_runtime_capability_governance") or {}
        return {
            "runtime": weekly.get("report_status") or weekly_health.get("runtime") or "healthy",
            "governance": governance.get("summary_status") or weekly_health.get("governance") or "stable",
            "ops": cls._first_status(ops, "ops_status", "health_status") or weekly_health.get("ops") or "healthy",
            "release": release.get("release_status") or weekly_health.get("release") or "ready",
            "capability": capability.get("governance_status") or weekly_health.get("capability") or "stable",
        }

    @classmethod
    def _governance_trends(cls, dashboard: dict) -> list[dict]:
        items = []
        governance = dashboard.get("ai_runtime_governance_summary") or {}
        items.extend(cls._entries(governance.get("high_risk_capabilities"), "Governance Summary", "治理高风险能力需要董事会关注。"))
        items.extend(cls._entries(governance.get("delegation_risks"), "Governance Summary", "委托风险需要收敛。"))
        compiler = dashboard.get("ai_runtime_policy_compiler") or {}
        items.extend(cls._entries(compiler.get("policy_conflicts") or compiler.get("warning_policies"), "Policy Compiler", "策略冲突需要管理层复核。"))
        linter = dashboard.get("ai_runtime_policy_linter") or {}
        items.extend(cls._entries(linter.get("critical_issues") or linter.get("warning_issues"), "Policy Linter", "策略静态检查结果需要跟进。"))
        capability = dashboard.get("ai_runtime_capability_governance") or {}
        items.extend(cls._entries(capability.get("delegation_risks") or capability.get("approval_required_capabilities"), "Capability Governance", "能力治理需要保持人工审批。"))
        return cls._dedupe(items)

    @classmethod
    def _risk_trends(cls, dashboard: dict) -> list[dict]:
        items = []
        weekly = dashboard.get("ai_runtime_weekly_executive_report") or {}
        items.extend(cls._entries(weekly.get("top_risks"), "Weekly Executive Report", "周度风险进入月度董事会观察。"))
        governance = dashboard.get("ai_runtime_governance_summary") or {}
        items.extend(cls._entries(governance.get("delegation_risks"), "Governance Summary", "委托风险可能扩大为长期风险。"))
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        items.extend(cls._entries(release.get("blocking_checks") or release.get("must_fix_before_release"), "Release Readiness", "上线阻塞风险。"))
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        items.extend(cls._entries(ops.get("risk_items") or ops.get("ops_risks"), "Ops Health", "运维风险。"))
        capability = dashboard.get("ai_runtime_capability_governance") or {}
        items.extend(cls._entries(capability.get("forbidden_capabilities") or capability.get("delegation_risks"), "Capability Governance", "能力治理风险。"))
        return cls._dedupe(items)

    @classmethod
    def _ops_trends(cls, dashboard: dict) -> list[dict]:
        items = []
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        items.extend(cls._entries(ops.get("warning_items") or ops.get("risk_items"), "Ops Health", "运维健康趋势。"))
        export_ops = dashboard.get("ai_dashboard_export_operations_center") or {}
        items.extend(cls._entries(export_ops.get("warnings") or export_ops.get("failed_items") or export_ops.get("recommended_actions"), "Export Operations", "导出运营趋势。"))
        maintenance = dashboard.get("ai_dashboard_ops_maintenance_center") or {}
        items.extend(cls._entries(maintenance.get("today_tasks") or maintenance.get("recommended_actions"), "Maintenance Plan", "维护计划趋势。"))
        return cls._dedupe(items)

    @classmethod
    def _release_trends(cls, dashboard: dict) -> list[dict]:
        items = []
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        items.extend(cls._entries(release.get("blocking_checks") or release.get("warning_checks") or release.get("passed_checks"), "Release Readiness", "上线准备趋势。"))
        package = dashboard.get("ai_dashboard_release_package_center") or {}
        items.extend(cls._entries(package.get("package_items") or package.get("recommended_actions"), "Release Package", "发布包趋势。"))
        runbook = dashboard.get("ai_dashboard_release_runbook_center") or {}
        items.extend(cls._entries(runbook.get("runbook_steps") or runbook.get("recommended_actions"), "Release Runbook", "发布手册趋势。"))
        return cls._dedupe(items)

    @classmethod
    def _major_achievements(cls, dashboard: dict) -> list[dict]:
        items = []
        weekly = dashboard.get("ai_runtime_weekly_executive_report") or {}
        items.extend(cls._entries(weekly.get("wins_this_week"), "Weekly Executive Report", "周度成果沉淀为月度成果。"))
        ops = dashboard.get("ai_dashboard_ops_health_center") or {}
        if cls._first_status(ops, "ops_status", "health_status") in {"healthy", "normal", "ok"}:
            items.append(cls._static("运维健康保持稳定", "healthy", "low", "Ops Health", "继续保持巡检节奏。"))
        release = dashboard.get("ai_dashboard_release_readiness_center") or {}
        if release.get("release_status") == "ready":
            items.append(cls._static("上线准备度保持 ready", "ready", "low", "Release Readiness", "继续保留上线前人工复核。"))
        linter = dashboard.get("ai_runtime_policy_linter") or {}
        if linter.get("linter_status") == "clean":
            items.append(cls._static("策略静态检查 clean", "clean", "low", "Policy Linter", "保持策略矩阵质量。"))
        export_ops = dashboard.get("ai_dashboard_export_operations_center") or {}
        if cls._first_status(export_ops, "operations_status", "operation_status") in {"normal", "healthy", "ok", "completed"}:
            items.append(cls._static("导出运营保持正常", "completed", "low", "Export Operations", "保持人工归档。"))
        return cls._dedupe(items)[:10]

    @classmethod
    def _strategic_threats(cls, dashboard: dict, risks: list[dict], governance: list[dict], release: list[dict], ops: list[dict]) -> list[dict]:
        items = []
        items.extend([item for item in risks if cls._risk(item) in {"critical", "high", "blocked", "forbidden"}])
        items.extend([item for item in governance if cls._risk(item) in {"critical", "high", "blocked", "forbidden"}])
        items.extend([item for item in release if cls._risk(item) in {"critical", "high", "blocked", "forbidden"}])
        items.extend([item for item in ops if cls._risk(item) in {"critical", "high", "failed", "risky"}])
        capability = dashboard.get("ai_runtime_capability_governance") or {}
        items.extend(cls._entries(capability.get("forbidden_capabilities"), "Capability Governance", "禁止能力不能开放。"))
        items.extend(cls._entries(capability.get("delegation_risks"), "Capability Governance", "高委托风险需要收敛。"))
        strategy = dashboard.get("ai_runtime_strategy_center") or {}
        items.extend(cls._entries(strategy.get("technical_debt_risks"), "Strategy Center", "长期技术债风险。"))
        return cls._dedupe(items)[:10]

    @classmethod
    def _quarter_focus(cls, status: str, threats: list[dict], governance: list[dict], ops: list[dict], release: list[dict]) -> list[dict]:
        focus = []
        if threats or governance or status == "critical":
            focus.append(cls._static("治理风险收敛", "high", "high", "Governance", "下季度优先收敛 forbidden、高委托与策略冲突。"))
        if ops:
            focus.append(cls._static("运维稳定性建设", "high", "medium", "Ops Health", "提升 Ops Health、维护计划和导出巡检质量。"))
        if release:
            focus.append(cls._static("上线体系成熟化", "high", "medium", "Release Readiness", "强化上线准备、发布包和发布手册。"))
        focus.append(cls._static("能力治理边界", "high", "medium", "Capability Governance", "持续明确人工审批、只读能力和禁止能力边界。"))
        focus.append(cls._static("导出归档体系", "medium", "low", "Export Operations", "稳定输出董事会、周报和每日简报归档。"))
        if status == "healthy":
            focus.insert(0, cls._static("保持 Runtime OS 稳态运营", "medium", "low", "Runtime OS", "维持月报、周报、日报三级治理节奏。"))
        return cls._dedupe(focus)[:5]

    @staticmethod
    def _investment_priorities(status: str, threats: list[dict], governance: list[dict], ops: list[dict], release: list[dict]) -> list[dict]:
        priorities = [
            {"title": "治理能力", "status": "P0" if threats or governance else "P1", "risk": "high" if threats else "medium", "source": "Board Report", "suggestion": "投入策略编译、静态检查和能力治理。"},
            {"title": "运维稳定性", "status": "P1" if ops else "P2", "risk": "medium", "source": "Board Report", "suggestion": "投入 Ops Health、维护计划和监控质量。"},
            {"title": "上线体系", "status": "P1" if release else "P2", "risk": "medium", "source": "Board Report", "suggestion": "投入 Release Readiness、Runbook 与 Package。"},
            {"title": "能力治理", "status": "P1", "risk": "medium", "source": "Board Report", "suggestion": "投入角色建议、审批边界和 forbidden 能力收敛。"},
            {"title": "导出归档体系", "status": "P2", "risk": "low", "source": "Board Report", "suggestion": "投入月报、周报、日报导出与人工归档流程。"},
        ]
        if status == "critical":
            priorities[0]["status"] = "P0"
        return priorities[:5]

    @staticmethod
    def _recommended_actions(status: str, quarter_focus: list[dict]) -> list[str]:
        actions = ["导出月度董事会报告。", "保留月报、周报、日报三级只读报告链路。"]
        if status == "critical":
            actions.insert(0, "董事会优先复核 critical strategic_threats。")
        elif status == "attention":
            actions.insert(0, "管理层下季度跟进 attention 治理和运维风险。")
        else:
            actions.insert(0, "保持 Runtime OS 稳态运营。")
        if quarter_focus:
            actions.append(f"下季度首要重点：{quarter_focus[0].get('title')}。")
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
                "risk": cls._risk(item) or cls._status(item) or "medium",
                "source": source,
                "suggestion": item.get("suggestion") or item.get("recommendation") or item.get("reason") or item.get("summary") or suggestion,
            }
        return {"title": str(item or ""), "status": "attention", "risk": "medium", "source": source, "suggestion": suggestion}

    @staticmethod
    def _static(title: str, status: str, risk: str, source: str, suggestion: str) -> dict:
        return {"title": title, "status": status, "risk": risk, "source": source, "suggestion": suggestion}

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
            or item.get("summary")
            or item
        )

    @staticmethod
    def _status(item: object) -> str:
        if isinstance(item, dict):
            return str(item.get("status") or item.get("priority") or item.get("maturity") or "")
        return ""

    @staticmethod
    def _risk(item: object) -> str:
        if isinstance(item, dict):
            return str(item.get("risk_level") or item.get("risk") or item.get("severity") or item.get("priority") or item.get("status") or "")
        return ""

    @staticmethod
    def _row_item(item: object) -> dict:
        if isinstance(item, dict):
            return {
                "title": item.get("title") or item.get("summary") or "",
                "status": item.get("status") or item.get("priority") or "",
                "risk": item.get("risk") or item.get("risk_level") or item.get("severity") or "",
                "suggestion": item.get("suggestion") or item.get("summary") or item.get("reason") or "",
            }
        return {"title": str(item or ""), "status": "", "risk": "", "suggestion": str(item or "")}

    @staticmethod
    def _format_item(item: object) -> str:
        row = AIRuntimeMonthlyBoardReportService._row_item(item)
        return f"- {row.get('title')} / {row.get('status')} / {row.get('risk')} / {row.get('suggestion')}"

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
            ("Governance Trends", "governance_trends"),
            ("Risk Trends", "risk_trends"),
            ("Ops Trends", "ops_trends"),
            ("Release Trends", "release_trends"),
            ("Major Achievements", "major_achievements"),
            ("Strategic Threats", "strategic_threats"),
            ("Quarter Focus", "quarter_focus"),
            ("Investment Priorities", "investment_priorities"),
        ]
