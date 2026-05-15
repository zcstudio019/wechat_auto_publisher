import unittest

from ai_processor.processor import format_original_article


class ArticleHeaderTestCase(unittest.TestCase):
    def test_original_article_header_does_not_show_brand_subtitle(self):
        article = {
            "title": "企业资金安排与风险把控",
            "content": "## 先看现金流\n\n企业资金安排要先看收入节奏和还款来源。\n\n## 再看风险\n\n根据实际情况评估融资方案。",
            "source_name": "沪上银原创",
        }

        result = format_original_article(article)
        html = result.get("html_content", "")
        header = html.split("</section>", 1)[0]

        self.assertIn("企业资金安排与风险把控", header)
        self.assertNotIn("沪上银 · 上海专业贷款顾问", header)
        self.assertNotIn("贷款顾问", header)


if __name__ == "__main__":
    unittest.main()
