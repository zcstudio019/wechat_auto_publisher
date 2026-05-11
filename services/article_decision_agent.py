"""
文章运营决策 Agent。

汇总文章状态、AI 审核结果、发布前终检结果和最近发布任务，给运营下一步建议。
只给建议，不自动执行任何审核、发布或修改动作。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

logger = logging.getLogger(__name__)


class ArticleDecisionAgent:
    """文章运营决策 Agent。"""

    DECISION_LABELS = {
        "rewrite": "建议先优化文章",
        "review": "建议先做 AI 审核",
        "preflight": "建议先做发布前终检",
        "approve": "建议进入人工审核",
        "publish": "建议推送微信草稿箱",
        "retry": "建议重试发布任务",
        "hold": "建议暂缓发布",
        "regenerate": "建议重新生成文章",
    }

    def __init__(self) -> None:
        """初始化 OpenAI 客户端；没有 Key 时仍使用本地规则给建议。"""
        self.client = None
        if not OPENAI_API_KEY:
            return
        try:
            from openai import OpenAI

            self.client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        except Exception as exc:  # pragma: no cover - 依赖运行环境，失败时降级本地规则。
            logger.warning("[ArticleDecisionAgent] OpenAI 初始化失败: %s", exc)
            self.client = None

    def decide_next_action(
        self,
        article: dict[str, Any],
        review_result: dict[str, Any] | None = None,
        preflight_result: dict[str, Any] | None = None,
        latest_publish_task: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """给出文章下一步运营建议。"""
        local_decision = self._local_decision(article, review_result, preflight_result, latest_publish_task)
        if not OPENAI_API_KEY or self.client is None:
            return local_decision

        raw_response = ""
        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是微信公众号运营决策 Agent。"
                            "你只能补充 reason、next_steps、warnings，不能输出新的 decision。"
                            "你只输出严格 JSON，不输出 Markdown 或解释文字。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._build_prompt(
                            article,
                            review_result,
                            preflight_result,
                            latest_publish_task,
                            local_decision,
                        ),
                    },
                ],
                temperature=0.25,
                max_tokens=900,
            )
            raw_response = (response.choices[0].message.content or "").strip()
            ai_payload = self._parse_json_response(raw_response)
            return self._merge_ai_payload(local_decision, ai_payload, raw_response)
        except Exception as exc:
            logger.warning("[ArticleDecisionAgent] AI 运营决策补充失败: %s", exc)
            fallback = dict(local_decision)
            fallback["raw_response"] = raw_response
            return fallback

    def _local_decision(
        self,
        article: dict[str, Any],
        review_result: dict[str, Any] | None,
        preflight_result: dict[str, Any] | None,
        latest_publish_task: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """本地决策规则，保证无 OpenAI 时也可用。"""
        title = self._safe_text(article.get("title"))
        content = self._safe_text(article.get("content") or article.get("html_content"))
        status = self._safe_text(article.get("status"))

        if not title or not content:
            return self._decision(
                "regenerate",
                "high",
                False,
                "文章标题或正文为空，无法进入稳定发布链路。",
                ["重新生成文章", "确认标题、摘要、正文完整后再执行审核"],
                ["当前文章基础内容不完整"],
            )

        if preflight_result and preflight_result.get("pass_preflight") is False:
            return self._decision(
                "hold",
                "high",
                False,
                "AI 发布前终检未通过，建议先处理阻断问题。",
                ["查看终检阻断问题", "点击“AI 一键优化草稿”或手动修改文章", "重新执行发布前终检"],
                self._ensure_list(preflight_result.get("blocking_issues")),
            )

        if review_result and self._safe_text(review_result.get("risk_level")).lower() == "high":
            return self._decision(
                "rewrite",
                "high",
                False,
                "AI 审核结果为高风险，建议先优化文章。",
                ["点击“AI 一键优化草稿”", "确认优化结果后点击“应用优化稿”", "重新执行 AI 审核和发布前终检"],
                self._ensure_list(review_result.get("issues")),
            )

        task_status = self._safe_text((latest_publish_task or {}).get("status")).lower()
        if task_status == "failed":
            return self._decision(
                "retry",
                "medium",
                False,
                "最近一次发布任务失败，建议优先处理失败任务。",
                ["查看最近发布任务错误信息", "前往发布任务列表重试失败任务", "确认微信草稿箱是否已生成"],
                [self._safe_text((latest_publish_task or {}).get("error_message")) or "最近发布任务失败"],
            )

        if status == "draft":
            return self._decision(
                "review",
                "medium",
                True,
                "文章仍为草稿，建议先做 AI 审核并进入人工审核。",
                ["点击“AI 审核建议”", "必要时优化并应用草稿", "执行“AI 发布前终检”", "人工确认后点击“审核通过”"],
                [],
            )

        if status == "approved":
            return self._decision(
                "publish",
                "medium",
                True,
                "文章已审核，建议确认终检后推送微信草稿箱。",
                ["点击“AI 发布前终检”", "确认无阻断问题后推送微信草稿箱"],
                [],
            )

        if status == "draft_sent":
            return self._decision(
                "hold",
                "low",
                False,
                "文章已进入微信草稿箱，无需重复推送。",
                ["进入微信后台确认草稿内容", "如需修改，请先编辑文章后重新走审核流程"],
                [],
            )

        if status == "published":
            return self._decision(
                "hold",
                "low",
                False,
                "文章已发布，当前无需继续发布链路。",
                ["如需复盘，可查看发布任务和获客数据"],
                [],
            )

        return self._decision(
            "preflight",
            "medium",
            True,
            "当前状态需要进一步确认，建议先做发布前终检。",
            ["点击“AI 发布前终检”", "根据终检结果决定是否继续审核或发布"],
            [],
        )

    def _build_prompt(
        self,
        article: dict[str, Any],
        review_result: dict[str, Any] | None,
        preflight_result: dict[str, Any] | None,
        latest_publish_task: dict[str, Any] | None,
        local_decision: dict[str, Any],
    ) -> str:
        """构造 AI 补充说明 prompt，明确禁止覆盖本地 decision。"""
        return f"""
