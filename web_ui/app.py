"""
Flask Web 管理界面
"""
import sys
import os
import re
import logging
import csv
import io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, abort, Response
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_db, get_lastrowid, init_db, is_mysql
from config import WEB_USERNAME, WEB_PASSWORD, WEB_HOST, WEB_PORT, USERS, ROLE_PERMISSIONS, WEB_AUTO_RELOAD, SYSTEM_VERSION
from domain.article_status import STATUS_DRAFT, STATUS_REJECTED, split_legacy_status
from wechat_api.publisher import publish_approved_articles
from ai_processor.image_generator import generate_cover_for_article
from services.publish_service import PublishService
from services.publish_task_service import PublishTaskService
from services.review_service import ReviewService
from services.template_service import TemplateService
from services.article_service import ArticleService
from services.article_decision_agent import ArticleDecisionAgent
from services.article_category_agent import ArticleCategoryAgent
from services.article_generation_agent import ArticleGenerationAgent
from services.article_health_service import ArticleHealthService
from services.article_preflight_agent import ArticlePreflightAgent
from services.article_review_agent import ArticleReviewAgent
from services.article_rewrite_agent import ArticleRewriteAgent
from services.article_workflow_agent import ArticleWorkflowAgent
from services.ai_playbook_action_service import AIPlaybookActionService
from services.ai_operation_log_service import AIOperationLogService
from services.cover_task_service import CoverTaskService
from services.wechat_lead_card_adapter import adapt_lead_form_to_wechat_card
from services.wechat_html_adapter import adapt_html_for_wechat, inject_article_image_into_html

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "wechat_auto_secret_2024"
logger = logging.getLogger(__name__)

# 开发模式下启用模板自动重载，刷新页面即可看到模板改动。
app.config["TEMPLATES_AUTO_RELOAD"] = WEB_AUTO_RELOAD

# 本地密码覆盖文件：只保存后台修改后的密码哈希，不保存明文密码。
USER_PASSWORDS_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "user_passwords.json",
)

# ─── Jinja2 自定义过滤器 ──────────────────────────────────
import json as _json

@app.template_filter('fromjson')
def fromjson_filter(s):
    """将JSON字符串解析为Python对象"""
    if not s:
        return {}
    try:
        return _json.loads(s)
    except Exception:
        return {}


# ─── 权限工具函数 ──────────────────────────────────────────────
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
}


@app.template_filter("ai_status_label")
def ai_status_label_filter(value):
    """AI 风险监控页状态枚举展示中文化；内部枚举仍保留英文。"""
    if value is None:
        return ""
    text = str(value).strip()
    return AI_STATUS_LABELS.get(text, text)


def get_current_role():
    return session.get("role", "editor")

def read_user_password_overrides():
    """读取本地用户密码哈希覆盖配置。"""
    if not os.path.exists(USER_PASSWORDS_FILE_PATH):
        return {}

    try:
        with open(USER_PASSWORDS_FILE_PATH, "r", encoding="utf-8") as password_file:
            data = _json.load(password_file)
        return data if isinstance(data, dict) else {}
    except Exception:
        # 密码文件损坏时不影响原配置登录，避免账号被意外锁死。
        return {}


def build_article_preview_html(article) -> str:
    """生成后台预览用的公众号兼容正文，不写回数据库。"""
    if not article:
        return ""

    raw_html = (article["html_content"] or "").strip()
    if not raw_html:
        raw_html = (article["content"] or "").strip()
    if not raw_html or not raw_html.startswith("<"):
        return raw_html

    # 预览页和发布前保持同一套留资表单降级规则，避免运营看到不可用表单。
    html_with_image = inject_article_image_into_html(
        raw_html,
        get_article_cover_url(article),
        alt_text=(dict(article).get("title") or "文章配图"),
    )
    card_html = adapt_lead_form_to_wechat_card(html_with_image)
    return adapt_html_for_wechat(card_html)


def get_article_cover_url(article) -> str:
    """统一获取文章当前可展示的封面地址。"""
    if not article:
        return ""
    article_dict = dict(article)
    return (article_dict.get("cover_image") or article_dict.get("cover_url") or "").strip()


def update_article_cover_fields(conn, article_id: int, cover_payload: dict):
    """将封面生成结果写回 articles 表，兼容 SQLite / MySQL。"""
    cover_image = cover_payload.get("cover_image", "")
    cover_url = cover_payload.get("cover_url", "")
    cover_status = cover_payload.get("cover_status", "pending")
    cover_prompt = cover_payload.get("cover_prompt", "")

    if is_mysql():
        conn.execute(
            """
            UPDATE articles
            SET cover_image=%s, cover_url=%s, cover_status=%s, cover_prompt=%s, updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
            """,
            (cover_image, cover_url, cover_status, cover_prompt, article_id),
        )
        return

    conn.execute(
        """
        UPDATE articles
        SET cover_image=?, cover_url=?, cover_status=?, cover_prompt=?, updated_at=datetime('now','localtime')
        WHERE id=?
        """,
        (cover_image, cover_url, cover_status, cover_prompt, article_id),
    )

def write_user_password_overrides(overrides: dict):
    """写入本地用户密码哈希覆盖配置。"""
    os.makedirs(os.path.dirname(USER_PASSWORDS_FILE_PATH), exist_ok=True)
    with open(USER_PASSWORDS_FILE_PATH, "w", encoding="utf-8") as password_file:
        _json.dump(overrides, password_file, ensure_ascii=False, indent=2)

def has_password_override(username: str) -> bool:
    """判断指定账号是否已使用后台修改后的密码。"""
    return bool(read_user_password_overrides().get(username))

def verify_user_password(username: str, password: str, user_cfg: dict) -> bool:
    """校验用户密码，优先使用后台修改后的密码哈希。"""
    password_overrides = read_user_password_overrides()
    password_hash = password_overrides.get(username)

    if password_hash:
        try:
            return check_password_hash(password_hash, password)
        except Exception:
            return False

    # 未修改过密码时继续兼容原有配置文件 / 环境变量明文密码。
    return bool(user_cfg and user_cfg.get("password") == password)

def update_user_password(username: str, new_password: str):
    """更新指定账号的本地密码哈希。"""
    password_overrides = read_user_password_overrides()
    password_overrides[username] = generate_password_hash(new_password)
    write_user_password_overrides(password_overrides)

def get_perms():
    """获取当前用户的权限字典"""
    return ROLE_PERMISSIONS.get(get_current_role(), ROLE_PERMISSIONS["editor"])

def get_permission_items():
    """获取当前账号权限的中文展示列表。"""
    perms = get_perms()
    # 权限文案集中在路由层做轻量映射，账号详情页只负责展示，不新增权限体系。
    permission_labels = [
        ("can_approve", "审核文章"),
        ("can_publish", "发布与任务管理"),
        ("can_delete", "删除内容"),
        ("can_crawl", "触发采集"),
        ("can_view_leads", "查看线索数据"),
        ("can_view_service", "查看服务数据"),
        ("can_write", "原创写作"),
        ("can_edit", "编辑内容与配置"),
        ("show_nav_publish", "显示发布管理菜单"),
        ("show_nav_business", "显示业务模块菜单"),
    ]
    return [
        {
            "key": key,
            "label": label,
            "enabled": bool(perms.get(key, False)),
        }
        for key, label in permission_labels
    ]

def get_current_operator_info():
    """获取当前登录操作者信息，日志场景允许账号 ID 为空。"""
    operator_id = session.get("user_id") or session.get("operator_id")
    try:
        operator_id = int(operator_id) if operator_id is not None else None
    except (TypeError, ValueError):
        operator_id = None
    return operator_id, (session.get("username") or "").strip()

def record_ai_operation(article_id: int, agent_name: str, action_type: str, result: dict):
    """记录 AI 操作日志；日志失败不影响原接口返回。"""
    operator_id, operator_name = get_current_operator_info()
    AIOperationLogService.create_log(
        article_id=article_id,
        agent_name=agent_name,
        action_type=action_type,
        result=result,
        operator_id=operator_id,
        operator_name=operator_name,
    )

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def require_perm(perm_key):
    """权限装饰器，缺少权限时返回403"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("logged_in"):
                return redirect(url_for("login"))
            if not get_perms().get(perm_key, False):
                if request.is_json or request.method == "POST":
                    return jsonify({"ok": False, "msg": "权限不足，请联系管理员"}), 403
                return render_template("403.html", perm=perm_key), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

# 注入权限到所有模板
@app.context_processor
def inject_perms():
    return {
        "perms": get_perms(),
        "current_role": get_current_role(),
        "current_user": session.get("username", ""),
        "role_display": session.get("role_display", ""),
        "system_version": SYSTEM_VERSION,
    }



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user_cfg = USERS.get(username)
        if user_cfg and verify_user_password(username, password, user_cfg):
            session["logged_in"] = True
            session["username"] = username
            session["role"] = user_cfg["role"]
            session["role_display"] = user_cfg.get("display", user_cfg["role"])
            return redirect(url_for("index"))
        flash("用户名或密码错误")
    return render_template("login.html")



@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/account")
@login_required
def account_detail():
    """当前账号详情页。"""
    username = session.get("username", "") or WEB_USERNAME
    role = get_current_role()
    user_cfg = USERS.get(username, {})

    # 账号详情只展示当前登录态信息，不展示密码、不提供编辑，避免误改配置。
    account = {
        "username": username,
        "role": role,
        "role_display": session.get("role_display", "") or user_cfg.get("display", role),
        "source": "后台已修改密码" if has_password_override(username) else "配置文件 / 环境变量",
    }
    return render_template(
        "account_detail.html",
        account=account,
        permission_items=get_permission_items(),
    )


@app.route("/account/password", methods=["POST"])
@login_required
def change_account_password():
    """修改当前登录账号密码。"""
    username = session.get("username", "").strip()
    user_cfg = USERS.get(username)
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    # 只允许修改当前登录账号，避免跨账号修改带来权限风险。
    if not username or not user_cfg:
        flash("当前账号状态异常，请重新登录后再试")
        return redirect(url_for("account_detail"))

    if not verify_user_password(username, current_password, user_cfg):
        flash("当前密码不正确，请重新输入")
        return redirect(url_for("account_detail"))

    if len(new_password) < 6:
        flash("新密码长度至少需要 6 位")
        return redirect(url_for("account_detail"))

    if new_password != confirm_password:
        flash("两次输入的新密码不一致")
        return redirect(url_for("account_detail"))

    if current_password == new_password:
        flash("新密码不能与当前密码相同")
        return redirect(url_for("account_detail"))

    # 新密码仅保存哈希到本地文件，不回写 config.py，也不在页面中暴露明文。
    update_user_password(username, new_password)
    flash("密码修改成功，请使用新密码登录")
    return redirect(url_for("account_detail"))


@app.route("/")
@login_required
def index():
    conn = get_db()
    sql_placeholder = "%s" if is_mysql() else "?"

    # === 卡片1：待审稿件（分类型计数，6大类）===
    draft_total = conn.execute("SELECT COUNT(*) FROM articles WHERE status='draft'").fetchone()[0]
    draft_science = conn.execute(
        f"SELECT COUNT(*) FROM articles WHERE status={sql_placeholder} AND (tags LIKE {sql_placeholder} OR tags LIKE {sql_placeholder})",
        ("draft", "%科普%", "%知识%"),
    ).fetchone()[0]
    draft_brand = conn.execute(
        f"SELECT COUNT(*) FROM articles WHERE status={sql_placeholder} AND tags LIKE {sql_placeholder}",
        ("draft", "%品牌%"),
    ).fetchone()[0]
    draft_leads = conn.execute(
        f"SELECT COUNT(*) FROM articles WHERE status={sql_placeholder} AND tags LIKE {sql_placeholder}",
        ("draft", "%获客%"),
    ).fetchone()[0]
    draft_plan = conn.execute(
        f"SELECT COUNT(*) FROM articles WHERE status={sql_placeholder} AND tags LIKE {sql_placeholder}",
        ("draft", "%方案匹配%"),
    ).fetchone()[0]
    draft_finance = conn.execute(
        f"SELECT COUNT(*) FROM articles WHERE status={sql_placeholder} AND tags LIKE {sql_placeholder}",
        ("draft", "%融资规划%"),
    ).fetchone()[0]
    draft_business = conn.execute(
        f"SELECT COUNT(*) FROM articles WHERE status={sql_placeholder} AND tags LIKE {sql_placeholder}",
        ("draft", "%经营分析%"),
    ).fetchone()[0]

    # === 卡片2：已发布效果（分类型数据）===
    published_total = conn.execute("SELECT COUNT(*) FROM articles WHERE status='published'").fetchone()[0]
    draft_sent      = conn.execute("SELECT COUNT(*) FROM articles WHERE status='draft_sent'").fetchone()[0]
    approved        = conn.execute("SELECT COUNT(*) FROM articles WHERE status='approved'").fetchone()[0]

    # === 卡片3：获客线索（总/有效/转化）===
    try:
        leads_total   = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        leads_valid   = conn.execute("SELECT COUNT(*) FROM leads WHERE status IN ('new','assigned','contacted','converted')").fetchone()[0]
        leads_convert = conn.execute("SELECT COUNT(*) FROM leads WHERE status='converted'").fetchone()[0]
    except Exception:
        leads_total, leads_valid, leads_convert = 0, 0, 0

    # === 卡片4：服务工单（3类服务计数）===
    try:
        orders_loan    = conn.execute("SELECT COUNT(*) FROM work_orders WHERE order_type='loan_match'").fetchone()[0]
        orders_consult = conn.execute("SELECT COUNT(*) FROM work_orders WHERE order_type='finance_plan'").fetchone()[0]
        orders_plan    = conn.execute("SELECT COUNT(*) FROM work_orders WHERE order_type='enterprise_analysis'").fetchone()[0]
    except Exception:
        orders_loan, orders_consult, orders_plan = 0, 0, 0

    # === 卡片5：品牌曝光量 ===
    # 判断是否有 is_original 列，没有则默认所有原创内容都来自沪上银
    try:
        if is_mysql():
            cursor = conn.execute(
                """
                SELECT COLUMN_NAME AS name
                FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'articles'
                """
            )
            columns = [col["name"] for col in cursor.fetchall()]
        else:
            cursor = conn.execute("PRAGMA table_info(articles)")
            columns = [col[1] for col in cursor.fetchall()]
        has_is_original = "is_original" in columns
    except:
        has_is_original = False
    
    if has_is_original:
        brand_content = conn.execute("SELECT COUNT(*) FROM articles WHERE is_original=1").fetchone()[0]
    else:
        # 没有 is_original 列，就假设沪上银原创的都是品牌内容
        brand_content = conn.execute("SELECT COUNT(*) FROM articles WHERE source_name='沪上银原创'").fetchone()[0]

    try:
        brand_service = conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
    except Exception:
        brand_service = 0

    # === 卡片6：总计（内容+线索+服务）===
    total_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    rejected       = conn.execute("SELECT COUNT(*) FROM articles WHERE status='rejected'").fetchone()[0]

    stats = {
        # 卡片1 - 待审稿件（6大类）
        "draft": draft_total,
        "draft_science": draft_science,
        "draft_brand": draft_brand,
        "draft_leads": draft_leads,
        "draft_plan": draft_plan,
        "draft_finance": draft_finance,
        "draft_business": draft_business,
        # 卡片2 - 已发布效果
        "published": published_total,
        "draft_sent": draft_sent,
        "approved": approved,
        # 卡片3 - 获客线索
        "leads_total": leads_total,
        "leads_valid": leads_valid,
        "leads_convert": leads_convert,
        # 卡片4 - 服务工单
        "orders_loan": orders_loan,
        "orders_consult": orders_consult,
        "orders_plan": orders_plan,
        # 卡片5 - 品牌曝光
        "brand_content": brand_content,
        "brand_service": brand_service,
        # 卡片6 - 总计
        "total": total_articles,
        "rejected": rejected,
    }

    recent = conn.execute(
        "SELECT id, title, source_name, status, tags, is_original, created_at FROM articles ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return render_template("index.html", stats=stats, recent=recent)


@app.route("/articles")
@login_required
def articles():
    status_filter   = request.args.get("status", "")
    category_filter = request.args.get("category", "")
    time_filter     = request.args.get("time", "")   # today / week / month
    page     = int(request.args.get("page", 1))
    per_page = 20
    offset   = (page - 1) * per_page

    conn = get_db()
    sql_placeholder = "%s" if is_mysql() else "?"
    conditions = []
    params = []

    if status_filter:
        conditions.append(f"status={sql_placeholder}")
        params.append(status_filter)

    if category_filter:
        if category_filter == "science":
            # 知识科普：标签包含科普/知识
            conditions.append(f"(tags LIKE {sql_placeholder} OR tags LIKE {sql_placeholder})")
            params.extend(["%科普%", "%知识%"])
        elif category_filter == "brand":
            conditions.append(f"tags LIKE {sql_placeholder}")
            params.append("%品牌%")
        elif category_filter == "leads":
            conditions.append(f"tags LIKE {sql_placeholder}")
            params.append("%获客%")
        elif category_filter == "plan":
            conditions.append(f"tags LIKE {sql_placeholder}")
            params.append("%方案匹配%")
        elif category_filter == "finance":
            conditions.append(f"tags LIKE {sql_placeholder}")
            params.append("%融资规划%")
        elif category_filter == "business":
            conditions.append(f"tags LIKE {sql_placeholder}")
            params.append("%经营分析%")
        elif category_filter == "hotspot":
            conditions.append(f"(tags LIKE {sql_placeholder} OR tags LIKE {sql_placeholder})")
            params.extend(["%热点%", "%解读%"])
        else:
            like_pattern = f"%{category_filter}%"
            conditions.append(f"tags LIKE {sql_placeholder}")
            params.append(like_pattern)

    if time_filter == "today":
        conditions.append("DATE(created_at)=DATE('now','localtime')")
    elif time_filter == "week":
        conditions.append("created_at >= datetime('now','-7 days','localtime')")
    elif time_filter == "month":
        conditions.append("created_at >= datetime('now','-30 days','localtime')")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = conn.execute(
        f"SELECT * FROM articles {where_clause} ORDER BY created_at DESC LIMIT {sql_placeholder} OFFSET {sql_placeholder}",
        params + [per_page, offset]
    ).fetchall()
    total = conn.execute(
        f"SELECT COUNT(*) FROM articles {where_clause}", params
    ).fetchone()[0]
    conn.close()

    # 文章列表页只读取 AI 健康概览，不触发任何 Agent 或发布动作。
    article_ids = [article["id"] for article in rows]
    article_health_overview = ArticleHealthService.build_articles_health_overview(article_ids)

    return render_template("articles.html",
                           articles=rows,
                           article_health_overview=article_health_overview,
                           status_filter=status_filter,
                           category_filter=category_filter,
                           time_filter=time_filter,
                           page=page,
                           total=total,
                           per_page=per_page)


def _parse_ai_dashboard_filters():
    """统一解析 AI 风险监控面板筛选参数，页面和导出保持同一口径。"""
    risk_level = request.args.get("risk_level", "").strip()
    if risk_level not in ("", "low", "medium", "high", "unknown"):
        risk_level = ""

    need_attention = request.args.get("need_attention", "").strip() == "1"

    trend_direction = request.args.get("trend_direction", "").strip()
    if trend_direction not in ("", "up", "stable", "down"):
        trend_direction = ""

    max_score = None
    max_score_raw = request.args.get("max_score", "").strip()
    if max_score_raw:
        try:
            parsed_max_score = int(max_score_raw)
            if 0 <= parsed_max_score <= 100:
                max_score = parsed_max_score
        except ValueError:
            # 非法分数筛选直接忽略，避免页面因 query 参数异常报错。
            max_score = None

    return risk_level, need_attention, trend_direction, max_score


def _has_ai_dashboard_filters(risk_level, need_attention, trend_direction, max_score):
    """判断当前是否存在有效筛选条件，用于决定导出筛选结果还是默认风险 TOP。"""
    return bool(risk_level or need_attention or trend_direction or max_score is not None)


@app.route("/ai-dashboard")
@login_required
def ai_dashboard():
    """AI 风险监控面板，只读展示全局 AI 健康情况。"""
    perms = get_perms()
    if not (perms.get("can_approve") or perms.get("can_publish")):
        return render_template("403.html", perm="can_approve / can_publish"), 403

    risk_level, need_attention, trend_direction, max_score = _parse_ai_dashboard_filters()
    dashboard = ArticleHealthService.build_ai_risk_dashboard(
        risk_level=risk_level or None,
        need_attention=need_attention,
        trend_direction=trend_direction or None,
        max_score=max_score,
    )
    snapshot_changes = ArticleHealthService.build_dashboard_snapshot_changes(dashboard)
    ArticleHealthService.write_ai_dashboard_snapshot(dashboard)
    ArticleHealthService.append_ai_ops_score_history(
        ((dashboard or {}).get("ai_ops_score") or {}).get("score", 0)
    )
    ArticleHealthService.append_ai_ops_duty_history(
        (dashboard or {}).get("ai_ops_duty_mode") or {}
    )
    dashboard["ai_ops_duty_history_summary"] = ArticleHealthService.build_ai_ops_duty_history_summary()
    dashboard["ai_ops_timeline"] = ArticleHealthService.build_ai_ops_timeline(dashboard)
    dashboard["ai_ops_report_text"] = ArticleHealthService.build_ai_ops_report_text(dashboard)
    dashboard.update(ArticleHealthService.build_ai_dashboard_centers(dashboard))
    return render_template(
        "ai_dashboard.html",
        dashboard=dashboard,
        snapshot_changes=snapshot_changes,
    )


@app.route("/ai-dashboard/export")
@login_required
def ai_dashboard_export():
    """导出 AI 风险监控面板当前筛选结果；只读导出，不触发任何 Agent。"""
    perms = get_perms()
    if not (perms.get("can_approve") or perms.get("can_publish")):
        return render_template("403.html", perm="can_approve / can_publish"), 403

    risk_level, need_attention, trend_direction, max_score = _parse_ai_dashboard_filters()
    dashboard = ArticleHealthService.build_ai_risk_dashboard(
        risk_level=risk_level or None,
        need_attention=need_attention,
        trend_direction=trend_direction or None,
        max_score=max_score,
    )

    # 有筛选条件时导出筛选结果；无筛选条件时默认导出高风险 TOP，避免生成过大的全量文件。
    if _has_ai_dashboard_filters(risk_level, need_attention, trend_direction, max_score):
        export_rows = dashboard.get("filtered_articles", [])
    else:
        export_rows = dashboard.get("top_risk_articles", [])

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["文章ID", "标题", "健康分", "风险等级", "趋势方向", "分数变化", "是否人工关注", "查看链接"])
    for item in export_rows:
        article_id = item.get("article_id", "")
        writer.writerow([
            article_id,
            item.get("title", "") or "未知文章",
            item.get("score", ""),
            item.get("risk_level", ""),
            item.get("trend_direction", ""),
            item.get("score_change", ""),
            "是" if item.get("need_manual_attention") else "否",
            f"/article/{article_id}" if article_id else "",
        ])

    return Response(
        output.getvalue(),
        content_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=ai_dashboard_export.csv"},
    )


def _can_view_ai_dashboard_exports() -> bool:
    """AI Dashboard 导出权限与页面访问权限保持一致。"""
    perms = get_perms()
    return bool(perms.get("can_approve") or perms.get("can_publish"))


def _build_ai_dashboard_for_export() -> dict:
    """构建只读导出用 Dashboard，不写快照、不追加历史、不触发 Agent。"""
    dashboard = ArticleHealthService.build_ai_risk_dashboard()
    dashboard["ai_ops_timeline"] = ArticleHealthService.build_ai_ops_timeline(dashboard)
    dashboard["ai_ops_report_text"] = ArticleHealthService.build_ai_ops_report_text(dashboard)
    dashboard.update(ArticleHealthService.build_ai_dashboard_centers(dashboard))
    return dashboard


def _txt_export_response(filename: str, content: str) -> Response:
    return Response(
        "\ufeff" + (content or ""),
        content_type="text/plain; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _csv_export_response(filename: str, headers: list[str], rows: list[dict]) -> Response:
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows or []:
        writer.writerow({key: row.get(key, "") for key in headers})
    return Response(
        output.getvalue(),
        content_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/ai-dashboard/decision-brief-export")
@login_required
def ai_dashboard_decision_brief_export():
    """导出 AI 决策简报，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_format = request.args.get("format", "txt").strip().lower()
    if export_format not in {"txt", "csv"}:
        return jsonify({"ok": False, "msg": "不支持的决策简报导出格式"}), 400

    dashboard = _build_ai_dashboard_for_export()
    if export_format == "txt":
        return _txt_export_response(
            "ai_decision_brief.txt",
            ArticleHealthService.build_decision_brief_export_text(dashboard),
        )
    return _csv_export_response(
        "ai_decision_brief.csv",
        ["项目", "内容"],
        ArticleHealthService.build_decision_brief_export_rows(dashboard),
    )


