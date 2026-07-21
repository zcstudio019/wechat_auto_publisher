import os
import shutil
import time
import uuid
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from flask import render_template

from config import CONTENT_GROWTH_LOW_TRAFFIC_THRESHOLD
import database
from database import (
    MYSQL_CONTENT_GROWTH_CREATE_SQL,
    SQLITE_CONTENT_GROWTH_CREATE_SQL,
)
from services.article_growth_analyzer import ArticleGrowthAnalyzer
from services.article_generation_agent import ArticleGenerationAgent
from services.article_generation_task_service import ArticleGenerationTaskService
from services.wechat_lead_card_adapter import append_lead_qr_at_end
import services.article_generation_agent as generation_module
from services.title_score_service import TitleScoreService
from services.title_guard import TitleGuard
from services.template_service import TemplateService
from services.topic_engine import TopicEngine
from ai_processor.processor import _make_image_card, _render_original_html
from web_ui.app import app
import wechat_api.publisher as publisher_module


class ContentGrowthDatabaseSqlTestCase(unittest.TestCase):
    def test_mysql_sql_does_not_use_legacy_reads_column(self):
        self.assertNotIn("reads INT DEFAULT 0", MYSQL_CONTENT_GROWTH_CREATE_SQL)
        self.assertNotIn("likes INT DEFAULT 0", MYSQL_CONTENT_GROWTH_CREATE_SQL)

    def test_mysql_sql_uses_canonical_metric_columns(self):
        self.assertIn("id INT AUTO_INCREMENT PRIMARY KEY", MYSQL_CONTENT_GROWTH_CREATE_SQL)
        self.assertIn("view_count INT DEFAULT 0", MYSQL_CONTENT_GROWTH_CREATE_SQL)
        self.assertIn("like_count INT DEFAULT 0", MYSQL_CONTENT_GROWTH_CREATE_SQL)

    def test_sqlite_create_sql_executes(self):
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute(SQLITE_CONTENT_GROWTH_CREATE_SQL)
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(article_growth_metrics)").fetchall()
            }
        finally:
            conn.close()

        self.assertIn("view_count", columns)
        self.assertIn("growth_score", columns)


class ContentGrowthServicesTestCase(unittest.TestCase):
    def test_missing_api_key_returns_explicit_config_error(self):
        with patch.object(generation_module, "OPENAI_API_KEY", ""), patch.object(
            generation_module,
            "OPENAI_BASE_URL",
            "https://api.example.com/v1",
        ), patch.object(generation_module, "OPENAI_MODEL", "test-model"):
            result = ArticleGenerationAgent().generate("企业经营贷")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "AI_CONFIG_MISSING")
        self.assertEqual(result["error_message"], "AI API Key 未配置")

    def test_generation_client_uses_timeout_and_retries(self):
        with patch.object(generation_module, "OPENAI_API_KEY", "sk-test12345678"), patch.object(
            generation_module,
            "OPENAI_BASE_URL",
            "https://api.example.com/v1",
        ), patch.object(generation_module, "OPENAI_MODEL", "test-model"), patch(
            "openai.OpenAI",
        ) as openai_client:
            ArticleGenerationAgent()

        openai_client.assert_called_once_with(
            api_key="sk-test12345678",
            base_url="https://api.example.com/v1",
            timeout=60,
            max_retries=2,
        )

    def test_local_generation_fallback_has_required_sections(self):
        result = ArticleGenerationAgent.build_local_fallback(
            "经营贷被拒后，老板先查这3点",
            {"pain_point": "银行不批，企业主不知道原因"},
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["fallback_used"])
        self.assertIn("真实案例", result["markdown"])
        self.assertIn("银行不批，通常卡在这 5 个点", result["markdown"])
        self.assertIn("申请前，老板先做这 5 个检查", result["markdown"])
        self.assertIn("风险提醒", result["markdown"])
        self.assertIn("企业融资体检", result["markdown"])

    def test_local_generation_fallback_uses_boss_click_title_and_fixed_cta(self):
        result = ArticleGenerationAgent.build_local_fallback(
            "如何科学规划企业融资",
            {"pain_point": "经营贷被拒后，老板不知道额度卡在哪里"},
        )

        self.assertTrue(result["ok"])
        self.assertNotIn("如何科学规划", result["title"])
        self.assertTrue(TitleGuard.inspect_title(result["title"])["qualified"])
        self.assertIn("企业融资体检", result["markdown"])
        self.assertIn("适合人群", result["markdown"])
        self.assertIn("体检结果", result["markdown"])
        self.assertIn("行动引导", result["markdown"])

    def test_local_generation_fallback_opening_hits_owner_pain_before_case(self):
        result = ArticleGenerationAgent.build_local_fallback("经营贷被拒后，老板先查这3点")
        markdown = result["markdown"]
        first_heading = markdown.index("## ")
        opening = markdown[:first_heading]

        self.assertGreaterEqual(opening.count("\n\n"), 2)
        self.assertIn("常见误区", opening)
        self.assertIn("银行为什么不批", opening)
        self.assertIn("解决一个具体问题", opening)
        self.assertLessEqual(markdown.count("\n## ") + (1 if markdown.startswith("## ") else 0), 5)

    def test_quote_card_has_no_standalone_english_quotes(self):
        html = _make_image_card("借得好，也是一种经营能力", "quote", "— 沪上银")

        self.assertIn("借得好，也是一种经营能力", html)
        self.assertNotIn('>"</div>', html)
        self.assertNotIn('>"</p>', html)

    def test_render_original_html_keeps_one_quote_card(self):
        content = """开头段落

[配图:quote:第一句金句:沪上银]

## 第一节

正文

[配图:quote:第二句金句:沪上银]

## 第二节

正文

## 第三节

正文"""
        html = _render_original_html("经营贷被拒后，老板先查这3点", content, "沪上银原创", category="leads")

        self.assertIn("第一句金句", html)
        self.assertNotIn("第二句金句", html)

    def test_topic_engine_returns_required_fields(self):
        topics = TopicEngine.generate_topics()

        self.assertEqual(len(topics), 8)
        for topic in topics:
            self.assertIn("target_customer", topic)
            self.assertIn("pain_point", topic)
            self.assertIn("article_angle", topic)
            self.assertIn("suggested_title", topic)
            self.assertIn("conversion_goal", topic)

    def test_low_title_score_generates_optimized_titles(self):
        result = TitleScoreService.score_title("融资知识科普")

        self.assertLess(result["score"], 80)
        self.assertEqual(len(result["optimized_titles"]), 5)

    def test_dashboard_structure_is_stable_when_database_fails(self):
        with patch.object(ArticleGrowthAnalyzer, "ensure_storage", return_value=False), patch.object(
            ArticleGrowthAnalyzer,
            "_fetch_dashboard_rows",
            side_effect=RuntimeError("db unavailable"),
        ):
            result = ArticleGrowthAnalyzer.get_dashboard_data()

        self.assertFalse(result["ok"])
        self.assertEqual(result["articles"], [])
        self.assertEqual(result["summary"], ArticleGrowthAnalyzer.SUMMARY_DEFAULTS)
        self.assertTrue(result["error"])

    def test_rewrite_uses_fallback_when_title_optimizer_fails(self):
        analysis = {
            "ok": True,
            "error": None,
            "title": "企业经营贷",
            "view_count": 10,
            "failure_reasons": ["阅读量偏低"],
            "title_score": {"optimized_titles": []},
        }
        article = {"id": 1, "title": "企业经营贷", "content": "原始正文"}
        with patch.object(ArticleGrowthAnalyzer, "analyze_article_growth", return_value=analysis), patch.object(
            TitleScoreService,
            "optimize_titles",
            side_effect=RuntimeError("AI unavailable"),
        ), patch.object(
            ArticleGrowthAnalyzer,
            "_get_article",
            return_value=article,
        ), patch.object(
            ArticleGrowthAnalyzer,
            "_save_rewrite_proposal",
            return_value=True,
        ):
            result = ArticleGrowthAnalyzer.rewrite_for_growth(1)

        self.assertTrue(result["ok"])
        self.assertTrue(result["fallback_used"])
        self.assertEqual(len(result["new_titles"]), 3)
        self.assertEqual(article["content"], "原始正文")
        self.assertIn("optimized_content", result)

    def test_metric_compatibility_maps_reads_and_likes(self):
        metrics = ArticleGrowthAnalyzer._normalize_metrics({"reads": 12, "likes": 3})

        self.assertEqual(metrics["view_count"], 12)
        self.assertEqual(metrics["like_count"], 3)

    def test_draft_sent_has_clear_chinese_status(self):
        self.assertEqual(
            ArticleGrowthAnalyzer._status_label("draft_sent"),
            "已推送草稿箱，未确认发布",
        )

    def test_new_account_low_traffic_threshold_defaults_to_50(self):
        self.assertEqual(CONTENT_GROWTH_LOW_TRAFFIC_THRESHOLD, 50)

    def test_growth_dashboard_template_does_not_hardcode_300(self):
        template_path = Path(__file__).resolve().parents[1] / "web_ui" / "templates" / "content_growth_dashboard.html"
        template = template_path.read_text(encoding="utf-8")

        self.assertNotIn("default(300", template)
        self.assertIn("default(50", template)


