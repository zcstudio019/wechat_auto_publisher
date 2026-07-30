import unittest
from unittest.mock import MagicMock, patch

from services.wechat_title_optimizer import build_wechat_title_suggestion
from wechat_api import publisher as publisher_module


FORMAL_TITLE = "初创企业老板企业周转时现金流紧张，为什么有利润仍周转困难？先查这3项"
SUGGESTED_TITLE = "现金流吃紧时，企业该怎么周转"


class TitleSingleSourceOfTruthTestCase(unittest.TestCase):
    @staticmethod
    def _article(title=FORMAL_TITLE):
        return {
            "id": 1201,
            "title": title,
            "optimized_title": SUGGESTED_TITLE,
            "summary": "企业融资测试摘要",
            "html_content": f"<section><h1>{title}</h1><p>正文内容保持原样。</p></section>",
            "content": "",
            "cover_prompt": f"公众号封面：{title}",
            "cover_image": "",
            "cover_url": "",
        }

    def _publish_and_capture(self, article):
        captured = {}

        def fake_add_draft(articles):
            captured["article"] = articles[0]
            return "media-title-sot"

        with patch("wechat_api.publisher.validate_wechat_config", return_value=None), patch(
            "wechat_api.publisher._select_article_publish_content",
            return_value=("html_content", article["html_content"]),
        ), patch(
            "wechat_api.publisher.ensure_thumb_media_id",
            return_value="thumb-title-sot",
        ), patch(
            "wechat_api.publisher._finalize_wechat_content_for_draft",
            return_value=(article["html_content"], {"qr_img_src": "https://example.com/qr.png"}),
        ), patch(
            "wechat_api.publisher._guard_and_save_add_draft_payload",
            side_effect=lambda _article, content, _meta: content,
        ), patch(
            "wechat_api.publisher._validate_publish_payload_before_add_draft",
            return_value=None,
        ), patch(
            "wechat_api.publisher._save_and_log_final_wechat_send",
            return_value=None,
        ), patch(
            "wechat_api.publisher.add_draft",
            side_effect=fake_add_draft,
        ):
            media_id = publisher_module.publish_single_article(article)
        return media_id, captured["article"]

    def test_wechat_draft_uses_formal_article_title_not_optimized_title(self):
        article = self._article()
        title_fields = build_wechat_title_suggestion({"title": FORMAL_TITLE})

        self.assertEqual(title_fields["title"], FORMAL_TITLE)
        self.assertEqual(title_fields["optimized_title"], SUGGESTED_TITLE)

        media_id, draft_article = self._publish_and_capture(article)

        self.assertEqual(media_id, "media-title-sot")
        self.assertEqual(draft_article["title"], FORMAL_TITLE)
        self.assertNotEqual(draft_article["title"], article["optimized_title"])

    def test_ordinary_template_title_is_not_changed(self):
        ordinary_title = "沪上银品牌服务介绍：企业融资顾问如何提供专业支持"
        article = self._article(ordinary_title)
        article["optimized_title"] = "企业融资顾问能帮你什么"

        _, draft_article = self._publish_and_capture(article)

        self.assertEqual(draft_article["title"], ordinary_title)

    def test_cover_prompt_and_body_h1_keep_formal_title(self):
        article = self._article()
        original_cover_prompt = article["cover_prompt"]
        original_html = article["html_content"]

        _, draft_article = self._publish_and_capture(article)

        self.assertEqual(article["cover_prompt"], original_cover_prompt)
        self.assertEqual(article["html_content"], original_html)
        self.assertIn(f"<h1>{FORMAL_TITLE}</h1>", draft_article["content"])

    def test_batch_publish_also_uses_formal_title(self):
        article = self._article()
        captured = {}
        connection = MagicMock()
        cursor = connection.cursor.return_value

        def fake_add_draft(articles):
            captured["article"] = articles[0]
            return "media-batch-title-sot"

        with patch("wechat_api.publisher.get_db", return_value=connection), patch(
            "wechat_api.publisher._select_approved_articles",
            return_value=[article],
        ), patch(
            "wechat_api.publisher.validate_wechat_config",
            return_value=None,
        ), patch(
            "wechat_api.publisher._select_article_publish_content",
            return_value=("html_content", article["html_content"]),
        ), patch(
            "wechat_api.publisher.ensure_thumb_media_id",
            return_value="thumb-title-sot",
        ), patch(
            "wechat_api.publisher._finalize_wechat_content_for_draft",
            return_value=(article["html_content"], {"qr_img_src": "https://example.com/qr.png"}),
        ), patch(
            "wechat_api.publisher._guard_and_save_add_draft_payload",
            side_effect=lambda _article, content, _meta: content,
        ), patch(
            "wechat_api.publisher._validate_publish_payload_before_add_draft",
            return_value=None,
        ), patch(
            "wechat_api.publisher._save_and_log_final_wechat_send",
            return_value=None,
        ), patch(
            "wechat_api.publisher._update_article_publish_status",
            return_value=None,
        ), patch(
            "wechat_api.publisher.add_draft",
            side_effect=fake_add_draft,
        ):
            success = publisher_module.publish_approved_articles(auto_submit=False)

        self.assertEqual(success, 1)
        self.assertEqual(captured["article"]["title"], FORMAL_TITLE)
        self.assertNotEqual(captured["article"]["title"], SUGGESTED_TITLE)
        cursor.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
