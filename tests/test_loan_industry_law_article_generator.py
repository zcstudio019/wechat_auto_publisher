import unittest
from types import SimpleNamespace

from services.enterprise_finance_growth_strategy import (
    FinanceGrowthTitleScorer,
    enterprise_finance_growth,
)
from services.loan_industry_law_article_generator import LoanIndustryLawArticleGenerator


VALID_CONTENT = """## 一、真实老板案例
一位企业老板经营6年，年流水500万元，申请经营贷时只获批30万元。
## 二、老板真实疑问
为什么有流水、有利润，银行额度仍然很低？这是老板最直接的融资痛点。
## 三、银行真实审核逻辑
1. 还款能力：利润能否覆盖本息。
2. 现金流：回款是否连续稳定。
3. 企业稳定性：经营时间和业务是否稳定。
4. 征信情况：查询、多头借贷和逾期情况。
5. 负债结构：短期负债是否集中到期。
## 四、老板行动建议
第一步：不要盲目申请贷款
第二步：分析融资条件
第三步：匹配融资方式
第四步：优化融资结构
"""


class FakeCompletions:
    def __init__(self, contents="", error=None):
        self.contents = list(contents) if isinstance(contents, (list, tuple)) else [contents]
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        index = min(len(self.calls) - 1, len(self.contents) - 1)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.contents[index]))]
        )


class FakeClient:
    def __init__(self, contents="", error=None):
        self.chat = SimpleNamespace(completions=FakeCompletions(contents, error))


