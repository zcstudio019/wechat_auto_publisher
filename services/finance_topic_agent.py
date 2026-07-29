"""Phase 2 topic agent for enterprise-finance acquisition content."""
from __future__ import annotations

import logging
import re
from typing import Any, Iterable

from services.enterprise_finance_content_library import (
    CUSTOMER_PROFILES,
    FINANCING_SCENARIOS,
    INDUSTRY_HOTSPOTS,
    OWNER_PAIN_POINTS,
    match_finance_cta,
)

logger = logging.getLogger(__name__)

TITLE_SCORE_THRESHOLD = 75


class FinanceTopicTitleScorer:
    """Score financing topics with the five Phase 2 dimensions."""

    WEIGHTS = {
        "boss_identity": 20,
        "specific_scenario": 25,
        "pain_intensity": 25,
        "curiosity": 20,
        "action_value": 10,
    }
    OWNER_WORDS = ("老板", "企业主", "公司", "企业", "经营者")
    SCENARIO_WORDS = FINANCING_SCENARIOS + (
        "贷款",
        "融资",
        "银行",
        "额度",
        "流水",
        "续贷",
        "授信",
    )
    PAIN_WORDS = (
        "紧张",
        "拒贷",
        "被拒",
        "不足",
        "征信",
        "负债",
        "困难",
        "失败",
        "过高",
        "只给",
        "只批",
        "不给",
        "批不下",
    )
    CURIOSITY_WORDS = ("为什么", "不一定", "真正", "竟然", "忽略", "问题在哪", "哪一步")
    ACTION_WORDS = ("先查", "检查", "忽略", "解决", "优化", "评估", "诊断", "避免", "怎么做")
    PROHIBITED_PHRASES = ("贷款行业的底层规律", "融资行业分析", "贷款行业分析")

    @classmethod
    def score_title(cls, title: str) -> dict[str, Any]:
        safe_title = re.sub(r"\s+", " ", str(title or "")).strip()
        dimensions = {
            "boss_identity": cls._contains_any(safe_title, cls.OWNER_WORDS),
            "specific_scenario": cls._contains_any(safe_title, cls.SCENARIO_WORDS),
            "pain_intensity": cls._contains_any(safe_title, cls.PAIN_WORDS),
            "curiosity": cls._contains_any(safe_title, cls.CURIOSITY_WORDS),
            "action_value": cls._contains_any(safe_title, cls.ACTION_WORDS),
        }
        score = sum(
            cls.WEIGHTS[name]
            for name, passed in dimensions.items()
            if passed
        )
        prohibited = cls._contains_any(safe_title, cls.PROHIBITED_PHRASES)
        if prohibited:
            score = min(score, 50)
        return {
            "title": safe_title,
            "score": score,
            "title_score": score,
            "dimensions": dimensions,
            "threshold": TITLE_SCORE_THRESHOLD,
            "qualified": score >= TITLE_SCORE_THRESHOLD and not prohibited,
            "prohibited": prohibited,
        }

    @staticmethod
    def _contains_any(text: str, words: Iterable[str]) -> bool:
        return any(word in text for word in words)


