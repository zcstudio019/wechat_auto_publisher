import unittest
from unittest.mock import MagicMock, patch

from ai_processor import content_writer
from services.template_service import TemplateService


class TemplateServiceGenerationTests(unittest.TestCase):
    def _template(self):
        return {
            "id": 9,
            "name": "贷款行业底层规律型文章",
            "category": "industry_law",
            "category_label": "贷款行业底层规律",
            "is_active": 1,
        }

    def _article(self):
        return {
            "title": "银行审批真正看的是什么",
            "content": "## 正文\n\n这是正文。",
            "html_content": "<h2>正文</h2><p>这是正文。</p>",
            "summary": "测试摘要",
            "tags": "企业融资,贷款行业底层规律",
        }

    def test_cover_is_queued_instead_of_generated_in_the_request(self):
        lookup_db = MagicMock()
        article_db = MagicMock()
        queued_task = {"id": 77, "status": "queued"}

        with patch("services.template_service.get_db", side_effect=[lookup_db, article_db]), patch.object(
            TemplateService, "_select_template_by_id", return_value=self._template()
        ), patch.object(
            TemplateService, "_select_article_id_by_title", return_value=None
        ), patch.object(
            TemplateService, "_insert_generated_article", return_value=123
        ), patch(
            "services.template_service.write_with_template", return_value=self._article()
        ), patch(
            "services.template_service.format_original_article", side_effect=lambda article: article
        ), patch(
            "services.template_service.generate_cover_for_article", create=True
        ) as synchronous_cover, patch(
            "services.cover_task_service.CoverTaskService.create_cover_task",
            return_value=queued_task,
        ) as create_cover_task:
            result = TemplateService.use_template(9, "银行审批逻辑", "industry_law")

        self.assertTrue(result["success"])
        self.assertEqual(result["article_id"], 123)
        self.assertEqual(result["cover_status"], "queued")
        self.assertEqual(result["cover_task_id"], 77)
        synchronous_cover.assert_not_called()
        create_cover_task.assert_called_once_with(123, style="贷款行业底层规律")
        article_db.commit.assert_called_once()

    def test_cover_queue_failure_does_not_fail_saved_article(self):
        lookup_db = MagicMock()
        article_db = MagicMock()

        with patch("services.template_service.get_db", side_effect=[lookup_db, article_db]), patch.object(
            TemplateService, "_select_template_by_id", return_value=self._template()
        ), patch.object(
            TemplateService, "_select_article_id_by_title", return_value=None
        ), patch.object(
            TemplateService, "_insert_generated_article", return_value=456
        ), patch(
            "services.template_service.write_with_template", return_value=self._article()
        ), patch(
            "services.template_service.format_original_article", side_effect=lambda article: article
        ), patch(
            "services.template_service.generate_cover_for_article", create=True
        ), patch(
            "services.cover_task_service.CoverTaskService.create_cover_task",
            side_effect=RuntimeError("cover queue unavailable"),
        ):
            result = TemplateService.use_template(9, "银行审批逻辑", "industry_law")

        self.assertTrue(result["success"])
        self.assertEqual(result["article_id"], 456)
        self.assertEqual(result["cover_status"], "pending")
        self.assertIn("cover queue unavailable", result["cover_error"])
        article_db.commit.assert_called_once()


class ContentWriterFallbackTests(unittest.TestCase):
    def test_long_topic_uses_local_fallback_without_name_error(self):
        template = {
            "name": "贷款行业底层规律型文章",
            "category": "industry_law",
            "structure": '["反常识结论", "银行真实逻辑", "行动建议"]',
            "pain_point": "企业主不了解银行审批逻辑",
            "solution": "解释偿债能力与产品匹配",
            "hook": "先做企业融资体检",
            "brand_rules": "{}",
            "prompt_template": "",
        }

        with patch.object(content_writer, "_client", None):
            article = content_writer.write_with_template(
                "银行为什么更看重还款来源",
                template,
            )

        self.assertTrue(article["fallback_used"])
        self.assertTrue(article["title"])
        self.assertIn("银行为什么更看重还款来源", article["content"])


if __name__ == "__main__":
    unittest.main()
