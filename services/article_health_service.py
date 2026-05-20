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
        "strong": "强",
        "weak": "较弱",
        "unstable": "不稳定",
        "unknown": "未知",
        "risky": "有风险",
        "success": "良好",
        "secondary": "建议",
        "info": "信息",
        "up": "上升",
        "down": "下降",
        "all_safe": "全部安全",
        "need_attention": "需要关注",
        "blocked": "存在禁止动作",
        "safe": "安全",
        "review_required": "需要复核",
        "pending": "待批准",
        "mixed": "混合状态",
        "attention": "需关注",
        "degraded": "降级",
        "idle": "空闲",
        "recovery_ready": "可恢复",
        "recovery_needed": "需要恢复",
        "urgent_recovery": "紧急恢复",
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
            dashboard.update(ArticleHealthService.build_ai_dashboard_centers(dashboard))
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
    def build_ai_dashboard_centers(dashboard: dict) -> dict:
        """从现有 Dashboard 数据构建只读运营中心模块。"""
        dashboard = dashboard or {}
        summary = dashboard.get("summary") or {}
        ops_score = dashboard.get("ai_ops_score") or {}
        health_index = dashboard.get("ai_ops_health_index") or {}
        stability_index = dashboard.get("ai_ops_stability_index") or {}
        volatility_index = dashboard.get("ai_ops_volatility_index") or {}
        recovery_index = dashboard.get("ai_ops_recovery_index") or {}
        trend = dashboard.get("ai_ops_score_trend") or {}
        conclusion = dashboard.get("ai_ops_conclusion") or {}
        daily = dashboard.get("daily_ai_ops_summary") or {}
        root_cause = dashboard.get("ai_root_cause_analysis") or {}
        template_ops = dashboard.get("template_ops_analysis") or {}
        prompt_ops = dashboard.get("prompt_ops_analysis") or {}
        playbooks = list(dashboard.get("ai_ops_playbooks") or [])
        suggestions = list(dashboard.get("ai_ops_suggestions") or [])
        incidents = list(dashboard.get("ai_ops_incident_feed") or [])
        persistent = list(dashboard.get("persistent_risk_articles") or [])
        recovered = list(dashboard.get("recovered_articles") or [])
        timeline = list(dashboard.get("ai_ops_timeline") or [])

        high_risk_count = ArticleHealthService._safe_int(summary.get("high_risk_articles"))
        attention_count = ArticleHealthService._safe_int(summary.get("need_attention_articles"))
        avg_score = ArticleHealthService._safe_int(summary.get("avg_health_score"))
        raw_score = ops_score.get("score")
        score = 100 if raw_score is None else ArticleHealthService._safe_int(raw_score)
        risk_level = "danger" if high_risk_count else ("warning" if attention_count else "success")

        governance_actions = []
        for playbook in playbooks[:5]:
            governance_actions.append({
                "title": playbook.get("title") or "AI 治理动作",
                "priority": playbook.get("priority") or playbook.get("level") or "normal",
                "summary": playbook.get("summary") or "",
                "recommended_actions": list(playbook.get("recommended_actions") or [])[:3],
            })
        if not governance_actions and suggestions:
            for item in suggestions[:5]:
                governance_actions.append({
                    "title": item.get("title") or "AI 治理动作",
                    "priority": item.get("level") or "normal",
                    "summary": item.get("message") or item.get("summary") or "",
                    "recommended_actions": [item.get("action") or item.get("suggestion") or "保持人工复核节奏"],
                })

        runtime_observability = ArticleHealthService.build_ai_runtime_observability_center(dashboard)
        runtime_alert = ArticleHealthService.build_ai_runtime_alert_center(dashboard, runtime_observability)
        autoops_control_tower = ArticleHealthService.build_ai_autoops_control_tower(dashboard)
        action_review = ArticleHealthService.build_ai_autoops_action_review_center(dashboard, autoops_control_tower)
        execution_sandbox = ArticleHealthService.build_ai_execution_sandbox_center(dashboard, action_review)
        approval_pipeline = ArticleHealthService.build_ai_approval_pipeline_center(dashboard, execution_sandbox)
        approval_audit = ArticleHealthService.build_ai_approval_audit_center(dashboard, approval_pipeline)
        runtime_recovery = ArticleHealthService.build_ai_runtime_recovery_center(
            dashboard,
            runtime_observability,
            runtime_alert,
            approval_audit,
        )
        runtime_incident = ArticleHealthService.build_ai_runtime_incident_center(
            dashboard,
            runtime_observability,
            runtime_alert,
            runtime_recovery,
            approval_audit,
        )
        knowledge_base = {
            "summary": "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。当前沉淀模板、提示词与根因分析中的可复用知识。",
            "knowledge_items": [
                {"label": "模板样本", "value": len(template_ops.get("template_health") or [])},
                {"label": "提示词样本", "value": len(prompt_ops.get("prompt_health") or [])},
                {"label": "风险模式", "value": len(root_cause.get("top_failure_patterns") or [])},
            ],
            "recommendations": list(template_ops.get("recommended_actions") or [])[:3]
                + list(prompt_ops.get("recommended_actions") or [])[:3],
        }
        runtime_postmortem = ArticleHealthService.build_ai_runtime_postmortem_center(
            dashboard,
            runtime_incident,
            runtime_recovery,
            approval_audit,
            knowledge_base,
        )
        sop_center = dashboard.get("ai_sop_center") or {}
        runtime_learning = ArticleHealthService.build_ai_runtime_learning_center(
            dashboard,
            runtime_observability,
            runtime_alert,
            runtime_recovery,
            runtime_incident,
            runtime_postmortem,
            knowledge_base,
            sop_center,
        )
        governance_center = {
            "summary": "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。当前基于风险事件、处置方案与人工关注队列生成治理状态。",
            "level": risk_level,
            "metrics": [
                {"label": "风险事件", "value": len(incidents)},
                {"label": "处置方案", "value": len(playbooks)},
                {"label": "治理动作", "value": len(governance_actions)},
            ],
            "alerts": incidents[:5],
        }
        governance_action_plan = {
            "summary": "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。",
            "actions": governance_actions,
        }
        runtime_knowledge_sync = ArticleHealthService.build_ai_runtime_knowledge_sync_center(
            dashboard,
            runtime_learning,
            knowledge_base,
            sop_center,
            governance_center,
            governance_action_plan,
        )
        runtime_weekly_review = ArticleHealthService.build_ai_runtime_weekly_review_center(
            dashboard,
            runtime_observability,
            runtime_alert,
            runtime_recovery,
            runtime_incident,
            runtime_postmortem,
            runtime_learning,
            runtime_knowledge_sync,
        )
        runtime_feedback_loop = ArticleHealthService.build_ai_runtime_feedback_loop_center(
            dashboard,
            runtime_weekly_review,
            runtime_knowledge_sync,
            runtime_learning,
            runtime_postmortem,
            sop_center,
            governance_center,
        )
        runtime_evolution = ArticleHealthService.build_ai_runtime_evolution_center(
            dashboard,
            runtime_feedback_loop,
            runtime_weekly_review,
            runtime_learning,
            runtime_knowledge_sync,
            knowledge_base,
            sop_center,
            governance_center,
        )
        runtime_orchestrator = ArticleHealthService.build_ai_runtime_orchestrator_center(
            dashboard,
            runtime_evolution,
            runtime_feedback_loop,
            runtime_weekly_review,
            runtime_knowledge_sync,
            autoops_control_tower,
            dashboard.get("ai_command_center") or {},
            sop_center,
            governance_action_plan,
        )
        runtime_control_policy = ArticleHealthService.build_ai_runtime_control_policy_center(
            dashboard,
            runtime_orchestrator,
            runtime_evolution,
            runtime_feedback_loop,
            dashboard.get("ai_command_center") or {},
            autoops_control_tower,
            action_review,
            execution_sandbox,
            approval_pipeline,
            approval_audit,
        )
        runtime_policy_gate = ArticleHealthService.build_ai_runtime_policy_gate_center(
            dashboard,
            runtime_control_policy,
            runtime_orchestrator,
            action_review,
            execution_sandbox,
            approval_pipeline,
            approval_audit,
        )

        return {
            "ai_runtime_observability_center": runtime_observability,
            "ai_runtime_alert_center": runtime_alert,
            "ai_autoops_control_tower": autoops_control_tower,
            "ai_autoops_action_review_center": action_review,
            "ai_execution_sandbox_center": execution_sandbox,
            "ai_approval_pipeline_center": approval_pipeline,
            "ai_approval_audit_center": approval_audit,
            "ai_runtime_recovery_center": runtime_recovery,
            "ai_runtime_incident_center": runtime_incident,
            "ai_runtime_postmortem_center": runtime_postmortem,
            "ai_runtime_learning_center": runtime_learning,
            "ai_runtime_knowledge_sync_center": runtime_knowledge_sync,
            "ai_runtime_weekly_review_center": runtime_weekly_review,
            "ai_runtime_feedback_loop_center": runtime_feedback_loop,
            "ai_runtime_evolution_center": runtime_evolution,
            "ai_runtime_orchestrator_center": runtime_orchestrator,
            "ai_runtime_control_policy_center": runtime_control_policy,
            "ai_runtime_policy_gate_center": runtime_policy_gate,
            "ai_decision_brief": {
                "level": risk_level,
                "title": conclusion.get("title") or daily.get("title") or "AI 决策简报",
                "summary": conclusion.get("summary") or daily.get("summary") or "当前暂无足够数据生成 AI 决策简报。",
                "top_issue": conclusion.get("top_issue") or "当前暂无明显问题",
                "top_action": conclusion.get("top_action") or "保持当前审核与终检节奏",
                "metrics": [
                    {"label": "AI 运营评分", "value": score},
                    {"label": "高风险文章", "value": high_risk_count},
                    {"label": "人工关注", "value": attention_count},
                    {"label": "平均健康分", "value": avg_score},
                ],
            },
            "ai_memory_center": {
                "summary": "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。当前汇总持续风险、恢复案例与最近运营事件。",
                "memory_items": [
                    {"label": "持续风险", "value": len(persistent), "level": "danger" if persistent else "success"},
                    {"label": "恢复案例", "value": len(recovered), "level": "success" if recovered else "secondary"},
                    {"label": "最近事件", "value": len(timeline), "level": "warning" if timeline else "secondary"},
                ],
                "recent_items": persistent[:5] or recovered[:5],
            },
            "ai_memory_insights": {
                "summary": root_cause.get("summary") or "当前暂无集中性运营风险洞察。",
                "insights": list(root_cause.get("root_causes") or [])[:5],
                "patterns": list(root_cause.get("top_failure_patterns") or [])[:5],
            },
            "ai_knowledge_base": knowledge_base,
            "ai_governance_center": governance_center,
            "ai_governance_action_plan": governance_action_plan,
            "ai_strategy_center": {
                "summary": "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。当前基于评分、稳定性、波动与恢复力生成运营策略视图。",
                "strategy": [
                    {"label": "健康指数", "value": health_index.get("health_index", 80), "level": health_index.get("health_level", "healthy")},
                    {"label": "稳定性指数", "value": stability_index.get("stability_index", 80), "level": stability_index.get("stability_level", "stable")},
                    {"label": "波动指数", "value": volatility_index.get("volatility_index", 20), "level": volatility_index.get("volatility_level", "stable")},
                    {"label": "恢复力指数", "value": recovery_index.get("recovery_index", 60), "level": recovery_index.get("recovery_level", "normal")},
                ],
            },
            "ai_strategy_execution_plan": {
                "summary": trend.get("summary") or "当前暂无足够历史数据生成策略执行趋势。",
                "steps": list(daily.get("recommended_focus") or [])[:5],
                "score_change": trend.get("score_change", 0),
                "trend_direction": trend.get("trend_direction", "stable"),
            },
            "ai_simulation_center": {
                "summary": "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。当前基于只读指标进行策略模拟推演。",
                "scenarios": [
                    {"name": "保持当前节奏", "impact": "风险保持稳定", "level": "success"},
                    {"name": "优先处理高风险文章", "impact": f"覆盖 {high_risk_count} 篇高风险文章", "level": "danger" if high_risk_count else "secondary"},
                    {"name": "加强人工关注队列", "impact": f"覆盖 {attention_count} 个关注对象", "level": "warning" if attention_count else "secondary"},
                ],
            },
            "ai_simulation_history_summary": {
                "summary": "当前基于已有评分历史与运营时间线汇总策略模拟历史。",
                "recent_scores": list(trend.get("recent_scores") or [])[-8:],
                "recent_events": timeline[:5],
            },
        }

    @staticmethod
    def build_ai_runtime_policy_gate_center(
        dashboard: dict,
        runtime_control_policy: dict | None = None,
        runtime_orchestrator: dict | None = None,
        action_review: dict | None = None,
        execution_sandbox: dict | None = None,
        approval_pipeline: dict | None = None,
        approval_audit: dict | None = None,
    ) -> dict:
        """构建只读 AI 运行时策略闸门中心，不执行任何放行或阻断动作。"""
        dashboard = dashboard or {}
        runtime_control_policy = runtime_control_policy or {}
        runtime_orchestrator = runtime_orchestrator or {}
        action_review = action_review or {}
        execution_sandbox = execution_sandbox or {}
        approval_pipeline = approval_pipeline or {}
        approval_audit = approval_audit or {}

        policy_status = runtime_control_policy.get("policy_status") or "idle"
        orchestrator_status = runtime_orchestrator.get("orchestrator_status") or "idle"
        approval_status = approval_pipeline.get("approval_status") or "healthy"
        audit_status = approval_audit.get("audit_status") or "healthy"

        policy_allowed = list(runtime_control_policy.get("allowed_actions") or [])
        policy_restricted = list(runtime_control_policy.get("restricted_actions") or [])
        policy_forbidden = list(runtime_control_policy.get("forbidden_actions") or [])
        policy_manual = list(runtime_control_policy.get("manual_review_required") or [])
        policy_recommended = list(runtime_control_policy.get("recommended_actions") or [])
        orchestrator_blocked = list(runtime_orchestrator.get("blocked_dependencies") or [])
        orchestrator_actions = list(runtime_orchestrator.get("system_recommended_actions") or [])
        safe_actions = list(action_review.get("safe_actions") or [])
        requires_confirmation = list(action_review.get("requires_confirmation") or [])
        risky_actions = list(action_review.get("risky_actions") or [])
        blocked_actions = list(action_review.get("blocked_actions") or [])
        recommended_to_execute = list(execution_sandbox.get("recommended_to_execute") or [])
        not_recommended = list(execution_sandbox.get("not_recommended") or [])
        risk_warnings = list(execution_sandbox.get("risk_warnings") or [])
        pending = list(approval_pipeline.get("pending") or [])
        stale_pending = list(approval_audit.get("stale_pending") or [])
        risky_pending = list(approval_audit.get("risky_pending") or [])

        def normalize_items(items: list, item_type: str, fallback_title: str, fallback_summary: str) -> list[dict]:
            normalized = []
            for item in items:
                if isinstance(item, dict):
                    normalized.append({
                        "type": item.get("type") or item_type,
                        "title": item.get("title") or item.get("name") or fallback_title,
                        "summary": item.get("summary") or item.get("reason") or item.get("message") or fallback_summary,
                    })
                else:
                    normalized.append({"type": item_type, "title": str(item), "summary": fallback_summary})
            return normalized

        forbidden_actions = normalize_items(
            policy_forbidden + blocked_actions + not_recommended,
            "forbid",
            "禁止前进动作",
            "策略闸门判定该动作不得继续前进。",
        )[:6]
        delayed_actions = normalize_items(
            policy_restricted + risky_actions + risk_warnings + orchestrator_blocked,
            "delay",
            "延迟处理动作",
            "该动作需要等待风险或依赖条件解除后再推进。",
        )[:6]
        manual_confirmation_actions = normalize_items(
            policy_manual + requires_confirmation + pending + stale_pending + risky_pending,
            "manual",
            "需要人工确认动作",
            "该动作必须经过人工确认后才能继续。",
        )[:6]
        allowed_forward_actions = normalize_items(
            policy_allowed + safe_actions + recommended_to_execute,
            "allow",
            "允许前进动作",
            "该动作可进入人工确认后的前进队列。",
        )[:6]

        gate_reasons = []
        if forbidden_actions:
            gate_reasons.append({"type": "forbid", "title": "存在禁止动作", "summary": "策略闸门发现禁止或不推荐动作，需阻断自动前进。"})
        if delayed_actions:
            gate_reasons.append({"type": "delay", "title": "存在延迟条件", "summary": "策略闸门发现风险、沙箱警告或依赖阻塞。"})
        if manual_confirmation_actions:
            gate_reasons.append({"type": "manual", "title": "需要人工确认", "summary": "存在待批准、待复核或审计关注项。"})
        if policy_status in {"paused", "emergency_stop"}:
            gate_reasons.append({"type": "gate", "title": "控制策略要求暂停", "summary": "上游控制策略要求暂停或紧急停止。"})
        if orchestrator_status in {"blocked", "escalation_needed"}:
            gate_reasons.append({"type": "gate", "title": "编排中心存在阻塞", "summary": "运行时编排中心存在阻塞依赖或升级建议。"})

        if policy_status == "emergency_stop" or forbidden_actions:
            gate_status = "blocked"
        elif policy_status == "paused" or delayed_actions:
            gate_status = "delayed"
        elif manual_confirmation_actions or approval_status in {"pending", "mixed"} or audit_status in {"attention", "risky"}:
            gate_status = "manual_required"
        elif allowed_forward_actions or policy_status in {"open", "guarded"}:
            gate_status = "guarded" if policy_status == "guarded" else "open"
        else:
            gate_status = "idle"

        global_gate = {
            "type": "gate",
            "title": "全局运行时策略闸门",
            "status": gate_status,
            "summary": "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。",
        }

        recommended_actions = []
        if gate_status == "blocked":
            recommended_actions.append("先处理禁止动作和阻断原因，暂不推进相关自动运营动作。")
        if gate_status == "delayed":
            recommended_actions.append("延迟处理存在风险或依赖阻塞的动作，等待人工复核。")
        if gate_status == "manual_required":
            recommended_actions.append("优先完成人工确认、批准流和审计关注项。")
        recommended_actions.extend(policy_recommended[:4])
        recommended_actions.extend(orchestrator_actions[:3])
        if not recommended_actions:
            recommended_actions.append("当前保持只读观察，不自动放行任何动作。")

        return {
            "gate_status": gate_status,
            "global_gate": global_gate,
            "allowed_forward_actions": allowed_forward_actions,
            "manual_confirmation_actions": manual_confirmation_actions,
            "delayed_actions": delayed_actions,
            "forbidden_actions": forbidden_actions,
            "gate_reasons": gate_reasons,
            "gate_summary": (
                "当前暂无运行时策略闸门数据。"
                if gate_status == "idle"
                else "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。当前已根据控制策略、编排、沙箱和批准流形成只读闸门视图。"
            ),
            "recommended_actions": recommended_actions[:8],
        }

    @staticmethod
    def build_ai_runtime_control_policy_center(
        dashboard: dict,
        runtime_orchestrator: dict | None = None,
        runtime_evolution: dict | None = None,
        runtime_feedback_loop: dict | None = None,
        command_center: dict | None = None,
        autoops_control_tower: dict | None = None,
        action_review: dict | None = None,
        execution_sandbox: dict | None = None,
        approval_pipeline: dict | None = None,
        approval_audit: dict | None = None,
    ) -> dict:
        """构建只读 AI 运行时控制策略中心，不执行审核、发布或 Agent 动作。"""
        dashboard = dashboard or {}
        runtime_orchestrator = runtime_orchestrator or {}
        runtime_evolution = runtime_evolution or {}
        runtime_feedback_loop = runtime_feedback_loop or {}
        command_center = command_center or {}
        autoops_control_tower = autoops_control_tower or {}
        action_review = action_review or {}
        execution_sandbox = execution_sandbox or {}
        approval_pipeline = approval_pipeline or {}
        approval_audit = approval_audit or {}

        orchestrator_status = runtime_orchestrator.get("orchestrator_status") or "idle"
        evolution_status = runtime_evolution.get("evolution_status") or "empty"
        feedback_status = runtime_feedback_loop.get("feedback_status") or "empty"
        audit_status = approval_audit.get("audit_status") or "healthy"
        review_status = action_review.get("review_status") or "all_safe"
        sandbox_status = execution_sandbox.get("sandbox_status") or "safe"
        approval_status = approval_pipeline.get("approval_status") or "healthy"

        safe_actions = list(action_review.get("safe_actions") or [])
        requires_confirmation = list(action_review.get("requires_confirmation") or [])
        risky_actions = list(action_review.get("risky_actions") or [])
        blocked_actions = list(action_review.get("blocked_actions") or [])
        recommended_to_execute = list(execution_sandbox.get("recommended_to_execute") or [])
        not_recommended = list(execution_sandbox.get("not_recommended") or [])
        risk_warnings = list(execution_sandbox.get("risk_warnings") or [])
        stale_pending = list(approval_audit.get("stale_pending") or [])
        risky_pending = list(approval_audit.get("risky_pending") or [])
        feedback_gaps = list(runtime_feedback_loop.get("feedback_gaps") or [])
        blocked_dependencies = list(runtime_orchestrator.get("blocked_dependencies") or [])
        system_recommended_actions = list(runtime_orchestrator.get("system_recommended_actions") or [])
        control_actions = list(autoops_control_tower.get("recommended_actions") or autoops_control_tower.get("actions") or [])
        command_actions = list(command_center.get("recommended_actions") or command_center.get("actions") or [])

        forbidden_actions = []
        for item in (blocked_actions + not_recommended)[:6]:
            if isinstance(item, dict):
                forbidden_actions.append({
                    "type": "forbid",
                    "title": item.get("title") or item.get("name") or "禁止自动执行动作",
                    "summary": item.get("summary") or item.get("reason") or "该动作需要禁止自动执行",
                })
            else:
                forbidden_actions.append({"type": "forbid", "title": str(item), "summary": "该动作需要禁止自动执行"})

        restricted_actions = []
        for item in (risky_actions + risk_warnings + blocked_dependencies)[:6]:
            if isinstance(item, dict):
                restricted_actions.append({
                    "type": "restrict",
                    "title": item.get("title") or item.get("name") or "受限动作",
                    "summary": item.get("summary") or item.get("reason") or "该动作需要限制执行范围",
                })
            else:
                restricted_actions.append({"type": "restrict", "title": str(item), "summary": "该动作需要限制执行范围"})

        manual_review_required = []
        for item in (requires_confirmation + stale_pending + risky_pending)[:6]:
            if isinstance(item, dict):
                manual_review_required.append({
                    "type": "review",
                    "title": item.get("title") or item.get("name") or "需要人工复核",
                    "summary": item.get("summary") or item.get("reason") or "该动作需要人工复核后再推进",
                })
            else:
                manual_review_required.append({"type": "review", "title": str(item), "summary": "该动作需要人工复核后再推进"})

        allowed_actions = []
        for item in (safe_actions + recommended_to_execute + control_actions + command_actions)[:6]:
            if isinstance(item, dict):
                allowed_actions.append({
                    "type": "allow",
                    "title": item.get("title") or item.get("name") or "允许动作",
                    "summary": item.get("summary") or item.get("message") or "该动作可进入人工确认后的执行准备",
                })
            else:
                allowed_actions.append({"type": "allow", "title": str(item), "summary": "该动作可进入人工确认后的执行准备"})

        pause_policies = []
        if orchestrator_status in {"blocked", "escalation_needed"}:
            pause_policies.append({"type": "pause", "title": "阻塞依赖暂停策略", "summary": "存在阻塞或升级事项时，暂停相关自动运营动作。"})
        if audit_status in {"attention", "risky", "blocked"} or risky_pending:
            pause_policies.append({"type": "pause", "title": "批准审计暂停策略", "summary": "批准审计存在风险时，暂停高风险动作推进。"})

        recovery_policies = []
        if evolution_status in {"risky", "stagnant"} or feedback_status in {"weak_loop", "empty"}:
            recovery_policies.append({"type": "recovery", "title": "运行时恢复策略", "summary": "优先处理反馈闭环和进化风险，再恢复扩展动作。"})
        if risk_warnings:
            recovery_policies.append({"type": "recovery", "title": "沙箱风险恢复策略", "summary": "先复核沙箱风险警告，再决定是否继续推进。"})

        growth_policies = []
        if not (forbidden_actions or restricted_actions or manual_review_required):
            growth_policies.append({"type": "growth", "title": "稳态增长策略", "summary": "当前未发现明显限制项，可保持低风险运营增长节奏。"})
        elif allowed_actions:
            growth_policies.append({"type": "growth", "title": "受控增长策略", "summary": "仅允许低风险动作进入人工确认后的增长尝试。"})

        if orchestrator_status == "escalation_needed" or forbidden_actions:
            policy_status = "emergency_stop" if forbidden_actions and (risky_pending or blocked_dependencies) else "paused"
        elif restricted_actions or manual_review_required:
            policy_status = "restricted"
        elif pause_policies:
            policy_status = "guarded"
        elif allowed_actions or growth_policies:
            policy_status = "open"
        else:
            policy_status = "idle"

        global_policy = {
            "type": "restrict" if policy_status in {"restricted", "paused", "emergency_stop"} else "allow",
            "title": "全局运行时控制策略",
            "summary": "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。",
            "status": policy_status,
        }

        recommended_actions = []
        if forbidden_actions:
            recommended_actions.append("禁止高风险动作自动推进，先完成人工复核。")
        if restricted_actions:
            recommended_actions.append("限制受控动作范围，并保留人工确认节点。")
        if manual_review_required:
            recommended_actions.append("优先处理需要人工复核的动作与批准项。")
        recommended_actions.extend(system_recommended_actions[:4])
        if not recommended_actions:
            recommended_actions.append("当前保持只读观察，不自动执行任何控制策略。")

        return {
            "policy_status": policy_status,
            "global_policy": global_policy,
            "allowed_actions": allowed_actions[:6],
            "restricted_actions": restricted_actions[:6],
            "forbidden_actions": forbidden_actions[:6],
            "manual_review_required": manual_review_required[:6],
            "pause_policies": pause_policies,
            "recovery_policies": recovery_policies,
            "growth_policies": growth_policies,
            "policy_summary": (
                "当前暂无运行时控制策略。"
                if policy_status == "idle"
                else "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。当前已根据编排、复核、沙箱和批准审计结果形成只读控制策略。"
            ),
            "recommended_actions": recommended_actions[:8],
        }

    @staticmethod
    def build_ai_runtime_orchestrator_center(
        dashboard: dict,
        runtime_evolution: dict | None = None,
        runtime_feedback_loop: dict | None = None,
        runtime_weekly_review: dict | None = None,
        runtime_knowledge_sync: dict | None = None,
        autoops_control_tower: dict | None = None,
        command_center: dict | None = None,
        sop_center: dict | None = None,
        governance_action_plan: dict | None = None,
    ) -> dict:
        """构建只读 AI 运行时编排中心，不执行任何自动动作。"""
        dashboard = dashboard or {}
        runtime_evolution = runtime_evolution or {}
        runtime_feedback_loop = runtime_feedback_loop or {}
        runtime_weekly_review = runtime_weekly_review or {}
        runtime_knowledge_sync = runtime_knowledge_sync or {}
        autoops_control_tower = autoops_control_tower or {}
        command_center = command_center or {}
        sop_center = sop_center or {}
        governance_action_plan = governance_action_plan or {}

        top_risks = list(runtime_weekly_review.get("top_risks") or [])
        next_week_focus = list(runtime_weekly_review.get("next_week_focus") or [])
        weekly_actions = list(runtime_weekly_review.get("recommended_actions") or [])
        sync_gaps = list(runtime_knowledge_sync.get("sync_gaps") or [])
        sync_actions = list(runtime_knowledge_sync.get("recommended_actions") or [])
        feedback_gaps = list(runtime_feedback_loop.get("feedback_gaps") or [])
        feedback_actions = list(runtime_feedback_loop.get("recommended_actions") or [])
        evolution_risks = list(runtime_evolution.get("evolution_risks") or [])
        evolution_actions = list(runtime_evolution.get("long_term_recommendations") or [])
        governance_actions = list(governance_action_plan.get("actions") or [])
        sop_items = list(sop_center.get("sop_items") or sop_center.get("items") or [])
        control_actions = list(autoops_control_tower.get("recommended_actions") or autoops_control_tower.get("actions") or [])
        command_actions = list(command_center.get("recommended_actions") or command_center.get("actions") or [])

        risk_count = len(top_risks) + len(sync_gaps) + len(feedback_gaps) + len(evolution_risks)
        action_count = len(weekly_actions) + len(sync_actions) + len(feedback_actions) + len(evolution_actions) + len(governance_actions)
        blocked_dependencies = []
        for item in sync_gaps[:4]:
            if isinstance(item, dict):
                blocked_dependencies.append({
                    "type": item.get("type") or "dependency",
                    "title": item.get("title") or "知识同步依赖缺口",
                    "summary": item.get("summary") or "运行时知识同步存在待补齐依赖",
                })
            else:
                blocked_dependencies.append({"type": "dependency", "title": "知识同步依赖缺口", "summary": str(item)})
        for item in feedback_gaps[:4]:
            if isinstance(item, dict):
                blocked_dependencies.append({
                    "type": item.get("type") or "dependency",
                    "title": item.get("title") or "反馈闭环依赖缺口",
                    "summary": item.get("summary") or "反馈闭环存在待补齐依赖",
                })
            else:
                blocked_dependencies.append({"type": "dependency", "title": "反馈闭环依赖缺口", "summary": str(item)})

        if blocked_dependencies and risk_count >= 6:
            orchestrator_status = "escalation_needed"
        elif blocked_dependencies:
            orchestrator_status = "blocked"
        elif next_week_focus or top_risks:
            orchestrator_status = "focused"
        elif action_count:
            orchestrator_status = "coordinated"
        else:
            orchestrator_status = "idle"

        global_priorities = []
        for item in top_risks[:3]:
            global_priorities.append({
                "type": "priority",
                "title": item.get("title") if isinstance(item, dict) else "运行时重点风险",
                "summary": item.get("summary") if isinstance(item, dict) else str(item),
                "level": item.get("level") if isinstance(item, dict) else "warning",
            })
        for item in governance_actions[:3]:
            global_priorities.append({
                "type": "priority",
                "title": item.get("title") or "治理优先动作",
                "summary": item.get("summary") or "需要纳入运行时统一编排",
                "level": item.get("priority") or item.get("level") or "normal",
            })

        runtime_focus = []
        for item in next_week_focus[:5]:
            runtime_focus.append({
                "type": "runtime",
                "title": item.get("title") if isinstance(item, dict) else "运行时焦点",
                "summary": item.get("summary") if isinstance(item, dict) else str(item),
            })
        if not runtime_focus and runtime_evolution.get("evolution_summary"):
            runtime_focus.append({
                "type": "runtime",
                "title": "运行时进化焦点",
                "summary": runtime_evolution.get("evolution_summary") or "",
            })

        cross_module_links = [
            {"type": "runtime", "title": "周复盘 -> 反馈闭环", "summary": "将周复盘风险与建议汇入反馈闭环复核"},
            {"type": "dependency", "title": "学习中心 -> 知识同步", "summary": "将运行时学习结果同步到知识库、SOP 与治理计划"},
            {"type": "execution", "title": "治理计划 -> 控制塔", "summary": "将治理动作纳入控制塔统一排序与人工复核"},
        ]
        resource_allocation = [
            {"type": "resource", "title": "人工复核资源", "summary": "优先处理高风险、阻塞依赖和需要升级的运行时事项", "level": "high" if risk_count else "medium"},
            {"type": "resource", "title": "SOP 与知识库资源", "summary": f"当前可参考 SOP/知识条目 {len(sop_items)} 项", "level": "medium"},
            {"type": "resource", "title": "自动运营资源", "summary": f"控制塔候选动作 {len(control_actions) + len(command_actions)} 项，仅展示不自动执行", "level": "medium"},
        ]

        unified_execution_order = []
        for title, source_items in [
            ("先处理阻塞依赖", blocked_dependencies),
            ("再复核重点风险", top_risks),
            ("随后同步知识与 SOP", sync_actions),
            ("最后沉淀长期建议", evolution_actions),
        ]:
            if source_items:
                unified_execution_order.append({
                    "type": "execution",
                    "title": title,
                    "summary": f"候选事项 {len(source_items)} 项，需人工确认后推进",
                })

        escalation_suggestions = []
        if orchestrator_status in {"blocked", "escalation_needed"}:
            escalation_suggestions.append("优先人工复核阻塞依赖，确认是否暂停相关自动运营动作。")
        if top_risks:
            escalation_suggestions.append("将周复盘高风险项提升到今日运营优先队列。")
        if sync_gaps:
            escalation_suggestions.append("补齐知识库、SOP 或治理计划的同步缺口。")

        system_recommended_actions = (
            weekly_actions[:3]
            + sync_actions[:3]
            + feedback_actions[:3]
            + evolution_actions[:3]
        )
        if not system_recommended_actions:
            system_recommended_actions = ["仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。"]

        return {
            "orchestrator_status": orchestrator_status,
            "global_priorities": global_priorities[:6],
            "runtime_focus": runtime_focus[:6],
            "cross_module_links": cross_module_links,
            "resource_allocation": resource_allocation,
            "unified_execution_order": unified_execution_order,
            "blocked_dependencies": blocked_dependencies[:6],
            "escalation_suggestions": escalation_suggestions,
            "orchestration_summary": (
                "当前暂无运行时编排数据。"
                if orchestrator_status == "idle"
                else "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。当前已根据运行时复盘、反馈、知识同步、控制塔与治理计划形成只读编排视图。"
            ),
            "system_recommended_actions": system_recommended_actions[:8],
        }

    @staticmethod
    def build_ai_runtime_evolution_center(
        dashboard: dict,
        runtime_feedback_loop: dict | None = None,
        runtime_weekly_review: dict | None = None,
        runtime_learning: dict | None = None,
        runtime_knowledge_sync: dict | None = None,
        knowledge_base: dict | None = None,
        sop_center: dict | None = None,
        governance_center: dict | None = None,
    ) -> dict:
        """构建只读 AI 运行时进化中心，不执行任何自动优化动作。"""
        runtime_feedback_loop = runtime_feedback_loop or {}
        runtime_weekly_review = runtime_weekly_review or {}
        runtime_learning = runtime_learning or {}
        runtime_knowledge_sync = runtime_knowledge_sync or {}
        knowledge_base = knowledge_base or {}
        sop_center = sop_center or {}
        governance_center = governance_center or {}

        def maturity(score: int) -> dict:
            safe_score = max(0, min(int(score or 0), 100))
            if safe_score >= 85:
                level = "excellent"
            elif safe_score >= 65:
                level = "high"
            elif safe_score >= 35:
                level = "medium"
            else:
                level = "low"
            return {"score": safe_score, "level": level}

        effective_actions = list(runtime_feedback_loop.get("effective_actions") or [])
        high_value_recoveries = list(runtime_feedback_loop.get("high_value_recoveries") or [])
        feedback_gaps = list(runtime_feedback_loop.get("feedback_gaps") or [])
        feedback_history = list(runtime_feedback_loop.get("feedback_history") or [])
        top_risks = list(runtime_weekly_review.get("top_risks") or [])
        weekly_wins = list(runtime_weekly_review.get("weekly_wins") or [])
        key_learnings = list(runtime_learning.get("key_learnings") or [])
        learning_history = list(runtime_learning.get("learning_history") or [])
        sync_gaps = list(runtime_knowledge_sync.get("sync_gaps") or [])
        knowledge_items = list(knowledge_base.get("knowledge_items") or [])
        knowledge_recommendations = list(knowledge_base.get("recommendations") or [])
        sop_items = list(sop_center.get("sop_items") or sop_center.get("items") or [])
        governance_metrics = list(governance_center.get("metrics") or [])
        governance_alerts = list(governance_center.get("alerts") or [])

        runtime_maturity = maturity(35 + len(weekly_wins) * 12 + len(high_value_recoveries) * 8 - len(top_risks) * 8)
        governance_maturity = maturity(35 + len(governance_metrics) * 10 + len(effective_actions) * 5 - len(governance_alerts) * 5)
        sop_maturity = maturity(30 + len(sop_items) * 12 + len(high_value_recoveries) * 8 + len(runtime_feedback_loop.get("sop_feedback") or []) * 6)
        feedback_maturity = maturity(25 + len(effective_actions) * 10 + len(feedback_history) * 4 - len(feedback_gaps) * 8)
        knowledge_maturity = maturity(30 + len(knowledge_items) * 10 + len(knowledge_recommendations) * 6 + len(key_learnings) * 5 - len(sync_gaps) * 8)

        positive_signals = []
        for item in weekly_wins[:5]:
            positive_signals.append({"type": "runtime", "title": "周复盘正向信号", "summary": str(item)})
        for item in effective_actions[:5]:
            positive_signals.append({
                "type": "action",
                "title": item.get("title") or "有效反馈动作",
                "summary": item.get("summary") or "运行时动作已形成反馈",
            })
        for item in key_learnings[:5]:
            positive_signals.append({
                "type": "learning",
                "title": "学习沉淀信号",
                "summary": item.get("text") or item.get("summary") or "运行时学习结果已沉淀",
            } if isinstance(item, dict) else {"type": "learning", "title": "学习沉淀信号", "summary": str(item)})

        risk_signals = []
        for item in top_risks[:5]:
            risk_signals.append({
                "type": "runtime",
                "title": item.get("title") or "运行时风险信号",
                "summary": item.get("summary") or "需要人工关注",
            })
        for item in feedback_gaps[:5]:
            risk_signals.append({
                "type": item.get("type") or "suggestion",
                "title": item.get("title") or "反馈闭环风险",
                "summary": item.get("summary") or "存在反馈闭环缺口",
            })
        for item in sync_gaps[:5]:
            risk_signals.append({
                "type": item.get("type") or "knowledge",
                "title": "知识同步风险",
                "summary": item.get("summary") or "存在知识同步缺口",
            })

        evolution_risks = []
        if risk_signals:
            evolution_risks.append("运行时进化仍存在风险信号，需要人工复核。")
        if feedback_maturity.get("level") in {"low", "medium"}:
            evolution_risks.append("反馈闭环成熟度不足，可能导致改进动作难以复用。")
        if knowledge_maturity.get("level") in {"low", "medium"}:
            evolution_risks.append("知识沉淀仍不充分，需要补齐知识库和 SOP 同步。")

        evolution_benefits = []
        if positive_signals:
            evolution_benefits.append("已形成运行时学习、反馈和复盘的正向信号。")
        if high_value_recoveries:
            evolution_benefits.append("高价值恢复经验可沉淀为长期运营能力。")
        if governance_maturity.get("level") in {"high", "excellent"}:
            evolution_benefits.append("治理成熟度较高，可支撑稳定复盘。")

        long_term_recommendations = [
            "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。",
            "持续将有效反馈沉淀为知识库、SOP 和治理复核规则。",
            "每周复核进化风险，避免把低价值建议固化为长期流程。",
        ]
        if evolution_risks:
            long_term_recommendations.append("优先处理进化风险，再扩大自动运营覆盖范围。")

        maturity_scores = [
            runtime_maturity["score"],
            governance_maturity["score"],
            sop_maturity["score"],
            feedback_maturity["score"],
            knowledge_maturity["score"],
        ]
        avg_score = sum(maturity_scores) // len(maturity_scores)
        if not (positive_signals or risk_signals or feedback_history or learning_history):
            evolution_status = "empty"
        elif risk_signals and avg_score < 45:
            evolution_status = "risky"
        elif avg_score >= 85:
            evolution_status = "optimized"
        elif avg_score >= 70:
            evolution_status = "mature"
        elif avg_score >= 45:
            evolution_status = "growing"
        elif positive_signals:
            evolution_status = "emerging"
        else:
            evolution_status = "stagnant"

        if avg_score >= 85:
            evolution_level = "excellent"
        elif avg_score >= 65:
            evolution_level = "high"
        elif avg_score >= 35:
            evolution_level = "medium"
        else:
            evolution_level = "low"

        return {
            "evolution_status": evolution_status,
            "evolution_level": evolution_level,
            "runtime_maturity": runtime_maturity,
            "governance_maturity": governance_maturity,
            "sop_maturity": sop_maturity,
            "feedback_maturity": feedback_maturity,
            "knowledge_maturity": knowledge_maturity,
            "positive_signals": positive_signals[:8],
            "risk_signals": risk_signals[:8],
            "evolution_risks": evolution_risks,
            "evolution_benefits": evolution_benefits,
            "long_term_recommendations": long_term_recommendations,
            "evolution_summary": (
                "当前暂无运行时进化数据。"
                if evolution_status == "empty"
                else f"当前运行时进化成熟度为 {avg_score} 分，状态为 {ArticleHealthService._ai_status_label(evolution_status)}。"
            ),
            "evolution_history": (feedback_history + learning_history)[:8],
        }

    @staticmethod
    def build_ai_runtime_feedback_loop_center(
        dashboard: dict,
        runtime_weekly_review: dict | None = None,
        runtime_knowledge_sync: dict | None = None,
        runtime_learning: dict | None = None,
        runtime_postmortem: dict | None = None,
        sop_center: dict | None = None,
        governance_center: dict | None = None,
    ) -> dict:
        """构建只读 AI 运行时反馈闭环中心，不执行任何闭环动作。"""
        runtime_weekly_review = runtime_weekly_review or {}
        runtime_knowledge_sync = runtime_knowledge_sync or {}
        runtime_learning = runtime_learning or {}
        runtime_postmortem = runtime_postmortem or {}
        sop_center = sop_center or {}
        governance_center = governance_center or {}

        weekly_wins = list(runtime_weekly_review.get("weekly_wins") or [])
        weekly_focus = list(runtime_weekly_review.get("next_week_focus") or [])
        weekly_actions = list(runtime_weekly_review.get("recommended_actions") or [])
        recovery_patterns = list(runtime_learning.get("effective_recovery_patterns") or [])
        unstable_components = list(runtime_learning.get("unstable_runtime_components") or [])
        prevention_actions = list(runtime_postmortem.get("prevention_actions") or [])
        what_worked = list(runtime_postmortem.get("what_worked") or [])
        what_failed = list(runtime_postmortem.get("what_failed") or [])
        sync_gaps = list(runtime_knowledge_sync.get("sync_gaps") or [])
        knowledge_sync = list(runtime_knowledge_sync.get("knowledge_sync_suggestions") or [])
        sop_sync = list(runtime_knowledge_sync.get("sop_sync_suggestions") or [])
        governance_sync = list(runtime_knowledge_sync.get("governance_sync_suggestions") or [])
        sop_items = list(sop_center.get("sop_items") or sop_center.get("items") or [])
        governance_alerts = list(governance_center.get("alerts") or [])

        effective_actions = []
        for item in weekly_wins[:5]:
            effective_actions.append({"type": "action", "title": "有效动作", "summary": str(item)})
        for item in what_worked[:5]:
            effective_actions.append({"type": "action", "title": "复盘有效经验", "summary": str(item)})

        ineffective_actions = []
        for item in what_failed[:5]:
            ineffective_actions.append({"type": "action", "title": "待改进动作", "summary": str(item)})
        for item in unstable_components[:5]:
            ineffective_actions.append({
                "type": "action",
                "title": item.get("title") or "不稳定组件",
                "summary": item.get("summary") or "需要复核运行时动作效果",
            })

        high_value_recoveries = []
        for item in recovery_patterns[:5]:
            high_value_recoveries.append({
                "type": "recovery",
                "title": item.get("title") or "高价值恢复经验",
                "summary": item.get("summary") or "可复用的恢复反馈",
            })

        low_value_suggestions = []
        for item in weekly_focus[:5]:
            low_value_suggestions.append({"type": "suggestion", "title": "待验证建议", "summary": str(item)})

        governance_feedback = []
        for item in governance_sync[:5]:
            governance_feedback.append({
                "type": "governance",
                "title": item.get("title") or "治理反馈",
                "summary": item.get("summary") or "需要纳入治理反馈",
            })
        for item in governance_alerts[:3]:
            governance_feedback.append({
                "type": "governance",
                "title": item.get("title") or "治理风险反馈",
                "summary": item.get("message") or item.get("summary") or "",
            })

        sop_feedback = []
        for item in sop_sync[:5]:
            sop_feedback.append({
                "type": "sop",
                "title": item.get("title") or "SOP 反馈",
                "summary": item.get("summary") or "需要同步到 SOP",
            })
        for item in prevention_actions[:3]:
            sop_feedback.append({"type": "sop", "title": "预防动作反馈", "summary": str(item)})

        feedback_gaps = []
        for item in sync_gaps[:5]:
            feedback_gaps.append({
                "type": item.get("type") or "suggestion",
                "title": "反馈闭环缺口",
                "summary": item.get("summary") or "存在未闭环的同步缺口",
            })
        if knowledge_sync and not (effective_actions or high_value_recoveries):
            feedback_gaps.append({"type": "suggestion", "title": "效果反馈缺口", "summary": "已有知识同步建议，但缺少有效动作反馈。"})
        if sop_items and not sop_feedback:
            feedback_gaps.append({"type": "sop", "title": "SOP 反馈缺口", "summary": "已有 SOP 数据，但暂无运行时反馈闭环。"})

        recommended_actions = []
        if effective_actions:
            recommended_actions.append("沉淀有效动作为可复用运行时经验")
        if ineffective_actions:
            recommended_actions.append("复核低效动作，避免重复执行无效建议")
        if high_value_recoveries:
            recommended_actions.append("将高价值恢复经验同步到 SOP 和知识库")
        if feedback_gaps:
            recommended_actions.append("优先补齐反馈缺口，不自动修改文章或发布状态")
        recommended_actions.extend(weekly_actions[:2])
        if not recommended_actions:
            recommended_actions.append("保持人工复核和只读反馈观察")

        feedback_history = (
            list(runtime_weekly_review.get("top_risks") or [])
            + list(runtime_knowledge_sync.get("sync_history") or [])
            + list(runtime_learning.get("learning_history") or [])
        )[:8]

        strong_count = len(effective_actions) + len(high_value_recoveries) + len(governance_feedback) + len(sop_feedback)
        weak_count = len(ineffective_actions) + len(low_value_suggestions) + len(feedback_gaps)
        if not (strong_count or weak_count or feedback_history):
            feedback_status = "empty"
        elif strong_count >= 4 and not feedback_gaps:
            feedback_status = "strong_loop"
        elif weak_count > strong_count:
            feedback_status = "weak_loop"
        elif strong_count:
            feedback_status = "active"
        else:
            feedback_status = "learning"

        return {
            "feedback_status": feedback_status,
            "effective_actions": effective_actions[:8],
            "ineffective_actions": ineffective_actions[:8],
            "high_value_recoveries": high_value_recoveries[:8],
            "low_value_suggestions": low_value_suggestions[:8],
            "governance_feedback": governance_feedback[:8],
            "sop_feedback": sop_feedback[:8],
            "feedback_gaps": feedback_gaps[:8],
            "feedback_summary": (
                "当前暂无运行时反馈闭环数据。"
                if feedback_status == "empty"
                else f"当前形成 {strong_count} 条正向反馈，发现 {weak_count} 条待闭环问题。"
            ),
            "recommended_actions": recommended_actions[:8],
            "feedback_history": feedback_history,
        }

    @staticmethod
    def build_ai_runtime_weekly_review_center(
        dashboard: dict,
        runtime_observability: dict | None = None,
        runtime_alert: dict | None = None,
        runtime_recovery: dict | None = None,
        runtime_incident: dict | None = None,
        runtime_postmortem: dict | None = None,
        runtime_learning: dict | None = None,
        runtime_knowledge_sync: dict | None = None,
    ) -> dict:
        """构建只读 AI 运行时周复盘中心，不触发任何运行时动作。"""
        runtime_observability = runtime_observability or {}
        runtime_alert = runtime_alert or {}
        runtime_recovery = runtime_recovery or {}
        runtime_incident = runtime_incident or {}
        runtime_postmortem = runtime_postmortem or {}
        runtime_learning = runtime_learning or {}
        runtime_knowledge_sync = runtime_knowledge_sync or {}

        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        week_range = f"{week_start.isoformat()} 至 {week_end.isoformat()}"

        runtime_health = runtime_observability.get("runtime_health") or {}
        active_alerts = list(runtime_alert.get("active_alerts") or [])
        critical_alerts = list(runtime_alert.get("critical_alerts") or [])
        warning_alerts = list(runtime_alert.get("warning_alerts") or [])
        active_incidents = list(runtime_incident.get("active_incidents") or [])
        critical_incidents = list(runtime_incident.get("critical_incidents") or [])
        recovery_paths = list(runtime_recovery.get("recovery_paths") or [])
        postmortems = list(runtime_postmortem.get("postmortems") or [])
        key_learnings = list(runtime_learning.get("key_learnings") or [])
        sync_gaps = list(runtime_knowledge_sync.get("sync_gaps") or [])

        runtime_summary = {
            "type": "runtime",
            "title": "运行时概览",
            "summary": runtime_health.get("summary") or "当前暂无运行时周复盘数据。",
            "score": runtime_health.get("score", 0),
        }
        alert_review = {
            "type": "alert",
            "title": "告警复盘",
            "summary": f"本周活跃告警 {len(active_alerts)} 个，严重告警 {len(critical_alerts)} 个，提醒/警告 {len(warning_alerts)} 个。",
            "items": active_alerts[:5],
        }
        incident_review = {
            "type": "incident",
            "title": "事故复盘",
            "summary": f"本周运行时事故 {len(active_incidents)} 个，重大事故 {len(critical_incidents)} 个。",
            "items": active_incidents[:5],
        }
        recovery_review = {
            "type": "recovery",
            "title": "恢复复盘",
            "summary": f"本周沉淀恢复路径 {len(recovery_paths)} 条。",
            "items": recovery_paths[:5],
        }
        postmortem_review = {
            "type": "postmortem",
            "title": "事故复盘沉淀",
            "summary": f"本周生成事故复盘草稿 {len(postmortems)} 条。",
            "items": postmortems[:5],
        }
        learning_review = {
            "type": "learning",
            "title": "学习复盘",
            "summary": runtime_learning.get("learning_summary") or "当前暂无运行时学习沉淀。",
            "items": key_learnings[:5],
        }
        knowledge_sync_review = {
            "type": "knowledge_sync",
            "title": "知识同步复盘",
            "summary": runtime_knowledge_sync.get("sync_summary") or "当前暂无运行时知识同步建议。",
            "items": sync_gaps[:5],
        }

        top_risks = []
        for item in (critical_alerts + critical_incidents + sync_gaps)[:6]:
            if isinstance(item, dict):
                top_risks.append({
                    "title": item.get("title") or "运行时风险",
                    "summary": item.get("summary") or item.get("message") or "需要人工关注",
                    "level": item.get("level") or item.get("type") or "warning",
                })
        weekly_wins = []
        if recovery_paths:
            weekly_wins.append("已形成可人工复核的恢复路径")
        if key_learnings:
            weekly_wins.append("已沉淀运行时学习线索")
        if runtime_knowledge_sync.get("sync_status") == "synced":
            weekly_wins.append("知识同步状态稳定")

        next_week_focus = []
        if critical_alerts or critical_incidents:
            next_week_focus.append("优先复盘严重告警与重大事故")
        if sync_gaps:
            next_week_focus.append("补齐知识库、SOP 或治理同步缺口")
        if recovery_paths:
            next_week_focus.append("验证恢复路径是否可复用")
        if not next_week_focus:
            next_week_focus.append("保持运行时巡检和人工复核节奏")

        recommended_actions = [
            "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。",
            "每周复盘运行时告警、事故、恢复、学习和知识同步链路。",
        ]
        if top_risks:
            recommended_actions.append("优先处理周复盘中的高风险项。")
        if sync_gaps:
            recommended_actions.append("将同步缺口加入下周人工检查清单。")

        if critical_alerts or critical_incidents:
            weekly_status = "critical"
        elif top_risks:
            weekly_status = "risky"
        elif active_alerts or active_incidents or sync_gaps:
            weekly_status = "attention"
        elif any([runtime_health, recovery_paths, postmortems, key_learnings]):
            weekly_status = "stable"
        else:
            weekly_status = "empty"

        return {
            "weekly_status": weekly_status,
            "week_range": week_range,
            "runtime_summary": runtime_summary,
            "alert_review": alert_review,
            "incident_review": incident_review,
            "recovery_review": recovery_review,
            "postmortem_review": postmortem_review,
            "learning_review": learning_review,
            "knowledge_sync_review": knowledge_sync_review,
            "top_risks": top_risks,
            "weekly_wins": weekly_wins,
            "next_week_focus": next_week_focus,
            "recommended_actions": recommended_actions,
        }

    @staticmethod
    def build_ai_runtime_knowledge_sync_center(
        dashboard: dict,
        runtime_learning: dict | None = None,
        knowledge_base: dict | None = None,
        sop_center: dict | None = None,
        governance_center: dict | None = None,
        governance_action_plan: dict | None = None,
    ) -> dict:
        """构建只读 AI 运行时知识同步中心，不写入知识库、SOP 或治理规则。"""
        runtime_learning = runtime_learning or {}
        knowledge_base = knowledge_base or {}
        sop_center = sop_center or {}
        governance_center = governance_center or {}
        governance_action_plan = governance_action_plan or {}

        key_learnings = list(runtime_learning.get("key_learnings") or [])
        repeated_patterns = list(runtime_learning.get("repeated_incident_patterns") or [])
        recovery_patterns = list(runtime_learning.get("effective_recovery_patterns") or [])
        unstable_components = list(runtime_learning.get("unstable_runtime_components") or [])
        sop_improvements = list(runtime_learning.get("sop_improvement_suggestions") or [])
        governance_improvements = list(runtime_learning.get("governance_improvement_suggestions") or [])
        learning_history = list(runtime_learning.get("learning_history") or [])
        knowledge_items = list(knowledge_base.get("knowledge_items") or [])
        knowledge_recommendations = list(knowledge_base.get("recommendations") or [])
        sop_items = list(sop_center.get("sop_items") or sop_center.get("items") or [])
        governance_actions = list(governance_action_plan.get("actions") or [])
        governance_alerts = list(governance_center.get("alerts") or [])

        knowledge_sync_suggestions = []
        for item in key_learnings[:5]:
            text = item.get("text") if isinstance(item, dict) else str(item)
            knowledge_sync_suggestions.append({
                "type": "knowledge",
                "title": "同步学习结果到知识库",
                "summary": text or "需要沉淀运行时学习结果",
            })
        for item in knowledge_recommendations[:3]:
            knowledge_sync_suggestions.append({
                "type": "knowledge",
                "title": "复用知识推荐",
                "summary": item,
            })

        sop_sync_suggestions = []
        for item in sop_improvements[:5]:
            text = item.get("text") if isinstance(item, dict) else str(item)
            sop_sync_suggestions.append({
                "type": "sop",
                "title": "同步到 SOP",
                "summary": text or "补充运行时处置 SOP",
            })

        governance_sync_suggestions = []
        for item in governance_improvements[:5]:
            text = item.get("text") if isinstance(item, dict) else str(item)
            governance_sync_suggestions.append({
                "type": "governance",
                "title": "同步到治理计划",
                "summary": text or "补充治理复核动作",
            })
        for item in governance_actions[:3]:
            governance_sync_suggestions.append({
                "type": "governance",
                "title": item.get("title") or "治理动作同步",
                "summary": item.get("summary") or "同步运行时学习到治理动作",
            })

        checklist_sync_suggestions = []
        for item in (repeated_patterns + unstable_components + recovery_patterns)[:8]:
            checklist_sync_suggestions.append({
                "type": "checklist",
                "title": item.get("title") if isinstance(item, dict) else "检查清单同步",
                "summary": (item.get("summary") if isinstance(item, dict) else str(item)) or "补充运行时检查项",
            })

        sync_gaps = []
        if key_learnings and not knowledge_items:
            sync_gaps.append({"type": "knowledge", "summary": "已有学习结果，但知识库暂无对应沉淀。"})
        if sop_improvements and not sop_items:
            sync_gaps.append({"type": "sop", "summary": "已有 SOP 改进建议，但暂无 SOP 中心数据。"})
        if (governance_improvements or governance_alerts) and not governance_actions:
            sync_gaps.append({"type": "governance", "summary": "已有治理同步线索，但治理行动计划暂无动作。"})
        if (repeated_patterns or unstable_components) and not checklist_sync_suggestions:
            sync_gaps.append({"type": "checklist", "summary": "已有运行时风险模式，但暂无检查清单同步项。"})

        recommended_actions = []
        if knowledge_sync_suggestions:
            recommended_actions.append("将关键学习沉淀为知识库条目")
        if sop_sync_suggestions:
            recommended_actions.append("把有效恢复和预防动作同步到 SOP")
        if governance_sync_suggestions:
            recommended_actions.append("将治理类学习纳入人工复核计划")
        if checklist_sync_suggestions:
            recommended_actions.append("把重复事故和不稳定组件加入巡检清单")
        if sync_gaps:
            recommended_actions.append("优先人工复核同步缺口，不自动写入任何规则或文章")

        if runtime_learning.get("learning_status") == "urgent" or len(sync_gaps) >= 2:
            sync_status = "urgent"
        elif sync_gaps:
            sync_status = "gap_found"
        elif any([knowledge_sync_suggestions, sop_sync_suggestions, governance_sync_suggestions, checklist_sync_suggestions]):
            sync_status = "pending"
        elif knowledge_items or sop_items or governance_actions:
            sync_status = "synced"
        else:
            sync_status = "idle"

        sync_total = (
            len(knowledge_sync_suggestions)
            + len(sop_sync_suggestions)
            + len(governance_sync_suggestions)
            + len(checklist_sync_suggestions)
        )

        return {
            "sync_status": sync_status,
            "knowledge_sync_suggestions": knowledge_sync_suggestions[:8],
            "sop_sync_suggestions": sop_sync_suggestions[:8],
            "governance_sync_suggestions": governance_sync_suggestions[:8],
            "checklist_sync_suggestions": checklist_sync_suggestions[:8],
            "sync_gaps": sync_gaps[:8],
            "sync_summary": (
                "当前暂无运行时知识同步建议。"
                if not (sync_total or sync_gaps)
                else f"当前生成 {sync_total} 条知识同步建议，发现 {len(sync_gaps)} 个同步缺口。"
            ),
            "recommended_actions": recommended_actions,
            "sync_history": learning_history[:8],
        }

    @staticmethod
    def build_ai_runtime_learning_center(
        dashboard: dict,
        runtime_observability: dict | None = None,
        runtime_alert: dict | None = None,
        runtime_recovery: dict | None = None,
        runtime_incident: dict | None = None,
        runtime_postmortem: dict | None = None,
        knowledge_base: dict | None = None,
        sop_center: dict | None = None,
    ) -> dict:
        """构建只读 AI 运行时学习中心，不执行任何治理、审核或发布动作。"""
        dashboard = dashboard or {}
        runtime_observability = runtime_observability or {}
        runtime_alert = runtime_alert or {}
        runtime_recovery = runtime_recovery or {}
        runtime_incident = runtime_incident or {}
        runtime_postmortem = runtime_postmortem or {}
        knowledge_base = knowledge_base or {}
        sop_center = sop_center or {}

        active_incidents = list(runtime_incident.get("active_incidents") or [])
        critical_incidents = list(runtime_incident.get("critical_incidents") or [])
        incident_history = list(runtime_incident.get("incident_history") or [])
        recovery_paths = list(runtime_recovery.get("recovery_paths") or [])
        recovery_timeline = list(runtime_recovery.get("recovery_timeline") or [])
        failure_hotspots = list(runtime_observability.get("failure_hotspots") or [])
        blocked_tasks = list(runtime_observability.get("blocked_tasks") or [])
        alert_history = list(runtime_alert.get("recent_alert_history") or [])
        postmortem_history = list(runtime_postmortem.get("postmortem_history") or [])
        what_worked = list(runtime_postmortem.get("what_worked") or [])
        what_failed = list(runtime_postmortem.get("what_failed") or [])
        prevention_actions = list(runtime_postmortem.get("prevention_actions") or [])
        knowledge_items = list(knowledge_base.get("knowledge_items") or [])
        knowledge_recommendations = list(knowledge_base.get("recommendations") or [])
        sop_items = list(sop_center.get("sop_items") or sop_center.get("items") or [])

        key_learnings = []
        for item in what_failed[:3]:
            key_learnings.append({"type": "incident", "text": item})
        for item in what_worked[:3]:
            key_learnings.append({"type": "recovery", "text": item})
        for item in knowledge_recommendations[:3]:
            key_learnings.append({"type": "governance", "text": item})

        repeated_incident_patterns = []
        for item in (critical_incidents + active_incidents)[:5]:
            repeated_incident_patterns.append({
                "type": "incident",
                "title": item.get("title") or "运行时事故模式",
                "summary": item.get("message") or item.get("summary") or "需要持续复盘的运行时事故模式",
            })

        effective_recovery_patterns = []
        for item in recovery_paths[:5]:
            effective_recovery_patterns.append({
                "type": "recovery",
                "title": item.get("title") or item.get("name") or "恢复路径",
                "summary": item.get("summary") or item.get("message") or item.get("advice") or "可复用的人工恢复经验",
            })
        if not effective_recovery_patterns and what_worked:
            effective_recovery_patterns = [
                {"type": "recovery", "title": "有效恢复经验", "summary": item}
                for item in what_worked[:5]
            ]

        unstable_runtime_components = []
        for item in failure_hotspots[:5]:
            unstable_runtime_components.append({
                "type": "runtime",
                "title": item.get("title") or "运行时不稳定组件",
                "summary": item.get("message") or f"失败次数 {item.get('failed_count') or 0}",
            })
        for item in blocked_tasks[:5]:
            unstable_runtime_components.append({
                "type": "runtime",
                "title": item.get("title") or "阻塞任务",
                "summary": item.get("message") or "需要人工关注的阻塞任务",
            })

        sop_improvement_suggestions = []
        for item in prevention_actions[:5]:
            sop_improvement_suggestions.append({"type": "sop", "text": item})
        for item in sop_items[:3]:
            sop_improvement_suggestions.append({
                "type": "sop",
                "text": item.get("步骤") or item.get("title") or item.get("name") or "补充运行时处置 SOP",
            })

        governance_improvement_suggestions = []
        governance_actions = (dashboard.get("ai_governance_action_plan") or {}).get("actions") or []
        for item in list(governance_actions)[:5]:
            governance_improvement_suggestions.append({
                "type": "governance",
                "text": item.get("title") or item.get("summary") or "补充治理复核动作",
            })
        if not governance_improvement_suggestions:
            for item in knowledge_recommendations[:5]:
                governance_improvement_suggestions.append({"type": "governance", "text": item})

        learning_history = (postmortem_history or incident_history or alert_history or recovery_timeline)[:8]
        if critical_incidents or runtime_postmortem.get("postmortem_status") == "urgent":
            learning_status = "urgent"
        elif key_learnings or repeated_incident_patterns or effective_recovery_patterns:
            learning_status = "learning"
        elif learning_history or knowledge_items:
            learning_status = "collecting"
        else:
            learning_status = "none"

        learning_count = (
            len(key_learnings)
            + len(repeated_incident_patterns)
            + len(effective_recovery_patterns)
            + len(unstable_runtime_components)
        )

        return {
            "learning_status": learning_status,
            "key_learnings": key_learnings,
            "repeated_incident_patterns": repeated_incident_patterns,
            "effective_recovery_patterns": effective_recovery_patterns,
            "unstable_runtime_components": unstable_runtime_components[:8],
            "sop_improvement_suggestions": sop_improvement_suggestions[:8],
            "governance_improvement_suggestions": governance_improvement_suggestions[:8],
            "learning_summary": (
                "当前暂无运行时学习沉淀。"
                if not learning_count
                else f"当前沉淀 {learning_count} 条运行时学习线索，供人工复盘和 SOP 优化参考。"
            ),
            "learning_history": learning_history,
        }

    @staticmethod
    def build_ai_runtime_postmortem_center(
        dashboard: dict,
        runtime_incident: dict | None = None,
        runtime_recovery: dict | None = None,
        approval_audit: dict | None = None,
        knowledge_base: dict | None = None,
    ) -> dict:
        """构建只读 AI 运行时事故复盘中心，不执行任何事故处理动作。"""
        runtime_incident = runtime_incident or {}
        runtime_recovery = runtime_recovery or {}
        approval_audit = approval_audit or {}
        knowledge_base = knowledge_base or {}

        active_incidents = list(runtime_incident.get("active_incidents") or [])
        critical_incidents = list(runtime_incident.get("critical_incidents") or [])
        incident_timeline = list(runtime_incident.get("incident_timeline") or [])
        incident_history = list(runtime_incident.get("incident_history") or [])
        recovery_paths = list(runtime_recovery.get("recovery_paths") or [])
        audit_findings = list(approval_audit.get("audit_findings") or [])
        knowledge_items = list(knowledge_base.get("knowledge_items") or [])
        knowledge_recommendations = list(knowledge_base.get("recommendations") or [])

        postmortems = [
            {
                "title": item.get("title") or "运行时事故复盘",
                "summary": item.get("message") or "需要复盘事故影响与恢复路径",
                "level": item.get("level") or "warning",
            }
            for item in active_incidents[:5]
        ]
        root_cause_hypotheses = []
        if critical_incidents:
            root_cause_hypotheses.append("重大告警可能来自阻塞任务或高优先级队列积压")
        if recovery_paths:
            root_cause_hypotheses.append("恢复路径提示存在发布失败、阻塞任务或人工确认缺口")
        if audit_findings:
            root_cause_hypotheses.extend(audit_findings[:3])

        timeline_review = incident_timeline[:5]
        impact_review = {
            "active_incident_count": len(active_incidents),
            "critical_count": len(critical_incidents),
            "history_count": len(incident_history),
            "recovery_path_count": len(recovery_paths),
        }
        what_worked = knowledge_recommendations[:3]
        if recovery_paths:
            what_worked.append("已形成可人工复核的恢复路径")
        what_failed = root_cause_hypotheses[:5]
        prevention_actions = [
            "将重大事故纳入人工复盘清单",
            "沉淀运行时告警到知识库",
            "恢复前保持人工批准，不自动触发审核、发布、Agent 或修改文章",
        ] if active_incidents or recovery_paths else []

        if critical_incidents:
            postmortem_status = "urgent"
        elif postmortems:
            postmortem_status = "draft"
        elif knowledge_items or incident_history:
            postmortem_status = "learning"
        else:
            postmortem_status = "none"

        return {
            "postmortem_status": postmortem_status,
            "postmortems": postmortems,
            "root_cause_hypotheses": root_cause_hypotheses,
            "timeline_review": timeline_review,
            "impact_review": impact_review,
            "what_worked": what_worked,
            "what_failed": what_failed,
            "prevention_actions": prevention_actions,
            "knowledge_items": knowledge_items,
            "postmortem_summary": (
                "当前暂无运行时事故复盘。"
                if not (postmortems or root_cause_hypotheses or incident_history)
                else f"当前生成 {len(postmortems)} 条事故复盘草稿，沉淀 {len(prevention_actions)} 条预防动作。"
            ),
            "postmortem_history": incident_history[:8],
        }

    @staticmethod
    def build_ai_runtime_incident_center(
        dashboard: dict,
        runtime_observability: dict | None = None,
        runtime_alert: dict | None = None,
        runtime_recovery: dict | None = None,
        approval_audit: dict | None = None,
    ) -> dict:
        """构建只读 AI 运行时事故中心，不触发任何事故处理动作。"""
        dashboard = dashboard or {}
        runtime_observability = runtime_observability or {}
        runtime_alert = runtime_alert or {}
        runtime_recovery = runtime_recovery or {}
        approval_audit = approval_audit or {}

        feed = list(dashboard.get("ai_ops_incident_feed") or [])
        active_alerts = list(runtime_alert.get("active_alerts") or [])
        critical_alerts = list(runtime_alert.get("critical_alerts") or [])
        warning_alerts = list(runtime_alert.get("warning_alerts") or [])
        blocked_tasks = list(runtime_observability.get("blocked_tasks") or [])
        failure_hotspots = list(runtime_observability.get("failure_hotspots") or [])
        recovery_paths = list(runtime_recovery.get("recovery_paths") or [])
        risky_pending = list(approval_audit.get("risky_pending") or [])

        critical_incidents = []
        warning_incidents = []
        for item in critical_alerts[:5]:
            critical_incidents.append({
                "title": item.get("title") or "重大运行时事故",
                "message": item.get("message") or "严重告警需要人工复核",
                "level": "critical",
                "article_id": item.get("article_id") or "",
            })
        for item in (warning_alerts + feed)[:8]:
            level = item.get("level") or "warning"
            incident = {
                "title": item.get("title") or "运行时事故",
                "message": item.get("message") or item.get("summary") or "需要关注运行时异常",
                "level": "warning" if level in ("warning", "danger", "critical") else "info",
                "article_id": item.get("article_id") or "",
            }
            if level in ("danger", "critical"):
                critical_incidents.append({**incident, "level": "critical"})
            else:
                warning_incidents.append(incident)

        active_incidents = critical_incidents + warning_incidents
        if critical_incidents:
            incident_status = "critical"
        elif len(active_incidents) >= 3 or blocked_tasks:
            incident_status = "major"
        elif active_incidents:
            incident_status = "minor"
        else:
            incident_status = "none"

        impacted_articles = {
            item.get("article_id")
            for item in (active_incidents + blocked_tasks + failure_hotspots + risky_pending)
            if item.get("article_id")
        }
        impact_summary = {
            "active_incident_count": len(active_incidents),
            "critical_count": len(critical_incidents),
            "warning_count": len(warning_incidents),
            "impacted_articles": len(impacted_articles),
            "recovery_path_count": len(recovery_paths),
        }

        incident_timeline = list(runtime_observability.get("runtime_timeline") or [])[:5] or feed[:5]
        return {
            "incident_status": incident_status,
            "active_incidents": active_incidents,
            "critical_incidents": critical_incidents,
            "warning_incidents": warning_incidents,
            "impact_summary": impact_summary,
            "incident_timeline": incident_timeline,
            "postmortem_suggestions": [
                "复盘严重告警产生的根因",
                "记录恢复路径是否有效",
                "沉淀人工复核标准，避免自动误执行",
            ] if active_incidents else [],
            "recommended_actions": [
                "先处理重大事故，再处理警告事故",
                "恢复前保持人工批准流",
                "仅做只读分析，不自动执行审核、发布、Agent 或修改文章",
            ] if active_incidents else [],
            "incident_history": feed[:8],
            "summary": (
                "当前暂无运行时事故。"
                if not active_incidents
                else f"当前共有 {len(active_incidents)} 个运行时事故，重大 {len(critical_incidents)} 个，警告 {len(warning_incidents)} 个。"
            ),
        }

    @staticmethod
    def build_ai_runtime_recovery_center(
        dashboard: dict,
        runtime_observability: dict | None = None,
        runtime_alert: dict | None = None,
        approval_audit: dict | None = None,
    ) -> dict:
        """构建只读 AI 运行时恢复中心，不执行任何恢复动作。"""
        dashboard = dashboard or {}
        runtime_observability = runtime_observability or {}
        runtime_alert = runtime_alert or {}
        approval_audit = approval_audit or {}

        active_alerts = list(runtime_alert.get("active_alerts") or [])
        critical_alerts = list(runtime_alert.get("critical_alerts") or [])
        warning_alerts = list(runtime_alert.get("warning_alerts") or [])
        blocked_tasks = list(runtime_observability.get("blocked_tasks") or [])
        failure_hotspots = list(runtime_observability.get("failure_hotspots") or [])
        runtime_timeline = list(runtime_observability.get("runtime_timeline") or [])
        risky_pending = list(approval_audit.get("risky_pending") or [])
        stale_pending = list(approval_audit.get("stale_pending") or [])

        recovery_paths = []
        if failure_hotspots:
            recovery_paths.append({
                "title": "发布失败恢复路径",
                "summary": "先定位失败发布任务，再人工复核文章与发布配置。",
                "priority": "high" if critical_alerts else "medium",
            })
        if blocked_tasks or risky_pending:
            recovery_paths.append({
                "title": "阻塞任务恢复路径",
                "summary": "优先处理阻塞对象，恢复前保持人工批准。",
                "priority": "critical" if critical_alerts else "high",
            })
        if active_alerts and not recovery_paths:
            recovery_paths.append({
                "title": "运行时告警恢复路径",
                "summary": "按告警等级逐项复核运行时异常。",
                "priority": "medium",
            })

        immediate_actions = []
        if critical_alerts:
            immediate_actions.append("优先人工复核严重运行时告警")
        if warning_alerts:
            immediate_actions.append("检查失败任务与运行时告警来源")
        if blocked_tasks:
            immediate_actions.append("处理阻塞任务后再恢复常规队列")

        manual_tasks = []
        for item in (blocked_tasks + risky_pending + stale_pending)[:5]:
            manual_tasks.append({
                "title": item.get("title") or item.get("label") or "人工恢复任务",
                "summary": item.get("reason") or item.get("message") or "需要人工复核后继续",
                "priority": item.get("level") or "medium",
            })

        pause_recommendations = []
        if critical_alerts or blocked_tasks:
            pause_recommendations.append("恢复前建议暂停自动推进高风险动作")
        if failure_hotspots:
            pause_recommendations.append("发布失败热点完成排查前保持人工确认")

        recovery_priority = "critical" if critical_alerts else ("high" if blocked_tasks or warning_alerts else ("medium" if active_alerts else "low"))
        if critical_alerts:
            recovery_status = "urgent_recovery"
        elif blocked_tasks or warning_alerts:
            recovery_status = "recovery_needed"
        elif recovery_paths:
            recovery_status = "recovery_ready"
        elif not (active_alerts or failure_hotspots or runtime_timeline):
            recovery_status = "idle"
        else:
            recovery_status = "healthy"

        return {
            "recovery_status": recovery_status,
            "recovery_priority": recovery_priority,
            "recovery_paths": recovery_paths,
            "immediate_actions": immediate_actions,
            "manual_tasks": manual_tasks,
            "pause_recommendations": pause_recommendations,
            "recovery_timeline": runtime_timeline[:5],
            "summary": (
                "当前暂无运行时恢复方案。"
                if recovery_status in ("idle", "healthy") and not recovery_paths
                else f"当前恢复状态为 {ArticleHealthService._ai_status_label(recovery_status)}，恢复优先级为 {ArticleHealthService._ai_status_label(recovery_priority)}。"
            ),
            "recovery_advice": "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。",
        }

    @staticmethod
    def build_ai_runtime_alert_center(dashboard: dict, runtime_observability: dict | None = None) -> dict:
        """构建只读 AI 运行时告警中心，不触发任何运行时动作。"""
        dashboard = dashboard or {}
        runtime_observability = runtime_observability or {}
        failure_hotspots = list(runtime_observability.get("failure_hotspots") or [])
        blocked_tasks = list(runtime_observability.get("blocked_tasks") or [])
        runtime_timeline = list(runtime_observability.get("runtime_timeline") or [])
        queue_pressure = runtime_observability.get("queue_pressure") or {}
        publish_task_metrics = runtime_observability.get("publish_task_metrics") or {}
        agent_failure_rate = runtime_observability.get("agent_failure_rate") or 0

        critical_alerts = []
        warning_alerts = []
        reminder_alerts = []

        for item in blocked_tasks[:5]:
            critical_alerts.append({
                "title": item.get("title") or "运行时阻塞任务",
                "message": item.get("reason") or "存在需要人工复核的阻塞对象",
                "level": "critical",
                "article_id": item.get("article_id") or "",
            })

        failed_count = ArticleHealthService._safe_int(publish_task_metrics.get("failed_count"))
        if failed_count:
            warning_alerts.append({
                "title": "发布任务失败告警",
                "message": f"当前观测到 {failed_count} 个失败发布任务。",
                "level": "warning",
            })

        if agent_failure_rate:
            warning_alerts.append({
                "title": "Agent 失败率提醒",
                "message": f"当前 Agent 失败率约 {agent_failure_rate}%。",
                "level": "warning" if agent_failure_rate < 20 else "critical",
            })

        queue_count = ArticleHealthService._safe_int(queue_pressure.get("pending_count"))
        if queue_count:
            reminder_alerts.append({
                "title": "队列压力提醒",
                "message": f"当前优先处理队列有 {queue_count} 个对象。",
                "level": "reminder",
            })

        for item in failure_hotspots[:5]:
            warning_alerts.append({
                "title": item.get("title") or "失败热点",
                "message": f"失败次数 {item.get('failed_count') or 0}",
                "level": "warning",
                "article_id": item.get("article_id") or "",
            })

        active_alerts = critical_alerts + warning_alerts + reminder_alerts
        alert_status = "critical" if critical_alerts else ("warning" if warning_alerts else ("reminder" if reminder_alerts else "normal"))
        return {
            "alert_status": alert_status,
            "active_alerts": active_alerts,
            "critical_alerts": critical_alerts,
            "warning_alerts": warning_alerts,
            "reminder_alerts": reminder_alerts,
            "alert_summary": (
                "当前暂无运行时告警。"
                if not active_alerts
                else f"当前共有 {len(active_alerts)} 条运行时告警，其中严重 {len(critical_alerts)} 条、警告 {len(warning_alerts)} 条、提醒 {len(reminder_alerts)} 条。"
            ),
            "recommended_actions": [
                "优先人工复核严重告警",
                "检查失败发布任务与高优先级队列",
                "保持只读观察，不自动触发审核、发布、Agent 或修改文章",
            ] if active_alerts else [],
            "recent_alert_history": runtime_timeline[:5],
        }

    @staticmethod
    def build_ai_runtime_observability_center(dashboard: dict) -> dict:
        """构建只读 AI 运行时可观测中心，不触发任何运行时动作。"""
        dashboard = dashboard or {}
        incidents = list(dashboard.get("ai_ops_incident_feed") or [])
        timeline = list(dashboard.get("ai_ops_timeline") or [])
        recent_fail_articles = list(dashboard.get("recent_fail_articles") or [])
        top_active_articles = list(dashboard.get("top_active_articles") or [])
        priority_queue = list(dashboard.get("ai_ops_priority_queue") or [])
        summary = dashboard.get("summary") or {}

        failed_count = sum(ArticleHealthService._safe_int(item.get("failed_count")) for item in recent_fail_articles)
        active_count = sum(ArticleHealthService._safe_int(item.get("ai_operation_count")) for item in top_active_articles)
        total_articles = ArticleHealthService._safe_int(summary.get("total_articles"))
        agent_failure_rate = round((failed_count / max(active_count, 1)) * 100, 1) if active_count else 0
        queue_count = len(priority_queue)
        blocked_tasks = [
            {
                "title": item.get("title") or "待处理对象",
                "article_id": item.get("article_id") or "",
                "reason": "高优先级对象需要人工复核",
                "level": item.get("priority_level") or "warning",
            }
            for item in priority_queue
            if item.get("priority_level") in ("critical", "high")
        ][:5]
        status = "attention" if failed_count or blocked_tasks else ("idle" if not (active_count or timeline or incidents) else "healthy")
        health_score = max(0, min(100, 100 - min(failed_count * 5, 40) - min(len(blocked_tasks) * 8, 40)))

        return {
            "runtime_status": status,
            "runtime_health": {
                "score": health_score,
                "level": "attention" if status == "attention" else "healthy",
                "summary": "当前暂无运行时观测数据。" if status == "idle" else f"当前运行时健康分 {health_score}，失败任务 {failed_count} 个，阻塞对象 {len(blocked_tasks)} 个。",
            },
            "agent_failure_rate": agent_failure_rate,
            "publish_task_metrics": {
                "failed_count": failed_count,
                "active_article_count": len(top_active_articles),
                "observed_articles": total_articles,
            },
            "queue_pressure": {
                "pending_count": queue_count,
                "level": "attention" if queue_count else "healthy",
                "summary": f"当前优先处理队列 {queue_count} 个对象。" if queue_count else "当前暂无队列压力。",
            },
            "failure_hotspots": recent_fail_articles[:5],
            "runtime_timeline": timeline[:5] or incidents[:5],
            "blocked_tasks": blocked_tasks,
            "runtime_advice": "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。",
        }

    @staticmethod
    def build_ai_autoops_control_tower(dashboard: dict) -> dict:
        """构建只读 AutoOps 总控数据，不执行任何动作。"""
        dashboard = dashboard or {}
        playbooks = list(dashboard.get("ai_ops_playbooks") or [])
        priority_queue = list(dashboard.get("ai_ops_priority_queue") or [])
        action_count = sum(len(playbook.get("actions") or []) for playbook in playbooks)
        risky_count = sum(1 for item in priority_queue if item.get("priority_level") in ("critical", "high"))
        status = "need_attention" if risky_count else ("review_required" if action_count else "all_safe")
        return {
            "control_status": status,
            "summary": (
                f"当前识别到 {action_count} 个可复核动作，{risky_count} 个高优先级对象。"
                if action_count or risky_count
                else "当前暂无需要进入 AutoOps 总控的动作。"
            ),
            "action_count": action_count,
            "risky_count": risky_count,
        }

    @staticmethod
    def build_ai_autoops_action_review_center(dashboard: dict, control_tower: dict | None = None) -> dict:
        """构建只读自动运营动作复核中心。"""
        dashboard = dashboard or {}
        control_tower = control_tower or {}
        playbooks = list(dashboard.get("ai_ops_playbooks") or [])
        safe_actions = []
        requires_confirmation = []
        risky_actions = []
        blocked_actions = []

        for playbook in playbooks:
            playbook_level = playbook.get("level") or playbook.get("priority") or "secondary"
            for action in list(playbook.get("actions") or []):
                item = {
                    "label": action.get("label") or "自动运营动作",
                    "action_type": action.get("action_type") or "unknown",
                    "article_id": action.get("article_id") or "",
                    "reason": playbook.get("summary") or playbook.get("title") or "",
                    "level": playbook_level,
                }
                if item["action_type"] == "open_article":
                    safe_actions.append(item)
                elif playbook_level in ("danger", "critical"):
                    risky_actions.append(item)
                else:
                    requires_confirmation.append(item)

        if control_tower.get("risky_count"):
            risky_actions.extend({
                "label": item.get("title") or "高优先级对象",
                "action_type": "manual_review",
                "article_id": item.get("article_id") or "",
                "reason": "优先级较高，建议人工复核后处理",
                "level": item.get("priority_level") or "warning",
            } for item in list(dashboard.get("ai_ops_priority_queue") or [])[:5])

        review_status = "risky" if risky_actions else ("review_required" if requires_confirmation else "all_safe")
        return {
            "review_status": review_status,
            "summary": (
                "当前暂无需要复核的自动运营动作。"
                if not (safe_actions or requires_confirmation or risky_actions or blocked_actions)
                else f"已汇总 {len(safe_actions)} 个安全动作、{len(requires_confirmation)} 个需确认动作、{len(risky_actions)} 个风险动作。"
            ),
            "safe_actions": safe_actions,
            "requires_confirmation": requires_confirmation,
            "risky_actions": risky_actions,
            "blocked_actions": blocked_actions,
            "recommended_actions": [
                "先处理需人工复核的动作",
                "风险动作必须保持人工确认",
                "禁止自动触发审核、发布、Agent 或文章修改",
            ],
        }

    @staticmethod
    def build_ai_execution_sandbox_center(dashboard: dict, action_review: dict | None = None) -> dict:
        """构建只读执行沙箱中心，仅模拟动作风险。"""
        action_review = action_review or {}
        safe_actions = list(action_review.get("safe_actions") or [])
        confirmation_actions = list(action_review.get("requires_confirmation") or [])
        risky_actions = list(action_review.get("risky_actions") or [])
        blocked_actions = list(action_review.get("blocked_actions") or [])
        simulated_actions = safe_actions + confirmation_actions + risky_actions + blocked_actions
        recommended_to_execute = safe_actions[:5]
        not_recommended = risky_actions + blocked_actions
        sandbox_status = "risky" if not_recommended else ("safe" if simulated_actions else "healthy")
        return {
            "sandbox_status": sandbox_status,
            "summary": (
                "当前暂无可沙箱推演的动作。"
                if not simulated_actions
                else f"沙箱只读推演 {len(simulated_actions)} 个动作，建议执行 {len(recommended_to_execute)} 个，暂不建议 {len(not_recommended)} 个。"
            ),
            "simulated_actions": simulated_actions,
            "recommended_to_execute": recommended_to_execute,
            "not_recommended": not_recommended,
            "risk_warnings": [item.get("reason") or item.get("label") for item in not_recommended[:5]],
            "sandbox_advice": "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。",
        }

    @staticmethod
    def build_ai_approval_pipeline_center(dashboard: dict, execution_sandbox: dict | None = None) -> dict:
        """构建只读人工批准流中心。"""
        execution_sandbox = execution_sandbox or {}
        pending = list(execution_sandbox.get("not_recommended") or [])
        approved = list(execution_sandbox.get("recommended_to_execute") or [])
        rejected = []
        expired = []
        approval_status = "pending" if pending else ("healthy" if approved else "healthy")
        return {
            "approval_status": approval_status,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "expired": expired,
            "approval_recommendations": [
                "所有待批准动作必须人工确认",
                "通过批准前不触发审核、发布、Agent 或文章修改",
            ] if pending else [],
            "summary": (
                "当前暂无待批准动作。"
                if not (pending or approved or rejected or expired)
                else f"待批准 {len(pending)} 个，已建议通过 {len(approved)} 个，拒绝 {len(rejected)} 个，过期 {len(expired)} 个。"
            ),
            "approval_advice": "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。",
        }

    @staticmethod
    def build_ai_approval_audit_center(dashboard: dict, approval_pipeline: dict | None = None) -> dict:
        """构建只读批准审计中心。"""
        approval_pipeline = approval_pipeline or {}
        pending = list(approval_pipeline.get("pending") or [])
        approved = list(approval_pipeline.get("approved") or [])
        rejected = list(approval_pipeline.get("rejected") or [])
        expired = list(approval_pipeline.get("expired") or [])
        risky_pending = [
            item for item in pending
            if item.get("level") in ("danger", "critical", "high", "warning")
        ]
        audit_status = "attention" if risky_pending or expired else "healthy"
        return {
            "audit_status": audit_status,
            "pending_count": len(pending),
            "approved_count": len(approved),
            "rejected_count": len(rejected),
            "expired_count": len(expired),
            "stale_pending": [],
            "risky_pending": risky_pending,
            "rejected_patterns": [],
            "expired_patterns": [],
            "audit_findings": [
                f"存在 {len(risky_pending)} 个风险待批准动作，建议保持人工复核。"
            ] if risky_pending else [],
            "summary": (
                "当前暂无批准审计风险。"
                if not (pending or approved or rejected or expired)
                else f"批准审计汇总：待批准 {len(pending)}，已建议通过 {len(approved)}，拒绝 {len(rejected)}，过期 {len(expired)}。"
            ),
            "audit_advice": "仅用于运营分析，不会自动执行审核、发布、Agent 或修改文章。",
        }

    @staticmethod
    def build_decision_brief_export_text(dashboard: dict) -> str:
        """构建 AI 决策简报 TXT 导出内容，只读汇总现有 Dashboard 字段。"""
        brief = ((dashboard or {}).get("ai_decision_brief") or {})
        lines = [
            "AI 决策简报",
            "",
            f"标题：{brief.get('title') or 'AI 决策简报'}",
            f"状态：{ArticleHealthService._ai_status_label(brief.get('level') or 'success')}",
            f"摘要：{brief.get('summary') or '当前暂无足够数据生成 AI 决策简报。'}",
            f"核心问题：{brief.get('top_issue') or '当前暂无明显问题'}",
            f"建议动作：{brief.get('top_action') or '保持当前审核与终检节奏'}",
            "",
            "核心指标：",
        ]
        metrics = list(brief.get("metrics") or [])
        if metrics:
            for item in metrics:
                lines.append(f"- {item.get('label') or '指标'}：{item.get('value', '')}")
        else:
            lines.append("- 当前暂无相关数据")
        return "\n".join(lines)

    @staticmethod
    def build_decision_brief_export_rows(dashboard: dict) -> list[dict]:
        """构建 AI 决策简报 CSV 导出行。"""
        brief = ((dashboard or {}).get("ai_decision_brief") or {})
        rows = [
            {"项目": "标题", "内容": brief.get("title") or "AI 决策简报"},
            {"项目": "状态", "内容": ArticleHealthService._ai_status_label(brief.get("level") or "success")},
            {"项目": "摘要", "内容": brief.get("summary") or "当前暂无足够数据生成 AI 决策简报。"},
            {"项目": "核心问题", "内容": brief.get("top_issue") or "当前暂无明显问题"},
            {"项目": "建议动作", "内容": brief.get("top_action") or "保持当前审核与终检节奏"},
        ]
        for item in list(brief.get("metrics") or []):
            rows.append({"项目": item.get("label") or "指标", "内容": item.get("value", "")})
        return rows

    @staticmethod
    def build_governance_export_rows(dashboard: dict, export_type: str) -> list[dict]:
        """构建治理中心 CSV 导出行。"""
        dashboard = dashboard or {}
        governance = dashboard.get("ai_governance_center") or {}
        action_plan = dashboard.get("ai_governance_action_plan") or {}

        if export_type == "governance_rules":
            rows = []
            for item in list(governance.get("metrics") or []):
                rows.append({
                    "类型": "治理指标",
                    "规则": item.get("label") or "治理指标",
                    "说明": item.get("value", 0),
                })
            if not rows:
                rows.append({"类型": "治理规则", "规则": "默认人工复核", "说明": "当前暂无额外治理规则"})
            return rows

        if export_type == "violations":
            return [
                {
                    "级别": ArticleHealthService._ai_status_label(item.get("level") or "secondary"),
                    "标题": item.get("title") or "治理风险提示",
                    "说明": item.get("message") or "",
                    "时间": item.get("created_at") or "",
                }
                for item in list(governance.get("alerts") or [])
            ]

        if export_type == "high_risk_targets":
            targets = list(dashboard.get("persistent_risk_articles") or []) or list(dashboard.get("top_risk_articles") or [])
            return [
                {
                    "文章ID": item.get("article_id") or "",
                    "标题": item.get("title") or "未知文章",
                    "风险等级": ArticleHealthService._ai_status_label(item.get("risk_level") or "unknown"),
                    "健康分": item.get("health_score", item.get("score", "")),
                    "说明": "需要重点关注" if item.get("need_manual_attention") else "",
                }
                for item in targets
            ]

        if export_type == "today_must_do":
            rows = []
            for item in list(dashboard.get("ai_ops_priority_queue") or []):
                rows.append({
                    "优先级": ArticleHealthService._ai_status_label(item.get("priority_level") or "normal"),
                    "标题": item.get("title") or "未知文章",
                    "建议动作": "；".join(item.get("reasons") or []),
                    "相关对象": item.get("article_id") or "",
                })
            for item in list(action_plan.get("actions") or []):
                rows.append({
                    "优先级": ArticleHealthService._ai_status_label(item.get("priority") or "normal"),
                    "标题": item.get("title") or "AI 治理动作",
                    "建议动作": "；".join(item.get("recommended_actions") or []),
                    "相关对象": item.get("summary") or "",
                })
            return rows

        return []

    @staticmethod
    def build_simulation_export_rows(dashboard: dict, export_type: str) -> list[dict]:
        """构建策略模拟 CSV 导出行。"""
        dashboard = dashboard or {}
        simulation = dashboard.get("ai_simulation_center") or {}
        history = dashboard.get("ai_simulation_history_summary") or {}
        scenarios = list(simulation.get("scenarios") or [])

        if export_type == "scenarios":
            selected = scenarios
        elif export_type == "best_scenario":
            selected = [item for item in scenarios if item.get("level") == "success"][:1] or scenarios[:1]
        elif export_type == "risk_scenario":
            selected = [item for item in scenarios if item.get("level") in ("danger", "warning")] or scenarios[-1:]
        elif export_type == "simulation_history":
            rows = [
                {
                    "类型": "评分",
                    "标题": "最近评分",
                    "说明": score,
                    "时间": "",
                }
                for score in list(history.get("recent_scores") or [])
            ]
            rows.extend({
                "类型": ArticleHealthService._ai_status_label(item.get("level") or "secondary"),
                "标题": item.get("title") or "运营时间线事件",
                "说明": item.get("message") or "",
                "时间": item.get("created_at") or "",
            } for item in list(history.get("recent_events") or []))
            return rows
        else:
            return []

        return [
            {
                "场景": item.get("name") or "策略模拟场景",
                "影响": item.get("impact") or "",
                "等级": ArticleHealthService._ai_status_label(item.get("level") or "secondary"),
            }
            for item in selected
        ]

    @staticmethod
    def build_sop_export_text(dashboard: dict, sop_type: str = "all") -> str:
        """构建 AI Dashboard SOP TXT 导出内容。"""
        rows = ArticleHealthService.build_sop_export_rows(dashboard, sop_type=sop_type)
        lines = ["AI Dashboard SOP", ""]
        if rows:
            for index, row in enumerate(rows, 1):
                lines.append(f"{index}. [{row.get('类型')}] {row.get('步骤')}")
                lines.append(f"   {row.get('说明')}")
        else:
            lines.append("当前暂无相关 SOP 数据")
        return "\n".join(lines)

    @staticmethod
    def build_sop_export_rows(dashboard: dict, sop_type: str = "all") -> list[dict]:
        """构建 AI Dashboard SOP CSV 导出行。"""
        dashboard = dashboard or {}
        action_plan = (dashboard.get("ai_governance_action_plan") or {}).get("actions") or []
        scenarios = (dashboard.get("ai_simulation_center") or {}).get("scenarios") or []

        base_rows = {
            "risk_control_sops": [
                {"类型": "风险控制 SOP", "步骤": "优先查看高风险对象", "说明": "根据 AI 运营优先处理队列逐项复核。"},
                {"类型": "风险控制 SOP", "步骤": "复核发布前终检", "说明": "确认文章结构、合规表达和微信兼容性。"},
            ],
            "recovery_sops": [
                {"类型": "恢复 SOP", "步骤": "跟踪恢复案例", "说明": "复盘健康分回升的文章并沉淀可复用做法。"},
            ],
            "governance_sops": [
                {"类型": "治理 SOP", "步骤": item.get("title") or "执行治理动作", "说明": "；".join(item.get("recommended_actions") or []) or item.get("summary") or ""}
                for item in action_plan
            ],
            "ops_checklists": [
                {"类型": "运营检查清单", "步骤": "检查风险事件", "说明": "确认异常播报、治理风险和今日必须处理事项。"},
                {"类型": "运营检查清单", "步骤": "检查策略推演", "说明": "查看推荐方案、风险方案和模拟历史。"},
            ],
            "duty_sops": [
                {"类型": "值班 SOP", "步骤": "确认当前值班模式", "说明": ((dashboard.get("ai_ops_duty_mode") or {}).get("recommended_action") or "保持当前审核与终检节奏。")},
            ],
            "incident_response_sops": [
                {"类型": "事件响应 SOP", "步骤": item.get("name") or "执行模拟方案", "说明": item.get("impact") or ""}
                for item in scenarios
            ],
        }

        if not base_rows["governance_sops"]:
            base_rows["governance_sops"] = [{"类型": "治理 SOP", "步骤": "保持人工复核节奏", "说明": "当前暂无额外治理动作。"}]
        if not base_rows["incident_response_sops"]:
            base_rows["incident_response_sops"] = [{"类型": "事件响应 SOP", "步骤": "保持常规巡检", "说明": "当前暂无模拟事件。"}]

        if sop_type == "all":
            rows = []
            for values in base_rows.values():
                rows.extend(values)
            return rows
        return list(base_rows.get(sop_type) or [])

    @staticmethod
    def build_runtime_learning_export_text(dashboard: dict, export_type: str = "all") -> str:
        """构建 AI 运行时学习中心 TXT 导出内容，只读汇总现有 Dashboard 字段。"""
        rows = ArticleHealthService.build_runtime_learning_export_rows(
            dashboard,
            export_type=export_type,
            include_empty_row=False,
        )
        lines = ["【AI 运行时学习中心】"]
        if not rows:
            lines.append("当前暂无可导出的学习数据。")
            return "\n".join(lines)

        for index, row in enumerate(rows, 1):
            lines.append("")
            lines.append(f"{index}. [{row.get('类别') or 'AI运行时学习'}] {row.get('标题/对象') or '学习项'}")
            if row.get("等级/状态"):
                lines.append(f"   等级/状态：{row.get('等级/状态')}")
            if row.get("摘要"):
                lines.append(f"   摘要：{row.get('摘要')}")
            if row.get("证据/原因"):
                lines.append(f"   证据/原因：{row.get('证据/原因')}")
            if row.get("建议动作"):
                lines.append(f"   建议动作：{row.get('建议动作')}")
            if row.get("来源"):
                lines.append(f"   来源：{row.get('来源')}")
        return "\n".join(lines)

    @staticmethod
    def build_runtime_learning_export_rows(
        dashboard: dict,
        export_type: str = "all",
        include_empty_row: bool = True,
    ) -> list[dict]:
        """构建 AI 运行时学习中心 CSV 导出行，只读导出现有学习沉淀。"""
        learning = ((dashboard or {}).get("ai_runtime_learning_center") or {})
        section_labels = {
            "key_learnings": "关键学习",
            "repeated_incident_patterns": "重复事故模式",
            "effective_recovery_patterns": "有效恢复模式",
            "unstable_runtime_components": "不稳定组件",
            "sop_improvement_suggestions": "SOP 改进建议",
            "governance_improvement_suggestions": "治理改进建议",
            "learning_history": "学习历史",
        }
        if export_type == "all":
            selected_sections = list(section_labels.keys())
        elif export_type in section_labels:
            selected_sections = [export_type]
        else:
            selected_sections = []

        rows = []
        for section in selected_sections:
            label = section_labels[section]
            for item in list(learning.get(section) or []):
                if isinstance(item, dict):
                    item_type = item.get("type") or ""
                    rows.append({
                        "类别": label,
                        "标题/对象": item.get("title") or item.get("name") or item.get("text") or label,
                        "等级/状态": ArticleHealthService._ai_status_label(item.get("level") or item.get("status") or item_type),
                        "摘要": item.get("summary") or item.get("message") or item.get("text") or "",
                        "证据/原因": item.get("reason") or item.get("evidence") or "",
                        "建议动作": item.get("action") or item.get("suggestion") or item.get("recommended_action") or "",
                        "来源": item.get("source") or item_type or "AI运行时学习中心",
                    })
                else:
                    rows.append({
                        "类别": label,
                        "标题/对象": str(item),
                        "等级/状态": "",
                        "摘要": str(item),
                        "证据/原因": "",
                        "建议动作": "",
                        "来源": "AI运行时学习中心",
                    })

        if rows or not include_empty_row:
            return rows
        return [{
            "类别": "AI运行时学习",
            "标题/对象": "状态",
            "等级/状态": "暂无可导出的学习数据",
            "摘要": "",
            "证据/原因": "",
            "建议动作": "",
            "来源": "",
        }]

    @staticmethod
    def build_runtime_knowledge_sync_export_text(dashboard: dict, export_type: str = "all") -> str:
        """构建 AI 运行时知识同步中心 TXT 导出内容，只读汇总现有 Dashboard 字段。"""
        rows = ArticleHealthService.build_runtime_knowledge_sync_export_rows(
            dashboard,
            export_type=export_type,
            include_empty_row=False,
        )
        lines = ["【AI 运行时知识同步中心】"]
        if not rows:
            lines.append("当前暂无可导出的知识同步数据。")
            return "\n".join(lines)

        for index, row in enumerate(rows, 1):
            lines.append("")
            lines.append(f"{index}. [{row.get('类别') or 'AI运行时知识同步'}] {row.get('标题/对象') or '同步项'}")
            if row.get("等级/状态"):
                lines.append(f"   等级/状态：{row.get('等级/状态')}")
            if row.get("摘要"):
                lines.append(f"   摘要：{row.get('摘要')}")
            if row.get("目标中心"):
                lines.append(f"   目标中心：{row.get('目标中心')}")
            if row.get("来源"):
                lines.append(f"   来源：{row.get('来源')}")
            if row.get("建议动作"):
                lines.append(f"   建议动作：{row.get('建议动作')}")
        return "\n".join(lines)

    @staticmethod
    def build_runtime_knowledge_sync_export_rows(
        dashboard: dict,
        export_type: str = "all",
        include_empty_row: bool = True,
    ) -> list[dict]:
        """构建 AI 运行时知识同步中心 CSV 导出行，只读导出现有同步建议。"""
        sync_center = ((dashboard or {}).get("ai_runtime_knowledge_sync_center") or {})
        section_labels = {
            "knowledge_sync_suggestions": ("知识库同步建议", "知识库"),
            "sop_sync_suggestions": ("SOP 同步建议", "SOP 中心"),
            "governance_sync_suggestions": ("治理同步建议", "治理中心"),
            "checklist_sync_suggestions": ("检查清单同步建议", "检查清单"),
            "sync_gaps": ("同步缺口", "同步复核"),
            "sync_history": ("同步历史", "运行时历史"),
        }
        if export_type == "all":
            selected_sections = list(section_labels.keys())
        elif export_type in section_labels:
            selected_sections = [export_type]
        else:
            selected_sections = []

        rows = []
        for section in selected_sections:
            label, target = section_labels[section]
            for item in list(sync_center.get(section) or []):
                if isinstance(item, dict):
                    item_type = item.get("type") or ""
                    rows.append({
                        "类别": label,
                        "标题/对象": item.get("title") or item.get("name") or label,
                        "等级/状态": ArticleHealthService._ai_status_label(item.get("level") or item.get("status") or item_type),
                        "摘要": item.get("summary") or item.get("message") or item.get("text") or "",
                        "目标中心": item.get("target") or target,
                        "来源": item.get("source") or item_type or "AI运行时知识同步中心",
                        "建议动作": item.get("action") or item.get("suggestion") or item.get("recommended_action") or "",
                    })
                else:
                    rows.append({
                        "类别": label,
                        "标题/对象": str(item),
                        "等级/状态": "",
                        "摘要": str(item),
                        "目标中心": target,
                        "来源": "AI运行时知识同步中心",
                        "建议动作": "",
                    })

        if rows or not include_empty_row:
            return rows
        return [{
            "类别": "AI运行时知识同步",
            "标题/对象": "状态",
            "等级/状态": "暂无可导出的知识同步数据",
            "摘要": "",
            "目标中心": "",
            "来源": "",
            "建议动作": "",
        }]

    @staticmethod
    def build_runtime_weekly_review_export_text(dashboard: dict) -> str:
        """构建 AI 运行时周复盘中心 TXT 导出内容。"""
        rows = ArticleHealthService.build_runtime_weekly_review_export_rows(
            dashboard,
            include_empty_row=False,
        )
        weekly = ((dashboard or {}).get("ai_runtime_weekly_review_center") or {})
        lines = ["【AI 运行时周复盘中心】", f"周期：{weekly.get('week_range') or ''}"]
        if not rows:
            lines.append("当前暂无可导出的运行时周复盘数据。")
            return "\n".join(lines)
        for index, row in enumerate(rows, 1):
            lines.append("")
            lines.append(f"{index}. [{row.get('类型') or '周复盘'}] {row.get('标题') or '复盘项'}")
            if row.get("状态/等级"):
                lines.append(f"   状态/等级：{row.get('状态/等级')}")
            if row.get("摘要"):
                lines.append(f"   摘要：{row.get('摘要')}")
            if row.get("建议动作"):
                lines.append(f"   建议动作：{row.get('建议动作')}")
        return "\n".join(lines)

    @staticmethod
    def build_runtime_weekly_review_export_rows(
        dashboard: dict,
        include_empty_row: bool = True,
    ) -> list[dict]:
        """构建 AI 运行时周复盘中心 CSV 导出行。"""
        weekly = ((dashboard or {}).get("ai_runtime_weekly_review_center") or {})
        review_keys = [
            ("runtime_summary", "运行时概览"),
            ("alert_review", "告警复盘"),
            ("incident_review", "事故复盘"),
            ("recovery_review", "恢复复盘"),
            ("postmortem_review", "事故复盘沉淀"),
            ("learning_review", "学习复盘"),
            ("knowledge_sync_review", "知识同步复盘"),
        ]
        rows = []
        for key, label in review_keys:
            item = weekly.get(key) or {}
            if item:
                rows.append({
                    "类型": label,
                    "标题": item.get("title") or label,
                    "状态/等级": ArticleHealthService._ai_status_label(item.get("type") or key),
                    "摘要": item.get("summary") or "",
                    "建议动作": "",
                })
        for item in list(weekly.get("top_risks") or []):
            rows.append({
                "类型": "重点风险",
                "标题": item.get("title") or "运行时风险",
                "状态/等级": ArticleHealthService._ai_status_label(item.get("level") or "warning"),
                "摘要": item.get("summary") or "",
                "建议动作": "",
            })
        for item in list(weekly.get("weekly_wins") or []):
            rows.append({"类型": "本周有效经验", "标题": str(item), "状态/等级": "", "摘要": str(item), "建议动作": ""})
        for item in list(weekly.get("next_week_focus") or []):
            rows.append({"类型": "下周关注", "标题": str(item), "状态/等级": "", "摘要": str(item), "建议动作": ""})
        for item in list(weekly.get("recommended_actions") or []):
            rows.append({"类型": "推荐动作", "标题": str(item), "状态/等级": "", "摘要": "", "建议动作": str(item)})

        if rows or not include_empty_row:
            return rows
        return [{
            "类型": "AI运行时周复盘",
            "标题": "状态",
            "状态/等级": "暂无可导出的运行时周复盘数据",
            "摘要": "",
            "建议动作": "",
        }]

    @staticmethod
    def build_runtime_feedback_loop_export_text(dashboard: dict) -> str:
        """构建 AI 运行时反馈闭环中心 TXT 导出内容。"""
        rows = ArticleHealthService.build_runtime_feedback_loop_export_rows(
            dashboard,
            include_empty_row=False,
        )
        lines = ["【AI 运行时反馈闭环中心】"]
        if not rows:
            lines.append("当前暂无可导出的运行时反馈闭环数据。")
            return "\n".join(lines)
        for index, row in enumerate(rows, 1):
            lines.append("")
            lines.append(f"{index}. [{row.get('类型') or '反馈闭环'}] {row.get('标题') or '反馈项'}")
            if row.get("状态/等级"):
                lines.append(f"   状态/等级：{row.get('状态/等级')}")
            if row.get("摘要"):
                lines.append(f"   摘要：{row.get('摘要')}")
            if row.get("建议动作"):
                lines.append(f"   建议动作：{row.get('建议动作')}")
        return "\n".join(lines)

    @staticmethod
    def build_runtime_feedback_loop_export_rows(
        dashboard: dict,
        include_empty_row: bool = True,
    ) -> list[dict]:
        """构建 AI 运行时反馈闭环中心 CSV 导出行。"""
        feedback = ((dashboard or {}).get("ai_runtime_feedback_loop_center") or {})
        section_labels = {
            "effective_actions": "有效动作",
            "ineffective_actions": "低效动作",
            "high_value_recoveries": "高价值恢复",
            "low_value_suggestions": "低价值建议",
            "governance_feedback": "治理反馈",
            "sop_feedback": "SOP 反馈",
            "feedback_gaps": "反馈缺口",
            "feedback_history": "反馈历史",
        }
        rows = []
        for section, label in section_labels.items():
            for item in list(feedback.get(section) or []):
                if isinstance(item, dict):
                    item_type = item.get("type") or ""
                    rows.append({
                        "类型": label,
                        "标题": item.get("title") or item.get("name") or label,
                        "状态/等级": ArticleHealthService._ai_status_label(item.get("level") or item.get("status") or item_type),
                        "摘要": item.get("summary") or item.get("message") or item.get("text") or "",
                        "建议动作": item.get("action") or item.get("suggestion") or item.get("recommended_action") or "",
                    })
                else:
                    rows.append({"类型": label, "标题": str(item), "状态/等级": "", "摘要": str(item), "建议动作": ""})
        for item in list(feedback.get("recommended_actions") or []):
            rows.append({"类型": "推荐动作", "标题": str(item), "状态/等级": "", "摘要": "", "建议动作": str(item)})

        if rows or not include_empty_row:
            return rows
        return [{
            "类型": "AI运行时反馈闭环",
            "标题": "状态",
            "状态/等级": "暂无可导出的运行时反馈闭环数据",
            "摘要": "",
            "建议动作": "",
        }]

    @staticmethod
    def build_runtime_evolution_export_text(dashboard: dict) -> str:
        """构建 AI 运行时进化中心 TXT 导出内容。"""
        rows = ArticleHealthService.build_runtime_evolution_export_rows(
            dashboard,
            include_empty_row=False,
        )
        lines = ["【AI 运行时进化中心】"]
        if not rows:
            lines.append("当前暂无可导出的运行时进化数据。")
            return "\n".join(lines)
        for index, row in enumerate(rows, 1):
            lines.append("")
            lines.append(f"{index}. [{row.get('类型') or '进化项'}] {row.get('标题') or '运行时进化'}")
            if row.get("等级/状态"):
                lines.append(f"   等级/状态：{row.get('等级/状态')}")
            if row.get("分数"):
                lines.append(f"   分数：{row.get('分数')}")
            if row.get("摘要"):
                lines.append(f"   摘要：{row.get('摘要')}")
            if row.get("建议动作"):
                lines.append(f"   建议动作：{row.get('建议动作')}")
        return "\n".join(lines)

    @staticmethod
    def build_runtime_evolution_export_rows(
        dashboard: dict,
        include_empty_row: bool = True,
    ) -> list[dict]:
        """构建 AI 运行时进化中心 CSV 导出行。"""
        evolution = ((dashboard or {}).get("ai_runtime_evolution_center") or {})
        rows = []
        maturity_items = [
            ("runtime_maturity", "运行时成熟度"),
            ("governance_maturity", "治理成熟度"),
            ("sop_maturity", "SOP 成熟度"),
            ("feedback_maturity", "反馈成熟度"),
            ("knowledge_maturity", "知识成熟度"),
        ]
        for key, title in maturity_items:
            item = evolution.get(key) or {}
            if item:
                rows.append({
                    "类型": "成熟度",
                    "标题": title,
                    "等级/状态": ArticleHealthService._ai_status_label(item.get("level") or ""),
                    "分数": item.get("score", ""),
                    "摘要": title,
                    "建议动作": "",
                })
        section_labels = {
            "positive_signals": "正向信号",
            "risk_signals": "风险信号",
            "evolution_risks": "进化风险",
            "evolution_benefits": "进化收益",
            "long_term_recommendations": "长期建议",
            "evolution_history": "进化历史",
        }
        for section, label in section_labels.items():
            for item in list(evolution.get(section) or []):
                if isinstance(item, dict):
                    item_type = item.get("type") or ""
                    rows.append({
                        "类型": label,
                        "标题": item.get("title") or item.get("name") or label,
                        "等级/状态": ArticleHealthService._ai_status_label(item.get("level") or item.get("status") or item_type),
                        "分数": item.get("score", ""),
                        "摘要": item.get("summary") or item.get("message") or item.get("text") or "",
                        "建议动作": item.get("action") or item.get("suggestion") or item.get("recommended_action") or "",
                    })
                else:
                    text = str(item)
                    rows.append({
                        "类型": label,
                        "标题": text,
                        "等级/状态": "",
                        "分数": "",
                        "摘要": text,
                        "建议动作": text if section == "long_term_recommendations" else "",
                    })

        if rows or not include_empty_row:
            return rows
        return [{
            "类型": "AI运行时进化",
            "标题": "状态",
            "等级/状态": "暂无可导出的运行时进化数据",
            "分数": "",
            "摘要": "",
            "建议动作": "",
        }]

    @staticmethod
    def build_runtime_orchestrator_export_text(dashboard: dict) -> str:
        """构建 AI 运行时编排中心 TXT 导出内容。"""
        rows = ArticleHealthService.build_runtime_orchestrator_export_rows(
            dashboard,
            include_empty_row=False,
        )
        lines = ["【AI 运行时编排中心】"]
        if not rows:
            lines.append("当前暂无可导出的运行时编排数据。")
            return "\n".join(lines)
        for index, row in enumerate(rows, 1):
            lines.append("")
            lines.append(f"{index}. [{row.get('类型') or '编排项'}] {row.get('标题') or '运行时编排'}")
            if row.get("状态/等级"):
                lines.append(f"   状态/等级：{row.get('状态/等级')}")
            if row.get("摘要"):
                lines.append(f"   摘要：{row.get('摘要')}")
            if row.get("建议动作"):
                lines.append(f"   建议动作：{row.get('建议动作')}")
        return "\n".join(lines)

    @staticmethod
    def build_runtime_orchestrator_export_rows(
        dashboard: dict,
        include_empty_row: bool = True,
    ) -> list[dict]:
        """构建 AI 运行时编排中心 CSV 导出行。"""
        orchestrator = ((dashboard or {}).get("ai_runtime_orchestrator_center") or {})
        rows = []
        section_labels = {
            "global_priorities": "全局优先级",
            "runtime_focus": "运行时焦点",
            "cross_module_links": "跨模块联动",
            "resource_allocation": "资源分配",
            "unified_execution_order": "统一执行顺序",
            "blocked_dependencies": "依赖阻塞",
            "escalation_suggestions": "升级建议",
            "system_recommended_actions": "系统推荐动作",
        }
        for section, label in section_labels.items():
            for item in list(orchestrator.get(section) or []):
                if isinstance(item, dict):
                    item_type = item.get("type") or ""
                    rows.append({
                        "类型": label,
                        "标题": item.get("title") or item.get("name") or label,
                        "状态/等级": ArticleHealthService._ai_status_label(item.get("level") or item.get("status") or item_type),
                        "摘要": item.get("summary") or item.get("message") or item.get("text") or "",
                        "建议动作": item.get("action") or item.get("suggestion") or item.get("recommended_action") or "",
                    })
                else:
                    text = str(item)
                    rows.append({
                        "类型": label,
                        "标题": text,
                        "状态/等级": "",
                        "摘要": text,
                        "建议动作": text if section in {"escalation_suggestions", "system_recommended_actions"} else "",
                    })

        if rows or not include_empty_row:
            return rows
        return [{
            "类型": "AI运行时编排",
            "标题": "状态",
            "状态/等级": "暂无可导出的运行时编排数据",
            "摘要": "",
            "建议动作": "",
        }]

    @staticmethod
    def build_runtime_control_policy_export_text(dashboard: dict) -> str:
        """构建 AI 运行时控制策略中心 TXT 导出内容。"""
        rows = ArticleHealthService.build_runtime_control_policy_export_rows(
            dashboard,
            include_empty_row=False,
        )
        lines = ["【AI 运行时控制策略中心】"]
        if not rows:
            lines.append("当前暂无可导出的运行时控制策略数据。")
            return "\n".join(lines)
        for index, row in enumerate(rows, 1):
            lines.append("")
            lines.append(f"{index}. [{row.get('类型') or '控制策略'}] {row.get('标题') or '运行时控制策略'}")
            if row.get("状态/等级"):
                lines.append(f"   状态/等级：{row.get('状态/等级')}")
            if row.get("摘要"):
                lines.append(f"   摘要：{row.get('摘要')}")
            if row.get("建议动作"):
                lines.append(f"   建议动作：{row.get('建议动作')}")
        return "\n".join(lines)

    @staticmethod
    def build_runtime_control_policy_export_rows(
        dashboard: dict,
        include_empty_row: bool = True,
    ) -> list[dict]:
        """构建 AI 运行时控制策略中心 CSV 导出行。"""
        policy = ((dashboard or {}).get("ai_runtime_control_policy_center") or {})
        rows = []
        global_policy = policy.get("global_policy") or {}
        if global_policy:
            rows.append({
                "类型": "全局策略",
                "标题": global_policy.get("title") or "全局运行时控制策略",
                "状态/等级": ArticleHealthService._ai_status_label(global_policy.get("status") or global_policy.get("type") or ""),
                "摘要": global_policy.get("summary") or "",
                "建议动作": "",
            })
        section_labels = {
            "allowed_actions": "允许动作",
            "restricted_actions": "限制动作",
            "forbidden_actions": "禁止动作",
            "manual_review_required": "人工复核",
            "pause_policies": "暂停策略",
            "recovery_policies": "恢复策略",
            "growth_policies": "增长策略",
            "recommended_actions": "推荐动作",
        }
        for section, label in section_labels.items():
            for item in list(policy.get(section) or []):
                if isinstance(item, dict):
                    item_type = item.get("type") or ""
                    rows.append({
                        "类型": label,
                        "标题": item.get("title") or item.get("name") or label,
                        "状态/等级": ArticleHealthService._ai_status_label(item.get("level") or item.get("status") or item_type),
                        "摘要": item.get("summary") or item.get("message") or item.get("text") or "",
                        "建议动作": item.get("action") or item.get("suggestion") or item.get("recommended_action") or "",
                    })
                else:
                    text = str(item)
                    rows.append({
                        "类型": label,
                        "标题": text,
                        "状态/等级": "",
                        "摘要": "",
                        "建议动作": text if section == "recommended_actions" else "",
                    })

        if rows or not include_empty_row:
            return rows
        return [{
            "类型": "AI运行时控制策略",
            "标题": "状态",
            "状态/等级": "暂无可导出的运行时控制策略数据",
            "摘要": "",
            "建议动作": "",
        }]

    @staticmethod
    def build_runtime_policy_gate_export_text(dashboard: dict) -> str:
        """构建 AI 运行时策略闸门中心 TXT 导出内容。"""
        rows = ArticleHealthService.build_runtime_policy_gate_export_rows(
            dashboard,
            include_empty_row=False,
        )
        lines = ["【AI 运行时策略闸门中心】"]
        if not rows:
            lines.append("当前暂无可导出的运行时策略闸门数据。")
            return "\n".join(lines)
        for index, row in enumerate(rows, 1):
            lines.append("")
            lines.append(f"{index}. [{row.get('类型') or '策略闸门'}] {row.get('标题') or '运行时策略闸门'}")
            if row.get("状态/等级"):
                lines.append(f"   状态/等级：{row.get('状态/等级')}")
            if row.get("摘要"):
                lines.append(f"   摘要：{row.get('摘要')}")
            if row.get("建议动作"):
                lines.append(f"   建议动作：{row.get('建议动作')}")
        return "\n".join(lines)

    @staticmethod
    def build_runtime_policy_gate_export_rows(
        dashboard: dict,
        include_empty_row: bool = True,
    ) -> list[dict]:
        """构建 AI 运行时策略闸门中心 CSV 导出行。"""
        gate = ((dashboard or {}).get("ai_runtime_policy_gate_center") or {})
        rows = []
        global_gate = gate.get("global_gate") or {}
        if global_gate:
            rows.append({
                "类型": "全局闸门",
                "标题": global_gate.get("title") or "全局运行时策略闸门",
                "状态/等级": ArticleHealthService._ai_status_label(global_gate.get("status") or global_gate.get("type") or ""),
                "摘要": global_gate.get("summary") or "",
                "建议动作": "",
            })
        section_labels = {
            "allowed_forward_actions": "允许前进",
            "manual_confirmation_actions": "人工确认",
            "delayed_actions": "延迟处理",
            "forbidden_actions": "禁止动作",
            "gate_reasons": "闸门原因",
            "recommended_actions": "推荐动作",
        }
        for section, label in section_labels.items():
            for item in list(gate.get(section) or []):
                if isinstance(item, dict):
                    item_type = item.get("type") or ""
                    rows.append({
                        "类型": label,
                        "标题": item.get("title") or item.get("name") or label,
                        "状态/等级": ArticleHealthService._ai_status_label(item.get("level") or item.get("status") or item_type),
                        "摘要": item.get("summary") or item.get("message") or item.get("text") or "",
                        "建议动作": item.get("action") or item.get("suggestion") or item.get("recommended_action") or "",
                    })
                else:
                    text = str(item)
                    rows.append({
                        "类型": label,
                        "标题": text,
                        "状态/等级": "",
                        "摘要": "",
                        "建议动作": text if section == "recommended_actions" else "",
                    })

        if rows or not include_empty_row:
            return rows
        return [{
            "类型": "AI运行时策略闸门",
            "标题": "状态",
            "状态/等级": "暂无可导出的运行时策略闸门数据",
            "摘要": "",
            "建议动作": "",
        }]

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
                    "部分文章连续被判为高风险，建议复核内容质量、提示词与模板输入。",
                    ["AI 内容质量下降", "提示词不稳定", "模板质量下降"],
                    ["人工复核", "重新生成", "检查模板", "检查提示词"],
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
                    ["复盘恢复文章", "沉淀有效提示词", "继续保持终检节奏"],
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
            add("检查高风险模板提示词")
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
        """构建提示词级 AI 运营分析，只读聚合文章、AI 日志和发布任务。"""
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
                    logger.warning("提示词运营单篇分析失败 article_id=%s：%s", article_id, exc)
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
            logger.warning("AI 提示词运营分析构建失败：%s", exc)
            return empty_result

    @staticmethod
    def _empty_prompt_ops_analysis() -> dict:
        return {
            "prompt_health": [],
            "high_risk_prompts": [],
            "unstable_prompts": [],
            "prompt_recommendations": [],
            "summary": "当前暂无可用于提示词分析的字段。",
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
            logger.warning("读取提示词运营文章数据失败：%s", exc)
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
                "prompt": item.get("prompt") or "未知提示词",
                "level": level or item.get("status") or "warning",
                "issue": issue,
                "suggestion": suggestion,
            })

        for item in prompt_health or []:
            if float(item.get("risk_rate") or 0) >= 40:
                add(item, "高风险率偏高", "建议降低营销承诺语气，增加合规提示，减少绝对化表达。", "danger")
            if ArticleHealthService._safe_int(item.get("preflight_fail_count")) >= 2:
                add(item, "终检失败偏高", "建议检查提示词中的 CTA 结构、HTML 约束和微信兼容性要求。")
            if ArticleHealthService._safe_int(item.get("publish_fail_count")) >= 3:
                add(item, "发布失败偏高", "建议优先检查封面图、media_id 和微信草稿箱兼容要求。", "danger")
            if ArticleHealthService._safe_int(item.get("average_volatility_index")) >= 60:
                add(item, "波动过高", "建议对不稳定提示词做 A/B 测试，并收敛输出结构。")
            if ArticleHealthService._safe_int(item.get("average_stability_index")) <= 40:
                add(item, "稳定性偏低", "建议增加固定输出格式、合规边界和微信 HTML 约束。")
            if len(recommendations) >= 10:
                break
        return recommendations[:10]

    @staticmethod
    def _build_prompt_ops_summary(prompt_health: list[dict], high_risk_prompts: list[dict]) -> str:
        if not prompt_health:
            return "当前暂无可用于提示词分析的数据。"
        if high_risk_prompts:
            names = "、".join((item.get("prompt") or "未知提示词") for item in high_risk_prompts[:3])
            return f"当前提示词风险主要集中在：{names}。"
        warning_prompts = [item for item in prompt_health if item.get("status") == "warning"]
        if warning_prompts:
            return "当前部分提示词存在稳定性或失败率问题，建议持续观察。"
        return "当前提示词运行整体健康，暂无明显集中风险。"

    @staticmethod
    def _build_prompt_ops_actions(prompt_recommendations: list[dict]) -> list[str]:
        action_map = {
            "高风险率偏高": ["优化高风险提示词的合规表达", "降低营销承诺语气", "人工复核高风险提示词生成结果"],
            "终检失败偏高": ["检查提示词中的 CTA 结构", "增加微信兼容性约束"],
            "发布失败偏高": ["优先优化发布失败率高的提示词", "增加微信素材与封面图约束"],
            "波动过高": ["对不稳定提示词做 A/B 测试"],
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

        prompt_summary = (prompt_ops_analysis.get("summary") or "当前暂无可用于提示词分析的数据。").strip()
        high_risk_prompt_names = [
            (item.get("prompt") or "未知提示词").strip() or "未知提示词"
            for item in list(prompt_ops_analysis.get("high_risk_prompts") or [])[:5]
        ]
        unstable_prompt_names = [
            (item.get("prompt") or "未知提示词").strip() or "未知提示词"
            for item in list(prompt_ops_analysis.get("unstable_prompts") or [])[:5]
        ]
        prompt_actions = [
            str(action).strip()
            for action in (prompt_ops_analysis.get("recommended_actions") or [])
            if str(action).strip()
        ][:5]
        lines.extend([
            "",
            "提示词运营分析：",
            f"- {prompt_summary}",
        ])
        if high_risk_prompt_names:
            lines.append("- 高风险提示词：" + "、".join(high_risk_prompt_names))
        if unstable_prompt_names:
            lines.append("- 不稳定提示词：" + "、".join(unstable_prompt_names))
        if prompt_actions:
            lines.append("- 建议：" + "、".join(prompt_actions))
        else:
            lines.append("- 当前暂无额外提示词运营动作")

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
            **ArticleHealthService.build_ai_dashboard_centers({}),
            "trend_summary": {
                "up_count": 0,
                "stable_count": 0,
                "down_count": 0,
            },
            "filters": safe_filters,
            "filtered_articles": [],
        }