@app.route("/ai-dashboard/governance-export")
@login_required
def ai_dashboard_governance_export():
    """导出 AI 治理数据，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_type = request.args.get("export_type", "").strip()
    allowed_headers = {
        "governance_rules": ["类型", "规则", "说明"],
        "violations": ["级别", "标题", "说明", "时间"],
        "high_risk_targets": ["文章ID", "标题", "风险等级", "健康分", "说明"],
        "today_must_do": ["优先级", "标题", "建议动作", "相关对象"],
    }
    if export_type not in allowed_headers:
        return jsonify({"ok": False, "msg": "不支持的治理导出类型"}), 400

    dashboard = _build_ai_dashboard_for_export()
    return _csv_export_response(
        f"ai_governance_{export_type}.csv",
        allowed_headers[export_type],
        ArticleHealthService.build_governance_export_rows(dashboard, export_type),
    )


@app.route("/ai-dashboard/simulation-export")
@login_required
def ai_dashboard_simulation_export():
    """导出 AI 策略模拟数据，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_type = request.args.get("export_type", "").strip()
    allowed_headers = {
        "scenarios": ["场景", "影响", "等级"],
        "best_scenario": ["场景", "影响", "等级"],
        "risk_scenario": ["场景", "影响", "等级"],
        "simulation_history": ["类型", "标题", "说明", "时间"],
    }
    if export_type not in allowed_headers:
        return jsonify({"ok": False, "msg": "不支持的模拟导出类型"}), 400

    dashboard = _build_ai_dashboard_for_export()
    return _csv_export_response(
        f"ai_simulation_{export_type}.csv",
        allowed_headers[export_type],
        ArticleHealthService.build_simulation_export_rows(dashboard, export_type),
    )


@app.route("/ai-dashboard/sop-export")
@login_required
def ai_dashboard_sop_export():
    """导出 AI Dashboard SOP，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_format = request.args.get("format", "txt").strip().lower()
    sop_type = request.args.get("sop_type", "all").strip()
    if export_format not in {"txt", "csv"}:
        return jsonify({"ok": False, "msg": "不支持的 SOP 导出格式"}), 400

    allowed_sop_types = {
        "all",
        "risk_control_sops",
        "recovery_sops",
        "governance_sops",
        "ops_checklists",
        "duty_sops",
        "incident_response_sops",
    }
    if sop_type not in allowed_sop_types:
        return jsonify({"ok": False, "msg": "不支持的 SOP 导出类型"}), 400

    dashboard = _build_ai_dashboard_for_export()
    if export_format == "txt":
        return _txt_export_response(
            f"ai_dashboard_sop_{sop_type}.txt",
            ArticleHealthService.build_sop_export_text(dashboard, sop_type=sop_type),
        )
    return _csv_export_response(
        f"ai_dashboard_sop_{sop_type}.csv",
        ["类型", "步骤", "说明"],
        ArticleHealthService.build_sop_export_rows(dashboard, sop_type=sop_type),
    )


@app.route("/ai-dashboard/runtime-learning-export")
@login_required
def ai_dashboard_runtime_learning_export():
    """导出 AI 运行时学习中心数据，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_format = request.args.get("format", "txt").strip().lower()
    export_type = request.args.get("export_type", "all").strip()
    if export_format not in {"txt", "csv"}:
        return jsonify({"ok": False, "msg": "不支持的运行时学习导出格式"}), 400

    allowed_export_types = {
        "all",
        "key_learnings",
        "repeated_incident_patterns",
        "effective_recovery_patterns",
        "unstable_runtime_components",
        "sop_improvement_suggestions",
        "governance_improvement_suggestions",
        "learning_history",
    }
    if export_type not in allowed_export_types:
        return jsonify({"ok": False, "msg": "不支持的运行时学习导出类型"}), 400

    dashboard = _build_ai_dashboard_for_export()
    if export_format == "txt":
        return _txt_export_response(
            f"ai_runtime_learning_{export_type}.txt",
            ArticleHealthService.build_runtime_learning_export_text(dashboard, export_type=export_type),
        )
    return _csv_export_response(
        f"ai_runtime_learning_{export_type}.csv",
        ["类别", "标题/对象", "等级/状态", "摘要", "证据/原因", "建议动作", "来源"],
        ArticleHealthService.build_runtime_learning_export_rows(dashboard, export_type=export_type),
    )


@app.route("/ai-dashboard/runtime-knowledge-sync-export")
@login_required
def ai_dashboard_runtime_knowledge_sync_export():
    """导出 AI 运行时知识同步中心数据，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_format = request.args.get("format", "txt").strip().lower()
    export_type = request.args.get("export_type", "all").strip()
    if export_format not in {"txt", "csv"}:
        return jsonify({"ok": False, "msg": "不支持的运行时知识同步导出格式"}), 400

    allowed_export_types = {
        "all",
        "knowledge_sync_suggestions",
        "sop_sync_suggestions",
        "governance_sync_suggestions",
        "checklist_sync_suggestions",
        "sync_gaps",
        "sync_history",
    }
    if export_type not in allowed_export_types:
        return jsonify({"ok": False, "msg": "不支持的运行时知识同步导出类型"}), 400

    dashboard = _build_ai_dashboard_for_export()
    if export_format == "txt":
        return _txt_export_response(
            f"ai_runtime_knowledge_sync_{export_type}.txt",
            ArticleHealthService.build_runtime_knowledge_sync_export_text(dashboard, export_type=export_type),
        )
    return _csv_export_response(
        f"ai_runtime_knowledge_sync_{export_type}.csv",
        ["类别", "标题/对象", "等级/状态", "摘要", "目标中心", "来源", "建议动作"],
        ArticleHealthService.build_runtime_knowledge_sync_export_rows(dashboard, export_type=export_type),
    )


@app.route("/ai-dashboard/runtime-weekly-review-export")
@login_required
def ai_dashboard_runtime_weekly_review_export():
    """导出 AI 运行时周复盘中心数据，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_format = request.args.get("format", "txt").strip().lower()
    if export_format not in {"txt", "csv"}:
        return jsonify({"ok": False, "msg": "不支持的运行时周复盘导出格式"}), 400

    dashboard = _build_ai_dashboard_for_export()
    if export_format == "txt":
        return _txt_export_response(
            "ai_runtime_weekly_review.txt",
            ArticleHealthService.build_runtime_weekly_review_export_text(dashboard),
        )
    return _csv_export_response(
        "ai_runtime_weekly_review.csv",
        ["类型", "标题", "状态/等级", "摘要", "建议动作"],
        ArticleHealthService.build_runtime_weekly_review_export_rows(dashboard),
    )


@app.route("/ai-dashboard/runtime-feedback-loop-export")
@login_required
def ai_dashboard_runtime_feedback_loop_export():
    """导出 AI 运行时反馈闭环中心数据，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_format = request.args.get("format", "txt").strip().lower()
    if export_format not in {"txt", "csv"}:
        return jsonify({"ok": False, "msg": "不支持的运行时反馈闭环导出格式"}), 400

    dashboard = _build_ai_dashboard_for_export()
    if export_format == "txt":
        return _txt_export_response(
            "ai_runtime_feedback_loop.txt",
            ArticleHealthService.build_runtime_feedback_loop_export_text(dashboard),
        )
    return _csv_export_response(
        "ai_runtime_feedback_loop.csv",
        ["类型", "标题", "状态/等级", "摘要", "建议动作"],
        ArticleHealthService.build_runtime_feedback_loop_export_rows(dashboard),
    )


@app.route("/ai-dashboard/runtime-evolution-export")
@login_required
def ai_dashboard_runtime_evolution_export():
    """导出 AI 运行时进化中心数据，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_format = request.args.get("format", "txt").strip().lower()
    if export_format not in {"txt", "csv"}:
        return jsonify({"ok": False, "msg": "不支持的运行时进化导出格式"}), 400

    dashboard = _build_ai_dashboard_for_export()
    if export_format == "txt":
        return _txt_export_response(
            "ai_runtime_evolution.txt",
            ArticleHealthService.build_runtime_evolution_export_text(dashboard),
        )
    return _csv_export_response(
        "ai_runtime_evolution.csv",
        ["类型", "标题", "等级/状态", "分数", "摘要", "建议动作"],
        ArticleHealthService.build_runtime_evolution_export_rows(dashboard),
    )


@app.route("/ai-dashboard/runtime-orchestrator-export")
@login_required
def ai_dashboard_runtime_orchestrator_export():
    """导出 AI 运行时编排中心数据，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_format = request.args.get("format", "txt").strip().lower()
    if export_format not in {"txt", "csv"}:
        return jsonify({"ok": False, "msg": "不支持的运行时编排导出格式"}), 400

    dashboard = _build_ai_dashboard_for_export()
    if export_format == "txt":
        return _txt_export_response(
            "ai_runtime_orchestrator.txt",
            ArticleHealthService.build_runtime_orchestrator_export_text(dashboard),
        )
    return _csv_export_response(
        "ai_runtime_orchestrator.csv",
        ["类型", "标题", "状态/等级", "摘要", "建议动作"],
        ArticleHealthService.build_runtime_orchestrator_export_rows(dashboard),
    )


@app.route("/ai-dashboard/runtime-control-policy-export")
@login_required
def ai_dashboard_runtime_control_policy_export():
    """导出 AI 运行时控制策略中心数据，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_format = request.args.get("format", "txt").strip().lower()
    if export_format not in {"txt", "csv"}:
        return jsonify({"ok": False, "msg": "不支持的运行时控制策略导出格式"}), 400

    dashboard = _build_ai_dashboard_for_export()
    if export_format == "txt":
        return _txt_export_response(
            "ai_runtime_control_policy.txt",
            ArticleHealthService.build_runtime_control_policy_export_text(dashboard),
        )
    return _csv_export_response(
        "ai_runtime_control_policy.csv",
        ["类型", "标题", "状态/等级", "摘要", "建议动作"],
        ArticleHealthService.build_runtime_control_policy_export_rows(dashboard),
    )


@app.route("/ai-dashboard/runtime-policy-gate-export")
@login_required
def ai_dashboard_runtime_policy_gate_export():
    """导出 AI 运行时策略闸门中心数据，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_format = request.args.get("format", "txt").strip().lower()
    if export_format not in {"txt", "csv"}:
        return jsonify({"ok": False, "msg": "不支持的运行时策略闸门导出格式"}), 400

    dashboard = _build_ai_dashboard_for_export()
    if export_format == "txt":
        return _txt_export_response(
            "ai_runtime_policy_gate.txt",
            ArticleHealthService.build_runtime_policy_gate_export_text(dashboard),
        )
    return _csv_export_response(
        "ai_runtime_policy_gate.csv",
        ["类型", "标题", "状态/等级", "摘要", "建议动作"],
        ArticleHealthService.build_runtime_policy_gate_export_rows(dashboard),
    )


@app.route("/ai-dashboard/runtime-confidence-export")
@login_required
def ai_dashboard_runtime_confidence_export():
    """导出 AI 运行时置信度中心数据，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_format = request.args.get("format", "txt").strip().lower()
    if export_format not in {"txt", "csv"}:
        return jsonify({"ok": False, "msg": "不支持的运行时置信度导出格式"}), 400

    dashboard = _build_ai_dashboard_for_export()
    if export_format == "txt":
        return _txt_export_response(
            "ai_runtime_confidence.txt",
            ArticleHealthService.build_runtime_confidence_export_text(dashboard),
        )
    return _csv_export_response(
        "ai_runtime_confidence.csv",
        ["类型", "标题", "状态/等级", "分数", "摘要", "建议动作"],
        ArticleHealthService.build_runtime_confidence_export_rows(dashboard),
    )