class FinanceTopicAgent:
    """Build ten scored financing topics from pain, scenario and customer assets."""

    @classmethod
    def generate_topics(
        cls,
        pain_points: Iterable[str] | None = None,
        scenarios: Iterable[str] | None = None,
        target_customers: Iterable[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        pains = cls._safe_assets(pain_points, OWNER_PAIN_POINTS)
        scenes = cls._safe_assets(scenarios, FINANCING_SCENARIOS)
        customers = cls._safe_assets(target_customers, CUSTOMER_PROFILES)
        safe_limit = max(1, min(int(limit or 10), 10))
        topics: list[dict[str, Any]] = []

        for index in range(safe_limit):
            pain_point = pains[index % len(pains)]
            scenario = cls._scenario_for_pain(pain_point, scenes, index)
            target_customer = customers[index % len(customers)]
            title = cls._build_title(pain_point, scenario, target_customer, index)
            title, title_score = cls._ensure_qualified_title(
                title,
                pain_point,
                scenario,
                target_customer,
            )
            cta = match_finance_cta(
                {
                    "pain_point": pain_point,
                    "scenario": scenario,
                    "title": title,
                }
            )
            topic = {
                "title": title,
                "pain_point": pain_point,
                "scenario": scenario,
                "target_customer": target_customer,
                "conversion_goal": cta["title"],
                "industry_hotspot": INDUSTRY_HOTSPOTS[index % len(INDUSTRY_HOTSPOTS)],
                "score": title_score,
                "article_type": "industry_law",
            }
            topics.append(topic)
            cls.log_topic(topic, generated_article_id="")
        return topics

    @classmethod
    def build_title(
        cls,
        pain_point: str,
        scenario: str,
        target_customer: str,
    ) -> tuple[str, int]:
        """Build one qualified title for article-generation fallback."""
        candidate = cls._build_title(pain_point, scenario, target_customer, 0)
        return cls._ensure_qualified_title(
            candidate,
            pain_point,
            scenario,
            target_customer,
        )

    @classmethod
    def _ensure_qualified_title(
        cls,
        title: str,
        pain_point: str,
        scenario: str,
        target_customer: str,
    ) -> tuple[str, int]:
        first = FinanceTopicTitleScorer.score_title(title)
        if first["qualified"]:
            return first["title"], first["score"]
        regenerated = (
            f"{target_customer}{scenario}遇到{pain_point}，为什么银行审批仍卡住？"
            "老板先查这3个融资条件"
        )
        second = FinanceTopicTitleScorer.score_title(regenerated)
        return second["title"], second["score"]

    @staticmethod
    def _build_title(
        pain_point: str,
        scenario: str,
        target_customer: str,
        index: int,
    ) -> str:
        if "现金流" in pain_point:
            return f"{target_customer}{scenario}时现金流紧张，为什么有利润仍周转困难？先查这3项"
        if "拒贷" in pain_point or "被拒" in pain_point or "失败" in pain_point:
            return f"{target_customer}{scenario}被银行拒贷，为什么换银行仍没用？先查这3个条件"
        if "额度" in pain_point:
            return f"{target_customer}{scenario}，企业流水300万为什么银行只给50万额度？先查这3点"
        if "征信" in pain_point:
            return f"{target_customer}{scenario}，征信没有逾期为什么贷款仍被拒？先检查这3个信号"
        if "负债" in pain_point:
            return f"{target_customer}{scenario}时负债过高，为什么银行不愿新增额度？先做这3项优化"
        if "续贷" in pain_point:
            return f"{target_customer}准备续贷，为什么临近到期更容易失败？提前检查这3个条件"
        if "经营贷" in pain_point:
            return f"{target_customer}首次申请经营贷，为什么有营业执照仍批不下？先查这3项"
        if "扩张" in pain_point:
            return f"{target_customer}{scenario}资金不足，为什么利润不错仍拿不到贷款？先评估这3项"
        if "成本" in pain_point:
            return f"{target_customer}{scenario}融资成本过高，为什么利率越比越高？先优化这3点"
        return (
            f"{target_customer}{scenario}连续申请贷款仍失败，为什么越申请越难？"
            f"先检查这{3 + index % 2}个信号"
        )

    @staticmethod
    def _scenario_for_pain(
        pain_point: str,
        scenarios: tuple[str, ...],
        index: int,
    ) -> str:
        preferred = {
            "现金流紧张": "企业周转",
            "银行拒贷": "申请经营贷",
            "额度不足": "设备采购",
            "征信问题": "申请经营贷",
            "负债过高": "债务优化",
            "续贷困难": "融资规划",
            "经营贷申请": "申请经营贷",
            "企业扩张资金不足": "扩大生产",
            "融资成本过高": "债务优化",
            "贷款申请频繁失败": "申请经营贷",
        }.get(pain_point)
        if preferred and preferred in scenarios:
            return preferred
        return scenarios[index % len(scenarios)]
    @staticmethod
    def _safe_assets(
        values: Iterable[str] | None,
        fallback: tuple[str, ...],
    ) -> tuple[str, ...]:
        if values is None:
            return fallback
        cleaned = tuple(str(value or "").strip() for value in values if str(value or "").strip())
        return cleaned or fallback

    @staticmethod
    def log_topic(topic: dict[str, Any], generated_article_id: Any = "") -> None:
        logger.info(
            "[finance-topic-agent] topic=%s pain_point=%s scenario=%s "
            "title_score=%s generated_article_id=%s",
            topic.get("title") or topic.get("suggested_title") or "",
            topic.get("pain_point") or "",
            topic.get("scenario") or "",
            topic.get("score") or topic.get("title_score") or 0,
            generated_article_id or "",
        )
