import json
import unittest
from unittest.mock import patch

from wechat_api.client import add_draft
from wechat_api.publisher import _make_digest


class _FakeResponse:
    def json(self):
        return {"media_id": "draft_media_id"}


class WechatDraftDigestTestCase(unittest.TestCase):
    def test_publisher_digest_uses_summary_only(self):
        self.assertEqual(
            _make_digest("这是一段文章摘要", "<p>沪上银 · 上海专业贷款顾问</p>"),
            "这是一段文章摘要",
        )
        self.assertEqual(_make_digest("", "<p>沪上银 · 上海专业贷款顾问</p>"), "")

    def test_add_draft_uses_summary_digest(self):
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
        self.assertEqual(
            captured["payload"]["articles"][0]["digest"],
            "这篇文章讲清企业经营贷申请前要关注的资料、现金流和还款风险。",
        )

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

        self.assertLessEqual(len(captured["payload"]["articles"][0]["digest"]), 54)


if __name__ == "__main__":
    unittest.main()
