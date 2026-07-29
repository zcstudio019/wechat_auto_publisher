"""Dedicated Phase 2 generator for enterprise-finance growth articles."""
from __future__ import annotations

import logging
import re
from typing import Any

from ai_processor.processor import _render_original_html
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, USE_AI
from services.enterprise_finance_content_library import DEFAULT_CTA, match_finance_cta
from services.enterprise_finance_growth_strategy import enterprise_finance_growth
from services.finance_topic_agent import (
    FinanceTopicAgent,
    FinanceTopicTitleScorer,
)

PROMPT_VERSION = "phase2"

logger = logging.getLogger(__name__)


class LoanIndustryLawArticleGenerator:
    """Generate enterprise-finance acquisition articles without JSON mode."""

    ARTICLE_TYPE = "industry_law"
    CATEGORY_LABEL = "贷款行业底层规律"
    CTA = DEFAULT_CTA

    REQUIRED_CONTENT_MARKERS = (
        "真实老板案例",
        "老板真实疑问",
        "银行真实审核逻辑",
        "老板行动建议",
    )

    def __init__(self, client: Any = None, model: str = "") -> None:
        self.model = str(model or OPENAI_MODEL or "").strip()
        self.client = client if client is not None else self._create_client()

    @classmethod
    def matches(cls, article_type: str = "", template: dict[str, Any] | None = None) -> bool:
        template = template or {}
        values = {
            str(article_type or "").strip(),
            str(template.get("article_type") or "").strip(),
            str(template.get("category") or "").strip(),
        }
        template_name = str(template.get("name") or "").strip()
        return cls.ARTICLE_TYPE in values or cls.CATEGORY_LABEL in template_name

    def generate(
        self,
        keyword: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        safe_keyword = str(keyword or "").strip() or "企业融资条件诊断"
        safe_context = dict(context or {})
        template_label = self._template_label(safe_context)
        ai_status = "disabled"
        parsed: dict[str, str] = {}
        title_regenerated = False

        if self.client and self.model:
            try:
                raw_text = self._request_article(safe_keyword, safe_context)
                parsed = self._parse_labeled_text(raw_text)
                ai_status = "success" if self._is_complete(parsed) else "invalid_response"
                if ai_status == "invalid_response":
                    logger.warning(
                        "[finance-growth-agent] title=%s template=%s score=0 "
                        "prompt_version=%s error_type=AI_RESPONSE_FORMAT_ERROR "
                        "error=%s",
                        parsed.get("title") or "",
                        template_label,
                        PROMPT_VERSION,
                        "AI返回内容缺少固定文章结构",
                    )
            except Exception as exc:
                ai_status = f"error:{type(exc).__name__}"
                logger.warning(
                    "[finance-growth-agent] title= template=%s score=0 "
                    "prompt_version=%s error_type=%s error=%s",
                    template_label,
                    PROMPT_VERSION,
                    type(exc).__name__,
                    exc,
                    exc_info=True,
                )

        if not self._is_complete(parsed):
            result = self.build_fallback(safe_keyword, safe_context, ai_status=ai_status)
        else:
            title, title_regenerated = self._ensure_growth_title(
                parsed["title"], safe_keyword, safe_context
            )
            result = self._build_result(
                keyword=safe_keyword,
                title=title,
                summary=parsed["summary"],
                content=parsed["content"],
                fallback_used=False,
                ai_status=ai_status,
                context=safe_context,
                title_regenerated=title_regenerated,
            )

        self._log_finance_growth(result, template_label)
        self._log_result(safe_keyword, result, article_id="")
        return result

    def _request_article(self, keyword: str, context: dict[str, Any]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(keyword, context)},
            ],
            max_tokens=4800,
            temperature=0.55,
        )
        choices = getattr(response, "choices", None) or []
        message = getattr(choices[0], "message", None) if choices else None
        return str(getattr(message, "content", "") or "").strip()

    def _ensure_growth_title(
        self,
        proposed_title: str,
        keyword: str,
        context: dict[str, Any],
    ) -> tuple[str, bool]:
        first = FinanceTopicTitleScorer.score_title(proposed_title)
        if first["qualified"]:
            return first["title"], False

        pain_point = str(context.get("pain_point") or "银行拒贷").strip()
        scenario = str(context.get("scenario") or "申请经营贷").strip()
        target_customer = str(context.get("target_customer") or "企业老板").strip()
        local_title, _ = FinanceTopicAgent.build_title(
            pain_point,
            scenario,
            target_customer,
        )
        candidates = [first["title"], local_title]
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._title_regeneration_prompt()},
                    {
                        "role": "user",
                        "content": (
                            f"主题：{keyword}\n目标客户：{target_customer}\n"
                            f"真实场景：{scenario}\n核心痛点：{pain_point}\n"
                            f"原标题：{proposed_title}\n只输出一行：TITLE: 新标题"
                        ),
                    },
                ],
                max_tokens=180,
                temperature=0.45,
            )
            choices = getattr(response, "choices", None) or []
            message = getattr(choices[0], "message", None) if choices else None
            raw_title = str(getattr(message, "content", "") or "").strip()
            parsed = self._parse_labeled_text(raw_title)
            regenerated = parsed.get("title") or re.sub(
                r"(?i)^\s*TITLE\s*[:：]\s*", "", raw_title
            ).strip()
            if regenerated:
                candidates.append(regenerated.splitlines()[0].strip())
        except Exception as exc:
            logger.warning(
                "[finance-growth-agent] title=%s template=%s score=%s "
                "prompt_version=%s error_type=%s error=%s",
                proposed_title,
                self._template_label(context),
                first["score"],
                PROMPT_VERSION,
                type(exc).__name__,
                exc,
            )

        scored = [FinanceTopicTitleScorer.score_title(item) for item in candidates if item]
        best = max(scored, key=lambda item: item["score"])
        if not best["qualified"]:
            best = FinanceTopicTitleScorer.score_title(local_title)
        return best["title"], best["title"] != first["title"]

    @classmethod
    def build_fallback(
        cls,
        keyword: str,
        context: dict[str, Any] | None = None,
        ai_status: str = "fallback",
    ) -> dict[str, Any]:
        safe_keyword = str(keyword or "").strip() or "企业融资条件诊断"
        safe_context = dict(context or {})
        pain_point = str(safe_context.get("pain_point") or "银行拒贷").strip()
        scenario = str(safe_context.get("scenario") or "申请经营贷").strip()
        target_customer = str(safe_context.get("target_customer") or "企业老板").strip()
        title, _ = FinanceTopicAgent.build_title(pain_point, scenario, target_customer)
        summary = (
            "企业有流水、有利润，并不等于银行一定会给足额度。"
            "从还款能力、现金流、经营稳定性、征信和负债结构入手，"
            "先诊断融资条件，再选择合适方案。"
        )
        content = f"""## 一、真实老板案例

一位{target_customer}经营企业6年，年营业额约500万元。当前融资场景是“{scenario}”，核心痛点是“{pain_point}”。老板需要一笔资金支持经营，但申请贷款后银行只批了30万元，另一家银行甚至直接拒绝。

### 这位老板真正的痛点

企业账面有利润，但客户回款周期拉长，短期负债又集中到期。老板真正缺的不是一个贷款产品，而是对自身融资条件的清晰判断。

围绕“{safe_keyword}”，问题不能只看企业缺多少钱，还要看银行如何判断这笔钱能不能安全收回。

## 二、老板真实疑问

- 为什么企业流水不少，银行给的额度却很低？
- 为什么同行能贷，自己的企业却被拒？
- 征信没有逾期，为什么审批仍然过不了？
- 是继续换银行申请，还是先优化企业条件？

## 三、银行真实审核逻辑

### 1. 还款能力

银行关注企业利润和可支配现金能否覆盖贷款本息，不会只看营业额大小。

### 2. 现金流

经营流水是否连续、稳定，回款周期是否合理，决定企业能不能按期还款。

### 3. 企业稳定性

成立时间、主营业务、上下游关系、纳税开票和订单持续性，会共同证明经营是否稳定。

### 4. 征信情况

没有逾期只是基础。短期频繁查询、多头借贷、对外担保和负债新增过快，同样会影响审批。

### 5. 负债结构

银行会看总负债、短期债务占比和集中到期压力，判断新增贷款会不会进一步放大风险。

## 四、老板行动建议与解决方案

### 第一步：不要盲目申请贷款

先停止短期内到处试产品，避免新增征信查询和申请记录。

### 第二步：分析融资条件

核对近12个月流水、纳税、开票、利润、征信及现有负债，找到额度低或被拒的真实原因。

### 第三步：匹配融资方式

根据企业成立时间、行业、现金流、资产和资金用途，匹配经营贷、抵押融资或其他合适方式。

### 第四步：优化融资结构

合理安排短期与长期负债、还款节奏和续贷时间，减少高成本资金对现金流的挤压。""".strip()
        return cls._build_result(
            keyword=safe_keyword,
            title=title,
            summary=summary,
            content=content,
            fallback_used=True,
            ai_status=ai_status,
            context=safe_context,
            title_regenerated=False,
        )

    @classmethod
    def log_saved(cls, article_id: Any, result: dict[str, Any], keyword: str = "") -> None:
        cls._log_result(keyword or str(result.get("source_title") or ""), result, article_id)

    @classmethod
    def _build_result(
        cls,
        keyword: str,
        title: str,
        summary: str,
        content: str,
        fallback_used: bool,
        ai_status: str,
        context: dict[str, Any] | None = None,
        title_regenerated: bool = False,
    ) -> dict[str, Any]:
        topic_context = dict(context or {})
        clean_title = re.sub(r"\s+", " ", str(title or keyword)).strip() or keyword
        title_details = FinanceTopicTitleScorer.score_title(clean_title)
        if not title_details["qualified"]:
            clean_title, _ = FinanceTopicAgent.build_title(
                str(topic_context.get("pain_point") or "银行拒贷"),
                str(topic_context.get("scenario") or "申请经营贷"),
                str(topic_context.get("target_customer") or "企业老板"),
            )
            title_details = FinanceTopicTitleScorer.score_title(clean_title)
            title_regenerated = True
        cta = match_finance_cta(topic_context, clean_title)
        clean_summary = re.sub(r"\s+", " ", str(summary or "")).strip()[:100]
        clean_content = cls._strip_fences(str(content or "").strip())
        clean_content = cls._append_fixed_cta(clean_content, cta)
        html = _render_original_html(clean_title, clean_content, "沪上银原创", category=cls.ARTICLE_TYPE)
        return {
            "ok": True,
            "success": True,
            "title": clean_title,
            "title_score": title_details["score"],
            "title_score_details": title_details["dimensions"],
            "title_regenerated": bool(title_regenerated),
            "summary": clean_summary,
            "content": clean_content,
            "markdown": clean_content,
            "html_content": html,
            "html": html,
            "cta": cta,
            "category": cls.ARTICLE_TYPE,
            "category_key": cls.ARTICLE_TYPE,
            "article_type": cls.ARTICLE_TYPE,
            "content_strategy": "enterprise_finance_growth",
            "prompt_version": PROMPT_VERSION,
            "tags": "企业融资,经营贷,融资诊断,小微企业",
            "source_name": "沪上银原创",
            "source_title": keyword,
            "cover_prompt": (
                f"企业融资底层规律主题公众号封面，{clean_title}，商务写实、稳重可信、16:9、无文字"
            ),
            "fallback_used": bool(fallback_used),
            "ai_used": not fallback_used,
            "ai_status": ai_status,
            "template": cls._template_label(topic_context),
            "pain_point": str(topic_context.get("pain_point") or ""),
            "scenario": str(topic_context.get("scenario") or ""),
            "target_customer": str(topic_context.get("target_customer") or ""),
            "conversion_goal": cta["title"],
        }

    @classmethod
    def _parse_labeled_text(cls, text: str) -> dict[str, str]:
        clean_text = cls._strip_fences(str(text or "").strip())
        marker_pattern = re.compile(r"(?im)^\s*(TITLE|SUMMARY|CONTENT|CTA)\s*[:：]\s*")
        matches = list(marker_pattern.finditer(clean_text))
        if not matches:
            return {}
        sections: dict[str, str] = {}
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(clean_text)
            sections[match.group(1).lower()] = cls._strip_fences(
                clean_text[match.end():end].strip()
            )
        return {
            "title": sections.get("title", ""),
            "summary": re.sub(r"\s+", " ", sections.get("summary", "")).strip()[:100],
            "content": sections.get("content", ""),
            "cta": sections.get("cta", ""),
        }

    @classmethod
    def _is_complete(cls, article: dict[str, str]) -> bool:
        if not all(str(article.get(field) or "").strip() for field in ("title", "summary", "content")):
            return False
        content = article.get("content", "")
        return all(marker in content for marker in cls.REQUIRED_CONTENT_MARKERS)

    @classmethod
    def _append_fixed_cta(cls, content: str, cta: dict[str, str]) -> str:
        text = re.split(
            r"(?im)^\s*##\s*(?:五[、.]?)?\s*(?:企业融资体检|现金流健康检测|征信优化诊断|融资额度评估|贷款失败原因分析)\s*$",
            content or "",
            maxsplit=1,
        )[0].rstrip()
        return (
            f"{text}\n\n## 五、{cta['title']}\n\n"
            f"### {cta['title']}\n\n"
            "如果你的企业正遇到本文提到的融资问题，可以先做一次针对性诊断。\n\n"
            "**诊断时请准备：**\n\n"
            "- 企业成立时间\n"
            "- 营业额与经营流水\n"
            "- 负债与征信情况\n"
            "- 当前融资需求\n\n"
            f"{cta['description']}\n\n"
            f"**{cta['button_text']}**"
        ).strip()

    @staticmethod
    def _strip_fences(text: str) -> str:
        value = str(text or "").strip()
        value = re.sub(r"^```(?:markdown|text)?\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*```\s*$", "", value)
        return value.strip()

    @classmethod
    def _system_prompt(cls) -> str:
        return (
            "你是企业融资内容增长Agent，读者是企业老板、小微企业主和经营者。"
            "目标是用真实融资场景帮助老板识别问题并产生融资诊断需求。"
            "不要输出JSON，不要使用代码围栏，只按TITLE、SUMMARY、CONTENT、CTA四个标签输出。"
            "标题必须包含老板身份、融资场景、明确冲突和解决期待。"
            "CONTENT必须依次包含真实老板案例、老板真实疑问、银行真实审核逻辑、老板行动建议。"
        )

    @classmethod
    def _user_prompt(cls, keyword: str, context: dict[str, Any]) -> str:
        pain_point = str(
            context.get("pain_point")
            or context.get("common_misunderstanding")
            or "银行拒贷、额度低或现金流紧张"
        ).strip()
        target_customer = str(
            context.get("target_customer") or "企业老板、小微企业主和经营者"
        ).strip()
        scenario = str(
            context.get("scenario")
            or context.get("article_angle")
            or "申请经营贷"
        ).strip()
        industry_hotspot = str(context.get("industry_hotspot") or "企业融资审核与经营现金流").strip()
        cta = match_finance_cta(context, keyword)
        pain_points = "、".join(enterprise_finance_growth["pain_points"])
        scenarios = "、".join(enterprise_finance_growth["scenarios"])
        return f"""请围绕以下完整选题对象生成企业融资顾问文章：

目标客户：
{target_customer}

真实场景：
{scenario}

核心痛点：
{pain_point}

行业热点参考：
{industry_hotspot}

选题标题：
{keyword}

必须使用以下纯文本格式：
TITLE:
文章标题

SUMMARY:
100字以内摘要

CONTENT:
完整正文

CTA:
{cta['title']}

标题规则：
1. 使用“老板身份 + 具体融资场景 + 冲突 + 解决期待”公式，评分目标不低于75分。
2. 禁止使用“贷款行业的底层规律”“融资行业分析”等行业大词。
3. 标题要自然，不夸大、不承诺放款。

CONTENT固定结构：
## 一、真实老板案例
围绕目标客户、真实场景和核心痛点写具体案例。

## 二、老板真实疑问
写清老板在该融资场景中的真实疑问和痛点。

## 三、银行真实审核逻辑
必须逐项解释：还款能力、现金流、企业稳定性、征信情况、负债结构。

## 四、老板行动建议与解决方案
必须依次写：
第一步：不要盲目申请贷款
第二步：分析融资条件
第三步：匹配融资方式
第四步：优化融资结构

CTA由系统根据topic固定匹配为“{cta['title']}”，不要在CONTENT内自由发挥。
可参考痛点库：{pain_points}
可参考场景库：{scenarios}
禁止输出JSON、```代码块和标签之外的解释。""".strip()

    @staticmethod
    def _title_regeneration_prompt() -> str:
        return (
            "你只负责重写企业融资获客标题。标题必须同时体现老板身份、具体融资场景、"
            "强痛点、好奇心和行动价值，评分必须不低于75分，语言自然，不承诺放款。"
            "只输出一行TITLE: 新标题。"
        )

    @classmethod
    def _template_label(cls, context: dict[str, Any]) -> str:
        return str(
            context.get("name")
            or context.get("template_name")
            or context.get("category")
            or cls.ARTICLE_TYPE
        ).strip()

    @staticmethod
    def _log_finance_growth(result: dict[str, Any], template_label: str) -> None:
        logger.info(
            "[finance-growth-agent] title=%s template=%s score=%s prompt_version=%s",
            result.get("title") or "",
            template_label,
            result.get("title_score") or 0,
            PROMPT_VERSION,
        )

    @staticmethod
    def _log_result(keyword: str, result: dict[str, Any], article_id: Any) -> None:
        logger.info(
            "[loan-industry-law-generator] keyword=%s title=%s ai_status=%s fallback=%s article_id=%s",
            keyword,
            result.get("title") or "",
            result.get("ai_status") or "",
            str(bool(result.get("fallback_used"))).lower(),
            article_id or "",
        )

    @staticmethod
    def _create_client() -> Any:
        if not USE_AI or not OPENAI_API_KEY or not OPENAI_BASE_URL or not OPENAI_MODEL:
            return None
        try:
            from openai import OpenAI

            return OpenAI(
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL,
                timeout=75,
                max_retries=1,
            )
        except Exception as exc:
            logger.warning(
                "[finance-growth-agent] title= template=industry_law score=0 "
                "prompt_version=%s error_type=%s error=%s",
                PROMPT_VERSION,
                type(exc).__name__,
                exc,
            )
            return None
