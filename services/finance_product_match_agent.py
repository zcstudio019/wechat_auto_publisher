"""Phase 5 bank financing product matcher."""
from __future__ import annotations

import importlib
from typing import Any, Iterable

from services.finance_diagnosis_agent import FinanceDiagnosisAgent


DEFAULT_FINANCE_PRODUCTS = (
    {
        "product_name": "企业税票经营贷",
        "product_type": "credit",
        "amount": "10万-500万元",
        "term": "1-3年",
        "keywords": ("纳税", "开票", "经营贷"),
        "min_business_years": 2,
        "risk_notice": "需要核验纳税、开票连续性及企业和法定代表人征信。",
    },
    {
        "product_name": "企业流水信用贷",
        "product_type": "credit",
        "amount": "10万-300万元",
        "term": "1-3年",
        "keywords": ("流水", "周转", "现金流"),
        "min_business_years": 1,
        "risk_notice": "对公回款占比、流水稳定性和负债水平会影响审批。",
    },
    {
        "product_name": "抵押经营贷",
        "product_type": "mortgage",
        "amount": "50万-2000万元",
        "term": "1-10年",
        "keywords": ("抵押", "房产", "设备", "大额"),
        "min_business_years": 1,
        "risk_notice": "额度受抵押物评估、用途合规和还款能力共同约束。",
    },
    {
        "product_name": "供应链融资",
        "product_type": "supply_chain",
        "amount": "50万-1000万元",
        "term": "3-24个月",
        "keywords": ("订单", "应收", "采购", "项目垫资", "备货"),
        "min_business_years": 1,
        "risk_notice": "需要核验核心交易、合同、发票和回款闭环。",
    },
    {
        "product_name": "科创企业信用贷",
        "product_type": "technology",
        "amount": "20万-1000万元",
        "term": "1-3年",
        "keywords": ("科技", "高新", "研发", "专精特新"),
        "min_business_years": 1,
        "risk_notice": "需结合科技资质、研发投入、知识产权和经营情况综合审核。",
    },
)


class FinanceProductMatchAgent:
    """Match normalized product-library entries against a diagnosis."""

    OPTIONAL_LIBRARY_MODULES = (
        "services.bank_product_library",
        "services.loan_product_library",
        "services.finance_product_library",
    )

    @classmethod
    def match(
        cls,
        enterprise: dict[str, Any] | None,
        diagnosis: dict[str, Any] | None = None,
        products: Iterable[dict[str, Any]] | None = None,
        limit: int = 3,
    ) -> dict[str, Any]:
        data = enterprise or {}
        safe_diagnosis = diagnosis or FinanceDiagnosisAgent.diagnose(data)
        library, source = cls._load_products(data, products)
        matches = [
            cls._score_product(data, safe_diagnosis, cls._normalize_product(item))
            for item in library
        ]
        matches.sort(key=lambda item: (item["match_score"], item["product_name"]), reverse=True)
        safe_limit = max(1, min(10, int(limit or 3)))
        return {
            "matches": matches[:safe_limit],
            "product_library_source": source,
            "total_products": len(matches),
            "disclaimer": "匹配结果仅用于融资规划参考，不构成银行授信承诺。",
        }

    @classmethod
    def _load_products(
        cls,
        enterprise: dict[str, Any],
        products: Iterable[dict[str, Any]] | None,
    ) -> tuple[list[dict[str, Any]], str]:
        explicit = list(products or enterprise.get("bank_products") or [])
        if explicit:
            return explicit, "existing_product_library"
        for module_name in cls.OPTIONAL_LIBRARY_MODULES:
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                continue
            for attribute in ("BANK_PRODUCTS", "LOAN_PRODUCTS", "PRODUCTS"):
                values = getattr(module, attribute, None)
                if values:
                    return list(values), module_name
            loader = getattr(module, "get_products", None)
            if callable(loader):
                values = loader()
                if values:
                    return list(values), module_name
        return list(DEFAULT_FINANCE_PRODUCTS), "phase5_fallback_library"

    @classmethod
    def _score_product(
        cls,
        enterprise: dict[str, Any],
        diagnosis: dict[str, Any],
        product: dict[str, Any],
    ) -> dict[str, Any]:
        searchable = " ".join(
            str(enterprise.get(key) or "")
            for key in (
                "industry",
                "financing_need",
                "financing_purpose",
                "scenario",
                "description",
                "assets",
                "qualifications",
            )
        )
        score = 35 + min(35, int(diagnosis.get("score") or 0) // 3)
        reasons = []
        matched_keywords = [
            keyword for keyword in product["keywords"] if keyword and keyword in searchable
        ]
        if matched_keywords:
            score += min(20, len(matched_keywords) * 10)
            reasons.append(f"融资场景与产品关注的“{'、'.join(matched_keywords)}”相符。")
        years = FinanceDiagnosisAgent._number(
            enterprise.get("business_years") or enterprise.get("operating_years")
        )
        if years >= product["min_business_years"]:
            score += 10
            reasons.append("企业经营年限达到该类产品的基础匹配条件。")
        elif product["min_business_years"]:
            score -= 20
            reasons.append("经营年限可能不足，需要进一步确认准入口径。")
        if product["product_type"] == "mortgage":
            has_collateral = any(
                word in searchable for word in ("房产", "抵押物", "厂房", "商铺", "设备")
            )
            score += 15 if has_collateral else -20
            reasons.append(
                "企业提供了可评估抵押物。" if has_collateral else "尚未提供明确抵押物信息。"
            )
        if not reasons:
            reasons.append("与企业当前综合评分和基础经营条件相匹配。")
        return {
            "product_name": product["product_name"],
            "match_reason": reasons,
            "amount": product["amount"],
            "term": product["term"],
            "risk_notice": product["risk_notice"],
            "match_score": max(0, min(100, score)),
        }

    @staticmethod
    def _normalize_product(product: dict[str, Any]) -> dict[str, Any]:
        keywords = product.get("keywords") or product.get("scenarios") or ()
        if isinstance(keywords, str):
            keywords = tuple(part.strip() for part in keywords.replace("，", ",").split(","))
        return {
            "product_name": str(
                product.get("product_name") or product.get("name") or "未命名融资产品"
            ),
            "product_type": str(product.get("product_type") or product.get("type") or "credit"),
            "amount": str(
                product.get("amount")
                or product.get("amount_range")
                or product.get("quota")
                or "以银行审核为准"
            ),
            "term": str(
                product.get("term")
                or product.get("term_range")
                or product.get("duration")
                or "以银行审核为准"
            ),
            "keywords": tuple(str(item) for item in keywords),
            "min_business_years": int(product.get("min_business_years") or 0),
            "risk_notice": str(
                product.get("risk_notice")
                or product.get("risk")
                or "具体准入、额度和期限以银行审核为准。"
            ),
        }
