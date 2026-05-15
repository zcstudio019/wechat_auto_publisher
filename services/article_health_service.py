"""文章 AI 健康度分析服务。

该服务只读取现有文章、AI 操作日志与发布任务，不修改文章、不触发任何
Agent、不改变审核发布流程。
"""
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

from database import get_db, is_mysql


logger = logging.getLogger(__name__)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI_DASHBOARD_SNAPSHOT_FILE_PATH = os.path.join(PROJECT_ROOT, "data", "ai_dashboard_snapshot.json")
AI_OPS_SCORE_HISTORY_FILE_PATH = os.path.join(PROJECT_ROOT, "data", "ai_ops_score_history.json")
AI_OPS_DUTY_HISTORY_FILE_PATH = os.path.join(PROJECT_ROOT, "data", "ai_ops_duty_history.json")


class ArticleHealthService:
    """根据 AI 操作记录与发布任务状态生成文章 AI 健康状态。"""

    AI_STATUS_LABELS = {
        "recovery": "恢复观察",
        "stable": "稳定",
        "excellent": "优秀",
        "good": "良好",
        "warning": "警告",
        "danger": "高风险",
        "volatile": "波动",
        "highly_volatile": "高度波动",
        "healthy": "健康",
        "very_stable": "非常稳定",
        "normal": "正常",
        "focus": "重点关注",
        "high_alert": "高危值班",
        "low": "低风险",
        "medium": "中风险",
        "high": "高风险",
        "critical": "紧急",
        "strong": "较强",
        "weak": "较弱",
        "unstable": "不稳定",
        "unknown": "未知",
        "risky": "有风险",
        "success": "成功",
        "info": "信息",
        "up": "上升",
        "down": "下降",
    }

    @staticmethod
    def _ai_status_label(value: Any) -> str:
        """将 AI Dashboard 内部英文状态枚举转换为中文展示文案。"""
        if value is None:
            return ""
        text = str(value).strip()
        return ArticleHealthService.AI_STATUS_LABELS.get(text, text)

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

            dashboard = {
                "summary": {
                    "total_articles": total_articles,
                    "high_risk_articles": high_risk_articles,
                    "need_attention_articles": need_attention_articles,
                    "avg_health_score": avg_health_score,
                },
                "top_risk_articles": top_risk_articles,
                "top_active_articles": ArticleHealthService._build_top_active_articles(articles),
                "recent_fail_articles": ArticleHealthService._build_recent_fail_articles(articles),
                "persistent_risk_articles": ArticleHealthService.build_persistent_risk_articles(limit=10),
                "recovered_articles": ArticleHealthService.build_recovered_articles(limit=10),
                "trend_summary": trend_summary,
                "filters": safe_filters,
                "filtered_articles": filtered_articles,
            }
            dashboard["ai_ops_priority_queue"] = ArticleHealthService.build_ai_ops_priority_queue(dashboard)
            dashboard["ai_ops_score"] = ArticleHealthService.build_ai_ops_score(dashboard)
            dashboard["ai_ops_health_index"] = ArticleHealthService.build_ai_ops_health_index(dashboard)
            dashboard["ai_ops_score_trend"] = ArticleHealthService.build_ai_ops_score_trend(dashboard)
            dashboard["ai_ops_suggestions"] = ArticleHealthService.build_ai_ops_suggestions(dashboard)
            dashboard["ai_ops_incident_feed"] = ArticleHealthService.build_ai_ops_incident_feed(dashboard)
            dashboard["daily_ai_ops_summary"] = ArticleHealthService.build_daily_ai_ops_summary(dashboard)
            dashboard["ai_ops_conclusion"] = ArticleHealthService.build_ai_ops_conclusion(dashboard)
            dashboard["ai_ops_duty_mode"] = ArticleHealthService.build_ai_ops_duty_mode(dashboard)
            dashboard["ai_ops_duty_history_summary"] = ArticleHealthService.build_ai_ops_duty_history_summary()
            # 稳定性指数依赖评分趋势、异常播报和值班模式，必须在这些只读指标生成后再计算。
            dashboard["ai_ops_stability_index"] = ArticleHealthService.build_ai_ops_stability_index(dashboard)
            dashboard["ai_ops_volatility_index"] = ArticleHealthService.build_ai_ops_volatility_index(dashboard)
            dashboard["ai_ops_recovery_index"] = ArticleHealthService.build_ai_ops_recovery_index(dashboard)
            dashboard["ai_ops_playbooks"] = ArticleHealthService.build_ai_ops_playbooks(dashboard)
            dashboard["ai_root_cause_analysis"] = ArticleHealthService.build_ai_root_cause_analysis(dashboard)
            dashboard["template_ops_analysis"] = ArticleHealthService.build_template_ops_analysis(dashboard)
            dashboard["prompt_ops_analysis"] = ArticleHealthService.build_prompt_ops_analysis(dashboard)
            dashboard["ai_ops_timeline"] = ArticleHealthService.build_ai_ops_timeline(dashboard)
            dashboard["ai_ops_report_text"] = ArticleHealthService.build_ai_ops_report_text(dashboard)
            return dashboard
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
    def build_persistent_risk_articles(limit: int = 10) -> list[dict]:
        """识别连续异常文章，用于 Dashboard 展示长期危险对象。"""
        try:
            safe_limit = max(1, min(int(limit or 10), 20))
        except (TypeError, ValueError):
            safe_limit = 10
        try:
            articles = ArticleHealthService._list_articles_for_dashboard()
            persistent_items = []

            for article in articles:
                try:
                    article_id = int(article.get("id") or 0)
                except (TypeError, ValueError):
                    continue
                if not article_id:
                    continue

                try:
                    title = (article.get("title") or "").strip() or "未知文章"
                    logs = ArticleHealthService._list_ai_logs(article_id, limit=10)
                    publish_tasks = ArticleHealthService._list_publish_tasks(article_id, limit=10)

                    high_risk_count = ArticleHealthService._count_recent_high_risk_logs(logs)
                    preflight_fail_count = ArticleHealthService._count_recent_preflight_failures(logs)
                    publish_fail_count = sum(1 for task in publish_tasks if task.get("status") == "failed")

                    risk_tags = []
                    if high_risk_count >= 3:
                        risk_tags.append("连续高风险")
                    if preflight_fail_count >= 2:
                        risk_tags.append("连续终检失败")
                    if publish_fail_count >= 2:
                        risk_tags.append("连续发布失败")
                    if not risk_tags:
                        continue

                    health = ArticleHealthService.build_article_health(article_id) or {}
                    persistent_items.append({
                        "article_id": article_id,
                        "title": title,
                        "risk_level": health.get("risk_level", "unknown"),
                        "health_score": int(health.get("score", 0) or 0),
                        "high_risk_count": high_risk_count,
                        "preflight_fail_count": preflight_fail_count,
                        "publish_fail_count": publish_fail_count,
                        "need_manual_attention": bool(health.get("need_manual_attention", False)) or bool(risk_tags),
                        "risk_tags": risk_tags,
                    })
                except Exception as exc:
                    logger.warning("连续异常文章分析失败 article_id=%s：%s", article_id, exc)
                    continue

            return sorted(
                persistent_items,
                key=lambda item: (
                    -len(item.get("risk_tags", [])),
                    item.get("health_score", 0),
                    item.get("article_id", 0),
                ),
            )[:safe_limit]
        except Exception as exc:
            logger.warning("连续异常文章列表构建失败：%s", exc)
            return []

    @staticmethod
    def build_recovered_articles(limit: int = 10) -> list[dict]:
        """识别已从风险状态恢复或健康分明显改善的文章。"""
        try:
            safe_limit = max(1, min(int(limit or 10), 20))
        except (TypeError, ValueError):
            safe_limit = 10

        try:
            articles = ArticleHealthService._list_articles_for_dashboard()
            recovered_items = []

            for article in articles:
                try:
                    article_id = int(article.get("id") or 0)
                except (TypeError, ValueError):
                    continue
                if not article_id:
                    continue

                try:
                    title = (article.get("title") or "").strip() or "未知文章"
                    logs = ArticleHealthService._list_ai_logs(article_id, limit=10)
                    publish_tasks = ArticleHealthService._list_publish_tasks(article_id, limit=10)
                    health = ArticleHealthService.build_article_health(article_id) or {}
                    trend = ArticleHealthService.build_health_trend(article_id) or {}

                    current_score = int(health.get("score", 0) or 0)
                    score_change = int(trend.get("score_change", 0) or 0)
                    previous_score = max(0, min(100, current_score - score_change))

                    high_risk_count = ArticleHealthService._count_recent_high_risk_logs(logs)
                    preflight_fail_count = ArticleHealthService._count_recent_preflight_failures(logs)
                    historical_preflight_fail_count = ArticleHealthService._count_recent_preflight_failures_before_latest_pass(logs)
                    publish_fail_count = sum(1 for task in publish_tasks if task.get("status") == "failed")
                    latest_preflight = ArticleHealthService._latest_result(logs, "ai_preflight")
                    latest_publish_task = publish_tasks[0] if publish_tasks else {}

                    recovered_tags = []
                    if high_risk_count >= 3 and health.get("risk_level") != "high":
                        recovered_tags.append("高风险已恢复")
                    if historical_preflight_fail_count >= 2 and latest_preflight.get("pass_preflight") is True:
                        recovered_tags.append("终检已恢复")
                    if publish_fail_count >= 2 and latest_publish_task.get("status") == "success":
                        recovered_tags.append("发布失败已恢复")

                    if not recovered_tags and score_change < 20:
                        continue

                    recovered_items.append({
                        "article_id": article_id,
                        "title": title,
                        "current_score": current_score,
                        "previous_score": previous_score,
                        "score_change": score_change,
                        "recovered_tags": recovered_tags,
                        "trend_direction": trend.get("trend_direction", "stable"),
                    })
                except Exception as exc:
                    logger.warning("风险恢复文章分析失败 article_id=%s：%s", article_id, exc)
                    continue

            return sorted(
                recovered_items,
                key=lambda item: (
                    -item.get("score_change", 0),
                    -len(item.get("recovered_tags", [])),
                    item.get("article_id", 0),
                ),
            )[:safe_limit]
        except Exception as exc:
            logger.warning("风险恢复文章列表构建失败：%s", exc)
            return []

    @staticmethod
    def build_ai_ops_priority_queue(dashboard: dict, limit: int = 10) -> list[dict]:
        """根据 Dashboard 当前状态生成 AI 运营优先处理队列，只做只读排序。"""
        try:
            safe_limit = max(1, min(int(limit or 10), 20))
        except (TypeError, ValueError):
            safe_limit = 10

        if not dashboard:
            return []

        candidates: dict[int, dict] = {}

        def ensure_candidate(article_id: int, title: str = "") -> dict | None:
            """统一创建候选文章，避免多来源重复计算。"""
            try:
                safe_article_id = int(article_id or 0)
            except (TypeError, ValueError):
                return None
            if not safe_article_id:
                return None
            if safe_article_id not in candidates:
                candidates[safe_article_id] = {
                    "article_id": safe_article_id,
                    "title": (title or "").strip() or "未知文章",
                    "priority_score": 0,
                    "health_score": 100,
                    "risk_level": "unknown",
                    "need_manual_attention": False,
                    "trend_direction": "stable",
                    "reasons": [],
                }
            elif title and candidates[safe_article_id].get("title") == "未知文章":
                candidates[safe_article_id]["title"] = title
            return candidates[safe_article_id]

        def add_reason(candidate: dict, reason: str) -> None:
            """追加去重后的处理原因，页面展示更清晰。"""
            if reason and reason not in candidate["reasons"]:
                candidate["reasons"].append(reason)

        for item in dashboard.get("top_risk_articles") or []:
            candidate = ensure_candidate(item.get("article_id"), item.get("title"))
            if not candidate:
                continue
            health_score = ArticleHealthService._safe_int(item.get("score"))
            candidate["health_score"] = health_score
            candidate["risk_level"] = item.get("risk_level", "unknown") or "unknown"
            candidate["need_manual_attention"] = bool(item.get("need_manual_attention"))
            candidate["trend_direction"] = item.get("trend_direction", "stable") or "stable"

            if candidate["risk_level"] == "high":
                candidate["priority_score"] += 30
                add_reason(candidate, "高风险文章")
            if candidate["need_manual_attention"]:
                candidate["priority_score"] += 15
                add_reason(candidate, "需人工关注")
            if health_score < 60:
                candidate["priority_score"] += 60 - health_score
                add_reason(candidate, "健康分过低")
            if candidate["trend_direction"] == "down":
                candidate["priority_score"] += 10
                add_reason(candidate, "趋势下降")

        for item in dashboard.get("persistent_risk_articles") or []:
            candidate = ensure_candidate(item.get("article_id"), item.get("title"))
            if not candidate:
                continue
            health_score = ArticleHealthService._safe_int(item.get("health_score"))
            candidate["health_score"] = min(candidate.get("health_score", 100), health_score)
            candidate["risk_level"] = item.get("risk_level") or candidate.get("risk_level", "unknown")
            candidate["need_manual_attention"] = bool(item.get("need_manual_attention")) or candidate.get("need_manual_attention", False)
            for tag in item.get("risk_tags") or []:
                candidate["priority_score"] += 20
                add_reason(candidate, str(tag))

        for item in dashboard.get("recent_fail_articles") or []:
            candidate = ensure_candidate(item.get("article_id"), item.get("title"))
            if not candidate:
                continue
            candidate["priority_score"] += 15
            add_reason(candidate, "存在发布失败")

        for item in dashboard.get("recovered_articles") or []:
            candidate = ensure_candidate(item.get("article_id"), item.get("title"))
            if not candidate:
                continue
            candidate["priority_score"] -= 15
            candidate["health_score"] = ArticleHealthService._safe_int(item.get("current_score"))
            candidate["trend_direction"] = item.get("trend_direction", candidate.get("trend_direction", "stable")) or "stable"

        priority_items = []
        for candidate in candidates.values():
            priority_score = max(0, ArticleHealthService._safe_int(candidate.get("priority_score")))
            if priority_score <= 0:
                continue
            if priority_score >= 80:
                priority_level = "critical"
            elif priority_score >= 60:
                priority_level = "high"
            elif priority_score >= 40:
                priority_level = "medium"
            else:
                priority_level = "low"

            priority_items.append({
                "article_id": candidate["article_id"],
                "title": candidate.get("title") or "未知文章",
                "priority_score": priority_score,
                "priority_level": priority_level,
                "reasons": candidate.get("reasons") or ["需要关注"],
                "health_score": max(0, min(100, ArticleHealthService._safe_int(candidate.get("health_score")))),
                "risk_level": candidate.get("risk_level", "unknown"),
                "need_manual_attention": bool(candidate.get("need_manual_attention")),
            })

        return sorted(
            priority_items,
            key=lambda item: (
                -item.get("priority_score", 0),
                item.get("health_score", 100),
                item.get("article_id", 0),
            ),
        )[:safe_limit]

    @staticmethod
    def build_ai_ops_playbooks(dashboard: dict, limit: int = 10) -> list[dict]:
        """生成 AI 运营处置建议中心，只读分析，不执行任何动作。"""
        if not dashboard:
            return []

        try:
            safe_limit = max(1, min(int(limit or 10), 10))
        except (TypeError, ValueError):
            safe_limit = 10

        try:
            persistent_items = list((dashboard or {}).get("persistent_risk_articles") or [])
            recovered_items = list((dashboard or {}).get("recovered_articles") or [])
            volatility_index = (dashboard or {}).get("ai_ops_volatility_index") or {}
            playbooks: list[dict] = []

            def has_tag(item: dict, keyword: str) -> bool:
                tags = [str(tag or "") for tag in item.get("risk_tags") or []]
                return any(keyword in tag for tag in tags)

            def related_by_tag(keyword: str) -> list[dict]:
                related = []
                for item in persistent_items:
                    if has_tag(item, keyword):
                        related.append({
                            "article_id": item.get("article_id"),
                            "title": item.get("title") or "未知文章",
                            "health_score": item.get("health_score"),
                            "risk_level": item.get("risk_level"),
                        })
                return related

            def append_playbook(
                playbook_type: str,
                level: str,
                title: str,
                summary: str,
                root_causes: list[str],
                recommended_actions: list[str],
                recommended_checks: list[str],
                priority: str,
                should_manual_review: bool,
                should_pause_publish: bool,
                related_articles: list[dict],
            ) -> None:
                safe_related_articles = related_articles or []
                playbooks.append({
                    "type": playbook_type,
                    "level": level,
                    "title": title,
                    "summary": summary,
                    "root_causes": root_causes,
                    "recommended_actions": recommended_actions,
                    "recommended_checks": recommended_checks,
                    "priority": priority,
                    "should_manual_review": bool(should_manual_review),
                    "should_pause_publish": bool(should_pause_publish),
                    "related_articles": safe_related_articles,
                    "actions": ArticleHealthService._build_playbook_actions(safe_related_articles),
                })

            preflight_articles = related_by_tag("连续终检失败")
            if preflight_articles:
                append_playbook(
                    "continuous_preflight_failure",
                    "danger",
                    "连续终检失败",
                    "多篇文章连续发布前终检未通过，建议优先排查正文 HTML 与 CTA 结构。",
                    ["CTA 结构异常", "markdown 转 html 异常", "HTML 结构异常", "内容格式异常"],
                    ["重新执行终检", "检查 CTA 卡片", "检查 HTML", "人工检查正文"],
                    ["确认正文是否包含 form/input/script/style", "确认 CTA 是否后置且结构完整", "检查微信兼容 HTML 是否为空或过短"],
                    "critical",
                    True,
                    True,
                    preflight_articles,
                )

            publish_articles = related_by_tag("连续发布失败")
            if publish_articles:
                append_playbook(
                    "continuous_publish_failure",
                    "danger",
                    "连续发布失败",
                    "存在文章连续推送失败，建议优先排查微信侧配置、素材上传与网络链路。",
                    ["微信 token", "media 上传", "封面图", "微信 API", "网络"],
                    ["检查微信配置", "检查封面图", "检查 media_id", "人工重新发布"],
                    ["确认 access_token 是否有效", "确认 thumb_media_id 是否存在", "查看 publish_tasks 失败原因", "检查服务器到微信 API 网络"],
                    "critical",
                    True,
                    True,
                    publish_articles,
                )

            high_risk_articles = related_by_tag("连续高风险")
            if high_risk_articles:
                append_playbook(
                    "continuous_high_risk",
                    "warning",
                    "连续高风险",
                    "部分文章连续被判为高风险，建议复核内容质量、Prompt 与模板输入。",
                    ["AI 内容质量下降", "Prompt 不稳定", "模板质量下降"],
                    ["人工复核", "重新生成", "检查模板", "检查 Prompt"],
                    ["检查是否出现违规承诺", "检查标题是否关键词堆砌", "复核 AI 审核与终检结果"],
                    "high",
                    True,
                    False,
                    high_risk_articles,
                )

            volatility_level = (
                volatility_index.get("level")
                or volatility_index.get("volatility_level")
                or ""
            )
            if volatility_level == "highly_volatile":
                append_playbook(
                    "high_volatility",
                    "warning",
                    "AI 波动过高",
                    "当前 AI 运营波动指数较高，建议进入重点关注节奏，避免批量风险扩散。",
                    ["评分变化较大", "值班模式切换频繁", "异常播报增多"],
                    ["进入 focus 值班", "暂停批量发布", "优先人工审核"],
                    ["查看 AI 运营评分趋势", "查看连续异常文章", "复核最近发布失败文章"],
                    "high",
                    True,
                    True,
                    list((dashboard or {}).get("ai_ops_priority_queue") or [])[:10],
                )

            if recovered_items and len(recovered_items) >= len(persistent_items):
                append_playbook(
                    "good_recovery",
                    "success",
                    "AI 恢复良好",
                    "恢复文章数量已覆盖当前连续异常文章，建议复盘有效处置路径并保持节奏。",
                    ["前期优化策略有效", "终检或发布链路逐步恢复", "人工复核节奏有效"],
                    ["复盘恢复文章", "沉淀有效 Prompt", "继续保持终检节奏"],
                    ["对比恢复前后健康分", "记录有效修改动作", "观察是否再次进入连续异常"],
                    "low",
                    False,
                    False,
                    recovered_items[:10],
                )

            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            level_order = {"danger": 0, "warning": 1, "success": 2}
            return sorted(
                playbooks,
                key=lambda item: (
                    priority_order.get(item.get("priority"), 99),
                    -len(item.get("related_articles") or []),
                    level_order.get(item.get("level"), 99),
                    item.get("title") or "",
                ),
            )[:safe_limit]
        except Exception as exc:
            logger.warning("AI 运营处置建议生成失败：%s", exc)
            return []

    @staticmethod
    def _build_playbook_actions(related_articles: list[dict]) -> list[dict]:
        """为 Playbook 关联文章生成安全动作入口，不包含任何危险动作。"""
        actions: list[dict] = []
        for article in list(related_articles or [])[:3]:
            try:
                article_id = int((article or {}).get("article_id") or 0)
            except (TypeError, ValueError):
                continue
            if article_id <= 0:
                continue

            actions.extend([
                {
                    "action_type": "open_article",
                    "label": "查看文章",
                    "method": "GET",
                    "url": f"/article/{article_id}",
                    "article_id": article_id,
                    "confirm_text": "",
                },
                {
                    "action_type": "rerun_preflight",
                    "label": "重新终检",
                    "method": "POST",
                    "url": "/ai-dashboard/playbook-action",
                    "article_id": article_id,
                    "confirm_text": "确认重新执行该文章的 AI 发布前终检？",
                },
                {
                    "action_type": "rerun_decision",
                    "label": "重新决策",
                    "method": "POST",
                    "url": "/ai-dashboard/playbook-action",
                    "article_id": article_id,
                    "confirm_text": "确认重新执行该文章的 AI 运营决策建议？",
                },
            ])
        return actions

    @staticmethod
    def build_ai_root_cause_analysis(dashboard: dict) -> dict:
        """构建 AI 根因分析中心，只读聚合风险来源，不执行任何动作。"""
        empty_result = {
            "root_causes": [],
            "top_templates": [],
            "top_failure_patterns": [],
            "summary": "当前暂无明显集中性根因，建议保持常规巡检。",
            "recommended_actions": [],
        }
        if not dashboard:
            return empty_result

        try:
            summary = (dashboard or {}).get("summary") or {}
            persistent_items = list((dashboard or {}).get("persistent_risk_articles") or [])
            recent_fail_items = list((dashboard or {}).get("recent_fail_articles") or [])
            score_trend = (dashboard or {}).get("ai_ops_score_trend") or {}
            volatility = (dashboard or {}).get("ai_ops_volatility_index") or {}
            stability = (dashboard or {}).get("ai_ops_stability_index") or {}
            root_causes: list[dict] = []

            def related_by_tag(keyword: str) -> list[dict]:
                related = []
                for item in persistent_items:
                    risk_tags = [str(tag or "") for tag in item.get("risk_tags") or []]
                    if any(keyword in tag for tag in risk_tags):
                        related.append({
                            "article_id": item.get("article_id"),
                            "title": item.get("title") or "未知文章",
                            "risk_tags": item.get("risk_tags") or [],
                        })
                return related

            def append_root_cause(
                cause_type: str,
                level: str,
                title: str,
                cause_summary: str,
                evidence: list[str],
                recommended_actions: list[str],
                related_articles: list[dict] | None = None,
            ) -> None:
                root_causes.append({
                    "type": cause_type,
                    "level": level,
                    "title": title,
                    "summary": cause_summary,
                    "evidence": evidence,
                    "recommended_actions": recommended_actions,
                    "related_articles": related_articles or [],
                })

            preflight_articles = related_by_tag("连续终检失败")
            if len(preflight_articles) >= 2:
                append_root_cause(
                    "preflight_failure_cluster",
                    "danger",
                    "终检失败集中出现",
                    "当前多篇文章出现连续终检失败，可能与 HTML 结构、CTA 卡片或微信兼容规则有关。",
                    [
                        f"连续终检失败文章数：{len(preflight_articles)}",
                        "关联文章 ID：" + "、".join(str(item.get("article_id")) for item in preflight_articles if item.get("article_id")),
                        "相关 risk_tags：连续终检失败",
                    ],
                    ["检查 CTA 卡片结构", "检查 HTML 清洗逻辑", "检查微信不兼容标签", "重新执行发布前终检"],
                    preflight_articles,
                )

            publish_articles = related_by_tag("连续发布失败")
            if len(recent_fail_items) >= 3 or publish_articles:
                related_articles = publish_articles or [
                    {
                        "article_id": item.get("article_id"),
                        "title": item.get("title") or "未知文章",
                        "risk_tags": ["最近发布失败"],
                    }
                    for item in recent_fail_items[:10]
                ]
                append_root_cause(
                    "publish_failure_cluster",
                    "danger",
                    "发布失败集中出现",
                    "最近发布失败较集中，可能与微信 API、token、封面图上传或 media_id 有关。",
                    [
                        f"最近发布失败文章数：{len(recent_fail_items)}",
                        f"连续发布失败文章数：{len(publish_articles)}",
                    ],
                    ["检查 WECHAT_APP_ID / WECHAT_APP_SECRET", "检查 access_token 获取", "检查封面图上传", "检查微信草稿箱接口返回"],
                    related_articles,
                )

            high_risk_articles = related_by_tag("连续高风险")
            high_risk_count = ArticleHealthService._safe_int(summary.get("high_risk_articles"))
            if high_risk_count >= 3 or high_risk_articles:
                append_root_cause(
                    "high_risk_content_cluster",
                    "warning",
                    "高风险内容集中出现",
                    "当前多篇文章被识别为高风险，可能与模板表达、行业敏感词或营销承诺有关。",
                    [
                        f"高风险文章数：{high_risk_count}",
                        f"连续高风险文章数：{len(high_risk_articles)}",
                    ],
                    ["检查高风险词", "优化模板表达", "降低营销承诺语气", "执行 AI 一键优化草稿"],
                    high_risk_articles,
                )

            score_change = ArticleHealthService._safe_int(score_trend.get("score_change"))
            if score_change <= -10:
                append_root_cause(
                    "ops_score_drop",
                    "warning",
                    "AI 运营评分明显下降",
                    "AI 运营评分出现明显下降，说明近期风险、失败或异常正在集中增加。",
                    [f"AI 运营评分变化：{score_change}", f"当前评分：{ArticleHealthService._safe_int(score_trend.get('current_score'))}"],
                    ["优先处理 AI 运营优先队列", "查看异常播报", "检查连续异常文章", "进入重点关注值班模式"],
                    list((dashboard or {}).get("ai_ops_priority_queue") or [])[:10],
                )

            volatility_level = (volatility.get("volatility_level") or volatility.get("level") or "").strip()
            stability_level = (stability.get("stability_level") or stability.get("level") or "").strip()
            if volatility_level == "highly_volatile" or stability_level == "unstable":
                append_root_cause(
                    "volatile_ops_state",
                    "warning",
                    "AI 运营状态波动较大",
                    "当前 AI 运营状态波动较大，可能存在风险反复、值班模式频繁切换或评分大幅变化。",
                    [f"波动等级：{volatility_level or '-'}", f"稳定性等级：{stability_level or '-'}"],
                    ["暂停批量发布", "优先人工复核高风险文章", "复查最近变更", "检查模板与终检规则"],
                    list((dashboard or {}).get("ai_ops_priority_queue") or [])[:10],
                )

            top_failure_patterns = ArticleHealthService._build_top_failure_patterns(
                dashboard,
                preflight_count=len(preflight_articles),
                publish_count=len(publish_articles),
                high_risk_count=len(high_risk_articles),
            )
            top_templates = ArticleHealthService._build_root_cause_top_templates(dashboard)
            recommended_actions = ArticleHealthService._collect_root_cause_actions(root_causes)
            return {
                "root_causes": root_causes,
                "top_templates": top_templates,
                "top_failure_patterns": top_failure_patterns,
                "summary": ArticleHealthService._build_root_cause_summary(root_causes),
                "recommended_actions": recommended_actions,
            }
        except Exception as exc:
            logger.warning("AI 根因分析构建失败：%s", exc)
            return empty_result

    @staticmethod
    def _build_top_failure_patterns(
        dashboard: dict,
        preflight_count: int,
        publish_count: int,
        high_risk_count: int,
    ) -> list[dict]:
        summary = (dashboard or {}).get("summary") or {}
        recent_fail_count = len(list((dashboard or {}).get("recent_fail_articles") or []))
        score_trend = (dashboard or {}).get("ai_ops_score_trend") or {}
        volatility = (dashboard or {}).get("ai_ops_volatility_index") or {}
        patterns = [
            {"pattern": "连续终检失败", "count": preflight_count, "level": "danger" if preflight_count >= 2 else "warning"},
            {"pattern": "连续发布失败", "count": publish_count, "level": "danger" if publish_count else "warning"},
            {"pattern": "连续高风险", "count": high_risk_count, "level": "danger" if high_risk_count >= 3 else "warning"},
            {"pattern": "最近发布失败", "count": recent_fail_count, "level": "danger" if recent_fail_count >= 3 else "warning"},
            {
                "pattern": "AI 评分下降",
                "count": 1 if ArticleHealthService._safe_int(score_trend.get("score_change")) <= -10 else 0,
                "level": "warning",
            },
            {
                "pattern": "高波动",
                "count": 1 if (volatility.get("volatility_level") or volatility.get("level")) == "highly_volatile" else 0,
                "level": "warning",
            },
            {
                "pattern": "高风险文章",
                "count": ArticleHealthService._safe_int(summary.get("high_risk_articles")),
                "level": "danger" if ArticleHealthService._safe_int(summary.get("high_risk_articles")) >= 3 else "warning",
            },
        ]
        return sorted(
            [item for item in patterns if item.get("count", 0) > 0],
            key=lambda item: (-ArticleHealthService._safe_int(item.get("count")), item.get("pattern") or ""),
        )

    @staticmethod
    def _build_root_cause_top_templates(dashboard: dict) -> list[dict]:
        """按现有文章模板字段聚合风险；字段不存在时返回空列表。"""
        try:
            conn = get_db()
            try:
                rows = conn.execute("SELECT * FROM articles").fetchall()
            finally:
                conn.close()
            articles = [dict(row) for row in rows]
            if not articles:
                return []
            template_fields = ["template_name", "template_title", "template_id"]
            available_fields = [field for field in template_fields if field in articles[0]]
            if not available_fields:
                return []

            persistent_ids = {
                ArticleHealthService._safe_int(item.get("article_id"))
                for item in list((dashboard or {}).get("persistent_risk_articles") or [])
            }
            high_risk_ids = {
                ArticleHealthService._safe_int(item.get("article_id"))
                for item in list((dashboard or {}).get("top_risk_articles") or [])
                if item.get("risk_level") == "high"
            }
            failed_ids = {
                ArticleHealthService._safe_int(item.get("article_id"))
                for item in list((dashboard or {}).get("recent_fail_articles") or [])
            }

            bucket: dict[str, dict] = {}
            for article in articles:
                template_value = ""
                for field in available_fields:
                    value = article.get(field)
                    if value not in (None, ""):
                        template_value = str(value)
                        break
                if not template_value:
                    continue
                article_id = ArticleHealthService._safe_int(article.get("id"))
                item = bucket.setdefault(template_value, {
                    "template": template_value,
                    "article_count": 0,
                    "risk_count": 0,
                    "failure_count": 0,
                    "risk_rate": 0.0,
                })
                item["article_count"] += 1
                if article_id in persistent_ids or article_id in high_risk_ids:
                    item["risk_count"] += 1
                if article_id in failed_ids:
                    item["failure_count"] += 1

            result = []
            for item in bucket.values():
                article_count = ArticleHealthService._safe_int(item.get("article_count"))
                risk_count = ArticleHealthService._safe_int(item.get("risk_count"))
                item["risk_rate"] = round((risk_count / article_count * 100), 1) if article_count else 0.0
                if risk_count or item.get("failure_count"):
                    result.append(item)
            return sorted(
                result,
                key=lambda item: (-ArticleHealthService._safe_int(item.get("risk_count")), -ArticleHealthService._safe_int(item.get("failure_count")), item.get("template") or ""),
            )[:10]
        except Exception as exc:
            logger.warning("AI 根因模板聚合失败：%s", exc)
            return []

    @staticmethod
    def _collect_root_cause_actions(root_causes: list[dict]) -> list[str]:
        actions: list[str] = []
        seen = set()
        for cause in root_causes or []:
            for action in cause.get("recommended_actions") or []:
                text = str(action).strip()
                if text and text not in seen:
                    seen.add(text)
                    actions.append(text)
                if len(actions) >= 8:
                    return actions
        return actions

    @staticmethod
    def _build_root_cause_summary(root_causes: list[dict]) -> str:
        if not root_causes:
            return "当前暂无明显集中性根因，建议保持常规巡检。"
        danger_titles = [item.get("title") for item in root_causes if item.get("level") == "danger"]
        if danger_titles:
            return "当前 AI 运营风险主要集中在：" + "、".join(danger_titles[:3]) + "，建议优先处理。"
        return "当前存在部分可疑根因，建议持续观察并按优先级处理。"

    @staticmethod
    def build_template_ops_analysis(dashboard: dict) -> dict:
        """构建模板级 AI 运营分析，只读聚合现有文章、AI 日志与发布任务。"""
        empty_result = ArticleHealthService._empty_template_ops_analysis()
        try:
            articles = ArticleHealthService._list_articles_with_template_fields()
            if not articles:
                return empty_result

            buckets: dict[str, dict] = {}
            for article in articles:
                template_name = ArticleHealthService._resolve_template_name(article)
                if not template_name:
                    continue
                article_id = ArticleHealthService._safe_int(article.get("id"))
                if not article_id:
                    continue

                try:
                    logs = ArticleHealthService._list_ai_logs(article_id, limit=10)
                    publish_tasks = ArticleHealthService._list_publish_tasks(article_id, limit=10)
                    health = ArticleHealthService.build_article_health(article_id) or {}
                    trend = ArticleHealthService.build_health_trend(article_id) or {}
                except Exception as exc:
                    logger.warning("模板运营单篇分析失败 article_id=%s：%s", article_id, exc)
                    logs = []
                    publish_tasks = []
                    health = {}
                    trend = {}

                health_score = ArticleHealthService._safe_int(health.get("score"))
                risk_level = (health.get("risk_level") or "unknown").strip()
                publish_fail_count = sum(1 for task in publish_tasks if task.get("status") == "failed")
                preflight_fail_count = ArticleHealthService._count_recent_preflight_failures(logs)
                volatility_index = ArticleHealthService._estimate_article_volatility_index(
                    health=health,
                    trend=trend,
                    preflight_fail_count=preflight_fail_count,
                    publish_fail_count=publish_fail_count,
                )
                stability_index = max(0, min(100, 100 - volatility_index))

                item = buckets.setdefault(template_name, {
                    "template": template_name,
                    "article_count": 0,
                    "high_risk_count": 0,
                    "publish_fail_count": 0,
                    "preflight_fail_count": 0,
                    "_health_total": 0,
                    "_stability_total": 0,
                    "_volatility_total": 0,
                    "average_health_score": 0,
                    "average_stability_index": 0,
                    "average_volatility_index": 0,
                    "risk_rate": 0,
                    "status": "healthy",
                })
                item["article_count"] += 1
                item["_health_total"] += health_score
                item["_stability_total"] += stability_index
                item["_volatility_total"] += volatility_index
                item["publish_fail_count"] += publish_fail_count
                item["preflight_fail_count"] += preflight_fail_count
                if risk_level == "high":
                    item["high_risk_count"] += 1

            template_health = []
            for item in buckets.values():
                article_count = ArticleHealthService._safe_int(item.get("article_count"))
                if not article_count:
                    continue
                high_risk_count = ArticleHealthService._safe_int(item.get("high_risk_count"))
                publish_fail_count = ArticleHealthService._safe_int(item.get("publish_fail_count"))
                item["average_health_score"] = int(round(item.pop("_health_total", 0) / article_count))
                item["average_stability_index"] = int(round(item.pop("_stability_total", 0) / article_count))
                item["average_volatility_index"] = int(round(item.pop("_volatility_total", 0) / article_count))
                item["risk_rate"] = round((high_risk_count / article_count) * 100, 1)
                if item["risk_rate"] >= 40 or publish_fail_count >= 3:
                    item["status"] = "danger"
                elif item["risk_rate"] >= 20:
                    item["status"] = "warning"
                else:
                    item["status"] = "healthy"
                template_health.append(item)

            if not template_health:
                return empty_result

            template_health = sorted(
                template_health,
                key=lambda item: (
                    ArticleHealthService._template_status_sort_weight(item.get("status")),
                    -float(item.get("risk_rate") or 0),
                    -ArticleHealthService._safe_int(item.get("publish_fail_count")),
                    -ArticleHealthService._safe_int(item.get("article_count")),
                    item.get("template") or "",
                ),
            )
            high_risk_templates = sorted(
                [item for item in template_health if item.get("status") == "danger"],
                key=lambda item: (
                    -float(item.get("risk_rate") or 0),
                    -ArticleHealthService._safe_int(item.get("publish_fail_count")),
                    -ArticleHealthService._safe_int(item.get("article_count")),
                    item.get("template") or "",
                ),
            )[:10]
            unstable_templates = sorted(
                [
                    item for item in template_health
                    if ArticleHealthService._safe_int(item.get("average_volatility_index")) >= 60
                    or ArticleHealthService._safe_int(item.get("average_stability_index")) <= 40
                ],
                key=lambda item: (
                    -ArticleHealthService._safe_int(item.get("average_volatility_index")),
                    ArticleHealthService._safe_int(item.get("average_stability_index")),
                    item.get("template") or "",
                ),
            )[:10]
            template_recovery = ArticleHealthService._build_template_recovery_items(template_health)
            return {
                "template_health": template_health,
                "high_risk_templates": high_risk_templates,
                "unstable_templates": unstable_templates,
                "template_recovery": template_recovery,
                "summary": ArticleHealthService._build_template_ops_summary(high_risk_templates, template_recovery),
                "recommended_actions": ArticleHealthService._build_template_ops_actions(high_risk_templates, unstable_templates),
            }
        except Exception as exc:
            logger.warning("AI 模板运营分析构建失败：%s", exc)
            return empty_result

    @staticmethod
    def _empty_template_ops_analysis() -> dict:
        return {
            "template_health": [],
            "high_risk_templates": [],
            "unstable_templates": [],
            "template_recovery": [],
            "summary": "当前暂无可用模板字段，暂无法生成模板级运营分析。",
            "recommended_actions": [],
        }

    @staticmethod
    def _list_articles_with_template_fields() -> list[dict]:
        try:
            conn = get_db()
            try:
                rows = conn.execute("SELECT * FROM articles").fetchall()
            finally:
                conn.close()
            articles = [dict(row) for row in rows]
            if not articles:
                return []
            if not any(ArticleHealthService._resolve_template_name(article) for article in articles):
                return []
            return articles
        except Exception as exc:
            logger.warning("读取模板运营文章数据失败：%s", exc)
            return []

    @staticmethod
    def _resolve_template_name(article: dict) -> str:
        template_fields = [
            "template_name",
            "template_title",
            "template_id",
            "article_template_name",
            "article_template_id",
        ]
        for field in template_fields:
            value = (article or {}).get(field)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    @staticmethod
    def _estimate_article_volatility_index(
        health: dict,
        trend: dict,
        preflight_fail_count: int,
        publish_fail_count: int,
    ) -> int:
        score = abs(ArticleHealthService._safe_int((trend or {}).get("score_change")))
        if (trend or {}).get("trend_direction") == "down":
            score += 15
        if (health or {}).get("risk_level") == "high":
            score += 30
        elif (health or {}).get("risk_level") == "medium":
            score += 15
        score += min(30, ArticleHealthService._safe_int(preflight_fail_count) * 10)
        score += min(30, ArticleHealthService._safe_int(publish_fail_count) * 10)
        return max(0, min(100, score))

    @staticmethod
    def _template_status_sort_weight(status: str) -> int:
        return {"danger": 0, "warning": 1, "healthy": 2}.get(status or "", 9)

    @staticmethod
    def _build_template_recovery_items(template_health: list[dict]) -> list[dict]:
        recovered = []
        for item in template_health or []:
            risk_rate = float(item.get("risk_rate") or 0)
            avg_health = ArticleHealthService._safe_int(item.get("average_health_score"))
            avg_stability = ArticleHealthService._safe_int(item.get("average_stability_index"))
            if risk_rate < 15 and avg_health >= 80 and avg_stability >= 70:
                recovery_score = max(0, min(100, int(round((avg_health + avg_stability + (100 - risk_rate)) / 3))))
                recovered.append({
                    "template": item.get("template") or "未知模板",
                    "recovery_score": recovery_score,
                    "summary": "该模板近期健康分和稳定性较好，风险率较低。",
                })
        return sorted(recovered, key=lambda item: (-ArticleHealthService._safe_int(item.get("recovery_score")), item.get("template") or ""))[:10]

    @staticmethod
    def _build_template_ops_summary(high_risk_templates: list[dict], template_recovery: list[dict]) -> str:
        if not high_risk_templates and not template_recovery:
            return "当前暂无明显模板级风险集中，建议保持常规模板巡检。"
        parts = []
        if high_risk_templates:
            names = "、".join((item.get("template") or "未知模板") for item in high_risk_templates[:3])
            parts.append(f"当前风险主要集中在：{names}。")
        if template_recovery:
            names = "、".join((item.get("template") or "未知模板") for item in template_recovery[:3])
            parts.append(f"当前恢复表现较好的模板：{names}。")
        return "".join(parts)

    @staticmethod
    def _build_template_ops_actions(high_risk_templates: list[dict], unstable_templates: list[dict]) -> list[str]:
        actions: list[str] = []
        seen = set()

        def add(action: str) -> None:
            text = (action or "").strip()
            if text and text not in seen and len(actions) < 8:
                seen.add(text)
                actions.append(text)

        if high_risk_templates:
            add("检查高风险模板 Prompt")
            add("降低营销承诺")
            add("优先人工审核危险模板")
        if unstable_templates:
            add("优化 CTA 结构")
            add("复查微信兼容标签")
            add("检查模板输出 HTML 稳定性")
        if high_risk_templates or unstable_templates:
            add("复盘异常文章与模板的对应关系")
        return actions

    @staticmethod
    def build_prompt_ops_analysis(dashboard: dict) -> dict:
        """构建 Prompt 级 AI 运营分析，只读聚合文章、AI 日志和发布任务。"""
        empty_result = ArticleHealthService._empty_prompt_ops_analysis()
        try:
            articles = ArticleHealthService._list_articles_with_prompt_fields()
            if not articles:
                return empty_result

            template_lookup = ArticleHealthService._load_prompt_template_lookup()
            buckets: dict[str, dict] = {}
            for article in articles:
                prompt_name = ArticleHealthService._resolve_prompt_name(article, template_lookup)
                if not prompt_name:
                    continue
                article_id = ArticleHealthService._safe_int(article.get("id"))
                if not article_id:
                    continue

                try:
                    logs = ArticleHealthService._list_ai_logs(article_id, limit=10)
                    publish_tasks = ArticleHealthService._list_publish_tasks(article_id, limit=10)
                    health = ArticleHealthService.build_article_health(article_id) or {}
                    trend = ArticleHealthService.build_health_trend(article_id) or {}
                except Exception as exc:
                    logger.warning("Prompt 运营单篇分析失败 article_id=%s：%s", article_id, exc)
                    logs = []
                    publish_tasks = []
                    health = {}
                    trend = {}

                health_score = ArticleHealthService._safe_int(health.get("score"))
                risk_level = (health.get("risk_level") or "unknown").strip()
                preflight_fail_count = ArticleHealthService._count_recent_preflight_failures(logs)
                publish_fail_count = sum(1 for task in publish_tasks if task.get("status") == "failed")
                failed_article = bool(preflight_fail_count or publish_fail_count)
                volatility_index = ArticleHealthService._estimate_article_volatility_index(
                    health=health,
                    trend=trend,
                    preflight_fail_count=preflight_fail_count,
                    publish_fail_count=publish_fail_count,
                )
                stability_index = max(0, min(100, 100 - volatility_index))

                item = buckets.setdefault(prompt_name, {
                    "prompt": prompt_name,
                    "article_count": 0,
                    "high_risk_count": 0,
                    "preflight_fail_count": 0,
                    "publish_fail_count": 0,
                    "_failure_article_count": 0,
                    "_health_total": 0,
                    "_stability_total": 0,
                    "_volatility_total": 0,
                    "average_health_score": 0,
                    "average_volatility_index": 0,
                    "average_stability_index": 0,
                    "risk_rate": 0,
                    "failure_rate": 0,
                    "status": "healthy",
                })
                item["article_count"] += 1
                item["_health_total"] += health_score
                item["_stability_total"] += stability_index
                item["_volatility_total"] += volatility_index
                item["preflight_fail_count"] += preflight_fail_count
                item["publish_fail_count"] += publish_fail_count
                if failed_article:
                    item["_failure_article_count"] += 1
                if risk_level == "high":
                    item["high_risk_count"] += 1

            prompt_health = []
            for item in buckets.values():
                article_count = ArticleHealthService._safe_int(item.get("article_count"))
                if not article_count:
                    continue
                high_risk_count = ArticleHealthService._safe_int(item.get("high_risk_count"))
                failure_article_count = ArticleHealthService._safe_int(item.pop("_failure_article_count", 0))
                publish_fail_count = ArticleHealthService._safe_int(item.get("publish_fail_count"))
                item["average_health_score"] = int(round(item.pop("_health_total", 0) / article_count))
                item["average_stability_index"] = int(round(item.pop("_stability_total", 0) / article_count))
                item["average_volatility_index"] = int(round(item.pop("_volatility_total", 0) / article_count))
                item["risk_rate"] = round((high_risk_count / article_count) * 100, 1)
                item["failure_rate"] = round((failure_article_count / article_count) * 100, 1)
                if item["risk_rate"] >= 40 or item["failure_rate"] >= 30 or publish_fail_count >= 3:
                    item["status"] = "danger"
                elif item["risk_rate"] >= 20 or item["failure_rate"] >= 15:
                    item["status"] = "warning"
                else:
                    item["status"] = "healthy"
                prompt_health.append(item)

            if not prompt_health:
                return empty_result

            prompt_health = sorted(
                prompt_health,
                key=lambda item: (
                    ArticleHealthService._template_status_sort_weight(item.get("status")),
                    -float(item.get("risk_rate") or 0),
                    -float(item.get("failure_rate") or 0),
                    -ArticleHealthService._safe_int(item.get("article_count")),
                    item.get("prompt") or "",
                ),
            )
            high_risk_prompts = sorted(
                [item for item in prompt_health if item.get("status") == "danger"],
                key=lambda item: (
                    -float(item.get("risk_rate") or 0),
                    -float(item.get("failure_rate") or 0),
                    -ArticleHealthService._safe_int(item.get("article_count")),
                    item.get("prompt") or "",
                ),
            )[:10]
            unstable_prompts = sorted(
                [
                    item for item in prompt_health
                    if ArticleHealthService._safe_int(item.get("average_volatility_index")) >= 60
                    or ArticleHealthService._safe_int(item.get("average_stability_index")) <= 40
                ],
                key=lambda item: (
                    -ArticleHealthService._safe_int(item.get("average_volatility_index")),
                    ArticleHealthService._safe_int(item.get("average_stability_index")),
                    item.get("prompt") or "",
                ),
            )[:10]
            prompt_recommendations = ArticleHealthService._build_prompt_recommendations(prompt_health)
            return {
                "prompt_health": prompt_health,
                "high_risk_prompts": high_risk_prompts,
                "unstable_prompts": unstable_prompts,
                "prompt_recommendations": prompt_recommendations,
                "summary": ArticleHealthService._build_prompt_ops_summary(prompt_health, high_risk_prompts),
                "recommended_actions": ArticleHealthService._build_prompt_ops_actions(prompt_recommendations),
            }
        except Exception as exc:
            logger.warning("AI Prompt 运营分析构建失败：%s", exc)
            return empty_result

    @staticmethod
    def _empty_prompt_ops_analysis() -> dict:
        return {
            "prompt_health": [],
            "high_risk_prompts": [],
            "unstable_prompts": [],
            "prompt_recommendations": [],
            "summary": "当前暂无可用于 Prompt 分析的字段。",
            "recommended_actions": [],
        }

    @staticmethod
    def _list_articles_with_prompt_fields() -> list[dict]:
        try:
            conn = get_db()
            try:
                rows = conn.execute("SELECT * FROM articles").fetchall()
            finally:
                conn.close()
            articles = [dict(row) for row in rows]
            if not articles:
                return []
            template_lookup = ArticleHealthService._load_prompt_template_lookup()
            if not any(ArticleHealthService._resolve_prompt_name(article, template_lookup) for article in articles):
                return []
            return articles
        except Exception as exc:
            logger.warning("读取 Prompt 运营文章数据失败：%s", exc)
            return []

    @staticmethod
    def _load_prompt_template_lookup() -> dict[str, dict[str, str]]:
        lookup: dict[str, dict[str, str]] = {}
        for table_name in ("article_templates", "templates"):
            try:
                conn = get_db()
                try:
                    rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
                finally:
                    conn.close()
            except Exception:
                continue

            table_lookup: dict[str, str] = {}
            for row in rows:
                row_dict = dict(row)
                prompt_name = ArticleHealthService._resolve_template_prompt_name(row_dict)
                if not prompt_name:
                    continue
                for key_field in ("id", "template_id", "article_template_id"):
                    key_value = row_dict.get(key_field)
                    if key_value not in (None, ""):
                        table_lookup[str(key_value)] = prompt_name
            if table_lookup:
                lookup[table_name] = table_lookup
        return lookup

    @staticmethod
    def _resolve_prompt_name(article: dict, template_lookup: dict | None = None) -> str:
        prompt_fields = [
            "prompt_type",
            "prompt_name",
            "prompt_key",
            "writing_style",
            "writing_mode",
            "template_type",
            "category",
            "tags",
        ]
        for field in prompt_fields:
            value = (article or {}).get(field)
            if value not in (None, ""):
                text = str(value).strip()
                if text:
                    return text

        lookup = template_lookup or {}
        for id_field, table_name in (("article_template_id", "article_templates"), ("template_id", "templates"), ("template_id", "article_templates")):
            value = (article or {}).get(id_field)
            if value in (None, ""):
                continue
            prompt_name = (lookup.get(table_name) or {}).get(str(value))
            if prompt_name:
                return prompt_name
        return ""

    @staticmethod
    def _resolve_template_prompt_name(template_row: dict) -> str:
        prompt_fields = [
            "prompt_type",
            "prompt_name",
            "prompt_key",
            "writing_style",
            "category",
            "tags",
            "name",
            "title",
        ]
        for field in prompt_fields:
            value = (template_row or {}).get(field)
            if value not in (None, ""):
                text = str(value).strip()
                if text:
                    return text
        return ""

    @staticmethod
    def _build_prompt_recommendations(prompt_health: list[dict]) -> list[dict]:
        recommendations: list[dict] = []

        def add(item: dict, issue: str, suggestion: str, level: str | None = None) -> None:
            recommendations.append({
                "prompt": item.get("prompt") or "未知 Prompt",
                "level": level or item.get("status") or "warning",
                "issue": issue,
                "suggestion": suggestion,
            })

        for item in prompt_health or []:
            if float(item.get("risk_rate") or 0) >= 40:
                add(item, "高风险率偏高", "建议降低营销承诺语气，增加合规提示，减少绝对化表达。", "danger")
            if ArticleHealthService._safe_int(item.get("preflight_fail_count")) >= 2:
                add(item, "终检失败偏高", "建议检查 Prompt 中的 CTA 结构、HTML 约束和微信兼容性要求。")
            if ArticleHealthService._safe_int(item.get("publish_fail_count")) >= 3:
                add(item, "发布失败偏高", "建议优先检查封面图、media_id 和微信草稿箱兼容要求。", "danger")
            if ArticleHealthService._safe_int(item.get("average_volatility_index")) >= 60:
                add(item, "波动过高", "建议对不稳定 Prompt 做 A/B 测试，并收敛输出结构。")
            if ArticleHealthService._safe_int(item.get("average_stability_index")) <= 40:
                add(item, "稳定性偏低", "建议增加固定输出格式、合规边界和微信 HTML 约束。")
            if len(recommendations) >= 10:
                break
        return recommendations[:10]

    @staticmethod
    def _build_prompt_ops_summary(prompt_health: list[dict], high_risk_prompts: list[dict]) -> str:
        if not prompt_health:
            return "当前暂无可用于 Prompt 分析的数据。"
        if high_risk_prompts:
            names = "、".join((item.get("prompt") or "未知 Prompt") for item in high_risk_prompts[:3])
            return f"当前 Prompt 风险主要集中在：{names}。"
        warning_prompts = [item for item in prompt_health if item.get("status") == "warning"]
        if warning_prompts:
            return "当前部分 Prompt 存在稳定性或失败率问题，建议持续观察。"
        return "当前 Prompt 运行整体健康，暂无明显集中风险。"

    @staticmethod
    def _build_prompt_ops_actions(prompt_recommendations: list[dict]) -> list[str]:
        action_map = {
            "高风险率偏高": ["优化高风险 Prompt 的合规表达", "降低营销承诺语气", "人工复核高风险 Prompt 生成结果"],
            "终检失败偏高": ["检查 Prompt 中的 CTA 结构", "增加微信兼容性约束"],
            "发布失败偏高": ["优先优化发布失败率高的 Prompt", "增加微信素材与封面图约束"],
            "波动过高": ["对不稳定 Prompt 做 A/B 测试"],
            "稳定性偏低": ["增加固定输出格式约束"],
        }
        actions: list[str] = []
        seen = set()
        for recommendation in prompt_recommendations or []:
            issue = recommendation.get("issue")
            for action in action_map.get(issue, []):
                if action not in seen:
                    seen.add(action)
                    actions.append(action)
                if len(actions) >= 8:
                    return actions
        return actions

    @staticmethod
    def build_ai_ops_suggestions(dashboard: dict) -> list[dict]:
        """根据 Dashboard 当前状态生成轻量运营建议。"""
        summary = (dashboard or {}).get("summary") or {}
        persistent_items = list((dashboard or {}).get("persistent_risk_articles") or [])
        recovered_items = list((dashboard or {}).get("recovered_articles") or [])
        active_items = list((dashboard or {}).get("top_active_articles") or [])

        suggestions = []
        if ArticleHealthService._safe_int(summary.get("high_risk_articles")) >= 5:
            suggestions.append({
                "level": "danger",
                "title": "存在多篇高风险文章",
                "message": "建议优先处理健康分较低的文章，避免持续风险扩大",
                "action_text": "查看高风险文章",
                "action_url": "/ai-dashboard?risk_level=high",
            })

        if len(persistent_items) >= 3:
            suggestions.append({
                "level": "warning",
                "title": "连续异常文章较多",
                "message": "建议优先检查连续终检失败和连续发布失败文章",
                "action_text": "查看连续异常",
                "action_url": "/ai-dashboard",
            })

        if len(recovered_items) >= len(persistent_items) and (recovered_items or persistent_items):
            suggestions.append({
                "level": "success",
                "title": "近期风险恢复情况良好",
                "message": "恢复文章数量已超过连续异常文章，可继续保持当前优化节奏",
                "action_text": "",
                "action_url": "",
            })

        if ArticleHealthService._safe_int(summary.get("avg_health_score")) < 60:
            suggestions.append({
                "level": "danger",
                "title": "整体文章健康分偏低",
                "message": "建议重点检查 AI 优化质量与发布前终检规则",
                "action_text": "查看低健康分",
                "action_url": "/ai-dashboard?max_score=60",
            })

        if any(ArticleHealthService._safe_int(item.get("ai_operation_count")) >= 10 for item in active_items):
            suggestions.append({
                "level": "warning",
                "title": "部分文章 AI 操作过于频繁",
                "message": "建议人工介入检查是否存在反复优化问题",
                "action_text": "查看 AI 活跃文章",
                "action_url": "/ai-dashboard",
            })

        return sorted(
            suggestions,
            key=lambda item: (
                {"danger": 0, "warning": 1, "success": 2}.get(item.get("level"), 3),
                item.get("title", ""),
            ),
        )[:5]

    @staticmethod
    def build_ai_ops_score(dashboard: dict) -> dict:
        """根据 Dashboard 当前盘面计算 AI 运营总评分。"""
        summary = (dashboard or {}).get("summary") or {}
        if not dashboard or not summary:
            return {
                "score": 100,
                "level": "good",
                "summary": "当前暂无足够数据，默认按稳定状态处理。",
                "score_breakdown": [],
            }

        high_risk_articles = ArticleHealthService._safe_int(summary.get("high_risk_articles"))
        need_attention_articles = ArticleHealthService._safe_int(summary.get("need_attention_articles"))
        avg_health_score = ArticleHealthService._safe_int(summary.get("avg_health_score"))
        persistent_count = len(list((dashboard or {}).get("persistent_risk_articles") or []))
        recovered_count = len(list((dashboard or {}).get("recovered_articles") or []))
        recent_fail_count = len(list((dashboard or {}).get("recent_fail_articles") or []))
        trend_summary = (dashboard or {}).get("trend_summary") or {}
        down_count = ArticleHealthService._safe_int(trend_summary.get("down_count"))

        breakdown = [
            {"name": "平均健康分", "score": 5 if avg_health_score >= 85 else 0},
            {"name": "高风险文章", "score": -min(high_risk_articles * 5, 30)},
            {"name": "连续异常文章", "score": -min(persistent_count * 4, 20)},
            {"name": "人工关注文章", "score": -min(need_attention_articles * 2, 20)},
            {"name": "最近失败文章", "score": -min(recent_fail_count * 3, 15)},
            {"name": "趋势下降文章", "score": -min(down_count * 2, 10)},
            {"name": "恢复文章", "score": min(recovered_count * 2, 10)},
        ]
        if high_risk_articles == 0:
            breakdown.append({"name": "无高风险文章", "score": 5})

        raw_score = 100 + sum(item["score"] for item in breakdown)
        score = max(0, min(raw_score, 100))
        if score >= 90:
            level = "excellent"
            summary_text = "当前 AI 运营表现优秀，整体风险极低。"
        elif score >= 75:
            level = "good"
            summary_text = "当前 AI 运营整体稳定，风险可控。"
        elif score >= 60:
            level = "warning"
            summary_text = "当前 AI 运营存在一定风险，建议重点关注异常文章。"
        else:
            level = "danger"
            summary_text = "当前 AI 运营风险较高，建议立即处理高风险与连续异常文章。"

        return {
            "score": score,
            "level": level,
            "summary": summary_text,
            "score_breakdown": breakdown,
        }

    @staticmethod
    def build_ai_ops_health_index(dashboard: dict) -> dict:
        """综合风险、趋势、恢复和发布稳定性生成全局 AI 运营健康指数。"""
        summary = (dashboard or {}).get("summary") or {}
        if not dashboard or not summary:
            return {
                "health_index": 80,
                "health_level": "healthy",
                "summary": "暂无足够数据生成 AI 运营健康指数。",
                "breakdown": [],
            }

        high_risk_articles = ArticleHealthService._safe_int(summary.get("high_risk_articles"))
        need_attention_articles = ArticleHealthService._safe_int(summary.get("need_attention_articles"))
        persistent_count = len(list((dashboard or {}).get("persistent_risk_articles") or []))
        recovered_count = len(list((dashboard or {}).get("recovered_articles") or []))
        recent_fail_count = len(list((dashboard or {}).get("recent_fail_articles") or []))
        trend_summary = (dashboard or {}).get("trend_summary") or {}
        down_count = ArticleHealthService._safe_int(trend_summary.get("down_count"))
        ai_ops_score = (dashboard or {}).get("ai_ops_score") or {}
        duty_mode = (dashboard or {}).get("ai_ops_duty_mode") or {}
        score_level = (ai_ops_score.get("level") or "").strip()
        mode = (duty_mode.get("mode") or "").strip()

        breakdown = [
            {"label": "高风险文章", "score": -(high_risk_articles * 5)},
            {"label": "连续异常文章", "score": -(persistent_count * 8)},
            {"label": "人工关注文章", "score": -(need_attention_articles * 3)},
            {"label": "最近失败文章", "score": -(recent_fail_count * 5)},
            {"label": "趋势下降文章", "score": -(down_count * 4)},
            {"label": "恢复文章", "score": recovered_count * 4},
        ]
        if mode == "high_alert":
            breakdown.append({"label": "高危值班模式", "score": -15})
        elif mode == "focus":
            breakdown.append({"label": "重点关注模式", "score": -8})
        elif mode == "recovery":
            breakdown.append({"label": "恢复观察模式", "score": 5})

        if score_level == "excellent":
            breakdown.append({"label": "运营评分优秀", "score": 8})
        if high_risk_articles == 0:
            breakdown.append({"label": "无高风险文章", "score": 5})

        health_index = max(0, min(100 + sum(item["score"] for item in breakdown), 100))
        if health_index >= 90:
            health_level = "excellent"
            summary_text = "当前 AI 运营状态非常健康。"
        elif health_index >= 75:
            health_level = "healthy"
            summary_text = "当前 AI 运营整体健康，风险可控。"
        elif health_index >= 60:
            health_level = "warning"
            summary_text = "当前 AI 运营存在一定风险，建议重点关注异常文章。"
        else:
            health_level = "danger"
            summary_text = "当前 AI 运营风险较高，建议立即进行风险处理。"

        return {
            "health_index": health_index,
            "health_level": health_level,
            "summary": summary_text,
            "breakdown": breakdown,
        }

    @staticmethod
    def build_ai_ops_stability_index(dashboard: dict) -> dict:
        """衡量最近 AI 运营波动情况，生成全局稳定性指数。"""
        if not dashboard:
            return {
                "stability_index": 80,
                "stability_level": "stable",
                "summary": "暂无足够数据生成 AI 运营稳定性指数。",
                "breakdown": [],
            }

        duty_mode = (dashboard or {}).get("ai_ops_duty_mode") or {}
        duty_history = (dashboard or {}).get("ai_ops_duty_history_summary") or {}
        score_trend = (dashboard or {}).get("ai_ops_score_trend") or {}
        incident_feed = list((dashboard or {}).get("ai_ops_incident_feed") or [])
        persistent_count = len(list((dashboard or {}).get("persistent_risk_articles") or []))
        recovered_count = len(list((dashboard or {}).get("recovered_articles") or []))

        mode = (duty_mode.get("mode") or "").strip()
        duty_trend = (duty_history.get("trend_direction") or "").strip()
        score_direction = (score_trend.get("trend_direction") or "").strip()
        score_change = ArticleHealthService._safe_int(score_trend.get("score_change"))
        danger_incident_count = sum(1 for item in incident_feed if item.get("level") == "danger")
        warning_incident_count = sum(1 for item in incident_feed if item.get("level") == "warning")

        breakdown = []
        if mode == "high_alert":
            breakdown.append({"label": "高危值班模式", "score": -20})
        elif mode == "focus":
            breakdown.append({"label": "重点关注模式", "score": -10})
        elif mode == "recovery":
            breakdown.append({"label": "恢复观察模式", "score": 10})

        if duty_trend == "up":
            breakdown.append({"label": "值班模式风险升级", "score": -15})
        elif duty_trend == "down":
            breakdown.append({"label": "值班模式风险回落", "score": 10})

        if score_change <= -10:
            breakdown.append({"label": "评分明显下降", "score": -15})
        if persistent_count:
            breakdown.append({"label": "连续异常文章", "score": -(persistent_count * 6)})
        if danger_incident_count:
            breakdown.append({"label": "danger 播报", "score": -min(danger_incident_count * 4, 20)})
        if warning_incident_count:
            breakdown.append({"label": "warning 播报", "score": -min(warning_incident_count * 2, 10)})

        if score_direction == "stable":
            breakdown.append({"label": "评分趋势稳定", "score": 5})
        if recovered_count > persistent_count:
            breakdown.append({"label": "恢复多于异常", "score": 10})
        if danger_incident_count == 0:
            breakdown.append({"label": "无 danger 播报", "score": 5})

        stability_index = max(0, min(100 + sum(item["score"] for item in breakdown), 100))
        if stability_index >= 90:
            stability_level = "excellent"
            summary_text = "最近 AI 运营状态非常稳定。"
        elif stability_index >= 75:
            stability_level = "stable"
            summary_text = "最近 AI 运营整体较稳定。"
        elif stability_index >= 60:
            stability_level = "warning"
            summary_text = "最近 AI 运营存在一定波动。"
        else:
            stability_level = "unstable"
            summary_text = "最近 AI 运营波动较大，建议重点关注风险变化。"

        return {
            "stability_index": stability_index,
            "stability_level": stability_level,
            "summary": summary_text,
            "breakdown": breakdown,
        }

    @staticmethod
    def build_ai_ops_volatility_index(dashboard: dict) -> dict:
        """衡量最近 AI 运营震荡程度，指数越高代表波动越大。"""
        if not dashboard:
            return {
                "volatility_index": 20,
                "volatility_level": "stable",
                "summary": "暂无足够数据生成 AI 运营波动指数。",
                "breakdown": [],
            }

        duty_mode = (dashboard or {}).get("ai_ops_duty_mode") or {}
        duty_history = (dashboard or {}).get("ai_ops_duty_history_summary") or {}
        score_trend = (dashboard or {}).get("ai_ops_score_trend") or {}
        incident_feed = list((dashboard or {}).get("ai_ops_incident_feed") or [])
        persistent_count = len(list((dashboard or {}).get("persistent_risk_articles") or []))
        recovered_count = len(list((dashboard or {}).get("recovered_articles") or []))

        mode = (duty_mode.get("mode") or "").strip()
        duty_trend = (duty_history.get("trend_direction") or "").strip()
        recent_modes = [
            str(item).strip()
            for item in list(duty_history.get("recent_modes") or [])
            if str(item).strip()
        ]
        score_direction = (score_trend.get("trend_direction") or "").strip()
        score_change = ArticleHealthService._safe_int(score_trend.get("score_change"))
        danger_incident_count = sum(1 for item in incident_feed if item.get("level") == "danger")
        warning_incident_count = sum(1 for item in incident_feed if item.get("level") == "warning")

        switch_count = 0
        for index in range(1, len(recent_modes)):
            if recent_modes[index] != recent_modes[index - 1]:
                switch_count += 1

        breakdown = []
        if mode == "high_alert":
            breakdown.append({"label": "高危值班模式", "score": 25})
        elif mode == "focus":
            breakdown.append({"label": "重点关注模式", "score": 15})
        elif mode == "recovery":
            breakdown.append({"label": "恢复观察模式", "score": -10})

        if duty_trend == "up":
            breakdown.append({"label": "值班模式风险升级", "score": 20})
        elif duty_trend == "down":
            breakdown.append({"label": "值班模式风险回落", "score": -10})

        if switch_count >= 4:
            breakdown.append({"label": "值班模式切换频繁", "score": 25})
        elif switch_count >= 2:
            breakdown.append({"label": "值班模式切换频繁", "score": 15})

        if score_change:
            breakdown.append({"label": "评分变化较大", "score": abs(score_change)})
        if persistent_count:
            breakdown.append({"label": "连续异常文章", "score": persistent_count * 8})
        if danger_incident_count:
            breakdown.append({"label": "danger 播报", "score": min(danger_incident_count * 5, 25)})
        if warning_incident_count:
            breakdown.append({"label": "warning 播报", "score": min(warning_incident_count * 2, 10)})

        if score_direction == "stable":
            breakdown.append({"label": "评分趋势稳定", "score": -5})
        if recovered_count > persistent_count:
            breakdown.append({"label": "恢复多于异常", "score": -15})
        if danger_incident_count == 0:
            breakdown.append({"label": "无 danger 播报", "score": -10})

        volatility_index = max(0, min(sum(item["score"] for item in breakdown), 100))
        if volatility_index < 20:
            volatility_level = "very_stable"
            summary_text = "最近 AI 运营波动极低。"
        elif volatility_index < 40:
            volatility_level = "stable"
            summary_text = "最近 AI 运营整体较稳定。"
        elif volatility_index < 70:
            volatility_level = "volatile"
            summary_text = "最近 AI 运营存在一定波动。"
        else:
            volatility_level = "highly_volatile"
            summary_text = "最近 AI 运营波动较大，建议重点关注风险变化。"

        return {
            "volatility_index": volatility_index,
            "volatility_level": volatility_level,
            "summary": summary_text,
            "breakdown": breakdown,
        }

    @staticmethod
    def build_ai_ops_recovery_index(dashboard: dict) -> dict:
        """衡量 AI 运营从风险中恢复的能力，指数越高代表恢复力越强。"""
        if not dashboard:
            return {
                "recovery_index": 60,
                "recovery_level": "normal",
                "summary": "暂无足够数据生成 AI 运营恢复力指数。",
                "breakdown": [],
            }

        duty_mode = (dashboard or {}).get("ai_ops_duty_mode") or {}
        duty_history = (dashboard or {}).get("ai_ops_duty_history_summary") or {}
        score_trend = (dashboard or {}).get("ai_ops_score_trend") or {}
        ai_ops_score = (dashboard or {}).get("ai_ops_score") or {}
        incident_feed = list((dashboard or {}).get("ai_ops_incident_feed") or [])
        persistent_count = len(list((dashboard or {}).get("persistent_risk_articles") or []))
        recovered_count = len(list((dashboard or {}).get("recovered_articles") or []))

        mode = (duty_mode.get("mode") or "").strip()
        duty_trend = (duty_history.get("trend_direction") or "").strip()
        score_change = ArticleHealthService._safe_int(score_trend.get("score_change"))
        score_level = (ai_ops_score.get("level") or "").strip()
        danger_incident_count = sum(1 for item in incident_feed if item.get("level") == "danger")

        breakdown = []
        if recovered_count:
            breakdown.append({"label": "恢复文章", "score": recovered_count * 6})
        if recovered_count > persistent_count:
            breakdown.append({"label": "恢复文章多于连续异常", "score": 20})

        if mode == "recovery":
            breakdown.append({"label": "恢复观察模式", "score": 15})
        elif mode == "normal":
            breakdown.append({"label": "稳定巡检模式", "score": 10})
        elif mode == "high_alert":
            breakdown.append({"label": "高危值班模式", "score": -20})
        elif mode == "focus":
            breakdown.append({"label": "重点关注模式", "score": -10})

        if duty_trend == "down":
            breakdown.append({"label": "值班模式风险回落", "score": 15})
        elif duty_trend == "up":
            breakdown.append({"label": "值班模式风险升级", "score": -15})

        if score_change >= 10:
            breakdown.append({"label": "运营评分明显提升", "score": 10})
        elif score_change <= -10:
            breakdown.append({"label": "运营评分明显下降", "score": -10})

        if danger_incident_count == 0:
            breakdown.append({"label": "无 danger 播报", "score": 10})
        else:
            breakdown.append({"label": "danger 播报", "score": -min(danger_incident_count * 5, 20)})

        if score_level == "excellent":
            breakdown.append({"label": "运营评分优秀", "score": 10})
        if persistent_count:
            breakdown.append({"label": "连续异常文章", "score": -(persistent_count * 8)})

        recovery_index = max(0, min(50 + sum(item["score"] for item in breakdown), 100))
        if recovery_index >= 90:
            recovery_level = "excellent"
            summary_text = "当前 AI 运营恢复能力非常强。"
        elif recovery_index >= 75:
            recovery_level = "strong"
            summary_text = "当前 AI 运营恢复能力较强。"
        elif recovery_index >= 60:
            recovery_level = "normal"
            summary_text = "当前 AI 运营恢复能力一般。"
        else:
            recovery_level = "weak"
            summary_text = "当前 AI 运营恢复能力较弱，建议重点关注风险修复。"

        return {
            "recovery_index": recovery_index,
            "recovery_level": recovery_level,
            "summary": summary_text,
            "breakdown": breakdown,
        }

    @staticmethod
    def _read_ai_ops_score_history() -> list[dict]:
        """读取 AI 运营总评分历史；缺失或损坏时安全返回空列表。"""
        if not os.path.exists(AI_OPS_SCORE_HISTORY_FILE_PATH):
            return []
        try:
            with open(AI_OPS_SCORE_HISTORY_FILE_PATH, "r", encoding="utf-8") as history_file:
                data = json.load(history_file)
            return data if isinstance(data, list) else []
        except Exception as exc:
            logger.warning("AI 运营评分历史读取失败，按空历史处理：%s", exc)
            return []

    @staticmethod
    def _write_ai_ops_score_history(history: list[dict]) -> None:
        """写入 AI 运营总评分历史，自动创建 data 目录。"""
        history_dir = os.path.dirname(AI_OPS_SCORE_HISTORY_FILE_PATH)
        if history_dir:
            os.makedirs(history_dir, exist_ok=True)
        with open(AI_OPS_SCORE_HISTORY_FILE_PATH, "w", encoding="utf-8") as history_file:
            json.dump(list(history or [])[-100:], history_file, ensure_ascii=False, indent=2)

    @staticmethod
    def append_ai_ops_score_history(score: int) -> None:
        """记录当前 AI 运营评分；分数未变化时不重复写入。"""
        try:
            safe_score = max(0, min(ArticleHealthService._safe_int(score), 100))
            history = ArticleHealthService._read_ai_ops_score_history()
            latest_score = ArticleHealthService._safe_int((history[-1] if history else {}).get("score"))
            if history and latest_score == safe_score:
                return
            history.append({
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "score": safe_score,
            })
            ArticleHealthService._write_ai_ops_score_history(history[-100:])
        except Exception as exc:
            logger.warning("AI 运营评分历史写入失败：%s", exc)

    @staticmethod
    def build_ai_ops_score_trend(dashboard: dict) -> dict:
        """结合评分历史，生成 AI 运营总评分趋势摘要。"""
        ai_ops_score = (dashboard or {}).get("ai_ops_score") or {}
        current_score = max(0, min(ArticleHealthService._safe_int(ai_ops_score.get("score")), 100))
        history = ArticleHealthService._read_ai_ops_score_history()
        if not history:
            return {
                "current_score": current_score,
                "previous_score": current_score,
                "score_change": 0,
                "trend_direction": "stable",
                "recent_scores": [current_score],
                "summary": "当前暂无足够历史数据。",
            }

        previous_score = max(0, min(ArticleHealthService._safe_int(history[-1].get("score")), 100))
        score_change = current_score - previous_score
        if score_change >= 5:
            trend_direction = "up"
            summary = "最近 AI 运营评分呈上升趋势。"
        elif score_change <= -5:
            trend_direction = "down"
            summary = "最近 AI 运营评分呈下降趋势，建议重点关注风险变化。"
        else:
            trend_direction = "stable"
            summary = "最近 AI 运营评分整体稳定。"

        recent_scores = [
            max(0, min(ArticleHealthService._safe_int(item.get("score")), 100))
            for item in history[-4:]
        ]
        recent_scores.append(current_score)
        return {
            "current_score": current_score,
            "previous_score": previous_score,
            "score_change": score_change,
            "trend_direction": trend_direction,
            "recent_scores": recent_scores[-5:],
            "summary": summary,
        }

    @staticmethod
    def _read_ai_ops_duty_history() -> list[dict]:
        """读取 AI 运营值班历史；文件缺失或损坏时安全返回空列表。"""
        if not os.path.exists(AI_OPS_DUTY_HISTORY_FILE_PATH):
            return []
        try:
            with open(AI_OPS_DUTY_HISTORY_FILE_PATH, "r", encoding="utf-8") as history_file:
                data = json.load(history_file)
            return data if isinstance(data, list) else []
        except Exception as exc:
            logger.warning("AI 运营值班历史读取失败，按空历史处理：%s", exc)
            return []

    @staticmethod
    def _write_ai_ops_duty_history(history: list[dict]) -> None:
        """写入 AI 运营值班历史，自动创建 data 目录并只保留最近 100 条。"""
        history_dir = os.path.dirname(AI_OPS_DUTY_HISTORY_FILE_PATH)
        if history_dir:
            os.makedirs(history_dir, exist_ok=True)
        with open(AI_OPS_DUTY_HISTORY_FILE_PATH, "w", encoding="utf-8") as history_file:
            json.dump(list(history or [])[-100:], history_file, ensure_ascii=False, indent=2)

    @staticmethod
    def append_ai_ops_duty_history(duty_mode: dict) -> None:
        """记录当前 AI 运营值班模式；模式未变化时不重复写入。"""
        try:
            safe_mode = ((duty_mode or {}).get("mode") or "normal").strip() or "normal"
            safe_title = ((duty_mode or {}).get("title") or "AI 运营稳定巡检模式").strip() or "AI 运营稳定巡检模式"
            history = ArticleHealthService._read_ai_ops_duty_history()
            latest_mode = ((history[-1] if history else {}).get("mode") or "").strip()
            if history and latest_mode == safe_mode:
                return
            history.append({
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mode": safe_mode,
                "title": safe_title,
            })
            ArticleHealthService._write_ai_ops_duty_history(history[-100:])
        except Exception as exc:
            logger.warning("AI 运营值班历史写入失败：%s", exc)

    @staticmethod
    def build_ai_ops_duty_history_summary() -> dict:
        """根据最近值班历史生成模式变化摘要，只做只读轨迹分析。"""
        history = ArticleHealthService._read_ai_ops_duty_history()
        if not history:
            return {
                "current_mode": "normal",
                "previous_mode": "normal",
                "recent_modes": ["normal"],
                "summary": "当前暂无足够值班历史数据。",
                "trend_direction": "stable",
            }

        recent_modes = [
            ((item or {}).get("mode") or "normal").strip() or "normal"
            for item in history[-5:]
        ] or ["normal"]
        current_mode = recent_modes[-1]
        previous_mode = recent_modes[-2] if len(recent_modes) >= 2 else current_mode

        severity_map = {
            "normal": 1,
            "recovery": 1,
            "focus": 2,
            "high_alert": 3,
        }
        current_weight = severity_map.get(current_mode, 1)
        previous_weight = severity_map.get(previous_mode, 1)
        if current_weight > previous_weight:
            trend_direction = "up"
            summary = "最近 AI 运营值班模式呈升级趋势。"
        elif current_weight < previous_weight:
            trend_direction = "down"
            summary = "最近 AI 运营值班模式风险正在回落。"
        else:
            trend_direction = "stable"
            summary = "最近 AI 运营值班模式整体稳定。"

        return {
            "current_mode": current_mode,
            "previous_mode": previous_mode,
            "recent_modes": recent_modes,
            "summary": summary,
            "trend_direction": trend_direction,
        }

    @staticmethod
    def build_daily_ai_ops_summary(dashboard: dict) -> dict:
        """基于 Dashboard 当前状态生成今日 AI 运营摘要。"""
        summary = (dashboard or {}).get("summary") or {}
        if not dashboard or not summary:
            return {
                "level": "normal",
                "title": "今日 AI 运营暂无异常",
                "summary": "当前暂无足够数据生成运营摘要。",
                "highlights": [],
                "recommended_focus": ["保持当前审核与终检节奏"],
            }

        high_risk_articles = ArticleHealthService._safe_int(summary.get("high_risk_articles"))
        avg_health_score = ArticleHealthService._safe_int(summary.get("avg_health_score"))
        need_attention_articles = ArticleHealthService._safe_int(summary.get("need_attention_articles"))
        persistent_count = len(list((dashboard or {}).get("persistent_risk_articles") or []))
        recovered_count = len(list((dashboard or {}).get("recovered_articles") or []))
        recent_fail_count = len(list((dashboard or {}).get("recent_fail_articles") or []))
        trend_summary = (dashboard or {}).get("trend_summary") or {}
        down_count = ArticleHealthService._safe_int(trend_summary.get("down_count"))

        if (
            high_risk_articles >= 5
            or avg_health_score < 60
            or persistent_count >= 3
        ):
            level = "danger"
            title = "今日 AI 风险偏高"
        elif (
            need_attention_articles >= 5
            or recent_fail_count >= 3
            or down_count >= 3
        ):
            level = "warning"
            title = "今日 AI 运营需要关注"
        elif (
            (recovered_count >= persistent_count and high_risk_articles == 0)
            or avg_health_score >= 85
        ):
            level = "good"
            title = "今日 AI 运营表现良好"
        else:
            level = "normal"
            title = "今日 AI 运营整体稳定"

        summary_text = (
            f"当前平均健康分 {avg_health_score}，高风险文章 {high_risk_articles} 篇，"
            f"需人工关注 {need_attention_articles} 篇，连续异常文章 {persistent_count} 篇，"
            f"恢复文章 {recovered_count} 篇。"
        )
        if level in ("danger", "warning"):
            summary_text += "建议优先处理风险文章。"
        elif level == "good":
            summary_text += "整体风险可控，可保持当前优化节奏。"

        highlights = [
            f"平均健康分：{avg_health_score}",
            f"高风险文章：{high_risk_articles}",
            f"需人工关注：{need_attention_articles}",
            f"连续异常文章：{persistent_count}",
            f"恢复文章：{recovered_count}",
            f"趋势下降文章：{down_count}",
        ]

        recommended_focus = []
        if high_risk_articles > 0:
            recommended_focus.append("优先处理高风险文章")
        if persistent_count > 0:
            recommended_focus.append("优先处理连续异常文章")
        if recent_fail_count > 0:
            recommended_focus.append("检查最近发布失败文章")
        if down_count > 0:
            recommended_focus.append("关注健康趋势下降文章")
        if recovered_count > 0:
            recommended_focus.append("复盘已恢复文章的优化路径")
        if not recommended_focus:
            recommended_focus.append("保持当前审核与终检节奏")

        return {
            "level": level,
            "title": title,
            "summary": summary_text,
            "highlights": highlights,
            "recommended_focus": recommended_focus[:5],
        }

    @staticmethod
    def build_ai_ops_conclusion(dashboard: dict) -> dict:
        """根据 Dashboard 当前盘面生成日报末尾的 AI 运营结论。"""
        if not dashboard:
            return {
                "risk_level": "normal",
                "title": "当前 AI 运营暂无明显异常",
                "summary": "暂无足够数据生成运营结论。",
                "top_issue": "暂无明显问题",
                "top_action": "保持当前审核与终检节奏",
            }

        summary = (dashboard or {}).get("summary") or {}
        ai_ops_score = (dashboard or {}).get("ai_ops_score") or {}
        score_trend = (dashboard or {}).get("ai_ops_score_trend") or {}
        persistent_items = list((dashboard or {}).get("persistent_risk_articles") or [])
        recovered_items = list((dashboard or {}).get("recovered_articles") or [])
        recent_fail_items = list((dashboard or {}).get("recent_fail_articles") or [])

        score_level = (ai_ops_score.get("level") or "").strip()
        trend_direction = (score_trend.get("trend_direction") or "").strip()
        score_change = ArticleHealthService._safe_int(score_trend.get("score_change"))
        high_risk_count = ArticleHealthService._safe_int(summary.get("high_risk_articles"))
        need_attention_count = ArticleHealthService._safe_int(summary.get("need_attention_articles"))

        if (
            score_level == "danger"
            or len(persistent_items) >= 3
            or (trend_direction == "down" and score_change <= -10)
        ):
            risk_level = "danger"
            title = "当前 AI 运营风险较高"
            summary_text = "当前存在连续异常文章，且 AI 运营评分出现下降趋势。"
        elif score_level == "warning" or high_risk_count > 0 or need_attention_count >= 5:
            risk_level = "warning"
            title = "当前 AI 运营存在一定风险"
            summary_text = "当前仍存在部分高风险文章，建议继续关注终检与发布情况。"
        elif score_level == "excellent" or len(recovered_items) > len(persistent_items):
            risk_level = "good"
            title = "当前 AI 运营恢复情况良好"
            summary_text = "近期恢复文章数量较多，整体风险正在改善。"
        else:
            risk_level = "normal"
            title = "当前 AI 运营整体稳定"
            summary_text = "当前 AI 运营整体稳定，未发现明显异常趋势。"

        if len(persistent_items) >= 3:
            top_issue = "连续异常文章较多"
        elif trend_direction == "down" and score_change < 0:
            top_issue = "AI 运营评分下降"
        elif high_risk_count > 0:
            top_issue = "高风险文章较多"
        elif len(recent_fail_items) >= 3:
            top_issue = "最近发布失败较多"
        else:
            top_issue = "暂无明显问题"

        if len(persistent_items) > 0 or high_risk_count > 0:
            top_action = "优先处理高风险与连续终检失败文章"
        elif len(recent_fail_items) > 0:
            top_action = "检查最近发布失败文章"
        elif trend_direction == "down":
            top_action = "关注健康趋势下降文章"
        else:
            top_action = "保持当前审核与终检节奏"

        return {
            "risk_level": risk_level,
            "title": title,
            "summary": summary_text,
            "top_issue": top_issue,
            "top_action": top_action,
        }

    @staticmethod
    def build_ai_ops_duty_mode(dashboard: dict) -> dict:
        """根据 Dashboard 当前风险盘面生成 AI 运营值班模式，只做只读状态分析。"""
        if not dashboard:
            return {
                "mode": "normal",
                "title": "AI 运营默认巡检模式",
                "description": "暂无足够数据生成值班模式。",
                "recommended_action": "保持当前审核与终检节奏即可。",
                "badge": "secondary",
            }

        summary = (dashboard or {}).get("summary") or {}
        ai_ops_score = (dashboard or {}).get("ai_ops_score") or {}
        score_trend = (dashboard or {}).get("ai_ops_score_trend") or {}
        persistent_count = len(list((dashboard or {}).get("persistent_risk_articles") or []))
        recovered_count = len(list((dashboard or {}).get("recovered_articles") or []))
        recent_fail_count = len(list((dashboard or {}).get("recent_fail_articles") or []))

        score_level = (ai_ops_score.get("level") or "").strip()
        trend_direction = (score_trend.get("trend_direction") or "").strip()
        score_change = ArticleHealthService._safe_int(score_trend.get("score_change"))
        high_risk_count = ArticleHealthService._safe_int(summary.get("high_risk_articles"))
        need_attention_count = ArticleHealthService._safe_int(summary.get("need_attention_articles"))

        if (
            score_level == "danger"
            or persistent_count >= 3
            or (trend_direction == "down" and score_change <= -10)
        ):
            return {
                "mode": "high_alert",
                "title": "AI 运营高危值班模式",
                "description": "当前存在较多连续异常文章，且 AI 运营评分明显下降。",
                "recommended_action": "建议立即重点处理高风险与连续终检失败文章。",
                "badge": "danger",
            }

        if high_risk_count > 0 or need_attention_count >= 5 or recent_fail_count >= 3:
            return {
                "mode": "focus",
                "title": "AI 运营重点关注模式",
                "description": "当前仍存在部分高风险与人工关注文章，需要重点巡检。",
                "recommended_action": "建议持续关注终检失败与发布失败文章。",
                "badge": "warning",
            }

        if recovered_count > persistent_count or score_level == "excellent":
            return {
                "mode": "recovery",
                "title": "AI 运营恢复观察模式",
                "description": "近期恢复文章数量较多，整体风险正在改善。",
                "recommended_action": "建议复盘恢复文章的优化路径并持续观察。",
                "badge": "success",
            }

        return {
            "mode": "normal",
            "title": "AI 运营稳定巡检模式",
            "description": "当前 AI 运营整体稳定，未发现明显异常。",
            "recommended_action": "保持当前审核与终检节奏即可。",
            "badge": "secondary",
        }

    @staticmethod
    def build_ai_ops_report_text(dashboard: dict) -> str:
        """把 Dashboard 摘要整理成可复制的 AI 运营日报纯文本。"""
        daily_summary = (dashboard or {}).get("daily_ai_ops_summary") or {}
        if not dashboard or not daily_summary:
            return (
                "【AI 公众号运营日报】\n\n"
                "今日 AI 运营状态：暂无足够数据\n\n"
                "核心指标：\n"
                "- 暂无数据\n\n"
                "今日建议：\n"
                "1. 保持当前审核与终检节奏"
            )

        title = (daily_summary.get("title") or "").strip() or "暂无足够数据"
        ai_ops_score = (dashboard or {}).get("ai_ops_score") or {}
        ai_ops_health_index = (dashboard or {}).get("ai_ops_health_index") or {}
        ai_ops_stability_index = (dashboard or {}).get("ai_ops_stability_index") or {}
        ai_ops_volatility_index = (dashboard or {}).get("ai_ops_volatility_index") or {}
        ai_ops_recovery_index = (dashboard or {}).get("ai_ops_recovery_index") or {}
        ai_ops_score_trend = (dashboard or {}).get("ai_ops_score_trend") or {}
        incident_feed = list((dashboard or {}).get("ai_ops_incident_feed") or [])
        ops_timeline = list((dashboard or {}).get("ai_ops_timeline") or [])
        priority_queue = list((dashboard or {}).get("ai_ops_priority_queue") or [])
        playbooks = list((dashboard or {}).get("ai_ops_playbooks") or [])
        root_cause_analysis = (dashboard or {}).get("ai_root_cause_analysis") or {}
        template_ops_analysis = (dashboard or {}).get("template_ops_analysis") or {}
        prompt_ops_analysis = (dashboard or {}).get("prompt_ops_analysis") or {}
        conclusion = (dashboard or {}).get("ai_ops_conclusion") or ArticleHealthService.build_ai_ops_conclusion(dashboard)
        duty_mode = (dashboard or {}).get("ai_ops_duty_mode") or ArticleHealthService.build_ai_ops_duty_mode(dashboard)
        duty_history = (dashboard or {}).get("ai_ops_duty_history_summary") or ArticleHealthService.build_ai_ops_duty_history_summary()
        highlights = list(daily_summary.get("highlights") or [])
        focus_items = list(daily_summary.get("recommended_focus") or ["保持当前审核与终检节奏"])[:5]
        risk_items = [
            item for item in list((dashboard or {}).get("ai_ops_suggestions") or [])
            if item.get("level") in ("danger", "warning")
        ][:5]

        lines = [
            "【AI 公众号运营日报】",
            "",
            f"今日 AI 运营状态：{title}",
            "",
            "AI 运营总评分：",
        ]
        lines.extend([
            "当前值班模式：",
            f"- {(duty_mode.get('title') or 'AI 运营默认巡检模式').strip() or 'AI 运营默认巡检模式'}",
            f"- {(duty_mode.get('recommended_action') or '保持当前审核与终检节奏即可。').strip() or '保持当前审核与终检节奏即可。'}",
            "",
        ])

        duty_recent_modes = list(duty_history.get("recent_modes") or [])
        duty_recent_text = " → ".join(ArticleHealthService._ai_status_label(mode) for mode in duty_recent_modes) if duty_recent_modes else "-"
        lines.extend([
            "值班模式变化：",
            f"- 当前模式：{ArticleHealthService._ai_status_label((duty_history.get('current_mode') or 'normal').strip() or 'normal')}",
            f"- 上次模式：{ArticleHealthService._ai_status_label((duty_history.get('previous_mode') or 'normal').strip() or 'normal')}",
            f"- 趋势：{ArticleHealthService._ai_status_label((duty_history.get('trend_direction') or 'stable').strip() or 'stable')}",
            f"- 轨迹：{duty_recent_text}",
            "",
        ])

        if ai_ops_score:
            lines.extend([
                f"- 当前评分：{ArticleHealthService._safe_int(ai_ops_score.get('score'))}",
                f"- 等级：{ArticleHealthService._ai_status_label((ai_ops_score.get('level') or '').strip() or '-')}",
                f"- 说明：{(ai_ops_score.get('summary') or '').strip() or '-'}",
            ])
        else:
            lines.append("- 暂无评分数据")

        lines.extend([
            "",
            "AI 运营评分趋势：",
        ])
        lines.extend([
            "AI 运营健康指数：",
        ])
        if ai_ops_health_index:
            lines.extend([
                f"- 指数：{ArticleHealthService._safe_int(ai_ops_health_index.get('health_index'))}",
                f"- 等级：{ArticleHealthService._ai_status_label((ai_ops_health_index.get('health_level') or '').strip() or '-')}",
                f"- 说明：{(ai_ops_health_index.get('summary') or '').strip() or '-'}",
                "",
            ])
        else:
            lines.extend(["- 暂无健康指数数据", ""])

        lines.extend([
            "AI 运营稳定性指数：",
        ])
        if ai_ops_stability_index:
            lines.extend([
                f"- 指数：{ArticleHealthService._safe_int(ai_ops_stability_index.get('stability_index'))}",
                f"- 等级：{ArticleHealthService._ai_status_label((ai_ops_stability_index.get('stability_level') or '').strip() or '-')}",
                f"- 说明：{(ai_ops_stability_index.get('summary') or '').strip() or '-'}",
                "",
            ])
        else:
            lines.extend(["- 暂无稳定性指数数据", ""])

        lines.extend([
            "AI 运营波动指数：",
        ])
        if ai_ops_volatility_index:
            lines.extend([
                f"- 指数：{ArticleHealthService._safe_int(ai_ops_volatility_index.get('volatility_index'))}",
                f"- 等级：{ArticleHealthService._ai_status_label((ai_ops_volatility_index.get('volatility_level') or '').strip() or '-')}",
                f"- 说明：{(ai_ops_volatility_index.get('summary') or '').strip() or '-'}",
                "",
            ])
        else:
            lines.extend(["- 暂无波动指数数据", ""])

        lines.extend([
            "AI 运营恢复力指数：",
        ])
        if ai_ops_recovery_index:
            lines.extend([
                f"- 指数：{ArticleHealthService._safe_int(ai_ops_recovery_index.get('recovery_index'))}",
                f"- 等级：{ArticleHealthService._ai_status_label((ai_ops_recovery_index.get('recovery_level') or '').strip() or '-')}",
                f"- 说明：{(ai_ops_recovery_index.get('summary') or '').strip() or '-'}",
                "",
            ])
        else:
            lines.extend(["- 暂无恢复力指数数据", ""])

        if ai_ops_score_trend:
            score_change = ArticleHealthService._safe_int(ai_ops_score_trend.get("score_change"))
            score_change_text = f"+{score_change}" if score_change > 0 else str(score_change)
            recent_scores = list(ai_ops_score_trend.get("recent_scores") or [])
            recent_scores_text = " → ".join(str(ArticleHealthService._safe_int(score)) for score in recent_scores) if recent_scores else "-"
            lines.extend([
                f"- 上次评分：{ArticleHealthService._safe_int(ai_ops_score_trend.get('previous_score'))}",
                f"- 当前评分：{ArticleHealthService._safe_int(ai_ops_score_trend.get('current_score'))}",
                f"- 变化：{score_change_text}",
                f"- 趋势：{ArticleHealthService._ai_status_label((ai_ops_score_trend.get('trend_direction') or '').strip() or '-')}",
                f"- 轨迹：{recent_scores_text}",
            ])
        else:
            lines.append("- 暂无趋势数据")

        lines.extend([
            "",
            "重要播报：",
        ])
        if incident_feed:
            for index, incident in enumerate(incident_feed[:5], start=1):
                incident_level = ArticleHealthService._ai_status_label((incident.get("level") or "info").strip() or "info")
                incident_title = (incident.get("title") or "未命名事件").strip() or "未命名事件"
                incident_message = (incident.get("message") or "").strip()
                if incident_message:
                    lines.append(f"{index}. [{incident_level}] {incident_title}： {incident_message}")
                else:
                    lines.append(f"{index}. [{incident_level}] {incident_title}：")
        else:
            lines.append("- 当前暂无重要播报")

        lines.extend([
            "",
            "最近状态时间线：",
        ])
        if ops_timeline:
            for index, timeline_item in enumerate(ops_timeline[:5], start=1):
                item_level = ArticleHealthService._ai_status_label((timeline_item.get("level") or "info").strip() or "info")
                item_title = (timeline_item.get("title") or "未命名状态").strip() or "未命名状态"
                lines.append(f"{index}. [{item_level}] {item_title}")
        else:
            lines.append("- 当前暂无 AI 运营状态时间线")
        lines.append("")

        lines.extend([
            "优先处理队列：",
        ])
        if priority_queue:
            for index, item in enumerate(priority_queue[:5], start=1):
                item_title = (item.get("title") or "未知文章").strip() or "未知文章"
                priority_level = ArticleHealthService._ai_status_label((item.get("priority_level") or "unknown").strip() or "unknown")
                priority_score = ArticleHealthService._safe_int(item.get("priority_score"))
                reasons = [
                    str(reason).strip()
                    for reason in (item.get("reasons") or [])
                    if str(reason).strip()
                ]
                reasons_joined = "、".join(reasons) if reasons else "暂无明确原因"
                lines.append(
                    f"{index}. 《{item_title}》｜优先级 {priority_level}｜分数 {priority_score}｜原因：{reasons_joined}"
                )
        else:
            lines.append("- 当前暂无优先处理文章")

        lines.extend([
            "",
            "今日重点处置建议：",
        ])
        if playbooks:
            for index, playbook in enumerate(playbooks[:5], start=1):
                playbook_title = (playbook.get("title") or "未命名处置建议").strip() or "未命名处置建议"
                actions = [
                    str(action).strip()
                    for action in (playbook.get("recommended_actions") or [])
                    if str(action).strip()
                ][:5]
                lines.append(f"{index}. {playbook_title}")
                lines.append("- 建议动作：")
                if actions:
                    lines.extend(f"  * {action}" for action in actions)
                else:
                    lines.append("  * 暂无明确建议动作")
        else:
            lines.append("- 当前暂无重点处置建议")

        root_cause_summary = (root_cause_analysis.get("summary") or "当前暂无明显集中性根因，建议保持常规巡检。").strip()
        root_cause_actions = [
            str(action).strip()
            for action in (root_cause_analysis.get("recommended_actions") or [])
            if str(action).strip()
        ][:5]
        lines.extend([
            "",
            "根因分析：",
            f"- {root_cause_summary}",
        ])
        if root_cause_actions:
            lines.append("- 建议优先检查" + "、".join(root_cause_actions))
        else:
            lines.append("- 当前暂无额外根因处置动作")

        template_summary = (template_ops_analysis.get("summary") or "当前暂无可用模板字段，暂无法生成模板级运营分析。").strip()
        high_risk_template_names = [
            (item.get("template") or "未知模板").strip() or "未知模板"
            for item in list(template_ops_analysis.get("high_risk_templates") or [])[:5]
        ]
        recovered_template_names = [
            (item.get("template") or "未知模板").strip() or "未知模板"
            for item in list(template_ops_analysis.get("template_recovery") or [])[:3]
        ]
        template_actions = [
            str(action).strip()
            for action in (template_ops_analysis.get("recommended_actions") or [])
            if str(action).strip()
        ][:5]
        lines.extend([
            "",
            "模板运营分析：",
            f"- {template_summary}",
        ])
        if high_risk_template_names:
            lines.append("- 高风险模板：" + "、".join(high_risk_template_names))
        if recovered_template_names:
            lines.append("- 当前恢复最佳模板：" + "、".join(recovered_template_names))
        if template_actions:
            lines.append("- 建议：" + "、".join(template_actions))
        else:
            lines.append("- 当前暂无额外模板运营动作")

        prompt_summary = (prompt_ops_analysis.get("summary") or "当前暂无可用于 Prompt 分析的数据。").strip()
        high_risk_prompt_names = [
            (item.get("prompt") or "未知 Prompt").strip() or "未知 Prompt"
            for item in list(prompt_ops_analysis.get("high_risk_prompts") or [])[:5]
        ]
        unstable_prompt_names = [
            (item.get("prompt") or "未知 Prompt").strip() or "未知 Prompt"
            for item in list(prompt_ops_analysis.get("unstable_prompts") or [])[:5]
        ]
        prompt_actions = [
            str(action).strip()
            for action in (prompt_ops_analysis.get("recommended_actions") or [])
            if str(action).strip()
        ][:5]
        lines.extend([
            "",
            "Prompt 运营分析：",
            f"- {prompt_summary}",
        ])
        if high_risk_prompt_names:
            lines.append("- 高风险 Prompt：" + "、".join(high_risk_prompt_names))
        if unstable_prompt_names:
            lines.append("- 不稳定 Prompt：" + "、".join(unstable_prompt_names))
        if prompt_actions:
            lines.append("- 建议：" + "、".join(prompt_actions))
        else:
            lines.append("- 当前暂无额外 Prompt 运营动作")

        lines.extend([
            "",
            "核心指标：",
        ])
        if highlights:
            lines.extend(f"- {item}" for item in highlights)
        else:
            lines.append("- 暂无数据")

        if risk_items:
            lines.extend(["", "重点风险："])
            for item in risk_items:
                risk_title = (item.get("title") or "").strip()
                risk_message = (item.get("message") or "").strip()
                if risk_title and risk_message:
                    lines.append(f"- {risk_title}，{risk_message}")
                elif risk_title:
                    lines.append(f"- {risk_title}")
                elif risk_message:
                    lines.append(f"- {risk_message}")

        lines.extend(["", "今日建议："])
        for index, item in enumerate(focus_items or ["保持当前审核与终检节奏"], start=1):
            lines.append(f"{index}. {item}")
        lines.extend([
            "",
            "运营结论：",
            f"- 风险等级：{ArticleHealthService._ai_status_label((conclusion.get('risk_level') or 'normal').strip() or 'normal')}",
            f"- 结论：{(conclusion.get('title') or '当前 AI 运营暂无明显异常').strip() or '当前 AI 运营暂无明显异常'}",
            f"- 核心问题：{(conclusion.get('top_issue') or '暂无明显问题').strip() or '暂无明显问题'}",
            f"- 当前建议动作：{(conclusion.get('top_action') or '保持当前审核与终检节奏').strip() or '保持当前审核与终检节奏'}",
        ])
        return "\n".join(lines)

    @staticmethod
    def build_ai_ops_incident_feed(dashboard: dict) -> list[dict]:
        """根据 Dashboard 当前状态生成 AI 运营异常播报事件流。"""
        if not dashboard:
            return []

        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        incidents = []

        for item in list((dashboard or {}).get("persistent_risk_articles") or []):
            title = (item.get("title") or "未知文章").strip()
            risk_tags = [str(tag).strip() for tag in item.get("risk_tags") or [] if str(tag).strip()]
            risk_tags_joined = "、".join(risk_tags) if risk_tags else "连续异常"
            incidents.append({
                "level": "danger",
                "title": "文章进入连续异常状态",
                "message": f"《{title}》存在：{risk_tags_joined}",
                "created_at": created_at,
            })

        for item in list((dashboard or {}).get("recovered_articles") or []):
            title = (item.get("title") or "未知文章").strip()
            previous_score = ArticleHealthService._safe_int(item.get("previous_score"))
            current_score = ArticleHealthService._safe_int(item.get("current_score"))
            incidents.append({
                "level": "success",
                "title": "文章风险已恢复",
                "message": f"《{title}》健康分从 {previous_score} 提升至 {current_score}",
                "created_at": created_at,
            })

        score_trend = (dashboard or {}).get("ai_ops_score_trend") or {}
        score_change = ArticleHealthService._safe_int(score_trend.get("score_change"))
        if score_change <= -10:
            incidents.append({
                "level": "danger",
                "title": "AI 运营评分明显下降",
                "message": f"当前评分下降 {score_change}",
                "created_at": created_at,
            })
        elif score_change >= 10:
            incidents.append({
                "level": "success",
                "title": "AI 运营评分明显提升",
                "message": f"当前评分提升 +{score_change}",
                "created_at": created_at,
            })

        for suggestion in list((dashboard or {}).get("ai_ops_suggestions") or []):
            if suggestion.get("level") not in ("danger", "warning"):
                continue
            incidents.append({
                "level": suggestion.get("level"),
                "title": (suggestion.get("title") or "").strip(),
                "message": (suggestion.get("message") or "").strip(),
                "created_at": created_at,
            })

        return sorted(
            incidents,
            key=lambda item: {"danger": 0, "warning": 1, "success": 2}.get(item.get("level"), 3),
        )[:10]

    @staticmethod
    def build_ai_ops_timeline(dashboard: dict, limit: int = 20) -> list[dict]:
        """聚合值班模式、评分趋势和异常播报，生成只读 AI 运营状态时间线。"""
        if not dashboard:
            return []
        try:
            safe_limit = max(1, min(int(limit or 20), 50))
        except (TypeError, ValueError):
            safe_limit = 20

        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timeline = []

        duty_history = (dashboard or {}).get("ai_ops_duty_history_summary") or {}
        duty_trend = (duty_history.get("trend_direction") or "").strip()
        current_mode = (duty_history.get("current_mode") or "normal").strip() or "normal"
        if duty_trend == "up" and current_mode == "high_alert":
            timeline.append({
                "type": "duty_mode",
                "level": "danger",
                "title": "进入 AI 高危值班模式",
                "message": f"当前值班模式切换为 {current_mode}",
                "created_at": created_at,
            })
        elif duty_trend == "down":
            timeline.append({
                "type": "duty_mode",
                "level": "success",
                "title": "AI 值班模式风险回落",
                "message": f"当前值班模式切换为 {current_mode}",
                "created_at": created_at,
            })

        score_trend = (dashboard or {}).get("ai_ops_score_trend") or {}
        score_change = ArticleHealthService._safe_int(score_trend.get("score_change"))
        if score_change <= -10:
            timeline.append({
                "type": "score_trend",
                "level": "danger",
                "title": "AI 运营评分明显下降",
                "message": f"AI 运营评分下降 {score_change}",
                "created_at": created_at,
            })
        elif score_change >= 10:
            timeline.append({
                "type": "score_trend",
                "level": "success",
                "title": "AI 运营评分明显提升",
                "message": f"AI 运营评分提升 +{score_change}",
                "created_at": created_at,
            })

        for incident in list((dashboard or {}).get("ai_ops_incident_feed") or []):
            timeline.append({
                "type": (incident.get("type") or "incident").strip() or "incident",
                "level": (incident.get("level") or "info").strip() or "info",
                "title": (incident.get("title") or "未命名事件").strip() or "未命名事件",
                "message": (incident.get("message") or "").strip(),
                "created_at": (incident.get("created_at") or created_at).strip() or created_at,
            })

        return sorted(
            timeline,
            key=lambda item: {"danger": 0, "warning": 1, "success": 2, "info": 3}.get(item.get("level"), 4),
        )[:safe_limit]

    @staticmethod
    def build_dashboard_snapshot_changes(dashboard: dict) -> dict:
        """对比当前 Dashboard 与最近一次快照，生成轻量变化摘要。"""
        current_snapshot = ArticleHealthService._build_dashboard_snapshot(dashboard)
        previous_snapshot = ArticleHealthService._read_ai_dashboard_snapshot()
        if not previous_snapshot:
            # 首次访问或旧文件损坏时，先落当前快照，页面变化值保持 0。
            ArticleHealthService.write_ai_dashboard_snapshot(dashboard)
            return {
                "last_snapshot_time": "",
                "high_risk_change": 0,
                "attention_change": 0,
                "avg_score_change": 0,
            }

        previous_summary = previous_snapshot.get("summary") or {}
        current_summary = current_snapshot["summary"]
        return {
            "last_snapshot_time": previous_snapshot.get("created_at", "") or "",
            "high_risk_change": ArticleHealthService._safe_int(current_summary.get("high_risk_articles")) - ArticleHealthService._safe_int(previous_summary.get("high_risk_articles")),
            "attention_change": ArticleHealthService._safe_int(current_summary.get("need_attention_articles")) - ArticleHealthService._safe_int(previous_summary.get("need_attention_articles")),
            "avg_score_change": ArticleHealthService._safe_int(current_summary.get("avg_health_score")) - ArticleHealthService._safe_int(previous_summary.get("avg_health_score")),
        }

    @staticmethod
    def write_ai_dashboard_snapshot(dashboard: dict) -> None:
        """把当前 Dashboard 摘要写入本地 JSON 快照文件，失败时只记日志。"""
        try:
            ArticleHealthService._write_ai_dashboard_snapshot(
                ArticleHealthService._build_dashboard_snapshot(dashboard)
            )
        except Exception as exc:
            logger.warning("AI Dashboard 快照写入失败：%s", exc)

    @staticmethod
    def _read_ai_dashboard_snapshot() -> dict:
        """读取最近一次 Dashboard 快照；缺失或损坏时安全返回空字典。"""
        if not os.path.exists(AI_DASHBOARD_SNAPSHOT_FILE_PATH):
            return {}
        try:
            with open(AI_DASHBOARD_SNAPSHOT_FILE_PATH, "r", encoding="utf-8") as snapshot_file:
                data = json.load(snapshot_file)
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.warning("AI Dashboard 快照读取失败，按首次访问处理：%s", exc)
            return {}

    @staticmethod
    def _write_ai_dashboard_snapshot(snapshot: dict) -> None:
        """落盘 Dashboard 快照，自动创建 data 目录。"""
        snapshot_dir = os.path.dirname(AI_DASHBOARD_SNAPSHOT_FILE_PATH)
        if snapshot_dir:
            os.makedirs(snapshot_dir, exist_ok=True)
        with open(AI_DASHBOARD_SNAPSHOT_FILE_PATH, "w", encoding="utf-8") as snapshot_file:
            json.dump(snapshot, snapshot_file, ensure_ascii=False, indent=2)

    @staticmethod
    def _build_dashboard_snapshot(dashboard: dict) -> dict:
        """从 Dashboard 稳定提取快照内容，避免页面对象结构外泄到文件。"""
        summary = (dashboard or {}).get("summary") or {}
        return {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "high_risk_articles": ArticleHealthService._safe_int(summary.get("high_risk_articles")),
                "need_attention_articles": ArticleHealthService._safe_int(summary.get("need_attention_articles")),
                "avg_health_score": ArticleHealthService._safe_int(summary.get("avg_health_score")),
            },
        }

    @staticmethod
    def _safe_int(value: Any) -> int:
        """把摘要数值收敛为整数，避免异常数据污染快照比较。"""
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _count_recent_high_risk_logs(logs: list[dict]) -> int:
        """统计最近日志里的高风险次数，兼容 review/preflight/workflow 三类结果。"""
        count = 0
        for log in logs[:10]:
            action_type = log.get("action_type")
            if action_type not in ("ai_review", "ai_preflight", "ai_workflow"):
                continue
            result = ArticleHealthService._parse_result_json(log.get("result_json"))
            if result.get("risk_level") == "high" or result.get("overall_risk") == "high":
                count += 1
        return count

    @staticmethod
    def _count_recent_preflight_failures(logs: list[dict]) -> int:
        """统计最近日志里的终检失败次数。"""
        count = 0
        for log in logs[:10]:
            if log.get("action_type") != "ai_preflight":
                continue
            result = ArticleHealthService._parse_result_json(log.get("result_json"))
            if result.get("pass_preflight") is False:
                count += 1
        return count

    @staticmethod
    def _count_recent_preflight_failures_before_latest_pass(logs: list[dict]) -> int:
        """统计最近一次终检通过之前，窗口内累计出现过多少次终检失败。"""
        seen_latest_pass = False
        failure_count = 0
        for log in logs[:10]:
            if log.get("action_type") != "ai_preflight":
                continue
            result = ArticleHealthService._parse_result_json(log.get("result_json"))
            if not seen_latest_pass:
                if result.get("pass_preflight") is True:
                    seen_latest_pass = True
                continue
            if result.get("pass_preflight") is False:
                failure_count += 1
        return failure_count

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
            "persistent_risk_articles": [],
            "recovered_articles": [],
            "ai_ops_priority_queue": [],
            "ai_ops_playbooks": [],
            "ai_root_cause_analysis": {
                "root_causes": [],
                "top_templates": [],
                "top_failure_patterns": [],
                "summary": "当前暂无明显集中性根因，建议保持常规巡检。",
                "recommended_actions": [],
            },
            "template_ops_analysis": ArticleHealthService._empty_template_ops_analysis(),
            "prompt_ops_analysis": ArticleHealthService._empty_prompt_ops_analysis(),
            "ai_ops_score": {
                "score": 100,
                "level": "good",
                "summary": "当前暂无足够数据，默认按稳定状态处理。",
                "score_breakdown": [],
            },
            "ai_ops_health_index": {
                "health_index": 80,
                "health_level": "healthy",
                "summary": "暂无足够数据生成 AI 运营健康指数。",
                "breakdown": [],
            },
            "ai_ops_stability_index": {
                "stability_index": 80,
                "stability_level": "stable",
                "summary": "暂无足够数据生成 AI 运营稳定性指数。",
                "breakdown": [],
            },
            "ai_ops_volatility_index": {
                "volatility_index": 20,
                "volatility_level": "stable",
                "summary": "暂无足够数据生成 AI 运营波动指数。",
                "breakdown": [],
            },
            "ai_ops_recovery_index": {
                "recovery_index": 60,
                "recovery_level": "normal",
                "summary": "暂无足够数据生成 AI 运营恢复力指数。",
                "breakdown": [],
            },
            "ai_ops_score_trend": {
                "current_score": 100,
                "previous_score": 100,
                "score_change": 0,
                "trend_direction": "stable",
                "recent_scores": [100],
                "summary": "当前暂无足够历史数据。",
            },
            "ai_ops_suggestions": [],
            "ai_ops_incident_feed": [],
            "ai_ops_timeline": [],
            "ai_ops_conclusion": {
                "risk_level": "normal",
                "title": "当前 AI 运营暂无明显异常",
                "summary": "暂无足够数据生成运营结论。",
                "top_issue": "暂无明显问题",
                "top_action": "保持当前审核与终检节奏",
            },
            "ai_ops_duty_mode": {
                "mode": "normal",
                "title": "AI 运营默认巡检模式",
                "description": "暂无足够数据生成值班模式。",
                "recommended_action": "保持当前审核与终检节奏即可。",
                "badge": "secondary",
            },
            "ai_ops_duty_history_summary": {
                "current_mode": "normal",
                "previous_mode": "normal",
                "recent_modes": ["normal"],
                "summary": "当前暂无足够值班历史数据。",
                "trend_direction": "stable",
            },
            "daily_ai_ops_summary": {
                "level": "normal",
                "title": "今日 AI 运营暂无异常",
                "summary": "当前暂无足够数据生成运营摘要。",
                "highlights": [],
                "recommended_focus": ["保持当前审核与终检节奏"],
            },
            "ai_ops_report_text": (
                "【AI 公众号运营日报】\n\n"
                "今日 AI 运营状态：暂无足够数据\n\n"
                "核心指标：\n"
                "- 暂无数据\n\n"
                "今日建议：\n"
                "1. 保持当前审核与终检节奏"
            ),
            "trend_summary": {
                "up_count": 0,
                "stable_count": 0,
                "down_count": 0,
            },
            "filters": safe_filters,
            "filtered_articles": [],
        }
