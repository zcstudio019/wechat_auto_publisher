"""
文章审核 Agent。

只提供 AI 审核建议，不自动修改文章、不替代人工审核、不触发发布流程。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

logger = logging.getLogger(__name__)


class ArticleReviewAgent:
    """微信公众号文章审核 Agent。"""

    RISK_WORDS = [
        "包过",
        "百分百下款",
        "100%下款",
        "无视征信",
        "黑户可做",
        "秒批",
        "秒下",
        "保证放款",
        "必下款",
    ]
    WECHAT_UNSAFE_TAGS = ["<form", "<input", "<textarea", "<select", "<script", "<style", "<link", "<iframe"]

    def __init__(self) -> None:
        """初始化 OpenAI 客户端，未配置时保持为空，避免页面 500。"""
        self.client = None
        if not OPENAI_API_KEY:
            return
        try:
            from openai import OpenAI

            self.client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        except Exception as exc:  # pragma: no cover - 依赖环境差异，运行时兜底即可。
            logger.warning("[ArticleReviewAgent] OpenAI 初始化失败: %s", exc)
            self.client = None

    def review_article(self, article: dict[str, Any]) -> dict[str, Any]:
        """审核单篇文章，返回固定结构的 AI 审核建议。"""
        if not OPENAI_API_KEY or self.client is None:
            return {
                "ok": False,
                "msg": "未配置 OPENAI_API_KEY，无法执行 AI 审核",
                "risk_level": "",
                "can_publish": False,
                "issues": [],
                "suggestions": [],
                "optimized_title": "",
                "optimized_summary": "",
                "raw_response": "",
            }

        prompt = self._build_prompt(article)
        raw_response = ""
        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是微信公众号助贷行业合规审核 Agent。"
                            "你只输出严格 JSON，不输出 Markdown，不输出解释文字。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=1200,
            )
            raw_response = (response.choices[0].message.content or "").strip()
            payload = self._parse_json_response(raw_response)
            return self._normalize_result(payload, raw_response)
        except Exception as exc:
            logger.exception("[ArticleReviewAgent] AI 审核失败: %s", exc)
            return {
                "ok": False,
                "msg": f"AI 审核失败：{exc}",
                "risk_level": "",
                "can_publish": False,
                "issues": [],
                "suggestions": [],
                "optimized_title": "",
                "optimized_summary": "",
                "raw_response": raw_response,
            }

    def _build_prompt(self, article: dict[str, Any]) -> str:
        """构造要求模型返回 JSON 的审核提示词。"""
        title = self._safe_text(article.get("title"))
        summary = self._safe_text(article.get("summary"))
        content = self._safe_text(article.get("content"))
        html_content = self._safe_text(article.get("html_content"))
        tags = self._safe_text(article.get("tags"))
        local_findings = self._build_local_findings(title, summary, content, html_content)

        # 控制正文长度，避免一次审核塞入过长内容导致调用失败。
        content_for_review = (content or html_content)[:6000]
        html_for_review = html_content[:2500]

        return f"""
请审核下面这篇微信公众号文章，必须只返回 JSON：

返回 JSON 字段固定为：
{{
  "risk_level": "low/medium/high",
  "can_publish": true/false,
  "issues": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"],
  "optimized_title": "优化后的标题",
  "optimized_summary": "优化后的摘要"
}}

审核维度：
1. 合规风险：是否出现包过、百分百下款、无视征信、黑户可做、秒批、违规承诺、具体利率承诺、夸大放款能力。
2. 标题质量：是否超过22字、是否关键词堆砌、是否通顺、是否适合公众号点击。
3. 摘要质量：是否简洁、有吸引力、符合助贷行业合规表达。
4. 正文质量：结构是否清晰、是否有明显错别字、是否过度营销、是否有合规留资引导、是否适合企业老板阅读。
5. 微信兼容性：是否含真实 form/input/textarea/select，是否含 script/style/link/iframe，是否可能导致草稿箱渲染异常。

本地预检查发现：
{json.dumps(local_findings, ensure_ascii=False)}

文章标题：
{title}

文章摘要：
{summary}

文章标签：
{tags}

正文内容：
{content_for_review}

HTML 内容片段：
{html_for_review}
""".strip()

    def _build_local_findings(self, title: str, summary: str, content: str, html_content: str) -> list[str]:
        """先做轻量规则检查，把明显风险交给模型参考。"""
        findings: list[str] = []
        full_text = f"{title}\n{summary}\n{content}\n{html_content}".lower()

        for word in self.RISK_WORDS:
            if word.lower() in full_text:
                findings.append(f"疑似违规承诺词：{word}")

        for tag in self.WECHAT_UNSAFE_TAGS:
            if tag in full_text:
                findings.append(f"微信正文兼容风险标签：{tag}")

        if len(title) > 22:
            findings.append("标题超过 22 字，建议压缩")

        if re.search(r"\d+(\.\d+)?\s*%", full_text) and any(key in full_text for key in ["利率", "年化", "最低"]):
            findings.append("疑似出现具体利率承诺，建议改为区间或提示以实际审批为准")

        return findings or ["未发现明显规则风险，仍需模型综合判断"]

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

    def _normalize_result(self, payload: dict[str, Any], raw_response: str) -> dict[str, Any]:
        """补齐固定返回结构，避免前端处理空字段时报错。"""
        risk_level = str(payload.get("risk_level") or "medium").lower()
        if risk_level not in {"low", "medium", "high"}:
            risk_level = "medium"

        return {
            "ok": True,
            "risk_level": risk_level,
            "can_publish": bool(payload.get("can_publish", False)),
            "issues": self._ensure_list(payload.get("issues")),
            "suggestions": self._ensure_list(payload.get("suggestions")),
            "optimized_title": self._safe_text(payload.get("optimized_title")),
            "optimized_summary": self._safe_text(payload.get("optimized_summary")),
            "raw_response": raw_response,
        }

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