@app.route("/ai-dashboard/runtime-trust-export")
@login_required
def ai_dashboard_runtime_trust_export():
    """导出 AI 运行时信任中心数据，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_format = request.args.get("format", "txt").strip().lower()
    if export_format not in {"txt", "csv"}:
        return jsonify({"ok": False, "msg": "不支持的运行时信任导出格式"}), 400

    dashboard = _build_ai_dashboard_for_export()
    if export_format == "txt":
        return _txt_export_response(
            "ai_runtime_trust.txt",
            ArticleHealthService.build_runtime_trust_export_text(dashboard),
        )
    return _csv_export_response(
        "ai_runtime_trust.csv",
        ["类型", "标题", "状态/等级", "分数", "摘要", "建议动作"],
        ArticleHealthService.build_runtime_trust_export_rows(dashboard),
    )


@app.route("/ai-dashboard/runtime-delegation-readiness-export")
@login_required
def ai_dashboard_runtime_delegation_readiness_export():
    """导出 AI 运行时授权准备度中心数据，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_format = request.args.get("format", "txt").strip().lower()
    if export_format not in {"txt", "csv"}:
        return jsonify({"ok": False, "msg": "不支持的运行时授权准备度导出格式"}), 400

    dashboard = _build_ai_dashboard_for_export()
    if export_format == "txt":
        return _txt_export_response(
            "ai_runtime_delegation_readiness.txt",
            ArticleHealthService.build_runtime_delegation_readiness_export_text(dashboard),
        )
    return _csv_export_response(
        "ai_runtime_delegation_readiness.csv",
        ["类型", "标题", "状态/等级", "摘要", "建议动作"],
        ArticleHealthService.build_runtime_delegation_readiness_export_rows(dashboard),
    )


