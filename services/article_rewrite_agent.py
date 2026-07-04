"""
文章修改 Agent。

只生成优化建议稿预览，不写数据库、不自动审核、不自动发布。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from ai_processor.processor import format_to_wechat_html
from services.wechat_html_adapter import adapt_html_for_wechat
from services.wechat_lead_card_adapter import adapt_lead_form_to_wechat_card, append_lead_qr_at_end

logger = logging.getLogger(__name__)


class ArticleRewriteAgent:
    """微信公众号文章修改 Agent。"""

    FORBIDDEN_WORDS = [
        "包过",
        "百分百下款",
        "100%下款",
        "无视征信",
        "黑户可做",
        "秒批",
        "保证放款",
        "必下款",
    ]

    def __init__(self) -> None:
        """初始化 OpenAI 客户端，未配置时保持为空，避免页面 500。"""
        self.client = None
        if not OPENAI_API_KEY:
            return
        try:
            from openai import OpenAI

            self.client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        except Exception as exc:  # pragma: no cover - 依赖运行环境，异常时走兜底返回。
            logger.warning("[ArticleRewriteAgent] OpenAI 初始化失败: %s", exc)
            self.client = None

    def rewrite_article(self, article: dict[str, Any], review_result: dict[str, Any] | None = None) -> dict[str, Any]:
        """根据当前文章和可选审核建议生成优化稿预览。"""
        if not OPENAI_API_KEY or self.client is None:
            return self._error_result("未配置 OPENAI_API_KEY，无法执行 AI 优化")

        prompt = self._build_prompt(article, review_result)
        raw_response = ""
        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是微信公众号助贷行业文章修改 Agent。"
                            "你只输出严格 JSON，不输出 Markdown 包裹，不输出解释文字。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.35,
                max_tokens=3200,
            )
            raw_response = (response.choices[0].message.content or "").strip()
            payload = self._parse_json_response(raw_response)
            return self._normalize_result(article, payload, raw_response)
        except Exception as exc:
            # 解析失败、网络失败都只返回给前端提示，不让详情页出现 500。
            logger.warning("[ArticleRewriteAgent] AI 优化失败: %s", exc)
            result = self._error_result(f"AI 优化失败：{exc}")
            result["raw_response"] = raw_response
            return result

    def _build_prompt(self, article: dict[str, Any], review_result: dict[str, Any] | None) -> str:
        """构造要求模型返回 JSON 的修改提示词。"""
        title = self._safe_text(article.get("title"))
        summary = self._safe_text(article.get("summary"))
        content = self._safe_text(article.get("content"))
        html_content = self._safe_text(article.get("html_content"))
        tags = self._safe_text(article.get("tags"))
        review_json = json.dumps(review_result or {}, ensure_ascii=False)

        return f"""
请基于当前文章和 AI 审核建议，生成一版优化后的公众号文章草稿。必须只返回 JSON：

返回 JSON 字段固定为：
{{
  "rewritten_title": "优化后的标题",
  "rewritten_summary": "优化后的摘要",
  "rewritten_content": "优化后的正文",
  "change_summary": ["修改点1", "修改点2"]
}}

硬性要求：
1. 标题 12～18 字最佳，最长不超过 22 字，不能关键词堆砌。
2. 摘要 60 字以内，适合公众号列表预览，不夸大、不承诺结果。
3. 正文保留原文核心意思和行业定位：企业融资顾问、上海贷款顾问、企业资金规划。
4. 正文结构更清晰：问题、原因、解决思路、风险提醒、合规咨询引导。
5. 删除或弱化违规营销词，不允许出现包过、秒批、无视征信、百分百下款、黑户可做。
6. 不允许具体利率承诺，不允许诱导式违规营销。
7. 不要生成真实 form/input/textarea/select/script/style/link/iframe。
8. 留资引导只能写成合规 CTA，例如“如需一对一评估，可点击菜单咨询”，不能承诺审批结果。

AI 审核建议：
{review_json}

原标题：
{title}

原摘要：
{summary}

标签：
{tags}

原正文：
{(content or html_content)[:8000]}
""".strip()

    def _normalize_result(self, article: dict[str, Any], payload: dict[str, Any], raw_response: str) -> dict[str, Any]:
        """补齐固定返回结构，并生成微信兼容 HTML 预览。"""
        title = self._normalize_title(self._safe_text(payload.get("rewritten_title")))
        summary = self._normalize_summary(self._safe_text(payload.get("rewritten_summary")))
        content = self._safe_text(payload.get("rewritten_content"))
        if not content:
            raise ValueError("模型未返回 rewritten_content")

        # 复用现有公众号排版和微信兼容清洗链路，仅用于前端预览，不写入数据库。
        source_name = self._safe_text(article.get("source_name")) or "沪上银原创"
        raw_html = format_to_wechat_html(title, content, source_name)
        lead_card_html = adapt_lead_form_to_wechat_card(raw_html)
        wechat_html = append_lead_qr_at_end(adapt_html_for_wechat(lead_card_html))

        return {
            "ok": True,
            "rewritten_title": title,
            "rewritten_summary": summary,
            "rewritten_content": content,
            "rewritten_html_content": wechat_html,
            "change_summary": self._ensure_list(payload.get("change_summary")),
            "raw_response": raw_response,
        }

    def _parse_json_response(self, raw_response: str) -> dict[str, Any]:
        """解析模型 JSON；兼容偶发代码块包裹。"""
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

    def _normalize_title(self, title: str) -> str:
        """标题长度兜底控制，避免模型偶发输出过长标题。"""
        cleaned = re.sub(r"\s+", "", title or "")
        for word in self.FORBIDDEN_WORDS:
            cleaned = cleaned.replace(word, "")
        if not cleaned:
            cleaned = "企业融资前先看这几点"
        return cleaned[:22]

    def _normalize_summary(self, summary: str) -> str:
        """摘要长度和风险词兜底清理。"""
        cleaned = re.sub(r"\s+", " ", summary or "").strip()
        for word in self.FORBIDDEN_WORDS:
            cleaned = cleaned.replace(word, "")
        return cleaned[:60]

    def _ensure_list(self, value: Any) -> list[str]:
        """把模型返回的列表字段统一成字符串列表。"""
        if isinstance(value, list):
            return [self._safe_text(item) for item in value if self._safe_text(item)]
        if value:
            return [self._safe_text(value)]
        return []

    def _safe_text(self, value: Any) -> str:
        """安全转字符串，避免 None 或 datetime 等对象影响 prompt/JSON。"""
        return str(value or "").strip()

    def _error_result(self, message: str) -> dict[str, Any]:
        """统一失败返回结构，前端可以稳定渲染。"""
        return {
            "ok": False,
            "msg": message,
            "rewritten_title": "",
            "rewritten_summary": "",
            "rewritten_content": "",
            "rewritten_html_content": "",
            "change_summary": [],
            "raw_response": "",
        }
