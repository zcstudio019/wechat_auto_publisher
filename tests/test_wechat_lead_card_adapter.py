import unittest

from services.wechat_html_adapter import adapt_html_for_wechat
from services.wechat_lead_card_adapter import adapt_lead_form_to_wechat_card


class WechatLeadCardAdapterTestCase(unittest.TestCase):
    """公众号留资入口卡片适配测试。"""

    def test_form_is_replaced_by_static_lead_card(self):
        """含 form 的正文发布前应替换为静态留资卡片。"""
        html = """
        <div class="lead-form-container">
            <h3>免费融资评估</h3>
            <form class="lead-form" data-form-type="quota_calc">
                <input type="text" name="name">
                <button type="submit">提交</button>
            </form>
        </div>
        """

        result = adapt_lead_form_to_wechat_card(html, lead_url="https://example.com/lead")
        lower_result = result.lower()

        self.assertNotIn("<form", lower_result)
        self.assertNotIn("<input", lower_result)
        self.assertNotIn("<button", lower_result)
        self.assertIn("免费融资评估", result)
        self.assertIn("了解适合自己的资金方案", result)

    def test_configured_lead_url_is_kept(self):
        """配置咨询链接时，卡片按钮应包含该链接。"""
        html = """
        <section class="work-order-form">
            <p>经营贷方案咨询</p>
            <form><textarea name="memo"></textarea><select name="amount"></select></form>
        </section>
        """

        result = adapt_lead_form_to_wechat_card(html, lead_url="https://example.com/contact")
        lower_result = result.lower()

        self.assertNotIn("<textarea", lower_result)
        self.assertNotIn("<select", lower_result)
        self.assertIn('href="https://example.com/contact"', result)
        self.assertIn("获取融资规划建议", result)

    def test_without_lead_url_uses_builtin_public_form(self):
        """未配置咨询链接时，应默认跳转到系统内置公开留资页。"""
        html = """
        <div class="lead-form-container">
            <form><input name="phone"></form>
        </div>
        """

        result = adapt_lead_form_to_wechat_card(html, lead_url="")

        self.assertNotIn("<form", result.lower())
        self.assertNotIn("<input", result.lower())
        self.assertIn("一对一贷款咨询", result)
        self.assertIn('href="/lead-form"', result)

    def test_wechat_html_adapter_keeps_safe_action_link(self):
        """后续微信 HTML 清洗后，咨询入口链接仍应保留。"""
        html = """
        <div class="lead-form-container">
            <form><input name="phone"></form>
        </div>
        """

        lead_card_html = adapt_lead_form_to_wechat_card(
            html,
            lead_url="https://example.com/lead",
        )
        result = adapt_html_for_wechat(lead_card_html)

        self.assertIn("<a", result)
        self.assertIn('href="https://example.com/lead"', result)
        self.assertIn("了解适合自己的资金方案", result)


if __name__ == "__main__":
    unittest.main()
