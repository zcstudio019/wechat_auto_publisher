import json
import unittest
from unittest.mock import patch

from wechat_api.client import add_draft


class _FakeResponse:
    def json(self):
        return {"media_id": "draft_media_id"}


class WechatDraftDigestTestCase(unittest.TestCase):
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
                        "digest": "沪上银 · 上海专业贷款顾问",
                        "summary": "这段摘要不应进入微信草稿箱",
                        "content": "<p>正文内容</p>",
                        "thumb_media_id": "thumb_media_id",
                    }
                ]
            )

        self.assertEqual(media_id, "draft_media_id")
        self.assertEqual(captured["payload"]["articles"][0]["digest"], "")


if __name__ == "__main__":
    unittest.main()
