"""
文章发布前终检 Agent。

只提供发布前安全建议，不自动审核、不自动发布、不修改文章内容。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

logger = logging.getLogger(__name__)


class ArticlePreflightAgent:
    """微信公众号文章发布前终检 Agent。"""

    UNSAFE_WECHAT_TAGS = ("script", "style", "iframe", "form", "input", "textarea", "select", "link")
    HIGH_RISK_WORDS = (
        "包过",
        "百分百下款",
        "100%下款",
        "无视征信",
        "黑户可做",
        "秒批",
        "无条件放款",
        "保证放款",
        "不看征信",
    )

    def __init__(self) -> None:
        """初始化 OpenAI 客户端；不可用时只返回本地规则结果，不让页面 500。"""
        self.client = None
        if not OPENAI_API_KEY:
            return
        try:
            from openai import OpenAI

            self.client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        except Exception as exc:  # pragma: no cover - 依赖运行环境，异常时走兜底。
            logger.warning("[ArticlePreflightAgent] OpenAI 初始化失败: %s", exc)
            self.client = None

    def preflight_article(self, article: dict[str, Any]) -> dict[str, Any]:
        """执行发布前终检：本地规则先兜底，AI 只能补充不能覆盖本地阻断项。"""
        local_result = self._local_preflight(article)
        if not OPENAI_API_KEY or self.client is None:
            local_result["ok"] = False
            local_result["msg"] = "未配置 OPENAI_API_KEY，无法执行 AI 发布前终检"
            return local_result

        raw_response = ""
        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是微信公众号助贷行业发布前终检 Agent。"
                            "你只输出严格 JSON，不输出 Markdown，不输出解释文字。"
                        ),
                    },
                    {"role": "user", "content": self._build_prompt(article, local_result)},
                ],
                temperature=0.2,
                max_tokens=1600,
            )
            raw_response = (response.choices[0].message.content or "").strip()
            ai_result = self._parse_json_response(raw_response)
            return self._merge_results(local_result, ai_result, raw_response, ok=True)
        except Exception as exc:
            logger.warning("[ArticlePreflightAgent] AI 发布前终检失败: %s", exc)
            failed_result = dict(local_result)
            failed_result["ok"] = False
            failed_result["msg"] = f"AI 发布前终检失败：{exc}"
            failed_result["raw_response"] = raw_response
            return failed_result

    def _local_preflight(self, article: dict[str, Any]) -> dict[str, Any]:
        """本地硬规则检查，不依赖 AI。"""
        title = self._safe_text(article.get("title"))
        summary = self._safe_text(article.get("summary"))
        content = self._safe_text(article.get("content"))
        html_content = self._safe_text(article.get("html_content"))
        full_text = f"{title}\n{summary}\n{content}\n{html_content}"

        blocking_issues: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []
        wechat_html_issues: list[str] = []
        title_issues: list[str] = []
        compliance_issues: list[str] = []

        if not title:
            issue = "标题为空，不能进入发布前流程"
            blocking_issues.append(issue)
            title_issues.append(issue)
        elif len(title) > 30:
            issue = "标题超过 30 字，移动端展示风险较高"
            blocking_issues.append(issue)
            title_issues.append(issue)
        elif len(title) > 22:
            issue = "标题超过 22 字，建议压缩后再发布"
            warnings.append(issue)
            title_issues.append(issue)

        for tag in self.UNSAFE_WECHAT_TAGS:
            if re.search(rf"<\s*{tag}\b", html_content, flags=re.IGNORECASE):
                issue = f"HTML 中包含微信公众号不兼容标签：{tag}"
                blocking_issues.append(issue)
                wechat_html_issues.append(issue)

        for word in self.HIGH_RISK_WORDS:
            if word.lower() in full_text.lower():
                issue = f"包含高风险营销表达：{word}"
                blocking_issues.append(issue)
                compliance_issues.append(issue)

        blank_issues = self._detect_blank_layout_risks(html_content)
        if blank_issues:
            warnings.extend(blank_issues)
            wechat_html_issues.extend(blank_issues)

        if not blocking_issues and not warnings:
            suggestions.append("本地规则未发现明显发布阻断问题，仍建议人工复核正文事实和表达。")

        risk_level = self._calculate_risk_level(blocking_issues, warnings)
        return {
            "ok": True,
            "pass_preflight": not blocking_issues,
            "risk_level": risk_level,
            "blocking_issues": self._unique(blocking_issues),
            "warnings": self._unique(warnings),
            "suggestions": self._unique(suggestions),
            "wechat_html_issues": self._unique(wechat_html_issues),
            "title_issues": self._unique(title_issues),
            "compliance_issues": self._unique(compliance_issues),
            "raw_response": "",
        }

    def _detect_blank_layout_risks(self, html_content: str) -> list[str]:
        """检查明显空白段落或排版异常风险。"""
        issues: list[str] = []
        if not html_content:
            return issues

        if re.search(r"(<br\s*/?>\s*){3,}", html_content, flags=re.IGNORECASE):
            issues.append("HTML 中存在连续多个换行，可能造成公众号大面积空白")
        if html_content.count("&nbsp;") >= 8:
            issues.append("HTML 中存在较多 &nbsp; 占位，可能造成异常留白")
        if len(re.findall(r"<p[^>]*>\s*(?:&nbsp;|<br\s*/?>|\s)*</p>", html_content, flags=re.IGNORECASE)) >= 3:
            issues.append("HTML 中存在多个空 p 标签，建议清理后再发布")
        if len(re.findall(r"<div[^>]*>\s*(?:&nbsp;|<br\s*/?>|\s)*</div>", html_content, flags=re.IGNORECASE)) >= 3:
            issues.append("HTML 中存在多个空 div 标签，建议清理后再发布")
        return issues

    def _build_prompt(self, article: dict[str, Any], local_result: dict[str, Any]) -> str:
        """构造要求模型返回 JSON 的终检提示词。"""
        title = self._safe_text(article.get("title"))
        summary = self._safe_text(article.get("summary"))
        content = self._safe_text(article.get("content"))
        html_content = self._safe_text(article.get("html_content"))

        return f"""
