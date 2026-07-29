"""Deterministic hit-content analysis for Phase 3 finance growth."""
from __future__ import annotations

from collections import Counter
from typing import Any


class FinanceContentAnalysisAgent:
    """Explain top and low-performing financing articles."""

    @classmethod
    def analyze(cls, growth_analysis: dict[str, Any] | None) -> dict[str, Any]:
        source = growth_analysis or {}
        articles = source.get("articles") if isinstance(source.get("articles"), list) else []
        top_articles = source.get("top_articles") if isinstance(source.get("top_articles"), list) else []
        low_articles = (
            source.get("low_performance_articles")
            if isinstance(source.get("low_performance_articles"), list)
            else []
        )
        return {
            "top_articles": top_articles,
            "low_performance_articles": low_articles,
            "success_reasons": cls._success_reasons(top_articles),
            "failure_reasons": cls._failure_reasons(low_articles),
            "replication_directions": cls._replication_directions(top_articles),
            "optimization_suggestions": cls._optimization_suggestions(low_articles),
            "content_direction_advice": cls._content_direction_advice(articles),
        }

    @staticmethod
    def _success_reasons(articles: list[dict[str, Any]]) -> list[str]:
        if not articles:
            return ["尚无足够的行业规律文章数据，先持续录入阅读和咨询数据。"]
        reasons = []
        if any(item.get("traffic_score", 0) >= 30 for item in articles):
            reasons.append("标题中的老板身份、具体金额或融资冲突带来了更高点击。")
        if any(item.get("interaction_score", 0) >= 22 for item in articles):
            reasons.append("真实案例和银行审核逻辑更容易引发点赞与评论。")
        if any(item.get("acquisition_score", 0) >= 22 for item in articles):
            reasons.append("文章痛点与诊断型CTA匹配，咨询和转化表现更好。")
        return reasons or ["TOP文章整体表现均衡，可继续复制其客户画像和场景组合。"]

    @staticmethod
    def _failure_reasons(articles: list[dict[str, Any]]) -> list[str]:
        if not articles:
            return ["暂未发现明确的低表现文章。"]
        reasons = []
        if any(item.get("traffic_score", 0) < 20 for item in articles):
            reasons.append("标题场景不够具体，点击入口偏弱。")
        if any(item.get("interaction_score", 0) < 15 for item in articles):
            reasons.append("案例细节或老板真实疑问不足，互动动力偏弱。")
        if any(item.get("acquisition_score", 0) < 15 for item in articles):
            reasons.append("CTA与核心痛点衔接不强，咨询动作不够明确。")
        return reasons or ["低表现主要来自流量、互动和获客三项没有形成协同。"]

    @classmethod
    def _replication_directions(cls, articles: list[dict[str, Any]]) -> list[str]:
        if not articles:
            return ["优先测试现金流、拒贷和额度不足三个高频老板痛点。"]
        pain = cls._most_common(articles, "pain_point")
        scenario = cls._most_common(articles, "scenario")
        customer = cls._most_common(articles, "target_customer")
        return [
            f"复制“{customer} + {scenario} + {pain}”的选题组合。",
            "保留具体经营数字、审批冲突和三步解决期待的标题结构。",
            "延续真实案例、银行逻辑、行动方案、诊断CTA的正文顺序。",
        ]

    @staticmethod
    def _optimization_suggestions(articles: list[dict[str, Any]]) -> list[str]:
        if not articles:
            return ["继续积累至少10篇文章的阅读、互动和咨询数据。"]
        suggestions = []
        for item in articles[:3]:
            suggestions.append(
                f"《{item.get('title') or '未命名文章'}》："
                f"{item.get('recommendation') or '强化标题与CTA'}"
            )
        return suggestions

    @classmethod
    def _content_direction_advice(cls, articles: list[dict[str, Any]]) -> list[str]:
        if not articles:
            return ["当前先围绕银行拒贷、现金流紧张、额度不足建立基础样本。"]
        high = [
            item for item in articles
            if item.get("growth_level") == "high_growth"
        ]
        if high:
            pain = cls._most_common(high, "pain_point")
            scenario = cls._most_common(high, "scenario")
            return [
                f"下阶段增加“{pain}”相关内容，占比建议提升到30%。",
                f"优先复用“{scenario}”场景，继续测试不同客户画像。",
                "每个方向至少连续测试3篇，再根据咨询率决定是否放大。",
            ]
        return [
            "目前没有高增长样本，先优化标题场景化和动态CTA匹配。",
            "每周至少测试现金流、拒贷、额度三个不同痛点。",
            "录入咨询与成交数据后再判断主推内容方向。",
        ]

    @staticmethod
    def _most_common(articles: list[dict[str, Any]], field: str) -> str:
        values = [
            str(item.get(field) or "").strip()
            for item in articles
            if str(item.get(field) or "").strip()
        ]
        return Counter(values).most_common(1)[0][0] if values else "企业融资"