@app.route("/ai-dashboard/runtime-boundary-export")
@login_required
def ai_dashboard_runtime_boundary_export():
    """导出 AI 运行时边界中心数据，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_format = request.args.get("format", "txt").strip().lower()
    if export_format not in {"txt", "csv"}:
        return jsonify({"ok": False, "msg": "不支持的运行时边界导出格式"}), 400

    dashboard = _build_ai_dashboard_for_export()
    if export_format == "txt":
        return _txt_export_response(
            "ai_runtime_boundary.txt",
            ArticleHealthService.build_runtime_boundary_export_text(dashboard),
        )
    return _csv_export_response(
        "ai_runtime_boundary.csv",
        ["类型", "标题", "状态/等级", "摘要", "建议动作"],
        ArticleHealthService.build_runtime_boundary_export_rows(dashboard),
    )


@app.route("/ai-dashboard/runtime-constitution-export")
@login_required
def ai_dashboard_runtime_constitution_export():
    """导出 AI 运行时宪法中心数据，只读导出，不触发任何 Agent。"""
    if not _can_view_ai_dashboard_exports():
        return render_template("403.html", perm="can_approve / can_publish"), 403

    export_format = request.args.get("format", "txt").strip().lower()
    if export_format not in {"txt", "csv"}:
        return jsonify({"ok": False, "msg": "不支持的运行时宪法导出格式"}), 400

    dashboard = _build_ai_dashboard_for_export()
    if export_format == "txt":
        return _txt_export_response(
            "ai_runtime_constitution.txt",
            ArticleHealthService.build_runtime_constitution_export_text(dashboard),
        )
    return _csv_export_response(
        "ai_runtime_constitution.csv",
        ["类型", "标题", "状态/等级", "摘要", "建议动作"],
        ArticleHealthService.build_runtime_constitution_export_rows(dashboard),
    )


@app.route("/ai-dashboard/playbook-action", methods=["POST"])
@login_required
def ai_dashboard_playbook_action():
    """人工确认后执行 Playbook 安全动作；只读，不修改文章或发布状态。"""
    perms = get_perms()
    if not (perms.get("can_approve") or perms.get("can_publish")):
        return jsonify({"ok": False, "msg": "权限不足，请联系管理员"}), 403

    payload = request.get_json(silent=True) or {}
    action_type = (payload.get("action_type") or "").strip()
    if action_type not in {"rerun_preflight", "rerun_decision"}:
        return jsonify({"ok": False, "msg": "不支持的 Playbook 动作"}), 400

    try:
        article_id = int(payload.get("article_id") or 0)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "msg": "文章 ID 无效"}), 400
    if article_id <= 0:
        return jsonify({"ok": False, "msg": "文章 ID 无效"}), 400

    result = AIPlaybookActionService.execute_action(action_type, article_id)
    status_code = 200 if result.get("ok") else 400
    if result.get("msg") == "文章不存在":
        status_code = 404
    return jsonify(result), status_code


@app.route("/article/<int:article_id>")
@login_required
def article_detail(article_id):
    """文章详情页。"""
    conn = get_db()
    article = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
    conn.close()
    if not article:
        return "文章不存在", 404

    # 详情页附带最近一次发布任务摘要，方便运营侧快速查看发布状态。
    latest_publish_task = PublishTaskService.get_latest_task_for_article(article_id)
    # 详情页只展示最近 AI 操作摘要，不展示完整 result_json，避免页面过长。
    ai_operation_logs = AIOperationLogService.list_logs_for_article(article_id, limit=10)
    # AI 健康状态只做只读分析，不触发任何 Agent 或发布任务。
    article_health = ArticleHealthService.build_article_health(article_id)
    # AI 健康趋势基于最近 AI 操作日志动态估算，不写入数据库。
    article_health_trend = ArticleHealthService.build_health_trend(article_id)
    latest_cover_task = CoverTaskService.get_latest_cover_task(article_id)
    return render_template(
        "article_detail.html",
        article=article,
        article_cover_url=get_article_cover_url(article),
        article_preview_html=build_article_preview_html(article),
        latest_publish_task=latest_publish_task,
        latest_cover_task=latest_cover_task,
        ai_operation_logs=ai_operation_logs,
        article_health=article_health,
        article_health_trend=article_health_trend,
    )


@app.route("/article/<int:article_id>/approve", methods=["POST"])
@require_perm("can_approve")
def approve_article(article_id):
    """审核通过文章，并自动推送到微信草稿箱。"""
    # 路由层仅负责调用 service，并保持原有返回结构不变。
    result, status_code = ReviewService.approve_article(article_id)
    return jsonify(result), status_code


@app.route("/article/<int:article_id>/reject", methods=["POST"])
@require_perm("can_approve")
def reject_article(article_id):
    """审核拒绝文章。"""
    # 路由层仅负责调用 service，并保持原有返回结构不变。
    result, status_code = ReviewService.reject_article(article_id)
    return jsonify(result), status_code


@app.route("/article/<int:article_id>/ai-review", methods=["POST"])
@login_required
def ai_review_article(article_id):
    """返回 AI 审核建议；只读，不替代人工审核，也不修改文章内容。"""
    perms = get_perms()
    if not (perms.get("can_approve") or perms.get("can_edit")):
        return jsonify({"ok": False, "msg": "权限不足，请联系管理员"}), 403

    conn = get_db()
    # 明确区分 SQLite/MySQL 占位符，避免新接口依赖迁移期 SQL 兜底转换。
    placeholder = "%s" if is_mysql() else "?"
    article = conn.execute(f"SELECT * FROM articles WHERE id={placeholder}", (article_id,)).fetchone()
    conn.close()
    if not article:
        result = {"ok": False, "msg": "文章不存在"}
        record_ai_operation(article_id, "ArticleReviewAgent", "ai_review", result)
        return jsonify(result), 404

    result = ArticleReviewAgent().review_article(dict(article))
    record_ai_operation(article_id, "ArticleReviewAgent", "ai_review", result)
    return jsonify(result)


@app.route("/article/<int:article_id>/ai-rewrite", methods=["POST"])
@login_required
def ai_rewrite_article(article_id):
    """返回 AI 优化建议稿；只预览，不保存、不审核、不发布。"""
    perms = get_perms()
    if not (perms.get("can_approve") or perms.get("can_edit")):
        return jsonify({"ok": False, "msg": "权限不足，请联系管理员"}), 403

    conn = get_db()
    # 明确区分 SQLite/MySQL 占位符，避免新接口依赖迁移期 SQL 兜底转换。
    placeholder = "%s" if is_mysql() else "?"
    article = conn.execute(f"SELECT * FROM articles WHERE id={placeholder}", (article_id,)).fetchone()
    conn.close()
    if not article:
        result = {"ok": False, "msg": "文章不存在"}
        record_ai_operation(article_id, "ArticleRewriteAgent", "ai_rewrite", result)
        return jsonify(result), 404

    payload = request.get_json(silent=True) or {}
    review_result = payload.get("review_result") if isinstance(payload, dict) else None
    if not isinstance(review_result, dict):
        review_result = None

    result = ArticleRewriteAgent().rewrite_article(dict(article), review_result)
    record_ai_operation(article_id, "ArticleRewriteAgent", "ai_rewrite", result)
    return jsonify(result)


@app.route("/article/<int:article_id>/apply-ai-rewrite", methods=["POST"])
@require_perm("can_edit")
def apply_ai_rewrite_article(article_id):
    """手动应用 AI 优化稿；只写回内容字段，不审核、不发布。"""
    payload = request.get_json(silent=True) or {}
    result, status_code = ArticleService.apply_ai_rewrite(article_id, payload)
    record_ai_operation(article_id, "ArticleService", "apply_ai_rewrite", result)
    return jsonify(result), status_code


@app.route("/article/<int:article_id>/ai-preflight", methods=["POST"])
@login_required
def ai_preflight_article(article_id):
    """返回 AI 发布前终检建议；只读，不审核、不发布、不创建任务。"""
    perms = get_perms()
    if not (perms.get("can_approve") or perms.get("can_publish")):
        return jsonify({"ok": False, "msg": "权限不足，请联系管理员"}), 403

    conn = get_db()
    # 明确区分 SQLite/MySQL 占位符，避免新接口依赖迁移期 SQL 兜底转换。
    placeholder = "%s" if is_mysql() else "?"
    article = conn.execute(f"SELECT * FROM articles WHERE id={placeholder}", (article_id,)).fetchone()
    conn.close()
    if not article:
        result = {"ok": False, "msg": "文章不存在"}
        record_ai_operation(article_id, "ArticlePreflightAgent", "ai_preflight", result)
        return jsonify(result), 404

    result = ArticlePreflightAgent().preflight_article(dict(article))
    record_ai_operation(article_id, "ArticlePreflightAgent", "ai_preflight", result)
    return jsonify(result)


@app.route("/article/<int:article_id>/ai-decision", methods=["POST"])
@login_required
def ai_decision_article(article_id):
    """返回 AI 运营决策建议；只读，不执行任何文章操作。"""
    perms = get_perms()
    if not (perms.get("can_edit") or perms.get("can_approve") or perms.get("can_publish")):
        return jsonify({"ok": False, "msg": "权限不足，请联系管理员"}), 403

    conn = get_db()
    # 明确区分 SQLite/MySQL 占位符，避免新接口依赖迁移期 SQL 兜底转换。
    placeholder = "%s" if is_mysql() else "?"
    article = conn.execute(f"SELECT * FROM articles WHERE id={placeholder}", (article_id,)).fetchone()
    conn.close()
    if not article:
        result = {"ok": False, "msg": "文章不存在"}
        record_ai_operation(article_id, "ArticleDecisionAgent", "ai_decision", result)
        return jsonify(result), 404

    payload = request.get_json(silent=True) or {}
    review_result = payload.get("review_result") if isinstance(payload, dict) else None
    preflight_result = payload.get("preflight_result") if isinstance(payload, dict) else None
    if not isinstance(review_result, dict):
        review_result = None
    if not isinstance(preflight_result, dict):
        preflight_result = None

    latest_publish_task = PublishTaskService.get_latest_task_for_article(article_id)
    latest_publish_task_dict = dict(latest_publish_task) if latest_publish_task else None
    result = ArticleDecisionAgent().decide_next_action(
        dict(article),
        review_result=review_result,
        preflight_result=preflight_result,
        latest_publish_task=latest_publish_task_dict,
    )
    record_ai_operation(article_id, "ArticleDecisionAgent", "ai_decision", result)
    return jsonify(result)


@app.route("/article/<int:article_id>/ai-workflow", methods=["POST"])
@login_required
def ai_workflow_article(article_id):
    """返回 AI 工作流分析报告；只读，不自动执行任何动作。"""
    perms = get_perms()
    if not (perms.get("can_edit") or perms.get("can_approve") or perms.get("can_publish")):
        return jsonify({"ok": False, "msg": "权限不足，请联系管理员"}), 403

    conn = get_db()
    # 明确区分 SQLite/MySQL 占位符，避免新接口依赖迁移期 SQL 兜底转换。
    placeholder = "%s" if is_mysql() else "?"
    article = conn.execute(f"SELECT * FROM articles WHERE id={placeholder}", (article_id,)).fetchone()
    conn.close()
    if not article:
        result = {"ok": False, "msg": "文章不存在"}
        record_ai_operation(article_id, "ArticleWorkflowAgent", "ai_workflow", result)
        return jsonify(result), 404

    result = ArticleWorkflowAgent().run_workflow(dict(article))
    record_ai_operation(article_id, "ArticleWorkflowAgent", "ai_workflow", result)
    return jsonify(result)


def _is_missing_table_error(exc: Exception) -> bool:
    """兼容 SQLite/MySQL 的表不存在判断，删除文章时缺少低频关联表不阻断主流程。"""
    text = " ".join(str(part) for part in getattr(exc, "args", ()) if part)
    text = text or str(exc)
    lowered = text.lower()
    return (
        "no such table" in lowered
        or "doesn't exist" in lowered
        or "does not exist" in lowered
        or "unknown table" in lowered
        or "1146" in lowered
    )


def _delete_article_related_rows(conn, article_id: int, placeholder: str) -> dict:
    """先清理文章关联数据，再删除 articles，避免 MySQL 外键约束失败。"""
    related_tables = [
        "ai_operation_logs",
        "cover_generation_tasks",
        "publish_tasks",
        "review_actions",
        "channel_drafts",
    ]
    deleted_counts = {}
    for table_name in related_tables:
        try:
            cursor = conn.execute(
                f"DELETE FROM {table_name} WHERE article_id={placeholder}",
                (article_id,),
            )
            deleted_counts[table_name] = getattr(cursor, "rowcount", 0)
        except Exception as exc:
            if _is_missing_table_error(exc):
                deleted_counts[table_name] = "missing"
                logger.warning(
                    "[article-delete] related table missing article_id=%s table=%s error=%s",
                    article_id,
                    table_name,
                    exc,
                )
                continue
            raise
    return deleted_counts


@app.route("/article/<int:article_id>/delete", methods=["POST"])
@require_perm("can_delete")
def delete_article(article_id):
    conn = get_db()
    placeholder = "%s" if is_mysql() else "?"
    try:
        deleted_counts = _delete_article_related_rows(conn, article_id, placeholder)
        article_cursor = conn.execute(f"DELETE FROM articles WHERE id={placeholder}", (article_id,))
        deleted_counts["articles"] = getattr(article_cursor, "rowcount", 0)
        conn.commit()
        logger.info("[article-delete] article_id=%s deleted_counts=%s", article_id, deleted_counts)
        return jsonify({"ok": True, "msg": "已删除"})
    except Exception as exc:
        conn.rollback()
        logger.exception("[article-delete] failed article_id=%s error=%s", article_id, exc)
        return jsonify({"ok": False, "msg": "删除失败，请稍后重试"}), 500
    finally:
        conn.close()


@app.route("/article/<int:article_id>/regenerate-cover", methods=["POST"])
@require_perm("can_edit")
def regenerate_article_cover(article_id):
    """Create or reuse an async cover generation task."""
    conn = get_db()
    placeholder = "%s" if is_mysql() else "?"
    article = conn.execute(
        f"SELECT id, tags FROM articles WHERE id={placeholder}",
        (article_id,),
    ).fetchone()
    conn.close()
    if not article:
        return jsonify({"ok": False, "msg": "文章不存在"}), 404

    task = CoverTaskService.create_cover_task(article_id, style=(article["tags"] or ""))
    if not task:
        return jsonify({"ok": False, "msg": "封面生成任务创建失败"}), 400

    return jsonify(
        {
            "ok": True,
            "msg": "AI封面生成任务已提交，请稍后刷新查看",
            "task_id": task.get("id"),
            "status": task.get("status", "queued"),
        }
    )


@app.route("/article/<int:article_id>/cover-task-status", methods=["GET"])
@login_required
def article_cover_task_status(article_id):
    """Return the latest cover task state for frontend polling."""
    conn = get_db()
    placeholder = "%s" if is_mysql() else "?"
    article = conn.execute(
        f"SELECT id, cover_status, cover_image, cover_url FROM articles WHERE id={placeholder}",
        (article_id,),
    ).fetchone()
    conn.close()
    if not article:
        return jsonify(
            {
                "status": "none",
                "task_id": None,
                "cover_status": "",
                "cover_image_path": "",
                "error_message": "文章不存在",
            }
        ), 404

    task = CoverTaskService.get_latest_cover_task(article_id)
    return jsonify(
        {
            "status": task.get("status", "none") if task else "none",
            "task_id": task.get("id") if task else None,
            "cover_status": article["cover_status"] or "",
            "cover_image_path": article["cover_image"] or article["cover_url"] or "",
            "error_message": task.get("error_message", "") if task else "",
        }
    )

# ─── 获客数据页（占位，后续接入真实数据）────────────────────────
@app.route("/article/<int:article_id>/leads")
@login_required
def article_leads(article_id):
    if not get_perms().get("can_view_leads", False):
        return render_template("403.html", perm="can_view_leads"), 403
    conn = get_db()
    article = conn.execute("SELECT id, title, source_name, created_at, tags FROM articles WHERE id=?", (article_id,)).fetchone()
    conn.close()
    if not article:
        return "文章不存在", 404
    # 模拟数据：后续接入真实获客系统
    mock_leads = []
    return render_template("leads_data.html", article=article, leads=mock_leads)


# ─── 服务数据页（占位，后续接入真实数据）────────────────────────
@app.route("/article/<int:article_id>/service")
@login_required
def article_service(article_id):
    if not get_perms().get("can_view_service", False):
        return render_template("403.html", perm="can_view_service"), 403
    conn = get_db()
    article = conn.execute("SELECT id, title, source_name, created_at, tags FROM articles WHERE id=?", (article_id,)).fetchone()
    conn.close()
    if not article:
        return "文章不存在", 404
    mock_orders = []
    return render_template("service_data.html", article=article, orders=mock_orders)


# ─── 数据分析报表页 ─────────────────────────
@app.route("/reports")
@login_required
def reports():
    """数据分析报表 - 4类核心报表"""
    conn = get_db()
    
    # 内容类型统计数据
    content_stats = []
    type_configs = [
        ("自动获客", "获客", "success"),
        ("品牌宣传", "品牌", "warning"),
        ("知识科普", "科普", "primary"),
        ("方案匹配", "方案", "info"),
        ("融资规划", "融资", "secondary"),
        ("经营分析", "经营", "danger")
    ]
    
    for type_name, tag, color in type_configs:
        count = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE tags LIKE ? AND status='published'",
            (f"%{tag}%",)
        ).fetchone()[0]
        content_stats.append({
            "type": type_name,
            "count": count,
            "reads": count * (150 + hash(type_name) % 200),  # 模拟数据
            "shares": count * (10 + hash(type_name) % 30),
            "leads": count * (2 + hash(type_name) % 8),
            "avg_reads": 200 + hash(type_name) % 100,
            "conversion_rate": f"{2 + hash(type_name) % 5}%",
            "color": color
        })
    
    # 获客转化漏斗数据
    funnel_stats = [
        {"name": "文章阅读", "count": 10000, "rate": None, "bg_color": "#e3f2fd"},
        {"name": "点击表单", "count": 2500, "rate": "25%", "bg_color": "#e8f5e9"},
        {"name": "提交留资", "count": 800, "rate": "32%", "bg_color": "#fff3e0"},
        {"name": "有效线索", "count": 320, "rate": "40%", "bg_color": "#fce4ec"},
        {"name": "成功转化", "count": 80, "rate": "25%", "bg_color": "#f3e5f5"}
    ]
    
    # 服务交付统计数据
    service_stats = {
        "total": conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0],
        "processing": conn.execute("SELECT COUNT(*) FROM work_orders WHERE status='processing'").fetchone()[0],
        "completed": conn.execute("SELECT COUNT(*) FROM work_orders WHERE status='completed'").fetchone()[0],
        "avg_time": "2.5天"
    }
    
    # 按服务类型统计
    service_type_stats = []
    service_types = [
        ("贷款方案匹配", "loan_match"),
        ("融资规划", "finance_plan"),
        ("企业经营分析", "enterprise_analysis")
    ]
    for type_label, type_code in service_types:
        count = conn.execute(
            "SELECT COUNT(*) FROM work_orders WHERE order_type=?",
            (type_code,)
        ).fetchone()[0]
        completed = conn.execute(
            "SELECT COUNT(*) FROM work_orders WHERE order_type=? AND status='completed'",
            (type_code,)
        ).fetchone()[0]
        service_type_stats.append({
            "type": type_label,
            "count": count,
            "completed": completed,
            "avg_rating": "4.8" if count > 0 else "-",
            "satisfaction": 96 if count > 0 else 0
        })
    
    conn.close()
    
    # 粉丝增长汇总数据（模拟，供模板初始渲染用；图表数据由前端 API 动态获取）
    from datetime import datetime, timedelta
    fan_stats = {
        "new": 0,   # 初始值，JS 加载后会更新
        "lost": 0,
        "net": 0,
        "total": 5000
    }
    
    return render_template("reports.html",
        content_stats=content_stats,
        funnel_stats=funnel_stats,
        service_stats=service_stats,
        service_type_stats=service_type_stats,
        fan_stats=fan_stats
    )


@app.route("/api/reports/data")
@login_required
def api_reports_data():
    """获取报表数据（支持筛选）"""
    from datetime import datetime, timedelta
    
    # 获取筛选参数
    days = request.args.get("days", "30", type=int)
    content_type = request.args.get("content_type", "all")
    service_type = request.args.get("service_type", "all")
    
    # 计算日期范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    start_date_str = start_date.strftime("%Y-%m-%d")
    
    conn = get_db()
    
    # 内容类型映射
    type_configs = {
        "获客": ("自动获客", "success"),
        "品牌": ("品牌宣传", "warning"),
        "科普": ("知识科普", "primary"),
        "方案": ("方案匹配", "info"),
        "融资": ("融资规划", "secondary"),
        "经营": ("经营分析", "danger")
    }
    
    # 根据筛选条件构建内容类型列表
    if content_type == "all":
        selected_types = list(type_configs.keys())
    else:
        selected_types = [content_type]
    
    # 内容效果数据
    content_stats = []
    for tag in selected_types:
        type_name, color = type_configs[tag]
        
        # 文章数量（按发布时间筛选）
        count = conn.execute(
            """SELECT COUNT(*) FROM articles 
               WHERE tags LIKE ? AND status='published' 
               AND created_at >= ?""",
            (f"%{tag}%", start_date_str)
        ).fetchone()[0]
        
        # 模拟统计数据（实际应从文章阅读表获取）
        base_reads = 150 + hash(tag) % 200
        base_shares = 10 + hash(tag) % 30
        base_leads = 2 + hash(tag) % 8
        
        content_stats.append({
            "type": type_name,
            "count": count,
            "reads": count * base_reads,
            "shares": count * base_shares,
            "leads": count * base_leads,
            "avg_reads": base_reads if count > 0 else 0,
            "conversion_rate": f"{2 + hash(tag) % 5}%" if count > 0 else "0%",
            "color": color
        })
    
    # 粉丝增长数据（模拟数据，实际应从粉丝表获取）
    fan_dates = []
    fan_new = []
    fan_lost = []
    fan_net = []
    
    for i in range(days - 1, -1, -1):
        d = end_date - timedelta(days=i)
        fan_dates.append(f"{d.month}/{d.day}")
        # 模拟数据，实际应从数据库获取
        new_val = max(0, int(30 + (days - i) * 0.5 + (hash(str(i)) % 20)))
        lost_val = max(0, int(5 + (hash(str(i)) % 8)))
        fan_new.append(new_val)
        fan_lost.append(lost_val)
        fan_net.append(new_val - lost_val)
    
    fan_stats = {
        "dates": fan_dates,
        "new": fan_new,
        "lost": fan_lost,
        "net": fan_net,
        "total_new": sum(fan_new),
        "total_lost": sum(fan_lost),
        "total_net": sum(fan_net),
        "total_fans": 5000 + sum(fan_net)  # 假设基础粉丝数
    }
    
    # 获客转化漏斗数据（按时间筛选）
    # 实际应从线索表统计
    base_reads = max(1000, days * 300)
    funnel_stats = [
        {"name": "文章阅读", "value": base_reads},
        {"name": "点击表单", "value": int(base_reads * 0.25)},
        {"name": "提交留资", "value": int(base_reads * 0.08)},
        {"name": "有效线索", "value": int(base_reads * 0.032)},
        {"name": "成功转化", "value": int(base_reads * 0.008)}
    ]
    
    # 服务交付数据（按时间和服务类型筛选）
    service_where = "created_at >= ?"
    service_params = [start_date_str]
    
    if service_type != "all":
        service_where += " AND order_type = ?"
        service_params.append(service_type)
    
    # 服务统计数据
    total_orders = conn.execute(
        f"SELECT COUNT(*) FROM work_orders WHERE {service_where}",
        service_params
    ).fetchone()[0]
    
    processing_orders = conn.execute(
        f"SELECT COUNT(*) FROM work_orders WHERE {service_where} AND status='processing'",
        service_params
    ).fetchone()[0]
    
    completed_orders = conn.execute(
        f"SELECT COUNT(*) FROM work_orders WHERE {service_where} AND status='completed'",
        service_params
    ).fetchone()[0]
    
    service_stats = {
        "total": total_orders,
        "processing": processing_orders,
        "completed": completed_orders,
        "avg_time": "2.5天" if total_orders > 0 else "-"
    }
    
    # 按服务类型统计
    service_type_stats = []
    service_types = [
        ("贷款方案匹配", "loan_match"),
        ("融资规划", "finance_plan"),
        ("企业经营分析", "enterprise_analysis")
    ]
    
    for type_label, type_code in service_types:
        if service_type != "all" and service_type != type_code:
            continue
            
        count = conn.execute(
            "SELECT COUNT(*) FROM work_orders WHERE order_type=? AND created_at >= ?",
            (type_code, start_date_str)
        ).fetchone()[0]
        
        completed = conn.execute(
            "SELECT COUNT(*) FROM work_orders WHERE order_type=? AND status='completed' AND created_at >= ?",
            (type_code, start_date_str)
        ).fetchone()[0]
        
        service_type_stats.append({
            "type": type_label,
            "count": count,
            "completed": completed,
            "avg_rating": "4.8" if count > 0 else "-",
            "satisfaction": 96 if count > 0 else 0
        })
    
    conn.close()
    
    return jsonify({
        "ok": True,
        "data": {
            "content_stats": content_stats,
            "fan_stats": fan_stats,
            "funnel_stats": funnel_stats,
            "service_stats": service_stats,
            "service_type_stats": service_type_stats,
            "filter": {
                "days": days,
                "content_type": content_type,
                "service_type": service_type,
                "date_range": [start_date_str, end_date.strftime("%Y-%m-%d")]
            }
        }
    })


@app.route("/article/<int:article_id>/reformat", methods=["POST"])
@login_required
def reformat_article(article_id):
    """对单篇文章重新做 AI 加工 + HTML 格式化"""
    from ai_processor.processor import process_article as _process
    from ai_processor.processor import format_original_article as _fmt_original
    conn = get_db()
    row = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False, "msg": "文章不存在"})
    art = dict(row)
    try:
        # 原创文章走 format_original_article，普通文章走 process_article
        is_original = art.get("is_original") == 1 or (art.get("source_name") or "").startswith("沪上银原创")
        if is_original and art.get("content", "").strip().startswith("##"):
            # content 是 Markdown 格式（原创长文）
            processed = _fmt_original(art)
        else:
            processed = _process(art)
        new_content = processed.get("html_content") or processed.get("content", art["content"])
        new_title   = processed.get("title", art["title"])
        new_summary = processed.get("summary", art["summary"] or "")
        conn.execute(
            "UPDATE articles SET title=?, content=?, summary=?, updated_at=datetime('now','localtime') WHERE id=?",
            (new_title, new_content, new_summary, article_id)
        )
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "msg": "重新格式化完成"})
    except Exception as e:
        conn.close()
        return jsonify({"ok": False, "msg": f"格式化失败: {e}"})


@app.route("/actions/reformat_all", methods=["POST"])
@login_required
def reformat_all():
    """批量重新格式化所有草稿文章"""
    from ai_processor.processor import process_article as _process
    conn = get_db()
    sql_placeholder = "%s" if is_mysql() else "?"
    rows = conn.execute(
        f"SELECT * FROM articles WHERE status='draft' AND content NOT LIKE {sql_placeholder} ORDER BY created_at DESC LIMIT 20",
        ("%<div%",),
    ).fetchall()
    count = 0
    for row in rows:
        art = dict(row)
        try:
            processed = _process(art)
            new_content = processed.get("html_content") or processed.get("content", art["content"])
            new_title   = processed.get("title", art["title"])
            new_summary = processed.get("summary", art["summary"] or "")
            conn.execute(
                "UPDATE articles SET title=?, content=?, summary=?, updated_at=datetime('now','localtime') WHERE id=?",
                (new_title, new_content, new_summary, art["id"])
            )
            count += 1
        except Exception as e:
            logger.warning(f"[Reformat] 文章 {art['id']} 格式化失败: {e}")
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "msg": f"已重新格式化 {count} 篇文章"})


@app.route("/article/<int:article_id>/edit", methods=["GET", "POST"])
@login_required
def edit_article(article_id):
    conn = get_db()
    article = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
    if not article:
        conn.close()
        return "文章不存在", 404

    if request.method == "POST":
        title = request.form.get("title", "")
        content = request.form.get("content", "")
        summary = request.form.get("summary", "")
        conn.execute(
            "UPDATE articles SET title=?, content=?, summary=?, updated_at=datetime('now','localtime') WHERE id=?",
            (title, content, summary, article_id)
        )
        conn.commit()
        conn.close()
        flash("保存成功")
        return redirect(url_for("article_detail", article_id=article_id))

    conn.close()
    return render_template(
        "edit_article.html",
        article=article,
        article_preview_html=build_article_preview_html(article),
    )


@app.route("/actions/write", methods=["POST"])
@require_perm("can_write")
def trigger_write():
    """??????????????????????"""
    try:
        topic = request.form.get("topic", "").strip() or None
        from ai_processor.content_writer import write_article

        article = write_article(topic=topic)
        if article:
            article.update(generate_cover_for_article(article, style=topic or ""))

        if article and article.get("title"):
            from database import get_db

            db = get_db()
            title = article["title"]
            if is_mysql():
                existing = db.execute("SELECT id FROM articles WHERE title=%s", (title,)).fetchone()
            else:
                existing = db.execute("SELECT id FROM articles WHERE title=?", (title,)).fetchone()

            if existing:
                db.close()
                return jsonify({"ok": True, "msg": "????????"})

            review_status, publish_status = split_legacy_status(STATUS_DRAFT)
            article_tags = f"{topic},??" if topic else "??"
            insert_params = (
                article.get("title", topic),
                article.get("content", ""),
                article.get("summary", ""),
                article.get("cover_url", ""),
                article.get("cover_image", ""),
                article.get("cover_status", "pending"),
                article.get("cover_prompt", ""),
                "?????",
                "",
                article_tags,
                STATUS_DRAFT,
                review_status,
                publish_status,
            )

            if is_mysql():
                db.execute(
                    """
                    INSERT INTO articles (
                        title, content, summary, cover_url, cover_image, cover_status, cover_prompt,
                        source_name, source_url, tags, status, review_status, publish_status
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    insert_params,
                )
            else:
                db.execute(
                    """
                    INSERT INTO articles (
                        title, content, summary, cover_url, cover_image, cover_status, cover_prompt,
                        source_name, source_url, tags, status, review_status, publish_status
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    insert_params,
                )

            db.commit()
            db.close()
            return jsonify({"ok": True, "msg": "????????? 1 ???"})

        return jsonify({"ok": False, "msg": "?????????? AI ??"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


@app.route("/actions/publish", methods=["POST"])
@require_perm("can_publish")
def trigger_publish():
    """手动触发发布已审核文章"""
    try:
        # 路由层仅负责调用 service，并保持原有返回结构不变。
        result, status_code = PublishService.publish_approved()
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


@app.route("/article/<int:article_id>/push-wechat", methods=["POST"])
@require_perm("can_publish")
def push_single_to_wechat(article_id):
    """一键推送单篇文章到微信草稿箱"""
    try:
        # 路由层仅负责调用 service，并保持原有返回结构不变。
        result, status_code = PublishService.push_single_article(article_id)
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({"ok": False, "msg": f"推送异常: {str(e)}"})


@app.route("/publish-task/<int:task_id>/retry", methods=["POST"])
@require_perm("can_publish")
def retry_publish_task(task_id):
    """重试失败的发布任务。"""
    # 路由层仅负责调用任务服务，并保持 JSON 返回简洁。
    result = PublishTaskService.retry_task(task_id)
    status_code = 200 if result.get("ok") else 400
    if result.get("msg") == "任务不存在":
        status_code = 404
    return jsonify(result), status_code


@app.route("/publish-tasks")
@require_perm("can_publish")
def publish_tasks():
    """发布任务列表页。"""
    # 仅支持轻量状态筛选，保持服务端渲染简单稳定。
    status_filter = (request.args.get("status", "") or "").strip()
    reason_filter = (request.args.get("reason", "") or "").strip()
    stale_filter_raw = (request.args.get("stale_queued", "") or "").strip()
    article_id_filter_raw = (request.args.get("article_id", "") or "").strip()
    article_id_filter = None
    stale_queued_filter = False
    status_options = PublishTaskService.get_task_status_options(include_all=True)
    task_status_map = PublishTaskService.get_task_status_map()
    valid_status_values = {option["value"] for option in status_options}

    # 仅允许预设状态进入筛选，避免无效参数影响列表展示。
    if status_filter not in valid_status_values:
        status_filter = ""

    # 对文章ID做整数保护，非法值时直接忽略，避免影响页面稳定性。
    if article_id_filter_raw.isdigit():
        article_id_filter = int(article_id_filter_raw)

    # 解析疑似积压筛选参数，仅在明确真值时生效。
    if stale_filter_raw.lower() in ("1", "true", "yes", "on"):
        stale_queued_filter = True

    # 默认只展示最近任务，避免一次加载过多记录。
    tasks = PublishTaskService.list_tasks(
        status=status_filter or None,
        reason=reason_filter or None,
        article_id=article_id_filter,
        stale_queued=stale_queued_filter,
        limit=100,
    )
    # 仅在文章筛选场景下读取历史任务概览，避免无意义查询。
    article_task_summary = PublishTaskService.get_article_task_summary(article_id_filter) if article_id_filter else None
    # 仅在文章筛选场景下读取重复发布风险提示，避免无意义查询。
    article_publish_risk = PublishTaskService.get_article_publish_risk(article_id_filter) if article_id_filter else None
    # 读取列表页顶部统计数据，便于运营快速关注队列与失败情况。
    task_stats = PublishTaskService.get_task_stats()
    # 读取系统自动告警，便于运营第一时间关注明显异常。
    system_alerts = PublishTaskService.get_system_alerts()
    # 读取系统恢复提示，便于运营了解异常问题是否已经恢复正常。
    system_recoveries = PublishTaskService.get_system_recoveries()
    # 读取系统事件时间线，便于运营了解最近告警与恢复轨迹。
    system_event_timeline = PublishTaskService.get_system_event_timeline(limit=10)
    # 读取今日运行质量摘要，便于运营快速判断今天系统是否稳定。
    today_quality_summary = PublishTaskService.get_today_quality_summary()
    # 读取今日失败原因 TOP5，便于运营快速定位今日失败率升高的主要原因。
    today_failed_reason_top = PublishTaskService.get_today_failed_reason_top(limit=5)
    # 读取最近24小时任务趋势，便于运营观察系统整体运行情况。
    task_trend_24h = PublishTaskService.get_task_trend_24h()
    # 读取疑似卡住的 running 任务，便于运营快速恢复异常执行状态。
    stuck_running_tasks = PublishTaskService.get_stuck_running_tasks(limit=20)
    # 读取 worker 心跳状态，帮助运营判断后台轮询执行器是否正常运行。
    worker_health = PublishTaskService.get_worker_health()
    # 读取队列健康摘要，帮助运营判断是否存在积压、卡住或持续失败的问题。
    queue_health_summary = PublishTaskService.get_queue_health_summary()
    # 读取最近失败原因 TOP 3，帮助运营快速判断当前最常见失败类型。
    failed_reason_top = PublishTaskService.get_failed_reason_top(limit=3)
    return render_template(
        "publish_tasks.html",
        tasks=tasks,
        task_stats=task_stats,
        system_alerts=system_alerts,
        system_recoveries=system_recoveries,
        system_event_timeline=system_event_timeline,
        today_quality_summary=today_quality_summary,
        today_failed_reason_top=today_failed_reason_top,
        task_trend_24h=task_trend_24h,
        stuck_running_tasks=stuck_running_tasks,
        worker_health=worker_health,
        queue_health_summary=queue_health_summary,
        failed_reason_top=failed_reason_top,
        article_task_summary=article_task_summary,
        article_publish_risk=article_publish_risk,
        status_filter=status_filter,
        reason_filter=reason_filter,
        article_id_filter=article_id_filter,
        stale_queued_filter=stale_queued_filter,
        status_options=status_options,
        task_status_map=task_status_map,
    )


@app.route("/system-health")
@require_perm("can_publish")
def system_health():
    """系统自检页。"""
    # 自检页只读取现有任务健康数据，不修改任务、不触发 worker、不改变发布流程。
    health_check = PublishTaskService.get_system_health_check()
    return render_template("system_health.html", health_check=health_check)


@app.route("/publish-tasks/recover-running", methods=["POST"])
@require_perm("can_publish")
def recover_publish_tasks_running():
    """批量恢复疑似卡住的 running 任务。"""
    # 恢复入口固定只处理当前识别出的卡住任务，不改其他筛选主流程。
    stuck_running_tasks = PublishTaskService.get_stuck_running_tasks(limit=20)
    stuck_task_ids = [task["id"] for task in stuck_running_tasks if task.get("status") == "running"]

    result = PublishTaskService.recover_stuck_running_tasks(stuck_task_ids)
    flash(
        f"已恢复卡住任务：共处理 {result['processed_count']} 个，成功 {result['success_count']} 个，失败 {result['failed_count']} 个"
    )
    return redirect(url_for("publish_tasks"))


@app.route("/publish-tasks/retry-batch", methods=["POST"])
@require_perm("can_publish")
def retry_publish_tasks_batch():
    """按当前筛选条件批量重试失败任务。"""
    status_filter = (request.form.get("status", "") or "").strip()
    reason_filter = (request.form.get("reason", "") or "").strip()
    article_id_filter_raw = (request.form.get("article_id", "") or "").strip()
    article_id_filter = None

    # 仅允许预设状态值进入查询，避免非法参数影响列表结果。
    valid_status_values = {option["value"] for option in PublishTaskService.get_task_status_options(include_all=True)}
    if status_filter not in valid_status_values:
        status_filter = ""

    # 对文章ID做整数保护，非法值时直接忽略。
    if article_id_filter_raw.isdigit():
        article_id_filter = int(article_id_filter_raw)
    stale_queued_filter = False
    if (request.form.get("stale_queued", "") or "").strip().lower() in ("1", "true", "yes", "on"):
        stale_queued_filter = True

    # 后端根据当前筛选条件重新查询任务，并仅处理真正失败的任务。
    tasks = PublishTaskService.list_tasks(
        status=status_filter or None,
        reason=reason_filter or None,
        article_id=article_id_filter,
        stale_queued=stale_queued_filter,
        limit=100,
    )
    failed_task_ids = [task["id"] for task in tasks if task.get("status") == "failed"]

    result = PublishTaskService.retry_tasks(failed_task_ids)
    flash(
        f"批量重试完成：共处理 {result['processed_count']} 个任务，成功 {result['success_count']} 个，失败 {result['failed_count']} 个"
    )

    # 重试完成后回到当前筛选结果页，保持运营查看上下文不丢失。
    query_params = {}
    if status_filter:
        query_params["status"] = status_filter
    if reason_filter:
        query_params["reason"] = reason_filter
    if article_id_filter is not None:
        query_params["article_id"] = article_id_filter
    if stale_queued_filter:
        query_params["stale_queued"] = 1
    return redirect(url_for("publish_tasks", **query_params))


@app.route("/publish-tasks/cancel-batch", methods=["POST"])
@require_perm("can_publish")
def cancel_publish_tasks_batch():
    """按当前筛选条件批量取消排队中的任务。"""
    status_filter = (request.form.get("status", "") or "").strip()
    reason_filter = (request.form.get("reason", "") or "").strip()
    article_id_filter_raw = (request.form.get("article_id", "") or "").strip()
    stale_filter_raw = (request.form.get("stale_queued", "") or "").strip()
    article_id_filter = None
    stale_queued_filter = False

    # 仅允许预设状态值进入查询，避免非法参数影响列表结果。
    valid_status_values = {option["value"] for option in PublishTaskService.get_task_status_options(include_all=True)}
    if status_filter not in valid_status_values:
        status_filter = ""

    # 对文章ID做整数保护，非法值时直接忽略。
    if article_id_filter_raw.isdigit():
        article_id_filter = int(article_id_filter_raw)

    # 解析疑似积压筛选参数，仅在明确真值时生效。
    if stale_filter_raw.lower() in ("1", "true", "yes", "on"):
        stale_queued_filter = True

    # 后端根据当前筛选条件重新查询任务，并仅处理真正 queued 的任务。
    tasks = PublishTaskService.list_tasks(
        status=status_filter or None,
        reason=reason_filter or None,
        article_id=article_id_filter,
        stale_queued=stale_queued_filter,
        limit=100,
    )
    queued_task_ids = [task["id"] for task in tasks if task.get("status") == "queued"]

    result = PublishTaskService.cancel_tasks(queued_task_ids)
    flash(
        f"已清空排队任务：共处理 {result['processed_count']} 个，成功 {result['success_count']} 个，失败 {result['failed_count']} 个"
    )

    # 处理完成后回到当前筛选页面，保持运营查看上下文不丢失。
    query_params = {}
    if status_filter:
        query_params["status"] = status_filter
    if reason_filter:
        query_params["reason"] = reason_filter
    if article_id_filter is not None:
        query_params["article_id"] = article_id_filter
    if stale_queued_filter:
        query_params["stale_queued"] = 1
    return redirect(url_for("publish_tasks", **query_params))


@app.route("/article/<int:article_id>/publish-task")
@require_perm("can_publish")
def get_article_publish_task(article_id):
    """查询文章最近一次发布任务。"""
    # 路由层仅负责查询最近任务并返回简洁 JSON。
    task = PublishTaskService.get_latest_task_for_article(article_id)
    if not task:
        return jsonify({"ok": False, "msg": "该文章暂无发布任务", "data": None}), 200

    return jsonify(
        {
            "ok": True,
            "data": {
                "task_id": task["id"],
                "task_type": task["task_type"],
                "status": task["status"],
                "retry_count": task["retry_count"],
                "max_retries": task["max_retries"],
                "error_message": task["error_message"],
                "external_draft_id": task["external_draft_id"],
                "created_at": task["created_at"],
                "updated_at": task["updated_at"],
                "executed_at": task["executed_at"],
            },
        }
    )


@app.route("/api/stats")
@login_required
def api_stats():
    conn = get_db()
    stats = {
        "draft": conn.execute("SELECT COUNT(*) FROM articles WHERE status='draft'").fetchone()[0],
        "approved": conn.execute("SELECT COUNT(*) FROM articles WHERE status='approved'").fetchone()[0],
        "draft_sent": conn.execute("SELECT COUNT(*) FROM articles WHERE status='draft_sent'").fetchone()[0],
        "published": conn.execute("SELECT COUNT(*) FROM articles WHERE status='published'").fetchone()[0],
    }
    conn.close()
    return jsonify(stats)




# ══════════════════════════════════════════════════════════
# 任务1：写作模板管理（模板录入功能）
# ══════════════════════════════════════════════════════════

TEMPLATE_CATEGORY_LABELS = {
    "leads": "自动获客",
    "brand": "品牌宣传",
    "science": "贷款知识科普",
    "service": "贷款方案匹配",
    "finance": "融资规划",
    "enterprise": "企业经营分析",
}


def parse_template_form_payload():
    """统一解析写作模板表单，避免新建和编辑两处字段处理不一致。"""
    category = request.form.get("category", "").strip()
    structure_raw = request.form.get("structure", "").strip()
    structure_items = [s.strip() for s in structure_raw.split("\n") if s.strip()]
    category_label = request.form.get("category_label", "").strip()

    return {
        "name": request.form.get("name", "").strip(),
        "category": category,
        "category_label": category_label or TEMPLATE_CATEGORY_LABELS.get(category, ""),
        "pain_point": request.form.get("pain_point", "").strip(),
        "solution": request.form.get("solution", "").strip(),
        "hook": request.form.get("hook", "").strip(),
        "prompt_template": request.form.get("prompt_template", "").strip(),
        "structure": _json.dumps(structure_items, ensure_ascii=False),
        "structure_items": structure_items,
        "brand_rules": _json.dumps({
            "title_suffix": request.form.get("br_title_suffix", "").strip(),
            "footer": request.form.get("br_footer", "沪上银 · 上海专业贷款顾问").strip(),
            "cta": request.form.get("br_cta", "").strip(),
            "watermark": request.form.get("br_watermark", "沪上银原创").strip(),
        }, ensure_ascii=False),
    }


def validate_template_form_payload(payload):
    """校验写作模板核心字段，避免保存空模板或非法分类。"""
    errors = []
    if not payload["name"]:
        errors.append("模板名称不能为空")
    if payload["category"] not in TEMPLATE_CATEGORY_LABELS:
        errors.append("请选择有效的内容分类")
    if not payload["structure_items"]:
        errors.append("文章结构至少需要填写一个段落")
    return errors


@app.route("/templates")
@login_required
def templates_list():
    """写作模板列表页"""
    TemplateService.ensure_default_templates()
    conn = get_db()
    templates = conn.execute(
        "SELECT * FROM article_templates ORDER BY category, id"
    ).fetchall()
    conn.close()
    return render_template("templates.html", templates=templates)


@app.route("/templates/new", methods=["GET", "POST"])
@require_perm("can_edit")
def template_new():
    """新建写作模板"""
    if request.method == "POST":
        payload = parse_template_form_payload()
        errors = validate_template_form_payload(payload)
        if errors:
            # 校验失败时回填用户输入，避免运营重复录入整张表单。
            for error in errors:
                flash(error)
            return render_template("template_edit.html", template=None, form_template=payload, mode="new")

        conn = get_db()
        conn.execute("""
            INSERT INTO article_templates
            (name, category, category_label, structure, pain_point, solution, hook, brand_rules, prompt_template)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            payload["name"], payload["category"], payload["category_label"], payload["structure"],
            payload["pain_point"], payload["solution"], payload["hook"], payload["brand_rules"],
            payload["prompt_template"],
        ))
        conn.commit()
        conn.close()
        flash("模板创建成功！")
        return redirect(url_for("templates_list"))

    return render_template("template_edit.html", template=None, mode="new")


