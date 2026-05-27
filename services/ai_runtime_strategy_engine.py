"""Read-only Runtime strategy analysis engine."""


class AIRuntimeStrategyEngine:
    """Build long-range Runtime strategy without executing any action."""

    def build_strategy(
        self,
        simulation_center,
        decision_center,
        intervention_center,
        trust_center,
        confidence_center,
        mission_control_center,
    ) -> dict:
        simulation_center = simulation_center or {}
        decision_center = decision_center or {}
        intervention_center = intervention_center or {}
        trust_center = trust_center or {}
        confidence_center = confidence_center or {}
        mission_control_center = mission_control_center or {}

        short_term = self._short_term_strategies(simulation_center, intervention_center)
        mid_term = self._mid_term_strategies(simulation_center, decision_center)
        long_term = self._long_term_strategies(trust_center, confidence_center, mission_control_center)
        stability = self._stability_roadmap(simulation_center, decision_center)
        automation = self._automation_roadmap()
        governance = self._governance_roadmap(trust_center, confidence_center, decision_center)
        technical_debt = self._technical_debt_risks(simulation_center, decision_center, intervention_center)
        priorities = self._capability_priorities(simulation_center, decision_center, trust_center, confidence_center)
        status = self._status(technical_debt, stability, governance)

        return {
            "strategy_status": status,
            "short_term_strategies": short_term,
            "mid_term_strategies": mid_term,
            "long_term_strategies": long_term,
            "stability_roadmap": stability,
            "automation_roadmap": automation,
            "governance_roadmap": governance,
            "technical_debt_risks": technical_debt,
            "capability_priorities": priorities,
            "strategy_summary": self._summary(short_term, mid_term, long_term, technical_debt),
            "recommended_actions": self._recommended_actions(status, technical_debt),
        }

    def _short_term_strategies(self, simulation: dict, intervention: dict) -> list[dict]:
        strategies = []
        targets = " ".join(
            str(item.get("target") or item.get("title") or "")
            for item in (intervention.get("root_cause_interventions") or [])
        )
        if "JSON" in targets:
            strategies.append(self._strategy(
                "修复 JSON instability",
                "short_term",
                "critical",
                "JSON coupling",
                "未来 1~3 天优先人工检查 JSON 写入、备份和读取稳定性。",
            ))
        if simulation.get("risk_propagation_forecasts"):
            strategies.append(self._strategy(
                "优先恢复 Smoke Test 与 Ops Health",
                "short_term",
                "critical",
                "risk propagation",
                "先压低风险传播链，再评估 release readiness。",
            ))
        if simulation.get("worst_case_scenarios"):
            strategies.append(self._strategy(
                "暂缓 Release 推进",
                "short_term",
                "high",
                "release blocked",
                "在 worst-case 未解除前，仅保留人工 release 评估。",
            ))
        if not strategies:
            strategies.append(self._strategy(
                "保持 Runtime 观察窗口",
                "short_term",
                "medium",
                "baseline",
                "未来 1~3 天持续观察事件、信号和模拟结果。",
            ))
        return strategies

    def _mid_term_strategies(self, simulation: dict, decision: dict) -> list[dict]:
        strategies = [
            self._strategy(
                "Runtime Event 标准化",
                "mid_term",
                "high",
                "event consistency",
                "未来 1~2 周统一事件命名、层级和恢复事件语义。",
            ),
            self._strategy(
                "Signal 去噪",
                "mid_term",
                "high" if decision.get("high_risk_decisions") else "medium",
                "signal quality",
                "减少重复 warning、false escalation 和噪声信号。",
            ),
            self._strategy(
                "Correlation 优化",
                "mid_term",
                "medium",
                "false correlation",
                "优化共现、因果候选和影响链判定。",
            ),
        ]
        if simulation.get("rollback_impacts"):
            strategies.append(self._strategy(
                "Export isolation",
                "mid_term",
                "medium",
                "export bottleneck",
                "将导出链路和 Runtime 诊断展示进一步隔离。",
            ))
        return strategies

    def _long_term_strategies(self, trust: dict, confidence: dict, mission: dict) -> list[dict]:
        trust_level = self._first_value(trust, ["trust_status", "trust_level", "status"]) or "medium"
        confidence_level = self._first_value(confidence, ["confidence_status", "confidence_level", "status"]) or "medium"
        return [
            self._strategy(
                "Runtime OS 分层稳定化",
                "long_term",
                "critical",
                "runtime high coupling",
                "未来 1~3 月持续压缩跨层耦合，固化只读 Runtime 层边界。",
            ),
            self._strategy(
                "Governance runtime abstraction",
                "long_term",
                "high",
                f"trust={trust_level}, confidence={confidence_level}",
                "将 Boundary、Constitution、Trust、Confidence 形成统一治理抽象。",
            ),
            self._strategy(
                "Autonomous simulation framework",
                "long_term",
                "medium",
                "simulation maturity",
                "只推进观察、报表、导出级自动化推演框架，不开放审核发布自动化。",
            ),
            self._strategy(
                "Risk propagation containment",
                "long_term",
                "high",
                "risk propagation",
                "建立风险传播收缩策略，减少单点异常扩散到 Release/Governance。",
            ),
        ]

    def _stability_roadmap(self, simulation: dict, decision: dict) -> list[dict]:
        degraded = bool(simulation.get("worst_case_scenarios") or decision.get("blocked_decisions"))
        return [
            self._roadmap("L1", "恢复 Runtime 基础稳定", "critical" if degraded else "high", "先恢复 Event/Smoke/Ops 基础可观测稳定。"),
            self._roadmap("L2", "降低 Event Storm", "high", "降低重复事件、critical 聚集和恢复波动。"),
            self._roadmap("L3", "降低 false correlation", "medium", "提高相关性与因果判断的人工可解释性。"),
            self._roadmap("L4", "提高 Trust/Confidence", "high", "增强 Trust、Confidence 与 Policy Gate 的一致性。"),
        ]

    def _automation_roadmap(self) -> list[dict]:
        return [
            self._roadmap("A1", "observation automation", "medium", "允许观察、汇总、报表自动化。"),
            self._roadmap("A2", "export automation", "medium", "仅限导出与报告生成自动化，不触发业务动作。"),
            self._roadmap("A3", "reporting automation", "medium", "允许只读运营报告自动化。"),
            self._roadmap("A-ban", "publish/approval automation forbidden", "critical", "禁止 publish automation 与 approval automation。"),
        ]

    def _governance_roadmap(self, trust: dict, confidence: dict, decision: dict) -> list[dict]:
        priority = "critical" if decision.get("blocked_decisions") else "high"
        return [
            self._roadmap("G1", "boundary strengthening", priority, "持续强化 Boundary 检查与人工复核边界。"),
            self._roadmap("G2", "constitution refinement", "high", "沉淀 Constitution 冲突、例外和人工升级标准。"),
            self._roadmap("G3", "policy gate standardization", "high", "统一 Policy Gate 阻断、观察和人工 only 的判断语义。"),
            self._roadmap("G4", "manual review hardening", "critical", "发布、审核、治理、内容、Prompt、模板保持人工确认。"),
        ]

    def _technical_debt_risks(self, simulation: dict, decision: dict, intervention: dict) -> list[dict]:
        risks = []
        root_targets = " ".join(str(item.get("target") or "") for item in intervention.get("root_cause_interventions") or [])
        if "JSON" in root_targets or simulation.get("risk_propagation_forecasts"):
            risks.append(self._risk("JSON coupling", "critical", "JSON 异常可沿 Smoke/Ops/Release 传播。"))
        if decision.get("high_risk_decisions") or simulation.get("worst_case_scenarios"):
            risks.append(self._risk("Runtime high coupling", "critical", "高风险决策或最坏情形显示 Runtime 仍存在跨层耦合。"))
        risks.append(self._risk("fragile modules", "high", "因果图与模拟推演中出现脆弱节点时需持续收缩依赖。"))
        risks.append(self._risk("export bottlenecks", "medium", "导出链路仍可能成为诊断与发布判断瓶颈。"))
        risks.append(self._risk("excessive dashboard dependency", "medium", "Dashboard 聚合较重，需保持只读并逐步分层。"))
        return risks

    def _capability_priorities(self, simulation: dict, decision: dict, trust: dict, confidence: dict) -> list[dict]:
        return [
            self._priority("stability", "critical", "先稳定 Event、Smoke、Ops、Release readiness 的只读诊断链。"),
            self._priority("governance", "critical", "保持 Boundary/Constitution/Policy Gate 的人工边界。"),
            self._priority("signal quality", "high", "提升信号去噪、重复问题识别和恢复失败识别。"),
            self._priority("causal accuracy", "high", "提高根因、症状、传播链和脆弱节点解释质量。"),
            self._priority("export optimization", "medium", "优化导出隔离与报表稳定性。"),
        ]

    @staticmethod
    def _strategy(title: str, strategy_type: str, priority: str, risk: str, summary: str) -> dict:
        return {
            "title": title,
            "type": strategy_type,
            "priority": priority,
            "risk": risk,
            "summary": summary,
        }

    @staticmethod
    def _roadmap(stage: str, title: str, priority: str, summary: str) -> dict:
        return {
            "stage": stage,
            "title": title,
            "priority": priority,
            "summary": summary,
        }

    @staticmethod
    def _risk(title: str, severity: str, summary: str) -> dict:
        return {
            "title": title,
            "severity": severity,
            "summary": summary,
        }

    @staticmethod
    def _priority(capability: str, priority: str, summary: str) -> dict:
        return {
            "capability": capability,
            "priority": priority,
            "summary": summary,
        }

    @staticmethod
    def _status(technical_debt: list[dict], stability: list[dict], governance: list[dict]) -> str:
        critical_debt = any(item.get("severity") == "critical" for item in technical_debt)
        missing_governance = not governance
        degraded_stability = any(
            item.get("stage") == "L1" and item.get("priority") == "critical"
            for item in stability
        )
        if critical_debt or missing_governance or degraded_stability:
            return "critical"
        if technical_debt:
            return "attention"
        return "stable"

    @staticmethod
    def _summary(short_term: list, mid_term: list, long_term: list, risks: list) -> str:
        return (
            f"Generated {len(short_term)} short-term, {len(mid_term)} mid-term, "
            f"{len(long_term)} long-term strategy item(s), with {len(risks)} technical debt risk(s)."
        )

    @staticmethod
    def _recommended_actions(status: str, risks: list[dict]) -> list[str]:
        actions = ["Keep Runtime strategy analysis read-only; do not trigger automatic execution."]
        if status == "critical":
            actions.append("Prioritize stability and governance strategy review before expanding automation.")
        if risks:
            actions.append("Use technical debt risks to guide manual roadmap planning.")
        return actions

    @staticmethod
    def _first_value(source: dict, keys: list[str]) -> str:
        for key in keys:
            value = source.get(key)
            if value is not None:
                return str(value).lower()
        if isinstance(source.get("global_trust"), dict):
            for key in keys:
                value = source["global_trust"].get(key)
                if value is not None:
                    return str(value).lower()
        return ""
