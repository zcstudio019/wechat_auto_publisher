import unittest

from services.wechat_html_adapter import (
    adapt_html_for_wechat,
    cleanup_empty_blocks,
    sanitize_wechat_html,
)


class WechatHtmlAdapterTestCase(unittest.TestCase):
    """微信公众号 HTML 适配器测试。"""

    def test_removes_style_script_and_unsafe_attrs(self):
        """输入带 style/script 和危险属性时，输出应删除这些内容。"""
        html = """
        <style>.card{display:flex}</style>
        <script>alert(1)</script>
        <p class="card" data-id="1" onclick="evil()" style="position:absolute;flex:1;color:#333;">正文</p>
        """

        result = adapt_html_for_wechat(html)

        self.assertNotIn("<style", result)
        self.assertNotIn("<script", result)
        self.assertNotIn("class=", result)
        self.assertNotIn("data-id", result)
        self.assertNotIn("onclick", result)
        self.assertNotIn("position", result)
        self.assertNotIn("flex", result)
        self.assertIn("正文", result)

    def test_cleans_empty_blocks(self):
        """空段落、空 div 和只包含 br 的段落应被清理。"""
        html = "<div></div><p>&nbsp;</p><p><br/></p><p>有效正文</p>"

        result = cleanup_empty_blocks(html)

        self.assertNotIn("<div></div>", result)
        self.assertNotIn("&nbsp;", result)
        self.assertIn("有效正文", result)

    def test_converts_complex_div_to_section(self):
        """复杂 div 容器应尽量降级为 section，减少微信草稿箱失真。"""
        html = '<div class="layout" style="display:flex;grid-template-columns:1fr;"><div><p>正文</p></div></div>'

        result = adapt_html_for_wechat(html)

        self.assertNotIn("<div", result)
        self.assertIn("<section", result)
        self.assertIn("正文", result)

    def test_title_card_keeps_basic_visual_hierarchy(self):
        """标题卡片应保留基础背景色、标题和段落层次。"""
        html = """
        <div class="hero-title" style="background:linear-gradient(135deg,#0D47A1,#1976D2);box-shadow:0 2px 8px #999;">
          <h1>主标题</h1>
          <p>引导语</p>
        </div>
        """

        result = adapt_html_for_wechat(html)

        self.assertIn("background-color:#1565C0", result)
        self.assertIn("主标题", result)
        self.assertIn("引导语", result)
        self.assertNotIn("linear-gradient", result)
        self.assertNotIn("box-shadow", result)

    def test_keeps_image_with_wechat_safe_style(self):
        """图片应保留，并统一为微信中更稳定的宽度和块级展示。"""
        html = '<p>配图如下</p><img src="https://example.com/a.jpg" style="width:600px;position:absolute;" data-x="1">'

        result = adapt_html_for_wechat(html)

        self.assertIn("<img", result)
        self.assertIn('src="https://example.com/a.jpg"', result)
        self.assertIn("max-width:100%", result)
        self.assertIn("width:100%", result)
        self.assertIn("display:block", result)
        self.assertNotIn("position", result)
        self.assertNotIn("data-x", result)

    def test_result_is_not_empty_for_plain_text_html(self):
        """即使输入结构很弱，也不能返回空字符串。"""
        result = sanitize_wechat_html("<article><unknown>普通正文</unknown></article>")

        self.assertTrue(result.strip())
        self.assertIn("普通正文", result)


if __name__ == "__main__":
    unittest.main()
