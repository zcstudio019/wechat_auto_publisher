"""文章 AI 健康度分析服务。

该服务只读取现有文章、AI 操作日志与发布任务，不修改文章、不触发任何
Agent、不改变审核发布流程。
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from database import get_db, is_mysql


logger = logging.getLogger(__name__)


class ArticleHealthService:
    """根据 AI 操作记录与发布任务状态生成文章 AI 健康状态。"""

    @staticmethod
    def build_article_health(article_id: int) -> dict:
        """构建单篇文章 AI 健康度，返回适合页面直接展示的结构。"""
        try:
            article = ArticleHealthService._get_article(article_id)
            if not article:
                return ArticleHealthService._build_result(
                    score=0,
                    signals=["文章不存在"],
                    summary="未找到文章，无法生成 AI 健康状态",
                    need_manual_attention=True,
                    ai_activity_count=0,
                )

            logs = ArticleHealthService._list_ai_logs(article_id, limit=200)
            publish_tasks = ArticleHealthService._list_publish_tasks(article_id, limit=100)

            latest_review = ArticleHealthService._latest_result(logs, "ai_review")
            latest_preflight = ArticleHealthService._latest_result(logs, "ai_preflight")
            latest_workflow = ArticleHealthService._latest_result(logs, "ai_workflow")
            latest_publish_task = publish_tasks[0] if publish_tasks else None

            rewrite_count_24h = ArticleHealthService._count_logs_in_24h(logs, "ai_rewrite")
            workflow_count_24h = ArticleHealthService._count_logs_in_24h(logs, "ai_workflow")
            ai_activity_count_24h = ArticleHealthService._count_logs_in_24h(logs)
            has_failed_publish_task = any((task.get("status") == "failed") for task in publish_tasks)

            score = 100
            signals = []
            need_manual_attention = False

            # 最近 AI 审核高风险说明内容本身仍需人工重点复核。
            if latest_review.get("risk_level") == "high":
                score -= 30
                need_manual_attention = True
                signals.append("AI审核高风险")

            # 发布前终检未通过属于强信号，说明不建议直接进入草稿箱。
            if latest_preflight and latest_preflight.get("pass_preflight") is False:
                score -= 25
                need_manual_attention = True
                signals.append("AI终检未通过")

            # 最近一次发布任务失败，运营应优先排查配置或内容问题。
            if latest_publish_task and latest_publish_task.get("status") == "failed":
                score -= 20
                need_manual_attention = True
                signals.append("最近发布失败")

            # 工作流综合风险高，说明多个 Agent 聚合后仍不稳。
            if latest_workflow.get("overall_risk") == "high":
                score -= 20
                signals.append("工作流高风险")

            if rewrite_count_24h > 3:
                score -= 10
                signals.append("AI重写次数较多")

            if workflow_count_24h > 5:
                score -= 10
                signals.append("AI工作流运行频繁")

            if has_failed_publish_task:
                score -= 15
                signals.append("存在失败发布任务")

            score = max(0, min(100, score))
            risk_level = ArticleHealthService._risk_level(score)
            if risk_level == "high":
                need_manual_attention = True

            return ArticleHealthService._build_result(
                score=score,
                signals=ArticleHealthService._unique_signals(signals),
                summary=ArticleHealthService._build_summary(score, signals, latest_preflight, latest_workflow),
                need_manual_attention=need_manual_attention,
                ai_activity_count=ai_activity_count_24h,
            )
        except Exception as exc:
            # 健康度卡片是只读增强，异常时返回安全兜底，避免影响文章详情页。
            logger.warning("文章 AI 健康度计算失败：%s", exc)
            return ArticleHealthService._build_result(
                score=50,
                signals=["健康度计算异常"],
                summary="AI 健康度暂时无法完整计算，请稍后刷新重试",
                need_manual_attention=True,
                ai_activity_count=0,
            )

    @staticmethod
    def _get_article(article_id: int) -> dict | None:
        """读取文章基础信息，仅用于确认文章存在。"""
        conn = get_db()
        try:
            placeholder = "%s" if is_mysql() else "?"
            row = conn.execute(f"SELECT id, title, status FROM articles WHERE id={placeholder}", (article_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def _list_ai_logs(article_id: int, limit: int = 200) -> list[dict]:
        """读取文章最近 AI 操作日志，包含 result_json 供健康度解析。"""
        conn = get_db()
        try:
            safe_limit = max(1, min(int(limit or 200), 500))
            placeholder = "%s" if is_mysql() else "?"
            rows = conn.execute(
                f"""
                SELECT id, action_type, ok, result_json, created_at
                FROM ai_operation_logs
                WHERE article_id={placeholder}
                ORDER BY id DESC
                LIMIT {safe_limit}
                """,
                (article_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def _list_publish_tasks(article_id: int, limit: int = 100) -> list[dict]:
        """读取文章最近发布任务，判断是否存在失败发布风险。"""
        conn = get_db()
        try:
            safe_limit = max(1, min(int(limit or 100), 200))
            placeholder = "%s" if is_mysql() else "?"
            rows = conn.execute(
                f"""
                SELECT id, status, updated_at, created_at
                FROM publish_tasks
                WHERE article_id={placeholder}
                ORDER BY id DESC
                LIMIT {safe_limit}
                """,
                (article_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def _latest_result(logs: list[dict], action_type: str) -> dict:
        """获取某类 AI 操作的最近一次 result_json。"""
        for log in logs:
            if log.get("action_type") != action_type:
                continue
            return ArticleHealthService._parse_result_json(log.get("result_json"))
        return {}

    @staticmethod
    def _parse_result_json(result_json: Any) -> dict:
        """解析日志中的 result_json，异常时返回空 dict。"""
        if isinstance(result_json, dict):
            return result_json
        if not result_json:
            return {}
        try:
            parsed = json.loads(str(result_json))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _count_logs_in_24h(logs: list[dict], action_type: str | None = None) -> int:
        """统计最近 24 小时内的 AI 操作次数。"""
        threshold = datetime.now() - timedelta(hours=24)
        count = 0
        for log in logs:
            if action_type and log.get("action_type") != action_type:
                continue
            created_at = ArticleHealthService._parse_datetime(log.get("created_at"))
            if created_at and created_at >= threshold:
                count += 1
        return count

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """兼容 SQLite 字符串时间和 MySQL datetime 对象。"""
        if isinstance(value, datetime):
            return value
        if not value:
            return None
        text = str(value).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(text[:19], fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _risk_level(score: int) -> str:
        """根据分数映射风险等级。"""
        if score >= 80:
            return "low"
        if score >= 50:
            return "medium"
        return "high"

    @staticmethod
    def _status(score: int) -> str:
        """根据分数映射健康状态。"""
        if score >= 80:
            return "healthy"
        if score >= 50:
            return "warning"
        return "dangerous"

    @staticmethod
    def _activity_level(count_24h: int) -> str:
        """根据最近 24 小时 AI 操作次数映射活跃度。"""
        if count_24h <= 2:
            return "low"
        if count_24h <= 6:
            return "medium"
        return "high"

    @staticmethod
    def _build_summary(score: int, signals: list[str], latest_preflight: dict, latest_workflow: dict) -> str:
        """生成运营可读的一句话摘要。"""
        if signals:
            return "，".join(signals[:3]) + "，建议运营重点关注"
        if latest_preflight.get("pass_preflight") is True:
            return "最近 AI 终检通过，未发现明显高风险问题"
        if latest_workflow.get("workflow_status") == "completed":
            return "最近 AI 工作流运行正常，未发现明显高风险问题"
        if score >= 80:
            return "当前文章 AI 健康度良好，暂无明显异常信号"
        return "当前文章需要继续观察 AI 操作与发布状态"

    @staticmethod
    def _unique_signals(signals: list[str]) -> list[str]:
        """保持顺序去重，避免页面标签重复。"""
        unique = []
        for signal in signals:
            if signal not in unique:
                unique.append(signal)
        return unique

    @staticmethod
    def _build_result(
        score: int,
        signals: list[str],
        summary: str,
        need_manual_attention: bool,
        ai_activity_count: int,
    ) -> dict:
        """统一组装健康度返回结构。"""
        return {
            "score": score,
            "risk_level": ArticleHealthService._risk_level(score),
            "status": ArticleHealthService._status(score),
            "ai_activity_level": ArticleHealthService._activity_level(ai_activity_count),
            "need_manual_attention": bool(need_manual_attention),
            "summary": summary,
            "signals": signals,
        }
