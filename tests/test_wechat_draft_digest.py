import json
import unittest
from unittest.mock import patch

from wechat_api.client import add_draft
from wechat_api.publisher import _strip_wechat_top_noise


class _FakeResponse:
    def json(self):
        return {"media_id": "draft_media_id"}


class WechatDraftDigestTestCase(unittest.TestCase):
    def test_strip_wechat_top_noise_removes_brand_header_and_hidden_summary(self):
        html = """
        <div style="display:none">沪上银 · 上海专业贷款顾问</div>
        <section class="article-header" style="background:linear-gradient(135deg,#0D47A1,#1565C0);">
          <p>沪上银 · 上海专业贷款顾问</p>
          <h1>企业资金安排与风险把控</h1>
        </section>
        <p>真正正文第一段，先讲企业资金安排。</p>
        """

        result = _strip_wechat_top_noise(html)

        self.assertNotIn("沪上银", result)
        self.assertNotIn("上海专业贷款顾问", result)
        self.assertIn("真正正文第一段", result)

    def test_add_draft_forces_empty_digest(self):
        captured = {}

        def fake_post(url, **kwargs):
            captured["payload"] = json.loads(kwargs["data"].decode("utf-8"))
            return _FakeResponse()

        with patch("wechat_api.client.get_access_token", return_value="token"), patch(
            "wechat_api.client._http_post",
            side_effect=fake_post,
        ):
            media_id = add_draft(
                [
                    {
                        "title": "企业经营贷申请避坑指南",
                        "author": "沪上银",
                        "digest": "这篇文章讲清企业经营贷申请前要关注的资料、现金流和还款风险。",
                        "content": "<p>正文内容</p>",
                        "thumb_media_id": "thumb_media_id",
                    }
                ]
            )

        self.assertEqual(media_id, "draft_media_id")
        self.assertEqual(captured["payload"]["articles"][0]["digest"], "")
        self.assertEqual(captured["payload"]["articles"][0]["author"], "")

    def test_add_draft_removes_brand_digest(self):
        captured = {}

        def fake_post(url, **kwargs):
            captured["payload"] = json.loads(kwargs["data"].decode("utf-8"))
            return _FakeResponse()

        with patch("wechat_api.client.get_access_token", return_value="token"), patch(
            "wechat_api.client._http_post",
            side_effect=fake_post,
        ):
            media_id = add_draft(
                [
                    {
                        "title": "企业经营贷申请避坑指南",
                        "author": "沪上银",
                        "digest": "沪上银 · 上海专业贷款顾问",
                        "content": "<p>正文内容</p>",
                        "thumb_media_id": "thumb_media_id",
                    }
                ]
            )

        self.assertEqual(media_id, "draft_media_id")
        self.assertEqual(captured["payload"]["articles"][0]["digest"], "")
        self.assertEqual(captured["payload"]["articles"][0]["author"], "")

    def test_add_draft_limits_digest_to_54_chars(self):
        captured = {}

        def fake_post(url, **kwargs):
            captured["payload"] = json.loads(kwargs["data"].decode("utf-8"))
            return _FakeResponse()

        long_digest = "企业资金安排需要先看现金流、还款节奏、负债结构和真实经营情况，再判断融资方案是否适合。"
        with patch("wechat_api.client.get_access_token", return_value="token"), patch(
            "wechat_api.client._http_post",
            side_effect=fake_post,
        ):
            add_draft(
                [
                    {
                        "title": "企业经营贷申请避坑指南",
                        "author": "沪上银",
                        "digest": long_digest,
                        "content": "<p>正文内容</p>",
                        "thumb_media_id": "thumb_media_id",
                    }
                ]
            )

        self.assertEqual(captured["payload"]["articles"][0]["digest"], "")
        self.assertEqual(captured["payload"]["articles"][0]["author"], "")


if __name__ == "__main__":
    unittest.main()
