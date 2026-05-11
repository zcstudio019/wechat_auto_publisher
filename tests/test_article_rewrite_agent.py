import unittest
from unittest.mock import patch

import services.article_rewrite_agent as rewrite_module
from services.article_rewrite_agent import ArticleRewriteAgent


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


class ArticleRewriteAgentTestCase(unittest.TestCase):
    def _build_agent(self, response_text):
        agent = ArticleRewriteAgent.__new__(ArticleRewriteAgent)
        agent.client = _FakeClient(response_text)
        return agent

    def test_missing_openai_key_returns_error(self):
        """未配置 OPENAI_API_KEY 时应返回 ok=false，不抛异常。"""
        with patch.object(rewrite_module, "OPENAI_API_KEY", ""):
            result = ArticleRewriteAgent().rewrite_article({"title": "测试文章"})

        self.assertFalse(result["ok"])
        self.assertIn("未配置 OPENAI_API_KEY", result["msg"])

    def test_model_json_response_can_be_parsed(self):
        """模型返回 JSON 时应正确解析并补齐固定结构。"""
        response_text = """
        {
          "rewritten_title": "融资前先看这几点",
          "rewritten_summary": "企业融资前，先理清需求、成本与风险。",
          "rewritten_content": "## 问题\\n很多企业融资前没有规划。\\n## 建议\\n先做资金测算，再沟通方案。",
          "change_summary": ["优化标题", "弱化营销表达"]
        }
        """
        with patch.object(rewrite_module, "OPENAI_API_KEY", "test-key"), \
             patch.object(rewrite_module, "format_to_wechat_html", return_value="<p>正文</p>"), \
             patch.object(rewrite_module, "adapt_lead_form_to_wechat_card", side_effect=lambda html: html), \
             patch.object(rewrite_module, "adapt_html_for_wechat", side_effect=lambda html: html):
            result = self._build_agent(response_text).rewrite_article({"title": "旧标题"})

        self.assertTrue(result["ok"])
        self.assertEqual(result["rewritten_title"], "融资前先看这几点")
        self.assertEqual(result["rewritten_html_content"], "<p>正文</p>")
        self.assertEqual(result["change_summary"], ["优化标题", "弱化营销表达"])

    def test_non_json_response_falls_back(self):
        """模型返回非 JSON 时应兜底返回 ok=false 并保留 raw_response。"""
        with patch.object(rewrite_module, "OPENAI_API_KEY", "test-key"):
            result = self._build_agent("这不是 JSON").rewrite_article({"title": "旧标题"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["raw_response"], "这不是 JSON")

    def test_result_contains_required_fields(self):
        """失败返回也应包含前端需要的固定字段。"""
        with patch.object(rewrite_module, "OPENAI_API_KEY", ""):
            result = ArticleRewriteAgent().rewrite_article({"title": "测试文章"})

        for key in [
            "rewritten_title",
            "rewritten_summary",
            "rewritten_content",
            "rewritten_html_content",
            "change_summary",
            "raw_response",
        ]:
            self.assertIn(key, result)

    def test_title_length_is_limited_to_22_chars(self):
        """标题长度兜底逻辑应限制在 22 字以内。"""
        long_title = "企业经营贷款融资申请前一定要先看清楚这几个关键问题"
        response_text = f"""
        {{
          "rewritten_title": "{long_title}",
          "rewritten_summary": "融资前先做好基础判断。",
          "rewritten_content": "正文内容",
          "change_summary": ["压缩标题"]
        }}
        """
        with patch.object(rewrite_module, "OPENAI_API_KEY", "test-key"), \
             patch.object(rewrite_module, "format_to_wechat_html", return_value="<p>正文</p>"), \
             patch.object(rewrite_module, "adapt_lead_form_to_wechat_card", side_effect=lambda html: html), \
             patch.object(rewrite_module, "adapt_html_for_wechat", side_effect=lambda html: html):
            result = self._build_agent(response_text).rewrite_article({"title": "旧标题"})

        self.assertTrue(result["ok"])
        self.assertLessEqual(len(result["rewritten_title"]), 22)


if __name__ == "__main__":
    unittest.main()
