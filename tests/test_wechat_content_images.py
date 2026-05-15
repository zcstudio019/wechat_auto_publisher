import unittest
from unittest.mock import patch

from wechat_api.publisher import _upload_content_images_for_wechat


class WechatContentImagesTestCase(unittest.TestCase):
    def test_uploads_and_replaces_content_image_src(self):
        html = '<p>正文</p><img src="https://wechat.linhongtech.com/static/generated_covers/a.png" style="width:96%;">'

        with patch(
            "wechat_api.publisher.upload_content_image",
            return_value="https://mmbiz.qpic.cn/sz_mmbiz_png/a/0",
        ) as upload_mock:
            result = _upload_content_images_for_wechat(html)

        upload_mock.assert_called_once_with("https://wechat.linhongtech.com/static/generated_covers/a.png")
        self.assertIn('src="https://mmbiz.qpic.cn/sz_mmbiz_png/a/0"', result)
        self.assertNotIn("wechat.linhongtech.com/static/generated_covers/a.png", result)

    def test_skips_existing_mmbiz_images(self):
        html = '<img src="https://mmbiz.qpic.cn/sz_mmbiz_png/existing/0">'

        with patch("wechat_api.publisher.upload_content_image") as upload_mock:
            result = _upload_content_images_for_wechat(html)

        upload_mock.assert_not_called()
        self.assertEqual(result, html)

    def test_deduplicates_repeated_image_uploads(self):
        html = '<img src="/static/generated_covers/a.png"><p>中段</p><img src="/static/generated_covers/a.png">'

        with patch(
            "wechat_api.publisher.upload_content_image",
            return_value="https://mmbiz.qpic.cn/sz_mmbiz_png/a/0",
        ) as upload_mock:
            result = _upload_content_images_for_wechat(html)

        upload_mock.assert_called_once_with("/static/generated_covers/a.png")
        self.assertEqual(result.count("https://mmbiz.qpic.cn/sz_mmbiz_png/a/0"), 2)


if __name__ == "__main__":
    unittest.main()
