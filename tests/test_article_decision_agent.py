import unittest
from unittest.mock import patch

import services.article_decision_agent as decision_module
from services.article_decision_agent import ArticleDecisionAgent


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content):
        self.content = content

    def create(self, **kwargs):
        return _FakeResponse(self.content)


class _FakeChat:
    def __init__(self, content):
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content):
        self.chat = _FakeChat(content)


class ArticleDecisionAgentTestCase(unittest.TestCase):
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

    def _build_agent(self, response_text):
        agent = ArticleDecisionAgent.__new__(ArticleDecisionAgent)
        agent.client = _FakeClient(response_text)
        return agent

    def test_empty_title_decision_regenerate(self):
        """标题为空时建议重新生成文章。"""
        with patch.object(decision_module, "OPENAI_API_KEY", ""):
            result = ArticleDecisionAgent().decide_next_action(self._article(title=""))

        self.assertEqual(result["decision"], "regenerate")
        self.assertEqual(result["priority"], "high")
        self.assertFalse(result["can_continue"])

    def test_failed_preflight_decision_hold(self):
        """终检不通过时建议暂缓发布。"""
        with patch.object(decision_module, "OPENAI_API_KEY", ""):
            result = ArticleDecisionAgent().decide_next_action(
                self._article(),
                preflight_result={"pass_preflight": False, "blocking_issues": ["包含高风险词"]},
            )

        self.assertEqual(result["decision"], "hold")
        self.assertEqual(result["priority"], "high")
        self.assertFalse(result["can_continue"])

    def test_high_review_risk_decision_rewrite(self):
        """AI 审核高风险时建议先优化文章。"""
        with patch.object(decision_module, "OPENAI_API_KEY", ""):
            result = ArticleDecisionAgent().decide_next_action(
                self._article(),
                review_result={"risk_level": "high", "issues": ["标题不合规"]},
            )

        self.assertEqual(result["decision"], "rewrite")
        self.assertFalse(result["can_continue"])

    def test_failed_publish_task_decision_retry(self):
        """最近发布任务失败时建议重试任务。"""
        with patch.object(decision_module, "OPENAI_API_KEY", ""):
            result = ArticleDecisionAgent().decide_next_action(
                self._article(status="approved"),
                latest_publish_task={"status": "failed", "error_message": "微信接口失败"},
            )

        self.assertEqual(result["decision"], "retry")
        self.assertEqual(result["priority"], "medium")

    def test_draft_status_decision_review(self):
        """草稿状态建议先审核。"""
        with patch.object(decision_module, "OPENAI_API_KEY", ""):
            result = ArticleDecisionAgent().decide_next_action(self._article(status="draft"))

        self.assertEqual(result["decision"], "review")
        self.assertTrue(result["can_continue"])

    def test_approved_status_decision_publish(self):
        """已审核状态建议推送草稿箱。"""
        with patch.object(decision_module, "OPENAI_API_KEY", ""):
            result = ArticleDecisionAgent().decide_next_action(self._article(status="approved"))

        self.assertEqual(result["decision"], "publish")
        self.assertTrue(result["can_continue"])

    def test_draft_sent_status_decision_hold(self):
        """已进草稿箱状态建议暂缓重复推送。"""
        with patch.object(decision_module, "OPENAI_API_KEY", ""):
            result = ArticleDecisionAgent().decide_next_action(self._article(status="draft_sent"))

        self.assertEqual(result["decision"], "hold")
        self.assertFalse(result["can_continue"])

    def test_published_status_decision_hold(self):
        """已发布状态建议暂缓。"""
        with patch.object(decision_module, "OPENAI_API_KEY", ""):
            result = ArticleDecisionAgent().decide_next_action(self._article(status="published"))

        self.assertEqual(result["decision"], "hold")
        self.assertFalse(result["can_continue"])

    def test_missing_openai_key_still_returns_local_decision(self):
        """未配置 OPENAI_API_KEY 时仍返回 ok=true 的本地决策。"""
        with patch.object(decision_module, "OPENAI_API_KEY", ""):
            result = ArticleDecisionAgent().decide_next_action(self._article(status="draft"))

        self.assertTrue(result["ok"])
        self.assertEqual(result["decision"], "review")

    def test_non_json_ai_response_keeps_local_decision(self):
        """AI 返回非 JSON 时不影响本地决策。"""
        with patch.object(decision_module, "OPENAI_API_KEY", "test-key"):
            result = self._build_agent("不是 JSON").decide_next_action(self._article(status="approved"))

        self.assertTrue(result["ok"])
        self.assertEqual(result["decision"], "publish")
        self.assertEqual(result["raw_response"], "不是 JSON")


if __name__ == "__main__":
    unittest.main()
