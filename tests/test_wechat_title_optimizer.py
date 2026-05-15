import unittest

from services.wechat_title_optimizer import optimize_wechat_title
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

    def test_wechat_draft_title_uses_optimizer(self):
        result = _truncate_title("经营贷申请攻略：企业资金安排与风险把控")

        self.assertEqual(result, "企业资金安排与风险把控（经营贷）")


if __name__ == "__main__":
    unittest.main()
