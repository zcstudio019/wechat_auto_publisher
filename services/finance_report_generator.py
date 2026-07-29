"""Phase 5 enterprise financing planning report generator."""
from __future__ import annotations

from typing import Any

from services.finance_diagnosis_agent import FinanceDiagnosisAgent
from services.finance_product_match_agent import FinanceProductMatchAgent
from services.finance_sales_assistant_agent import FinanceSalesAssistantAgent


class FinanceReportGenerator:
    """Compose diagnosis and product matches into a financing report."""

    @classmethod
    def generate(
        cls,
        enterprise: dict[str, Any] | None,
        diagnosis: dict[str, Any] | None = None,
        product_matches: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = enterprise or {}
        safe_diagnosis = diagnosis or FinanceDiagnosisAgent.diagnose(data)
        safe_products = product_matches or FinanceProductMatchAgent.match(
            data, diagnosis=safe_diagnosis
        )
        sales = FinanceSalesAssistantAgent.generate(data, safe_diagnosis)
        report = {
            "enterprise_profile": cls._profile(data),
            "financing_score": {
                "score": safe_diagnosis["score"],
                "level": safe_diagnosis["level"],
                "financing_capacity": safe_diagnosis["financing_capacity"],
            },
            "bank_review_analysis": cls._bank_review(safe_diagnosis),
            "problem_diagnosis": list(safe_diagnosis["problems"]),
            "optimization_recommendations": list(safe_diagnosis["recommendations"]),
            "solution_recommendations": list(safe_products.get("matches") or []),
            "required_documents": list(safe_diagnosis["required_documents"]),
            "sales_follow_up": sales,
            "disclaimer": "本报告为初步融资规划建议，不构成银行授信、额度、利率或放款承诺。",
        }
        report["report_text"] = cls._render_text(report)
        return report

    @staticmethod
    def _profile(data: dict[str, Any]) -> dict[str, str]:
        return {
            "customer": str(data.get("name") or data.get("customer_name") or "未命名客户"),
            "industry": str(data.get("industry") or "待补充"),
            "business_years": str(
                data.get("business_years") or data.get("operating_years") or "待补充"
            ),
            "annual_revenue": str(
                data.get("annual_revenue") or data.get("annual_turnover") or "待补充"
            ),
            "financing_need": str(
                data.get("financing_need")
                or data.get("financing_purpose")
                or data.get("loan_amount")
                or "待补充"
            ),
        }

    @staticmethod
    def _bank_review(diagnosis: dict[str, Any]) -> list[str]:
        detail = diagnosis.get("score_detail") or {}
        dimensions = (
            ("企业经营", detail.get("enterprise_operation", 0), 30),
            ("现金流", detail.get("cash_flow", 0), 25),
            ("负债结构", detail.get("debt", 0), 20),
            ("征信", detail.get("credit", 0), 15),
            ("融资需求", detail.get("financing_need", 0), 10),
        )
        return [
            f"{label}：{score}/{maximum}，"
            + ("基础较好。" if score >= maximum * 0.75 else "需要补充或优化。")
            for label, score, maximum in dimensions
        ]

    @staticmethod
    def _render_text(report: dict[str, Any]) -> str:
        profile = report["enterprise_profile"]
        financing = report["financing_score"]
        lines = [
            "# 企业融资规划报告",
            "",
            "## 企业画像",
            f"- 客户：{profile['customer']}",
            f"- 行业：{profile['industry']}",
            f"- 经营年限：{profile['business_years']}",
            f"- 营收情况：{profile['annual_revenue']}",
            f"- 融资需求：{profile['financing_need']}",
            "",
            "## 融资评分",
            f"- 综合评分：{financing['score']}分",
            f"- 客户等级：{financing['level']}",
            f"- 融资能力：{financing['financing_capacity']}",
            "",
            "## 银行审核分析",
            *[f"- {item}" for item in report["bank_review_analysis"]],
            "",
            "## 问题诊断",
            *[f"- {item}" for item in report["problem_diagnosis"]],
            "",
            "## 优化建议",
            *[f"- {item}" for item in report["optimization_recommendations"]],
            "",
            "## 方案推荐",
        ]
        for product in report["solution_recommendations"]:
            lines.extend([
                f"### {product['product_name']}",
                f"- 额度：{product['amount']}",
                f"- 期限：{product['term']}",
                f"- 匹配原因：{'；'.join(product['match_reason'])}",
                f"- 风险提示：{product['risk_notice']}",
            ])
        lines.extend([
            "",
            "## 资料清单",
            *[f"- {item}" for item in report["required_documents"]],
            "",
            report["disclaimer"],
        ])
        return "\n".join(lines)
