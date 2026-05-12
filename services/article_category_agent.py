"""Keyword-driven article category detection for the generation console."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

logger = logging.getLogger(__name__)


class ArticleCategoryAgent:
    """Use lightweight rules first, then fall back to AI when rules are weak."""

    CATEGORY_LABELS = {
        "leads": "自动获客",
        "brand": "品牌宣传",
        "science": "知识科普",
        "hotspot": "热点解读",
        "service": "方案匹配",
        "finance": "融资规划",
        "enterprise": "经营分析",
    }
    LABEL_TO_KEY = {label: key for key, label in CATEGORY_LABELS.items()}
    RULES = (
        {
            "keywords": ("现金流", "资金周转", "资金缺口", "融资节奏", "还款安排"),
            "primary": "finance",
            "secondary": ("enterprise",),
            "reason": "关键词更偏企业资金安排，同时涉及经营状况判断。",
        },
        {
            "keywords": ("被拒", "拒贷", "审核不过", "申请失败", "批不下来"),
            "primary": "science",
            "secondary": ("service",),
            "reason": "关键词适合先解释被拒原因，再给出适配思路。",
        },
        {
            "keywords": ("利率政策", "政策变化", "监管", "降息", "市场变化", "新规"),
            "primary": "hotspot",
            "secondary": ("science",),
            "reason": "关键词带有政策或市场变化属性，适合做热点解读。",
        },
        {
            "keywords": ("征信", "流水", "负债", "报表", "纳税", "额度"),
            "primary": "science",
            "secondary": ("service",),
            "reason": "关键词更适合先做知识解释，再衔接方案判断。",
        },
        {
            "keywords": ("方案", "匹配", "哪种贷款", "适合什么", "产品怎么选"),
            "primary": "service",
            "secondary": ("science",),
            "reason": "关键词明显偏向融资方案对比与适配。",
        },
        {
            "keywords": ("利润", "成本", "应收账款", "库存", "负债结构", "经营问题"),
            "primary": "enterprise",
            "secondary": ("finance",),
            "reason": "关键词涉及企业经营质量与资金结构分析。",
        },
        {
            "keywords": ("品牌", "口碑", "案例", "服务能力", "顾问团队"),
            "primary": "brand",
            "secondary": ("leads",),
            "reason": "关键词适合塑造专业度与品牌可信度。",
        },
        {
            "keywords": ("咨询", "获客", "私信", "留资", "客户线索"),
            "primary": "leads",
            "secondary": ("brand",),
            "reason": "关键词更偏引流与咨询转化。",
        },
    )

    def __init__(self) -> None:
        self.client = None
        if not OPENAI_API_KEY:
            return
        try:
            from openai import OpenAI

            self.client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        except Exception as exc:  # pragma: no cover - runtime dependent
            logger.warning("[ArticleCategoryAgent] OpenAI 初始化失败: %s", exc)

    def detect_categories(self, keyword: str) -> dict[str, Any]:
        """Return the best primary category plus optional secondary categories."""
        safe_keyword = self._safe_text(keyword)
        if not safe_keyword:
            return {
                "ok": False,
                "msg": "请输入关键词",
                "primary_category": "",
                "secondary_categories": [],
                "reason": "",
            }

        rule_result = self._detect_by_rules(safe_keyword)
        if rule_result:
            return rule_result

        ai_result = self._detect_by_ai(safe_keyword)
        if ai_result:
            return ai_result

        return {
            "ok": True,
            "primary_category": "science",
            "secondary_categories": [],
            "reason": "未命中明确规则，且 AI 分类暂不可用，先按知识科普生成，可再手动调整。",
            "source": "fallback",
        }

    def _detect_by_rules(self, keyword: str) -> dict[str, Any] | None:
        for rule in self.RULES:
            matches = [item for item in rule["keywords"] if item in keyword]
            if not matches:
                continue
            return {
                "ok": True,
                "primary_category": rule["primary"],
                "secondary_categories": list(rule["secondary"]),
                "reason": f"命中关键词：{'、'.join(matches)}。{rule['reason']}",
                "source": "rule",
            }
        return None

    def _detect_by_ai(self, keyword: str) -> dict[str, Any] | None:
        if not OPENAI_API_KEY or self.client is None:
            return None

        raw_response = ""
        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "你是公众号文章分类 Agent，只返回严格 JSON。",
                    },
                    {
                        "role": "user",
                        "content": self._build_ai_prompt(keyword),
                    },
                ],
                temperature=0.2,
                max_tokens=500,
            )
            raw_response = (response.choices[0].message.content or "").strip()
            payload = self._parse_json_response(raw_response)
            primary = self._normalize_category(payload.get("primary_category"))
            secondaries = self._normalize_categories(payload.get("secondary_categories"), exclude=primary)
            reason = self._safe_text(payload.get("reason")) or "AI 根据关键词语义完成分类判断。"
            if not primary:
                return None
            return {
                "ok": True,
                "primary_category": primary,
                "secondary_categories": secondaries,
                "reason": reason,
                "source": "ai",
            }
        except Exception as exc:
            logger.warning("[ArticleCategoryAgent] AI 分类失败: %s; raw=%s", exc, raw_response[:200])
            return None

    def _build_ai_prompt(self, keyword: str) -> str:
        labels = "、".join(self.CATEGORY_LABELS.values())
        return f"""
请判断关键词“{keyword}”最适合用于哪类公众号文章。
可选分类仅限：{labels}

只返回 JSON：
{{
  "primary_category": "分类名称",
  "secondary_categories": ["分类名称1", "分类名称2"],
  "reason": "一句话理由"
}}

要求：
1. primary_category 必须只有 1 个。
2. secondary_categories 最多 2 个，可为空。
3. 如果关键词同时涉及经营与融资，请允许多分类。
4. 不要输出 Markdown，不要解释 JSON 之外的内容。
""".strip()

    def _normalize_category(self, category: Any) -> str:
        safe = self._safe_text(category)
        if safe in self.CATEGORY_LABELS:
            return safe
        return self.LABEL_TO_KEY.get(safe, "")

    def _normalize_categories(self, values: Any, exclude: str = "") -> list[str]:
        raw_values = values if isinstance(values, list) else [values]
        result: list[str] = []
        for item in raw_values:
            normalized = self._normalize_category(item)
            if normalized and normalized != exclude and normalized not in result:
                result.append(normalized)
        return result[:2]

    def _parse_json_response(self, raw_response: str) -> dict[str, Any]:
        text = (raw_response or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise

    def _safe_text(self, value: Any) -> str:
        return str(value or "").strip()


def detect_categories(keyword: str) -> dict[str, Any]:
    """Convenience wrapper for callers that prefer a functional entrypoint."""
    return ArticleCategoryAgent().detect_categories(keyword)