class LeadQrPlacementTestCase(unittest.TestCase):
    def _with_qr(self, html: str) -> str:
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "services.wechat_lead_card_adapter.WECHAT_LEAD_QR_IMAGE",
            str(Path(tmpdir) / "lead_qr.png"),
        ):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            return append_lead_qr_at_end(html)

    def test_qr_is_final_module_when_article_has_later_paragraphs(self):
        html = """
        <h2>案例拆解</h2><p>第一段正文</p><p>第二段正文</p>
        <h2>解决建议</h2><p>建议一</p><p>建议二</p><p>最后一段正文</p>
        """
        result = self._with_qr(html)

        self.assertGreater(result.rfind("data-lead-qr"), result.rfind("最后一段正文"))
        self.assertTrue(result.strip().endswith("</div>"))
        self.assertNotIn("最后一段正文", result[result.rfind("data-lead-qr"):])

    def test_existing_middle_qr_is_removed_then_appended_once(self):
        html = """
        <p>开头正文</p>
        <div data-lead-qr="true"><p>如果你最近准备申请经营贷、续贷、降息或提高额度，可以扫码做一次企业融资体检。</p><img src="old.png"></div>
        <p>二维码后面的正文</p>
        """
        result = self._with_qr(html)

        self.assertEqual(result.count("data-lead-qr"), 1)
        self.assertEqual(result.count("扫码做一次企业融资体检"), 1)
        self.assertGreater(result.rfind("data-lead-qr"), result.rfind("二维码后面的正文"))

    def test_cta_and_disclaimer_stay_before_qr(self):
        html = """
        <p>正文主体</p>
        <div data-lead-cta="true"><p>结尾 CTA</p></div>
        <p>免责声明：不承诺放款结果。</p>
        """
        result = self._with_qr(html)

        qr_index = result.rfind("data-lead-qr")
        self.assertLess(result.rfind("结尾 CTA"), qr_index)
        self.assertLess(result.rfind("免责声明"), qr_index)

    def test_no_body_text_after_qr_module(self):
        html = "<p>正文</p><p>最后正文文本</p>"
        result = self._with_qr(html)
        tail = result[result.rfind("data-lead-qr"):]

        self.assertNotIn("最后正文文本", tail)
        self.assertIn("先看清楚自己属于", tail)

    def test_fallback_article_html_has_qr_at_end(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "services.wechat_lead_card_adapter.WECHAT_LEAD_QR_IMAGE",
            str(Path(tmpdir) / "lead_qr.png"),
        ):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            result = ArticleGenerationAgent.build_local_fallback("经营贷被拒后老板先查现金流")

        html = result["html"]
        self.assertGreater(html.rfind("data-lead-qr"), html.rfind("风险"))
        self.assertNotIn("老板", html[html.rfind("data-lead-qr"):])

class TitleGuardTestCase(unittest.TestCase):
    def test_incomplete_title_is_repaired(self):
        bad_title = "老板经营贷总被拒？这3个地方老板最容易忽略，银行为什么不"

        result = TitleGuard.sanitize_title(bad_title)

        self.assertEqual(result["title"], "经营贷总被拒？先查这3个地方")
        self.assertTrue(TitleGuard.inspect_title(result["title"])["qualified"])

    def test_repeated_owner_word_is_deduplicated(self):
        result = TitleGuard.sanitize_title("老板经营贷被拒？老板先查这3个地方")

        self.assertLessEqual(result["title"].count("老板"), 1)
        self.assertIn("经营贷", result["title"])
        self.assertTrue(TitleGuard.inspect_title(result["title"])["qualified"])

    def test_ai_tone_title_is_low_score(self):
        inspection = TitleGuard.inspect_title("企业经营贷申请关键事项深度解析")

        self.assertFalse(inspection["qualified"])
        self.assertLess(inspection["score"], 80)
        self.assertIn("ai_tone", inspection["reasons"])

    def test_long_title_is_shortened(self):
        long_title = "老板申请经营贷被拒以后到底应该怎么复盘银行审批逻辑并且提前准备全部资料"

        result = TitleGuard.sanitize_title(long_title)
        inspection = TitleGuard.inspect_title(result["title"])

        self.assertTrue(inspection["qualified"])
        self.assertLessEqual(inspection["cjk_length"], 36)

