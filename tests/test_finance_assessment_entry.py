import json
import unittest
from unittest.mock import MagicMock, patch

import config
from services.finance_assessment_service import (
    FINANCE_ASSESSMENT_CTA_MARKER,
    append_finance_assessment_cta,
    get_finance_assessment_url,
)
from services.template_service import TemplateService
from wechat_api import client as client_module
from wechat_api import publisher as publisher_module


ASSESSMENT_URL = "https://capital.linhongtech.com"


class FinanceAssessmentCtaTestCase(unittest.TestCase):
    def test_finance_templates_append_cta_at_the_end_once(self):
        cases = (
            {"_template_category": "industry_law"},
            {"_template_category": "finance"},
            {"_template_category": "leads", "_template_name": "自动获客型模板"},
            {"_template_name": "企业融资获客型文章"},
        )
        for metadata in cases:
            with self.subTest(metadata=metadata):
                original = "<article><p>正文内容</p><p>总结</p></article>"
                result = append_finance_assessment_cta(original, metadata)
                self.assertIn(FINANCE_ASSESSMENT_CTA_MARKER, result)
                self.assertGreater(result.index(FINANCE_ASSESSMENT_CTA_MARKER), result.index("总结"))
                self.assertIn("点击文末“阅读原文”", result)
                self.assertIn("立即免费测评", result)
                self.assertNotIn(f'href="{ASSESSMENT_URL}"', result)
                self.assertEqual(
                    append_finance_assessment_cta(result, metadata).count(
                        FINANCE_ASSESSMENT_CTA_MARKER
                    ),
                    1,
                )

    def test_template_save_chain_persists_cta_after_summary(self):
        db = MagicMock()
        db.execute.return_value.lastrowid = 501
        article = {
            "title": "企业融资文章",
            "content": "正文\n总结",
            "html_content": "<article><p>正文</p><p>总结</p></article>",
            "_template_category": "industry_law",
        }
        with patch("services.template_service.is_mysql", return_value=False), patch(
            "services.template_service.append_lead_qr_at_end", side_effect=lambda html: html + '<section data-lead-qr="true">二维码</section>'
        ):
            article_id = TemplateService._insert_generated_article(
                db, article, "企业融资", "pending_review", "not_ready"
            )

        saved_html = db.execute.call_args.args[1][-1]
        self.assertEqual(article_id, 501)
        self.assertIn(FINANCE_ASSESSMENT_CTA_MARKER, saved_html)
        self.assertGreater(saved_html.index(FINANCE_ASSESSMENT_CTA_MARKER), saved_html.index("总结"))
        self.assertGreater(saved_html.index(FINANCE_ASSESSMENT_CTA_MARKER), saved_html.index("data-lead-qr"))

    def test_non_finance_template_does_not_get_forced_cta(self):
        original = "<article><p>品牌宣传正文</p></article>"
        result = append_finance_assessment_cta(
            original,
            {"_template_category": "brand", "_template_name": "品牌宣传型模板"},
        )
        self.assertEqual(result, original)
        self.assertNotIn(FINANCE_ASSESSMENT_CTA_MARKER, result)

    def test_url_validation_accepts_only_expected_https_domain(self):
        with patch.object(config, "FINANCE_ASSESSMENT_URL", ASSESSMENT_URL):
            self.assertEqual(get_finance_assessment_url(), ASSESSMENT_URL)

        for invalid_url in (
            "http://capital.linhongtech.com",
            "https://example.com",
            "https://capital.linhongtech.com.evil.example",
            "https://capital.linhongtech.com:8443",
        ):
            with self.subTest(url=invalid_url), patch.object(
                config, "FINANCE_ASSESSMENT_URL", invalid_url
            ):
                self.assertIsNone(get_finance_assessment_url())


