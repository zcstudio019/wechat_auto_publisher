import logging
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ai_processor import content_writer
from ai_processor.json_repair import parse_ai_json_object
from services.article_generation_agent import ArticleGenerationAgent


BROKEN_JSON_CASES = {
    "missing_closing_brace": '{"title":"审批逻辑","summary":"摘要","markdown":"## 正文\\n\\n内容"',
    "unterminated_string": '{"title":"审批逻辑","summary":"摘要","markdown":"## 正文\\n\\n内容没有结束',
    "markdown_fence": '```json\n{"title":"审批逻辑","summary":"摘要","markdown":"## 正文\\n\\n内容"}\n```',
}


class FakeCompletions:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    def __init__(self, content):
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


class ArticleGenerationJsonRepairTests(unittest.TestCase):
    def test_broken_json_cases_still_generate_article(self):
        for case_name, raw_content in BROKEN_JSON_CASES.items():
            with self.subTest(case=case_name):
                agent = ArticleGenerationAgent.__new__(ArticleGenerationAgent)
                agent.config_error = ""
                agent.client = FakeClient(raw_content)

                result = agent.generate(
                    keyword="银行审批逻辑",
                    primary_category="science",
                )

                self.assertTrue(result["ok"])
                self.assertTrue(result["title"])
                self.assertTrue(result["summary"])
                self.assertTrue(result["markdown"])
                request = agent.client.chat.completions.calls[0]
                self.assertEqual(request["response_format"], {"type": "json_object"})

    def test_empty_required_fields_use_local_fallback(self):
        agent = ArticleGenerationAgent.__new__(ArticleGenerationAgent)
        agent.config_error = ""
        agent.client = FakeClient('{"title":"","summary":"","markdown":""}')

        result = agent.generate(keyword="银行审批逻辑", primary_category="science")

        self.assertTrue(result["ok"])
        self.assertTrue(result["title"])
        self.assertTrue(result["summary"])
        self.assertTrue(result["markdown"])
        self.assertTrue(result["fallback_used"])

    def test_required_parse_and_repair_logs_are_emitted(self):
        repair_logger = logging.getLogger("services.article_generation_agent")
        with self.assertLogs(repair_logger.name, level="INFO") as logs:
            payload = parse_ai_json_object(
                BROKEN_JSON_CASES["missing_closing_brace"],
                repair_logger,
            )

        self.assertEqual(payload["title"], "审批逻辑")
        output = "\n".join(logs.output)
        self.assertIn("[AI-RAW-RESPONSE]", output)
        self.assertIn("[AI-JSON-PARSE] failure", output)
        self.assertIn("[AI-JSON-REPAIR] before_length=", output)
        self.assertIn("[AI-JSON-PARSE] success method=repair", output)


class TemplateWriterJsonRepairTests(unittest.TestCase):
    def test_broken_json_cases_still_generate_template_article(self):
        template = {
            "name": "贷款行业底层规律型文章",
            "category": "industry_law",
            "structure": '["反常识结论", "银行真实逻辑", "行动建议"]',
            "pain_point": "企业主不了解银行审批逻辑",
            "solution": "解释还款来源和偿债能力",
            "hook": "先做企业融资体检",
            "brand_rules": "{}",
            "prompt_template": "",
        }

        for case_name, raw_content in BROKEN_JSON_CASES.items():
            with self.subTest(case=case_name):
                fake_client = FakeClient(raw_content)
                with patch.object(content_writer, "_client", fake_client):
                    article = content_writer.write_with_template(
                        "银行审批逻辑",
                        template,
                    )

                self.assertTrue(article["title"])
                self.assertTrue(article["summary"])
                self.assertTrue(article["content"])

    def test_empty_required_fields_use_template_fallback(self):
        template = {
            "name": "贷款行业底层规律型文章",
            "category": "industry_law",
            "structure": '["反常识结论", "银行真实逻辑", "行动建议"]',
            "pain_point": "企业主不了解银行审批逻辑",
            "solution": "解释还款来源和偿债能力",
            "hook": "先做企业融资体检",
            "brand_rules": "{}",
            "prompt_template": "",
        }
        with patch.object(content_writer, "_client", FakeClient('{"title":"","summary":"","content":""}')):
            article = content_writer.write_with_template("银行审批逻辑", template)

        self.assertTrue(article["title"])
        self.assertTrue(article["summary"])
        self.assertTrue(article["content"])
        self.assertTrue(article["fallback_used"])


if __name__ == "__main__":
    unittest.main()
