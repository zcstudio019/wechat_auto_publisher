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
            return self._error_result(
                "AI 客户端初始化失败",
                error_type="AI_CLIENT_INIT_FAILED",
            )

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
                        "content": (
                            "你是微信公众号企业融资内容生成 Agent。"
                            "你必须只返回严格 JSON，不要输出 Markdown 包裹，不要输出额外解释。"
                        ),
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
                        ) + "\n\n补充要求：cta 只返回结构化对象，字段为 title、description、button_text；禁止把 CTA 文案写进 markdown 正文，也不要把 CTA 放在文章开头、标题下方或导语后。",
                    },
                ],
                temperature=0.45,
                max_tokens=4200,
            )
            choice = response.choices[0] if getattr(response, "choices", None) else None
            message = getattr(choice, "message", None)
            raw_response = (getattr(message, "content", "") or "").strip()
            if not raw_response:
                result = self._error_result(
                    "AI 返回内容为空，请稍后重试",
                    error_type="AI_EMPTY_RESPONSE",
                )
                result["raw_response"] = raw_response
                return result
            payload = safe_dict(self._parse_json_response(raw_response))
            if not payload:
                result = self._error_result(
                    "AI 返回内容为空，请稍后重试",
                    error_type="AI_EMPTY_RESPONSE",
                )
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
                result = self._error_result(
                    "AI 返回内容为空，请稍后重试",
                    error_type="AI_EMPTY_RESPONSE",
                )
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
            base_result.update({
                "error_type": "AI_CLIENT_INIT_FAILED",
                "error_message": "AI 客户端初始化失败",
            })
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
        target_customer = str(context.get("target_customer") or "正在申请经营贷或面临资金周转压力的企业老板")
        pain_point = str(context.get("pain_point") or "银行不批、额度不足、续贷不稳，却不知道问题出在哪里")
        angle = str(context.get("article_angle") or "从银行审批视角拆解企业经营数据、征信与现金流")
        markdown = f"""一位企业老板最近遇到的情况很典型：订单在增加，回款却变慢，月底工资、采购款和贷款到期日挤在一起。老板最着急的不是听金融概念，而是想知道银行为什么不批、额度怎么提升。

## 老板真正卡住的是什么

这篇文章面向{target_customer}。常见痛点是：{pain_point}。银行审批看的不是老板口头说业务不错，而是经营流水、纳税、负债、征信和还款来源能否互相印证。

## 一个真实经营场景

一家贸易企业有稳定订单，但前一次经营贷申请只拿到较低额度。复盘后发现，企业短期查询次数偏多、上下游回款波动、部分资金用途材料不完整。调整重点不是盲目换银行，而是先把申请顺序和经营证据重新梳理。

## 银行通常会拆这 5 个问题

1. 企业流水是否稳定，能否和合同、发票、纳税对应。
2. 企业和法人征信是否存在逾期、担保或频繁查询。
3. 当前负债是否挤压新增贷款的还款能力。
4. 资金用途是否清晰并符合真实经营需求。
5. 申请时间是否过晚，尤其是续贷临近到期才准备。

## 给企业老板的 5 个建议

1. 申请前先做融资体检，明确被拒原因和可优化空间。
2. 控制短期查询次数，不要同时向多家机构盲目申请。
3. 把流水、纳税、合同和回款节奏放在一起准备。
4. 根据企业阶段匹配银行和产品，不只比较利率。
5. 续贷至少提前 60 至 90 天排查风险。

## 风险提醒

{angle}。融资方案必须根据企业实际情况评估，不能承诺一定放款、固定额度或固定利率。任何要求先交高额费用、包装虚假材料的做法都需要谨慎。

## 企业融资体检

如果你的企业也遇到银行不批、额度低或续贷不稳，可以先做一次融资体检：梳理被拒原因、额度提升空间和下一步申请顺序，再决定是否提交申请。
"""
        article = {
            "title": safe_topic,
            "summary": f"从老板真实场景出发，拆解银行审批卡点和融资优化路径。"[:60],
            "content": markdown,
            "category": "leads",
            "tags": f"{safe_topic},企业融资,自动获客,原创",
            "cover_prompt": f"企业融资顾问公众号封面，主题：{safe_topic}，商务写实、可信、16:9，无文字",
            "source_name": "沪上银原创",
        }
        return {
            "ok": True,
            "title": safe_topic,
            "summary": article["summary"],
            "category": "企业融资获客",
            "category_key": "leads",
            "secondary_categories": ["finance", "enterprise"],
            "tags": [safe_topic, "企业融资", "自动获客", "原创"],
            "markdown": markdown,
            "html": adapt_html_for_wechat(
                _render_original_html(
                    safe_topic,
                    markdown,
                    article["source_name"],
                    category="leads",
                )
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
1. 标题必须是痛点型标题，优先包含“老板”“银行为什么不批”“额度怎么提升”“被拒原因”“融资体检”等表达。
2. 开头必须写老板真实场景：订单、账期、工资、采购、续贷、被拒、额度低或现金流周转压力。
3. 正文必须包含一个匿名企业融资案例，写清企业类型、融资卡点、银行关注点和调整方向。
4. 必须用 3-5 个问题拆解：如征信、流水、负债、纳税、用途、担保、查询次数。
5. 必须给出 3-5 个解决建议：如提前体检、资料梳理、控制查询、优化流水、匹配银行、规划续贷。
6. 必须有风险提醒：不承诺放款，不夸大额度，强调根据企业实际情况评估。
7. 必须有融资诊断 CTA 和二维码/咨询引导；CTA 仍只放在结构化 cta 字段，不写进 markdown 正文。
8. 不要写成金融百科，不要写成银行宣传稿，不要写空泛大道理，要像懂融资顾问的人在跟老板说话。
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
5. 长度：{self.LENGTH_HINTS[length]}
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
        title = self._clean_text(self._safe_text(payload.get("title")) or keyword)
        summary = self._clean_text(self._safe_text(payload.get("summary")))[:60]
        markdown = self._clean_markdown(self._safe_text(payload.get("markdown")))
        markdown = self._remove_legacy_cta_from_markdown(markdown)
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
