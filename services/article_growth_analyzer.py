"""Fault-tolerant growth analytics for WeChat articles."""
from __future__ import annotations

import json
import logging
from typing import Any

from database import get_db, init_content_growth_tables, is_mysql
from services.title_score_service import TitleScoreService
from services.topic_engine import TopicEngine

logger = logging.getLogger(__name__)


class ArticleGrowthAnalyzer:
    """Return stable growth-analysis structures even when dependencies fail."""

    DEFAULT_LOW_TRAFFIC_THRESHOLD = 300
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

            return {
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
            title_payload = analysis.get("title_score")
            title_payload = title_payload if isinstance(title_payload, dict) else {}
            optimized = title_payload.get("optimized_titles") or cls._safe_optimized_titles(title)
            view_count = cls._safe_int(analysis.get("view_count"))
            return {
                "ok": True,
                "error": None,
                "article_id": article_id,
                "low_traffic": view_count < threshold,
                "threshold": threshold,
                "failure_reason_analysis": cls._safe_list(analysis.get("failure_reasons")),
                "new_titles": cls._safe_list(optimized)[:3],
                "new_opening": cls._new_opening(title),
                "new_article_structure": cls._new_structure(),
                "new_cta": cls._new_cta(),
                "analysis": analysis,
                "fallback_used": True,
            }
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
                        a.id, a.title, a.summary, a.content, a.html_content,
                        a.status, a.created_at, a.updated_at,
                        COALESCE(g.view_count, 0) AS view_count,
                        COALESCE(g.like_count, 0) AS like_count,
                        COALESCE(g.comment_count, 0) AS comment_count,
                        COALESCE(g.share_count, 0) AS share_count,
                        COALESCE(g.favorite_count, 0) AS favorite_count,
                        COALESCE(g.scan_count, 0) AS scan_count,
                        COALESCE(g.consult_count, 0) AS consult_count,
                        COALESCE(g.title_score, 0) AS stored_title_score,
                        COALESCE(g.content_score, 0) AS stored_content_score,
                        COALESCE(g.growth_score, 0) AS stored_growth_score,
                        g.failure_reasons, g.suggestions
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
        metrics = cls._normalize_metrics(item)
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
            "summary": str(item.get("summary") or ""),
            "status": str(item.get("status") or "-"),
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
            "title_score": title_score,
            "content_score": content_score,
            "growth_score": growth_score,
            "growth_advice": cls._dashboard_advice(metrics, title_score, content_score, conversion_score),
            "failure_reasons": cls._parse_json_list(item.get("failure_reasons")),
            "suggestions": cls._parse_json_list(item.get("suggestions")),
        }

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
                       favorite_count, scan_count, consult_count
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
            return topics if isinstance(topics, list) else []
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
        return {
            "article_id": article_id,
            "low_traffic": True,
            "threshold": cls._safe_threshold(threshold),
            "failure_reason_analysis": ["暂未取得完整数据，请先检查文章和数据库状态。"],
            "new_titles": cls._safe_optimized_titles("企业融资")[:3],
            "new_opening": cls._new_opening("企业融资"),
            "new_article_structure": cls._new_structure(),
            "new_cta": cls._new_cta(),
            "analysis": {},
            "fallback_used": True,
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
