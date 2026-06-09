"""Read-only Runtime OS policy linter."""

from services.ai_runtime_policy_compiler_service import AIRuntimePolicyCompilerService


class AIRuntimePolicyLinterService:
    """Statically inspect compiled runtime policies without mutating them."""

    @classmethod
    def build_policy_linter(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        compiler = dashboard.get("ai_runtime_policy_compiler") or AIRuntimePolicyCompilerService.build_policy_compiler(dashboard)
        policies = compiler.get("compiled_policies") or []
        matrix = compiler.get("policy_matrix") or []

        lint_issues = []
        duplicate_policies = cls._find_duplicate_policies(policies)
        invalid_matrix_rows = cls._find_invalid_matrix_rows(matrix)
        conflicting_policies = cls._find_conflicting_policies(matrix)
        missing_source_policies = []
        human_review_gaps = []

        for policy in policies:
            lint_issues.extend(cls._inspect_policy(policy))
            if not policy.get("source"):
                missing_source_policies.append(cls._issue("missing_source", "critical", policy, "补充策略来源。"))
            if cls._needs_human_review(policy):
                human_review_gaps.append(cls._issue("human_review_gap", "critical", policy, "高风险或阻断策略必须要求人工复核。"))

        lint_issues.extend(duplicate_policies)
        lint_issues.extend(invalid_matrix_rows)
        lint_issues.extend(conflicting_policies)
        lint_issues.extend(missing_source_policies)
        lint_issues.extend(human_review_gaps)

        critical_issues = [issue for issue in lint_issues if issue.get("severity") == "critical"]
        warning_issues = [issue for issue in lint_issues if issue.get("severity") == "warning"]
        linter_status = cls._status(critical_issues, warning_issues, duplicate_policies, invalid_matrix_rows)

        return {
            "linter_status": linter_status,
            "summary": cls._summary(linter_status, lint_issues),
            "lint_issues": lint_issues,
            "critical_issues": critical_issues,
            "warning_issues": warning_issues,
            "duplicate_policies": duplicate_policies,
            "conflicting_policies": conflicting_policies,
            "missing_source_policies": missing_source_policies,
            "invalid_matrix_rows": invalid_matrix_rows,
            "human_review_gaps": human_review_gaps,
            "recommended_actions": cls._recommended_actions(linter_status),
        }

    @classmethod
    def build_policy_linter_text(cls, linter: dict | None = None) -> str:
        linter = linter or {}
        lines = [
            "【AI Runtime 策略静态检查器】",
            f"状态：{linter.get('linter_status') or 'clean'}",
            f"摘要：{linter.get('summary') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"{label}：")
            issues = linter.get(key) or []
            for issue in issues[:12]:
                lines.append(cls._format_issue(issue))
            if not issues:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_policy_linter_markdown(cls, linter: dict | None = None) -> str:
        linter = linter or {}
        lines = [
            "# AI Runtime 策略静态检查器",
            "",
            f"- 状态：{linter.get('linter_status') or 'clean'}",
            f"- 摘要：{linter.get('summary') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"## {label}")
            issues = linter.get(key) or []
            for issue in issues[:12]:
                lines.append(cls._format_issue(issue))
            if not issues:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @staticmethod
    def build_policy_linter_rows(linter: dict | None = None) -> list[dict]:
        rows = []
        for issue in (linter or {}).get("lint_issues") or []:
            rows.append({
                "问题": issue.get("issue") or "",
                "类型": issue.get("issue_type") or "",
                "严重级别": issue.get("severity") or "",
                "Policy": issue.get("policy") or "",
                "建议": issue.get("recommendation") or "",
            })
        return rows

    @classmethod
    def _inspect_policy(cls, policy: dict) -> list[dict]:
        issues = []
        if not policy.get("policy_key"):
            issues.append(cls._issue("policy_key 为空", "critical", policy, "补充 policy_key。"))
        if not policy.get("source"):
            issues.append(cls._issue("source 为空", "critical", policy, "补充 source。"))
        if not policy.get("risk_level"):
            issues.append(cls._issue("risk_level 为空", "warning", policy, "补充 risk_level。"))
        if policy.get("risk_level") in {"high", "critical"} and not policy.get("human_required"):
            issues.append(cls._issue("高风险策略缺少人工复核", "critical", policy, "设置 human_required=true。"))
        if policy.get("status") == "blocked" and not policy.get("summary"):
            issues.append(cls._issue("blocked policy 没有原因", "critical", policy, "补充阻断原因。"))
        if policy.get("human_required") and not policy.get("summary"):
            issues.append(cls._issue("human_only policy 缺少说明", "warning", policy, "补充人工复核说明。"))
        return issues

    @classmethod
    def _find_duplicate_policies(cls, policies: list[dict]) -> list[dict]:
        counts = {}
        samples = {}
        for policy in policies:
            key = policy.get("policy_key")
            if not key:
                continue
            counts[key] = counts.get(key, 0) + 1
            samples.setdefault(key, policy)
        return [
            cls._issue("同一个 policy_key 重复", "warning", samples[key], "合并或重命名重复策略。")
            for key, count in counts.items()
            if count > 1
        ]

    @classmethod
    def _find_invalid_matrix_rows(cls, matrix: list[dict]) -> list[dict]:
        issues = []
        for row in matrix:
            if row.get("Allowed") and row.get("Forbidden"):
                issues.append(cls._matrix_issue("Allowed 和 Forbidden 同时为 true", "critical", row, "拆分或修正矩阵布尔值。"))
            if row.get("Forbidden") and not row.get("HumanOnly"):
                issues.append(cls._matrix_issue("Forbidden 但 HumanOnly 为 false", "critical", row, "Forbidden 策略必须要求人工复核。"))
            if not row.get("Policy") or not row.get("Layer") or not row.get("RiskLevel"):
                issues.append(cls._matrix_issue("策略矩阵字段缺失", "critical", row, "补充 Policy、Layer、RiskLevel。"))
        return issues

    @classmethod
    def _find_conflicting_policies(cls, matrix: list[dict]) -> list[dict]:
        by_layer = {}
        for row in matrix:
            layer = row.get("Layer") or ""
            if not layer:
                continue
            by_layer.setdefault(layer, []).append(row)

        issues = []
        for layer, rows in by_layer.items():
            has_allowed = any(row.get("Allowed") for row in rows)
            has_forbidden = any(row.get("Forbidden") for row in rows)
            if has_allowed and has_forbidden:
                issue = cls._matrix_issue("同一 Layer 下策略冲突", "warning", rows[0], "人工复核同层 Allowed 与 Forbidden 策略。")
                issue["policy"] = layer
                issues.append(issue)
        return issues

    @staticmethod
    def _needs_human_review(policy: dict) -> bool:
        return (
            policy.get("risk_level") in {"high", "critical"} or policy.get("status") == "blocked"
        ) and not policy.get("human_required")

    @staticmethod
    def _status(critical: list[dict], warning: list[dict], duplicates: list[dict], invalid_rows: list[dict]) -> str:
        if critical or invalid_rows:
            return "critical"
        if warning or duplicates:
            return "warning"
        return "clean"

    @staticmethod
    def _summary(status: str, issues: list[dict]) -> str:
        if status == "critical":
            return f"策略静态检查发现 {len(issues)} 个问题，其中包含 critical 或无效矩阵行，需要人工复核。"
        if status == "warning":
            return f"策略静态检查发现 {len(issues)} 个警告，建议人工整理策略质量。"
        return "策略静态检查未发现明显质量问题。"

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        if status == "critical":
            return ["人工复核 critical_issues 与 invalid_matrix_rows。", "保持 Linter 只读，不修改策略、不阻断流程。"]
        if status == "warning":
            return ["人工检查 duplicate_policies、warning_issues 与 conflicting_policies。"]
        return ["保留当前策略矩阵，按需导出供人工审阅。"]

    @staticmethod
    def _issue(issue: str, severity: str, policy: dict, recommendation: str) -> dict:
        return {
            "issue": issue,
            "issue_type": "policy",
            "severity": severity,
            "policy": policy.get("policy_key") or "",
            "recommendation": recommendation,
            "summary": policy.get("summary") or "",
        }

    @staticmethod
    def _matrix_issue(issue: str, severity: str, row: dict, recommendation: str) -> dict:
        return {
            "issue": issue,
            "issue_type": "matrix",
            "severity": severity,
            "policy": row.get("Policy") or "",
            "recommendation": recommendation,
            "summary": f"Layer={row.get('Layer') or ''}; Source={row.get('Source') or ''}",
        }

    @staticmethod
    def _format_issue(issue: dict) -> str:
        return (
            f"- {issue.get('issue') or ''} / {issue.get('issue_type') or ''} / "
            f"{issue.get('severity') or ''} / {issue.get('policy') or ''} / "
            f"{issue.get('recommendation') or ''}"
        )

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("严重问题", "critical_issues"),
            ("警告问题", "warning_issues"),
            ("重复策略", "duplicate_policies"),
            ("冲突策略", "conflicting_policies"),
            ("人工复核缺口", "human_review_gaps"),
        ]
