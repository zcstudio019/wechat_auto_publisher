import unittest

from ai_processor.content_writer import optimize_wechat_title


class WechatTitleGenerationTestCase(unittest.TestCase):
    """公众号标题优化测试。"""

    def test_long_title_is_compressed_to_22_chars(self):
        """超过 22 字的标题应自动压缩。"""
        title = "上海企业经营贷融资贷款批款服务案例分享解析说明"

        result = optimize_wechat_title(title)

        self.assertLessEqual(len(result), 22)
        self.assertTrue(result)

    def test_keyword_stacking_title_is_rewritten(self):
        """关键词堆砌标题应改写为更自然的公众号标题。"""
        title = "贷款融资专业解决方案服务"

        result = optimize_wechat_title(title)

        self.assertLessEqual(len(result), 22)
        self.assertNotIn("专业解决方案服务", result)
        self.assertIn("融资", result)

    def test_bad_enterprise_case_title_is_rewritten(self):
        """当前问题案例应被修正为通顺标题。"""
        result = optimize_wechat_title("企业才能经营真实案例")

        self.assertEqual(result, "企业经营贷真实案例")
        self.assertLessEqual(len(result), 22)

    def test_truncated_bad_enterprise_case_title_is_rewritten(self):
        """旧规则截断后的坏标题也应被修正。"""
        result = optimize_wechat_title("企业才能经真实案例")

        self.assertEqual(result, "企业经营贷真实案例")
        self.assertLessEqual(len(result), 22)

    def test_title_is_not_empty(self):
        """空标题应有兜底标题。"""
        result = optimize_wechat_title("")

        self.assertTrue(result)
        self.assertLessEqual(len(result), 22)

    def test_title_keeps_business_keyword_naturally(self):
        """业务关键词应自然保留，而不是被全部删除。"""
        result = optimize_wechat_title("上海企业经营贷融资贷款批款服务")

        self.assertLessEqual(len(result), 22)
        self.assertTrue(any(keyword in result for keyword in ["经营贷", "融资", "贷款", "上海"]))
        self.assertFalse(result.endswith("服务"))

    def test_title_has_natural_subject_or_question_structure(self):
        """标题至少应包含自然问题、主语或结果结构之一。"""
        result = optimize_wechat_title("企业税票征信额度案例解析方案")

        self.assertLessEqual(len(result), 22)
        self.assertTrue(any(marker in result for marker in ["企业", "征信", "为什么", "为何", "？", "3坑"]))


if __name__ == "__main__":
    unittest.main()
