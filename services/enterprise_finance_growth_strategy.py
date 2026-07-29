"""Phase 1 content strategy for enterprise-finance lead generation."""
from __future__ import annotations

import re
from typing import Any


enterprise_finance_growth = {
    "title_strategy": "企业老板真实融资场景标题",
    "audience": [
        "企业老板",
        "小微企业主",
        "经营者",
    ],
    "pain_points": [
        "银行拒贷",
        "额度低",
        "负债高",
        "征信问题",
        "现金流紧张",
        "续贷困难",
        "利率过高",
        "融资规划错误",
    ],
    "scenarios": [
        "经营贷申请",
        "企业周转",
        "扩大经营",
        "贷款被拒",
        "银行额度不足",
        "融资成本优化",
    ],
}

TITLE_SCORE_THRESHOLD = 70
PROMPT_VERSION = "phase1"


class FinanceGrowthTitleScorer:
    """Score titles with the five Phase 1 acquisition dimensions."""

    OWNER_WORDS = ("老板", "企业主", "小微企业", "公司", "企业", "经营者")
    FINANCE_WORDS = (
        "融资", "贷款", "经营贷", "周转", "额度", "续贷", "利率", "银行",
    )
    PAIN_WORDS = (
        "拒贷", "被拒", "不批", "批不下", "只批", "额度低", "额度不足",
        "负债高", "征信", "现金流紧", "现金流断", "续贷难", "利率高",
        "成本高", "融资规划错",
    )
    EXPECTATION_WORDS = (
        "为什么", "原因", "怎么办", "怎么做", "如何", "先查", "先看",
        "忽略", "真正看", "这3个", "这4个", "解决", "优化", "提升",
        "诊断", "体检", "关键",
    )
    UNNATURAL_WORDS = (
        "贷款行业有什么规律", "全面解析", "一文读懂", "必知基础",
        "关键事项", "稳健发展", "专业解决方案服务",
    )
    WEIGHTS = {
        "boss_identity": 20,
        "financing_need": 25,
        "pain_intensity": 25,
        "solution_expectation": 20,
        "naturalness": 10,
    }

    @classmethod
    def score_title(cls, title: str) -> dict[str, Any]:
        safe_title = re.sub(r"\s+", " ", str(title or "")).strip()
        dimensions = {
            "boss_identity": cls._contains_any(safe_title, cls.OWNER_WORDS),
            "financing_need": cls._contains_any(safe_title, cls.FINANCE_WORDS),
            "pain_intensity": cls._contains_any(safe_title, cls.PAIN_WORDS),
            "solution_expectation": cls._contains_any(safe_title, cls.EXPECTATION_WORDS),
            "naturalness": cls._is_natural(safe_title),
        }
        score = sum(
            cls.WEIGHTS[name]
            for name, passed in dimensions.items()
            if passed
        )
        return {
            "title": safe_title,
            "title_score": min(100, score),
            "dimensions": dimensions,
            "threshold": TITLE_SCORE_THRESHOLD,
            "qualified": score >= TITLE_SCORE_THRESHOLD,
        }

    @classmethod
    def build_scenario_title(cls, keyword: str) -> str:
        """Generate a deterministic owner-scenario title when AI title is weak."""
        topic = re.sub(r"\s+", " ", str(keyword or "")).strip()
        if "最缺钱" in topic or "残酷真相" in topic:
            return "公司流水500万，为什么银行只批30万额度？老板最容易忽略这3个原因"
        if "征信" in topic:
            return "征信没有逾期，为什么贷款还是被拒？老板要先看银行审核的这3个信号"
        if "拒贷" in topic or "被拒" in topic:
            return "贷款被拒后，老板先别急着换银行：这3个融资条件更值得检查"
        if "额度" in topic:
            return "公司有流水，银行额度为什么还是低？老板先检查这3个融资条件"
        if "现金流" in topic or "周转" in topic:
            return "公司有利润却现金流紧张，老板融资前要先解决这3个问题"
        if "续贷" in topic:
            return "企业续贷为什么越来越难？老板要提前检查这3个融资条件"
        if "利率" in topic or "成本" in topic:
            return "企业贷款利率为什么偏高？老板先看这3个融资成本问题"
        return "企业融资为什么总卡住？老板先检查银行最关注的这3个条件"

    @staticmethod
    def _contains_any(text: str, words: tuple[str, ...]) -> bool:
        return any(word in text for word in words)

    @classmethod
    def _is_natural(cls, title: str) -> bool:
        if not 14 <= len(title) <= 48:
            return False
        if "\n" in title or title.count("？") + title.count("?") > 1:
            return False
        return not cls._contains_any(title, cls.UNNATURAL_WORDS)
