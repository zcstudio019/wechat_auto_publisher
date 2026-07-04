"""Article generation agent for template-free公众号草稿创作。"""
from __future__ import annotations

import json
import logging
import re
import time
import traceback
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from ai_processor.processor import _render_original_html
from config import CONTENT_GROWTH_ENABLED, OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from services.wechat_html_adapter import adapt_html_for_wechat
from services.wechat_lead_card_adapter import (
    adapt_lead_form_to_wechat_card,
    build_cta_html,
    inject_cta_into_html,
)
from services.title_score_service import TitleScoreService

logger = logging.getLogger(__name__)


def safe_dict(value: Any) -> dict[str, Any]:
    """Return a dict for optional AI payloads without assuming shape."""
    return value if isinstance(value, dict) else {}


class ArticleGenerationAgent:
    """根据关键词与分类生成可直接入库的公众号文章草稿。"""

    CATEGORY_STRATEGIES = {
        "leads": {
            "label": "自动获客",
            "focus": "重点写老板痛点、决策焦虑与咨询触发点，结尾引导私信或咨询。",
        },
        "brand": {
            "label": "品牌宣传",
            "focus": "重点塑造专业度、可信度与案例感，避免夸大承诺。",
        },
        "science": {
            "label": "知识科普",
            "focus": "用大白话解释融资、贷款、征信、现金流知识，适合长期内容沉淀。",
        },
        "hotspot": {
            "label": "热点解读",
            "focus": "结合政策、市场与行业变化做解释，不编造具体政策或不存在的数据。",
        },
        "service": {
            "label": "方案匹配",
            "focus": "根据不同企业情况给出融资思路，不承诺放款、不写具体利率。",
        },
        "finance": {
            "label": "融资规划",
            "focus": "重点讲企业资金安排、融资节奏、提前规划，强调合规和风险意识。",
        },
        "enterprise": {
            "label": "经营分析",
            "focus": "从现金流、利润、成本、应收账款、负债结构角度写，帮助老板发现经营问题。",
        },
    }
    CATEGORY_ALIASES = {
        "自动获客": "leads",
        "品牌宣传": "brand",
        "知识科普": "science",
        "贷款知识科普": "science",
        "热点解读": "hotspot",
        "方案匹配": "service",
        "贷款方案匹配": "service",
        "融资规划": "finance",
        "经营分析": "enterprise",
        "企业经营分析": "enterprise",
    }
    LENGTH_HINTS = {
        "short": "正文控制在 900~1300 字，结构紧凑。",
        "medium": "正文控制在 1500~2200 字，观点完整。",
        "long": "正文控制在 2400~3200 字，分析更充分。",
    }
    FORBIDDEN_WORDS = (
        "包过",
        "百分百下款",
        "100%下款",
        "无视征信",
        "黑户可做",
        "秒批",
        "无条件放款",
        "保证放款",
        "不看征信",
        "最低利率",
    )
    AI_TIMEOUT_SECONDS = 60
    AI_MAX_RETRIES = 2
    TITLE_FORBIDDEN_PHRASES = (
        "如何科学规划",
        "必知基础",
        "关键事项",
        "稳健发展",
        "一文读懂",
        "全面解析",
    )

    def __init__(self) -> None:
        self.client = None
        self.config_error = self._validate_ai_config()
        if self.config_error:
            return
        try:
            from openai import OpenAI

            self.client = OpenAI(
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL,
                timeout=self.AI_TIMEOUT_SECONDS,
                max_retries=self.AI_MAX_RETRIES,
            )
        except Exception as exc:  # pragma: no cover - runtime environment dependent
            self._log_ai_exception("[content-growth-ai-client-init-error]", exc)
            self.client = None

    def generate(
        self,
        keyword: str,
        category: str = "",
        primary_category: str | None = None,
        secondary_categories: list[str] | None = None,
        audience: str = "企业老板 / 小微企业主",
        tone: str = "专业、可信、接地气、适合助贷/企业融资顾问行业",
        length: str = "medium",
    ) -> dict[str, Any]:
        """生成文章结构，并输出公众号兼容 HTML。"""
        safe_keyword = self._safe_text(keyword)
        if not safe_keyword:
            return self._error_result("请输入关键词")
        if self.config_error:
            return self._error_result(
                "AI API Key 未配置" if not OPENAI_API_KEY else "AI 服务配置不完整",
                error_type="AI_CONFIG_MISSING",
            )
        if self.client is None:
            return self._error_result("AI 客户端初始化失败", error_type="AI_CLIENT_INIT_FAILED")

        category_key = self._normalize_category(primary_category or category) or "science"
        normalized_secondary_categories = self._normalize_secondary_categories(
            secondary_categories or [],
            exclude=category_key,
        )
        safe_length = length if length in self.LENGTH_HINTS else "medium"
        raw_response = ""
        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "你是微信公众号企业融资内容生成 Agent。你必须只返回严格 JSON，不要输出 Markdown 包裹，不要输出额外解释。",
                    },
                    {
                        "role": "user",
                        "content": self._build_prompt(
                            keyword=safe_keyword,
                            category_key=category_key,
                            secondary_category_keys=normalized_secondary_categories,
                            audience=self._safe_text(audience) or "企业老板 / 小微企业主",
                            tone=self._safe_text(tone) or "专业、可信、接地气、适合助贷/企业融资顾问行业",
                            length=safe_length,
                        ) + "\n\n补充要求：cta 返回结构化对象，字段为 title、description、button_text；正文结尾仍需写企业融资体检模块。",
                    },
                ],
                temperature=0.45,
                max_tokens=4200,
            )
            choice = response.choices[0] if getattr(response, "choices", None) else None
            message = getattr(choice, "message", None)
            raw_response = (getattr(message, "content", "") or "").strip()
            if not raw_response:
                result = self._error_result("AI 返回内容为空，请稍后重试", error_type="AI_EMPTY_RESPONSE")
                result["raw_response"] = raw_response
                return result
            payload = safe_dict(self._parse_json_response(raw_response))
            if not payload:
                result = self._error_result("AI 返回内容为空，请稍后重试", error_type="AI_EMPTY_RESPONSE")
                result["raw_response"] = raw_response
                return result
            return self._normalize_result(
                payload,
                safe_keyword,
                category_key,
                normalized_secondary_categories,
                raw_response,
            )
        except Exception as exc:
            error_type, error_message = self._classify_ai_error(exc)
            self._log_ai_exception("[content-growth-ai-generate-error]", exc)
            result = self._error_result(error_message, error_type=error_type)
            if "AI返回内容为空" in str(exc) or "NoneType" in str(exc):
                result = self._error_result("AI 返回内容为空，请稍后重试", error_type="AI_EMPTY_RESPONSE")
            result["raw_response"] = raw_response
            return result

    def health_check(self) -> dict[str, Any]:
        """Send a minimal provider request and return sanitized diagnostics."""
        started_at = time.perf_counter()
        base_result = {
            "success": False,
            "provider": self._provider_name(),
            "base_url": self._safe_base_url(),
            "model": OPENAI_MODEL or "",
            "api_key_loaded": bool(OPENAI_API_KEY),
            "api_key_masked": self._mask_api_key(OPENAI_API_KEY),
            "latency_ms": 0,
            "error_type": "",
            "error_message": "",
        }
        if self.config_error:
            base_result.update({
                "error_type": "AI_CONFIG_MISSING",
                "error_message": "AI API Key 未配置" if not OPENAI_API_KEY else "AI 服务配置不完整",
            })
            return base_result
        if self.client is None:
            base_result.update({"error_type": "AI_CLIENT_INIT_FAILED", "error_message": "AI 客户端初始化失败"})
            return base_result
        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": "只回复 OK"}],
                temperature=0,
                max_tokens=8,
            )
            content = ""
            if getattr(response, "choices", None):
                content = str(getattr(response.choices[0].message, "content", "") or "").strip()
            base_result["success"] = bool(content)
            if not content:
                base_result["error_type"] = "AI_EMPTY_RESPONSE"
                base_result["error_message"] = "AI 服务返回空内容"
        except Exception as exc:
            error_type, error_message = self._classify_ai_error(exc)
            self._log_ai_exception("[content-growth-ai-health-error]", exc)
            base_result["error_type"] = error_type
            base_result["error_message"] = error_message
        finally:
            base_result["latency_ms"] = round((time.perf_counter() - started_at) * 1000)
        return base_result

    @classmethod
    def build_local_fallback(cls, topic: str, topic_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Build a complete enterprise-finance draft without any external service."""
        safe_topic = str(topic or "企业融资").strip() or "企业融资"
        context = topic_payload if isinstance(topic_payload, dict) else {}
        title = cls._growth_title(str(context.get("suggested_title") or safe_topic))
        target_customer = str(context.get("target_customer") or "正在申请经营贷或面临资金周转压力的企业老板")
        pain_point = str(context.get("pain_point") or "银行不批、额度不足、续贷不稳，却不知道问题出在哪里")
        angle = str(context.get("article_angle") or "从银行审批视角拆解企业经营数据、征信与现金流")
        markdown = cls._build_growth_markdown(target_customer, pain_point, angle)
        article = {
            "title": title,
            "summary": f"从老板真实场景出发，拆解银行审批卡点和融资优化路径。"[:60],
            "content": markdown,
            "category": "leads",
            "tags": f"{safe_topic},企业融资,自动获客,原创",
            "cover_prompt": f"企业融资顾问公众号封面，主题：{safe_topic}，商务写实、可信、16:9，无文字",
            "source_name": "沪上银原创",
        }
        return {
            "ok": True,
            "title": title,
            "summary": article["summary"],
            "category": "企业融资获客",
            "category_key": "leads",
            "secondary_categories": ["finance", "enterprise"],
            "tags": [safe_topic, "企业融资", "自动获客", "原创"],
            "markdown": markdown,
            "html": adapt_html_for_wechat(
                _render_original_html(title, markdown, article["source_name"], category="leads")
            ),
            "cover_prompt": article["cover_prompt"],
            "cta": {
                "title": "企业融资体检",
                "description": "先查被拒原因，再判断额度提升空间和申请顺序。",
                "button_text": "预约融资体检",
            },
            "raw_response": "",
            "fallback_used": True,
        }

    def _build_prompt(
        self,
        keyword: str,
        category_key: str,
        secondary_category_keys: list[str],
        audience: str,
        tone: str,
        length: str,
    ) -> str:
        strategy = self.CATEGORY_STRATEGIES[category_key]
        secondary_strategies = [
            self.CATEGORY_STRATEGIES[item]
            for item in secondary_category_keys
            if item in self.CATEGORY_STRATEGIES
        ]
        combined_labels = " + ".join([strategy["label"]] + [item["label"] for item in secondary_strategies])
        combined_focus = "；".join([strategy["focus"]] + [item["focus"] for item in secondary_strategies])
        growth_requirements = ""
        if CONTENT_GROWTH_ENABLED:
            growth_requirements = """

企业融资获客型内容要求（必须执行）：
1. 标题必须像老板会点开的公众号标题，优先使用：被拒原因型、额度卡点型、申请前检查型、真实案例型。
2. 标题避免“如何科学规划”“必知基础”“关键事项”“稳健发展”“一文读懂”“全面解析”等科普味表达。
3. 正文控制在 1800-2500 字之间，最多 5 个 ## 小节。
4. 开头先写 2-3 段老板痛点，再进入案例；必须包含老板常见误区、银行不批的真实原因、本文要解决的问题。
5. 正文必须包含一个匿名企业融资案例，写清企业类型、融资卡点、银行关注点和调整方向。
6. 每个主要小节尽量按“问题是什么 → 为什么影响审批 → 老板应该怎么做”展开。
7. 必须拆解 3-5 个问题：如征信、流水、负债、纳税、用途、担保、查询次数。
8. 必须给出 3-5 个解决建议：如提前体检、资料梳理、控制查询、优化流水、匹配银行、规划续贷。
9. 金句卡最多 1 次，不要输出单独英文引号，不要让金句影响阅读节奏。
10. 结尾必须固定加入“企业融资体检”转化模块，包含适合人群、体检结果、行动引导。
11. 必须有风险提醒：不承诺放款，不夸大额度，强调根据企业实际情况评估。
12. 不要写成金融百科，不要写成银行宣传稿，不要写空泛大道理，要像懂融资顾问的人在跟老板说话。
""".rstrip()

        return f"""
请围绕关键词“{keyword}”生成一篇微信公众号文章，严格返回 JSON：
{{
  "title": "文章标题",
  "summary": "文章摘要",
  "category": "{strategy['label']}",
  "tags": ["标签1", "标签2", "标签3"],
  "markdown": "完整 Markdown 正文",
  "cover_prompt": "封面图提示词",
  "cta": "合规咨询引导"
}}

写作条件：
1. 分类：{combined_labels}
2. 分类策略：{combined_focus}
3. 目标读者：{audience}
4. 语气：{tone}
5. 长度：{self.LENGTH_HINTS[length]}；如果是企业融资获客型内容，优先按 1800-2500 字执行。
6. 标题自然通顺，优先 12~18 字，最长不超过 22 字。
7. 摘要 60 字以内，适合公众号列表预览。
8. Markdown 正文要有清晰小标题、自然段和风险提醒；CTA 只放在结构化 cta 字段。
9. cover_prompt 要适合金融/企业服务公众号封面，画面高级可信，不要乱码文字。
10. cta 只做合规咨询引导，不作结果承诺。

合规硬约束：
- 不承诺一定放款。
- 不写“最低利率”“包过”“无视征信”“秒批”“百分百下款”等表达。
- 不制造焦虑，不夸大金融产品效果。
- 强调“根据企业实际情况评估”。
- 热点解读不得编造具体政策或未经确认的数据。
{growth_requirements}
""".strip()

    def _normalize_result(
        self,
        payload: dict[str, Any],
        keyword: str,
        category_key: str,
        secondary_category_keys: list[str],
        raw_response: str,
    ) -> dict[str, Any]:
        payload = safe_dict(payload)
        if not payload:
            raise ValueError("AI返回内容为空，请稍后重试")
        strategy = self.CATEGORY_STRATEGIES[category_key]
        secondary_strategies = [
            self.CATEGORY_STRATEGIES[item]
            for item in secondary_category_keys
            if item in self.CATEGORY_STRATEGIES
        ]
        combined_labels = [strategy["label"]] + [item["label"] for item in secondary_strategies]
        title = self._growth_title(self._clean_text(self._safe_text(payload.get("title")) or keyword), keyword)
        summary = self._clean_text(self._safe_text(payload.get("summary")))[:60]
        markdown = self._clean_markdown(self._safe_text(payload.get("markdown")))
        markdown = self._remove_legacy_cta_from_markdown(markdown)
        markdown = self._ensure_growth_cta(markdown)
        if not title or not markdown:
            raise ValueError("AI返回内容为空，请稍后重试")

        raw_cta = payload.get("cta")
        cta_payload = safe_dict(raw_cta)
        if cta_payload:
            cta = {
                "title": self._clean_text(self._safe_text(cta_payload.get("title"))),
                "description": self._clean_text(self._safe_text(cta_payload.get("description"))),
                "button_text": self._clean_text(self._safe_text(cta_payload.get("button_text"))),
            }
        else:
            cta_text = self._clean_text(self._safe_text(raw_cta))
            cta = {
                "title": "延伸阅读",
                "description": cta_text or "继续查看更适合当前阶段的内容建议。",
                "button_text": "了解适合自己的资金方案",
            }

        if not raw_cta:
            cta = None
        tags = self._normalize_tags(payload.get("tags"), keyword, combined_labels)
        cover_prompt = self._clean_text(self._safe_text(payload.get("cover_prompt")))
        if not cover_prompt:
            cover_prompt = (
                f"{' + '.join(combined_labels)}公众号封面图，主题：{keyword}，"
                "金融商务风，稳重、可信、16:9 构图，无乱码文字。"
            )

        article = {
            "title": title,
            "summary": summary,
            "content": markdown,
            "category": category_key,
            "tags": ",".join(tags),
            "cover_prompt": cover_prompt,
            "source_name": "沪上银原创",
        }
        raw_html = _render_original_html(
            title,
            markdown,
            article["source_name"],
            category=category_key,
        )
        try:
            html_with_cta = inject_cta_into_html(raw_html, build_cta_html(cta))
        except Exception as exc:
            logger.warning("[ArticleGenerationAgent] CTA 插入失败，已跳过: %s", exc)
            html_with_cta = raw_html
        lead_html = adapt_lead_form_to_wechat_card(html_with_cta)
        safe_html = adapt_html_for_wechat(lead_html)

        return {
            "ok": True,
            "title": title,
            "summary": summary,
            "category": " + ".join(combined_labels),
            "category_key": category_key,
            "secondary_categories": secondary_category_keys,
            "tags": tags,
            "markdown": markdown,
            "html": safe_html,
            "cover_prompt": cover_prompt,
            "cta": cta,
            "raw_response": raw_response,
        }

    def _remove_legacy_cta_from_markdown(self, markdown: str) -> str:
        markers = (
            "场景案例",
            "上海企业融资规划咨询",
            "一对一咨询",
            "融资规划咨询",
            "科学规划",
            "多渠道融资",
            "降低风险",
            "立即咨询",
        )
        blocks = re.split(r"\n{2,}", markdown or "")
        kept_blocks = []
        for block in blocks:
            marker_count = sum(1 for marker in markers if marker in block)
            if marker_count >= 2 or "场景案例" in block:
                continue
            kept_blocks.append(block)
        return "\n\n".join(item.strip() for item in kept_blocks if item.strip()).strip()

    @classmethod
    def _growth_title(cls, title: str, keyword: str = "") -> str:
        safe_title = re.sub(r"\s+", " ", str(title or "").strip(" #　"))
        safe_title = safe_title or str(keyword or "企业融资").strip()
        for phrase in cls.TITLE_FORBIDDEN_PHRASES:
            safe_title = safe_title.replace(phrase, "")
        safe_title = safe_title.strip(" ，,。.-—_|｜:：")
        score = TitleScoreService.score_title(safe_title)
        if score.get("score", 0) < 80:
            candidates = score.get("optimized_titles") or []
            safe_title = str(candidates[0] if candidates else f"{safe_title}被拒后，先查这3点")
        for phrase in cls.TITLE_FORBIDDEN_PHRASES:
            safe_title = safe_title.replace(phrase, "")
        safe_title = safe_title.strip(" ，,。.-—_|｜:：")
        if len(safe_title) > 28:
            safe_title = safe_title[:28].rstrip("，,。？?：:")
        return safe_title or "经营贷被拒后，老板先查这3点"

    @staticmethod
    def _ensure_growth_cta(markdown: str) -> str:
        text = (markdown or "").strip()
        if "企业融资体检" in text and "适合人群" in text and "体检结果" in text:
            return text
        return f"""{text}

## 企业融资体检

适合人群：准备申请经营贷、续贷、降息、提额的企业主。

体检结果：看清当前属于能批、难批、可优化，还是暂缓申请。

行动引导：扫码做融资体检，或添加顾问咨询，先查被拒原因和额度提升空间，再决定下一步怎么申请。""".strip()

    @staticmethod
    def _build_growth_markdown(target_customer: str, pain_point: str, angle: str) -> str:
        return f"""很多老板申请经营贷时，第一反应是“我有营业执照、有流水，银行应该会批”。真正被拒以后才发现，银行看的不是老板觉得生意好不好，而是流水、征信、负债、纳税、用途和还款来源能不能互相对上。

另一个常见误区，是被拒后马上换银行、找熟人、同时多投几家。老板以为这是提高成功率，银行看到的却可能是短期查询变多、资金需求更急、风险信号更重。越着急，越容易把下一次申请也拖进去。

这篇文章解决一个具体问题：{pain_point}。如果你属于{target_customer}，先别急着问“哪家银行利率低”，更应该先弄清银行为什么不批、额度卡在哪里、申请前哪几项能优化。

## 真实案例：一家贸易公司为什么被卡额度

有一家做建材贸易的小微企业，经营 6 年，年流水看起来不低，也有稳定客户。老板原本想申请一笔经营贷，用来垫付采购款和员工工资，结果银行只给了很低额度，离实际周转需求差了一大截。

问题是什么？表面看是额度低，实际是银行没有看见稳定的还款来源。企业流水有高峰，也有断档；部分回款进入个人账户，和合同、发票、纳税匹配不够完整；法人近 3 个月又连续查了几次征信。

为什么影响审批？银行不是只看“有没有生意”，而是看这笔钱借出去后，企业未来几个月能不能按时还。流水波动、查询偏多、用途说明不清，会让银行觉得这家公司资金压力正在放大。

老板应该怎么做？先把对公流水、主要合同、开票记录、纳税记录和回款节奏放在一起复盘，再判断是先补材料、调整申请顺序，还是换更匹配的产品。

## 银行不批，通常卡在这 5 个点

第一，征信不是只看有没有逾期。短期查询次数、对外担保、信用卡和其他贷款使用率，都会影响银行对老板资金紧张程度的判断。

第二，流水不是越大越好。银行更关心流水是否稳定、是否和真实业务对应、是否能覆盖月供和日常经营支出。突然进出的大额资金，如果解释不清，反而会变成疑点。

第三，负债结构会影响新增额度。企业已有贷款、法人个人负债、担保责任叠加后，银行会重新计算还款压力。老板只看自己还得上，银行看的是压力测试下还能不能还。

第四，资金用途必须讲清楚。经营贷不是随便拿去周转，采购、租金、工资、设备、项目垫资等用途都需要和企业经营逻辑一致。

第五，申请时点很关键。续贷临近到期、现金流已经紧张、征信已经被查多次时再申请，银行看到的是风险，而不是机会。

## 申请前，老板先做这 5 个检查

问题是什么？很多老板把融资当成“缺钱时才办”的事，资料临时拼，银行问什么才补什么。这样最容易暴露准备不足，也容易浪费一次征信查询。

为什么影响审批？银行审批有顺序，先看主体和征信，再看经营数据，再看还款来源和用途。任何一项说不清，额度、利率、期限都会被影响。

老板应该怎么做？申请前先做 5 个检查：查企业和法人征信；看近 6-12 个月流水是否稳定；整理合同、发票、纳税和回款证明；计算现有负债和月供压力；明确这笔钱用于哪一段经营周转。

如果已经被拒，不要马上重复提交。先复盘被拒原因，再决定补材料、降额度、换产品，还是暂缓一段时间优化数据。

## 风险提醒：别用“包装”解决审批问题

{angle}。但融资优化不是包装材料，更不是承诺一定能批。任何要求虚构流水、虚假合同、先交高额费用、承诺固定额度和固定利率的做法，都要谨慎。

真正有价值的融资顾问，不是替老板赌运气，而是把银行审批逻辑讲清楚：哪些条件已经够，哪些地方会被卡，哪些动作能提高通过率，哪些情况应该暂缓申请。

## 企业融资体检

适合人群：准备申请经营贷、续贷、降息、提额的企业主。

体检结果：看清当前属于能批、难批、可优化，还是暂缓申请。

行动引导：扫码做融资体检，或添加顾问咨询，先查被拒原因和额度提升空间，再决定下一步怎么申请。"""

    def _normalize_category(self, category: str) -> str:
        safe_category = self._safe_text(category)
        if safe_category in self.CATEGORY_STRATEGIES:
            return safe_category
        return self.CATEGORY_ALIASES.get(safe_category, "")

    def _normalize_secondary_categories(self, categories: list[str], exclude: str) -> list[str]:
        result: list[str] = []
        for category in categories:
            normalized = self._normalize_category(category)
            if normalized and normalized != exclude and normalized not in result:
                result.append(normalized)
        return result[:2]

    def _normalize_tags(self, raw_tags: Any, keyword: str, category_labels: list[str]) -> list[str]:
        tags: list[str] = []
        if isinstance(raw_tags, list):
            tags.extend(self._safe_text(item) for item in raw_tags)
        elif raw_tags:
            tags.extend(self._safe_text(item) for item in str(raw_tags).split(","))
        tags.extend([keyword, *category_labels, "原创"])

        deduped: list[str] = []
        for item in tags:
            cleaned = self._clean_text(item)
            if cleaned and cleaned not in deduped:
                deduped.append(cleaned)
        return deduped[:8]

    def _clean_text(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text or "").strip()
        for word in self.FORBIDDEN_WORDS:
            cleaned = cleaned.replace(word, "")
        return cleaned.strip()

    def _clean_markdown(self, text: str) -> str:
        cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        for word in self.FORBIDDEN_WORDS:
            cleaned = cleaned.replace(word, "")
        cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

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

    @staticmethod
    def _mask_api_key(api_key: str) -> str:
        key = str(api_key or "")
        if not key:
            return ""
        if len(key) <= 8:
            return f"{key[:2]}****{key[-2:]}"
        return f"{key[:4]}****{key[-4:]}"

    @staticmethod
    def _safe_base_url() -> str:
        raw_url = str(OPENAI_BASE_URL or "").strip()
        if not raw_url:
            return ""
        try:
            parsed = urlsplit(raw_url)
            hostname = parsed.hostname or ""
            port = f":{parsed.port}" if parsed.port else ""
            return urlunsplit((parsed.scheme, f"{hostname}{port}", parsed.path.rstrip("/"), "", ""))
        except Exception:
            return raw_url.split("?")[0]

    @classmethod
    def _provider_name(cls) -> str:
        safe_url = cls._safe_base_url().lower()
        if "openai.com" in safe_url:
            return "OpenAI"
        if safe_url:
            return "OpenAI-compatible"
        return ""

    @staticmethod
    def _validate_ai_config() -> str:
        missing = []
        if not str(OPENAI_API_KEY or "").strip():
            missing.append("OPENAI_API_KEY")
        if not str(OPENAI_BASE_URL or "").strip():
            missing.append("OPENAI_BASE_URL")
        if not str(OPENAI_MODEL or "").strip():
            missing.append("OPENAI_MODEL")
        return ",".join(missing)

    @staticmethod
    def _classify_ai_error(exc: Exception) -> tuple[str, str]:
        error_name = type(exc).__name__
        message = str(exc or "")
        combined = f"{error_name} {message}".lower()
        if "timeout" in combined or "timed out" in combined:
            return "AI_TIMEOUT", "AI 生成超时，请稍后重试"
        if (
            "connection" in combined
            or "connecterror" in combined
            or "network" in combined
            or "dns" in combined
        ):
            return "AI_CONNECTION_ERROR", "服务器无法连接 AI 服务，请检查 BASE_URL 或服务器网络"
        if (
            "model" in combined
            and any(word in combined for word in ("not found", "does not exist", "permission", "access", "invalid"))
        ):
            return "AI_MODEL_ERROR", "模型名称错误或当前账号无权限"
        if any(word in combined for word in ("authentication", "unauthorized", "invalid api key", "401")):
            return "AI_AUTH_ERROR", "AI API Key 无效或当前账号无权限"
        return "AI_PROVIDER_ERROR", message or "AI 服务调用失败"

    def _log_ai_exception(self, prefix: str, exc: Exception) -> None:
        logger.error(
            "%s model=%s base_url=%s api_key_loaded=%s api_key_masked=%s "
            "error_type=%s error=%s\n%s",
            prefix,
            OPENAI_MODEL or "",
            self._safe_base_url(),
            bool(OPENAI_API_KEY),
            self._mask_api_key(OPENAI_API_KEY),
            type(exc).__name__,
            str(exc),
            traceback.format_exc(),
        )

    def _error_result(self, message: str, error_type: str = "AI_PROVIDER_ERROR") -> dict[str, Any]:
        return {
            "ok": False,
            "msg": message,
            "error_type": error_type,
            "error_message": message,
            "title": "",
            "summary": "",
            "category": "",
            "category_key": "",
            "tags": [],
            "markdown": "",
            "html": "",
            "cover_prompt": "",
            "cta": None,
            "raw_response": "",
        }