class WechatDraftAssessmentUrlTestCase(unittest.TestCase):
    @staticmethod
    def _article():
        title = "初创企业老板企业周转时现金流紧张，为什么有利润仍周转困难？先查这3项"
        content = (
            f"<article><h1>{title}</h1><p>完整正文</p>"
            '<section data-finance-assessment-cta="true">企业融资免费测评</section>'
            '<section data-lead-qr="true"><img src="https://example.com/qr.png"></section>'
            "</article>"
        )
        return {
            "id": 2301,
            "title": title,
            "optimized_title": "现金流吃紧时，企业该怎么周转",
            "summary": "融资测评摘要",
            "html_content": content,
            "content": "",
            "cover_image": "",
            "cover_url": "",
        }

    def _publish_and_capture(self, configured_url=ASSESSMENT_URL):
        article = self._article()
        captured = {}

        def fake_add_draft(articles):
            captured["article"] = articles[0]
            return "wechat-draft-media-2301"

        with patch.object(config, "FINANCE_ASSESSMENT_URL", configured_url), patch(
            "wechat_api.publisher.validate_wechat_config", return_value=None
        ), patch(
            "wechat_api.publisher._select_article_publish_content",
            return_value=("html_content", article["html_content"]),
        ), patch(
            "wechat_api.publisher.ensure_thumb_media_id",
            return_value="thumb-media-2301",
        ), patch(
            "wechat_api.publisher._finalize_wechat_content_for_draft",
            return_value=(
                article["html_content"],
                {"qr_img_src": "https://example.com/qr.png"},
            ),
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
            "wechat_api.publisher.add_draft", side_effect=fake_add_draft
        ):
            media_id = publisher_module.publish_single_article(article, auto_submit=True)
        return media_id, captured["article"]

    def test_manual_draft_payload_keeps_all_article_fields_and_source_url(self):
        media_id, payload = self._publish_and_capture()
        original = self._article()

        self.assertEqual(media_id, "wechat-draft-media-2301")
        self.assertEqual(payload["title"], original["title"])
        self.assertNotEqual(payload["title"], original["optimized_title"])
        self.assertEqual(payload["digest"], original["summary"])
        self.assertEqual(payload["thumb_media_id"], "thumb-media-2301")
        self.assertIn("完整正文", payload["content"])
        self.assertIn("data-finance-assessment-cta", payload["content"])
        self.assertIn("data-lead-qr", payload["content"])
        self.assertGreater(payload["content"].index("data-finance-assessment-cta"), payload["content"].index("data-lead-qr"))
        self.assertEqual(payload["content_source_url"], ASSESSMENT_URL)
        self.assertEqual(payload["need_open_comment"], 1)
        self.assertEqual(payload["only_fans_can_comment"], 0)

    def test_invalid_source_url_is_omitted_without_blocking_draft(self):
        media_id, payload = self._publish_and_capture("http://capital.linhongtech.com")
        self.assertEqual(media_id, "wechat-draft-media-2301")
        self.assertNotIn("content_source_url", payload)

    def test_draft_add_transport_preserves_content_source_url(self):
        captured = {}
        response = MagicMock()
        response.json.return_value = {"media_id": "transport-media-id"}

        def fake_post(_url, data, headers, timeout):
            captured["payload"] = json.loads(data.decode("utf-8"))
            captured["headers"] = headers
            captured["timeout"] = timeout
            return response

        article = {
            "title": "正式标题",
            "author": "沪上银",
            "digest": "摘要",
            "content": "<p>正文</p>",
            "content_source_url": ASSESSMENT_URL,
            "thumb_media_id": "thumb-1",
            "need_open_comment": 1,
            "only_fans_can_comment": 0,
        }
        with patch("wechat_api.client.get_access_token", return_value="token"), patch(
            "wechat_api.client._http_post", side_effect=fake_post
        ):
            media_id = client_module.add_draft([article])

        sent_article = captured["payload"]["articles"][0]
        self.assertEqual(media_id, "transport-media-id")
        self.assertEqual(sent_article["content_source_url"], ASSESSMENT_URL)
        self.assertEqual(sent_article["title"], "正式标题")
        self.assertEqual(sent_article["content"], "<p>正文</p>")
        self.assertEqual(sent_article["thumb_media_id"], "thumb-1")


    def test_draft_add_transport_omits_invalid_direct_source_url(self):
        captured = {}
        response = MagicMock()
        response.json.return_value = {"media_id": "transport-media-id-invalid"}

        def fake_post(_url, data, headers, timeout):
            captured["payload"] = json.loads(data.decode("utf-8"))
            return response

        article = {
            "title": "正式标题",
            "content": "<p>正文</p>",
            "content_source_url": "https://evil.example/assessment",
            "thumb_media_id": "thumb-1",
        }
        with patch("wechat_api.client.get_access_token", return_value="token"), patch(
            "wechat_api.client._http_post", side_effect=fake_post
        ):
            media_id = client_module.add_draft([article])

        self.assertEqual(media_id, "transport-media-id-invalid")
        self.assertNotIn("content_source_url", captured["payload"]["articles"][0])


if __name__ == "__main__":
    unittest.main()
