import unittest
from unittest.mock import patch

from services.ai_playbook_action_service import AIPlaybookActionService


class AIPlaybookActionServiceTestCase(unittest.TestCase):
    """AI Playbook 安全动作执行服务测试。"""

    @patch("services.ai_playbook_action_service.ArticlePreflightAgent")
    @patch.object(AIPlaybookActionService, "_get_article")
    def test_rerun_preflight_success(self, mock_get_article, mock_agent_cls):
        mock_get_article.return_value = {"id": 1, "title": "测试文章", "content": "正文"}
        mock_agent_cls.return_value.preflight_article.return_value = {
            "ok": True,
            "pass_preflight": True,
            "risk_level": "low",
        }

        result = AIPlaybookActionService.execute_action("rerun_preflight", 1)

        self.assertTrue(result["ok"])
        self.assertEqual(result["action_type"], "rerun_preflight")
        self.assertEqual(result["article_id"], 1)
        self.assertTrue(result["result"]["pass_preflight"])

    @patch("services.ai_playbook_action_service.PublishTaskService")
    @patch("services.ai_playbook_action_service.ArticleDecisionAgent")
    @patch.object(AIPlaybookActionService, "_get_article")
    def test_rerun_decision_success(self, mock_get_article, mock_agent_cls, mock_task_service):
        article = {"id": 2, "title": "测试文章", "content": "正文", "status": "draft"}
        mock_get_article.return_value = article
        mock_task_service.get_latest_task_for_article.return_value = {"status": "failed"}
        mock_agent_cls.return_value.decide_next_action.return_value = {
            "ok": True,
            "decision": "retry",
            "decision_label": "建议重试发布任务",
            "priority": "medium",
        }

        result = AIPlaybookActionService.execute_action("rerun_decision", 2)

        self.assertTrue(result["ok"])
        self.assertEqual(result["action_type"], "rerun_decision")
        self.assertEqual(result["article_id"], 2)
        self.assertEqual(result["result"]["decision"], "retry")
        mock_agent_cls.return_value.decide_next_action.assert_called_once()

    def test_unsupported_action_type(self):
        result = AIPlaybookActionService.execute_action("publish", 1)

        self.assertFalse(result["ok"])
        self.assertEqual(result["msg"], "不支持的 Playbook 动作")

    @patch.object(AIPlaybookActionService, "_get_article")
    def test_article_not_found(self, mock_get_article):
        mock_get_article.return_value = None

        result = AIPlaybookActionService.execute_action("rerun_preflight", 999)

        self.assertFalse(result["ok"])
        self.assertEqual(result["msg"], "文章不存在")

    @patch("services.ai_playbook_action_service.ArticlePreflightAgent")
    @patch.object(AIPlaybookActionService, "_get_article")
    def test_agent_exception_fallback(self, mock_get_article, mock_agent_cls):
        mock_get_article.return_value = {"id": 3, "title": "测试文章", "content": "正文"}
        mock_agent_cls.return_value.preflight_article.side_effect = RuntimeError("agent down")

        result = AIPlaybookActionService.execute_action("rerun_preflight", 3)

        self.assertFalse(result["ok"])
        self.assertIn("Playbook 动作执行失败", result["msg"])


if __name__ == "__main__":
    unittest.main()
