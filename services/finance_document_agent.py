"""Phase 6 financing-document checklist agent."""
from __future__ import annotations

from typing import Any, Iterable


class FinanceDocumentAgent:
    """Compare required financing documents with already supplied documents."""

    COMMON_DOCUMENTS = (
        "营业执照及公司章程",
        "法定代表人和主要股东身份证明",
        "近12个月对公及主要经营流水",
        "近两年财务报表和近期科目余额表",
        "纳税、开票及主要经营合同",
        "企业和法定代表人征信报告",
        "现有借款、担保和抵押物清单",
        "融资用途说明及还款来源证明",
    )

    TYPE_DOCUMENTS = {
        "抵押经营贷": ("抵押物权属证明", "抵押物评估及使用情况资料"),
        "企业税票经营贷": ("近两年纳税申报记录", "近12个月开票明细"),
        "企业流水信用贷": ("主要账户流水明细", "主要客户和供应商清单"),
        "供应链融资": ("核心交易合同", "订单、发票及应收账款证明"),
        "科创企业信用贷": ("高新或专精特新资质", "知识产权和研发投入证明"),
    }

    @classmethod
    def analyze(
        cls,
        financing_type: str = "",
        bank_solution: dict[str, Any] | None = None,
        existing_documents: Iterable[str] | str | None = None,
    ) -> dict[str, Any]:
        solution = bank_solution or {}
        product_name = str(
            solution.get("product_name") or solution.get("name") or financing_type or "企业融资"
        )
        required = list(cls.COMMON_DOCUMENTS)
        for key, documents in cls.TYPE_DOCUMENTS.items():
            if key in product_name or key in str(financing_type or ""):
                required.extend(documents)
        existing = cls._normalize_existing(existing_documents)
        missing = [
            document for document in required
            if not any(cls._matches(document, supplied) for supplied in existing)
        ]
        warnings = []
        if any("征信" in item for item in missing):
            warnings.append("申请前缺少征信报告，无法完整判断查询、负债和逾期风险。")
        if any("流水" in item for item in missing):
            warnings.append("缺少连续经营流水，可能影响还款来源核验。")
        if "抵押" in product_name and any("抵押物" in item for item in missing):
            warnings.append("抵押资料不完整，暂不能确认抵押物可用性和额度空间。")
        if not warnings:
            warnings.append("资料完整性仍需由顾问和银行逐项核验。")
        return {
            "financing_type": str(financing_type or product_name),
            "bank_solution": product_name,
            "required_documents": required,
            "existing_documents": existing,
            "missing_documents": missing,
            "completion_rate": round((len(required) - len(missing)) / max(1, len(required)) * 100, 1),
            "risk_notices": warnings,
        }

    @staticmethod
    def _normalize_existing(documents: Iterable[str] | str | None) -> list[str]:
        if not documents:
            return []
        if isinstance(documents, str):
            return [
                item.strip()
                for item in documents.replace("，", ",").replace("、", ",").split(",")
                if item.strip()
            ]
        return [str(item).strip() for item in documents if str(item).strip()]

    @staticmethod
    def _matches(required: str, supplied: str) -> bool:
        keywords = ("营业执照", "身份证", "流水", "财务报表", "纳税", "开票", "合同", "征信", "借款", "抵押物", "用途", "知识产权", "研发")
        return required == supplied or any(
            keyword in required and keyword in supplied for keyword in keywords
        )
