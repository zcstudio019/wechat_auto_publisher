"""Data-aware title optimizer for Phase 3 financing content."""
from __future__ import annotations

from typing import Any

from services.finance_topic_agent import (
    FinanceTopicAgent,
    FinanceTopicTitleScorer,
)


class FinanceTitleOptimizer:
    """Optimize an industry-law title using its performance and topic context."""

    @classmethod
    def optimize(cls, article: dict[str, Any] | None) -> dict[str, Any]:
        safe_article = article or {}
        original_title = str(safe_article.get("title") or "企业融资").strip()
        pain_point = str(safe_article.get("pain_point") or "银行拒贷").strip()
        scenario = str(safe_article.get("scenario") or "申请经营贷").strip()
        target_customer = str(
            safe_article.get("target_customer") or "企业老板"
        ).strip()
        original_result = FinanceTopicTitleScorer.score_title(original_title)
        optimized_title, _ = FinanceTopicAgent.build_title(
            pain_point,
            scenario,
            target_customer,
        )
        if optimized_title == original_title:
            optimized_title = (
                f"{target_customer}{scenario}遇到{pain_point}，"
                "为什么银行审批仍卡住？先检查这3个融资条件"
            )
        optimized_result = FinanceTopicTitleScorer.score_title(optimized_title)
        growth_level = str(safe_article.get("growth_level") or "low_growth")
        reason = cls._reason(
            original_result,
            optimized_result,
            growth_level,
            safe_article,
        )
        return {
            "article_id": safe_article.get("article_id") or safe_article.get("id") or 0,
            "original_title": original_title,
            "optimized_title": optimized_result["title"],
            "reason": reason,
            "original_score": original_result["score"],
            "optimized_score": optimized_result["score"],
            "score_change": optimized_result["score"] - original_result["score"],
        }

    @staticmethod
    def _reason(
        original: dict[str, Any],
        optimized: dict[str, Any],
        growth_level: str,
        article: dict[str, Any],
    ) -> str:
        missing = [
            label
            for key, label in (
                ("boss_identity", "老板身份"),
                ("specific_scenario", "具体融资场景"),
                ("pain_intensity", "痛点冲突"),
                ("curiosity", "好奇心"),
                ("action_value", "行动价值"),
            )
            if not original.get("dimensions", {}).get(key)
        ]
        reasons = []
        if missing:
            reasons.append(f"原标题缺少{'、'.join(missing)}")
        if growth_level == "low_growth":
            reasons.append("当前文章增长表现偏低")
        elif growth_level == "medium_growth":
            reasons.append("当前文章仍有点击和获客提升空间")
        if article.get("traffic_score", 0) < 24:
            reasons.append("流量评分偏低，需要强化场景冲突")
        if not reasons and optimized["score"] >= original["score"]:
            reasons.append("保留原有高分结构，并提高标题与本次痛点的匹配度")
        return "；".join(reasons)

    @classmethod
    def optimize_articles(
        cls,
        articles: list[dict[str, Any]] | None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        candidates = [
            article
            for article in (articles or [])
            if article.get("growth_level") != "high_growth"
            or FinanceTopicTitleScorer.score_title(article.get("title", ""))["score"] < 75
        ]
        candidates.sort(
            key=lambda item: (
                item.get("growth_score", 0),
                item.get("title_score", 0),
            )
        )
        return [cls.optimize(article) for article in candidates[: max(1, int(limit or 5))]]