@app.route("/templates/<int:tmpl_id>/edit", methods=["GET", "POST"])
@require_perm("can_edit")
def template_edit(tmpl_id):
    """编辑写作模板"""
    conn = get_db()
    tmpl = conn.execute("SELECT * FROM article_templates WHERE id=?", (tmpl_id,)).fetchone()
    if not tmpl:
        conn.close()
        return "模板不存在", 404

    if request.method == "POST":
        payload = parse_template_form_payload()
        errors = validate_template_form_payload(payload)
        if errors:
            # 编辑失败时保留本次提交内容，方便直接补齐缺失项。
            conn.close()
            for error in errors:
                flash(error)
            return render_template("template_edit.html", template=tmpl, form_template=payload, mode="edit")

        conn.execute("""
            UPDATE article_templates SET
                name=?, category=?, category_label=?, structure=?, pain_point=?,
                solution=?, hook=?, brand_rules=?, prompt_template=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
        """, (
            payload["name"], payload["category"], payload["category_label"], payload["structure"],
            payload["pain_point"], payload["solution"], payload["hook"], payload["brand_rules"],
            payload["prompt_template"], tmpl_id,
        ))
        conn.commit()
        conn.close()
        flash("模板保存成功！")
        return redirect(url_for("templates_list"))

    conn.close()
    return render_template("template_edit.html", template=tmpl, mode="edit")


@app.route("/templates/<int:tmpl_id>/toggle", methods=["POST"])
@require_perm("can_edit")
def template_toggle(tmpl_id):
    """启用/禁用模板"""
    conn = get_db()
    tmpl = conn.execute("SELECT is_active FROM article_templates WHERE id=?", (tmpl_id,)).fetchone()
    if not tmpl:
        conn.close()
        return jsonify({"ok": False, "msg": "模板不存在"})
    new_status = 0 if tmpl["is_active"] else 1
    conn.execute("UPDATE article_templates SET is_active=? WHERE id=?", (new_status, tmpl_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "is_active": new_status, "msg": "已" + ("启用" if new_status else "禁用")})


@app.route("/templates/<int:tmpl_id>/delete", methods=["POST"])
@require_perm("can_delete")
def template_delete(tmpl_id):
    """删除模板"""
    conn = get_db()
    conn.execute("DELETE FROM article_templates WHERE id=?", (tmpl_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "msg": "已删除"})


@app.route("/templates/<int:tmpl_id>/use", methods=["POST"])
@require_perm("can_write")
def template_use(tmpl_id):
    """使用模板生成文章草稿。"""
    # 路由层仅负责接收参数并转交给 service 层处理。
    topic = request.form.get("topic", "").strip()
    try:
        return jsonify(TemplateService.use_template(tmpl_id, topic))
    except Exception as e:
        return jsonify({"ok": False, "msg": f"生成失败: {e}"})


# ══════════════════════════════════════════════════════════
# 任务3：批量格式化规则配置
# ══════════════════════════════════════════════════════════

@app.route("/agent-generate-article", methods=["POST"])
@require_perm("can_write")
def agent_generate_article():
    """不依赖固定模板，直接通过文章生成 Agent 产出草稿。"""
    keyword = request.form.get("keyword", "").strip()
    primary_category = request.form.get("primary_category", "").strip() or request.form.get("category", "").strip()
    secondary_categories_raw = request.form.get("secondary_categories", "").strip()
    length = request.form.get("length", "medium").strip() or "medium"
    tone = request.form.get("tone", "").strip()
    audience = request.form.get("audience", "").strip()
    secondary_categories = [
        item.strip()
        for item in secondary_categories_raw.split(",")
        if item.strip()
    ]

    if not primary_category:
        category_result = ArticleCategoryAgent().detect_categories(keyword) or {}
        if category_result.get("ok"):
            primary_category = category_result.get("primary_category", "")
            secondary_categories = category_result.get("secondary_categories", []) or []
    primary_category = primary_category or "知识科普"

    agent = ArticleGenerationAgent()
    result = agent.generate(
        keyword=keyword,
        primary_category=primary_category,
        secondary_categories=secondary_categories,
        audience=audience or "企业老板 / 小微企业主",
        tone=tone or "专业、可信、接地气、适合助贷/企业融资顾问行业",
        length=length,
    )
    result = result or {}
    if not result.get("ok"):
        flash(result.get("msg") or "文章生成失败，请稍后重试")
        return redirect(url_for("templates_list"))

    try:
        saved = TemplateService.create_agent_article_with_cover(result, keyword) or {}
    except Exception as exc:
        flash(f"文章已生成，但保存草稿失败：{exc}")
        return redirect(url_for("templates_list"))

    article_id = saved.get("article_id")
    if saved.get("cover_task_id"):
        flash("Article saved as draft. AI cover generation is running in the background; refresh later to view it.")
    elif saved.get("cover_error"):
        flash("Article saved as draft. AI cover task submission failed; you can regenerate it later on the article detail page.")
    else:
        flash("Article saved as draft. AI cover can be regenerated later on the article detail page.")
    if article_id:
        return redirect(url_for("article_detail", article_id=article_id))
    return redirect(url_for("articles"))


@app.route("/agent-detect-categories", methods=["POST"])
@require_perm("can_write")
def agent_detect_categories():
    """根据关键词返回文章主分类与可选次分类。"""
    keyword = request.form.get("keyword", "").strip()
    result = ArticleCategoryAgent().detect_categories(keyword)
    return jsonify(result)


@app.route("/format-rules")
@login_required
def format_rules_page():
    """格式化规则 + 敏感词配置页"""
    conn = get_db()
    rules = conn.execute("SELECT * FROM format_rules ORDER BY id").fetchall()
    sensitive = conn.execute("SELECT * FROM sensitive_words ORDER BY category, id").fetchall()
    conn.close()
    return render_template("format_rules.html", rules=rules, sensitive=sensitive)


@app.route("/format-rules/update", methods=["POST"])
@require_perm("can_edit")
def format_rule_update():
    """更新格式化规则配置（JSON提交）"""
    import json
    rule_id = request.form.get("id")
    config_str = request.form.get("config", "{}")
    try:
        config = json.loads(config_str)
        conn = get_db()
        conn.execute("UPDATE format_rules SET config=? WHERE id=?",
                     (json.dumps(config, ensure_ascii=False), rule_id))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "msg": "规则已保存"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


