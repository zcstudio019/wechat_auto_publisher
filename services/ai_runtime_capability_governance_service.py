"""Read-only Runtime OS capability governance service."""

from services.ai_runtime_capability_matrix_service import AIRuntimeCapabilityMatrixService


class AIRuntimeCapabilityGovernanceService:
    """Generate capability governance recommendations without enforcing them."""

    @classmethod
    def build_capability_governance(cls, dashboard: dict | None = None) -> dict:
        dashboard = dashboard or {}
        capability_matrix = dashboard.get("ai_runtime_capability_matrix") or AIRuntimeCapabilityMatrixService.build_capability_matrix(dashboard)
        capabilities = capability_matrix.get("capabilities") or []
        governed = [cls._governed_capability(item) for item in capabilities]
        human_only = [item for item in governed if item.get("human_only")]
        restricted = [item for item in governed if item.get("maturity") == "restricted"]
        forbidden = [item for item in governed if item.get("forbidden")]
        approval_required = [item for item in governed if item.get("approval_required")]
        role_recommendations = cls._role_recommendations(governed)
        delegation_risks = cls._delegation_risks(capabilities, governed)
        boundary_conflicts = cls._boundary_conflicts(capabilities, dashboard)
        governance_status = cls._status(forbidden, delegation_risks, boundary_conflicts)

        return {
            "governance_status": governance_status,
            "summary": cls._summary(governance_status, governed, delegation_risks),
            "governed_capabilities": governed,
            "human_only_capabilities": human_only,
            "restricted_capabilities": restricted,
            "forbidden_capabilities": forbidden,
            "role_recommendations": role_recommendations,
            "approval_required_capabilities": approval_required,
            "delegation_risks": delegation_risks,
            "capability_boundary_conflicts": boundary_conflicts,
            "recommended_actions": cls._recommended_actions(governance_status),
        }

    @classmethod
    def build_capability_governance_text(cls, governance: dict | None = None) -> str:
        governance = governance or {}
        lines = [
            "【AI Runtime OS 能力治理层】",
            f"状态：{governance.get('governance_status') or 'stable'}",
            f"摘要：{governance.get('summary') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"{label}：")
            items = governance.get(key) or []
            for item in items[:12]:
                lines.append(cls._format_item(item))
            if not items:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def build_capability_governance_markdown(cls, governance: dict | None = None) -> str:
        governance = governance or {}
        lines = [
            "# AI Runtime OS 能力治理层",
            "",
            f"- 状态：{governance.get('governance_status') or 'stable'}",
            f"- 摘要：{governance.get('summary') or ''}",
            "",
        ]
        for label, key in cls._sections():
            lines.append(f"## {label}")
            items = governance.get(key) or []
            for item in items[:12]:
                lines.append(cls._format_item(item))
            if not items:
                lines.append("- 暂无")
            lines.append("")
        return "\n".join(lines).rstrip()

    @staticmethod
    def build_capability_governance_rows(governance: dict | None = None) -> list[dict]:
        rows = []
        for item in (governance or {}).get("governed_capabilities") or []:
            rows.append({
                "Capability": item.get("title") or "",
                "Role": item.get("recommended_role") or "",
                "Risk": item.get("risk_level") or "",
                "Approval": str(bool(item.get("approval_required"))),
                "HumanOnly": str(bool(item.get("human_only"))),
                "Forbidden": str(bool(item.get("forbidden"))),
                "Summary": item.get("summary") or "",
            })
        return rows

    @classmethod
    def _governed_capability(cls, capability: dict) -> dict:
        risk = capability.get("risk_level") or "medium"
        maturity = capability.get("maturity") or "basic"
        human_only = bool(capability.get("human_required")) or maturity == "restricted"
        forbidden = maturity == "restricted" and not capability.get("automation_allowed")
        approval_required = human_only or forbidden or risk in {"high", "critical"}
        return {
            "capability_key": capability.get("capability_key") or "",
            "title": capability.get("title") or "",
            "category": capability.get("category") or "",
            "maturity": maturity,
            "risk_level": risk,
            "recommended_role": cls._recommended_role(capability, human_only, forbidden, approval_required),
            "approval_required": approval_required,
            "human_only": human_only,
            "forbidden": forbidden,
            "summary": capability.get("summary") or "",
        }

    @staticmethod
    def _recommended_role(capability: dict, human_only: bool, forbidden: bool, approval_required: bool) -> str:
        risk = capability.get("risk_level") or "medium"
        maturity = capability.get("maturity") or "basic"
        readonly = bool(capability.get("readonly"))
        if forbidden or maturity == "restricted":
            return "governance/admin"
        if risk in {"high", "critical"} or approval_required:
            return "reviewer/governance"
        if readonly:
            return "observer/readonly"
        if maturity == "advanced":
            return "ops/admin"
        if human_only:
            return "reviewer/governance"
        return "ops"

    @staticmethod
    def _role_recommendations(governed: list[dict]) -> list[dict]:
        counts = {}
        for item in governed:
            role = item.get("recommended_role") or "readonly"
            counts[role] = counts.get(role, 0) + 1
        return [
            {"role": role, "count": count, "summary": f"{count} capabilities recommended for {role}."}
            for role, count in sorted(counts.items())
        ]

    @classmethod
    def _delegation_risks(cls, capabilities: list[dict], governed: list[dict]) -> list[dict]:
        risks = []
        governed_by_key = {item.get("capability_key"): item for item in governed}
        for capability in capabilities:
            governed_item = governed_by_key.get(capability.get("capability_key")) or {}
            title = capability.get("title") or capability.get("capability_key") or "Capability"
            if capability.get("risk_level") in {"high", "critical"} and capability.get("automation_allowed"):
                risks.append(cls._risk("HIGH_RISK_OPEN", title, "高风险能力被错误开放。"))
            if governed_item.get("human_only") and not governed_item.get("approval_required"):
                risks.append(cls._risk("HUMAN_ONLY_WITHOUT_APPROVAL", title, "HumanOnly 能力缺审批建议。"))
            if governed_item.get("forbidden") and capability.get("automation_allowed"):
                risks.append(cls._risk("FORBIDDEN_AUTOMATION_ALLOWED", title, "forbidden 能力存在 automation_allowed。"))
            if capability.get("maturity") == "experimental" and not governed_item.get("approval_required"):
                risks.append(cls._risk("EXPERIMENTAL_WITHOUT_GOVERNANCE", title, "experimental 能力缺人工治理。"))
            if capability.get("maturity") == "advanced" and "Governance" not in str(capability.get("category")) and not governed_item.get("approval_required"):
                risks.append(cls._risk("ADVANCED_WITHOUT_GOVERNANCE_SUPPORT", title, "advanced 能力缺 governance support。"))
        return cls._dedupe_risks(risks)

    @classmethod
    def _boundary_conflicts(cls, capabilities: list[dict], dashboard: dict) -> list[dict]:
        conflicts = []
        boundary = dashboard.get("ai_runtime_boundary_center") or {}
        judgment = dashboard.get("ai_runtime_judgment_center") or {}
        has_boundary_risk = bool(boundary.get("boundary_violations") or boundary.get("forbidden_actions") or judgment.get("dangerous_automations"))
        if not has_boundary_risk:
            return conflicts
        for capability in capabilities:
            if capability.get("automation_allowed") and capability.get("risk_level") in {"high", "critical"}:
                conflicts.append({
                    "conflict_key": f"BOUNDARY_CAPABILITY_{capability.get('capability_key')}",
                    "capability": capability.get("title") or "",
                    "risk_level": capability.get("risk_level") or "",
                    "summary": "能力边界存在高风险自动化冲突，需要人工治理复核。",
                })
        return conflicts

    @staticmethod
    def _risk(risk_key: str, capability: str, summary: str) -> dict:
        return {
            "risk_key": risk_key,
            "capability": capability,
            "risk_level": "critical" if "FORBIDDEN" in risk_key or "HIGH_RISK" in risk_key else "warning",
            "summary": summary,
        }

    @staticmethod
    def _status(forbidden: list[dict], risks: list[dict], conflicts: list[dict]) -> str:
        if forbidden or any(item.get("risk_level") == "critical" for item in risks) or conflicts:
            return "critical"
        if risks:
            return "warning"
        return "stable"

    @staticmethod
    def _summary(status: str, governed: list[dict], risks: list[dict]) -> str:
        if status == "critical":
            return f"能力治理层分析 {len(governed)} 项能力，发现禁止能力或 critical 委托风险，需要人工复核。"
        if status == "warning":
            return f"能力治理层分析 {len(governed)} 项能力，发现 {len(risks)} 项委托风险。"
        return f"能力治理层分析 {len(governed)} 项能力，当前治理建议稳定。"

    @staticmethod
    def _recommended_actions(status: str) -> list[str]:
        if status == "critical":
            return ["人工复核 forbidden_capabilities、approval_required_capabilities 与 delegation_risks。", "保持能力治理层只读，不新增真实权限或阻断。"]
        if status == "warning":
            return ["检查 delegation_risks 与 role_recommendations。"]
        return ["按需导出能力治理矩阵供人工评审。"]

    @staticmethod
    def _format_item(item: dict) -> str:
        title = item.get("title") or item.get("capability") or item.get("role") or item.get("risk_key") or item.get("capability_key") or ""
        role = item.get("recommended_role") or item.get("role") or ""
        risk = item.get("risk_level") or ""
        summary = item.get("summary") or ""
        return f"- {title} / {role} / {risk} / {summary}"

    @staticmethod
    def _sections() -> list[tuple[str, str]]:
        return [
            ("治理能力", "governed_capabilities"),
            ("人工能力", "human_only_capabilities"),
            ("受限能力", "restricted_capabilities"),
            ("禁止能力", "forbidden_capabilities"),
            ("需审批能力", "approval_required_capabilities"),
            ("委托风险", "delegation_risks"),
        ]

    @staticmethod
    def _dedupe_risks(risks: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for risk in risks:
            key = (risk.get("risk_key"), risk.get("capability"))
            if key in seen:
                continue
            seen.add(key)
            result.append(risk)
        return result
