"""Fault-tolerant growth analytics for WeChat articles."""
from __future__ import annotations

import json
import logging
from typing import Any

from config import CONTENT_GROWTH_LOW_TRAFFIC_THRESHOLD
from ai_processor.processor import format_to_wechat_html
from database import get_db, init_content_growth_tables, is_mysql
from services.title_score_service import TitleScoreService
from services.topic_engine import TopicEngine
from services.wechat_html_adapter import adapt_html_for_wechat
from services.wechat_lead_card_adapter import append_lead_qr_at_end

logger = logging.getLogger(__name__)


class ArticleGrowthAnalyzer:
    """Return stable growth-analysis structures even when dependencies fail."""

    DEFAULT_LOW_TRAFFIC_THRESHOLD = CONTENT_GROWTH_LOW_TRAFFIC_THRESHOLD
    SUMMARY_DEFAULTS = {
        "total_articles": 0,
        "total_views": 0,
        "total_likes": 0,
        "total_shares": 0,
        "avg_title_score": 0,
        "avg_growth_score": 0,
    }
    METRIC_DEFAULTS = {
        "view_count": 0,
        "like_count": 0,
        "comment_count": 0,
        "share_count": 0,
        "favorite_count": 0,
        "scan_count": 0,
        "consult_count": 0,
        "deal_count": 0,
    }

    @classmethod
    def ensure_storage(cls) -> bool:
        """Compatibility wrapper around the centralized safe migration."""
        try:
            return bool(init_content_growth_tables())
        except Exception as exc:
            logger.exception("[content-growth-db-init-error] analyzer storage error=%s", exc)
            return False

    @classmethod
    def get_dashboard_data(cls, limit: int = 100) -> dict[str, Any]:
        """Return dashboard data with a stable shape under every failure mode."""
        result = cls._dashboard_result()
        try:
            storage_ready = cls.ensure_storage()
            rows = cls._fetch_dashboard_rows(limit=limit, include_growth=storage_ready)
            articles = [cls._normalize_dashboard_article(dict(row)) for row in rows]
            result["articles"] = articles
            result["summary"] = cls._build_summary(articles)
            result["topics"] = cls._safe_topics()
            if not storage_ready:
                result["ok"] = False
                result["error"] = "文章增长数据表暂不可用，已降级展示文章基础数据。"
            return result
        except Exception as exc:
            logger.exception("[content-growth-dashboard-error] analyzer error=%s", exc)
            result["ok"] = False
            result["error"] = "文章增长数据加载异常"
            result["topics"] = cls._safe_topics()
            return result

    @classmethod
    def analyze_article_growth(
        cls,
        article_id: int,
        metrics_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Analyze one article without propagating database or parser errors."""
        try:
            article = cls._get_article(article_id)
            if not article:
                return cls._analysis_error(article_id, "文章不存在")

            metrics = cls._get_metrics(article_id)
            override = cls._normalize_metrics(metrics_override or {})
            for key, value in override.items():
                if cls._has_metric_value(metrics_override or {}, key):
                    metrics[key] = value

            title_result = cls._safe_title_score(article.get("title", ""))
            title_score = cls._safe_int(title_result.get("score"))
            content_score = cls._score_content(article)
            conversion_score = cls._score_conversion(metrics)
            growth_score = round(title_score * 0.35 + content_score * 0.35 + conversion_score * 0.3)

            title_problem = cls._title_problem(title_result)
            content_problem = cls._content_problem(content_score)
            cta_problem = cls._cta_problem(metrics, article)
            weakest = cls._weakest_area(title_score, content_score, conversion_score)
            failure_reasons = cls._failure_reasons(
                metrics,
                growth_score,
                title_problem,
                content_problem,
                cta_problem,
            )
            suggestions = cls._suggestions(weakest)

            result = {
                "ok": True,
                "error": None,
                "article_id": article_id,
                "title": str(article.get("title") or "未命名文章"),
                **metrics,
                "metrics": dict(metrics),
                "performance_score": growth_score,
                "growth_score": growth_score,
                "title_score": title_result,
                "title_score_value": title_score,
                "content_score": content_score,
                "conversion_score": conversion_score,
                "failure_reasons": failure_reasons,
                "title_problem": title_problem,
                "content_problem": content_problem,
                "cta_problem": cta_problem,
                "next_optimization_suggestions": suggestions,
                "recommended_next_topic": cls._safe_recommended_topic(weakest),
            }
            cls._upsert_growth_record(
                article_id,
                {
                    "title": str(article.get("title") or ""),
                    **metrics,
                    "title_score": title_score,
                    "content_score": content_score,
                    "growth_score": growth_score,
                    "failure_reasons": json.dumps(failure_reasons, ensure_ascii=False),
                    "suggestions": json.dumps(suggestions, ensure_ascii=False),
                },
                analyzed_only=True,
            )
            return result
        except Exception as exc:
            logger.exception(
                "[content-growth-analyze-error] article_id=%s error=%s",
                article_id,
                exc,
            )
            return cls._analysis_error(article_id, "文章增长分析暂不可用，已返回默认结果。")

    @classmethod
    def rewrite_for_growth(
        cls,
        article_id: int,
        low_traffic_threshold: int | None = None,
        metrics_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a deterministic rewrite fallback even if AI or storage is unavailable."""
        try:
            analysis = cls.analyze_article_growth(article_id, metrics_override=metrics_override)
            if not analysis.get("ok"):
                return {
                    **cls._rewrite_defaults(article_id, low_traffic_threshold),
                    "ok": False,
                    "error": analysis.get("error") or "文章不存在",
                    "analysis": analysis,
                }

            threshold = cls._safe_threshold(low_traffic_threshold)
            title = str(analysis.get("title") or "企业融资")
            article = cls._get_article(article_id) or {}
            title_payload = analysis.get("title_score")
            title_payload = title_payload if isinstance(title_payload, dict) else {}
            optimized = title_payload.get("optimized_titles") or cls._safe_optimized_titles(title)
            view_count = cls._safe_int(analysis.get("view_count"))
            optimized_title = str((cls._safe_list(optimized) or [title])[0])
            optimized_intro = cls._new_opening(title)
            optimized_outline = cls._new_structure()
            optimized_cta = cls._new_cta()
            growth_reason = "；".join(cls._safe_list(analysis.get("failure_reasons"))[:3])
            optimized_content = cls._build_optimized_content(
                article.get("content", ""),
                optimized_intro,
                optimized_cta,
            )
            is_published = str(article.get("status") or "") in {"published", "已发表"}
            proposal = {
                "ok": True,
                "success": True,
                "error": None,
                "article_id": article_id,
                "is_published": is_published,
                "low_traffic": view_count < threshold,
                "threshold": threshold,
                "original_title": title,
                "optimized_title": optimized_title,
                "optimized_intro": optimized_intro,
                "optimized_outline": optimized_outline,
                "optimized_cta": optimized_cta,
                "optimized_content": optimized_content,
                "growth_reason": growth_reason,
                "failure_reason_analysis": cls._safe_list(analysis.get("failure_reasons")),
                "new_titles": cls._safe_list(optimized)[:3],
                "new_opening": optimized_intro,
                "new_article_structure": optimized_outline,
                "new_cta": optimized_cta,
                "analysis": analysis,
                "fallback_used": True,
                "applied": False,
                "available_actions": (
                    ["create_new_draft"]
                    if is_published
                    else ["apply_to_current_draft"]
                ),
            }
            cls._save_rewrite_proposal(article_id, proposal)
            return proposal
        except Exception as exc:
            logger.exception(
                "[content-growth-rewrite-error] article_id=%s error=%s",
                article_id,
                exc,
            )
            return {
                **cls._rewrite_defaults(article_id, low_traffic_threshold),
                "ok": False,
                "error": "文章增长改写暂不可用，已返回默认建议。",
            }

    @classmethod
    def update_metrics(cls, article_id: int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Persist manually entered growth metrics without touching articles."""
        try:
            article = cls._get_article(article_id)
            if not article:
                return {"ok": False, "error": "文章不存在", "article_id": article_id}
            if not cls.ensure_storage():
                return {"ok": False, "error": "增长数据表暂不可用", "article_id": article_id}

            metrics = cls._normalize_metrics(payload or {})
            analysis = cls.analyze_article_growth(article_id, metrics_override=metrics)
            title_score = cls._safe_int(analysis.get("title_score_value"))
            content_score = cls._safe_int(analysis.get("content_score"))
            growth_score = cls._safe_int(analysis.get("growth_score"))
            failure_reasons = json.dumps(
                cls._safe_list(analysis.get("failure_reasons")),
                ensure_ascii=False,
            )
            suggestions = json.dumps(
                cls._safe_list(analysis.get("next_optimization_suggestions")),
                ensure_ascii=False,
            )
            cls._upsert_growth_record(
                article_id,
                {
                    "title": str(article.get("title") or ""),
                    **metrics,
                    "title_score": title_score,
                    "content_score": content_score,
                    "growth_score": growth_score,
                    "failure_reasons": failure_reasons,
                    "suggestions": suggestions,
                },
                update_timestamps=True,
            )
            return {
                "ok": True,
                "error": None,
                "article_id": article_id,
                "metrics": metrics,
                "title_score": title_score,
                "content_score": content_score,
                "growth_score": growth_score,
                "analysis": analysis,
            }
        except Exception as exc:
            logger.exception(
                "[content-growth-metrics-update-error] article_id=%s error=%s",
                article_id,
                exc,
            )
            return {"ok": False, "error": "增长数据保存失败", "article_id": article_id}

    @classmethod
    def create_optimized_draft(cls, article_id: int) -> dict[str, Any]:
        """Create a new draft from a stored proposal without changing the source article."""
        conn = None
        try:
            if not cls.ensure_storage():
                return {"ok": False, "error": "增长数据表暂不可用"}
            article = cls._get_article(article_id)
            if not article:
                return {"ok": False, "error": "文章不存在"}
            proposal = cls._get_rewrite_proposal(article_id)
            if not proposal.get("optimized_content"):
                return {"ok": False, "error": "尚未生成可采用的优化稿"}

            conn = get_db()
            optimized_title = proposal.get("optimized_title") or article.get("title") or "未命名文章"
            optimized_content = proposal.get("optimized_content") or ""
            optimized_html = cls._build_optimized_html(optimized_title, optimized_content)
            if is_mysql():
                cursor = conn.execute(
                    """
                    INSERT INTO articles
                    (title, content, summary, source_name, source_url, tags, status,
                     review_status, publish_status, is_original, html_content, source_article_id)
                    VALUES (%s,%s,%s,%s,%s,%s,'draft','draft','not_ready',1,%s,%s)
                    """,
                    (
                        optimized_title,
                        optimized_content,
                        article.get("summary") or "",
                        "沪上银原创",
                        article.get("source_url") or "",
                        article.get("tags") or "",
                        optimized_html,
                        article_id,
                    ),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO articles
                    (title, content, summary, source_name, source_url, tags, status,
                     review_status, publish_status, is_original, html_content, source_article_id)
                    VALUES (?,?,?,?,?,?,'draft','draft','not_ready',1,?,?)
                    """,
                    (
                        optimized_title,
                        optimized_content,
                        article.get("summary") or "",
                        "沪上银原创",
                        article.get("source_url") or "",
                        article.get("tags") or "",
                        optimized_html,
                        article_id,
                    ),
                )
            target_article_id = cursor.lastrowid
            conn.commit()
            cls._mark_proposal_applied(article_id)
            return {
                "ok": True,
                "success": True,
                "error": None,
                "article_id": article_id,
                "new_article_id": target_article_id,
                "target_article_id": target_article_id,
                "redirect_url": f"/article/{target_article_id}",
                "message": "已基于原文生成优化版草稿，请进入文章详情页审核后再推送",
            }
        except Exception as exc:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            logger.exception(
                "[content-growth-rewrite-apply-error] article_id=%s error=%s",
                article_id,
                exc,
            )
            return {"ok": False, "error": "采用优化稿失败"}
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    @classmethod
    def apply_optimized_to_draft(cls, article_id: int) -> dict[str, Any]:
        """Apply a stored proposal only to non-published draft-like articles."""
        conn = None
        try:
            article = cls._get_article(article_id)
            if not article:
                return {"ok": False, "success": False, "error": "文章不存在"}
            status = str(article.get("status") or "")
            if status in {"published", "已发表"}:
                return {
                    "ok": False,
                    "success": False,
                    "error": "已发表文章不能直接覆盖，请生成优化版新草稿",
                }
            if status not in {"draft", "generated", "approved", "draft_sent"}:
                return {
                    "ok": False,
                    "success": False,
                    "error": "当前文章状态不允许直接采用优化稿",
                }
            proposal = cls._get_rewrite_proposal(article_id)
            if not proposal.get("optimized_content"):
                return {"ok": False, "success": False, "error": "尚未生成可采用的优化稿"}

            conn = get_db()
            placeholder = "%s" if is_mysql() else "?"
            timestamp_sql = "CURRENT_TIMESTAMP" if is_mysql() else "datetime('now','localtime')"
            conn.execute(
                f"""
                UPDATE articles
                SET title={placeholder}, content={placeholder}, html_content={placeholder},
                    updated_at={timestamp_sql}
                WHERE id={placeholder}
                """,
                (
                    proposal.get("optimized_title") or article.get("title") or "未命名文章",
                    proposal.get("optimized_content") or "",
                    cls._build_optimized_html(
                        proposal.get("optimized_title") or article.get("title") or "untitled",
                        proposal.get("optimized_content") or "",
                    ),
                    article_id,
                ),
            )
            conn.commit()
            cls._mark_proposal_applied(article_id)
            return {
                "ok": True,
                "success": True,
                "error": None,
                "article_id": article_id,
                "redirect_url": f"/article/{article_id}",
                "message": "优化稿已应用到当前草稿，请进入文章详情页审核",
            }
        except Exception as exc:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            logger.exception(
                "[content-growth-rewrite-apply-error] article_id=%s error=%s",
                article_id,
                exc,
            )
            return {"ok": False, "success": False, "error": "采用优化稿失败"}
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    @classmethod
    def apply_rewrite_proposal(cls, article_id: int, mode: str = "new_draft") -> dict[str, Any]:
        """Backward-compatible dispatcher for older callers."""
        if mode == "replace":
            return cls.apply_optimized_to_draft(article_id)
        return cls.create_optimized_draft(article_id)

    # Backward-compatible public names used by existing routes/tests.
    dashboard = get_dashboard_data
    analyze_article = analyze_article_growth

    @classmethod
    def _fetch_dashboard_rows(cls, limit: int, include_growth: bool):
        conn = get_db()
        placeholder = "%s" if is_mysql() else "?"
        safe_limit = max(1, min(cls._safe_int(limit, 100), 500))
        try:
            if include_growth:
                return conn.execute(
                    f"""
                    SELECT
                        a.*,
                        COALESCE(g.view_count, 0) AS view_count,
                        COALESCE(g.like_count, 0) AS like_count,
                        COALESCE(g.comment_count, 0) AS comment_count,
                        COALESCE(g.share_count, 0) AS share_count,
                        COALESCE(g.favorite_count, 0) AS favorite_count,
                        COALESCE(g.scan_count, 0) AS scan_count,
                        COALESCE(g.consult_count, 0) AS consult_count,
                        COALESCE(g.deal_count, 0) AS deal_count,
                        COALESCE(g.title_score, 0) AS stored_title_score,
                        COALESCE(g.content_score, 0) AS stored_content_score,
                        COALESCE(g.growth_score, 0) AS stored_growth_score,
                        g.id AS growth_record_id,
                        COALESCE(g.optimization_applied, 0) AS optimization_applied,
                        g.optimized_at, g.applied_at, g.metrics_updated_at,
                        g.last_analyzed_at, g.failure_reasons, g.suggestions
                    FROM articles a
                    LEFT JOIN article_growth_metrics g ON g.article_id = a.id
                    ORDER BY a.created_at DESC
                    LIMIT {placeholder}
                    """,
                    (safe_limit,),
                ).fetchall()
            return conn.execute(
                f"""
                SELECT id, title, summary, content, html_content, status, created_at, updated_at
                FROM articles
                ORDER BY created_at DESC
                LIMIT {placeholder}
                """,
                (safe_limit,),
            ).fetchall()
        finally:
            conn.close()

    @classmethod
    def _normalize_dashboard_article(cls, raw: dict[str, Any]) -> dict[str, Any]:
        item = raw if isinstance(raw, dict) else {}
        metric_source = dict(item)
        if not item.get("growth_record_id"):
            for canonical_name in cls.METRIC_DEFAULTS:
                metric_source.pop(canonical_name, None)
        metrics = cls._normalize_metrics(metric_source)
        computed_title = cls._safe_title_score(item.get("title", ""))
        title_score = cls._safe_int(item.get("stored_title_score")) or cls._safe_int(computed_title.get("score"))
        content_score = cls._safe_int(item.get("stored_content_score")) or cls._score_content(item)
        conversion_score = cls._score_conversion(metrics)
        growth_score = (
            cls._safe_int(item.get("stored_growth_score"))
            or round(title_score * 0.35 + content_score * 0.35 + conversion_score * 0.3)
        )
        return {
            "id": cls._safe_int(item.get("id")),
            "title": str(item.get("title") or "未命名文章"),
            "source_title": str(item.get("source_title") or ""),
            "generated_title": str(item.get("generated_title") or item.get("title") or ""),
            "summary": str(item.get("summary") or ""),
            "status": str(item.get("status") or "-"),
            "status_label": cls._status_label(item.get("status")),
            "is_published": str(item.get("status") or "") in {"published", "已发表"},
            "has_metrics": bool(item.get("metrics_updated_at")),
            "is_optimized": bool(
                item.get("optimized_at")
                or item.get("applied_at")
                or cls._safe_int(item.get("optimization_applied"))
            ),
            "last_analyzed_at": item.get("last_analyzed_at"),
            "metrics_updated_at": item.get("metrics_updated_at"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
            **metrics,
            # Legacy response aliases kept for older callers only.
            "reads": metrics["view_count"],
            "likes": metrics["like_count"],
            "shares": metrics["share_count"],
            "favorites": metrics["favorite_count"],
            "comments": metrics["comment_count"],
            "qr_scans": metrics["scan_count"],
            "consultations": metrics["consult_count"],
            "deals": metrics["deal_count"],
            "title_score": title_score,
            "content_score": content_score,
            "growth_score": growth_score,
            "growth_advice": cls._dashboard_advice(metrics, title_score, content_score, conversion_score),
            "failure_reasons": cls._parse_json_list(item.get("failure_reasons")),
            "suggestions": cls._parse_json_list(item.get("suggestions")),
        }

    @classmethod
    def _upsert_growth_record(
        cls,
        article_id: int,
        data: dict[str, Any],
        *,
        update_timestamps: bool = False,
        analyzed_only: bool = False,
    ) -> bool:
        if not cls.ensure_storage():
            return False
        conn = None
        fields = [
            "title",
            "view_count",
            "like_count",
            "comment_count",
            "share_count",
            "favorite_count",
            "scan_count",
            "consult_count",
            "deal_count",
            "title_score",
            "content_score",
            "growth_score",
            "failure_reasons",
            "suggestions",
        ]
        values = [
            str(data.get("title") or ""),
            *[cls._safe_int(data.get(key)) for key in fields[1:12]],
            str(data.get("failure_reasons") or "[]"),
            str(data.get("suggestions") or "[]"),
        ]
        try:
            conn = get_db()
            if is_mysql():
                updates = ", ".join(f"{field}=VALUES({field})" for field in fields)
                timestamp_updates = ["last_analyzed_at=CURRENT_TIMESTAMP", "updated_at=CURRENT_TIMESTAMP"]
                if update_timestamps:
                    timestamp_updates.append("metrics_updated_at=CURRENT_TIMESTAMP")
                conn.execute(
                    f"""
                    INSERT INTO article_growth_metrics
                    (article_id, {", ".join(fields)}, last_analyzed_at, metrics_updated_at)
                    VALUES (%s, {", ".join(["%s"] * len(fields))}, CURRENT_TIMESTAMP,
                            {"CURRENT_TIMESTAMP" if update_timestamps else "NULL"})
                    ON DUPLICATE KEY UPDATE
                    {updates}, {", ".join(timestamp_updates)}
                    """,
                    (article_id, *values),
                )
            else:
                updates = ", ".join(f"{field}=excluded.{field}" for field in fields)
                timestamp_updates = [
                    "last_analyzed_at=datetime('now','localtime')",
                    "updated_at=datetime('now','localtime')",
                ]
                if update_timestamps:
                    timestamp_updates.append("metrics_updated_at=datetime('now','localtime')")
                conn.execute(
                    f"""
                    INSERT INTO article_growth_metrics
                    (article_id, {", ".join(fields)}, last_analyzed_at, metrics_updated_at)
                    VALUES (?, {", ".join(["?"] * len(fields))}, datetime('now','localtime'),
                            {"datetime('now','localtime')" if update_timestamps else "NULL"})
                    ON CONFLICT(article_id) DO UPDATE SET
                    {updates}, {", ".join(timestamp_updates)}
                    """,
                    (article_id, *values),
                )
            conn.commit()
            return True
        except Exception as exc:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            logger.exception(
                "[content-growth-metrics-update-error] article_id=%s analyzed_only=%s error=%s",
                article_id,
                analyzed_only,
                exc,
            )
            return False
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    @classmethod
    def _save_rewrite_proposal(cls, article_id: int, proposal: dict[str, Any]) -> bool:
        if not cls.ensure_storage():
            return False
        conn = None
        titles_json = json.dumps(cls._safe_list(proposal.get("new_titles")), ensure_ascii=False)
        outline_json = json.dumps(cls._safe_list(proposal.get("optimized_outline")), ensure_ascii=False)
        try:
            conn = get_db()
            if is_mysql():
                conn.execute(
                    """
                    INSERT INTO article_growth_metrics
                    (article_id, title, rewrite_titles, rewrite_intro, rewrite_outline,
                     rewrite_cta, optimized_content, growth_reason, optimization_applied,
                     optimized_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
                    ON DUPLICATE KEY UPDATE
                    title=VALUES(title), rewrite_titles=VALUES(rewrite_titles),
                    rewrite_intro=VALUES(rewrite_intro), rewrite_outline=VALUES(rewrite_outline),
                    rewrite_cta=VALUES(rewrite_cta), optimized_content=VALUES(optimized_content),
                    growth_reason=VALUES(growth_reason), optimization_applied=0,
                    optimized_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                    """,
                    (
                        article_id,
                        proposal.get("original_title") or "",
                        titles_json,
                        proposal.get("optimized_intro") or "",
                        outline_json,
                        proposal.get("optimized_cta") or "",
                        proposal.get("optimized_content") or "",
                        proposal.get("growth_reason") or "",
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO article_growth_metrics
                    (article_id, title, rewrite_titles, rewrite_intro, rewrite_outline,
                     rewrite_cta, optimized_content, growth_reason, optimization_applied,
                     optimized_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,0,datetime('now','localtime'),datetime('now','localtime'))
                    ON CONFLICT(article_id) DO UPDATE SET
                    title=excluded.title, rewrite_titles=excluded.rewrite_titles,
                    rewrite_intro=excluded.rewrite_intro, rewrite_outline=excluded.rewrite_outline,
                    rewrite_cta=excluded.rewrite_cta, optimized_content=excluded.optimized_content,
                    growth_reason=excluded.growth_reason, optimization_applied=0,
                    optimized_at=datetime('now','localtime'), updated_at=datetime('now','localtime')
                    """,
                    (
                        article_id,
                        proposal.get("original_title") or "",
                        titles_json,
                        proposal.get("optimized_intro") or "",
                        outline_json,
                        proposal.get("optimized_cta") or "",
                        proposal.get("optimized_content") or "",
                        proposal.get("growth_reason") or "",
                    ),
                )
            conn.commit()
            return True
        except Exception as exc:
            logger.exception(
                "[content-growth-rewrite-error] save proposal article_id=%s error=%s",
                article_id,
                exc,
            )
            return False
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    @classmethod
    def _get_rewrite_proposal(cls, article_id: int) -> dict[str, Any]:
        conn = None
        try:
            conn = get_db()
            placeholder = "%s" if is_mysql() else "?"
            row = conn.execute(
                f"""
                SELECT rewrite_titles, rewrite_intro, rewrite_outline, rewrite_cta,
                       optimized_content, growth_reason
                FROM article_growth_metrics
                WHERE article_id={placeholder}
                """,
                (article_id,),
            ).fetchone()
            data = dict(row) if row else {}
            titles = cls._parse_json_list(data.get("rewrite_titles"))
            return {
                "optimized_title": str(titles[0]) if titles else "",
                "optimized_intro": str(data.get("rewrite_intro") or ""),
                "optimized_outline": cls._parse_json_list(data.get("rewrite_outline")),
                "optimized_cta": str(data.get("rewrite_cta") or ""),
                "optimized_content": str(data.get("optimized_content") or ""),
                "growth_reason": str(data.get("growth_reason") or ""),
            }
        except Exception as exc:
            logger.exception(
                "[content-growth-rewrite-error] read proposal article_id=%s error=%s",
                article_id,
                exc,
            )
            return {}
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    @classmethod
    def _mark_proposal_applied(cls, article_id: int) -> None:
        conn = None
        try:
            conn = get_db()
            placeholder = "%s" if is_mysql() else "?"
            timestamp = "CURRENT_TIMESTAMP" if is_mysql() else "datetime('now','localtime')"
            conn.execute(
                f"""
                UPDATE article_growth_metrics
                SET optimization_applied=1, applied_at={timestamp}, updated_at={timestamp}
                WHERE article_id={placeholder}
                """,
                (article_id,),
            )
            conn.commit()
        finally:
            if conn is not None:
                conn.close()

    @classmethod
    def _get_article(cls, article_id: int) -> dict[str, Any] | None:
        conn = None
        try:
            conn = get_db()
            placeholder = "%s" if is_mysql() else "?"
            row = conn.execute(f"SELECT * FROM articles WHERE id={placeholder}", (article_id,)).fetchone()
            return dict(row) if row else None
        except Exception as exc:
            logger.exception(
                "[content-growth-analyze-error] article query article_id=%s error=%s",
                article_id,
                exc,
            )
            return None
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    logger.exception("[content-growth-analyze-error] article connection close failed")

    @classmethod
    def _get_metrics(cls, article_id: int) -> dict[str, int]:
        defaults = dict(cls.METRIC_DEFAULTS)
        if not cls.ensure_storage():
            return defaults
        conn = None
        try:
            conn = get_db()
            placeholder = "%s" if is_mysql() else "?"
            row = conn.execute(
                f"""
                SELECT view_count, like_count, comment_count, share_count,
                       favorite_count, scan_count, consult_count, deal_count
                FROM article_growth_metrics
                WHERE article_id={placeholder}
                """,
                (article_id,),
            ).fetchone()
            return cls._normalize_metrics(dict(row) if row else {})
        except Exception as exc:
            logger.exception(
                "[content-growth-analyze-error] metrics query article_id=%s error=%s",
                article_id,
                exc,
            )
            return defaults
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    logger.exception("[content-growth-analyze-error] metrics connection close failed")

    @classmethod
    def _normalize_metrics(cls, raw: dict[str, Any]) -> dict[str, int]:
        source = raw if isinstance(raw, dict) else {}
        aliases = {
            "view_count": ("view_count", "reads", "read_count", "阅读量"),
            "like_count": ("like_count", "likes", "点赞"),
            "comment_count": ("comment_count", "comments", "评论"),
            "share_count": ("share_count", "shares", "分享"),
            "favorite_count": ("favorite_count", "favorites", "收藏"),
            "scan_count": ("scan_count", "qr_scans", "扫码数"),
            "consult_count": ("consult_count", "consultations", "咨询数"),
            "deal_count": ("deal_count", "deals", "成交数"),
        }
        metrics: dict[str, int] = {}
        for canonical_name, names in aliases.items():
            value = 0
            for name in names:
                if source.get(name) is not None:
                    value = source.get(name)
                    break
            metrics[canonical_name] = cls._safe_int(value)
        return metrics

    @classmethod
    def _has_metric_value(cls, raw: dict[str, Any], canonical_name: str) -> bool:
        aliases = {
            "view_count": ("view_count", "reads", "read_count", "阅读量"),
            "like_count": ("like_count", "likes", "点赞"),
            "comment_count": ("comment_count", "comments", "评论"),
            "share_count": ("share_count", "shares", "分享"),
            "favorite_count": ("favorite_count", "favorites", "收藏"),
            "scan_count": ("scan_count", "qr_scans", "扫码数"),
            "consult_count": ("consult_count", "consultations", "咨询数"),
            "deal_count": ("deal_count", "deals", "成交数"),
        }
        return any(name in raw for name in aliases.get(canonical_name, (canonical_name,)))

    @classmethod
    def _build_summary(cls, articles: list[dict[str, Any]]) -> dict[str, Any]:
        if not articles:
            return dict(cls.SUMMARY_DEFAULTS)
        count = len(articles)
        return {
            "total_articles": count,
            "total_views": sum(cls._safe_int(item.get("view_count")) for item in articles),
            "total_likes": sum(cls._safe_int(item.get("like_count")) for item in articles),
            "total_shares": sum(cls._safe_int(item.get("share_count")) for item in articles),
            "avg_title_score": round(sum(cls._safe_int(item.get("title_score")) for item in articles) / count),
            "avg_growth_score": round(sum(cls._safe_int(item.get("growth_score")) for item in articles) / count),
        }

    @classmethod
    def _score_content(cls, article: dict[str, Any]) -> int:
        try:
            text = f"{article.get('content', '')}\n{article.get('html_content', '')}"
            checks = [
                any(word in text for word in ("老板", "企业主", "银行为什么不批", "被拒原因")),
                any(word in text for word in ("案例", "某企业", "贸易公司", "加工厂", "真实")),
                sum(text.count(word) for word in ("？", "?", "问题", "为什么")) >= 3,
                any(word in text for word in ("建议", "先做", "提前", "优化", "准备")),
                any(word in text for word in ("风险", "不承诺", "根据企业实际情况", "合规")),
                any(word in text for word in ("融资诊断", "融资体检", "扫码", "咨询", "顾问")),
            ]
            return min(100, 30 + sum(12 for passed in checks if passed))
        except Exception:
            return 30

    @classmethod
    def _score_conversion(cls, metrics: dict[str, int]) -> int:
        try:
            views = max(1, cls._safe_int(metrics.get("view_count")))
            engagement = (
                cls._safe_int(metrics.get("like_count"))
                + cls._safe_int(metrics.get("share_count")) * 2
                + cls._safe_int(metrics.get("favorite_count")) * 2
                + cls._safe_int(metrics.get("comment_count")) * 2
            )
            conversion = (
                cls._safe_int(metrics.get("scan_count")) * 4
                + cls._safe_int(metrics.get("consult_count")) * 8
                + cls._safe_int(metrics.get("deal_count")) * 15
            )
            return min(100, round((engagement + conversion) / views * 1000))
        except Exception:
            return 0

    @classmethod
    def _safe_title_score(cls, title: str) -> dict[str, Any]:
        try:
            result = TitleScoreService.score_title(title)
            return result if isinstance(result, dict) else {"score": 0, "optimized_titles": []}
        except Exception as exc:
            logger.exception("[content-growth-analyze-error] title score error=%s", exc)
            return {"title": str(title or ""), "score": 0, "problems": [], "optimized_titles": []}

    @classmethod
    def _safe_topics(cls) -> list[dict[str, Any]]:
        try:
            topics = TopicEngine.generate_topics(limit=8)
            industry_law_topics = TopicEngine.generate_industry_law_topics(limit=8)
            return [*(topics if isinstance(topics, list) else []), *(industry_law_topics if isinstance(industry_law_topics, list) else [])]
        except Exception as exc:
            logger.exception("[content-growth-dashboard-error] topic engine error=%s", exc)
            return []

    @classmethod
    def _safe_recommended_topic(cls, weak_area: str) -> dict[str, Any]:
        try:
            topic = TopicEngine.recommend_next_topic(weak_area)
            return topic if isinstance(topic, dict) else {}
        except Exception:
            return {}

    @classmethod
    def _safe_optimized_titles(cls, title: str) -> list[str]:
        try:
            titles = TitleScoreService.optimize_titles(title)
            return titles if isinstance(titles, list) else []
        except Exception:
            return [
                f"{title or '企业融资'}被拒后，先查这3个原因",
                f"老板做{title or '企业融资'}，银行到底看什么？",
                f"{title or '企业融资'}额度低，问题通常出在这4处",
            ]

    @classmethod
    def _dashboard_result(cls) -> dict[str, Any]:
        return {
            "ok": True,
            "articles": [],
            "summary": dict(cls.SUMMARY_DEFAULTS),
            "topics": [],
            "error": None,
        }

    @classmethod
    def _analysis_error(cls, article_id: int, error: str) -> dict[str, Any]:
        return {
            "ok": False,
            "error": error,
            "article_id": article_id,
            "title": "",
            **dict(cls.METRIC_DEFAULTS),
            "metrics": dict(cls.METRIC_DEFAULTS),
            "performance_score": 0,
            "growth_score": 0,
            "title_score": {"score": 0, "problems": [], "optimized_titles": []},
            "title_score_value": 0,
            "content_score": 0,
            "conversion_score": 0,
            "failure_reasons": [error],
            "title_problem": "",
            "content_problem": "",
            "cta_problem": "",
            "next_optimization_suggestions": [],
            "recommended_next_topic": {},
        }

    @classmethod
    def _rewrite_defaults(cls, article_id: int, threshold: Any) -> dict[str, Any]:
        optimized_intro = cls._new_opening("企业融资")
        optimized_outline = cls._new_structure()
        optimized_cta = cls._new_cta()
        titles = cls._safe_optimized_titles("企业融资")[:3]
        return {
            "success": False,
            "article_id": article_id,
            "is_published": False,
            "low_traffic": True,
            "threshold": cls._safe_threshold(threshold),
            "original_title": "",
            "optimized_title": titles[0] if titles else "企业融资怎么优化？",
            "optimized_intro": optimized_intro,
            "optimized_outline": optimized_outline,
            "optimized_cta": optimized_cta,
            "optimized_content": cls._build_optimized_content("", optimized_intro, optimized_cta),
            "growth_reason": "暂未取得完整数据",
            "failure_reason_analysis": ["暂未取得完整数据，请先检查文章和数据库状态。"],
            "new_titles": titles,
            "new_opening": optimized_intro,
            "new_article_structure": optimized_outline,
            "new_cta": optimized_cta,
            "analysis": {},
            "fallback_used": True,
            "applied": False,
            "available_actions": [],
        }

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return max(0, int(value if value is not None else default))
        except (TypeError, ValueError):
            return max(0, int(default))

    @classmethod
    def _safe_threshold(cls, value: Any) -> int:
        threshold = cls._safe_int(value, cls.DEFAULT_LOW_TRAFFIC_THRESHOLD)
        return threshold or cls.DEFAULT_LOW_TRAFFIC_THRESHOLD

    @staticmethod
    def _safe_list(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return []

    @staticmethod
    def _parse_json_list(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if not value:
            return []
        try:
            parsed = json.loads(str(value))
            return parsed if isinstance(parsed, list) else []
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    @staticmethod
    def _title_problem(title_score: dict[str, Any]) -> str:
        problems = title_score.get("problems") if isinstance(title_score, dict) else []
        problems = problems if isinstance(problems, list) else []
        return "；".join(str(item) for item in problems[:2]) or "标题可继续测试不同痛点角度。"

    @staticmethod
    def _content_problem(score: int) -> str:
        if score >= 80:
            return "内容结构基本完整，可继续强化案例细节和老板可执行动作。"
        return "内容缺少真实场景、案例拆解、问题清单或融资诊断引导。"

    @staticmethod
    def _cta_problem(metrics: dict[str, int], article: dict[str, Any]) -> str:
        text = f"{article.get('content', '')}\n{article.get('html_content', '')}"
        if metrics.get("scan_count", 0) or metrics.get("consult_count", 0):
            return "CTA 已产生转化，建议继续测试更具体的诊断入口。"
        if not any(word in text for word in ("扫码", "咨询", "融资诊断", "融资体检")):
            return "CTA 不够明确，缺少扫码、咨询或融资体检动作。"
        return "CTA 有动作但转化弱，建议明确“查被拒原因/测额度空间”。"

    @staticmethod
    def _weakest_area(title_score: int, content_score: int, conversion_score: int) -> str:
        values = {"标题点击": title_score, "内容信任": content_score, "CTA转化": conversion_score}
        return min(values, key=values.get)

    @classmethod
    def _failure_reasons(
        cls,
        metrics: dict[str, int],
        growth_score: int,
        title_problem: str,
        content_problem: str,
        cta_problem: str,
    ) -> list[str]:
        reasons = []
        if metrics.get("view_count", 0) < cls.DEFAULT_LOW_TRAFFIC_THRESHOLD:
            reasons.append("阅读量低于默认阈值，优先检查标题点击欲望和首屏场景。")
        if growth_score < 70:
            reasons.extend([title_problem, content_problem, cta_problem])
        return reasons or ["当前数据未显示明显失败点，建议继续积累阅读和转化数据。"]

    @staticmethod
    def _suggestions(weakest: str) -> list[str]:
        if weakest == "标题点击":
            return ["标题改成老板痛点句", "加入被拒原因或额度提升", "用数字表达问题数量"]
        if weakest == "内容信任":
            return ["开头换成真实经营场景", "加入匿名企业案例", "拆解3-5个审批卡点"]
        return ["CTA 改成融资体检", "把咨询利益点写具体", "文末加入二维码或顾问引导"]

    @classmethod
    def _dashboard_advice(
        cls,
        metrics: dict[str, int],
        title_score: int,
        content_score: int,
        conversion_score: int,
    ) -> str:
        if metrics.get("view_count", 0) < cls.DEFAULT_LOW_TRAFFIC_THRESHOLD:
            return "低流量：优先重写标题和开头。"
        if title_score < 80:
            return "标题弱：补痛点、数字和冲突。"
        if content_score < 80:
            return "内容弱：补案例、问题拆解和建议。"
        if conversion_score < 30:
            return "转化弱：强化融资诊断 CTA。"
        return "表现正常：继续测试相邻选题。"

    @staticmethod
    def _status_label(status: Any) -> str:
        labels = {
            "draft": "草稿",
            "approved": "已审核，待推送",
            "draft_sent": "已推送草稿箱，未确认发布",
            "published": "已发表",
            "error": "发布失败",
            "rejected": "审核未通过",
        }
        safe_status = str(status or "").strip()
        return labels.get(safe_status, safe_status or "未知状态")

    @staticmethod
    def _build_optimized_html(title: str, content: str) -> str:
        raw_html = format_to_wechat_html(title or "enterprise finance", content or "", "original")
        return append_lead_qr_at_end(adapt_html_for_wechat(raw_html))

    @staticmethod
    def _build_optimized_content(original_content: Any, intro: str, cta: str) -> str:
        body = str(original_content or "").strip()
        sections = [intro.strip()]
        if body:
            sections.append(body)
        sections.append(f"## 融资诊断\n\n{cta.strip()}")
        return "\n\n".join(section for section in sections if section)

    @staticmethod
    def _new_opening(title: str) -> str:
        return (
            f"一位老板最近问我：{title or '企业贷款'}这件事，为什么资料交了、流水也有，银行还是迟迟不批？"
            "很多企业主卡住的不是单一材料，而是银行看到的经营信号和老板自己理解的不一样。"
        )

    @staticmethod
    def _new_structure() -> list[str]:
        return [
            "痛点标题：点出老板当前融资卡点",
            "真实场景开头：订单、账期、工资、采购或续贷压力",
            "匿名案例：企业背景、申请过程、被拒或额度低原因",
            "3-5个问题拆解：征信、流水、负债、纳税、用途",
            "3-5个解决建议：资料、节奏、额度、银行匹配、风险控制",
            "风险提醒：不承诺放款，根据企业实际情况评估",
            "融资诊断 CTA：引导扫码或留言做融资体检",
        ]

    @staticmethod
    def _new_cta() -> str:
        return "如果你也遇到银行不批、额度低、续贷不稳，可以扫码做一次融资体检：先看被拒原因，再判断额度提升空间和下一步申请顺序。"
