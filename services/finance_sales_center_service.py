"""Phase 6 orchestration for financing delivery and sales collaboration."""
from __future__ import annotations

from typing import Any, Iterable

from services.finance_advisor_center_service import FinanceAdvisorCenterService
from services.finance_document_agent import FinanceDocumentAgent
from services.finance_followup_agent import FinanceFollowupAgent
from services.finance_project_pipeline_service import FinanceProjectPipelineService
from services.finance_sales_funnel_analyzer import FinanceSalesFunnelAnalyzer
from services.finance_sales_script_agent import FinanceSalesScriptAgent


class FinanceSalesCenterService:
    """Combine Phase 5 diagnosis with Phase 6 sales-delivery services."""

    @classmethod
    def build_center(cls, customers: Iterable[dict[str, Any]] | None) -> dict[str, Any]:
        entries = [cls.build_customer(customer) for customer in (customers or [])]
        entries.sort(
            key=lambda item: (
                item["diagnosis"]["score"],
                item["customer"].get("id", 0),
            ),
            reverse=True,
        )
        funnel = FinanceSalesFunnelAnalyzer.analyze([
            {
                "project": item["project"],
                "diagnosis": item["diagnosis"],
            }
            for item in entries
        ])
        return {
            "customers": entries,
            "funnel": funnel,
            "summary": {
                "total_customers": len(entries),
                "pending_followups": sum(
                    bool(item["followup"].get("next_action")) for item in entries
                ),
                "document_complete_count": sum(
                    item["documents"]["completion_rate"] >= 80 for item in entries
                ),
                "deal_count": funnel["deal_count"],
            },
        }

    @classmethod
    def build_customer(cls, customer: dict[str, Any] | None) -> dict[str, Any]:
        phase5 = FinanceAdvisorCenterService.analyze_customer(customer or {})
        normalized = phase5["customer"]
        diagnosis = phase5["diagnosis"]
        project = FinanceProjectPipelineService.create(normalized, diagnosis)
        followup = FinanceFollowupAgent.generate(
            diagnosis,
            customer=normalized,
            project=project,
        )
        scripts = FinanceSalesScriptAgent.generate(
            diagnosis["level"],
            financing_need=str(
                normalized.get("financing_need") or normalized.get("loan_amount") or ""
            ),
            risks=diagnosis.get("risks") or [],
            customer_name=str(normalized.get("name") or ""),
        )
        matches = phase5["product_matches"].get("matches") or []
        bank_solution = matches[0] if matches else {}
        documents = FinanceDocumentAgent.analyze(
            financing_type=str(bank_solution.get("product_name") or "企业融资"),
            bank_solution=bank_solution,
            existing_documents=normalized.get("documents") or [],
        )
        return {
            **phase5,
            "project": project,
            "followup": followup,
            "sales_scripts": scripts,
            "documents": documents,
        }