class WechatDraftContentGuardTestCase(unittest.TestCase):
    def setUp(self):
        self._old_qr_cache = publisher_module._lead_qr_wechat_image_url_cache
        publisher_module._lead_qr_wechat_image_url_cache = "https://mmbiz.qpic.cn/default-lead-qr.png"

    def tearDown(self):
        publisher_module._lead_qr_wechat_image_url_cache = self._old_qr_cache
    def _qr_patch(self, tmpdir: str):
        return patch("services.wechat_lead_card_adapter.WECHAT_LEAD_QR_IMAGE", str(Path(tmpdir) / "lead_qr.png"))

    def _long_publish_html(self, keyword: str = "publish-body-keyword") -> str:
        paragraphs = "".join(
            f"<p>{keyword} paragraph {i}: 经营贷文章主体内容，案例说明银行关注流水、征信、负债、用途和还款来源，老板需要先复盘资料，再决定如何优化申请顺序、额度方案和风险控制。</p>"
            for i in range(1, 10)
        )
        return f"<h2>案例拆解</h2>{paragraphs}<h2>解决建议</h2><p>{keyword} 申请前先做融资体检，避免正文被留资模块覆盖。</p>"

    def test_append_lead_qr_keeps_original_html_and_qr(self):
        html = "<h2>案例拆解</h2><p>正文关键词 A</p><p>正文关键词 B</p><p>正文关键词 C</p>"
        with tempfile.TemporaryDirectory() as tmpdir, self._qr_patch(tmpdir):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            result = append_lead_qr_at_end(html)

        self.assertIn("正文关键词 A", result)
        self.assertIn("正文关键词 C", result)
        self.assertIn("data-lead-qr", result)
        self.assertGreater(result.rfind("data-lead-qr"), result.rfind("正文关键词 C"))

    def test_existing_middle_qr_removed_without_dropping_body(self):
        html = """
        <p>正文关键词 A</p><div data-lead-qr="true"><img src="old.png"></div>
        <p>正文关键词 B</p><p>正文关键词 C</p>
        """
        with tempfile.TemporaryDirectory() as tmpdir, self._qr_patch(tmpdir):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            result = append_lead_qr_at_end(html)

        self.assertIn("正文关键词 A", result)
        self.assertIn("正文关键词 B", result)
        self.assertIn("正文关键词 C", result)
        self.assertEqual(result.count("data-lead-qr"), 1)
        self.assertGreater(result.rfind("data-lead-qr"), result.rfind("正文关键词 C"))

    def test_wechat_draft_payload_content_contains_article_body(self):
        article = {
            "id": 901,
            "title": "经营贷申请前检查",
            "summary": "摘要",
            "html_content": self._long_publish_html("正文关键词A"),
            "content": "",
            "cover_image": "",
            "cover_url": "",
        }
        captured = {}

        def fake_add_draft(articles):
            captured["article"] = articles[0]
            return "media-123"

        with tempfile.TemporaryDirectory() as tmpdir, self._qr_patch(tmpdir), patch(
            "wechat_api.publisher.ensure_thumb_media_id", return_value="thumb-123"
        ), patch("wechat_api.publisher.add_draft", side_effect=fake_add_draft), patch(
            "wechat_api.publisher._upload_content_images_for_wechat", side_effect=lambda html: html
        ):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            media_id = publisher_module.publish_single_article(article)

        content = captured["article"]["content"]
        self.assertEqual(media_id, "media-123")
        self.assertIn("paragraph 1", content)
        self.assertIn("案例拆解", content)
        self.assertIn("data-lead-qr", content)
        self.assertNotEqual(content.strip(), content[content.rfind("<div data-lead-qr"):].strip())
        self.assertEqual(captured["article"]["digest"], "摘要")

    def test_publish_content_uses_content_when_html_content_empty(self):
        article = {
            "id": 904,
            "title": "经营贷申请前检查",
            "summary": "摘要",
            "html_content": "",
            "content": "\n\n".join([f"content-body-keyword paragraph {i}: 经营贷文章主体内容，案例说明银行关注流水、征信、负债和用途，老板需要先做资料复盘，并根据真实经营数据准备解决方案和风险提醒。" for i in range(1, 22)]),
            "cover_image": "",
            "cover_url": "",
        }
        captured = {}

        def fake_add_draft(articles):
            captured["article"] = articles[0]
            return "media-content"

        with tempfile.TemporaryDirectory() as tmpdir, self._qr_patch(tmpdir), patch(
            "wechat_api.publisher.ensure_thumb_media_id", return_value="thumb-123"
        ), patch("wechat_api.publisher.add_draft", side_effect=fake_add_draft), patch(
            "wechat_api.publisher._upload_content_images_for_wechat", side_effect=lambda html: html
        ):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            media_id = publisher_module.publish_single_article(article)

        self.assertEqual(media_id, "media-content")
        self.assertIn("content-body-keyword", captured["article"]["content"])
        self.assertIn("data-lead-qr", captured["article"]["content"])

    def test_publish_content_prefers_valid_html_content(self):
        article = {
            "id": 905,
            "title": "经营贷申请前检查",
            "summary": "摘要",
            "html_content": self._long_publish_html("HTML正文关键词"),
            "content": "\n\n".join([f"content字段正文 第{i}段，银行审批会看真实经营数据。" for i in range(1, 12)]),
            "cover_image": "",
            "cover_url": "",
        }
        self.assertEqual(publisher_module._select_article_publish_content(article)[0], "html_content")

    def test_final_content_contains_body_keyword_and_qr(self):
        article = {"id": 906, "title": "经营贷申请前检查", "html_content": self._long_publish_html("完整正文关键词"), "cover_image": "", "cover_url": ""}
        with tempfile.TemporaryDirectory() as tmpdir, self._qr_patch(tmpdir), patch(
            "wechat_api.publisher._upload_content_images_for_wechat", side_effect=lambda html: html
        ):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            final_content, qr_meta = publisher_module._finalize_wechat_content_for_draft(article, article["html_content"], "html_content")

        qr_tail = final_content[final_content.rfind("data-lead-qr"):]
        self.assertIn("完整正文关键词", final_content)
        self.assertIn("data-lead-qr", final_content)
        self.assertNotIn("完整正文关键词", qr_tail)
        self.assertNotEqual(final_content.strip(), qr_tail.strip())

    def test_add_draft_payload_content_is_not_lead_module_only(self):
        article = {
            "id": 907,
            "title": "经营贷申请前检查",
            "summary": "摘要",
            "html_content": self._long_publish_html("payload正文关键词"),
            "content": "",
            "cover_image": "",
            "cover_url": "",
        }
        captured = {}

        def fake_add_draft(articles):
            captured["article"] = articles[0]
            return "media-payload"

        with tempfile.TemporaryDirectory() as tmpdir, self._qr_patch(tmpdir), patch(
            "wechat_api.publisher.ensure_thumb_media_id", return_value="thumb-123"
        ), patch("wechat_api.publisher.add_draft", side_effect=fake_add_draft), patch(
            "wechat_api.publisher._upload_content_images_for_wechat", side_effect=lambda html: html
        ):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            media_id = publisher_module.publish_single_article(article)

        content = captured["article"]["content"]
        self.assertEqual(media_id, "media-payload")
        self.assertIn("payload正文关键词", content)
        self.assertIn("data-lead-qr", content)
        self.assertNotEqual(content.strip(), content[content.rfind("<div data-lead-qr"):].strip())
    def test_final_content_is_longer_than_selected_content_after_qr_append(self):
        article = {"id": 908, "title": "经营贷申请前检查", "html_content": self._long_publish_html("length-body-keyword"), "cover_image": "", "cover_url": ""}
        selected_content = article["html_content"]
        with tempfile.TemporaryDirectory() as tmpdir, self._qr_patch(tmpdir), patch(
            "wechat_api.publisher._upload_content_images_for_wechat", side_effect=lambda html: html
        ):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            final_content, qr_meta = publisher_module._finalize_wechat_content_for_draft(article, selected_content, "html_content")

        self.assertIn("length-body-keyword", final_content)
        self.assertTrue(publisher_module.has_lead_qr(final_content))
        self.assertGreater(len(final_content), len(selected_content))
        self.assertGreater(final_content.rfind("data-lead-qr"), final_content.rfind("length-body-keyword"))

    def test_add_draft_payload_content_equals_final_content(self):
        article = {
            "id": 909,
            "title": "经营贷申请前检查",
            "summary": "摘要",
            "html_content": self._long_publish_html("payload-equals-body"),
            "content": "",
            "cover_image": "",
            "cover_url": "",
        }
        final_content = self._long_publish_html("payload-equals-body final") + "<section data-role=\"lead-qr\" data-lead-qr=\"true\"><p>企业融资体检扫码</p><img src=\"https://mmbiz.qpic.cn/final.png\"></section>"
        captured = {}

        def fake_add_draft(articles):
            captured["article"] = articles[0]
            return "media-final"

        with patch("wechat_api.publisher.ensure_thumb_media_id", return_value="thumb-123"), patch(
            "wechat_api.publisher._finalize_wechat_content_for_draft", return_value=(final_content, {"qr_img_src": "https://mmbiz.qpic.cn/final.png", "qr_img_src_type": "wechat_url"})
        ), patch("wechat_api.publisher.add_draft", side_effect=fake_add_draft):
            media_id = publisher_module.publish_single_article(article)

        self.assertEqual(media_id, "media-final")
        self.assertEqual(captured["article"]["content"], final_content)

    def test_missing_qr_configuration_blocks_publish_before_add_draft(self):
        article = {"id": 910, "title": "经营贷申请前检查", "html_content": self._long_publish_html("missing-qr-body"), "cover_image": "", "cover_url": ""}
        publisher_module._lead_qr_wechat_image_url_cache = ""
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "services.wechat_lead_card_adapter.WECHAT_LEAD_QR_IMAGE",
            str(Path(tmpdir) / "missing.png"),
        ), patch("wechat_api.publisher._upload_content_images_for_wechat", side_effect=lambda html: html), self.assertLogs(
            "wechat_api.publisher", level="WARNING"
        ) as logs, self.assertRaisesRegex(ValueError, "二维码图片未配置"):
            publisher_module._finalize_wechat_content_for_draft(article, article["html_content"], "html_content")

        self.assertTrue(any("publish-lead-qr-image-missing" in line for line in logs.output))
    def test_qr_only_final_content_blocks_push(self):
        article = {
            "id": 902,
            "title": "异常文章",
            "summary": "摘要",
            "html_content": "<div data-lead-qr=\"true\"><p>如果你最近准备申请经营贷、续贷、降息或提高额度，可以扫码做一次企业融资体检。</p><img src=\"old.png\"></div>",
            "content": "",
            "cover_image": "",
            "cover_url": "",
        }
        with tempfile.TemporaryDirectory() as tmpdir, self._qr_patch(tmpdir), patch(
            "wechat_api.publisher.ensure_thumb_media_id", return_value="thumb-123"
        ), patch("wechat_api.publisher.add_draft") as add_draft, patch(
            "wechat_api.publisher._upload_content_images_for_wechat", side_effect=lambda html: html
        ):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            media_id = publisher_module.publish_single_article(article)

        self.assertIsNone(media_id)
        add_draft.assert_not_called()

    def test_preview_like_article_not_much_shorter_before_push(self):
        html = self._long_publish_html("preview-body-keyword")
        article = {"id": 903, "title": "正常文章", "html_content": html, "cover_image": "", "cover_url": ""}
        with tempfile.TemporaryDirectory() as tmpdir, self._qr_patch(tmpdir), patch(
            "wechat_api.publisher._upload_content_images_for_wechat", side_effect=lambda content: content
        ):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            final_content, qr_meta = publisher_module._finalize_wechat_content_for_draft(article, html)

        self.assertIn("preview-body-keyword", final_content)
        self.assertIn("案例拆解", final_content)
        self.assertGreater(len(final_content), len(html) * 0.8)

    def test_final_content_uses_uploadimg_url_for_qr_image(self):
        article = {"id": 911, "title": "经营贷申请前检查", "html_content": self._long_publish_html("uploadimg-body"), "cover_image": "", "cover_url": ""}
        publisher_module._lead_qr_wechat_image_url_cache = ""
        with tempfile.TemporaryDirectory() as tmpdir, self._qr_patch(tmpdir), patch(
            "wechat_api.publisher.upload_content_image", return_value="https://mmbiz.qpic.cn/uploaded-lead-qr.png"
        ) as upload_mock, patch("wechat_api.publisher._upload_content_images_for_wechat", side_effect=lambda html: html):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            final_content, qr_meta = publisher_module._finalize_wechat_content_for_draft(article, article["html_content"], "html_content")

        upload_mock.assert_called_once()
        self.assertIn("uploadimg-body", final_content)
        self.assertIn('data-role="lead-qr"', final_content)
        self.assertIn('src="https://mmbiz.qpic.cn/uploaded-lead-qr.png"', final_content)
        self.assertNotIn('src="/static/', final_content)
        self.assertNotIn('src="data:image', final_content)
        self.assertGreater(final_content.rfind("data-role=\"lead-qr\""), final_content.rfind("uploadimg-body"))

    def test_cached_wechat_qr_url_skips_uploadimg(self):
        article = {"id": 912, "title": "经营贷申请前检查", "html_content": self._long_publish_html("cached-qr-body"), "cover_image": "", "cover_url": ""}
        publisher_module._lead_qr_wechat_image_url_cache = "https://mmbiz.qpic.cn/cached-lead-qr.png"
        with tempfile.TemporaryDirectory() as tmpdir, self._qr_patch(tmpdir), patch(
            "wechat_api.publisher.upload_content_image"
        ) as upload_mock, patch("wechat_api.publisher._upload_content_images_for_wechat", side_effect=lambda html: html):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            final_content, qr_meta = publisher_module._finalize_wechat_content_for_draft(article, article["html_content"], "html_content")

        upload_mock.assert_not_called()
        self.assertIn('src="https://mmbiz.qpic.cn/cached-lead-qr.png"', final_content)
        self.assertIn("cached-qr-body", final_content)

    def test_debug_file_matches_add_draft_payload_content(self):
        article = {
            "id": 913,
            "title": "经营贷申请前检查",
            "summary": "摘要",
            "html_content": self._long_publish_html("debug-payload-body"),
            "content": "",
            "cover_image": "",
            "cover_url": "",
        }
        captured = {}

        def fake_add_draft(articles):
            captured["article"] = articles[0]
            return "media-debug"

        with tempfile.TemporaryDirectory() as tmpdir, self._qr_patch(tmpdir), patch(
            "wechat_api.publisher.PUBLISH_DEBUG_DIR", Path(tmpdir)
        ), patch("wechat_api.publisher.ensure_thumb_media_id", return_value="thumb-123"), patch(
            "wechat_api.publisher.add_draft", side_effect=fake_add_draft
        ), patch("wechat_api.publisher._upload_content_images_for_wechat", side_effect=lambda html: html):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            media_id = publisher_module.publish_single_article(article)
            debug_html = Path(tmpdir, "wechat_publish_debug_article_913.html").read_text(encoding="utf-8")

        self.assertEqual(media_id, "media-debug")
        self.assertEqual(debug_html, captured["article"]["content"])
        self.assertIn("debug-payload-body", debug_html)
        self.assertIn("data-lead-qr", debug_html)

    def test_body_without_qr_returned_from_finalizer_blocks_add_draft(self):
        article = {
            "id": 914,
            "title": "经营贷申请前检查",
            "summary": "摘要",
            "html_content": self._long_publish_html("body-only-final"),
            "content": "",
            "cover_image": "",
            "cover_url": "",
        }
        with patch("wechat_api.publisher.ensure_thumb_media_id", return_value="thumb-123"), patch(
            "wechat_api.publisher._finalize_wechat_content_for_draft", return_value=(article["html_content"], {})
        ), patch("wechat_api.publisher.add_draft") as add_draft:
            media_id = publisher_module.publish_single_article(article)

        self.assertIsNone(media_id)
        add_draft.assert_not_called()
    def test_build_lead_qr_html_contains_img(self):
        html = publisher_module.build_lead_qr_html("https://mmbiz.qpic.cn/build-lead-qr.png")

        self.assertIn('data-role="lead-qr"', html)
        self.assertIn("<img", html)
        self.assertIn('src="https://mmbiz.qpic.cn/build-lead-qr.png"', html)
        self.assertIn("企业融资体检", html)

    def test_build_lead_qr_html_without_image_returns_empty(self):
        html = publisher_module.build_lead_qr_html("")

        self.assertEqual(html, "")
        self.assertNotIn("企业融资体检", html)

    def test_final_content_without_img_blocks_push(self):
        article = {
            "id": 915,
            "title": "经营贷申请前检查",
            "summary": "摘要",
            "html_content": self._long_publish_html("no-img-final"),
            "content": "",
            "cover_image": "",
            "cover_url": "",
        }
        final_without_img = article["html_content"] + '<section data-role="lead-qr" data-lead-qr="true"><p>企业融资体检，扫码了解。</p></section>'
        with patch("wechat_api.publisher.ensure_thumb_media_id", return_value="thumb-123"), patch(
            "wechat_api.publisher._finalize_wechat_content_for_draft", return_value=(final_without_img, {})
        ), patch("wechat_api.publisher.add_draft") as add_draft:
            media_id = publisher_module.publish_single_article(article)

        self.assertIsNone(media_id)
        add_draft.assert_not_called()

    def test_payload_content_contains_body_lead_copy_and_qr_img(self):
        article = {
            "id": 916,
            "title": "经营贷申请前检查",
            "summary": "摘要",
            "html_content": self._long_publish_html("payload-img-body"),
            "content": "",
            "cover_image": "",
            "cover_url": "",
        }
        captured = {}

        def fake_add_draft(articles):
            captured["article"] = articles[0]
            return "media-img"

        with tempfile.TemporaryDirectory() as tmpdir, self._qr_patch(tmpdir), patch(
            "wechat_api.publisher.ensure_thumb_media_id", return_value="thumb-123"
        ), patch("wechat_api.publisher.add_draft", side_effect=fake_add_draft), patch(
            "wechat_api.publisher._upload_content_images_for_wechat", side_effect=lambda html: html
        ):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            media_id = publisher_module.publish_single_article(article)

        content = captured["article"]["content"]
        self.assertEqual(media_id, "media-img")
        self.assertIn("payload-img-body", content)
        self.assertIn("企业融资体检", content)
        self.assertIn("<img", content)
        self.assertIn("https://mmbiz.qpic.cn/default-lead-qr.png", content)
        self.assertNotIn('src="/static/', content)
        self.assertNotIn('src="data:image', content)

    def test_finalize_wechat_content_returns_qr_meta_tuple(self):
        article = {"id": 917, "title": "经营贷申请前检查", "html_content": self._long_publish_html("tuple-meta-body"), "cover_image": "", "cover_url": ""}
        publisher_module._lead_qr_wechat_image_url_cache = ""
        with tempfile.TemporaryDirectory() as tmpdir, self._qr_patch(tmpdir), patch(
            "wechat_api.publisher.upload_content_image", return_value="https://mmbiz.qpic.cn/tuple-meta-qr.png"
        ), patch("wechat_api.publisher._upload_content_images_for_wechat", side_effect=lambda html: html):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            final_content, qr_meta = publisher_module._finalize_wechat_content_for_draft(article, article["html_content"], "html_content")

        self.assertIn("tuple-meta-body", final_content)
        self.assertIsInstance(qr_meta, dict)
        self.assertEqual(qr_meta["qr_img_src"], "https://mmbiz.qpic.cn/tuple-meta-qr.png")
        self.assertEqual(qr_meta["qr_img_src_type"], "wechat_url")
        self.assertTrue(qr_meta["qr_upload_success"])

    def test_validate_publish_payload_uses_qr_meta_wechat_url(self):
        article = {"id": 918, "title": "经营贷申请前检查"}
        final_content = self._long_publish_html("meta-pass-body") + '<section data-role="lead-qr" data-lead-qr="true"><p>企业融资体检</p><img src="broken-local.png"></section>'
        qr_meta = {"qr_img_src": "https://mmbiz.qpic.cn/meta-pass-qr.png", "qr_img_src_type": "wechat_url"}
        with patch("wechat_api.publisher.validate_wechat_config", return_value=None):
            publisher_module._validate_publish_payload_before_add_draft(article, "thumb-123", final_content, qr_meta)

    def test_validate_publish_payload_allows_missing_html_img_when_qr_meta_has_url(self):
        article = {"id": 919, "title": "经营贷申请前检查"}
        final_content = self._long_publish_html("meta-only-body") + '<section data-role="lead-qr" data-lead-qr="true"><p>企业融资体检</p></section>'
        qr_meta = {"qr_img_src": "https://mmbiz.qpic.cn/meta-only-qr.png", "qr_img_src_type": "wechat_url"}
        with patch("wechat_api.publisher.validate_wechat_config", return_value=None):
            publisher_module._validate_publish_payload_before_add_draft(article, "thumb-123", final_content, qr_meta)

    def test_validate_publish_payload_without_qr_meta_or_html_img_fails(self):
        article = {"id": 920, "title": "经营贷申请前检查"}
        final_content = self._long_publish_html("missing-meta-body")
        with patch("wechat_api.publisher.validate_wechat_config", return_value=None), self.assertRaisesRegex(
            publisher_module.WechatPublishError, "缺少二维码 img"
        ):
            publisher_module._validate_publish_payload_before_add_draft(article, "thumb-123", final_content, None)
class ArticleGenerationTaskTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = os.path.join(tempfile.gettempdir(), f"article_generation_task_{uuid.uuid4().hex}")
        os.makedirs(self.temp_dir, exist_ok=False)
        self.original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir, "test_articles.db")
        self._init_schema()
        app.config.update(TESTING=True)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "admin"
            session["role"] = "admin"
            session["role_display"] = "管理员"

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _init_schema(self):
        conn = database.get_db()
        try:
            conn.execute(
                """
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    content TEXT,
                    summary TEXT,
                    cover_url TEXT,
                    cover_image TEXT,
                    cover_status TEXT,
                    cover_prompt TEXT,
                    source_name TEXT,
                    source_url TEXT,
                    tags TEXT,
                    status TEXT,
                    review_status TEXT,
                    publish_status TEXT,
                    is_original INTEGER,
                    html_content TEXT,
                    source_article_id INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE cover_generation_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER,
                    status TEXT,
                    task_type TEXT,
                    model TEXT,
                    prompt TEXT,
                    style TEXT,
                    created_at DATETIME DEFAULT (datetime('now','localtime'))
                )
                """
            )
            conn.commit()
            database.init_content_growth_tables(conn)
        finally:
            conn.close()

    def test_saved_article_title_cover_and_content_are_guarded_consistently(self):
        bad_title = "老板经营贷总被拒？这3个地方老板最容易忽略，银行为什么不"
        article = {
            "title": bad_title,
            "title_candidates": [bad_title, "经营贷总被拒？先查这3个地方"],
            "final_title": bad_title,
            "markdown": f"# {bad_title}\n\n正文段落A\n\n正文段落B",
            "summary": "摘要",
            "tags": ["经营贷"],
            "html": f"<section><h1>{bad_title}</h1><p>正文段落A</p><p>正文段落B</p></section>",
        }

        result = TemplateService.create_agent_article(article, "经营贷")
        self.assertTrue(result["ok"])

        conn = database.get_db()
        try:
            saved = conn.execute("SELECT title, content, html_content FROM articles WHERE id=?", (result["article_id"],)).fetchone()
        finally:
            conn.close()

        final_title = "经营贷总被拒？先查这3个地方"
        self.assertEqual(saved["title"], final_title)
        self.assertIn(final_title, saved["content"])
        self.assertIn(final_title, saved["html_content"])
        self.assertNotIn(bad_title, saved["content"])
        self.assertNotIn(bad_title, saved["html_content"])
    def test_create_article_generation_task_endpoint_returns_task_id_immediately(self):
        started = time.perf_counter()
        with patch("web_ui.app._start_article_generation_background") as start_background:
            response = self.client.post(
                "/api/article-generation-tasks",
                data={"keyword": "企业经营贷", "length": "medium"},
            )
        elapsed = time.perf_counter() - started
        data = response.get_json()

        self.assertEqual(response.status_code, 202)
        self.assertTrue(data["task_id"])
        self.assertEqual(data["status"], "queued")
        self.assertLess(elapsed, 1.0)
        start_background.assert_called_once_with(data["task_id"])

    def test_ai_timeout_task_falls_back_without_failed_status(self):
        task = ArticleGenerationTaskService.create_task({"keyword": "企业经营贷超时"})
        ai_failure = {
            "ok": False,
            "error_type": "AI_TIMEOUT",
            "error_message": "AI 调用超时",
        }
        fallback = {
            "ok": True,
            "title": "超时兜底标题",
            "markdown": "超时兜底正文",
            "summary": "摘要",
            "tags": ["企业融资"],
            "html": "<p>超时兜底正文</p>",
            "fallback_used": True,
        }
        with patch("services.article_generation_task_service.ArticleGenerationAgent.generate", return_value=ai_failure), patch(
            "services.article_generation_task_service.ArticleGenerationAgent.build_local_fallback",
            return_value=fallback,
        ):
            result = ArticleGenerationTaskService.run_task(task["task_id"])

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["fallback_used"])
        self.assertTrue(result["article_id"])

    def test_ai_failure_sets_fallback_used_and_saves_draft(self):
        task = ArticleGenerationTaskService.create_task({"keyword": "银行拒贷后老板先查现金流"})
        ai_failure = {"ok": False, "error_type": "AI_CONNECTION_ERROR", "error_message": "AI 连接失败"}
        fallback = {
            "ok": True,
            "title": "本地兜底标题",
            "markdown": "本地兜底正文",
            "summary": "摘要",
            "tags": ["企业融资"],
            "html": "<p>本地兜底正文</p>",
            "fallback_used": True,
        }
        with patch("services.article_generation_task_service.ArticleGenerationAgent.generate", return_value=ai_failure), patch(
            "services.article_generation_task_service.ArticleGenerationAgent.build_local_fallback",
            return_value=fallback,
        ):
            result = ArticleGenerationTaskService.run_task(task["task_id"])

        conn = database.get_db()
        try:
            article = conn.execute("SELECT * FROM articles WHERE id=?", (result["article_id"],)).fetchone()
        finally:
            conn.close()

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["fallback_used"])
        self.assertEqual(article["title"], "本地兜底标题")
        self.assertEqual(article["content"], "本地兜底正文")

    def test_task_success_returns_article_id_and_url(self):
        task = ArticleGenerationTaskService.create_task({"keyword": "企业融资规划"})
        generated = {
            "ok": True,
            "title": "AI 生成标题",
            "markdown": "AI 正文",
            "summary": "摘要",
            "tags": ["企业融资"],
            "html": "<p>AI 正文</p>",
        }
        with patch("services.article_generation_task_service.ArticleGenerationAgent.generate", return_value=generated):
            result = ArticleGenerationTaskService.run_task(task["task_id"])

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["article_id"])
        self.assertEqual(result["article_url"], f"/article/{result['article_id']}")
        self.assertFalse(result["fallback_used"])

    def test_agent_generate_article_page_no_long_ai_wait(self):
        with patch("web_ui.app._start_article_generation_background") as start_background, patch(
            "web_ui.app.ArticleGenerationAgent.generate",
            side_effect=AssertionError("route must not call AI synchronously"),
        ):
            response = self.client.post("/agent-generate-article", data={"keyword": "经营贷申请"})

        data = response.get_json()
        self.assertEqual(response.status_code, 202)
        self.assertTrue(data["task_id"])
        start_background.assert_called_once_with(data["task_id"])

    def test_rewrite_for_growth_optimized_draft_has_qr_at_end(self):
        conn = database.get_db()
        try:
            cursor = conn.execute(
                """
                INSERT INTO articles
                (title, content, summary, source_name, source_url, tags, status, review_status, publish_status, is_original, html_content)
                VALUES (?, ?, ?, ?, ?, ?, 'draft', 'draft', 'not_ready', 1, '')
                """,
                ("经营贷被拒", "原正文", "摘要", "沪上银原创", "", "企业融资"),
            )
            article_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()

        proposal = {
            "optimized_title": "经营贷被拒先查现金流",
            "optimized_intro": "新开头",
            "optimized_outline": ["结构"],
            "optimized_cta": "结尾 CTA",
            "optimized_content": "<p>优化正文</p><p>免责声明：不承诺放款。</p>",
            "growth_reason": "CTA 优化",
        }
        ArticleGrowthAnalyzer._save_rewrite_proposal(article_id, proposal)

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "services.wechat_lead_card_adapter.WECHAT_LEAD_QR_IMAGE",
            str(Path(tmpdir) / "lead_qr.png"),
        ):
            Path(tmpdir, "lead_qr.png").write_bytes(b"fake-png")
            result = ArticleGrowthAnalyzer.create_optimized_draft(article_id)

        conn = database.get_db()
        try:
            draft = conn.execute("SELECT html_content FROM articles WHERE id=?", (result["new_article_id"],)).fetchone()
        finally:
            conn.close()

        html = draft["html_content"]
        self.assertTrue(result["ok"])
        self.assertGreater(html.rfind("data-lead-qr"), html.rfind("免责声明"))
        self.assertNotIn("优化正文", html[html.rfind("data-lead-qr"):])
    def test_frontend_polls_task_status_instead_of_waiting_for_ai(self):
        template_path = Path(__file__).resolve().parents[1] / "web_ui" / "templates" / "templates.html"
        template = template_path.read_text(encoding="utf-8")

        self.assertIn('id="agent-generate-form"', template)
        self.assertIn("/api/article-generation-tasks", template)
        self.assertIn("setInterval", template)
        self.assertIn("2000", template)
        self.assertIn("agent-generation-status", template)

