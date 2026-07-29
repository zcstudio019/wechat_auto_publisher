"""Phase 3 growth scoring for industry-law financing content."""
from __future__ import annotations

import logging
from typing import Any

from services.enterprise_finance_content_library import (
    CUSTOMER_PROFILES,
    FINANCING_SCENARIOS,
    OWNER_PAIN_POINTS,
)

logger = logging.getLogger(__name__)


class ContentGrowthScore:
    """Calculate a 100-point score: traffic 40%, interaction 30%, leads 30%."""

    HIGH_GROWTH_THRESHOLD = 80
    MEDIUM_GROWTH_THRESHOLD = 50

    @classmethod
    def calculate(
        cls,
        article: dict[str, Any],
        benchmarks: dict[str, float],
    ) -> dict[str, Any]:
        reads = cls._safe_number(article.get("read_count"))
        likes = cls._safe_number(article.get("like_count"))
        comments = cls._safe_number(article.get("comment_count"))
        consults = cls._safe_number(article.get("consult_count"))
        conversions = cls._safe_number(article.get("conversion_count"))

        interaction_rate = (likes + comments * 2) / max(1, reads)
        acquisition_rate = (consults + conversions * 2) / max(1, reads)

        traffic_ratio = reads / max(1.0, benchmarks.get("max_reads", 0))
        interaction_ratio = interaction_rate / max(
            0.000001,
            benchmarks.get("max_interaction_rate", 0),
        )
        acquisition_ratio = acquisition_rate / max(
            0.000001,
            benchmarks.get("max_acquisition_rate", 0),
        )

        traffic_score = round(min(1.0, traffic_ratio) * 40, 2)
        interaction_score = round(
            min(1.0, interaction_ratio) * 30 if interaction_rate else 0,
            2,
        )
        acquisition_score = round(
            min(1.0, acquisition_ratio) * 30 if acquisition_rate else 0,
            2,
        )
        growth_score = round(
            traffic_score + interaction_score + acquisition_score,
            2,
        )
        return {
            "growth_score": growth_score,
            "growth_level": cls.level(growth_score),
            "traffic_score": traffic_score,
            "interaction_score": interaction_score,
            "acquisition_score": acquisition_score,
            "interaction_rate": round(interaction_rate, 4),
            "acquisition_rate": round(acquisition_rate, 4),
        }

    @classmethod
    def level(cls, score: float) -> str:
        if score >= cls.HIGH_GROWTH_THRESHOLD:
            return "high_growth"
        if score >= cls.MEDIUM_GROWTH_THRESHOLD:
            return "medium_growth"
        return "low_growth"

    @staticmethod
    def _safe_number(value: Any) -> int:
        try:
            return max(0, int(float(value or 0)))
        except (TypeError, ValueError):
            return 0


