"""文章 AI 操作日志服务。

该服务只负责记录和读取 Agent 操作轨迹，任何写入异常都不能影响原有
AI 审核、优化、终检、决策和工作流接口的主流程。
"""
import json
import logging
from typing import Any

from database import get_db, is_mysql


logger = logging.getLogger(__name__)


class AIOperationLogService:
    """提供 AI 操作日志的写入、摘要生成和文章维度查询能力。"""

    @staticmethod
    def create_log(
        article_id: int,
        agent_name: str,
        action_type: str,
        result: dict,
        operator_id: int | None = None,
        operator_name: str = "",
    ) -> int | None:
        """创建一条 AI 操作日志；失败时返回 None，绝不影响主流程。"""
        try:
            safe_result = result if isinstance(result, dict) else {"ok": False, "msg": "返回结果格式异常"}
            ok = 1 if bool(safe_result.get("ok")) else 0
            summary = AIOperationLogService.build_summary(action_type, safe_result)
            error_message = "" if ok else str(safe_result.get("msg") or safe_result.get("error") or "操作失败")
            result_json = json.dumps(safe_result, ensure_ascii=False, default=str)

            conn = get_db()
            if is_mysql():
                cursor = conn.execute(
                    """
                    INSERT INTO ai_operation_logs
                    (article_id, agent_name, action_type, operator_id, operator_name, ok, summary, result_json, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        article_id,
                        agent_name,
                        action_type,
                        operator_id,
                        operator_name,
                        ok,
                        summary,
                        result_json,
                        error_message,
                    ),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO ai_operation_logs
                    (article_id, agent_name, action_type, operator_id, operator_name, ok, summary, result_json, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        article_id,
                        agent_name,
                        action_type,
                        operator_id,
                        operator_name,
                        ok,
                        summary,
                        result_json,
                        error_message,
                    ),
                )
            conn.commit()
            log_id = cursor.lastrowid
            conn.close()
            return log_id
        except Exception as exc:  # pragma: no cover - 兜底保护主流程
            logger.warning("AI 操作日志写入失败：%s", exc)
            try:
                conn.close()  # type: ignore[name-defined]
            except Exception:
                pass
            return None

    @staticmethod
    def list_logs_for_article(article_id: int, limit: int = 20) -> list[dict]:
        """查询某篇文章最近 AI 操作日志，按 id 倒序返回。"""
        try:
            safe_limit = max(1, min(int(limit or 20), 100))
            conn = get_db()
            placeholder = "%s" if is_mysql() else "?"
            rows = conn.execute(
                f"""
                SELECT id, article_id, agent_name, action_type, operator_id, operator_name,
                       ok, summary, error_message, created_at
                FROM ai_operation_logs
                WHERE article_id={placeholder}
                ORDER BY id DESC
                LIMIT {safe_limit}
                """,
                (article_id,),
            ).fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as exc:
            # 日志读取失败不应拖垮文章详情页，只记录 warning 并返回空列表。
            logger.warning("AI 操作日志读取失败：%s", exc)
            try:
                conn.close()  # type: ignore[name-defined]
            except Exception:
                pass
            return []

    @staticmethod
    def build_summary(action_type: str, result: dict) -> str:
        """按操作类型生成页面快速展示摘要。"""
        if not isinstance(result, dict):
            return "操作失败"

        if not result.get("ok"):
            return "操作失败"

        if action_type == "ai_review":
            can_publish = "是" if result.get("can_publish") else "否"
            return f"风险等级：{result.get('risk_level') or '-'}，建议发布：{can_publish}"

        if action_type == "ai_rewrite":
            title = AIOperationLogService._short_text(result.get("rewritten_title") or "")
            return f"已生成优化稿：标题 {title}" if title else "已生成优化稿"

        if action_type == "apply_ai_rewrite":
            return result.get("msg") or "已应用 AI 优化稿"

        if action_type == "ai_preflight":
            pass_text = "是" if result.get("pass_preflight") else "否"
            return f"终检通过：{pass_text}，风险等级：{result.get('risk_level') or '-'}"

        if action_type == "ai_decision":
            decision_label = result.get("decision_label") or result.get("decision") or "-"
            return f"决策：{decision_label}"

        if action_type == "ai_workflow":
            workflow_status = result.get("workflow_status") or "-"
            overall_risk = result.get("overall_risk") or "-"
            return f"工作流：{workflow_status}，综合风险：{overall_risk}"

        return "操作成功"

    @staticmethod
    def _short_text(value: Any, max_length: int = 40) -> str:
        """生成适合列表展示的短文本。"""
        text = str(value or "").strip()
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
