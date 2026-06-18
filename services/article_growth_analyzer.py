"""Growth analytics and rewrite suggestions for WeChat articles."""
from __future__ import annotations

from typing import Any

from database import get_db, is_mysql
from services.title_score_service import TitleScoreService
from services.topic_engine import TopicEngine


class ArticleGrowthAnalyzer:
    """Analyze article performance with safe defaults and no AI dependency."""

    DEFAULT_LOW_TRAFFIC_THRESHOLD = 300

    @classmethod
    def ensure_storage(cls) -> None:
        conn = get_db()
        try:
            if is_mysql():
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS article_growth_metrics (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        article_id BIGINT NOT NULL,
                        reads INT DEFAULT 0,
                        likes INT DEFAULT 0,
                        shares INT DEFAULT 0,
                        favorites INT DEFAULT 0,
                        comments INT DEFAULT 0,
                        qr_scans INT DEFAULT 0,
                        consultations INT DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE KEY uniq_article_growth_metrics_article_id (article_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            else:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS article_growth_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        article_id INTEGER NOT NULL UNIQUE,
                        reads INTEGER DEFAULT 0,
                        likes INTEGER DEFAULT 0,
                        shares INTEGER DEFAULT 0,
                        favorites INTEGER DEFAULT 0,
                        comments INTEGER DEFAULT 0,
                        qr_scans INTEGER DEFAULT 0,
                        consultations INTEGER DEFAULT 0,
                        created_at DATETIME DEFAULT (datetime('now','localtime')),
                        updated_at DATETIME DEFAULT (datetime('now','localtime'))
                    )
                    """
                )
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def analyze_article(cls, article_id: int, metrics_override: dict[str, Any] | None = None) -> dict[str, Any]:
        article = cls._get_article(article_id)
        if not article:
            return {"ok": False, "msg": "文章不存在"}

        metrics = cls._get_metrics(article_id)
        metrics.update(cls._normalize_metrics(metrics_override or {}))
        title_score = TitleScoreService.score_title(article.get("title", ""))
        content_score = cls._score_content(article)
        conversion_score = cls._score_conversion(metrics)
        performance_score = round(title_score["score"] * 0.35 + content_score * 0.35 + conversion_score * 0.3)

        title_problem = cls._title_problem(title_score)
        content_problem = cls._content_problem(article, content_score)
        cta_problem = cls._cta_problem(metrics, article)
        weakest = cls._weakest_area(title_score["score"], content_score, conversion_score)

        return {
            "ok": True,
            "article_id": article_id,
            "title": article.get("title", ""),
            "metrics": metrics,
            "performance_score": performance_score,
            "title_score": title_score,
            "content_score": content_score,
            "conversion_score": conversion_score,
            "failure_reasons": cls._failure_reasons(metrics, performance_score, title_problem, content_problem, cta_problem),
            "title_problem": title_problem,
            "content_problem": content_problem,
            "cta_problem": cta_problem,
            "next_optimization_suggestions": cls._suggestions(weakest, metrics),
            "recommended_next_topic": TopicEngine.recommend_next_topic(weakest),
        }

    @classmethod
    def rewrite_for_growth(
        cls,
        article_id: int,
        low_traffic_threshold: int | None = None,
        metrics_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        analysis = cls.analyze_article(article_id, metrics_override=metrics_override)
        if not analysis.get("ok"):
            return analysis
        threshold = int(low_traffic_threshold or cls.DEFAULT_LOW_TRAFFIC_THRESHOLD)
        metrics = analysis["metrics"]
        title = analysis.get("title", "")
        optimized = analysis["title_score"].get("optimized_titles") or TitleScoreService.optimize_titles(title)
        low_traffic = metrics.get("reads", 0) < threshold
        return {
            "ok": True,
            "article_id": article_id,
            "low_traffic": low_traffic,
            "threshold": threshold,
            "failure_reason_analysis": analysis["failure_reasons"],
            "new_titles": optimized[:3],
            "new_opening": cls._new_opening(title),
            "new_article_structure": cls._new_structure(),
            "new_cta": cls._new_cta(),
            "analysis": analysis,
        }

    @classmethod
    def dashboard(cls, limit: int = 100) -> dict[str, Any]:
        cls.ensure_storage()
        conn = get_db()
        placeholder = "%s" if is_mysql() else "?"
        try:
            rows = conn.execute(
                f"""
                SELECT
                    a.id, a.title, a.summary, a.content, a.html_content, a.status, a.created_at, a.updated_at,
                    COALESCE(g.reads, 0) AS reads,
                    COALESCE(g.likes, 0) AS likes,
                    COALESCE(g.shares, 0) AS shares,
                    COALESCE(g.favorites, 0) AS favorites,
                    COALESCE(g.comments, 0) AS comments,
                    COALESCE(g.qr_scans, 0) AS qr_scans,
                    COALESCE(g.consultations, 0) AS consultations
                FROM articles a
                LEFT JOIN article_growth_metrics g ON g.article_id = a.id
                ORDER BY a.created_at DESC
                LIMIT {placeholder}
                """,
                (int(limit or 100),),
            ).fetchall()
        except Exception:
            rows = conn.execute(
                f"SELECT id, title, summary, content, html_content, status, created_at, updated_at FROM articles ORDER BY created_at DESC LIMIT {placeholder}",
                (int(limit or 100),),
            ).fetchall()
        finally:
            conn.close()

        articles = []
        for row in rows:
            item = dict(row)
            metrics = cls._normalize_metrics(item)
            title_score = TitleScoreService.score_title(item.get("title", ""))
            content_score = cls._score_content(item)
            conversion_score = cls._score_conversion(metrics)
            growth_advice = cls._dashboard_advice(metrics, title_score["score"], content_score, conversion_score)
            articles.append({
                **item,
                **metrics,
                "title_score": title_score["score"],
                "content_score": content_score,
                "growth_advice": growth_advice,
            })
        return {
            "ok": True,
            "articles": articles,
            "topics": TopicEngine.generate_topics(limit=8),
        }

    @classmethod
    def _get_article(cls, article_id: int) -> dict[str, Any] | None:
        conn = get_db()
        placeholder = "%s" if is_mysql() else "?"
        try:
            row = conn.execute(f"SELECT * FROM articles WHERE id={placeholder}", (article_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @classmethod
    def _get_metrics(cls, article_id: int) -> dict[str, int]:
        cls.ensure_storage()
        conn = get_db()
        placeholder = "%s" if is_mysql() else "?"
        try:
            row = conn.execute(
                f"SELECT reads, likes, shares, favorites, comments, qr_scans, consultations FROM article_growth_metrics WHERE article_id={placeholder}",
                (article_id,),
            ).fetchone()
            return cls._normalize_metrics(dict(row) if row else {})
        finally:
            conn.close()

    @staticmethod
    def _normalize_metrics(raw: dict[str, Any]) -> dict[str, int]:
        aliases = {
            "reads": ("reads", "read_count", "阅读量"),
            "likes": ("likes", "like_count", "点赞"),
            "shares": ("shares", "share_count", "分享"),
            "favorites": ("favorites", "favorite_count", "收藏"),
            "comments": ("comments", "comment_count", "评论"),
            "qr_scans": ("qr_scans", "scan_count", "扫码数"),
            "consultations": ("consultations", "consult_count", "咨询数"),
        }
        metrics: dict[str, int] = {}
        for key, names in aliases.items():
            value = 0
            for name in names:
                if name in raw and raw.get(name) is not None:
                    value = raw.get(name)
                    break
            try:
                metrics[key] = max(0, int(value or 0))
            except (TypeError, ValueError):
                metrics[key] = 0
        return metrics

    @staticmethod
    def _score_content(article: dict[str, Any]) -> int:
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

    @staticmethod
    def _score_conversion(metrics: dict[str, int]) -> int:
        reads = max(1, metrics.get("reads", 0))
        engagement = metrics.get("likes", 0) + metrics.get("shares", 0) * 2 + metrics.get("favorites", 0) * 2 + metrics.get("comments", 0) * 2
        conversion = metrics.get("qr_scans", 0) * 4 + metrics.get("consultations", 0) * 8
        return min(100, round((engagement + conversion) / reads * 1000))

    @staticmethod
    def _title_problem(title_score: dict[str, Any]) -> str:
        problems = title_score.get("problems") or []
        return "；".join(problems[:2]) if problems else "标题具备痛点和转化钩子，可继续测试不同角度。"

    @staticmethod
    def _content_problem(article: dict[str, Any], score: int) -> str:
        if score >= 80:
            return "内容结构基本完整，继续强化案例细节和老板可执行动作。"
        return "内容缺少真实场景、案例拆解、问题清单或融资诊断引导，容易像泛泛科普。"

    @staticmethod
    def _cta_problem(metrics: dict[str, int], article: dict[str, Any]) -> str:
        text = f"{article.get('content', '')}\n{article.get('html_content', '')}"
        if metrics.get("qr_scans", 0) or metrics.get("consultations", 0):
            return "CTA 已产生转化，建议继续测试更具体的诊断入口。"
        if not any(word in text for word in ("扫码", "咨询", "融资诊断", "融资体检")):
            return "CTA 不够明确，缺少扫码、咨询或融资体检动作。"
        return "CTA 有动作但转化弱，建议把利益点改成“查被拒原因/测额度空间”。"

    @staticmethod
    def _weakest_area(title_score: int, content_score: int, conversion_score: int) -> str:
        values = {"标题点击": title_score, "内容信任": content_score, "CTA转化": conversion_score}
        return min(values, key=values.get)

    @staticmethod
    def _failure_reasons(metrics: dict[str, int], performance_score: int, title_problem: str, content_problem: str, cta_problem: str) -> list[str]:
        reasons = []
        if metrics.get("reads", 0) < ArticleGrowthAnalyzer.DEFAULT_LOW_TRAFFIC_THRESHOLD:
            reasons.append("阅读量低于默认阈值，优先检查标题点击欲望和首屏场景。")
        if performance_score < 70:
            reasons.extend([title_problem, content_problem, cta_problem])
        return reasons or ["当前数据未显示明显失败点，建议继续积累阅读和转化数据。"]

    @staticmethod
    def _suggestions(weakest: str, metrics: dict[str, int]) -> list[str]:
        if weakest == "标题点击":
            return ["标题改成老板痛点句", "加入被拒原因/额度提升/续贷风险", "用数字表达可检查的问题数量"]
        if weakest == "内容信任":
            return ["开头换成真实经营场景", "加入一个匿名企业案例", "用3-5个问题拆解审批卡点"]
        return ["CTA 改成融资体检", "把咨询利益点写具体", "在文末加入二维码/顾问引导"]

    @staticmethod
    def _dashboard_advice(metrics: dict[str, int], title_score: int, content_score: int, conversion_score: int) -> str:
        if metrics.get("reads", 0) < ArticleGrowthAnalyzer.DEFAULT_LOW_TRAFFIC_THRESHOLD:
            return "低流量：优先重写标题和开头。"
        if title_score < 80:
            return "标题弱：补痛点、数字和冲突。"
        if content_score < 80:
            return "内容弱：补案例、拆问题和建议。"
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
            "匿名案例：企业背景、申请过程、被拒/额度低原因",
            "3-5个问题拆解：征信、流水、负债、纳税、用途",
            "3-5个解决建议：资料、节奏、额度、银行匹配、风险控制",
            "风险提醒：不承诺放款，根据企业实际情况评估",
            "融资诊断 CTA：引导扫码/留言做融资体检",
        ]

    @staticmethod
    def _new_cta() -> str:
        return "如果你也遇到银行不批、额度低、续贷不稳，可以扫码做一次融资体检：先看被拒原因，再判断额度提升空间和下一步申请顺序。"