请基于下面信息，为运营补充更清晰的原因、下一步步骤和风险提醒。
只能返回 JSON，字段固定为：
{{
  "reason": "一句话说明",
  "next_steps": ["步骤1", "步骤2"],
  "warnings": ["风险1", "风险2"]
}}

重要限制：
- 不要输出 decision、priority、can_continue。
- 不要覆盖本地规则给出的决策。
- 如果本地决策 priority=high，请保持谨慎，不建议继续发布链路。

文章信息：
{json.dumps(self._compact_article(article), ensure_ascii=False)}

AI 审核结果：
{json.dumps(review_result or {}, ensure_ascii=False)}

AI 发布前终检结果：
{json.dumps(preflight_result or {}, ensure_ascii=False)}

最近发布任务：
{json.dumps(latest_publish_task or {}, ensure_ascii=False, default=str)}

本地决策结果：
{json.dumps(local_decision, ensure_ascii=False)}
""".strip()

    def _merge_ai_payload(self, local_decision: dict[str, Any], ai_payload: dict[str, Any], raw_response: str) -> dict[str, Any]:
        """合并 AI 补充内容，保留本地决策字段不被覆盖。"""
        result = dict(local_decision)
        reason = self._safe_text(ai_payload.get("reason"))
        next_steps = self._ensure_list(ai_payload.get("next_steps"))
        warnings = self._ensure_list(ai_payload.get("warnings"))

        if reason:
            result["reason"] = reason
        if next_steps:
            result["next_steps"] = next_steps
        if warnings:
            result["warnings"] = self._unique(result.get("warnings", []) + warnings)
        result["raw_response"] = raw_response
        return result

    def _decision(
        self,
        decision: str,
        priority: str,
        can_continue: bool,
        reason: str,
        next_steps: list[str],
        warnings: list[str],
    ) -> dict[str, Any]:
        """生成固定结构的本地决策结果。"""
        return {
            "ok": True,
            "decision": decision,
            "decision_label": self.DECISION_LABELS.get(decision, "建议人工判断下一步"),
            "priority": priority,
            "can_continue": can_continue,
            "reason": reason,
            "next_steps": self._unique(next_steps),
            "warnings": self._unique([item for item in warnings if item]),
            "raw_response": "",
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

    def _compact_article(self, article: dict[str, Any]) -> dict[str, str]:
        """压缩文章信息，避免 prompt 过长。"""
        return {
            "id": self._safe_text(article.get("id")),
            "title": self._safe_text(article.get("title")),
            "summary": self._safe_text(article.get("summary"))[:300],
            "status": self._safe_text(article.get("status")),
            "review_status": self._safe_text(article.get("review_status")),
            "publish_status": self._safe_text(article.get("publish_status")),
            "content": self._safe_text(article.get("content"))[:1200],
            "html_content": self._safe_text(article.get("html_content"))[:800],
        }

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
        """安全转字符串。"""
        return str(value or "").strip()
