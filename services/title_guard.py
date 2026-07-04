from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from typing import Any, Iterable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TitleGuardResult:
    title: str
    original_title: str
    changed: bool
    qualified: bool
    score: int
    reasons: tuple[str, ...]


class TitleGuard:
    """Validate and repair generated article titles before they are saved or published."""

    FALLBACK_TITLE = "经营贷被拒？先查这3个地方"
    MAX_CJK_CHARS = 36
    RECOMMENDED_TITLES = (
        "经营贷总被拒？先查这3个地方",
        "银行为什么不批？问题多半在这几点",
        "有流水也被拒？老板先看这3个信号",
        "贷款批不下来，不一定是银行的问题",
        "申请经营贷前，先做这5步体检",
    )
    INCOMPLETE_ENDINGS = (
        "为什么不",
        "银行为什么不",
        "怎么办才",
        "到底差在哪",
        "该如何",
        "如何做才",
        "银行不给",
        "银行为何",
        "老板该",
        "申请前先",
    )
    SUSPICIOUS_TAILS = (
        "为什么",
        "为什么不",
        "怎么办",
        "怎么才",
        "如何做",
        "如何做才",
        "该如何",
        "该怎么",
        "银行不给",
        "银行为何",
        "老板该",
        "申请前先",
        "不批",
        "不给批",
    )
    AI_PHRASES = (
        "科学规划",
        "稳健发展",
        "必知基础",
        "关键事项",
        "深度解析",
        "一文读懂",
    )
    REPEATED_WORDS = ("老板", "经营贷", "银行")
    END_PUNCTUATION = "。！？!?》）)"

    @classmethod
    def sanitize_title(
        cls,
        title: Any,
        candidates: Iterable[Any] | None = None,
        keyword: str = "",
        fallback_title: str | None = None,
    ) -> dict[str, Any]:
        original_title = cls._clean_title(title)
        candidate_list = cls._dedupe_candidates([original_title, *(list(candidates or []))])
        chosen = cls.choose_best_title(candidate_list, keyword=keyword, fallback_title=fallback_title)
        inspection = cls.inspect_title(chosen)
        final_title = chosen if inspection["qualified"] else (fallback_title or cls.FALLBACK_TITLE)
        if not cls.inspect_title(final_title)["qualified"]:
            final_title = cls.FALLBACK_TITLE
        changed = final_title != original_title
        if changed:
            logger.warning("[title-guard-fixed] original_title=%s fixed_title=%s", original_title, final_title)
        final_inspection = cls.inspect_title(final_title)
        return {
            "title": final_title,
            "original_title": original_title,
            "changed": changed,
            "qualified": final_inspection["qualified"],
            "score": final_inspection["score"],
            "reasons": final_inspection["reasons"],
        }

    @classmethod
    def choose_best_title(
        cls,
        candidates: Iterable[Any],
        keyword: str = "",
        fallback_title: str | None = None,
    ) -> str:
        fallback = fallback_title or cls.FALLBACK_TITLE
        candidate_list = cls._dedupe_candidates([*list(candidates or []), keyword, *cls.RECOMMENDED_TITLES])
        scored: list[tuple[int, int, str]] = []
        for index, raw in enumerate(candidate_list):
            title = cls._clean_title(raw)
            if not title:
                continue
            fixed = cls._rule_fix(title, keyword=keyword)
            for candidate in cls._dedupe_candidates([title, fixed]):
                inspection = cls.inspect_title(candidate)
                score = int(inspection["score"])
                if inspection["qualified"]:
                    score += 100
                scored.append((score, -index, candidate))
        if scored:
            scored.sort(reverse=True)
            best = scored[0][2]
            if cls.inspect_title(best)["qualified"]:
                return best
        fixed = cls._rule_fix(candidate_list[0] if candidate_list else keyword, keyword=keyword)
        return fixed if cls.inspect_title(fixed)["qualified"] else fallback

    @classmethod
    def inspect_title(cls, title: Any) -> dict[str, Any]:
        safe_title = cls._clean_title(title)
        reasons: list[str] = []
        if not safe_title:
            reasons.append("empty")
        cjk_len = cls._cjk_len(safe_title)
        if cjk_len > cls.MAX_CJK_CHARS:
            reasons.append("too_long")
        if cls._has_incomplete_ending(safe_title):
            reasons.append("incomplete_ending")
        if cls._has_suspicious_unfinished_tail(safe_title):
            reasons.append("unfinished_tail")
        for word in cls.REPEATED_WORDS:
            if safe_title.count(word) >= 2:
                reasons.append(f"repeated_{word}")
        for phrase in cls.AI_PHRASES:
            if phrase in safe_title:
                reasons.append("ai_tone")
                break
        score = 100
        penalties = {
            "empty": 100,
            "too_long": 25,
            "incomplete_ending": 60,
            "unfinished_tail": 45,
            "ai_tone": 40,
        }
        for reason in reasons:
            score -= penalties.get(reason, 30 if reason.startswith("repeated_") else 20)
        score = max(0, score)
        return {
            "title": safe_title,
            "qualified": bool(safe_title) and not reasons,
            "score": score,
            "reasons": reasons,
            "cjk_length": cjk_len,
        }

    @classmethod
    def ensure_title_in_html(cls, html_content: str, old_title: str, final_title: str) -> str:
        content = html_content or ""
        old = cls._clean_title(old_title)
        final = cls._clean_title(final_title)
        if not content or not final:
            return content
        replacements = cls._dedupe_candidates([old, html.escape(old), final])
        for item in replacements:
            if item and item != final:
                content = content.replace(item, final)
        return content

    @classmethod
    def ensure_title_in_text(cls, text: str, old_title: str, final_title: str) -> str:
        content = text or ""
        old = cls._clean_title(old_title)
        final = cls._clean_title(final_title)
        if old and final and old != final:
            content = content.replace(old, final)
        return content

    @classmethod
    def _rule_fix(cls, title: Any, keyword: str = "") -> str:
        safe_title = cls._clean_title(title)
        if not safe_title:
            safe_title = cls._clean_title(keyword)
        if not safe_title:
            return cls.FALLBACK_TITLE

        if safe_title.count("老板") >= 2:
            safe_title = re.sub(r"^老板", "", safe_title, count=1)
            if cls.inspect_title(safe_title)["qualified"]:
                return safe_title

        if "经营贷" in safe_title and ("总被拒" in safe_title or "被拒" in safe_title) and ("3" in safe_title or "三" in safe_title or "地方" in safe_title):
            return "经营贷总被拒？先查这3个地方"
        if "流水" in safe_title and "被拒" in safe_title:
            return "有流水也被拒？老板先看这3个信号"
        if "银行" in safe_title and ("不批" in safe_title or "不给" in safe_title or "为什么不" in safe_title):
            return "银行为什么不批？问题多半在这几点"
        if "批不下来" in safe_title or "批不下" in safe_title:
            return "贷款批不下来，不一定是银行的问题"
        if "申请" in safe_title and "经营贷" in safe_title:
            return "申请经营贷前，先做这5步体检"
        if "经营贷" in safe_title and ("拒" in safe_title or "不批" in safe_title):
            return "经营贷被拒？先查这3个地方"
        if any(phrase in safe_title for phrase in cls.AI_PHRASES):
            if "申请" in safe_title or "经营贷" in safe_title:
                return "申请经营贷前，先做这5步体检"
            return cls.FALLBACK_TITLE
        if cls._cjk_len(safe_title) > cls.MAX_CJK_CHARS:
            return cls._compress_long_title(safe_title)
        if cls._has_incomplete_ending(safe_title) or cls._has_suspicious_unfinished_tail(safe_title):
            return cls.FALLBACK_TITLE
        return safe_title

    @classmethod
    def _compress_long_title(cls, title: str) -> str:
        if "经营贷" in title and "拒" in title:
            return "经营贷被拒？先查这3个地方"
        if "银行" in title and ("不批" in title or "不给" in title):
            return "银行为什么不批？问题多半在这几点"
        if "申请" in title and "经营贷" in title:
            return "申请经营贷前，先做这5步体检"
        return cls.FALLBACK_TITLE

    @classmethod
    def _has_incomplete_ending(cls, title: str) -> bool:
        return any(title.endswith(ending) for ending in cls.INCOMPLETE_ENDINGS)

    @classmethod
    def _has_suspicious_unfinished_tail(cls, title: str) -> bool:
        if not title or title.endswith(tuple(cls.END_PUNCTUATION)):
            return False
        tail = title[-6:]
        return any(tail.endswith(item) for item in cls.SUSPICIOUS_TAILS)

    @staticmethod
    def _clean_title(title: Any) -> str:
        text = str(title or "").strip()
        text = re.sub(r"^#+\s*", "", text)
        text = re.sub(r"\s+", "", text)
        return text.strip(" 《》[]【】「」『』-—_|，,。；;：:、")

    @staticmethod
    def _cjk_len(title: str) -> int:
        return len(re.findall(r"[\u4e00-\u9fff]", title or ""))

    @classmethod
    def _dedupe_candidates(cls, candidates: Iterable[Any]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            title = cls._clean_title(item)
            if title and title not in seen:
                seen.add(title)
                result.append(title)
        return result


TitleSanitizer = TitleGuard