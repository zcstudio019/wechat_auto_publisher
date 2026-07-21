import unittest
from types import SimpleNamespace

from services.loan_industry_law_article_generator import LoanIndustryLawArticleGenerator


class FakeCompletions:
    def __init__(self, content="", error=None):
        self.content = content
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class FakeClient:
    def __init__(self, content="", error=None):
        self.chat = SimpleNamespace(completions=FakeCompletions(content, error))


class LoanIndustryLawArticleGeneratorTests(unittest.TestCase):
    def test_plain_text_ai_response_is_parsed_without_json_mode(self):
        response = """TITLE:
银行拒贷后，老板先别急着换银行
SUMMARY:
先看懂银行真正的审批逻辑。
CONTENT:
## 一、反常识开头
银行不看谁最缺钱。
## 二、老板常见误区
缺钱才融资。
## 三、银行真实审批逻辑
银行看现金流。
## 四、贷款行业底层规律
规律1：借未来现金流。
规律2：申请会留下信号。
规律3：资料必须互相印证。
## 五、真实经营场景案例
一家营业额500万元的小微企业现金流断裂。
## 六、行动建议
先整理流水和征信。
CTA:
免费企业融资体检
"""
        client = FakeClient(response)
        generator = LoanIndustryLawArticleGenerator(client=client, model="deepseek-chat")

        result = generator.generate("银行拒贷后，老板先别急着换银行")

        self.assertTrue(result["ok"])
        self.assertFalse(result["fallback_used"])
        self.assertEqual(result["article_type"], "industry_law")
        self.assertIn("## 七、融资体检", result["markdown"])
        self.assertEqual(result["cta"]["button_text"], "立即获取融资方案")
        request = client.chat.completions.calls[0]
        self.assertNotIn("response_format", request)
        self.assertIn("TITLE:", request["messages"][1]["content"])

    def test_ai_exception_always_returns_fixed_structure_fallback(self):
        client = FakeClient(error=TimeoutError("AI timeout"))
        generator = LoanIndustryLawArticleGenerator(client=client, model="deepseek-chat")
        keyword = "贷款行业有个残酷真相：银行从来不把钱借给最缺钱的人"

        result = generator.generate(keyword)

        self.assertTrue(result["ok"])
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["title"], keyword)
        self.assertLessEqual(len(result["summary"]), 100)
        for heading in (
            "反常识开头",
            "老板常见误区",
            "银行真实审批逻辑",
            "贷款行业底层规律",
            "真实经营场景案例",
            "行动建议",
            "融资体检",
        ):
            self.assertIn(heading, result["markdown"])

    def test_invalid_ai_structure_uses_fallback(self):
        generator = LoanIndustryLawArticleGenerator(
            client=FakeClient("TITLE:\n只有标题"),
            model="deepseek-chat",
        )

        result = generator.generate("银行审批为什么看现金流")

        self.assertTrue(result["ok"])
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["ai_status"], "invalid_response")

    def test_matches_article_type_and_chinese_template_category(self):
        self.assertTrue(LoanIndustryLawArticleGenerator.matches(article_type="industry_law"))
        self.assertTrue(
            LoanIndustryLawArticleGenerator.matches(
                template={"category": "贷款行业底层规律"}
            )
        )
        self.assertFalse(
            LoanIndustryLawArticleGenerator.matches(template={"category": "brand"})
        )


if __name__ == "__main__":
    unittest.main()