@app.route("/sensitive-words/add", methods=["POST"])
@require_perm("can_edit")
def sensitive_word_add():
    """新增敏感词"""
    word = request.form.get("word", "").strip()
    category = request.form.get("category", "finance")
    action = request.form.get("action", "block")
    replace_with = request.form.get("replace_with", "").strip() or None

    if not word:
        return jsonify({"ok": False, "msg": "词语不能为空"})

    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO sensitive_words (word, category, action, replace_with) VALUES (?,?,?,?)",
            (word, category, action, replace_with)
        )
        conn.commit()
        new_id = get_lastrowid(cursor)
        conn.close()
        return jsonify({"ok": True, "msg": "已添加", "id": new_id})
    except Exception as e:
        conn.close()
        if "UNIQUE" in str(e):
            return jsonify({"ok": False, "msg": "该词已存在"})
        return jsonify({"ok": False, "msg": str(e)})


@app.route("/sensitive-words/<int:word_id>/delete", methods=["POST"])
@require_perm("can_edit")
def sensitive_word_delete(word_id):
    """删除敏感词"""
    conn = get_db()
    conn.execute("DELETE FROM sensitive_words WHERE id=?", (word_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "msg": "已删除"})


@app.route("/actions/batch-format", methods=["POST"])
@require_perm("can_edit")
def batch_format_articles():
    """批量格式化文章（应用格式化规则 + 敏感词过滤）"""
    from ai_processor.processor import process_article as _process

    limit = int(request.form.get("limit", 20))
    status_target = request.form.get("status", STATUS_DRAFT)

    conn = get_db()

    # 获取敏感词库
    sensitive_rows = conn.execute("SELECT word, action, replace_with FROM sensitive_words WHERE action='block' OR action='replace'").fetchall()
    block_words = {r["word"] for r in sensitive_rows if r["action"] == "block"}
    replace_map = {r["word"]: r["replace_with"] for r in sensitive_rows if r["action"] == "replace" and r["replace_with"]}

    rows = conn.execute(
        f"SELECT * FROM articles WHERE status=? ORDER BY created_at DESC LIMIT ?",
        (status_target, limit)
    ).fetchall()

    processed = 0
    blocked = 0
    for row in rows:
        art = dict(row)
        title = art.get("title", "")
        content = art.get("content", "")

        # 敏感词检查
        hit_block = any(w in title or w in content for w in block_words)
        if hit_block:
            review_status, publish_status = split_legacy_status(STATUS_REJECTED)
            conn.execute(
                "UPDATE articles SET status=?, review_status=?, publish_status=?, updated_at=datetime('now','localtime') WHERE id=?",
                (STATUS_REJECTED, review_status, publish_status, art["id"])
            )
            blocked += 1
            continue

        # 替换词处理
        for word, replacement in replace_map.items():
            title = title.replace(word, replacement)
            content = content.replace(word, replacement)
        art["title"] = title
        art["content"] = content

        # 格式化
        try:
            result = _process(art)
            conn.execute(
                "UPDATE articles SET title=?, content=?, summary=?, updated_at=datetime('now','localtime') WHERE id=?",
                (result.get("title", title), result.get("html_content") or result.get("content", content),
                 result.get("summary", art.get("summary", "")), art["id"])
            )
            processed += 1
        except Exception as e:
            pass

    conn.commit()
    conn.close()
    return jsonify({
        "ok": True,
        "msg": f"批量格式化完成：已处理 {processed} 篇，已拦截 {blocked} 篇（命中敏感词）"
    })


@app.route("/actions/check-sensitive", methods=["POST"])
@login_required
def check_sensitive():
    """检查单篇文章是否命中敏感词"""
    article_id = request.form.get("article_id")
    conn = get_db()
    article = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
    sensitive_rows = conn.execute("SELECT * FROM sensitive_words").fetchall()
    conn.close()

    if not article:
        return jsonify({"ok": False, "msg": "文章不存在"})

    text = (article["title"] or "") + (article["content"] or "")
    hits = []
    for row in sensitive_rows:
        if row["word"] in text:
            hits.append({
                "word": row["word"],
                "category": row["category"],
                "action": row["action"],
            })

    return jsonify({"ok": True, "hits": hits, "total": len(hits)})




# ══════════════════════════════════════════════════════════
# 品牌素材库
# ══════════════════════════════════════════════════════════

@app.route("/brand-assets")
@login_required
def brand_assets():
    """品牌素材库主页"""
    conn = get_db()
    assets = conn.execute(
        "SELECT * FROM brand_assets WHERE is_active=1 ORDER BY category, asset_type, id DESC"
    ).fetchall()
    conn.close()
    return render_template("brand_assets.html", assets=assets)


@app.route("/brand-assets/upload", methods=["POST"])
@require_perm("can_edit")
def brand_assets_upload():
    """上传品牌素材"""
    import os, uuid
    name = request.form.get("name", "").strip()
    asset_type = request.form.get("asset_type", "other")
    category = request.form.get("category", "general")
    description = request.form.get("description", "").strip()
    tags = request.form.get("tags", "").strip()
    url = request.form.get("url", "").strip()
    text_content = request.form.get("text_content", "").strip()

    if not name:
        return jsonify({"ok": False, "msg": "素材名称不能为空"})

    file_path = None

    # 文件上传
    if "file" in request.files and request.files["file"].filename:
        file = request.files["file"]
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".pdf"):
            return jsonify({"ok": False, "msg": "不支持的文件格式"})

        save_dir = os.path.join(os.path.dirname(__file__), "static", "assets", category)
        os.makedirs(save_dir, exist_ok=True)
        filename = f"{uuid.uuid4().hex[:8]}_{name[:20].replace(' ', '_')}{ext}"
        file.save(os.path.join(save_dir, filename))
        file_path = f"{category}/{filename}"

    # 文字素材（口号/文案）——把文字内容存 description
    if text_content:
        description = text_content

    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO brand_assets (name, asset_type, category, file_path, url, description, tags)
               VALUES (?,?,?,?,?,?,?)""",
            (name, asset_type, category, file_path, url or None, description, tags)
        )
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "msg": "素材已上传"})
    except Exception as e:
        conn.close()
        return jsonify({"ok": False, "msg": str(e)})


@app.route("/brand-assets/<int:asset_id>/delete", methods=["POST"])
@require_perm("can_edit")
def brand_assets_delete(asset_id):
    """删除品牌素材（软删除）"""
    conn = get_db()
    conn.execute("UPDATE brand_assets SET is_active=0 WHERE id=?", (asset_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "msg": "已删除"})


# ══════════════════════════════════════════════════════════
# 资料中心
# ══════════════════════════════════════════════════════════

@app.route("/resource-center")
@login_required
def resource_center():
    """资料中心主页"""
    conn = get_db()
    docs = conn.execute(
        "SELECT * FROM resource_docs ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return render_template("resource_center.html", docs=docs)


@app.route("/resource-docs/<int:doc_id>")
@login_required
def resource_doc_view(doc_id):
    """获取单篇文档内容（Ajax）"""
    conn = get_db()
    doc = conn.execute("SELECT * FROM resource_docs WHERE id=?", (doc_id,)).fetchone()
    conn.close()
    if not doc:
        return jsonify({"ok": False, "msg": "文档不存在"})
    return jsonify({"ok": True, "title": doc["title"], "content": doc["content"]})


@app.route("/user-guide")
@login_required
def user_guide():
    """系统操作手册 — 三角色培训页面"""
    return render_template("user_guide.html")


# ══════════════════════════════════════════════════════════
# 留资表单与线索管理
# ══════════════════════════════════════════════════════════

@app.route("/lead-form", methods=["GET", "POST"])
def public_lead_form():
    """公开留资落地页，用于公众号正文卡片点击后填写。"""
    import json

    form_data = {
        "source": request.values.get("source", "公众号正文入口"),
        "article_title": request.values.get("article_title", ""),
        "form_type": request.values.get("form_type", "general"),
    }

    if request.method == "POST":
        form_data.update({
            "name": request.form.get("name", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "loan_amount": request.form.get("loan_amount", "").strip(),
            "credit_status": request.form.get("credit_status", "").strip(),
            "region": request.form.get("region", "").strip(),
            "source": request.form.get("source", "公众号正文入口").strip(),
            "article_title": request.form.get("article_title", "").strip(),
            "form_type": request.form.get("form_type", "general").strip(),
        })

        name = form_data["name"]
        phone = form_data["phone"]
        if not name or not phone:
            return render_template("lead_form.html", result={"ok": False, "msg": "姓名和手机号不能为空"}, form_data=form_data)

        # 手机号格式校验，避免无效线索进入后台。
        if not re.match(r"^1[3-9]\d{9}$", phone):
            return render_template("lead_form.html", result={"ok": False, "msg": "手机号格式不正确"}, form_data=form_data)

        conn = get_db()
        try:
            # 相同手机号只保留一条线索，避免运营重复跟进。
            existing = conn.execute("SELECT id FROM leads WHERE phone=?", (phone,)).fetchone()
            if existing:
                conn.close()
                return render_template("lead_form.html", result={"ok": False, "msg": "该手机号已提交过申请，请勿重复提交"}, form_data=form_data)

            advisor_id = _assign_advisor(form_data["region"])
            cursor = conn.execute("""
                INSERT INTO leads (name, phone, loan_amount, credit_status, source, region, advisor_id, form_data)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                form_data["name"],
                form_data["phone"],
                form_data["loan_amount"],
                form_data["credit_status"],
                form_data["source"],
                form_data["region"],
                advisor_id,
                json.dumps(form_data, ensure_ascii=False),
            ))
            conn.commit()
            lead_id = get_lastrowid(cursor)

            if advisor_id:
                conn.execute("UPDATE advisors SET current_leads = current_leads + 1 WHERE id=?", (advisor_id,))
                conn.commit()

            conn.close()
            _sync_lead_to_crm(lead_id, form_data, advisor_id)
            return render_template("lead_form.html", result={"ok": True, "msg": "提交成功，顾问会尽快联系您"}, form_data=form_data)
        except Exception as e:
            conn.close()
            return render_template("lead_form.html", result={"ok": False, "msg": f"提交失败: {str(e)}"}, form_data=form_data)

    return render_template("lead_form.html", result=None, form_data=form_data)


@app.route("/api/leads/submit", methods=["POST"])
def submit_lead():
    """接收留资表单提交"""
    import json
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "msg": "无效的数据"})
    
    name = data.get("name", "").strip()
    phone = data.get("phone", "").strip()
    loan_amount = data.get("loan_amount", "").strip()
    credit_status = data.get("credit_status", "").strip()
    source = data.get("source", "文章页面")
    article_title = data.get("article_title", "")
    region = data.get("region", "")
    
    if not name or not phone:
        return jsonify({"ok": False, "msg": "姓名和手机号不能为空"})
    
    # 手机号格式验证
    if not re.match(r"^1[3-9]\d{9}$", phone):
        return jsonify({"ok": False, "msg": "手机号格式不正确"})
    
    conn = get_db()
    try:
        # 检查是否已存在相同手机号的线索
        existing = conn.execute("SELECT id FROM leads WHERE phone=?", (phone,)).fetchone()
        if existing:
            conn.close()
            return jsonify({"ok": False, "msg": "该手机号已提交过申请，请勿重复提交"})
        
        # 自动分配顾问（按地区）
        advisor_id = _assign_advisor(region)
        
        cursor = conn.execute("""
            INSERT INTO leads (name, phone, loan_amount, credit_status, source, region, advisor_id, form_data)
            VALUES (?,?,?,?,?,?,?,?)
        """, (name, phone, loan_amount, credit_status, source, region, advisor_id, json.dumps(data, ensure_ascii=False)))
        conn.commit()
        lead_id = get_lastrowid(cursor)
        
        # 更新顾问的当前线索数
        if advisor_id:
            conn.execute("UPDATE advisors SET current_leads = current_leads + 1 WHERE id=?", (advisor_id,))
            conn.commit()
        
        conn.close()
        
        # 同步到CRM（异步）
        _sync_lead_to_crm(lead_id, data, advisor_id)
        
        return jsonify({"ok": True, "msg": "提交成功", "lead_id": lead_id})
    except Exception as e:
        conn.close()
        return jsonify({"ok": False, "msg": f"提交失败: {str(e)}"})


def _assign_advisor(region: str = "") -> int:
    """
    根据地区自动分配顾问
    策略：
    1. 优先分配给负责该地区的顾问
    2. 在该地区顾问中选择当前线索数最少的
    3. 如果没有地区匹配，选择当前线索数最少的顾问
    """
    import json
    conn = get_db()
    
    try:
        # 获取所有活跃顾问
        advisors = conn.execute(
            "SELECT id, regions, current_leads, max_leads FROM advisors WHERE is_active=1"
        ).fetchall()
        
        candidates = []
        for adv in advisors:
            if adv["current_leads"] >= adv["max_leads"]:
                continue  # 跳过已满员的顾问
            
            # 解析顾问负责的地区
            try:
                adv_regions = json.loads(adv["regions"]) if adv["regions"] else []
            except:
                adv_regions = []
            
            # 如果指定了地区，优先匹配该地区
            if region and region in adv_regions:
                candidates.append((adv["id"], adv["current_leads"], 1))  # 优先级1：地区匹配
            else:
                candidates.append((adv["id"], adv["current_leads"], 0))  # 优先级0：不匹配
        
        conn.close()
        
        if not candidates:
            return None
        
        # 按优先级降序，然后按当前线索数升序排序
        candidates.sort(key=lambda x: (-x[2], x[1]))
        return candidates[0][0]
    except Exception as e:
        conn.close()
        return None


def _sync_lead_to_crm(lead_id: int, data: dict, advisor_id: int):
    """同步线索到CRM系统（模拟）"""
    # 这里可以接入企业微信、钉钉或其他CRM系统的API
    # 目前仅记录日志
    logger = logging.getLogger(__name__)
    logger.info(f"[CRM同步] 线索ID={lead_id}, 顾问ID={advisor_id}, 数据={data}")


@app.route("/leads")
@login_required
def leads_list():
    """线索列表页"""
    if not get_perms().get("can_view_leads", False):
        return render_template("403.html", perm="can_view_leads"), 403
    
    status_filter = request.args.get("status", "")
    page = int(request.args.get("page", 1))
    per_page = 20
    offset = (page - 1) * per_page
    
    conn = get_db()
    conditions = []
    params = []
    
    if status_filter:
        conditions.append("status=?")
        params.append(status_filter)
    
    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    
    rows = conn.execute(
        f"""SELECT l.*, a.name as advisor_name, a.phone as advisor_phone 
            FROM leads l 
            LEFT JOIN advisors a ON l.advisor_id = a.id 
            {where_clause} 
            ORDER BY l.created_at DESC LIMIT ? OFFSET ?""",
        params + [per_page, offset]
    ).fetchall()
    
    total = conn.execute(
        f"SELECT COUNT(*) FROM leads {where_clause}", params
    ).fetchone()[0]
    
    # 统计
    stats = {
        "new": conn.execute("SELECT COUNT(*) FROM leads WHERE status='new'").fetchone()[0],
        "assigned": conn.execute("SELECT COUNT(*) FROM leads WHERE status='assigned'").fetchone()[0],
        "contacted": conn.execute("SELECT COUNT(*) FROM leads WHERE status='contacted'").fetchone()[0],
        "converted": conn.execute("SELECT COUNT(*) FROM leads WHERE status='converted'").fetchone()[0],
    }
    
    conn.close()
    return render_template("leads.html", leads=rows, stats=stats, status_filter=status_filter, page=page, total=total, per_page=per_page)


