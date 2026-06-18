"""Rule-based title scoring for enterprise-finance lead-generation articles."""
from __future__ import annotations

import re
from typing import Any


class TitleScoreService:
    """Score WeChat titles and generate stronger conversion-oriented variants."""

    PAIN_WORDS = (
        "拒贷", "被拒", "批不下", "额度低", "续贷", "征信", "现金流", "周转",
        "负债", "查询", "流水", "银行为什么", "不批", "踩坑", "风险",
    )
    RESULT_WORDS = ("额度", "提升", "批", "通过", "少走弯路", "降低", "补救", "重新")
    CONFLICT_WORDS = ("为什么", "不是", "别急", "反而", "先别", "真正", "不是银行")
    OWNER_WORDS = ("老板", "企业主", "小微企业", "经营贷", "银行", "融资", "贷款")
    AI_SCIENCE_WORDS = ("科普", "一文读懂", "全面解析", "基础知识", "干货分享", "你需要知道")
    CONVERSION_WORDS = ("诊断", "体检", "被拒原因", "额度怎么提升", "申请", "咨询", "评估")

    @classmethod
    def score_title(cls, title: str) -> dict[str, Any]:
        safe_title = str(title or "").strip()
        checks = {
            "specific_pain_point": cls._contains_any(safe_title, cls.PAIN_WORDS),
            "number_or_result": bool(re.search(r"\d", safe_title)) or cls._contains_any(safe_title, cls.RESULT_WORDS),
            "conflict": cls._contains_any(safe_title, cls.CONFLICT_WORDS),
            "boss_click_fit": cls._contains_any(safe_title, cls.OWNER_WORDS),
            "avoid_ai_science_feel": not cls._contains_any(safe_title, cls.AI_SCIENCE_WORDS),
            "consulting_conversion": cls._contains_any(safe_title, cls.CONVERSION_WORDS),
        }
        weights = {
            "specific_pain_point": 22,
            "number_or_result": 16,
            "conflict": 16,
            "boss_click_fit": 18,
            "avoid_ai_science_feel": 12,
            "consulting_conversion": 16,
        }
        score = sum(weights[key] for key, passed in checks.items() if passed)
        if len(safe_title) < 8 or len(safe_title) > 28:
            score = max(0, score - 8)

        result = {
            "title": safe_title,
            "score": min(100, score),
            "dimensions": checks,
            "problems": cls._problems(checks, safe_title),
            "optimized_titles": [],
        }
        if result["score"] < 80:
            result["optimized_titles"] = cls.optimize_titles(safe_title)
        return result

    @classmethod
    def optimize_titles(cls, title: str) -> list[str]:
        base = str(title or "").strip(" ？?。") or "企业融资"
        return [
            f"老板{base}，银行为什么不批？",
            f"{base}被拒后，先查这3个原因",
            f"{base}额度低，问题通常出在这4处",
            f"企业主申请{base}前，先做一次融资体检",
            f"{base}不是换家银行就能解决",
        ][:5]

    @staticmethod
    def _contains_any(text: str, words: tuple[str, ...]) -> bool:
        return any(word in text for word in words)

    @classmethod
    def _problems(cls, checks: dict[str, bool], title: str) -> list[str]:
        problems: list[str] = []
        if not checks["specific_pain_point"]:
            problems.append("缺少具体痛点，老板不容易判断和自己有关。")
        if not checks["number_or_result"]:
            problems.append("缺少数字或结果感，点击预期不够明确。")
        if not checks["conflict"]:
            problems.append("冲突感不足，像普通说明文标题。")
        if not checks["boss_click_fit"]:
            problems.append("没有直接点到老板、企业主、银行审批等决策语境。")
        if not checks["avoid_ai_science_feel"]:
            problems.append("有知识科普感，容易降低咨询转化。")
        if not checks["consulting_conversion"]:
            problems.append("缺少融资诊断、被拒原因、额度提升等转化钩子。")
        if len(title) < 8 or len(title) > 28:
            problems.append("标题长度不适合公众号列表快速阅读。")
        return problems
