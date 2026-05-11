import unittest
from unittest.mock import patch

import services.article_preflight_agent as preflight_module
from services.article_preflight_agent import ArticlePreflightAgent


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


class ArticlePreflightAgentTestCase(unittest.TestCase):
    def _article(self, **overrides):
        article = {
            "title": "融资前先看这几点",
            "summary": "企业融资前，先理清需求、成本与风险。",
            "content": "正文内容，没有违规承诺。",
            "html_content": "<section><p>正文内容</p></section>",
        }
        article.update(overrides)
        return article

    def _build_agent(self, response_text):
        agent = ArticlePreflightAgent.__new__(ArticlePreflightAgent)
        agent.client = _FakeClient(response_text)
        return agent

    def test_missing_openai_key_returns_no_500(self):
        """OPENAI_API_KEY 未配置时应返回 ok=false 且不抛异常。"""
        with patch.object(preflight_module, "OPENAI_API_KEY", ""):
            result = ArticlePreflightAgent().preflight_article(self._article())

        self.assertFalse(result["ok"])
        self.assertIn("未配置 OPENAI_API_KEY", result["msg"])

    def test_empty_title_creates_blocking_issue(self):
        """标题为空应产生阻断问题。"""
        result = ArticlePreflightAgent.__new__(ArticlePreflightAgent)._local_preflight(self._article(title=""))

        self.assertFalse(result["pass_preflight"])
        self.assertTrue(result["blocking_issues"])
        self.assertTrue(result["title_issues"])

    def test_title_over_30_creates_blocking_issue(self):
        """标题超过 30 字应产生阻断问题。"""
        title = "这是一条超过三十个字的公众号文章标题用于测试终检阻断逻辑请不要进入发布流程"
        result = ArticlePreflightAgent.__new__(ArticlePreflightAgent)._local_preflight(self._article(title=title))

        self.assertFalse(result["pass_preflight"])
        self.assertIn("标题超过 30 字，移动端展示风险较高", result["blocking_issues"])

    def test_script_tag_creates_blocking_issue(self):
        """HTML 包含 script 应产生阻断问题。"""
        result = ArticlePreflightAgent.__new__(ArticlePreflightAgent)._local_preflight(
            self._article(html_content="<section><script>alert(1)</script></section>")
        )

        self.assertFalse(result["pass_preflight"])
        self.assertTrue(result["wechat_html_issues"])

    def test_form_input_creates_blocking_issue(self):
        """HTML 包含 form/input 应产生阻断问题。"""
        result = ArticlePreflightAgent.__new__(ArticlePreflightAgent)._local_preflight(
            self._article(html_content="<form><input name='phone'></form>")
        )

        self.assertFalse(result["pass_preflight"])
        self.assertGreaterEqual(len(result["wechat_html_issues"]), 2)

    def test_high_risk_words_create_compliance_blocking_issue(self):
        """内容包含高风险词应产生合规阻断问题。"""
        result = ArticlePreflightAgent.__new__(ArticlePreflightAgent)._local_preflight(
            self._article(content="我们包过，无视征信，百分百下款。")
        )

        self.assertFalse(result["pass_preflight"])
        self.assertTrue(result["compliance_issues"])

    def test_normal_article_local_rules_can_pass(self):
        """正常文章本地规则应可通过。"""
        result = ArticlePreflightAgent.__new__(ArticlePreflightAgent)._local_preflight(self._article())

        self.assertTrue(result["pass_preflight"])
        self.assertEqual(result["risk_level"], "low")

    def test_non_json_model_response_falls_back_to_local_result(self):
        """模型返回非 JSON 时应保留本地结果并返回 ok=false。"""
        with patch.object(preflight_module, "OPENAI_API_KEY", "test-key"):
            result = self._build_agent("不是 JSON").preflight_article(self._article())

        self.assertFalse(result["ok"])
        self.assertIn("raw_response", result)
        self.assertEqual(result["raw_response"], "不是 JSON")
        self.assertIn("pass_preflight", result)


if __name__ == "__main__":
    unittest.main()
