"""Read-only Runtime intervention planning from causal graph output."""


class AIRuntimeInterventionPlanner:
    """Generate human intervention plans without executing any intervention."""

    NEVER_AUTO_INTERVENTIONS = [
        "自动发布",
        "自动审核",
        "自动改文章",
        "自动改 Prompt",
        "自动改模板",
        "自动改配置",
        "自动删除文件",
        "自动关闭事故",
    ]

    MANUAL_REVIEW_TARGETS = [
        "release",
        "publish",
        "approval",
        "governance",
        "boundary",
        "constitution",
        "prompt/template/content mutation",
    ]

    PRE_CHECKS = [
        "Smoke Test",
        "Ops Health",
        "Event Timeline",
        "Signal Intelligence",
        "Causal Graph",
        "Release Readiness",
    ]

    POST_CHECKS = [
        "Smoke Test 是否恢复",
        "Ops Health 是否恢复",
        "critical event 是否减少",
        "Release Readiness 是否非 blocked",
        "Timeline 是否改善",
    ]

    INTERVENTION_SEQUENCE = [
        "1. 先处理根因",
        "2. 再处理阻断链路",
        "3. 再验证症状是否恢复",
        "4. 最后更新 SOP/知识库建议",
    ]

    def plan(self, causal_graph: dict, dashboard: dict | None = None) -> dict:
        causal_graph = causal_graph or {}
        root_causes = causal_graph.get("root_causes") or []
        symptoms = causal_graph.get("symptoms") or []
        critical_paths = causal_graph.get("critical_paths") or []

        root_cause_interventions = [
            self._root_cause_intervention(item)
            for item in root_causes
        ]
        symptom_interventions = [
            self._symptom_intervention(item)
            for item in symptoms
        ]
        blocking_interventions = [
            self._blocking_intervention(item)
            for item in critical_paths
        ]
        manual_review_interventions = self._manual_review_interventions(dashboard or {})
        never_auto_interventions = self._never_auto_interventions()

        interventions = (
            root_cause_interventions
            + symptom_interventions
            + blocking_interventions
            + manual_review_interventions
            + never_auto_interventions
        )

        return {
            "interventions": interventions,
            "root_cause_interventions": root_cause_interventions,
            "symptom_interventions": symptom_interventions,
            "blocking_interventions": blocking_interventions,
            "manual_review_interventions": manual_review_interventions,
            "never_auto_interventions": never_auto_interventions,
            "intervention_sequence": list(self.INTERVENTION_SEQUENCE),
            "pre_checks": list(self.PRE_CHECKS),
            "post_checks": list(self.POST_CHECKS),
            "intervention_summary": self._summary(
                root_cause_interventions,
                symptom_interventions,
                blocking_interventions,
                manual_review_interventions,
            ),
            "recommended_actions": self._recommended_actions(root_cause_interventions, blocking_interventions),
        }

    def _root_cause_intervention(self, item: dict) -> dict:
        target = item.get("node_id") or item.get("target") or "unknown"
        priority = self._priority(item)
        templates = {
            "JSON_CORRUPTED": (
                "人工检查 JSON 写入来源",
                "建议先备份相关 JSON，再人工检查写入来源、格式和最近变更。",
                "降低 Runtime 配置/状态读取异常继续传播的概率。",
                "json",
            ),
            "EXPORT_FAILED": (
                "人工检查导出链路",
                "建议人工检查导出目录、权限和报表生成逻辑。",
                "降低导出失败继续影响运维和发布判断的概率。",
                "export",
            ),
            "SMOKE_TEST_FAILED": (
                "人工修复冒烟测试失败项",
                "建议先定位冒烟测试失败项，再判断是否影响发布推进。",
                "阻断测试失败向 Ops 和 Release 继续升级。",
                "ops",
            ),
            "TRUST_DECREASED": (
                "人工复核信任与边界风险",
                "建议人工复核 Governance、Boundary、Constitution 与 Policy Gate 状态。",
                "降低治理风险误扩散到发布或审核流程的概率。",
                "governance",
            ),
        }
        title, reason, expected_effect, intervention_type = templates.get(
            target,
            (
                "人工复核根因节点",
                f"建议人工复核 {target} 的上游来源和下游影响。",
                "降低根因继续传播的概率。",
                "root_cause",
            ),
        )
        return self._intervention(title, target, intervention_type, priority, reason, expected_effect)

    def _symptom_intervention(self, item: dict) -> dict:
        target = item.get("node_id") or "unknown"
        priority = "high" if item.get("severity") == "critical" else "medium"
        if target == "RELEASE_BLOCKED":
            reason = "Release blocked 更可能是下游症状，不建议直接处理 release，应先回溯根因。"
            expected_effect = "避免绕过根因导致重复阻塞。"
            intervention_type = "release"
        elif target in {"OPS_WARNING", "OPS_CRITICAL"}:
            reason = "Ops 症状需要先检查上游 JSON、export、smoke-test。"
            expected_effect = "帮助确认 Ops 是否随上游修复而恢复。"
            intervention_type = "ops"
        else:
            reason = f"{target} 更像下游症状，建议先追踪根因再处理表象。"
            expected_effect = "避免只处理症状而遗漏传播源。"
            intervention_type = "symptom"
        return self._intervention("人工复核症状节点", target, intervention_type, priority, reason, expected_effect)

    def _blocking_intervention(self, item: dict) -> dict:
        path = item.get("path") or []
        target = " -> ".join(path) if path else "critical_path"
        priority = "critical" if item.get("severity") == "critical" else "high"
        reason = "关键因果链存在传播风险；仅建议人工暂停推进判断，并检查链路源头。"
        expected_effect = "阻断风险从根因继续传播到 Ops、Release 或 Governance。"
        return self._intervention("人工阻断风险传播链", target, "blocking", priority, reason, expected_effect)

    def _manual_review_interventions(self, dashboard: dict) -> list[dict]:
        interventions = []
        for target in self.MANUAL_REVIEW_TARGETS:
            interventions.append(self._intervention(
                "必须人工复核",
                target,
                self._manual_type(target),
                "high" if target in {"release", "publish", "approval"} else "medium",
                f"{target} 涉及高风险边界，禁止自动处理。",
                "确保所有高风险决策保留人工确认。",
            ))
        return interventions

    def _never_auto_interventions(self) -> list[dict]:
        return [
            self._intervention(
                title,
                title,
                "governance",
                "critical",
                f"{title} 属于永不自动处理项。",
                "保持 Runtime 干预层只读规划，不触发执行。",
            )
            for title in self.NEVER_AUTO_INTERVENTIONS
        ]

    @staticmethod
    def _intervention(
        title: str,
        target: str,
        intervention_type: str,
        priority: str,
        reason: str,
        expected_effect: str,
    ) -> dict:
        return {
            "title": title,
            "target": target,
            "intervention_type": intervention_type,
            "priority": priority,
            "automation_allowed": False,
            "manual_required": True,
            "reason": reason,
            "expected_effect": expected_effect,
        }

    @staticmethod
    def _manual_type(target: str) -> str:
        if target == "release":
            return "release"
        if target in {"governance", "boundary", "constitution", "prompt/template/content mutation"}:
            return "governance"
        return "observation"

    @staticmethod
    def _priority(item: dict) -> str:
        if item.get("severity") == "critical" or item.get("confidence") == "high":
            return "critical"
        if item.get("confidence") == "medium":
            return "high"
        return "medium"

    @staticmethod
    def _summary(root_causes: list, symptoms: list, blocking: list, manual: list) -> str:
        if root_causes or blocking:
            return (
                f"Generated {len(root_causes)} root cause intervention(s), "
                f"{len(symptoms)} symptom intervention(s), and {len(blocking)} blocking intervention(s)."
            )
        return f"Generated baseline manual review guardrails with {len(manual)} manual review item(s)."

    @staticmethod
    def _recommended_actions(root_causes: list, blocking: list) -> list[str]:
        actions = []
        if root_causes:
            actions.append("先人工复核根因干预建议，不执行自动修复。")
        if blocking:
            actions.append("按关键链路进行人工阻断评估，不自动冻结或恢复。")
        actions.append("所有发布、审核、内容、Prompt、模板和配置变更均需人工确认。")
        return actions
