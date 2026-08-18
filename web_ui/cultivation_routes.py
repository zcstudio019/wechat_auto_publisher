"""融资客户培育中心 Blueprint。"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from config import ROLE_PERMISSIONS
from database import get_db, get_placeholder
from services.cultivation_service import CustomerCultivationService as Service

logger = logging.getLogger(__name__)
cultivation_bp = Blueprint("cultivation", __name__, url_prefix="/cultivation")


def format_article_status(review_status, publish_status, legacy_status=None) -> dict[str, str]:
    """把文章内部状态组合转换为运营可读文案，未知值绝不回显。"""
    review = str(review_status or "").strip().lower()
    publish = str(publish_status or "").strip().lower()
    legacy = str(legacy_status or "").strip().lower()

    if publish == "published" or legacy == "published":
        return {"label": "已发布", "badge": "bg-success"}
    if publish in {"failed", "error"} or legacy in {"failed", "error"}:
        return {"label": "推送失败", "badge": "bg-danger"}
    if review == "rejected" or legacy == "rejected":
        return {"label": "审核未通过", "badge": "bg-danger"}
    if publish in {"wechat_draft", "draft_sent"} or legacy in {"wechat_draft", "draft_sent"}:
        return {"label": "已审核 · 已推送草稿箱", "badge": "bg-info text-dark"}
    if publish == "waiting_publish" or legacy == "waiting_publish":
        return {"label": "已审核 · 等待人工发表", "badge": "bg-primary"}
    if (review == "approved" or legacy == "approved") and publish in {"", "not_ready", "not_published"}:
        return {"label": "已审核 · 待推送", "badge": "bg-warning text-dark"}
    if (review in {"pending", "pending_review", "draft"} or legacy in {"pending", "pending_review", "draft"}) and publish in {"", "not_ready", "not_published"}:
        return {"label": "待审核", "badge": "bg-warning text-dark"}
    return {"label": "状态待确认", "badge": "bg-secondary"}


def format_followup_trigger(trigger_type) -> str:
    """跟进节点展示中文；未知节点不暴露内部枚举。"""
    normalized = str(trigger_type or "").strip()
    if normalized.startswith("manual_followup"):
        return "人工后续跟进"
    if normalized == "manual" or normalized.startswith("manual_"):
        return "人工跟进"
    return {
        "90_day": "到期前90天提醒",
        "60_day": "到期前60天提醒",
        "30_day": "到期前30天提醒",
        "15_day": "到期前15天紧急提醒",
    }.get(normalized, "触发原因待确认")


def format_cultivation_tag_type(tag_type) -> str:
    """培育标签类型展示中文；未知类型不回显数据库原值。"""
    return {
        "risk": "风险",
        "stage": "生命周期",
        "industry": "行业",
        "feature": "客户特征",
        "need": "融资需求",
    }.get(str(tag_type or "").strip(), "标签类型待确认")


def format_followup_datetime(value) -> str:
    """把数据库/表单时间统一为运营可读格式，空值不展示技术值。"""
    if not value:
        return "—"
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip())
        except (TypeError, ValueError):
            return "—"
    return parsed.strftime("%Y-%m-%d %H:%M")


def _perms():
    return ROLE_PERMISSIONS.get(session.get("role", "editor"), ROLE_PERMISSIONS["editor"])


@cultivation_bp.before_request
def _protect_cultivation():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    if not (_perms().get("show_nav_business") or _perms().get("can_view_leads")):
        return render_template("403.html", perm="show_nav_business"), 403
    # 现有系统没有 advisor 登录映射；沿用“可查看线索”的运营权限处理客户培育。
    if request.method != "GET" and not (_perms().get("can_edit") or _perms().get("can_view_leads")):
        return jsonify({"ok": False, "msg": "权限不足，请联系管理员"}), 403


@cultivation_bp.errorhandler(Exception)
def _cultivation_error(exc):
    logger.exception("[cultivation-route-error] path=%s error=%s", request.path, exc)
    if request.method != "GET" or request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": False, "msg": "培育模块暂时无法处理该请求，其他功能不受影响"}), 500
    return render_template("500.html", error_message="融资客户培育模块暂时不可用，公众号其他功能不受影响。"), 500


def _dicts(rows):
    return [dict(row) for row in rows]


def _form_payload():
    payload = {key: value.strip() for key, value in request.form.items()}
    for key in ("advisor_id", "credit_query_count", "bank_count"):
        payload[key] = int(payload[key]) if payload.get(key) else None
    for key in ("annual_revenue", "credit_card_usage", "loan_amount", "loan_balance", "interest_rate"):
        if key in payload:
            payload[key] = float(payload[key]) if payload.get(key) else None
    for key in ("has_online_loans", "has_collateral"):
        if key in payload:
            payload[key] = 1 if payload[key] in ("1", "true", "是") else 0
    return payload


def _advisors(conn):
    return _dicts(conn.execute("SELECT id,name FROM advisors WHERE is_active=1 ORDER BY name,id").fetchall())


def _decorate_customer(conn, customer: dict):
    p = get_placeholder()
    loans = _dicts(conn.execute(f"SELECT * FROM cultivation_loans WHERE customer_id={p} AND is_active=1 ORDER BY expire_date", (customer["id"],)).fetchall())
    for loan in loans:
        loan["days_to_expire"] = Service.days_to_expire(loan.get("expire_date"))
    open_loans = [loan for loan in loans if loan["status"] not in Service.CLOSED_LOAN_STATUSES]
    nearest = open_loans[0] if open_loans else None
    customer["loans"] = loans
    customer["loan_count"] = len(loans)
    customer["loan_total"] = sum(float(loan.get("loan_amount") or 0) for loan in loans)
    customer["nearest_loan"] = nearest
    customer["days_to_expire"] = nearest.get("days_to_expire") if nearest else None
    last = conn.execute(f"SELECT created_at FROM cultivation_followups WHERE customer_id={p} AND completed_at IS NOT NULL ORDER BY completed_at DESC,id DESC LIMIT 1", (customer["id"],)).fetchone()
    customer["last_followup"] = last["created_at"] if last else None
    return customer


@cultivation_bp.route("")
def dashboard():
    conn = get_db()
    try:
        customers = [_decorate_customer(conn, dict(row)) for row in conn.execute("SELECT * FROM cultivation_customers WHERE is_active=1 ORDER BY id DESC").fetchall()]
        today = date.today()
        pending_statuses = {"待处理", "延期跟进"}
        followups = _dicts(conn.execute("SELECT * FROM cultivation_followups ORDER BY due_date,id").fetchall())
        stats = {
            "total": len(customers),
            "profiled": sum(1 for item in customers if item.get("phone") or item.get("legal_person")),
            "expire_90": sum(1 for item in customers if item["days_to_expire"] is not None and 0 <= item["days_to_expire"] <= 90),
            "expire_60": sum(1 for item in customers if item["days_to_expire"] is not None and 0 <= item["days_to_expire"] <= 60),
            "expire_30": sum(1 for item in customers if item["days_to_expire"] is not None and 0 <= item["days_to_expire"] <= 30),
            "today_followups": sum(1 for item in followups if str(item["due_date"])[:10] <= today.isoformat() and item["status"] in pending_statuses),
            "high_risk": sum(1 for item in customers if item["risk_level"] in ("高风险", "紧急")),
            "consultations": sum(1 for item in customers if item["consultation_status"] == "已产生咨询"),
        }
        focus = sorted(
            [item for item in customers if item["nearest_loan"]],
            key=lambda item: (Service.RISK_RANK.get(item["risk_level"], 0), -(item["days_to_expire"] or 99999)),
            reverse=True,
        )[:15]
        for item in focus:
            item["recommendation"] = Service.recommend_article(item["id"], connection=conn)
            trigger = Service._trigger_for_stage(item["current_stage"])
            item["recommended_action"] = trigger[2] if trigger else "保持常规贷后沟通"
        return render_template("cultivation/dashboard.html", stats=stats, focus_customers=focus)
    finally:
        conn.close()


@cultivation_bp.route("/customers")
def customers():
    filters = {key: request.args.get(key, "").strip() for key in ("q", "industry", "stage", "risk_level", "advisor_id", "expiry")}
    conn = get_db()
    try:
        rows = _dicts(conn.execute("SELECT c.*,a.name advisor_name FROM cultivation_customers c LEFT JOIN advisors a ON a.id=c.advisor_id WHERE c.is_active=1 ORDER BY c.updated_at DESC,c.id DESC").fetchall())
        items = [_decorate_customer(conn, row) for row in rows]
        q = filters["q"].lower()
        if q:
            items = [item for item in items if q in " ".join(str(item.get(k) or "") for k in ("company_name", "legal_person", "phone")).lower()]
        for key in ("industry", "risk_level"):
            if filters[key]: items = [item for item in items if str(item.get(key) or "") == filters[key]]
        if filters["stage"]: items = [item for item in items if item.get("current_stage") == filters["stage"]]
        if filters["advisor_id"]: items = [item for item in items if str(item.get("advisor_id") or "") == filters["advisor_id"]]
        if filters["expiry"]:
            limit = int(filters["expiry"])
            items = [item for item in items if item["days_to_expire"] is not None and 0 <= item["days_to_expire"] <= limit]
        page = max(request.args.get("page", 1, type=int), 1)
        per_page = 20
        total = len(items)
        total_pages = max((total + per_page - 1) // per_page, 1)
        page = min(page, total_pages)
        items = items[(page - 1) * per_page:page * per_page]
        return render_template(
            "cultivation/customers.html", customers=items, filters=filters,
            advisors=_advisors(conn), industries=Service.INDUSTRIES,
            page=page, total=total, total_pages=total_pages,
            filter_query=urlencode({key: value for key, value in filters.items() if value}),
        )
    finally:
        conn.close()


@cultivation_bp.route("/customers/new", methods=["GET", "POST"])
def customer_new():
    if request.method == "POST":
        customer_id = Service.create_customer(_form_payload())
        flash("客户档案已创建")
        return redirect(url_for("cultivation.customer_detail", customer_id=customer_id))
    conn = get_db()
    try:
        return render_template("cultivation/customer_form.html", customer=None, advisors=_advisors(conn), industries=Service.INDUSTRIES)
    finally: conn.close()


@cultivation_bp.route("/customers/<int:customer_id>/edit", methods=["GET", "POST"])
def customer_edit(customer_id):
    p = get_placeholder(); conn = get_db()
    try:
        customer = conn.execute(f"SELECT * FROM cultivation_customers WHERE id={p} AND is_active=1", (customer_id,)).fetchone()
        if not customer: return render_template("404.html"), 404
        if request.method == "POST":
            conn.close(); Service.update_customer(customer_id, _form_payload()); flash("客户档案已更新")
            return redirect(url_for("cultivation.customer_detail", customer_id=customer_id))
        return render_template("cultivation/customer_form.html", customer=dict(customer), advisors=_advisors(conn), industries=Service.INDUSTRIES)
    finally:
        try: conn.close()
        except Exception: pass


@cultivation_bp.route("/customers/<int:customer_id>")
def customer_detail(customer_id):
    p = get_placeholder(); conn = get_db()
    try:
        row = conn.execute(f"SELECT c.*,a.name advisor_name FROM cultivation_customers c LEFT JOIN advisors a ON a.id=c.advisor_id WHERE c.id={p} AND c.is_active=1", (customer_id,)).fetchone()
        if not row: return render_template("404.html"), 404
        customer = _decorate_customer(conn, dict(row))
        tags = _dicts(conn.execute(f"SELECT * FROM cultivation_tags WHERE customer_id={p} ORDER BY tag_type,created_at", (customer_id,)).fetchall())
        followups = _dicts(conn.execute(f"SELECT f.*,a.name advisor_name FROM cultivation_followups f LEFT JOIN advisors a ON a.id=f.advisor_id WHERE f.customer_id={p} AND (f.completed_at IS NOT NULL OR f.task_type IN ('人工跟进','人工后续跟进') OR f.contact_method IS NOT NULL OR f.followup_result IS NOT NULL) ORDER BY COALESCE(f.completed_at,f.created_at) DESC", (customer_id,)).fetchall())
        for followup in followups:
            followup["next_followup_display"] = format_followup_datetime(followup.get("next_followup_at"))
            followup["activity_at_display"] = format_followup_datetime(followup.get("completed_at") or followup.get("created_at"))
        next_row = conn.execute(f"SELECT next_followup_at FROM cultivation_followups WHERE customer_id={p} AND next_followup_at IS NOT NULL AND status IN ('待处理','延期跟进') ORDER BY next_followup_at LIMIT 1", (customer_id,)).fetchone()
        customer["next_followup_at"] = next_row["next_followup_at"] if next_row else None
        customer["next_followup_display"] = format_followup_datetime(customer["next_followup_at"])
        recommendation = Service.recommend_article(customer_id, connection=conn)
        return render_template("cultivation/customer_detail.html", customer=customer, tags=tags, followups=followups, recommendation=recommendation, loan_statuses=Service.LOAN_STATUSES, repayment_types=Service.REPAYMENT_TYPES)
    finally: conn.close()


@cultivation_bp.route("/customers/<int:customer_id>/loans/new", methods=["POST"])
def loan_new(customer_id):
    Service.add_loan(customer_id, _form_payload()); flash("贷款已新增，客户状态已重新计算")
    return redirect(url_for("cultivation.customer_detail", customer_id=customer_id))


@cultivation_bp.route("/loans")
def loans():
    conn = get_db()
    try:
        rows = _dicts(conn.execute("SELECT l.*,c.company_name,c.risk_level,c.current_stage FROM cultivation_loans l JOIN cultivation_customers c ON c.id=l.customer_id WHERE l.is_active=1 AND c.is_active=1 ORDER BY l.expire_date,l.id").fetchall())
        for row in rows: row["days_to_expire"] = Service.days_to_expire(row["expire_date"])
        return render_template("cultivation/loans.html", loans=rows, loan_statuses=Service.LOAN_STATUSES, repayment_types=Service.REPAYMENT_TYPES)
    finally: conn.close()


@cultivation_bp.route("/loans/<int:loan_id>/edit", methods=["POST"])
def loan_edit(loan_id):
    payload = _form_payload(); Service.update_loan(loan_id, payload); flash("贷款信息已更新")
    return redirect(request.referrer or url_for("cultivation.loans"))


@cultivation_bp.route("/customers/<int:customer_id>/followups", methods=["POST"])
def followup_new(customer_id):
    try:
        result = Service.record_followup(customer_id, _form_payload())
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("cultivation.customer_detail", customer_id=customer_id))
    message = "跟进记录已保存"
    if result.get("next_followup_at"):
        message += f"，下次跟进：{format_followup_datetime(result['next_followup_at'])}"
    flash(message)
    return redirect(url_for("cultivation.customer_detail", customer_id=customer_id))


@cultivation_bp.route("/followups")
def followups():
    view = request.args.get("view", "today")
    filters = {key: request.args.get(key, "").strip() for key in ("advisor_id", "risk_level", "stage", "industry", "status")}
    conn = get_db()
    try:
        rows = _dicts(conn.execute("""SELECT f.*,c.company_name,c.legal_person,c.phone,c.industry,c.current_stage,c.risk_level,
            l.bank_name,l.loan_amount,l.expire_date,a.name advisor_name,ar.title article_title
            FROM cultivation_followups f JOIN cultivation_customers c ON c.id=f.customer_id
            LEFT JOIN cultivation_loans l ON l.id=f.loan_id LEFT JOIN advisors a ON a.id=f.advisor_id
            LEFT JOIN articles ar ON ar.id=f.recommended_article_id WHERE c.is_active=1 ORDER BY f.due_date,f.priority,f.id""").fetchall())
        today = date.today(); completed = {"已联系", "已预约诊断", "客户暂无需求", "已完成"}
        for row in rows: row["days_to_expire"] = Service.days_to_expire(row.get("expire_date"))
        for row in rows:
            row["trigger_label"] = format_followup_trigger(row.get("trigger_type"))
            row["next_followup_display"] = format_followup_datetime(row.get("next_followup_at"))
        if view == "overdue": rows = [r for r in rows if str(r["due_date"])[:10] < today.isoformat() and r["status"] not in completed]
        elif view == "future": rows = [r for r in rows if today.isoformat() < str(r["due_date"])[:10] <= (today + timedelta(days=7)).isoformat() and r["status"] not in completed]
        elif view == "completed": rows = [r for r in rows if r["status"] in completed]
        else: rows = [r for r in rows if str(r["due_date"])[:10] <= today.isoformat() and r["status"] not in completed]
        field_map = {"advisor_id":"advisor_id", "risk_level":"risk_level", "stage":"current_stage", "industry":"industry", "status":"status"}
        for key, field in field_map.items():
            if filters[key]: rows = [r for r in rows if str(r.get(field) or "") == filters[key]]
        return render_template("cultivation/followups.html", followups=rows, view=view, filters=filters, advisors=_advisors(conn), statuses=Service.FOLLOWUP_STATUSES, industries=Service.INDUSTRIES)
    finally: conn.close()


@cultivation_bp.route("/followups/<int:followup_id>/update", methods=["POST"])
def followup_update(followup_id):
    try:
        result = Service.update_followup(followup_id, _form_payload())
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(request.referrer or url_for("cultivation.followups"))
    message = "跟进记录已保存"
    if result.get("next_followup_at"):
        message += f"，下次跟进：{format_followup_datetime(result['next_followup_at'])}"
    flash(message)
    return redirect(request.referrer or url_for("cultivation.followups"))


@cultivation_bp.route("/tags")
def tags():
    conn = get_db()
    try:
        rows = _dicts(conn.execute("SELECT t.*,c.company_name FROM cultivation_tags t JOIN cultivation_customers c ON c.id=t.customer_id WHERE c.is_active=1 ORDER BY t.created_at DESC,t.id DESC").fetchall())
        for row in rows:
            row["tag_type_label"] = format_cultivation_tag_type(row.get("tag_type"))
        return render_template("cultivation/tags.html", tags=rows)
    finally: conn.close()


@cultivation_bp.route("/content")
def content():
    conn = get_db()
    try:
        articles = _dicts(conn.execute("SELECT * FROM articles ORDER BY created_at DESC,id DESC").fetchall())
        tag_rows = _dicts(conn.execute("SELECT * FROM article_cultivation_tags ORDER BY article_id,tag_type").fetchall())
        tag_map = {}
        for tag in tag_rows: tag_map.setdefault(tag["article_id"], {})[tag["tag_type"]] = tag["tag_value"]
        for article in articles:
            article["cultivation_tags"] = tag_map.get(article["id"], {})
            article["article_status"] = format_article_status(
                article.get("review_status"), article.get("publish_status"), article.get("status")
            )
        return render_template("cultivation/content.html", articles=articles, industries=Service.INDUSTRIES)
    finally: conn.close()


@cultivation_bp.route("/content/<int:article_id>/tags", methods=["POST"])
def content_tags(article_id):
    Service.set_article_tags(article_id, _form_payload()); flash("文章培育标签已更新")
    return redirect(url_for("cultivation.content"))
