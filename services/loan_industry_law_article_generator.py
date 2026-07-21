"""Dedicated generator for loan-industry-law articles."""
from __future__ import annotations

import logging
import re
from typing import Any

from ai_processor.processor import _render_original_html
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, USE_AI

logger = logging.getLogger(__name__)


class LoanIndustryLawArticleGenerator:
    """Generate fixed-structure industry-law articles without JSON mode."""

    ARTICLE_TYPE = "industry_law"
    CATEGORY_LABEL = "贷款行业底层规律"
    CTA = {
        "title": "免费企业融资体检",
        "description": "帮你分析企业当前融资条件、额度空间和优化方向。",
        "button_text": "立即获取融资方案",
    }
    REQUIRED_CONTENT_MARKERS = (
        "反常识",
        "老板常见误区",
        "银行真实审批逻辑",
        "贷款行业底层规律",
        "真实经营场景案例",
        "行动建议",
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
            str(template.get("category_label") or "").strip(),
            str(template.get("name") or "").strip(),
        }
        return cls.ARTICLE_TYPE in values or any(cls.CATEGORY_LABEL in value for value in values if value)

    def generate(
        self,
        keyword: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        safe_keyword = str(keyword or "").strip() or "贷款行业底层规律"
        safe_context = dict(context or {})
        ai_status = "disabled"
        parsed: dict[str, str] = {}

        if self.client and self.model:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self._system_prompt()},
                        {"role": "user", "content": self._user_prompt(safe_keyword, safe_context)},
                    ],
                    max_tokens=4800,
                    temperature=0.55,
                )
                choices = getattr(response, "choices", None) or []
                message = getattr(choices[0], "message", None) if choices else None
                raw_text = str(getattr(message, "content", "") or "").strip()
                parsed = self._parse_labeled_text(raw_text)
                ai_status = "success" if self._is_complete(parsed) else "invalid_response"
            except Exception as exc:
                ai_status = f"error:{type(exc).__name__}"
                logger.warning(
                    "[loan-industry-law-generator] keyword=%s title= ai_status=%s "
                    "fallback=true article_id= error=%s",
                    safe_keyword,
                    ai_status,
                    exc,
                )

        if not self._is_complete(parsed):
            result = self.build_fallback(safe_keyword, safe_context, ai_status=ai_status)
        else:
            result = self._build_result(
                keyword=safe_keyword,
                title=parsed["title"],
                summary=parsed["summary"],
                content=parsed["content"],
                fallback_used=False,
                ai_status=ai_status,
            )

        self._log_result(safe_keyword, result, article_id="")
        return result

    @classmethod
    def build_fallback(
        cls,
        keyword: str,
        context: dict[str, Any] | None = None,
        ai_status: str = "fallback",
    ) -> dict[str, Any]:
        del context
        safe_keyword = str(keyword or "").strip() or "贷款行业底层规律"
        title = safe_keyword
        summary = "银行审批不看谁最缺钱，而是判断企业能否稳定还款。看懂现金流、经营真实性、征信和负债结构，才能减少盲目申请。"
        content = f"""## 一、反常识开头：银行从来不把钱借给最缺钱的人

很多老板认为，企业越缺资金，银行越应该提供贷款。

但银行真正关注的，从来不是谁最缺钱，而是谁有稳定、可验证的还款能力。企业越是到了资金链最紧张的时候才申请，财务数据、征信查询和上下游付款往往越容易出现异常，审批反而更谨慎。

所以，讨论“{safe_keyword}”，第一步不是到处找产品，而是先站在银行风控的角度重新看企业。

## 二、老板常见误区

### 误区1：缺资金时才开始融资

融资不是临时救火。等到账上资金只能支撑一两个月时，企业已经很难从容整理流水、降低负债或补齐经营资料。

### 误区2：一家银行拒绝，就马上多家申请

短期内频繁申请会增加征信查询记录。后面的银行看到密集查询，可能判断企业资金压力正在快速上升。

### 误区3：只关注利率，不关注审批条件

利率低不代表适合。额度、期限、还款方式、续贷安排和资金用途限制，都会影响企业真实的资金成本。

## 三、银行真实审批逻辑

银行审批企业贷款，通常围绕五个问题展开：

- **还款能力**：企业利润和可支配现金能否覆盖本息。
- **现金流**：经营流水是否连续、稳定，并与业务规模匹配。
- **经营真实性**：合同、发票、纳税、上下游交易能否相互印证。
- **征信情况**：是否存在逾期、频繁查询、多头借贷或对外担保风险。
- **资产负债结构**：现有负债是否过高，短期债务是否集中到期。

银行不是只看某一个数字，而是判断这些信息能否共同证明企业具有持续偿债能力。

## 四、贷款行业底层规律

### 规律1：银行借的是未来现金流，不是过去的营业额

营业额只是经营规模，真正决定还款能力的是收入质量、利润水平和现金回笼速度。

### 规律2：融资条件最好时，往往是企业暂时不缺钱的时候

企业现金流稳定、负债合理时，可选择的银行和产品更多，也更有时间比较方案。

### 规律3：每一次申请都会留下风险信号

盲目试错不只是浪费时间，还可能增加征信查询，压缩后续选择空间。

### 规律4：银行喜欢可以被验证的经营

口头说明很难替代合同、流水、发票、纳税和库存等证据。资料之间越一致，银行越容易形成稳定判断。

### 规律5：额度不是谈出来的，而是企业条件共同支撑出来的

额度通常由现金流、负债、资产、信用和产品规则共同决定。先改善条件，再匹配银行，比单纯要求提高额度更有效。

## 五、真实经营场景案例

一家年营业额约500万元的小微贸易企业，账面利润并不差，但客户回款周期从30天拉长到90天。老板为了支付货款，连续使用多笔短期借款，并在一个月内申请了多家银行。

银行看到的不是“企业有500万元营业额”，而是回款变慢、短期负债上升、征信查询密集。即使企业仍有利润，也可能因为现金流覆盖不足而拿不到预期额度。

正确做法不是继续换银行，而是先梳理应收账款、压降短期高成本负债、解释异常流水，并准备能够证明真实交易和未来回款的材料。

## 六、行动建议

- 先核对近12个月经营流水、纳税、开票和利润是否相互匹配。
- 整理营业执照、公司章程、财务报表、主要合同、发票和上下游交易凭证。
- 查询企业及法人的征信情况，控制短期新增申请和不必要的查询。
- 列出未来6至12个月资金缺口、回款计划和现有债务到期时间。
- 根据企业行业、现金流、资产和负债情况匹配银行，不要只按最低利率选择。
- 对续贷和还款提前规划，不要等资金到期前才临时处理。
""".strip()
        return cls._build_result(
            keyword=safe_keyword,
            title=title,
            summary=summary,
            content=content,
            fallback_used=True,
            ai_status=ai_status,
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
    ) -> dict[str, Any]:
        clean_title = re.sub(r"\s+", " ", str(title or keyword)).strip() or keyword
        clean_summary = re.sub(r"\s+", " ", str(summary or "")).strip()[:100]
        clean_content = cls._strip_fences(str(content or "").strip())
        clean_content = cls._append_fixed_cta(clean_content)
        html = _render_original_html(clean_title, clean_content, "沪上银原创", category=cls.ARTICLE_TYPE)
        return {
            "ok": True,
            "success": True,
            "title": clean_title,
            "summary": clean_summary,
            "content": clean_content,
            "markdown": clean_content,
            "html_content": html,
            "html": html,
            "cta": dict(cls.CTA),
            "category": cls.ARTICLE_TYPE,
            "category_key": cls.ARTICLE_TYPE,
            "article_type": cls.ARTICLE_TYPE,
            "tags": "企业融资,贷款行业底层规律,小微企业",
            "source_name": "沪上银原创",
            "source_title": keyword,
            "cover_prompt": f"企业融资底层规律主题公众号封面，{clean_title}，商务写实、稳重可信、16:9、无文字",
            "fallback_used": bool(fallback_used),
            "ai_used": not fallback_used,
            "ai_status": ai_status,
        }

    @classmethod
    def _parse_labeled_text(cls, text: str) -> dict[str, str]:
        clean_text = cls._strip_fences(str(text or "").strip())
        marker_pattern = re.compile(
            r"(?im)^\s*(TITLE|SUMMARY|CONTENT|CTA)\s*[:：]\s*"
        )
        matches = list(marker_pattern.finditer(clean_text))
        if not matches:
            return {}
        sections: dict[str, str] = {}
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(clean_text)
            sections[match.group(1).lower()] = cls._strip_fences(clean_text[match.end():end].strip())
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
    def _append_fixed_cta(cls, content: str) -> str:
        text = re.split(r"(?m)^\s*##\s*七[、.]", content or "", maxsplit=1)[0].rstrip()
        return (
            f"{text}\n\n## 七、融资体检\n\n"
            f"### {cls.CTA['title']}\n\n"
            f"{cls.CTA['description']}\n\n"
            f"**{cls.CTA['button_text']}**"
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
            "你是熟悉银行风控和小微企业经营的融资内容作者。"
            "不要输出JSON，不要使用代码围栏，只按TITLE、SUMMARY、CONTENT、CTA四个标签输出。"
            "CONTENT必须依次包含反常识开头、老板常见误区、银行真实审批逻辑、"
            "3至5条贷款行业底层规律、真实经营场景案例、行动建议。"
        )

    @classmethod
    def _user_prompt(cls, keyword: str, context: dict[str, Any]) -> str:
        pain_point = str(context.get("pain_point") or context.get("common_misunderstanding") or "老板不了解银行审批逻辑").strip()
        bank_logic = str(context.get("bank_logic") or "银行关注还款能力、现金流、经营真实性、征信和资产负债结构").strip()
        return f"""围绕“{keyword}”写一篇面向小微企业老板的长文章。

必须使用以下纯文本格式：
TITLE:
文章标题

SUMMARY:
100字以内摘要

CONTENT:
完整正文

CTA:
标题、描述、按钮

写作要求：
1. CONTENT依次使用这些明确标题：反常识开头、老板常见误区、银行真实审批逻辑、贷款行业底层规律、真实经营场景案例、行动建议。
2. 底层规律输出3至5条，逐条给出标题和解释。
3. 案例使用年营业额约500万元的小微企业，说明利润尚可但现金流断裂后银行为何不给预期额度。
4. 常见痛点：{pain_point}
5. 银行逻辑：{bank_logic}
6. 不承诺放款，不使用“包过、最低利率、百分百下款”等表达。
7. 不输出JSON，不输出```代码块，不输出标签之外的解释。
""".strip()

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
                "[loan-industry-law-generator] keyword= title= ai_status=client_init_error "
                "fallback=true article_id= error=%s",
                exc,
            )
            return None