class LoanIndustryLawArticleGeneratorTests(unittest.TestCase):
    def test_plain_text_ai_response_uses_phase2_topic_structure_without_json_mode(self):
        response = f"""TITLE:
公司流水500万，为什么银行只批30万额度？老板最容易忽略这3个原因
SUMMARY:
从真实经营场景拆解银行审核逻辑，并给出企业融资优化步骤。
CONTENT:
{VALID_CONTENT}
CTA:
企业融资体检
"""
        client = FakeClient(response)
        generator = LoanIndustryLawArticleGenerator(client=client, model="deepseek-chat")

        result = generator.generate(
            "贷款行业有个残酷真相：银行从来不把钱借给最缺钱的人",
            {"name": "贷款行业底层规律型文章", "target_customer": "年流水500万以上老板", "scenario": "设备采购", "pain_point": "额度不足"},
        )

        self.assertTrue(result["ok"])
        self.assertFalse(result["fallback_used"])
        self.assertGreaterEqual(result["title_score"], 75)
        self.assertEqual(result["content_strategy"], "enterprise_finance_growth")
        self.assertEqual(result["prompt_version"], "phase2")
        for marker in ("真实老板案例", "痛点", "银行真实审核逻辑", "老板行动建议", result["cta"]["title"]):
            self.assertIn(marker, result["markdown"])
        self.assertEqual(result["cta"]["title"], "融资额度评估")
        request = client.chat.completions.calls[0]
        self.assertNotIn("response_format", request)
        self.assertIn("老板身份 + 具体融资场景 + 冲突 + 解决期待", request["messages"][1]["content"])
        self.assertIn("负债结构", request["messages"][1]["content"])
        self.assertIn("目标客户：\n年流水500万以上老板", request["messages"][1]["content"])
        self.assertIn("真实场景：\n设备采购", request["messages"][1]["content"])
        self.assertIn("核心痛点：\n额度不足", request["messages"][1]["content"])

    def test_low_score_ai_title_is_regenerated(self):
        article = f"""TITLE:
贷款行业有什么规律
SUMMARY:
企业融资审核分析。
CONTENT:
{VALID_CONTENT}
CTA:
企业融资体检
"""
        better_title = "TITLE: 征信没有逾期，为什么企业贷款仍被拒？老板先检查这3个融资条件"
        client = FakeClient([article, better_title])
        generator = LoanIndustryLawArticleGenerator(client=client, model="deepseek-chat")

        result = generator.generate("征信没有逾期为什么贷款被拒")

        self.assertTrue(result["title_regenerated"])
        self.assertGreaterEqual(result["title_score"], 75)
        self.assertNotEqual(result["title"], "贷款行业有什么规律")
        self.assertEqual(len(client.chat.completions.calls), 2)
        self.assertNotIn("response_format", client.chat.completions.calls[1])

    def test_ai_exception_always_returns_growth_fallback(self):
        client = FakeClient(error=TimeoutError("AI timeout"))
        generator = LoanIndustryLawArticleGenerator(client=client, model="deepseek-chat")
        keyword = "贷款行业有个残酷真相：银行从来不把钱借给最缺钱的人"

        result = generator.generate(keyword)

        self.assertTrue(result["ok"])
        self.assertTrue(result["fallback_used"])
        self.assertIn("老板", result["title"])
        self.assertGreaterEqual(result["title_score"], 75)
        self.assertLessEqual(len(result["summary"]), 100)
        for heading in (
            "真实老板案例",
            "老板真实疑问",
            "银行真实审核逻辑",
            "老板行动建议",
            result["cta"]["title"],
        ):
            self.assertIn(heading, result["markdown"])
        for field in ("企业成立时间", "营业额与经营流水", "负债与征信情况", "当前融资需求"):
            self.assertIn(field, result["markdown"])

    def test_topic_context_controls_article_and_dynamic_cta(self):
        cases = (
            ("贷款被拒", "申请经营贷", "经营3年以上老板", "贷款失败原因分析"),
            ("现金流紧张", "企业周转", "现金流困难老板", "现金流健康检测"),
            ("额度不足", "设备采购", "年流水500万以上老板", "融资额度评估"),
        )
        for pain_point, scenario, target_customer, cta_title in cases:
            with self.subTest(pain_point=pain_point):
                result = LoanIndustryLawArticleGenerator(client=None, model="").generate(
                    pain_point,
                    {
                        "article_type": "industry_law",
                        "pain_point": pain_point,
                        "scenario": scenario,
                        "target_customer": target_customer,
                    },
                )
                self.assertTrue(result["ok"])
                self.assertGreaterEqual(result["title_score"], 75)
                self.assertEqual(result["cta"]["title"], cta_title)
                for marker in (
                    "真实老板案例",
                    "融资场景",
                    "银行真实审核逻辑",
                    "解决方案",
                    cta_title,
                ):
                    self.assertIn(marker, result["markdown"])
                self.assertEqual(result["pain_point"], pain_point)
                self.assertEqual(result["scenario"], scenario)
                self.assertEqual(result["target_customer"], target_customer)
    def test_invalid_ai_structure_uses_fallback(self):
        generator = LoanIndustryLawArticleGenerator(
            client=FakeClient("TITLE:\n只有标题"),
            model="deepseek-chat",
        )

        result = generator.generate("银行审核为什么看现金流")

        self.assertTrue(result["ok"])
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["ai_status"], "invalid_response")

    def test_strategy_configuration_and_title_score_dimensions(self):
        self.assertEqual(enterprise_finance_growth["title_strategy"], "企业老板真实融资场景标题")
        self.assertEqual(len(enterprise_finance_growth["pain_points"]), 8)
        self.assertEqual(len(enterprise_finance_growth["scenarios"]), 6)
        weak = FinanceGrowthTitleScorer.score_title("贷款行业有什么规律")
        strong = FinanceGrowthTitleScorer.score_title(
            "公司流水500万，为什么银行只批30万额度？老板最容易忽略这3个原因"
        )
        self.assertLess(weak["title_score"], 70)
        self.assertGreaterEqual(strong["title_score"], 70)
        self.assertEqual(sum(FinanceGrowthTitleScorer.WEIGHTS.values()), 100)

    def test_matches_only_industry_law_and_named_template(self):
        self.assertTrue(LoanIndustryLawArticleGenerator.matches(article_type="industry_law"))
        self.assertTrue(
            LoanIndustryLawArticleGenerator.matches(
                template={"name": "贷款行业底层规律型文章"}
            )
        )
        self.assertFalse(LoanIndustryLawArticleGenerator.matches(template={"category": "brand"}))


if __name__ == "__main__":
    unittest.main()
