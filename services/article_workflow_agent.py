"""
文章 AI 工作流总控 Agent。

负责串联审核、优化、发布前终检和运营决策，生成只读运营报告。
不自动审核、不自动发布、不自动修改文章、不创建发布任务。
"""
from __future__ import annotations

from typing import Any

from services.article_decision_agent import ArticleDecisionAgent
from services.article_preflight_agent import ArticlePreflightAgent
from services.article_review_agent import ArticleReviewAgent
from services.article_rewrite_agent import ArticleRewriteAgent
from services.publish_task_service import PublishTaskService


class ArticleWorkflowAgent:
    """文章 AI 工作流总控 Agent。"""

    RISK_ORDER = {"low": 0, "medium": 1, "high": 2}

    def run_workflow(self, article: dict[str, Any]) -> dict[str, Any]:
        """运行文章运营工作流，返回完整只读报告。"""
        if not article:
            return self._failed_result("文章不存在，无法执行 AI 工作流分析")

        warnings: list[str] = []
        review_result = self._safe_step(
            "AI 审核建议",
            lambda: ArticleReviewAgent().review_article(article),
            warnings,
        )
        rewrite_result = self._safe_step(
            "AI 一键优化草稿",
            lambda: ArticleRewriteAgent().rewrite_article(article, review_result),
            warnings,
        )
        preflight_result = self._safe_step(
            "AI 发布前终检",
            lambda: ArticlePreflightAgent().preflight_article(article),
            warnings,
        )

        article_id = self._safe_int(article.get("id"))
        latest_publish_task = None
        if article_id:
            try:
                task = PublishTaskService.get_latest_task_for_article(article_id)
                latest_publish_task = dict(task) if task else None
            except Exception as exc:
                warnings.append(f"读取最近发布任务失败：{exc}")

        decision_result = self._safe_step(
            "AI 运营决策建议",
            lambda: ArticleDecisionAgent().decide_next_action(
                article,
                review_result=review_result if isinstance(review_result, dict) else None,
                preflight_result=preflight_result if isinstance(preflight_result, dict) else None,
                latest_publish_task=latest_publish_task,
            ),
            warnings,
        )

        step_results = [review_result, rewrite_result, preflight_result, decision_result]
        success_count = sum(1 for item in step_results if isinstance(item, dict) and item.get("ok"))
        workflow_status = self._workflow_status(success_count, len(step_results))
        overall_risk = self._overall_risk(review_result, preflight_result, decision_result)
        blocking_issues = self._collect_blocking_issues(review_result, preflight_result, decision_result)
        recommended_actions = self._recommended_actions(
            article,
            review_result,
            preflight_result,
            decision_result,
            blocking_issues,
        )
        summary = self._summary(workflow_status, overall_risk, decision_result, blocking_issues)

        if workflow_status == "failed":
            summary = "AI 工作流核心步骤均未成功，请检查 OpenAI 配置或稍后重试。"

        return {
            "ok": workflow_status != "failed",
            "workflow_status": workflow_status,
            "overall_risk": overall_risk,
            "review_result": review_result or {},
            "rewrite_result": rewrite_result or {},
            "preflight_result": preflight_result or {},
            "decision_result": decision_result or {},
            "summary": summary,
            "recommended_actions": recommended_actions,
            "blocking_issues": self._unique(blocking_issues),
            "warnings": self._unique(warnings + self._collect_warnings(review_result, preflight_result, decision_result)),
            "raw_response": "",
        }

    def _safe_step(self, step_name: str, func, warnings: list[str]) -> dict[str, Any]:
        """安全执行单个 Agent，避免一个步骤失败拖垮整条工作流。"""
        try:
            result = func()
            if not isinstance(result, dict):
                warnings.append(f"{step_name}返回格式异常")
                return {"ok": False, "msg": f"{step_name}返回格式异常"}
            if not result.get("ok"):
                warnings.append(result.get("msg") or f"{step_name}未完成")
            return result
        except Exception as exc:
            warnings.append(f"{step_name}执行失败：{exc}")
            return {"ok": False, "msg": f"{step_name}执行失败：{exc}"}

    def _workflow_status(self, success_count: int, total_count: int) -> str:
        """根据成功步骤数量判断工作流状态。"""
        if success_count == total_count:
            return "completed"
        if success_count == 0:
            return "failed"
        return "partial"

    def _overall_risk(
        self,
        review_result: dict[str, Any],
        preflight_result: dict[str, Any],
        decision_result: dict[str, Any],
    ) -> str:
        """聚合 Review / Preflight / Decision 的最高风险。"""
        risk_values = [
            self._risk_value((review_result or {}).get("risk_level")),
            self._risk_value((preflight_result or {}).get("risk_level")),
            self._priority_value((decision_result or {}).get("priority")),
        ]
        max_risk = max(risk_values)
        if max_risk >= 2:
            return "high"
        if max_risk == 1:
            return "medium"
        return "low"

    def _collect_blocking_issues(
        self,
        review_result: dict[str, Any],
        preflight_result: dict[str, Any],
        decision_result: dict[str, Any],
    ) -> list[str]:
        """聚合阻断问题。"""
        issues: list[str] = []
        if self._safe_text((review_result or {}).get("risk_level")).lower() == "high":
            issues.extend(self._ensure_list((review_result or {}).get("issues")))
        issues.extend(self._ensure_list((preflight_result or {}).get("blocking_issues")))
        if self._safe_text((decision_result or {}).get("priority")).lower() == "high":
            issues.extend(self._ensure_list((decision_result or {}).get("warnings")))
        return self._unique(issues)

    def _collect_warnings(
        self,
        review_result: dict[str, Any],
        preflight_result: dict[str, Any],
        decision_result: dict[str, Any],
    ) -> list[str]:
        """聚合普通风险提醒。"""
        warnings: list[str] = []
        warnings.extend(self._ensure_list((review_result or {}).get("suggestions")))
        warnings.extend(self._ensure_list((preflight_result or {}).get("warnings")))
        warnings.extend(self._ensure_list((decision_result or {}).get("warnings")))
        return self._unique(warnings)

    def _recommended_actions(
        self,
        article: dict[str, Any],
        review_result: dict[str, Any],
        preflight_result: dict[str, Any],
        decision_result: dict[str, Any],
        blocking_issues: list[str],
    ) -> list[str]:
        """根据各 Agent 结果生成去重后的推荐动作，最多 8 条。"""
        actions: list[str] = []
        title = self._safe_text(article.get("title"))
        if len(title) > 22:
            actions.append("优化标题长度")
        if blocking_issues:
            actions.append("修复阻断问题后再继续")
        if (preflight_result or {}).get("pass_preflight") is False:
            actions.append("修复发布前终检问题")
            actions.append("重新执行发布前终检")
        if self._safe_text((review_result or {}).get("risk_level")).lower() == "high":
            actions.append("执行 AI 一键优化草稿")
        decision = self._safe_text((decision_result or {}).get("decision"))
        if decision == "publish":
            actions.append("可以推送微信草稿箱")
        elif decision == "review":
            actions.append("可以进入人工审核")
        elif decision == "retry":
            actions.append("先处理发布任务失败并重试")
        elif decision == "regenerate":
            actions.append("重新生成文章")
        elif decision in {"rewrite", "hold"}:
            actions.append("先暂缓发布并处理风险")
        actions.extend(self._ensure_list((decision_result or {}).get("next_steps")))
        return self._unique(actions)[:8]

    def _summary(
        self,
        workflow_status: str,
        overall_risk: str,
        decision_result: dict[str, Any],
        blocking_issues: list[str],
    ) -> str:
        """生成整体总结。"""
        if blocking_issues:
            return "当前文章仍存在阻断问题，建议先修复后再进入审核或发布。"
        decision = self._safe_text((decision_result or {}).get("decision"))
        if decision == "publish" and overall_risk == "low":
            return "当前文章风险较低，可考虑进入微信草稿箱推送。"
        if decision == "review":
            return "当前文章建议先完成 AI 审核和人工审核确认。"
        if decision == "rewrite":
            return "当前文章建议先生成并应用 AI 优化稿。"
        if workflow_status == "partial":
            return "AI 工作流部分完成，建议结合已完成结果人工判断下一步。"
        if overall_risk == "high":
            return "当前文章发布风险较高，建议暂缓发布。"
        if overall_risk == "medium":
            return "当前文章存在中等风险，建议优化后再继续。"
        return "当前文章整体风险较低，可继续推进运营流程。"

    def _failed_result(self, message: str) -> dict[str, Any]:
        """生成工作流失败结果。"""
        return {
            "ok": False,
            "workflow_status": "failed",
            "overall_risk": "high",
            "review_result": {},
            "rewrite_result": {},
            "preflight_result": {},
            "decision_result": {},
            "summary": message,
            "recommended_actions": [],
            "blocking_issues": [message],
            "warnings": [],
            "raw_response": "",
        }

    def _risk_value(self, risk_level: Any) -> int:
        """风险等级转数值。"""
        return self.RISK_ORDER.get(self._safe_text(risk_level).lower(), 0)

    def _priority_value(self, priority: Any) -> int:
        """决策优先级转风险数值。"""
        return self.RISK_ORDER.get(self._safe_text(priority).lower(), 0)

    def _ensure_list(self, value: Any) -> list[str]:
        """把任意值整理成字符串列表。"""
        if isinstance(value, list):
            return [self._safe_text(item) for item in value if self._safe_text(item)]
        if value:
            return [self._safe_text(value)]
        return []

    def _unique(self, items: list[str]) -> list[str]:
        """列表去重并保持顺序。"""
        result: list[str] = []
        for item in items:
            if item and item not in result:
                result.append(item)
        return result

    def _safe_int(self, value: Any) -> int:
        """安全转整数。"""
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _safe_text(self, value: Any) -> str:
        """安全转字符串。"""
        return str(value or "").strip()