请对下面这篇微信公众号文章做发布前终检，必须只返回 JSON：

返回 JSON 字段固定为：
{{
  "pass_preflight": true/false,
  "risk_level": "low/medium/high",
  "blocking_issues": [],
  "warnings": [],
  "suggestions": [],
  "wechat_html_issues": [],
  "title_issues": [],
  "compliance_issues": []
}}

重点检查：
1. 是否仍存在包过、无视征信、百分百下款、秒批、保证放款等违规营销表达。
2. 是否仍包含 script/style/link/iframe/form/input/textarea/select 等微信公众号不兼容标签。
3. 标题是否过长、堆砌、不适合公众号移动端展示。
4. 留资表单是否已转换为公众号兼容入口，而不是真实表单。
5. 是否存在明显空白段落或排版风险。
6. 是否适合进入微信草稿箱。

本地规则检查结果，AI 只能补充，不能删除本地阻断项：
{json.dumps(local_result, ensure_ascii=False)}

文章标题：
{title}

文章摘要：
{summary}

正文内容：
{content[:6000]}

HTML 内容片段：
{html_content[:3500]}
""".strip()

    def _merge_results(
        self,
        local_result: dict[str, Any],
        ai_result: dict[str, Any],
        raw_response: str,
        ok: bool,
    ) -> dict[str, Any]:
        """合并本地和 AI 结果，本地阻断项拥有最高优先级。"""
        blocking_issues = self._unique(
            self._ensure_list(local_result.get("blocking_issues")) + self._ensure_list(ai_result.get("blocking_issues"))
        )
        warnings = self._unique(
            self._ensure_list(local_result.get("warnings")) + self._ensure_list(ai_result.get("warnings"))
        )
        suggestions = self._unique(
            self._ensure_list(local_result.get("suggestions")) + self._ensure_list(ai_result.get("suggestions"))
        )
        wechat_html_issues = self._unique(
            self._ensure_list(local_result.get("wechat_html_issues")) + self._ensure_list(ai_result.get("wechat_html_issues"))
        )
        title_issues = self._unique(
            self._ensure_list(local_result.get("title_issues")) + self._ensure_list(ai_result.get("title_issues"))
        )
        compliance_issues = self._unique(
            self._ensure_list(local_result.get("compliance_issues")) + self._ensure_list(ai_result.get("compliance_issues"))
        )

        ai_risk_level = self._safe_text(ai_result.get("risk_level")).lower()
        risk_level = self._max_risk(local_result.get("risk_level"), ai_risk_level)
        if blocking_issues:
            risk_level = "high"

        return {
            "ok": ok,
            "pass_preflight": bool(ai_result.get("pass_preflight", True)) and not blocking_issues,
            "risk_level": risk_level,
            "blocking_issues": blocking_issues,
            "warnings": warnings,
            "suggestions": suggestions,
            "wechat_html_issues": wechat_html_issues,
            "title_issues": title_issues,
            "compliance_issues": compliance_issues,
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

    def _calculate_risk_level(self, blocking_issues: list[str], warnings: list[str]) -> str:
        """根据本地规则结果计算风险等级。"""
        if blocking_issues:
            return "high"
        if warnings:
            return "medium"
        return "low"

    def _max_risk(self, first: Any, second: Any) -> str:
        """取两个风险等级中更高的一个。"""
        order = {"low": 0, "medium": 1, "high": 2}
        first_level = self._safe_text(first).lower()
        second_level = self._safe_text(second).lower()
        first_level = first_level if first_level in order else "medium"
        second_level = second_level if second_level in order else "medium"
        return first_level if order[first_level] >= order[second_level] else second_level

    def _ensure_list(self, value: Any) -> list[str]:
        """把任意值整理成字符串列表。"""
        if isinstance(value, list):
            return [self._safe_text(item) for item in value if self._safe_text(item)]
        if value:
            return [self._safe_text(value)]
        return []

    def _unique(self, items: list[str]) -> list[str]:
        """列表去重并保持顺序。"""
        result: list[str] = []
        for item in items:
            if item and item not in result:
                result.append(item)
        return result

    def _safe_text(self, value: Any) -> str:
        """安全转字符串，避免 None 影响检查。"""
        return str(value or "").strip()