class ContentGrowthRoutesTestCase(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "admin"
            session["role"] = "admin"
            session["role_display"] = "管理员"

    def test_dashboard_empty_data_returns_200(self):
        empty = {
            "ok": True,
            "articles": [],
            "summary": dict(ArticleGrowthAnalyzer.SUMMARY_DEFAULTS),
            "topics": [],
            "error": None,
        }
        with patch.object(ArticleGrowthAnalyzer, "get_dashboard_data", return_value=empty):
            response = self.client.get("/content-growth/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn("暂无文章增长数据", response.get_data(as_text=True))

    def test_dashboard_database_exception_returns_200(self):
        with patch.object(
            ArticleGrowthAnalyzer,
            "get_dashboard_data",
            side_effect=RuntimeError("database failed"),
        ):
            response = self.client.get("/content-growth/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn("已自动降级展示", response.get_data(as_text=True))

    def test_dashboard_disabled_returns_200(self):
        with patch("web_ui.app.CONTENT_GROWTH_ENABLED", False):
            response = self.client.get("/content-growth/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn("文章增长中心未启用", response.get_data(as_text=True))

    def test_missing_article_analyze_returns_json_not_500(self):
        response = self.client.post("/article/999999999/growth-analyze", json={})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content_type, "application/json")
        self.assertFalse(response.get_json()["ok"])

    def test_rewrite_route_exception_returns_fallback_json(self):
        with patch.object(
            ArticleGrowthAnalyzer,
            "rewrite_for_growth",
            side_effect=RuntimeError("AI failed"),
        ):
            response = self.client.post("/article/1/rewrite-for-growth", json={})

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(data["ok"])
        self.assertEqual(len(data["new_titles"]), 3)

    def test_manual_metrics_update_endpoint(self):
        expected = {
            "ok": True,
            "article_id": 12,
            "metrics": {"view_count": 88, "deal_count": 2},
            "growth_score": 76,
        }
        with patch.object(ArticleGrowthAnalyzer, "update_metrics", return_value=expected) as update:
            response = self.client.post(
                "/article/12/growth-metrics/update",
                json={"view_count": 88, "deal_count": 2},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])
        update.assert_called_once_with(12, {"view_count": 88, "deal_count": 2})

    def test_rewrite_generation_does_not_overwrite_original_article(self):
        original = {"id": 3, "title": "原始标题", "content": "原始正文", "status": "published"}
        analysis = {
            "ok": True,
            "title": original["title"],
            "view_count": 10,
            "failure_reasons": ["标题点击弱"],
            "title_score": {"optimized_titles": ["优化标题"]},
        }
        with patch.object(ArticleGrowthAnalyzer, "_get_article", return_value=original), patch.object(
            ArticleGrowthAnalyzer,
            "analyze_article_growth",
            return_value=analysis,
        ), patch.object(
            ArticleGrowthAnalyzer,
            "_save_rewrite_proposal",
            return_value=True,
        ):
            result = ArticleGrowthAnalyzer.rewrite_for_growth(3)

        self.assertTrue(result["ok"])
        self.assertFalse(result["applied"])
        self.assertTrue(result["is_published"])
        self.assertEqual(result["available_actions"], ["create_new_draft"])
        self.assertEqual(result["original_title"], "原始标题")
        self.assertEqual(original["content"], "原始正文")

    def test_recommended_topic_generate_article_endpoint(self):
        generated = {
            "ok": True,
            "title": "老板经营贷被拒，先查这3点",
            "markdown": "正文",
            "summary": "摘要",
            "tags": ["企业融资"],
            "html": "<p>正文</p>",
        }
        with patch("web_ui.app.ArticleGenerationAgent.generate", return_value=generated) as generate, patch(
            "web_ui.app.TemplateService.create_agent_article",
            return_value={"ok": True, "article_id": 321},
        ) as save:
            response = self.client.post(
                "/content-growth/topic/generate",
                json={"suggested_title": "老板经营贷被拒，先查这3点"},
            )

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["article_id"], 321)
        generate.assert_called_once()
        save.assert_called_once()

    def test_ai_connection_failure_creates_local_fallback_draft(self):
        ai_failure = {
            "ok": False,
            "error_type": "AI_CONNECTION_ERROR",
            "error_message": "服务器无法连接 AI 服务，请检查 BASE_URL 或服务器网络",
        }
        fallback = {
            "ok": True,
            "title": "本地兜底标题",
            "markdown": "本地兜底正文",
            "summary": "摘要",
            "tags": ["企业融资"],
            "html": "<p>本地兜底正文</p>",
            "fallback_used": True,
        }
        with patch("web_ui.app.ArticleGenerationAgent.generate", return_value=ai_failure), patch(
            "web_ui.app.ArticleGenerationAgent.build_local_fallback",
            return_value=fallback,
        ), patch(
            "web_ui.app.TemplateService.create_agent_article",
            return_value={"ok": True, "article_id": 654},
        ):
            response = self.client.post(
                "/content-growth/topic/generate",
                json={"suggested_title": "银行拒贷后，老板先别急着换银行"},
            )

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertTrue(data["fallback_used"])
        self.assertEqual(data["article_id"], 654)
        self.assertIn("本地模板生成草稿", data["message"])

    def test_recommended_topic_generate_accepts_title_only(self):
        generated = {"ok": True, "title": "只有标题也能生成", "markdown": "正文", "summary": "摘要", "tags": ["企业融资"], "html": "<p>正文</p>"}
        with patch("web_ui.app.ArticleGenerationAgent.generate", return_value=generated) as generate, patch(
            "web_ui.app.TemplateService.create_agent_article", return_value={"ok": True, "article_id": 322}
        ):
            response = self.client.post("/content-growth/topic/generate", json={"title": "只有标题也能生成"})

        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["article_id"], 322)
        self.assertEqual(data["article_url"], "/article/322")
        self.assertIn("只有标题也能生成", generate.call_args.kwargs["keyword"])

    def test_recommended_topic_generate_uses_fallback_title_when_missing(self):
        generated = {"ok": True, "title": "兜底标题", "markdown": "正文", "summary": "摘要", "tags": ["企业融资"], "html": "<p>正文</p>"}
        with patch("web_ui.app.ArticleGenerationAgent.generate", return_value=generated) as generate, patch(
            "web_ui.app.TemplateService.create_agent_article", return_value={"ok": True, "article_id": 323}
        ):
            response = self.client.post("/content-growth/topic/generate", json={})

        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["article_id"], 323)
        self.assertEqual(generate.call_args.kwargs["keyword"], "经营贷被拒？先查这3个地方")

    def test_recommended_topic_ai_exception_falls_back_and_creates_article(self):
        fallback = {"ok": True, "title": "异常兜底", "markdown": "本地正文", "summary": "摘要", "tags": ["企业融资"], "html": "<p>本地正文</p>", "fallback_used": True}
        with patch("web_ui.app.ArticleGenerationAgent.generate", side_effect=TimeoutError("AI 超时")), patch(
            "web_ui.app.ArticleGenerationAgent.build_local_fallback", return_value=fallback
        ) as fallback_builder, patch(
            "web_ui.app.TemplateService.create_agent_article", return_value={"ok": True, "article_id": 324}
        ):
            response = self.client.post("/content-growth/topic/generate", json={"article_angle": "申请经营贷前先体检"})

        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["fallback_used"])
        self.assertEqual(data["article_url"], "/article/324")
        fallback_builder.assert_called_once()

    def test_recommended_topic_save_failure_returns_error_message(self):
        generated = {"ok": True, "title": "保存失败标题", "markdown": "正文", "summary": "摘要", "tags": ["企业融资"], "html": "<p>正文</p>"}
        with patch("web_ui.app.ArticleGenerationAgent.generate", return_value=generated), patch(
            "web_ui.app.TemplateService.create_agent_article", return_value={"ok": False, "error_message": "数据库写入失败"}
        ):
            response = self.client.post("/content-growth/topic/generate", json={"suggested_title": "保存失败标题"})

        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error_type"], "SAVE_FAILED")
        self.assertEqual(data["error_message"], "数据库写入失败")

    def test_recommended_topic_real_save_contains_required_article_fields(self):
        temp_dir = tempfile.mkdtemp(prefix="topic_generate_article_")
        old_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(temp_dir, "articles.db")
        conn = database.get_db()
        try:
            conn.execute(
                """
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    content TEXT,
                    summary TEXT,
                    cover_url TEXT,
                    cover_image TEXT,
                    cover_status TEXT,
                    cover_prompt TEXT,
                    source_name TEXT,
                    source_url TEXT,
                    tags TEXT,
                    status TEXT,
                    review_status TEXT,
                    publish_status TEXT,
                    is_original INTEGER,
                    html_content TEXT,
                    created_at DATETIME DEFAULT (datetime('now','localtime')),
                    updated_at DATETIME DEFAULT (datetime('now','localtime'))
                )
                """
            )
            conn.commit()
        finally:
            conn.close()
        generated = {
            "ok": True,
            "title": "真实保存标题",
            "markdown": "真实保存正文",
            "summary": "真实摘要",
            "tags": ["企业融资"],
            "html": "<p>真实保存正文</p>",
        }
        try:
            with patch("web_ui.app.ArticleGenerationAgent.generate", return_value=generated):
                response = self.client.post("/content-growth/topic/generate", json={"suggested_title": "真实保存标题"})
            data = response.get_json()
            self.assertTrue(data["success"])
            conn = database.get_db()
            try:
                row = conn.execute("SELECT title, content, summary, source_name, status, html_content FROM articles WHERE id=?", (data["article_id"],)).fetchone()
            finally:
                conn.close()
            self.assertIsNotNone(row)
            self.assertEqual(row[1], "真实保存正文")
            self.assertEqual(row[2], "真实摘要")
            self.assertIn("沪上银", row[3])
            self.assertEqual(row[4], "draft")
            self.assertIn("真实保存正文", row[5])
        finally:
            database.DB_PATH = old_db_path
            shutil.rmtree(temp_dir, ignore_errors=True)
    def test_frontend_contains_fallback_message(self):
        template_path = Path(__file__).resolve().parents[1] / "web_ui" / "templates" / "content_growth_dashboard.html"
        template = template_path.read_text(encoding="utf-8")

        self.assertIn("AI 不可用", template)
        self.assertIn("data.error_message", template)
        self.assertIn("生成中", template)

    def test_ai_provider_health_returns_structured_result(self):
        health = {
            "success": False,
            "provider": "OpenAI-compatible",
            "base_url": "https://api.example.com/v1",
            "model": "test-model",
            "api_key_loaded": True,
            "api_key_masked": "sk-t****abcd",
            "latency_ms": 123,
            "error_type": "AI_CONNECTION_ERROR",
            "error_message": "服务器无法连接 AI 服务，请检查 BASE_URL 或服务器网络",
        }
        with patch("web_ui.app.ArticleGenerationAgent.health_check", return_value=health):
            response = self.client.get("/debug/ai-provider/health")

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["error_type"], "AI_CONNECTION_ERROR")
        self.assertNotIn("完整密钥", str(data))

    def test_create_draft_endpoint_returns_new_article(self):
        result = {
            "ok": True,
            "success": True,
            "new_article_id": 456,
            "redirect_url": "/article/456",
        }
        with patch.object(ArticleGrowthAnalyzer, "create_optimized_draft", return_value=result):
            response = self.client.post("/article/10/growth-rewrite/create-draft", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["new_article_id"], 456)

    def test_apply_endpoint_rejects_published_article(self):
        result = {
            "ok": False,
            "success": False,
            "error": "已发表文章不能直接覆盖，请生成优化版新草稿",
        }
        with patch.object(ArticleGrowthAnalyzer, "apply_optimized_to_draft", return_value=result):
            response = self.client.post("/article/10/growth-rewrite/apply", json={})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["success"])
        self.assertIn("不能直接覆盖", response.get_json()["error"])

    def test_template_renders_with_empty_articles_and_summary(self):
        with app.test_request_context("/content-growth/dashboard"):
            html = render_template(
                "content_growth_dashboard.html",
                articles=[],
                summary={},
                topics=[],
                error=None,
                growth_enabled=True,
                low_traffic_threshold=50,
            )

        self.assertIn("暂无文章增长数据", html)
        self.assertIn("总阅读量", html)

    def test_system_health_always_returns_json(self):
        response = self.client.get("/system/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")
        self.assertIn("errors", response.get_json())

    def test_system_health_database_failure_still_returns_json(self):
        with patch("web_ui.app.get_db", side_effect=RuntimeError("db unavailable")), patch(
            "web_ui.app.init_content_growth_tables",
            return_value=False,
        ), patch.object(
            ArticleGrowthAnalyzer,
            "get_dashboard_data",
            return_value=ArticleGrowthAnalyzer._dashboard_result(),
        ):
            response = self.client.get("/system/health")

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(data["ok"])
        self.assertEqual(data["db"], "error")


class ContentGrowthRewriteIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        conn = sqlite3.connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                summary TEXT,
                source_name TEXT,
                source_url TEXT,
                tags TEXT,
                status TEXT DEFAULT 'draft',
                review_status TEXT DEFAULT 'draft',
                publish_status TEXT DEFAULT 'not_ready',
                is_original INTEGER DEFAULT 0,
                html_content TEXT,
                source_article_id INTEGER,
                created_at DATETIME DEFAULT (datetime('now','localtime')),
                updated_at DATETIME DEFAULT (datetime('now','localtime'))
            );
            """
        )
        conn.execute(SQLITE_CONTENT_GROWTH_CREATE_SQL)
        conn.execute(
            "INSERT INTO articles (title, content, status) VALUES (?,?,?)",
            ("已发表原文", "原始正文", "published"),
        )
        conn.execute(
            "INSERT INTO articles (title, content, status) VALUES (?,?,?)",
            ("草稿原文", "草稿正文", "draft"),
        )
        for article_id, optimized_title in ((1, "已发表优化标题"), (2, "草稿优化标题")):
            conn.execute(
                """
                INSERT INTO article_growth_metrics
                (article_id, rewrite_titles, rewrite_intro, rewrite_outline,
                 rewrite_cta, optimized_content, growth_reason)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    article_id,
                    f'["{optimized_title}"]',
                    "优化开头",
                    '["结构一", "结构二"]',
                    "优化 CTA",
                    "优化后的完整正文",
                    "阅读量偏低",
                ),
            )
        conn.commit()
        conn.close()

        def connection_factory():
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            return connection

        self.connection_factory = connection_factory
        self.db_patch = patch(
            "services.article_growth_analyzer.get_db",
            side_effect=self.connection_factory,
        )
        self.storage_patch = patch.object(
            ArticleGrowthAnalyzer,
            "ensure_storage",
            return_value=True,
        )
        self.db_patch.start()
        self.storage_patch.start()

    def tearDown(self):
        self.storage_patch.stop()
        self.db_patch.stop()
        try:
            os.remove(self.db_path)
        except PermissionError:
            pass

    def test_published_create_draft_generates_new_linked_article(self):
        result = ArticleGrowthAnalyzer.create_optimized_draft(1)

        self.assertTrue(result["ok"])
        conn = self.connection_factory()
        try:
            source = conn.execute("SELECT title, content FROM articles WHERE id=1").fetchone()
            new_article = conn.execute(
                "SELECT title, content, status, source_article_id FROM articles WHERE id=?",
                (result["new_article_id"],),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(source["content"], "原始正文")
        self.assertEqual(new_article["status"], "draft")
        self.assertEqual(new_article["source_article_id"], 1)
        self.assertEqual(new_article["title"], "已发表优化标题")

    def test_draft_apply_updates_current_article(self):
        result = ArticleGrowthAnalyzer.apply_optimized_to_draft(2)

        self.assertTrue(result["ok"])
        conn = self.connection_factory()
        try:
            article = conn.execute("SELECT title, content FROM articles WHERE id=2").fetchone()
        finally:
            conn.close()
        self.assertEqual(article["title"], "草稿优化标题")
        self.assertEqual(article["content"], "优化后的完整正文")

    def test_published_apply_returns_error(self):
        result = ArticleGrowthAnalyzer.apply_optimized_to_draft(1)

        self.assertFalse(result["ok"])
        self.assertIn("不能直接覆盖", result["error"])

    def test_manual_metrics_are_read_by_dashboard(self):
        update = ArticleGrowthAnalyzer.update_metrics(
            2,
            {
                "read_count": 125,
                "like_count": 8,
                "share_count": 3,
                "favorite_count": 2,
                "comment_count": 1,
                "scan_count": 4,
                "consult_count": 2,
                "deal_count": 1,
            },
        )
        dashboard = ArticleGrowthAnalyzer.get_dashboard_data()
        article = next(item for item in dashboard["articles"] if item["id"] == 2)

        self.assertTrue(update["ok"])
        self.assertEqual(article["view_count"], 125)
        self.assertEqual(article["deal_count"], 1)
        self.assertTrue(article["has_metrics"])


if __name__ == "__main__":
    unittest.main()


class IndustryLawArticleTestCase(unittest.TestCase):
    def test_industry_law_topics_have_required_metadata(self):
        topics = TopicEngine.generate_industry_law_topics()
        self.assertEqual(len(topics), 8)
        for topic in topics:
            self.assertEqual(topic["article_type"], "industry_law")
            for key in ("category", "core_law", "source_title", "suggested_title", "target_customer", "common_misunderstanding", "bank_logic", "article_angle", "conversion_goal"):
                self.assertTrue(topic.get(key), key)

    def test_industry_law_fallback_has_required_structure(self):
        topic = TopicEngine.generate_industry_law_topics()[0]
        result = ArticleGenerationAgent.build_local_fallback(topic["suggested_title"], topic)
        text = result["markdown"]
        self.assertTrue(result["fallback_used"])
        self.assertIn("老板的常见误区", text)
        self.assertIn("银行的真实逻辑", text)
        self.assertIn("一个典型经营场景", text)
        self.assertGreaterEqual(text.count("## 规律"), 3)
        self.assertIn("企业现在可以做什么", text)
        self.assertIn("企业融资体检", text)
        self.assertTrue(TitleGuard.inspect_title(result["title"])["qualified"])

    def test_industry_law_generation_endpoint_keeps_title_tracking(self):
        topic = dict(TopicEngine.generate_industry_law_topics()[0])
        topic["suggested_title"] = "银行拒贷后，老板先别急着换银行"
        generated = {"ok": True, "title": topic["suggested_title"], "markdown": "正文", "summary": "摘要", "tags": ["企业融资"], "html": "<p>正文</p>", "ai_used": True}
        with app.test_client() as client, patch("web_ui.app.LoanIndustryLawArticleGenerator.generate", return_value=generated) as generate, patch("web_ui.app.ArticleGenerationAgent.generate") as generic_generate, patch("web_ui.app.TemplateService.create_agent_article", return_value={"ok": True, "article_id": 987, "source_title": topic["source_title"], "generated_title": topic["suggested_title"]}):
            with client.session_transaction() as session:
                session["logged_in"] = True
                session["username"] = "admin"
                session["role"] = "admin"
            response = client.post("/content-growth/topic/generate", json=topic)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["article_id"], 987)
        self.assertEqual(data["source_title"], topic["source_title"])
        self.assertEqual(data["generated_title"], topic["suggested_title"])
        self.assertEqual(generate.call_args.kwargs["keyword"], topic["suggested_title"])
        self.assertEqual(generate.call_args.kwargs["context"]["article_type"], "industry_law")
        generic_generate.assert_not_called()