class FinanceContentGrowthAnalyzer:
    """Normalize, score and rank only ``industry_law`` articles."""

    @classmethod
    def analyze_articles(cls, articles: list[dict[str, Any]] | None) -> dict[str, Any]:
        normalized = [
            cls._normalize_article(article)
            for article in (articles or [])
            if cls.is_industry_law(article)
        ]
        benchmarks = cls._build_benchmarks(normalized)
        scored: list[dict[str, Any]] = []
        for article in normalized:
            score = ContentGrowthScore.calculate(article, benchmarks)
            result = {
                **article,
                **score,
            }
            result["recommendation"] = cls._recommendation(result)
            scored.append(result)
            logger.info(
                "[finance-growth-analysis] article_id=%s score=%s recommendation=%s",
                result["article_id"],
                result["growth_score"],
                result["recommendation"],
            )

        scored.sort(
            key=lambda item: (
                item["growth_score"],
                item["read_count"],
            ),
            reverse=True,
        )
        acquisition_ranking = sorted(
            scored,
            key=lambda item: (
                item["consult_count"] + item["conversion_count"] * 2,
                item["acquisition_score"],
                item["read_count"],
            ),
            reverse=True,
        )
        return {
            "articles": scored,
            "top_articles": scored[:5],
            "low_performance_articles": list(reversed(scored[-5:])),
            "acquisition_ranking": acquisition_ranking[:5],
            "summary": cls._summary(scored),
        }

    @classmethod
    def analyze_article(
        cls,
        article: dict[str, Any],
        benchmarks: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Analyze one industry-law article and return its growth score fields."""
        if not cls.is_industry_law(article):
            return {
                "ok": False,
                "error": "仅支持industry_law文章",
                "article_id": ContentGrowthScore._safe_number(
                    article.get("article_id") or article.get("id")
                ),
            }
        normalized = cls._normalize_article(article)
        safe_benchmarks = benchmarks or cls._build_benchmarks([normalized])
        result = {
            "ok": True,
            **normalized,
            **ContentGrowthScore.calculate(normalized, safe_benchmarks),
        }
        result["recommendation"] = cls._recommendation(result)
        logger.info(
            "[finance-growth-analysis] article_id=%s score=%s recommendation=%s",
            result["article_id"],
            result["growth_score"],
            result["recommendation"],
        )
        return result
    @classmethod
    def is_industry_law(cls, article: dict[str, Any] | None) -> bool:
        safe_article = article or {}
        values = {
            str(safe_article.get("article_type") or "").strip(),
            str(safe_article.get("category") or "").strip(),
            str(safe_article.get("category_key") or "").strip(),
            str(safe_article.get("content_strategy") or "").strip(),
        }
        return "industry_law" in values or "enterprise_finance_growth" in values

    @classmethod
    def _normalize_article(cls, article: dict[str, Any]) -> dict[str, Any]:
        title = str(article.get("title") or "未命名融资文章").strip()
        return {
            "article_id": ContentGrowthScore._safe_number(
                article.get("article_id") or article.get("id")
            ),
            "title": title,
            "pain_point": str(
                article.get("pain_point") or cls._infer_value(title, OWNER_PAIN_POINTS)
                or "融资条件不清晰"
            ),
            "scenario": str(
                article.get("scenario") or cls._infer_value(title, FINANCING_SCENARIOS)
                or "企业融资"
            ),
            "target_customer": str(
                article.get("target_customer")
                or cls._infer_value(title, CUSTOMER_PROFILES)
                or "企业老板"
            ),
            "title_score": cls._title_score(article.get("title_score")),
            "read_count": ContentGrowthScore._safe_number(
                article.get("read_count")
                if article.get("read_count") is not None
                else article.get("view_count")
            ),
            "like_count": ContentGrowthScore._safe_number(article.get("like_count")),
            "comment_count": ContentGrowthScore._safe_number(article.get("comment_count")),
            "consult_count": ContentGrowthScore._safe_number(article.get("consult_count")),
            "conversion_count": ContentGrowthScore._safe_number(
                article.get("conversion_count")
                if article.get("conversion_count") is not None
                else article.get("deal_count")
            ),
            "article_type": "industry_law",
        }

    @staticmethod
    def _infer_value(title: str, values: tuple[str, ...]) -> str:
        return next((value for value in values if value in title), "")

    @staticmethod
    def _title_score(value: Any) -> int:
        if isinstance(value, dict):
            value = value.get("score") or value.get("title_score")
        return ContentGrowthScore._safe_number(value)

    @staticmethod
    def _build_benchmarks(articles: list[dict[str, Any]]) -> dict[str, float]:
        interaction_rates = [
            (item["like_count"] + item["comment_count"] * 2)
            / max(1, item["read_count"])
            for item in articles
        ]
        acquisition_rates = [
            (item["consult_count"] + item["conversion_count"] * 2)
            / max(1, item["read_count"])
            for item in articles
        ]
        return {
            "max_reads": max((item["read_count"] for item in articles), default=0),
            "max_interaction_rate": max(interaction_rates, default=0),
            "max_acquisition_rate": max(acquisition_rates, default=0),
        }

    @staticmethod
    def _recommendation(article: dict[str, Any]) -> str:
        recommendations = []
        if article["traffic_score"] < 24:
            recommendations.append("强化老板场景标题和开头冲突")
        if article["interaction_score"] < 18:
            recommendations.append("增加可讨论的真实疑问与案例细节")
        if article["acquisition_score"] < 18:
            recommendations.append("让CTA与痛点匹配并降低咨询门槛")
        if not recommendations:
            return "保持当前结构，复制该痛点与场景组合"
        return "；".join(recommendations)

    @staticmethod
    def _summary(articles: list[dict[str, Any]]) -> dict[str, Any]:
        count = len(articles)
        return {
            "total_articles": count,
            "average_growth_score": round(
                sum(item["growth_score"] for item in articles) / count,
                2,
            ) if count else 0,
            "high_growth_count": sum(
                item["growth_level"] == "high_growth" for item in articles
            ),
            "medium_growth_count": sum(
                item["growth_level"] == "medium_growth" for item in articles
            ),
            "low_growth_count": sum(
                item["growth_level"] == "low_growth" for item in articles
            ),
        }