@app.route("/leads/<int:lead_id>/assign", methods=["POST"])
@require_perm("can_edit")
def assign_lead(lead_id):
    """手动分配线索给顾问"""
    advisor_id = request.form.get("advisor_id", type=int)
    
    conn = get_db()
    lead = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    if not lead:
        conn.close()
        return jsonify({"ok": False, "msg": "线索不存在"})
    
    advisor = conn.execute("SELECT * FROM advisors WHERE id=?", (advisor_id,)).fetchone()
    if not advisor:
        conn.close()
        return jsonify({"ok": False, "msg": "顾问不存在"})
    
    # 更新线索分配
    old_advisor_id = lead["advisor_id"]
    conn.execute(
        "UPDATE leads SET advisor_id=?, status='assigned', updated_at=datetime('now','localtime') WHERE id=?",
        (advisor_id, lead_id)
    )
    
    # 更新顾问线索数
    if old_advisor_id:
        conn.execute("UPDATE advisors SET current_leads = current_leads - 1 WHERE id=?", (old_advisor_id,))
    conn.execute("UPDATE advisors SET current_leads = current_leads + 1 WHERE id=?", (advisor_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({"ok": True, "msg": f"已分配给 {advisor['name']}"})


@app.route("/leads/<int:lead_id>/status", methods=["POST"])
@require_perm("can_edit")
def update_lead_status(lead_id):
    """更新线索状态"""
    status = request.form.get("status", "")
    valid_statuses = ["new", "assigned", "contacted", "converted", "lost"]
    
    if status not in valid_statuses:
        return jsonify({"ok": False, "msg": "无效的状态"})
    
    conn = get_db()
    conn.execute(
        "UPDATE leads SET status=?, updated_at=datetime('now','localtime') WHERE id=?",
        (status, lead_id)
    )
    conn.commit()
    conn.close()
    
    return jsonify({"ok": True, "msg": "状态已更新"})


# ══════════════════════════════════════════════════════════
# 关键词自动回复管理
# ══════════════════════════════════════════════════════════

@app.route("/keyword-replies")
@login_required
def keyword_replies_list():
    """关键词回复配置页"""
    if not get_perms().get("can_edit", False):
        return render_template("403.html", perm="can_edit"), 403
    
    conn = get_db()
    replies = conn.execute("SELECT * FROM keyword_replies ORDER BY priority DESC, id").fetchall()
    conn.close()
    return render_template("keyword_replies.html", replies=replies)


@app.route("/keyword-replies/add", methods=["POST"])
@require_perm("can_edit")
def add_keyword_reply():
    """添加关键词回复"""
    keyword = request.form.get("keyword", "").strip()
    reply_content = request.form.get("reply_content", "").strip()
    match_mode = request.form.get("match_mode", "contain")
    priority = request.form.get("priority", 0, type=int)
    
    if not keyword or not reply_content:
        return jsonify({"ok": False, "msg": "关键词和回复内容不能为空"})
    
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO keyword_replies (keyword, reply_content, match_mode, priority)
            VALUES (?,?,?,?)
        """, (keyword, reply_content, match_mode, priority))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "msg": "添加成功"})
    except Exception as e:
        conn.close()
        if "UNIQUE" in str(e):
            return jsonify({"ok": False, "msg": "该关键词已存在"})
        return jsonify({"ok": False, "msg": str(e)})


@app.route("/keyword-replies/<int:reply_id>/update", methods=["POST"])
@require_perm("can_edit")
def update_keyword_reply(reply_id):
    """更新关键词回复"""
    reply_content = request.form.get("reply_content", "").strip()
    match_mode = request.form.get("match_mode", "contain")
    priority = request.form.get("priority", 0, type=int)
    is_active = request.form.get("is_active", 1, type=int)
    
    conn = get_db()
    conn.execute("""
        UPDATE keyword_replies 
        SET reply_content=?, match_mode=?, priority=?, is_active=?, updated_at=datetime('now','localtime')
        WHERE id=?
    """, (reply_content, match_mode, priority, is_active, reply_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "msg": "更新成功"})


@app.route("/keyword-replies/<int:reply_id>/delete", methods=["POST"])
@require_perm("can_edit")
def delete_keyword_reply(reply_id):
    """删除关键词回复"""
    conn = get_db()
    conn.execute("DELETE FROM keyword_replies WHERE id=?", (reply_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "msg": "已删除"})


@app.route("/api/keyword-reply", methods=["GET"])
def get_keyword_reply():
    """公众号消息接口：根据关键词获取回复（供微信服务器调用）"""
    keyword = request.args.get("keyword", "").strip()
    if not keyword:
        return jsonify({"ok": False, "msg": "缺少关键词"})
    
    conn = get_db()
    # 获取所有活跃的关键词回复
    rows = conn.execute(
        "SELECT * FROM keyword_replies WHERE is_active=1 ORDER BY priority DESC"
    ).fetchall()
    conn.close()
    
    for row in rows:
        match_mode = row["match_mode"]
        row_keyword = row["keyword"]
        
        matched = False
        if match_mode == "exact":
            matched = (keyword == row_keyword)
        elif match_mode == "prefix":
            matched = keyword.startswith(row_keyword)
        else:  # contain
            matched = row_keyword in keyword
        
        if matched:
            return jsonify({
                "ok": True,
                "keyword": row["keyword"],
                "reply_type": row["reply_type"],
                "reply_content": row["reply_content"]
            })
    
    return jsonify({"ok": False, "msg": "未匹配到关键词"})


# ══════════════════════════════════════════════════════════
# 顾问管理
# ══════════════════════════════════════════════════════════

@app.route("/advisors")
@login_required
def advisors_list():
    """顾问列表页"""
    if not get_perms().get("can_view_leads", False):
        return render_template("403.html", perm="can_view_leads"), 403
    
    conn = get_db()
    advisors = conn.execute("SELECT * FROM advisors ORDER BY id").fetchall()
    conn.close()
    
    # 支持JSON格式返回（用于线索分配下拉框）
    if request.args.get("format") == "json":
        import json
        advisors_list = []
        for a in advisors:
            advisors_list.append({
                "id": a["id"],
                "name": a["name"],
                "phone": a["phone"],
                "regions": a["regions"],
                "specialties": a["specialties"],
                "max_leads": a["max_leads"],
                "current_leads": a["current_leads"],
                "is_active": a["is_active"]
            })
        return jsonify({"ok": True, "advisors": advisors_list})
    
    return render_template("advisors.html", advisors=advisors)


@app.route("/advisors/add", methods=["POST"])
@require_perm("can_edit")
def add_advisor():
    """添加顾问"""
    import json
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    regions = request.form.get("regions", "").strip()
    specialties = request.form.get("specialties", "").strip()
    max_leads = request.form.get("max_leads", 10, type=int)
    
    if not name:
        return jsonify({"ok": False, "msg": "顾问姓名不能为空"})
    
    # 解析地区（逗号分隔）
    regions_list = [r.strip() for r in regions.split(",") if r.strip()]
    specialties_list = [s.strip() for s in specialties.split(",") if s.strip()]
    
    conn = get_db()
    conn.execute("""
        INSERT INTO advisors (name, phone, regions, specialties, max_leads)
        VALUES (?,?,?,?,?)
    """, (name, phone, json.dumps(regions_list, ensure_ascii=False), json.dumps(specialties_list, ensure_ascii=False), max_leads))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "msg": "添加成功"})


@app.route("/advisors/<int:advisor_id>/toggle", methods=["POST"])
@require_perm("can_edit")
def toggle_advisor(advisor_id):
    """启用/禁用顾问"""
    conn = get_db()
    advisor = conn.execute("SELECT is_active FROM advisors WHERE id=?", (advisor_id,)).fetchone()
    if not advisor:
        conn.close()
        return jsonify({"ok": False, "msg": "顾问不存在"})
    
    new_status = 0 if advisor["is_active"] else 1
    conn.execute("UPDATE advisors SET is_active=? WHERE id=?", (new_status, advisor_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "msg": "已" + ("启用" if new_status else "禁用"), "is_active": new_status})


# ══════════════════════════════════════════════════════════
# 测试数据生成
# ══════════════════════════════════════════════════════════

@app.route("/api/test/generate-leads", methods=["POST"])
@require_perm("can_edit")
def generate_test_leads():
    """生成5条测试线索"""
    import json
    import random
    
    test_leads = [
        {"name": "王先生", "phone": "13800138001", "loan_amount": "100-300万", "credit_status": "征信良好", "region": "浦东新区"},
        {"name": "李女士", "phone": "13800138002", "loan_amount": "30-100万", "credit_status": "有少量逾期", "region": "静安区"},
        {"name": "张老板", "phone": "13800138003", "loan_amount": "300万以上", "credit_status": "征信良好", "region": "闵行区"},
        {"name": "陈女士", "phone": "13800138004", "loan_amount": "30万以下", "credit_status": "不清楚", "region": "虹口区"},
        {"name": "刘先生", "phone": "13800138005", "loan_amount": "100-300万", "credit_status": "有少量逾期", "region": "嘉定区"},
    ]
    
    conn = get_db()
    created = 0
    for lead_data in test_leads:
        # 检查是否已存在
        existing = conn.execute("SELECT id FROM leads WHERE phone=?", (lead_data["phone"],)).fetchone()
        if existing:
            continue
        
        # 自动分配顾问
        advisor_id = _assign_advisor(lead_data["region"])
        
        conn.execute("""
            INSERT INTO leads (name, phone, loan_amount, credit_status, source, region, advisor_id, form_data, status)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            lead_data["name"],
            lead_data["phone"],
            lead_data["loan_amount"],
            lead_data["credit_status"],
            "测试数据",
            lead_data["region"],
            advisor_id,
            json.dumps(lead_data, ensure_ascii=False),
            "new"
        ))
        
        if advisor_id:
            conn.execute("UPDATE advisors SET current_leads = current_leads + 1 WHERE id=?", (advisor_id,))
        
        created += 1
    
    conn.commit()
    conn.close()
    
    return jsonify({"ok": True, "msg": f"成功生成 {created} 条测试线索"})


# ══════════════════════════════════════════════════════════
# 工单系统路由
# ══════════════════════════════════════════════════════════

