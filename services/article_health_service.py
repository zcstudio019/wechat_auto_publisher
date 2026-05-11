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
    def build_health_trend(article_id: int) -> dict:
        """构建文章 AI 健康趋势，只读估算最近 AI 操作带来的分数变化。"""
        try:
            article = ArticleHealthService._get_article(article_id)
            if not article:
                return ArticleHealthService._build_trend_result(
                    recent_scores=[],
                    signals=["文章不存在"],
                    summary="未找到文章，无法生成 AI 健康趋势",
                )

            logs = ArticleHealthService._list_ai_logs(article_id, limit=20)
            publish_tasks = ArticleHealthService._list_publish_tasks(article_id, limit=20)
            recent_logs = list(reversed(logs[:5]))

            if not recent_logs:
                return ArticleHealthService._build_trend_result(
                    recent_scores=[],
                    signals=[],
                    summary="暂无 AI 操作记录，趋势仍需继续观察",
                )

            recent_scores = []
            for index in range(len(recent_logs)):
                # 每次用“截至当前操作”的日志片段估算阶段健康分。
                stage_logs = list(reversed(recent_logs[: index + 1]))
                recent_scores.append(ArticleHealthService._calculate_score(stage_logs, publish_tasks))

            signals = ArticleHealthService._build_trend_signals(recent_logs, publish_tasks)
            return ArticleHealthService._build_trend_result(
                recent_scores=recent_scores,
                signals=signals[:4],
                summary="",
            )
        except Exception as exc:
            logger.warning("文章 AI 健康趋势计算失败：%s", exc)
            return ArticleHealthService._build_trend_result(
                recent_scores=[],
                signals=["趋势计算异常"],
                summary="AI 健康趋势暂时无法完整计算，请稍后刷新重试",
            )

    @staticmethod
    def build_articles_health_overview(article_ids: list[int]) -> dict[int, dict]:
        """批量构建文章 AI 健康概览，供文章列表页轻量展示。"""
        safe_article_ids = []
        for article_id in article_ids or []:
            try:
                safe_id = int(article_id)
            except (TypeError, ValueError):
                continue
            if safe_id not in safe_article_ids:
                safe_article_ids.append(safe_id)

        if not safe_article_ids:
            return {}

        overview = {}
        for article_id in safe_article_ids:
            try:
                health = ArticleHealthService.build_article_health(article_id) or {}
                trend = ArticleHealthService.build_health_trend(article_id) or {}
                signals = list(health.get("signals") or []) + list(trend.get("signals") or [])

                overview[article_id] = {
                    "score": health.get("score", 0),
                    "risk_level": health.get("risk_level", "unknown"),
                    "status": health.get("status", "unknown"),
                    "need_manual_attention": bool(health.get("need_manual_attention", False)),
                    "trend_direction": trend.get("trend_direction", "stable"),
                    "score_change": trend.get("score_change", 0),
                    # 列表页只展示最关键的两个信号，避免表格被撑高。
                    "signals": ArticleHealthService._unique_signals(signals)[:2],
                }
            except Exception as exc:
                logger.warning("文章 AI 健康概览计算失败 article_id=%s：%s", article_id, exc)
                overview[article_id] = ArticleHealthService._fallback_overview()
        return overview

    @staticmethod
    def build_ai_risk_dashboard(
        risk_level: str | None = None,
        need_attention: bool = False,
        trend_direction: str | None = None,
        max_score: int | None = None,
    ) -> dict:
        """构建全局 AI 风险监控面板，只读聚合现有文章、AI 日志和发布任务。"""
        try:
            safe_filters = ArticleHealthService._normalize_dashboard_filters(
                risk_level=risk_level,
                need_attention=need_attention,
                trend_direction=trend_direction,
                max_score=max_score,
            )
            articles = ArticleHealthService._list_articles_for_dashboard()
            if not articles:
                return ArticleHealthService._empty_dashboard(safe_filters)

            health_items = []
            trend_summary = {"up_count": 0, "stable_count": 0, "down_count": 0}

            for article in articles:
                article_id = int(article.get("id") or 0)
                title = (article.get("title") or "").strip() or "未知文章"
                try:
                    health = ArticleHealthService.build_article_health(article_id) or {}
                    trend = ArticleHealthService.build_health_trend(article_id) or {}
                    item = {
                        "article_id": article_id,
                        "title": title,
                        "score": int(health.get("score", 0) or 0),
                        "risk_level": health.get("risk_level", "unknown"),
                        "status": health.get("status", "unknown"),
                        "trend_direction": trend.get("trend_direction", "stable"),
                        "need_manual_attention": bool(health.get("need_manual_attention", False)),
                    }
                except Exception as exc:
                    logger.warning("Dashboard 单篇文章健康分析失败 article_id=%s：%s", article_id, exc)
                    item = {
                        "article_id": article_id,
                        "title": title,
                        "score": 0,
                        "risk_level": "unknown",
                        "status": "unknown",
                        "trend_direction": "stable",
                        "need_manual_attention": False,
                    }
                health_items.append(item)

                trend_direction = item.get("trend_direction", "stable")
                if trend_direction == "up":
                    trend_summary["up_count"] += 1
                elif trend_direction == "down":
                    trend_summary["down_count"] += 1
                else:
                    trend_summary["stable_count"] += 1

            total_articles = len(health_items)
            high_risk_articles = sum(1 for item in health_items if item.get("risk_level") == "high")
            need_attention_articles = sum(1 for item in health_items if item.get("need_manual_attention"))
            avg_health_score = int(round(sum(item.get("score", 0) for item in health_items) / total_articles)) if total_articles else 0

            top_risk_articles = sorted(
                health_items,
                key=lambda item: (
                    ArticleHealthService._risk_sort_weight(item.get("risk_level", "unknown")),
                    item.get("score", 0),
                    item.get("article_id", 0),
                ),
            )[:10]
            filtered_articles = ArticleHealthService._filter_dashboard_articles(health_items, safe_filters)

            return {
                "summary": {
                    "total_articles": total_articles,
                    "high_risk_articles": high_risk_articles,
                    "need_attention_articles": need_attention_articles,
                    "avg_health_score": avg_health_score,
                },
                "top_risk_articles": top_risk_articles,
                "top_active_articles": ArticleHealthService._build_top_active_articles(articles),
                "recent_fail_articles": ArticleHealthService._build_recent_fail_articles(articles),
                "trend_summary": trend_summary,
                "filters": safe_filters,
                "filtered_articles": filtered_articles,
            }
        except Exception as exc:
            logger.warning("AI 风险监控面板构建失败：%s", exc)
            return ArticleHealthService._empty_dashboard(
                ArticleHealthService._normalize_dashboard_filters(
                    risk_level=risk_level,
                    need_attention=need_attention,
                    trend_direction=trend_direction,
                    max_score=max_score,
                )
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
    def _list_articles_for_dashboard() -> list[dict]:
        """读取 Dashboard 需要的文章基础信息。"""
        conn = get_db()
        try:
            rows = conn.execute("SELECT id, title FROM articles ORDER BY id DESC").fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def _build_top_active_articles(articles: list[dict]) -> list[dict]:
        """统计最近 24 小时 AI 操作最活跃的文章 TOP10。"""
        title_map = ArticleHealthService._build_title_map(articles)
        threshold = datetime.now() - timedelta(hours=24)
        counter: dict[int, int] = {}
        conn = get_db()
        try:
            rows = conn.execute("SELECT article_id, created_at FROM ai_operation_logs").fetchall()
        finally:
            conn.close()

        for row in rows:
            row_dict = dict(row)
            created_at = ArticleHealthService._parse_datetime(row_dict.get("created_at"))
            if not created_at or created_at < threshold:
                continue
            try:
                article_id = int(row_dict.get("article_id") or 0)
            except (TypeError, ValueError):
                continue
            if not article_id:
                continue
            counter[article_id] = counter.get(article_id, 0) + 1

        return [
            {
                "article_id": article_id,
                "title": title_map.get(article_id, "未知文章"),
                "ai_operation_count": count,
            }
            for article_id, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:10]
        ]

    @staticmethod
    def _build_recent_fail_articles(articles: list[dict]) -> list[dict]:
        """统计最近发布失败次数最多的文章 TOP10。"""
        title_map = ArticleHealthService._build_title_map(articles)
        counter: dict[int, int] = {}
        conn = get_db()
        try:
            rows = conn.execute("SELECT article_id, status FROM publish_tasks WHERE status='failed'").fetchall()
        finally:
            conn.close()

        for row in rows:
            row_dict = dict(row)
            try:
                article_id = int(row_dict.get("article_id") or 0)
            except (TypeError, ValueError):
                continue
            if not article_id:
                continue
            counter[article_id] = counter.get(article_id, 0) + 1

        return [
            {
                "article_id": article_id,
                "title": title_map.get(article_id, "未知文章"),
                "failed_count": count,
            }
            for article_id, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:10]
        ]

    @staticmethod
    def _build_title_map(articles: list[dict]) -> dict[int, str]:
        """生成 article_id 到标题的映射，标题缺失时兜底为未知文章。"""
        title_map = {}
        for article in articles:
            try:
                article_id = int(article.get("id") or 0)
            except (TypeError, ValueError):
                continue
            if article_id:
                title_map[article_id] = (article.get("title") or "").strip() or "未知文章"
        return title_map

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
    def _calculate_score(logs: list[dict], publish_tasks: list[dict]) -> int:
        """复用健康度规则，根据指定日志片段估算阶段分数。"""
        latest_review = ArticleHealthService._latest_result(logs, "ai_review")
        latest_preflight = ArticleHealthService._latest_result(logs, "ai_preflight")
        latest_workflow = ArticleHealthService._latest_result(logs, "ai_workflow")
        latest_publish_task = publish_tasks[0] if publish_tasks else None

        score = 100
        if latest_review.get("risk_level") == "high":
            score -= 30
        if latest_preflight and latest_preflight.get("pass_preflight") is False:
            score -= 25
        if latest_publish_task and latest_publish_task.get("status") == "failed":
            score -= 20
        if latest_workflow.get("overall_risk") == "high":
            score -= 20
        if ArticleHealthService._count_logs_in_24h(logs, "ai_rewrite") > 3:
            score -= 10
        if ArticleHealthService._count_logs_in_24h(logs, "ai_workflow") > 5:
            score -= 10
        if any((task.get("status") == "failed") for task in publish_tasks):
            score -= 15
        return max(0, min(100, score))

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
    def _trend_direction(score_change: int) -> str:
        """根据分数变化判断趋势方向。"""
        if score_change >= 15:
            return "up"
        if score_change <= -15:
            return "down"
        return "stable"

    @staticmethod
    def _trend_level(trend_direction: str) -> str:
        """根据趋势方向映射趋势级别。"""
        if trend_direction == "up":
            return "good"
        if trend_direction == "down":
            return "danger"
        return "normal"

    @staticmethod
    def _trend_summary(trend_direction: str, custom_summary: str = "") -> str:
        """生成趋势摘要。"""
        if custom_summary:
            return custom_summary
        if trend_direction == "up":
            return "最近 AI 优化后文章健康度持续提升"
        if trend_direction == "down":
            return "最近文章风险正在升高，建议人工关注"
        return "最近文章 AI 状态整体稳定"

    @staticmethod
    def _build_trend_signals(recent_logs: list[dict], publish_tasks: list[dict]) -> list[str]:
        """根据最近日志前后片段生成趋势信号。"""
        if len(recent_logs) < 2:
            return []

        split_index = max(1, len(recent_logs) // 2)
        earlier_logs = recent_logs[:split_index]
        later_logs = recent_logs[split_index:]

        signals = []
        if ArticleHealthService._count_action(later_logs, "ai_rewrite") < ArticleHealthService._count_action(earlier_logs, "ai_rewrite"):
            signals.append("最近 AI 优化次数减少")

        if ArticleHealthService._has_workflow_high_risk(earlier_logs) and not ArticleHealthService._has_workflow_high_risk(later_logs):
            signals.append("最近工作流高风险已消失")

        if ArticleHealthService._count_preflight_pass(later_logs) > ArticleHealthService._count_preflight_pass(earlier_logs):
            signals.append("最近终检通过率提升")

        if ArticleHealthService._count_review_high_risk(later_logs) > ArticleHealthService._count_review_high_risk(earlier_logs):
            signals.append("最近审核高风险增加")

        if ArticleHealthService._failed_publish_task_reduced(publish_tasks):
            signals.append("最近发布失败减少")

        return ArticleHealthService._unique_signals(signals)[:4]

    @staticmethod
    def _count_action(logs: list[dict], action_type: str) -> int:
        """统计指定动作次数。"""
        return sum(1 for log in logs if log.get("action_type") == action_type)

    @staticmethod
    def _has_workflow_high_risk(logs: list[dict]) -> bool:
        """判断日志片段中是否出现过工作流高风险。"""
        for log in logs:
            if log.get("action_type") != "ai_workflow":
                continue
            if ArticleHealthService._parse_result_json(log.get("result_json")).get("overall_risk") == "high":
                return True
        return False

    @staticmethod
    def _count_preflight_pass(logs: list[dict]) -> int:
        """统计终检通过次数。"""
        count = 0
        for log in logs:
            if log.get("action_type") != "ai_preflight":
                continue
            if ArticleHealthService._parse_result_json(log.get("result_json")).get("pass_preflight") is True:
                count += 1
        return count

    @staticmethod
    def _count_review_high_risk(logs: list[dict]) -> int:
        """统计审核高风险次数。"""
        count = 0
        for log in logs:
            if log.get("action_type") != "ai_review":
                continue
            if ArticleHealthService._parse_result_json(log.get("result_json")).get("risk_level") == "high":
                count += 1
        return count

    @staticmethod
    def _failed_publish_task_reduced(publish_tasks: list[dict]) -> bool:
        """基于最近发布任务粗略判断失败是否减少。"""
        if len(publish_tasks) < 2:
            return False
        chronological_tasks = list(reversed(publish_tasks[:6]))
        split_index = max(1, len(chronological_tasks) // 2)
        earlier_failed = sum(1 for task in chronological_tasks[:split_index] if task.get("status") == "failed")
        later_failed = sum(1 for task in chronological_tasks[split_index:] if task.get("status") == "failed")
        return later_failed < earlier_failed

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

    @staticmethod
    def _build_trend_result(recent_scores: list[int], signals: list[str], summary: str = "") -> dict:
        """统一组装健康趋势返回结构。"""
        if len(recent_scores) >= 2:
            score_change = recent_scores[-1] - recent_scores[0]
        else:
            score_change = 0

        trend_direction = ArticleHealthService._trend_direction(score_change)
        return {
            "trend_direction": trend_direction,
            "trend_level": ArticleHealthService._trend_level(trend_direction),
            "summary": ArticleHealthService._trend_summary(trend_direction, summary),
            "signals": signals[:4],
            "recent_scores": recent_scores,
            "score_change": score_change,
        }

    @staticmethod
    def _fallback_overview() -> dict:
        """单篇文章健康概览失败时的安全兜底结构。"""
        return {
            "score": 0,
            "risk_level": "unknown",
            "status": "unknown",
            "need_manual_attention": False,
            "trend_direction": "stable",
            "score_change": 0,
            "signals": ["健康分析失败"],
        }

    @staticmethod
    def _risk_sort_weight(risk_level: str) -> int:
        """Dashboard 高风险文章排序权重，高风险优先。"""
        return {
            "high": 0,
            "medium": 1,
            "low": 2,
            "unknown": 3,
        }.get(risk_level or "unknown", 3)

    @staticmethod
    def _normalize_dashboard_filters(
        risk_level: str | None = None,
        need_attention: bool = False,
        trend_direction: str | None = None,
        max_score: int | None = None,
    ) -> dict:
        """统一清洗 Dashboard 筛选条件，避免非法参数影响页面。"""
        safe_risk_level = (risk_level or "").strip()
        if safe_risk_level not in ("", "low", "medium", "high", "unknown"):
            safe_risk_level = ""

        safe_trend_direction = (trend_direction or "").strip()
        if safe_trend_direction not in ("", "up", "stable", "down"):
            safe_trend_direction = ""

        safe_max_score = None
        try:
            if max_score is not None and str(max_score).strip() != "":
                parsed_score = int(max_score)
                if 0 <= parsed_score <= 100:
                    safe_max_score = parsed_score
        except (TypeError, ValueError):
            safe_max_score = None

        return {
            "risk_level": safe_risk_level,
            "need_attention": bool(need_attention),
            "trend_direction": safe_trend_direction,
            "max_score": safe_max_score,
        }

    @staticmethod
    def _filter_dashboard_articles(health_items: list[dict], filters: dict) -> list[dict]:
        """按 Dashboard 筛选条件过滤全部文章健康结果。"""
        filtered = []
        for item in health_items:
            if filters.get("risk_level") and item.get("risk_level") != filters["risk_level"]:
                continue
            if filters.get("need_attention") and not item.get("need_manual_attention"):
                continue
            if filters.get("trend_direction") and item.get("trend_direction") != filters["trend_direction"]:
                continue
            if filters.get("max_score") is not None and item.get("score", 0) > filters["max_score"]:
                continue
            filtered.append(item)

        return sorted(
            filtered,
            key=lambda item: (
                ArticleHealthService._risk_sort_weight(item.get("risk_level", "unknown")),
                item.get("score", 0),
                item.get("article_id", 0),
            ),
        )[:100]

    @staticmethod
    def _dashboard_filters_active(filters: dict) -> bool:
        """判断 Dashboard 当前是否存在任意筛选条件。"""
        return bool(
            filters.get("risk_level")
            or filters.get("need_attention")
            or filters.get("trend_direction")
            or filters.get("max_score") is not None
        )

    @staticmethod
    def _empty_dashboard(filters: dict | None = None) -> dict:
        """Dashboard 空数据或异常时的稳定返回结构。"""
        safe_filters = filters or ArticleHealthService._normalize_dashboard_filters()
        return {
            "summary": {
                "total_articles": 0,
                "high_risk_articles": 0,
                "need_attention_articles": 0,
                "avg_health_score": 0,
            },
            "top_risk_articles": [],
            "top_active_articles": [],
            "recent_fail_articles": [],
            "trend_summary": {
                "up_count": 0,
                "stable_count": 0,
                "down_count": 0,
            },
            "filters": safe_filters,
            "filtered_articles": [],
        }
