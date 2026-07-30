import unittest

from services.wechat_title_optimizer import build_wechat_title_suggestion, optimize_wechat_title
from wechat_api.publisher import _truncate_title


class WechatTitleOptimizerTestCase(unittest.TestCase):
    def test_moves_long_prefix_behind_core_info(self):
        result = optimize_wechat_title("经营贷申请攻略：企业资金安排与风险把控")

        self.assertEqual(result, "企业资金安排与风险把控（经营贷）")
        self.assertNotIn("经营贷申请攻略：", result)

    def test_removes_category_prefix(self):
        result = optimize_wechat_title("融资规划：企业现金流紧张时怎么安排资金")

        self.assertFalse(result.startswith("融资规划："))
        self.assertIn("企业现金流", result)
        self.assertLessEqual(len(result), 28)

    def test_keeps_problem_style_title(self):
        result = optimize_wechat_title("经营贷申请攻略：经营贷申请为什么被拒")

        self.assertIn("经营贷", result)
        self.assertTrue("？" in result or "被拒" in result)
        self.assertLessEqual(len(result), 28)

    def test_empty_title_has_safe_fallback(self):
        result = optimize_wechat_title("")

        self.assertTrue(result)
        self.assertLessEqual(len(result), 28)

    def test_long_title_is_limited(self):
        result = optimize_wechat_title("知识科普：企业老板在现金流紧张时如何判断融资节奏与还款风险")

        self.assertLessEqual(len(result), 28)
        self.assertFalse(result.startswith("知识科普："))

    def test_wechat_draft_title_preserves_formal_title(self):
        formal_title = "初创企业老板企业周转时现金流紧张，为什么有利润仍周转困难？先查这3项"

        self.assertEqual(_truncate_title(formal_title), formal_title)

    def test_optimizer_only_populates_optimized_title(self):
        formal_title = "初创企业老板企业周转时现金流紧张，为什么有利润仍周转困难？先查这3项"
        article = {"title": formal_title, "cover_prompt": formal_title, "html_content": f"<h1>{formal_title}</h1>"}

        result = build_wechat_title_suggestion(article)

        self.assertEqual(result["title"], formal_title)
        self.assertEqual(result["optimized_title"], "现金流吃紧时，企业该怎么周转")
        self.assertEqual(result["cover_prompt"], formal_title)
        self.assertIn(f"<h1>{formal_title}</h1>", result["html_content"])
        self.assertEqual(article["title"], formal_title)
        self.assertNotIn("optimized_title", article)


if __name__ == "__main__":
    unittest.main()
