"""Phase 4 conversion tracking for enterprise-finance growth content."""
from __future__ import annotations

import logging
from typing import Any

from services.finance_content_growth_analyzer import FinanceContentGrowthAnalyzer

logger = logging.getLogger(__name__)


class FinanceConversionTracker:
    """Aggregate conversion data for ``industry_law`` articles only.

    The current growth table stores QR scans, consultations and deals.  Phase 4
    accepts dedicated CTA-click and WeChat-add fields when available, while
    retaining compatible aliases for existing data.
    """

    EVENT_FIELDS = {
        "cta_click": "click_count",
        "click": "click_count",
        "wechat_add": "wechat_add_count",
        "consult": "consult_count",
        "deal": "deal_count",
    }

    def __init__(self) -> None:
        self._records: dict[int, dict[str, Any]] = {}

    def record(
        self,
        article: dict[str, Any],
        conversion_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Normalize and keep one finance-content conversion record."""
        combined = {**(article or {}), **(conversion_data or {})}
        if not FinanceContentGrowthAnalyzer.is_industry_law(combined):
            return {
                "ok": False,
                "error": "仅支持industry_law文章",
                "article_id": self._safe_int(combined.get("article_id") or combined.get("id")),
            }

        record = self._normalize(combined)
        self._records[record["article_id"]] = record
        logger.info(
            "[finance-conversion-tracker] article_id=%s cta_type=%s clicks=%s "
            "wechat_adds=%s consults=%s deals=%s",
            record["article_id"],
            record["cta_type"],
            record["click_count"],
            record["wechat_add_count"],
            record["consult_count"],
            record["deal_count"],
        )
        return {"ok": True, **record}

    def record_event(self, article_id: int, event: str, count: int = 1) -> dict[str, Any]:
        """Increment a conversion event for a previously recorded article."""
        safe_id = self._safe_int(article_id)
        record = self._records.get(safe_id)
        field = self.EVENT_FIELDS.get(str(event or "").strip().lower())
        if record is None:
            return {"ok": False, "error": "文章转化记录不存在", "article_id": safe_id}
        if field is None:
            return {"ok": False, "error": "不支持的转化事件", "article_id": safe_id}
        record[field] += max(0, self._safe_int(count))
        self._refresh_derived(record)
        return {"ok": True, **record}

    def get_record(self, article_id: int) -> dict[str, Any] | None:
        record = self._records.get(self._safe_int(article_id))
        return dict(record) if record else None

    def conversion_ranking(self, limit: int = 10) -> list[dict[str, Any]]:
        ranked = sorted(
            self._records.values(),
            key=lambda item: (
                item["deal_count"],
                item["consult_count"],
                item["wechat_add_count"],
                item["click_count"],
                item["read_count"],
            ),
            reverse=True,
        )
        return [dict(item) for item in ranked[: max(0, self._safe_int(limit))]]

    def build_funnel(self) -> dict[str, Any]:
        records = list(self._records.values())
        reads = sum(item["read_count"] for item in records)
        consultations = sum(item["click_count"] for item in records)
        leads = sum(item["wechat_add_count"] for item in records)
        valid_leads = sum(item["consult_count"] for item in records)
        deals = sum(item["deal_count"] for item in records)
        return {
            "read_count": reads,
            "consult_count": consultations,
            "lead_count": leads,
            "valid_lead_count": valid_leads,
            "deal_count": deals,
            "consult_rate": self._rate(consultations, reads),
            "lead_rate": self._rate(leads, consultations),
            "valid_lead_rate": self._rate(valid_leads, leads),
            "deal_rate": self._rate(deals, valid_leads),
        }

    def recommend_high_value_content(self, limit: int = 5) -> list[dict[str, Any]]:
        records = sorted(
            self._records.values(),
            key=lambda item: (
                item["value_score"],
                item["deal_count"],
                item["consult_count"],
            ),
            reverse=True,
        )
        recommendations = []
        for item in records[: max(0, self._safe_int(limit))]:
            if item["deal_count"]:
                reason = f"已带来{item['deal_count']}个成交，建议复制该痛点和CTA组合"
            elif item["consult_count"]:
                reason = f"已获得{item['consult_count']}个有效客户，建议延展同类场景"
            elif item["click_count"]:
                reason = "CTA点击表现较好，可补强案例与信任证据促进留资"
            else:
                reason = "已有阅读基础，建议优化CTA与咨询入口"
            recommendations.append({
                **item,
                "reason": reason,
                "recommendation": reason,
            })
        return recommendations

    @classmethod
    def analyze_articles(cls, articles: list[dict[str, Any]] | None) -> dict[str, Any]:
        tracker = cls()
        for article in articles or []:
            if FinanceContentGrowthAnalyzer.is_industry_law(article):
                tracker.record(article)
        return {
            "records": tracker.conversion_ranking(limit=len(tracker._records)),
            "ranking": tracker.conversion_ranking(limit=10),
            "funnel": tracker.build_funnel(),
            "recommendations": tracker.recommend_high_value_content(limit=5),
            "summary": {
                "total_articles": len(tracker._records),
                "total_deals": sum(
                    item["deal_count"] for item in tracker._records.values()
                ),
            },
        }

    @classmethod
    def _normalize(cls, article: dict[str, Any]) -> dict[str, Any]:
        click_count = cls._first_number(article, "click_count", "cta_click_count", "scan_count")
        consult_count = cls._first_number(article, "consult_count", "valid_lead_count")
        wechat_add_count = cls._first_number(
            article,
            "wechat_add_count",
            "wechat_count",
            fallback=consult_count,
        )
        cta = article.get("cta")
        cta_title = cta.get("title") if isinstance(cta, dict) else cta
        record = {
            "article_id": cls._safe_int(article.get("article_id") or article.get("id")),
            "title": str(article.get("title") or "未命名融资文章").strip(),
            "cta_type": str(
                article.get("cta_type")
                or article.get("conversion_goal")
                or cta_title
                or "企业融资体检"
            ).strip(),
            "conversion_goal": str(
                article.get("conversion_goal") or cta_title or "企业融资体检"
            ).strip(),
            "read_count": cls._first_number(article, "read_count", "view_count"),
            "click_count": click_count,
            "wechat_add_count": wechat_add_count,
            "consult_count": consult_count,
            "deal_count": cls._first_number(article, "deal_count", "conversion_count"),
            "article_type": "industry_law",
        }
        cls._refresh_derived(record)
        return record

    @classmethod
    def _refresh_derived(cls, record: dict[str, Any]) -> None:
        record["click_rate"] = cls._rate(record["click_count"], record["read_count"])
        record["deal_rate"] = cls._rate(record["deal_count"], record["consult_count"])
        record["value_score"] = round(
            record["deal_count"] * 40
            + record["consult_count"] * 12
            + record["wechat_add_count"] * 5
            + record["click_count"],
            2,
        )

    @classmethod
    def _first_number(
        cls,
        values: dict[str, Any],
        *keys: str,
        fallback: int = 0,
    ) -> int:
        for key in keys:
            if values.get(key) is not None:
                return cls._safe_int(values.get(key))
        return cls._safe_int(fallback)

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return max(0, int(float(value or 0)))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float:
        return round(numerator / max(1, denominator), 4)
