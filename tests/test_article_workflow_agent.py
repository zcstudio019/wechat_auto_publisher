import unittest
from unittest.mock import patch

import services.article_workflow_agent as workflow_module
from services.article_workflow_agent import ArticleWorkflowAgent


class ArticleWorkflowAgentTestCase(unittest.TestCase):
    def _article(self, **overrides):
        article = {
            "id": 1,
            "title": "融资前先看这几点",
            "summary": "企业融资前，先理清需求、成本与风险。",
            "content": "完整正文内容",
            "html_content": "<section><p>完整正文内容</p></section>",
            "status": "draft",
        }
        article.update(overrides)
        return article

    def _patch_success_agents(self, review=None, rewrite=None, preflight=None, decision=None, task=None):
        review = review or {"ok": True, "risk_level": "low", "issues": [], "suggestions": []}
        rewrite = rewrite or {"ok": True, "rewritten_title": "融资前先看这几点", "change_summary": []}
        preflight = preflight or {"ok": True, "pass_preflight": True, "risk_level": "low", "blocking_issues": [], "warnings": []}
        decision = decision or {
            "ok": True,
            "decision": "review",
            "decision_label": "建议先做 AI 审核",
            "priority": "medium",
            "can_continue": True,
            "reason": "文章仍为草稿",
            "next_steps": ["点击“AI 审核建议”"],
            "warnings": [],
        }
        return (
            patch.object(workflow_module.ArticleReviewAgent, "review_article", return_value=review),
            patch.object(workflow_module.ArticleRewriteAgent, "rewrite_article", return_value=rewrite),
            patch.object(workflow_module.ArticlePreflightAgent, "preflight_article", return_value=preflight),
            patch.object(workflow_module.ArticleDecisionAgent, "decide_next_action", return_value=decision),
            patch.object(workflow_module.PublishTaskService, "get_latest_task_for_article", return_value=task),
        )

    def test_all_agents_success_workflow_completed(self):
        """所有 Agent 成功时 workflow_status=completed。"""
        patches = self._patch_success_agents()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = ArticleWorkflowAgent().run_workflow(self._article())

        self.assertTrue(result["ok"])
        self.assertEqual(result["workflow_status"], "completed")
        self.assertIn("review_result", result)

    def test_one_agent_exception_workflow_partial(self):
        """某个 Agent 异常时 workflow_status=partial。"""
        patches = self._patch_success_agents()
        with patch.object(workflow_module.ArticleReviewAgent, "review_article", side_effect=RuntimeError("boom")), \
             patches[1], patches[2], patches[3], patches[4]:
            result = ArticleWorkflowAgent().run_workflow(self._article())

        self.assertEqual(result["workflow_status"], "partial")
        self.assertTrue(result["warnings"])

    def test_all_agents_fail_workflow_failed(self):
        """全部核心 Agent 失败时 workflow_status=failed。"""
        failed = {"ok": False, "msg": "失败"}
        with patch.object(workflow_module.ArticleReviewAgent, "review_article", return_value=failed), \
             patch.object(workflow_module.ArticleRewriteAgent, "rewrite_article", return_value=failed), \
             patch.object(workflow_module.ArticlePreflightAgent, "preflight_article", return_value=failed), \
             patch.object(workflow_module.ArticleDecisionAgent, "decide_next_action", return_value=failed), \
             patch.object(workflow_module.PublishTaskService, "get_latest_task_for_article", return_value=None):
            result = ArticleWorkflowAgent().run_workflow(self._article())

        self.assertFalse(result["ok"])
        self.assertEqual(result["workflow_status"], "failed")

    def test_high_risk_aggregation(self):
        """任一高风险结果应聚合为 high。"""
        patches = self._patch_success_agents(
            review={"ok": True, "risk_level": "high", "issues": ["包含高风险词"], "suggestions": []}
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = ArticleWorkflowAgent().run_workflow(self._article())

        self.assertEqual(result["overall_risk"], "high")
        self.assertIn("包含高风险词", result["blocking_issues"])

    def test_recommended_actions_are_deduplicated(self):
        """推荐动作应去重。"""
        patches = self._patch_success_agents(
            review={"ok": True, "risk_level": "high", "issues": ["风险"], "suggestions": []},
            decision={
                "ok": True,
                "decision": "rewrite",
                "decision_label": "建议先优化文章",
                "priority": "high",
                "can_continue": False,
                "reason": "高风险",
                "next_steps": ["执行 AI 一键优化草稿", "执行 AI 一键优化草稿"],
                "warnings": ["风险"],
            },
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = ArticleWorkflowAgent().run_workflow(self._article())

        self.assertEqual(
            result["recommended_actions"].count("执行 AI 一键优化草稿"),
            1,
        )

    def test_missing_openai_key_workflow_still_runs(self):
        """OPENAI_API_KEY 未配置时，只要子 Agent 有本地结果，工作流仍可运行。"""
        patches = self._patch_success_agents()
        with patch.object(workflow_module, "ArticleReviewAgent") as review_cls, \
             patches[1], patches[2], patches[3], patches[4]:
            review_cls.return_value.review_article.return_value = {
                "ok": False,
                "msg": "未配置 OPENAI_API_KEY，无法执行 AI 审核",
                "risk_level": "",
            }
            result = ArticleWorkflowAgent().run_workflow(self._article())

        self.assertEqual(result["workflow_status"], "partial")
        self.assertIn("未配置 OPENAI_API_KEY", " ".join(result["warnings"]))

    def test_approved_article_recommends_publish(self):
        """已审核文章应聚合出推送草稿箱建议。"""
        patches = self._patch_success_agents(
            decision={
                "ok": True,
                "decision": "publish",
                "decision_label": "建议推送微信草稿箱",
                "priority": "medium",
                "can_continue": True,
                "reason": "文章已审核",
                "next_steps": ["推送微信草稿箱"],
                "warnings": [],
            }
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = ArticleWorkflowAgent().run_workflow(self._article(status="approved"))

        self.assertIn("可以推送微信草稿箱", result["recommended_actions"])

    def test_preflight_blocking_makes_high_risk(self):
        """终检阻断问题应使 overall_risk=high。"""
        patches = self._patch_success_agents(
            preflight={
                "ok": True,
                "pass_preflight": False,
                "risk_level": "high",
                "blocking_issues": ["HTML 包含 script"],
                "warnings": [],
            }
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = ArticleWorkflowAgent().run_workflow(self._article())

        self.assertEqual(result["overall_risk"], "high")
        self.assertIn("HTML 包含 script", result["blocking_issues"])


if __name__ == "__main__":
    unittest.main()