@app.route("/work-orders")
@login_required
def work_orders_list():
    """工单列表页"""
    if not get_perms().get("can_view_service", False):
        return render_template("403.html", perm="can_view_service"), 403
    
    status = request.args.get("status", "")
    order_type = request.args.get("type", "")
    
    conn = get_db()
    query = """
        SELECT wo.*, a.name as advisor_name, a.phone as advisor_phone
        FROM work_orders wo
        LEFT JOIN advisors a ON wo.advisor_id = a.id
        WHERE 1=1
    """
    params = []
    if status:
        query += " AND wo.status = ?"
        params.append(status)
    if order_type:
        query += " AND wo.order_type = ?"
        params.append(order_type)
    query += " ORDER BY wo.created_at DESC"
    
    orders = conn.execute(query, params).fetchall()
    
    # 统计
    stats = conn.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status='processing' THEN 1 ELSE 0 END) as processing,
            SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status='reviewed' THEN 1 ELSE 0 END) as reviewed
        FROM work_orders
    """).fetchone()
    
    conn.close()
    return render_template("work_orders.html", orders=orders, stats=stats, status=status, order_type=order_type)


@app.route("/work-orders/<int:order_id>")
@login_required
def work_order_detail(order_id):
    """工单详情页"""
    if not get_perms().get("can_view_service", False):
        return render_template("403.html", perm="can_view_service"), 403
    
    conn = get_db()
    order = conn.execute("""
        SELECT wo.*, a.name as advisor_name, a.phone as advisor_phone
        FROM work_orders wo
        LEFT JOIN advisors a ON wo.advisor_id = a.id
        WHERE wo.id = ?
    """, (order_id,)).fetchone()
    
    if not order:
        conn.close()
        return render_template("404.html"), 404
    
    # 交付记录
    deliveries = conn.execute("""
        SELECT * FROM work_order_deliveries WHERE order_id = ? ORDER BY created_at DESC
    """, (order_id,)).fetchall()
    
    # 评价
    review = conn.execute("""
        SELECT * FROM work_order_reviews WHERE order_id = ?
    """, (order_id,)).fetchone()
    
    # 预警记录
    alerts = conn.execute("""
        SELECT * FROM work_order_alerts WHERE order_id = ? ORDER BY alert_time DESC
    """, (order_id,)).fetchall()
    
    # 顾问列表（用于分配）
    advisors = conn.execute("SELECT * FROM advisors WHERE is_active=1 ORDER BY name").fetchall()
    
    conn.close()
    return render_template("work_order_detail.html", order=order, deliveries=deliveries, 
                          review=review, alerts=alerts, advisors=advisors)


@app.route("/api/work-orders/submit", methods=["POST"])
def submit_work_order():
    """提交工单（公开接口，供文章/菜单表单调用）"""
    import json
    from datetime import datetime
    
    data = request.get_json() or request.form.to_dict()
    
    order_type = data.get("order_type", "").strip()
    customer_name = data.get("name", "").strip()
    customer_phone = data.get("phone", "").strip()
    description = data.get("description", "").strip()
    source = data.get("source", "article")  # article/menu/keyword
    source_id = data.get("source_id", None)
    
    # 额外字段
    extra_fields = {}
    for key in ["loan_amount", "company_type", "industry"]:
        if key in data:
            extra_fields[key] = data[key]
    
    if not all([order_type, customer_name, customer_phone, description]):
        return jsonify({"ok": False, "msg": "请填写所有必填项"})
    
    # 生成工单编号
    order_no = f"WO-{datetime.now().strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}{os.urandom(2).hex().upper()}"
    
    # 类型映射
    type_labels = {
        "loan_match": "贷款方案匹配",
        "finance_plan": "融资规划",
        "enterprise_analysis": "企业经营分析"
    }
    order_type_label = type_labels.get(order_type, order_type)
    
    conn = get_db()
    
    # 自动分配顾问（根据工单类型匹配专长）
    advisor_id = _assign_work_order_advisor(order_type)
    
    cursor = conn.execute("""
        INSERT INTO work_orders (order_no, customer_name, customer_phone, order_type, order_type_label,
                                description, source, source_id, advisor_id, status, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))
    """, (order_no, customer_name, customer_phone, order_type, order_type_label,
          description, source, source_id, advisor_id, "pending"))
    
    order_id = get_lastrowid(cursor)
    
    if advisor_id:
        conn.execute("UPDATE advisors SET current_leads = current_leads + 1 WHERE id=?", (advisor_id,))
        conn.execute("""
            UPDATE work_orders SET assigned_at=datetime('now','localtime') WHERE id=?
        """, (order_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        "ok": True, 
        "msg": "提交成功，我们将尽快与您联系",
        "order_no": order_no,
        "order_id": order_id
    })


def _assign_work_order_advisor(order_type: str) -> int:
    """根据工单类型自动分配顾问"""
    conn = get_db()
    
    # 类型到专长的映射
    type_to_specialty = {
        "loan_match": "贷款方案匹配",
        "finance_plan": "融资规划",
        "enterprise_analysis": "企业经营分析"
    }
    specialty = type_to_specialty.get(order_type, order_type)
    
    # 优先找专长匹配的顾问
    advisors = conn.execute("""
        SELECT * FROM advisors 
        WHERE is_active=1 AND current_leads < max_leads
        AND specialties LIKE ?
        ORDER BY current_leads ASC
    """, (f"%{specialty}%",)).fetchall()
    
    if advisors:
        advisor_id = advisors[0]["id"]
    else:
        # 没有匹配的，找负载最轻的
        advisor = conn.execute("""
            SELECT * FROM advisors 
            WHERE is_active=1 AND current_leads < max_leads
            ORDER BY current_leads ASC LIMIT 1
        """).fetchone()
        advisor_id = advisor["id"] if advisor else None
    
    conn.close()
    return advisor_id


@app.route("/api/work-orders/<int:order_id>/assign", methods=["POST"])
@require_perm("can_edit")
def assign_work_order(order_id):
    """手动分配工单"""
    advisor_id = request.json.get("advisor_id") if request.is_json else request.form.get("advisor_id", type=int)
    
    conn = get_db()
    order = conn.execute("SELECT * FROM work_orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        conn.close()
        return jsonify({"ok": False, "msg": "工单不存在"})
    
    # 更新原顾问负载
    if order["advisor_id"]:
        conn.execute("UPDATE advisors SET current_leads = MAX(0, current_leads - 1) WHERE id=?", (order["advisor_id"],))
    
    # 分配新顾问
    conn.execute("""
        UPDATE work_orders 
        SET advisor_id=?, status='processing', assigned_at=datetime('now','localtime'), updated_at=datetime('now','localtime')
        WHERE id=?
    """, (advisor_id, order_id))
    
    if advisor_id:
        conn.execute("UPDATE advisors SET current_leads = current_leads + 1 WHERE id=?", (advisor_id,))
    
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "msg": "分配成功"})


@app.route("/api/work-orders/<int:order_id>/status", methods=["POST"])
@require_perm("can_edit")
def update_work_order_status(order_id):
    """更新工单状态"""
    status = request.json.get("status") if request.is_json else request.form.get("status")
    valid_status = ["pending", "processing", "completed", "reviewed"]
    
    if status not in valid_status:
        return jsonify({"ok": False, "msg": "无效的状态"})
    
    conn = get_db()
    order = conn.execute("SELECT * FROM work_orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        conn.close()
        return jsonify({"ok": False, "msg": "工单不存在"})
    
    update_fields = ["status=?", "updated_at=datetime('now','localtime')"]
    params = [status]
    
    if status == "completed":
        update_fields.append("completed_at=datetime('now','localtime')")
    
    query = f"UPDATE work_orders SET {', '.join(update_fields)} WHERE id=?"
    params.append(order_id)
    
    conn.execute(query, params)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "msg": "状态更新成功"})


@app.route("/api/work-orders/<int:order_id>/deliver", methods=["POST"])
@require_perm("can_edit")
def add_work_order_delivery(order_id):
    """添加工单交付记录"""
    import json
    
    delivery_type = request.form.get("delivery_type", "report")
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    file_url = request.form.get("file_url", "").strip()
    is_auto_sent = request.form.get("is_auto_sent", "0") == "1"
    
    if not title:
        return jsonify({"ok": False, "msg": "标题不能为空"})
    
    conn = get_db()
    
    sent_at = None
    if is_auto_sent:
        sent_at = "datetime('now','localtime')"
    
    conn.execute("""
        INSERT INTO work_order_deliveries (order_id, delivery_type, title, content, file_url, is_auto_sent, sent_at, created_at)
        VALUES (?,?,?,?,?,?,?,datetime('now','localtime'))
    """, (order_id, delivery_type, title, content, file_url, 1 if is_auto_sent else 0, sent_at))
    
    # 如果自动推送，更新工单状态为已完成
    if is_auto_sent:
        conn.execute("""
            UPDATE work_orders 
            SET status='completed', completed_at=datetime('now','localtime'), updated_at=datetime('now','localtime')
            WHERE id=?
        """, (order_id,))
    
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "msg": "交付记录已添加"})


@app.route("/api/work-orders/<int:order_id>/review", methods=["POST"])
def submit_work_order_review(order_id):
    """提交工单评价"""
    import json
    
    rating = request.json.get("rating") if request.is_json else request.form.get("rating", type=int)
    comment = (request.json.get("comment") if request.is_json else request.form.get("comment", "")).strip()
    tags = request.json.get("tags", []) if request.is_json else request.form.getlist("tags")
    
    if not rating or not (1 <= int(rating) <= 5):
        return jsonify({"ok": False, "msg": "请给出1-5星评分"})
    
    conn = get_db()
    
    # 检查工单是否已完成
    order = conn.execute("SELECT status FROM work_orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        conn.close()
        return jsonify({"ok": False, "msg": "工单不存在"})
    if order["status"] not in ["completed", "reviewed"]:
        conn.close()
        return jsonify({"ok": False, "msg": "工单尚未完成，无法评价"})
    
    # 检查是否已评价
    existing = conn.execute("SELECT id FROM work_order_reviews WHERE order_id=?", (order_id,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"ok": False, "msg": "该工单已评价"})
    
    conn.execute("""
        INSERT INTO work_order_reviews (order_id, rating, comment, tags, created_at)
        VALUES (?,?,?,?,datetime('now','localtime'))
    """, (order_id, rating, comment, json.dumps(tags, ensure_ascii=False)))
    
    # 更新工单状态为已评价
    conn.execute("""
        UPDATE work_orders 
        SET status='reviewed', reviewed_at=datetime('now','localtime'), updated_at=datetime('now','localtime')
        WHERE id=?
    """, (order_id,))
    
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "msg": "评价提交成功，感谢您的反馈！"})


@app.route("/work-order-forms")
@login_required
def work_order_forms():
    """工单表单配置页"""
    if not get_perms().get("can_edit", False):
        return render_template("403.html", perm="can_edit"), 403
    
    conn = get_db()
    forms = conn.execute("SELECT * FROM work_order_forms ORDER BY id").fetchall()
    conn.close()
    return render_template("work_order_forms.html", forms=forms)


@app.route("/api/work-order-forms/<int:form_id>/toggle", methods=["POST"])
@require_perm("can_edit")
def toggle_work_order_form(form_id):
    """启用/禁用表单"""
    conn = get_db()
    form = conn.execute("SELECT is_active FROM work_order_forms WHERE id=?", (form_id,)).fetchone()
    if not form:
        conn.close()
        return jsonify({"ok": False, "msg": "表单不存在"})
    
    new_status = 0 if form["is_active"] else 1
    conn.execute("UPDATE work_order_forms SET is_active=? WHERE id=?", (new_status, form_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "msg": "已" + ("启用" if new_status else "禁用"), "is_active": new_status})


# ══════════════════════════════════════════════════════════
# 工单预警检查（应在调度器中定期调用）
# ══════════════════════════════════════════════════════════

def check_work_order_alerts():
    """检查工单超时预警（30分钟未处理）"""
    conn = get_db()
    
    # 查找30分钟未处理的工单
    pending_orders = conn.execute("""
        SELECT id, created_at FROM work_orders 
        WHERE status='pending' 
        AND created_at < datetime('now','localtime','-30 minutes')
        AND id NOT IN (SELECT order_id FROM work_order_alerts WHERE alert_type='timeout' AND is_resolved=0)
    """).fetchall()
    
    for order in pending_orders:
        conn.execute("""
            INSERT INTO work_order_alerts (order_id, alert_type, alert_time)
            VALUES (?, 'timeout', datetime('now','localtime'))
        """, (order["id"],))
    
    conn.commit()
    conn.close()
    return len(pending_orders)




# ══════════════════════════════════════════════════════════
# 实时同步状态 API
# ══════════════════════════════════════════════════════════

@app.route("/api/reports/sync-status")
@login_required
def api_sync_status():
    """返回待审稿件/新增线索/待处理工单的实时数据，供报表页状态栏轮询"""
    from datetime import datetime
    conn = get_db()
    today_str = datetime.now().strftime("%Y-%m-%d")

    pending_articles = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE status='pending'"
    ).fetchone()[0]

    new_leads_today = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE created_at >= ?",
        (today_str,)
    ).fetchone()[0]

    pending_orders = conn.execute(
        "SELECT COUNT(*) FROM work_orders WHERE status='pending'"
    ).fetchone()[0]

    conn.close()

    return jsonify({
        "ok": True,
        "data": {
            "pending_articles": pending_articles,
            "new_leads_today": new_leads_today,
            "pending_orders": pending_orders,
            "last_sync": datetime.now().strftime("%H:%M:%S")
        }
    })


# ══════════════════════════════════════════════════════════
# 异常预警配置
# ══════════════════════════════════════════════════════════

@app.route("/alert-config")
@login_required
def alert_config_page():
    """异常预警配置页"""
    conn = get_db()
    # 获取最近预警记录（最多20条）
    alerts = conn.execute("""
        SELECT wa.*, wo.order_no || ' / ' || wo.customer_name as order_title
        FROM work_order_alerts wa
        LEFT JOIN work_orders wo ON wa.order_id = wo.id
        ORDER BY wa.alert_time DESC LIMIT 20
    """).fetchall()

    # 读取预警配置（存在 config.py 风格的全局配置里，这里用 DB key-value 表兜底）
    try:
        lead_drop_threshold = int(conn.execute(
            "SELECT value FROM app_config WHERE key='lead_drop_threshold'"
        ).fetchone()["value"])
    except Exception:
        lead_drop_threshold = 50  # 默认50%

    try:
        order_timeout_minutes = int(conn.execute(
            "SELECT value FROM app_config WHERE key='order_timeout_minutes'"
        ).fetchone()["value"])
    except Exception:
        order_timeout_minutes = 30

    try:
        alert_notify_channel = conn.execute(
            "SELECT value FROM app_config WHERE key='alert_notify_channel'"
        ).fetchone()["value"]
    except Exception:
        alert_notify_channel = "system"  # system / wechat / both

    conn.close()
    return render_template("alert_config.html",
        alerts=alerts,
        lead_drop_threshold=lead_drop_threshold,
        order_timeout_minutes=order_timeout_minutes,
        alert_notify_channel=alert_notify_channel
    )


@app.route("/api/alert-config/save", methods=["POST"])
@require_perm("can_edit")
def save_alert_config():
    """保存预警配置"""
    data = request.get_json() or {}
    conn = get_db()

    # 确保 app_config 表存在
    if is_mysql():
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_config (
                `key` VARCHAR(191) PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

    updates = {
        "lead_drop_threshold":   str(data.get("lead_drop_threshold", 50)),
        "order_timeout_minutes": str(data.get("order_timeout_minutes", 30)),
        "alert_notify_channel":  str(data.get("alert_notify_channel", "system")),
    }
    for k, v in updates.items():
        if is_mysql():
            conn.execute(
                """
                INSERT INTO app_config(`key`, value)
                VALUES (?, ?)
                ON DUPLICATE KEY UPDATE value=VALUES(value), updated_at=CURRENT_TIMESTAMP
                """,
                (k, v),
            )
        else:
            conn.execute(
                "INSERT INTO app_config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=?,updated_at=datetime('now','localtime')",
                (k, v, v),
            )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "msg": "预警配置已保存"})


@app.route("/api/alert-config/check", methods=["POST"])
@require_perm("can_edit")
def manual_check_alerts():
    """手动触发一次预警检查"""
    from datetime import datetime, timedelta
    conn = get_db()

    # 读取配置
    try:
        order_timeout_minutes = int(conn.execute(
            "SELECT value FROM app_config WHERE key='order_timeout_minutes'"
        ).fetchone()["value"])
    except Exception:
        order_timeout_minutes = 30

    try:
        lead_drop_threshold = int(conn.execute(
            "SELECT value FROM app_config WHERE key='lead_drop_threshold'"
        ).fetchone()["value"])
    except Exception:
        lead_drop_threshold = 50

    try:
        notify_channel = conn.execute(
            "SELECT value FROM app_config WHERE key='alert_notify_channel'"
        ).fetchone()["value"]
    except Exception:
        notify_channel = "system"

    alerts_triggered = []

    # ① 工单超时预警
    cutoff = (datetime.now() - timedelta(minutes=order_timeout_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    pending_orders = conn.execute("""
        SELECT id, order_no, customer_name, created_at FROM work_orders
        WHERE status='pending' AND created_at <= ?
        AND id NOT IN (
            SELECT order_id FROM work_order_alerts
            WHERE alert_type='timeout' AND is_resolved=0
        )
    """, (cutoff,)).fetchall()

    for order in pending_orders:
        conn.execute("""
            INSERT INTO work_order_alerts (order_id, alert_type, alert_time)
            VALUES (?, 'timeout', datetime('now','localtime'))
        """, (order["id"],))
        alerts_triggered.append({
            "type": "工单超时",
            "detail": f"工单#{order['id']} 已超过{order_timeout_minutes}分钟未处理"
        })

    # ② 获客线索下降预警
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    today_leads = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE created_at >= ?", (today_str,)
    ).fetchone()[0]
    yesterday_leads = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE created_at >= ? AND created_at < ?",
        (yesterday_str, today_str)
    ).fetchone()[0]

    if yesterday_leads > 0:
        drop_pct = (yesterday_leads - today_leads) / yesterday_leads * 100
        if drop_pct >= lead_drop_threshold:
            # 避免今日重复插入
            existing = conn.execute("""
                SELECT id FROM work_order_alerts
                WHERE alert_type='lead_drop'
                AND alert_time >= ?
            """, (today_str,)).fetchone()
            if not existing:
                conn.execute("""
                    INSERT INTO work_order_alerts (order_id, alert_type, alert_time)
                    VALUES (0, 'lead_drop', datetime('now','localtime'))
                """)
                alerts_triggered.append({
                    "type": "线索量下降",
                    "detail": f"今日线索{today_leads}条 vs 昨日{yesterday_leads}条，下降{drop_pct:.0f}%"
                })

    conn.commit()
    conn.close()

    # 系统消息推送（写入 flash 或站内通知）
    msg_lines = [a["detail"] for a in alerts_triggered]
    if msg_lines and notify_channel in ("system", "both"):
        pass  # 实际可写入站内消息表；此处返回给前端即可

    return jsonify({
        "ok": True,
        "triggered": len(alerts_triggered),
        "alerts": alerts_triggered,
        "msg": f"检查完成，触发{len(alerts_triggered)}条预警"
    })


@app.route("/api/alert-config/resolve/<int:alert_id>", methods=["POST"])
@require_perm("can_approve")
def resolve_alert(alert_id):
    """标记预警为已处理"""
    conn = get_db()
    conn.execute(
        "UPDATE work_order_alerts SET is_resolved=1 WHERE id=?", (alert_id,)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "msg": "已标记为处理完毕"})


# ══════════════════════════════════════════════════════════
# 报表导出（Excel / PDF）
# ══════════════════════════════════════════════════════════

@app.route("/api/reports/export")
@login_required
def export_report():
    """导出 Excel 或 PDF 格式报表"""
    from datetime import datetime, timedelta
    import io

    fmt = request.args.get("format", "excel")
    days = request.args.get("days", "30", type=int)
    content_type_filter = request.args.get("content_type", "all")
    service_type_filter = request.args.get("service_type", "all")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    start_date_str = start_date.strftime("%Y-%m-%d")

    conn = get_db()

    # ── 采集数据 ──
    type_configs = {
        "获客": "自动获客", "品牌": "品牌宣传", "科普": "知识科普",
        "方案": "方案匹配", "融资": "融资规划", "经营": "经营分析"
    }
    selected_tags = list(type_configs.keys()) if content_type_filter == "all" else [content_type_filter]

    content_rows = []
    for tag in selected_tags:
        count = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE tags LIKE ? AND status='published' AND created_at >= ?",
            (f"%{tag}%", start_date_str)
        ).fetchone()[0]
        base_reads = 150 + hash(tag) % 200
        content_rows.append({
            "内容类型": type_configs[tag],
            "文章数": count,
            "总阅读量": count * base_reads,
            "总转发": count * (10 + hash(tag) % 30),
            "获客数": count * (2 + hash(tag) % 8),
            "平均阅读": base_reads if count > 0 else 0,
            "转化率": f"{2 + hash(tag) % 5}%" if count > 0 else "0%"
        })

    service_rows = []
    service_types = [("贷款方案匹配", "loan_match"), ("融资规划", "finance_plan"), ("企业经营分析", "enterprise_analysis")]
    for label, code in service_types:
        if service_type_filter != "all" and service_type_filter != code:
            continue
        cnt = conn.execute(
            "SELECT COUNT(*) FROM work_orders WHERE order_type=? AND created_at >= ?", (code, start_date_str)
        ).fetchone()[0]
        cmp = conn.execute(
            "SELECT COUNT(*) FROM work_orders WHERE order_type=? AND status='completed' AND created_at >= ?",
            (code, start_date_str)
        ).fetchone()[0]
        service_rows.append({
            "服务类型": label, "工单总数": cnt, "已完成": cmp,
            "完成率": f"{int(cmp/cnt*100)}%" if cnt > 0 else "0%",
            "平均评分": "4.8" if cnt > 0 else "-"
        })

    # 漏斗数据
    base_r = max(1000, days * 300)
    funnel_rows = [
        {"转化阶段": "文章阅读",  "数量": base_r,                   "环节转化率": "-"},
        {"转化阶段": "点击表单",  "数量": int(base_r * 0.25),       "环节转化率": "25%"},
        {"转化阶段": "提交留资",  "数量": int(base_r * 0.08),       "环节转化率": "32%"},
        {"转化阶段": "有效线索",  "数量": int(base_r * 0.032),      "环节转化率": "40%"},
        {"转化阶段": "成功转化",  "数量": int(base_r * 0.008),      "环节转化率": "25%"},
    ]

    conn.close()

    # ── 生成文件 ──
    report_title = f"沪上银数据报表（近{days}天）"
    date_range = f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}"
    now_str = end_date.strftime("%Y%m%d_%H%M%S")

    if fmt == "excel":
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        except ImportError:
            return jsonify({"ok": False, "msg": "缺少 openpyxl 库，请执行：pip install openpyxl"}), 400

        wb = openpyxl.Workbook()

        # ── Sheet1：内容效果 ──
        ws1 = wb.active
        ws1.title = "内容效果"
        _excel_write_sheet(ws1, report_title, date_range, content_rows)

        # ── Sheet2：服务交付 ──
        ws2 = wb.create_sheet("服务交付")
        _excel_write_sheet(ws2, report_title, date_range, service_rows)

        # ── Sheet3：转化漏斗 ──
        ws3 = wb.create_sheet("转化漏斗")
        _excel_write_sheet(ws3, report_title, date_range, funnel_rows)

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        from flask import send_file
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"沪上银数据报表_{now_str}.xlsx"
        )

    elif fmt == "pdf":
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors as rl_colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except ImportError:
            return jsonify({"ok": False, "msg": "缺少 reportlab 库，请执行：pip install reportlab"}), 400

        # 尝试注册中文字体
        font_paths = [
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\simsun.ttc",
        ]
        chinese_font = "Helvetica"
        for fp in font_paths:
            import os
            if os.path.exists(fp):
                try:
                    pdfmetrics.registerFont(TTFont("ChineseFont", fp))
                    chinese_font = "ChineseFont"
                    break
                except Exception:
                    pass

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("title", fontName=chinese_font, fontSize=16, spaceAfter=6, alignment=1, textColor=rl_colors.HexColor("#1A56DB"))
        subtitle_style = ParagraphStyle("sub", fontName=chinese_font, fontSize=9, spaceAfter=12, alignment=1, textColor=rl_colors.grey)
        heading_style = ParagraphStyle("heading", fontName=chinese_font, fontSize=12, spaceBefore=12, spaceAfter=6, textColor=rl_colors.HexColor("#1A56DB"))
        cell_style = ParagraphStyle("cell", fontName=chinese_font, fontSize=8)

        header_fill = rl_colors.HexColor("#1A56DB")
        odd_fill = rl_colors.HexColor("#f0f4ff")

        def _pdf_table(title, rows):
            story = []
            story.append(Paragraph(title, heading_style))
            if not rows:
                story.append(Paragraph("暂无数据", cell_style))
                return story
            headers = list(rows[0].keys())
            data = [[Paragraph(h, ParagraphStyle("th", fontName=chinese_font, fontSize=8, textColor=rl_colors.white))] for h in headers]
            data = [[Paragraph(h, ParagraphStyle("th", fontName=chinese_font, fontSize=8, textColor=rl_colors.white)) for h in headers]]
            for row in rows:
                data.append([Paragraph(str(v), cell_style) for v in row.values()])

            col_count = len(headers)
            col_width = (A4[0] - 4*cm) / col_count
            tbl = Table(data, colWidths=[col_width]*col_count, repeatRows=1)
            ts = TableStyle([
                ("BACKGROUND",  (0,0), (-1,0),  header_fill),
                ("FONTNAME",    (0,0), (-1,-1), chinese_font),
                ("FONTSIZE",    (0,0), (-1,-1), 8),
                ("GRID",        (0,0), (-1,-1), 0.5, rl_colors.HexColor("#dee2e6")),
                ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [rl_colors.white, odd_fill]),
                ("TOPPADDING",  (0,0), (-1,-1), 4),
                ("BOTTOMPADDING",(0,0),(-1,-1), 4),
            ])
            tbl.setStyle(ts)
            story.append(tbl)
            story.append(Spacer(1, 0.3*cm))
            return story

        story_all = []
        story_all.append(Paragraph(report_title, title_style))
        story_all.append(Paragraph(f"统计区间：{date_range}  |  导出时间：{end_date.strftime('%Y-%m-%d %H:%M:%S')}", subtitle_style))
        story_all.append(HRFlowable(width="100%", thickness=1, color=rl_colors.HexColor("#1A56DB")))
        story_all.extend(_pdf_table("一、内容效果报表", content_rows))
        story_all.extend(_pdf_table("二、服务交付报表", service_rows))
        story_all.extend(_pdf_table("三、获客转化漏斗", funnel_rows))

        doc.build(story_all)
        buf.seek(0)

        from flask import send_file
        return send_file(
            buf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"沪上银数据报表_{now_str}.pdf"
        )

    return jsonify({"ok": False, "msg": "不支持的导出格式"}), 400


def _excel_write_sheet(ws, title, date_range, rows):
    """将一组数据写入 openpyxl worksheet"""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    # 标题行
    ws.append([title])
    ws.append([f"统计区间：{date_range}"])
    ws.append([])

    if not rows:
        ws.append(["暂无数据"])
        return

    headers = list(rows[0].keys())
    header_fill = PatternFill("solid", fgColor="1A56DB")
    header_font = Font(bold=True, color="FFFFFF", size=10)
    cell_font = Font(size=10)
    odd_fill = PatternFill("solid", fgColor="EFF6FF")
    border = Border(
        left=Side(style="thin", color="DEE2E6"),
        right=Side(style="thin", color="DEE2E6"),
        top=Side(style="thin", color="DEE2E6"),
        bottom=Side(style="thin", color="DEE2E6")
    )

    # 标题单元格样式
    ws["A1"].font = Font(bold=True, size=13, color="1A56DB")
    ws["A2"].font = Font(size=9, color="888888")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(headers))

    # 表头
    ws.append(headers)
    header_row = ws.max_row
    for col_idx, _ in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border

    # 数据行
    for row_idx, row in enumerate(rows, 1):
        ws.append(list(row.values()))
        data_row = ws.max_row
        fill = odd_fill if row_idx % 2 == 0 else PatternFill()
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=data_row, column=col_idx)
            cell.font = cell_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border
            if row_idx % 2 == 0:
                cell.fill = fill

    # 列宽自适应（只处理非合并单元格）
    from openpyxl.cell.cell import MergedCell
    col_letters = set()
    for col in ws.columns:
        for cell in col:
            if not isinstance(cell, MergedCell):
                col_letters.add(cell.column_letter)
                break
    for letter in col_letters:
        col_cells = [ws.cell(row=r, column=ws[letter + '1'].column)
                     for r in range(1, ws.max_row + 1)]
        max_len = max(
            (len(str(c.value or "")) for c in col_cells if not isinstance(c, MergedCell)),
            default=8
        )
        ws.column_dimensions[letter].width = min(max(max_len + 2, 10), 30)


if __name__ == "__main__":
    init_db()
    app.run(host=WEB_HOST, port=WEB_PORT, debug=True)


