"""Wechat draft title optimizer.

This module only prepares the title used by the WeChat draft card. It must not
rewrite the article title stored in the database.
"""

from __future__ import annotations

import re


TITLE_MIN_CHARS = 18
TITLE_MAX_CHARS = 28

_PREFIX_HINTS = {
    "经营贷申请攻略": "经营贷",
    "经营贷攻略": "经营贷",
    "融资规划": "融资规划",
    "知识科普": "科普",
    "贷款知识科普": "贷款",
    "热点解读": "热点",
    "方案匹配": "方案匹配",
    "贷款方案匹配": "贷款",
    "企业经营分析": "经营分析",
    "经营分析": "经营分析",
    "品牌宣传": "品牌",
    "自动获客": "获客",
}

_LONG_PREFIXES = tuple(sorted(_PREFIX_HINTS, key=len, reverse=True))

_FILLER_WORDS = (
    "一文看懂",
    "全面解析",
    "深度解析",
    "详细攻略",
    "完整攻略",
    "最新攻略",
    "实用攻略",
    "申请攻略",
    "操作指南",
    "解决方案",
    "专业服务",
)


def optimize_wechat_title(title: str) -> str:
    """Optimize a title for the WeChat draft card without changing DB title.

    Rules:
    - Move long category prefixes away from the front.
    - Keep core information first.
    - Prefer problem / benefit / risk / result oriented phrasing.
    - Keep the title concise, aiming for 18-28 Chinese characters.
    """

    cleaned = _clean_title(title)
    if not cleaned:
        return "企业融资规划怎么做更稳妥"

    body, hint = _remove_long_prefix(cleaned)
    body = _remove_fillers(body)
    body = _normalize_common_patterns(body)

    if hint and hint not in body and len(body) + len(hint) + 2 <= TITLE_MAX_CHARS:
        body = f"{body}（{hint}）"

    body = _prefer_wechat_style(body, hint)
    body = _truncate_title(body)

    return body or "企业融资规划怎么做更稳妥"


def _clean_title(title: str) -> str:
    text = str(title or "").strip()
    text = re.sub(r"^#+\s*", "", text)
    text = re.sub(r"\s+", "", text)
    text = text.strip("「」『』《》[]【】()（）|｜-—_:： ")
    text = re.sub(r"[-—|｜]\s*沪上银.*$", "", text)
    return text.strip()


def _remove_long_prefix(title: str) -> tuple[str, str]:
    for prefix in _LONG_PREFIXES:
        pattern = rf"^{re.escape(prefix)}[：:｜|、\-\—]?"
        if re.match(pattern, title):
            body = re.sub(pattern, "", title, count=1).strip("：:｜|、-— ")
            return body or title, _PREFIX_HINTS.get(prefix, "")
    return title, ""


def _remove_fillers(title: str) -> str:
    result = title
    for word in _FILLER_WORDS:
        result = result.replace(word, "")
    result = re.sub(r"(解析|说明|指南){2,}$", "指南", result)
    return result.strip("：:｜|、-— ")


def _normalize_common_patterns(title: str) -> str:
    replacements = (
        ("企业资金安排和风险把控", "企业资金安排与风险把控"),
        ("资金安排及风险把控", "资金安排与风险把控"),
        ("贷款融资", "融资"),
        ("融资贷款", "融资"),
        ("经营贷贷款", "经营贷"),
    )
    result = title
    for old, new in replacements:
        result = result.replace(old, new)
    return result


def _prefer_wechat_style(title: str, hint: str = "") -> str:
    if len(title) <= TITLE_MAX_CHARS and _has_title_hook(title):
        return title

    if "被拒" in title and "经营贷" in title:
        return "经营贷为什么被拒？先看这几点"
    if "被拒" in title and ("贷款" in title or "融资" in title):
        return "贷款被拒后，先排查这几个问题"
    if "避坑" in title:
        return title
    if "申请" in title and "经营贷" in title and len(title) > TITLE_MAX_CHARS:
        return "企业经营贷申请避坑指南"
    if "现金流" in title and ("压力" in title or "周转" in title):
        return "现金流吃紧时，企业该怎么周转"
    if "风险" in title and "把控" in title:
        return title
    if hint == "经营贷" and "申请" in title and len(title) > TITLE_MAX_CHARS:
        return "企业经营贷申请避坑指南"
    return title


def _has_title_hook(title: str) -> bool:
    markers = (
        "？",
        "?",
        "怎么",
        "为什么",
        "为何",
        "避坑",
        "风险",
        "把控",
        "指南",
        "结果",
        "提升",
        "降低",
        "解决",
    )
    return any(marker in title for marker in markers)


def _truncate_title(title: str) -> str:
    if len(title) <= TITLE_MAX_CHARS:
        return title

    # Prefer keeping the core part before punctuation if it is still readable.
    for mark in ("，", "。", "；", ";", "：", ":"):
        index = title.find(mark)
        if TITLE_MIN_CHARS <= index <= TITLE_MAX_CHARS:
            return title[:index].strip()

    # Drop parenthetical hint first if the core title is too long.
    without_hint = re.sub(r"（[^）]{1,8}）$", "", title).strip()
    if TITLE_MIN_CHARS <= len(without_hint) <= TITLE_MAX_CHARS:
        return without_hint

    return title[:TITLE_MAX_CHARS].rstrip("，。；：、-— ")
