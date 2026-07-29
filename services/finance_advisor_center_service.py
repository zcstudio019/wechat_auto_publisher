"""Phase 5 orchestration service for the AI financing diagnosis center."""
from __future__ import annotations

import json
from typing import Any, Iterable

from services.finance_diagnosis_agent import FinanceDiagnosisAgent
from services.finance_product_match_agent import FinanceProductMatchAgent
from services.finance_report_generator import FinanceReportGenerator
from services.finance_sales_assistant_agent import FinanceSalesAssistantAgent


class FinanceAdvisorCenterService:
    """Build diagnosis-center rows from existing lead/customer records."""

    @classmethod
    def build_center(cls, customers: Iterable[dict[str, Any]] | None) -> dict[str, Any]:
        entries = [cls.analyze_customer(customer) for customer in (customers or [])]
        entries.sort(
            key=lambda item: (
                item["diagnosis"]["score"],
                item["customer"].get("id", 0),
            ),
            reverse=True,
        )
        levels = {level: 0 for level in ("S", "A", "B", "C", "D")}
        for entry in entries:
            levels[entry["diagnosis"]["level"]] += 1
        return {
            "customers": entries,
            "summary": {
                "total_customers": len(entries),
                "average_score": round(
                    sum(item["diagnosis"]["score"] for item in entries) / len(entries), 2
                ) if entries else 0,
                "levels": levels,
                "high_value_customers": levels["S"] + levels["A"],
            },
        }

    @classmethod
    def analyze_customer(cls, customer: dict[str, Any] | None) -> dict[str, Any]:
        normalized = cls._normalize_customer(customer or {})
        diagnosis = FinanceDiagnosisAgent.diagnose(normalized)
        products = FinanceProductMatchAgent.match(normalized, diagnosis=diagnosis)
        sales = FinanceSalesAssistantAgent.generate(normalized, diagnosis)
        report = FinanceReportGenerator.generate(normalized, diagnosis, products)
        return {
            "customer": normalized,
            "diagnosis": diagnosis,
            "product_matches": products,
            "sales_assistance": sales,
            "report": report,
        }

    @staticmethod
    def _normalize_customer(customer: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(customer)
        form_data = customer.get("form_data")
        if isinstance(form_data, str):
            try:
                parsed = json.loads(form_data)
            except (TypeError, ValueError, json.JSONDecodeError):
                parsed = {}
        elif isinstance(form_data, dict):
            parsed = form_data
        else:
            parsed = {}
        normalized = {**normalized, **parsed}
        normalized["id"] = customer.get("id") or parsed.get("id") or 0
        normalized["name"] = (
            customer.get("name")
            or parsed.get("name")
            or customer.get("customer_name")
            or "未命名客户"
        )
        normalized["loan_amount"] = (
            customer.get("loan_amount")
            or parsed.get("loan_amount")
            or parsed.get("financing_amount")
            or ""
        )
        normalized["financing_amount"] = (
            parsed.get("financing_amount")
            or customer.get("financing_amount")
            or normalized["loan_amount"]
        )
        normalized["financing_need"] = (
            parsed.get("financing_need")
            or parsed.get("financing_purpose")
            or parsed.get("description")
            or customer.get("financing_need")
            or customer.get("financing_purpose")
            or customer.get("description")
            or normalized["loan_amount"]
        )
        normalized["credit_status"] = (
            customer.get("credit_status")
            or parsed.get("credit_status")
            or ""
        )
        return normalized
