"""Phase 6 financing sales-funnel analysis."""
from __future__ import annotations

from typing import Any, Iterable

from services.finance_project_pipeline_service import FinanceProjectPipelineService


class FinanceSalesFunnelAnalyzer:
    """Calculate lead-to-deal counts, conversion rates and bottlenecks."""

    @classmethod
    def analyze(cls, items: Iterable[dict[str, Any]] | None) -> dict[str, Any]:
        records = list(items or [])
        counts = {
            "lead_count": len(records),
            "contact_count": 0,
            "valid_customer_count": 0,
            "solution_count": 0,
            "deal_count": 0,
        }
        for item in records:
            project = item.get("project") if isinstance(item.get("project"), dict) else item
            stage = str(project.get("current_stage") or cls._stage_from_status(item))
            stage_index = cls._stage_index(stage)
            level = str(
                item.get("level")
                or (item.get("diagnosis") or {}).get("level")
                or project.get("level")
                or "D"
            ).upper()
            if stage_index >= cls._stage_index("初步沟通"):
                counts["contact_count"] += 1
            is_valid = (
                stage_index >= cls._stage_index("资料收集")
                or (
                    level in {"S", "A", "B"}
                    and stage_index >= cls._stage_index("初步沟通")
                )
            )
            if is_valid:
                counts["valid_customer_count"] += 1
            if stage_index >= cls._stage_index("方案确认"):
                counts["solution_count"] += 1
            if stage_index >= cls._stage_index("放款"):
                counts["deal_count"] += 1
        rates = {
            "contact_rate": cls._rate(counts["contact_count"], counts["lead_count"]),
            "valid_customer_rate": cls._rate(
                counts["valid_customer_count"], counts["contact_count"]
            ),
            "solution_rate": cls._rate(
                counts["solution_count"], counts["valid_customer_count"]
            ),
            "deal_rate": cls._rate(counts["deal_count"], counts["solution_count"]),
            "overall_conversion_rate": cls._rate(
                counts["deal_count"], counts["lead_count"]
            ),
        }
        bottlenecks = cls._bottlenecks(counts, rates)
        return {
            **counts,
            "conversion_rates": rates,
            "problem_nodes": bottlenecks,
            "optimization_recommendations": cls._recommendations(bottlenecks),
        }

    @classmethod
    def _bottlenecks(cls, counts: dict[str, int], rates: dict[str, float]) -> list[str]:
        problems = []
        if counts["lead_count"] and rates["contact_rate"] < 0.7:
            problems.append("线索联系率偏低")
        if counts["contact_count"] and rates["valid_customer_rate"] < 0.5:
            problems.append("有效客户识别率偏低")
        if counts["valid_customer_count"] and rates["solution_rate"] < 0.4:
            problems.append("方案产出率偏低")
        if counts["solution_count"] and rates["deal_rate"] < 0.2:
            problems.append("方案到成交转化率偏低")
        return problems or ["当前漏斗未发现明显异常节点"]

    @staticmethod
    def _recommendations(problems: list[str]) -> list[str]:
        mapping = {
            "线索联系率偏低": "缩短S/A级客户首次响应时间，并设置当天未联系提醒。",
            "有效客户识别率偏低": "首次沟通统一核验需求、经营、现金流、负债和征信。",
            "方案产出率偏低": "资料收集阶段使用标准清单，减少反复补件。",
            "方案到成交转化率偏低": "提供主方案和备选方案，提前说明风险与申请顺序。",
        }
        return [mapping[item] for item in problems if item in mapping] or [
            "保持分级跟进节奏，持续记录各阶段转化数据。"
        ]

    @staticmethod
    def _stage_from_status(item: dict[str, Any]) -> str:
        return FinanceProjectPipelineService.LEAD_STATUS_STAGE.get(
            str(item.get("status") or ""), "线索进入"
        )

    @staticmethod
    def _stage_index(stage: str) -> int:
        try:
            return FinanceProjectPipelineService.STAGES.index(stage)
        except ValueError:
            return 0

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float:
        return round(numerator / max(1, denominator), 4)
