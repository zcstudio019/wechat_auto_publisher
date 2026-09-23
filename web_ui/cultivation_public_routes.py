"""公众号用户可访问的融资档案登记页面。"""

from __future__ import annotations

import logging
import re

from flask import Blueprint, render_template, request

from services.cultivation_wechat_service import CultivationWechatService as Service

logger = logging.getLogger(__name__)
cultivation_public_bp = Blueprint("cultivation_public", __name__, url_prefix="/public/cultivation")
LOAN_FIELD_RE = re.compile(r"^loans\[(\d+)\]\[(loan_id|bank_name|product_name|loan_amount_wan|expire_date|repayment_type|status)\]$")
LOAN_FIELDS = ("loan_id", "bank_name", "product_name", "loan_amount_wan", "expire_date", "repayment_type", "status")


def _loans_from_form(form) -> list[dict]:
    grouped: dict[int, dict] = {}
    for key, value in form.items():
        match = LOAN_FIELD_RE.match(key)
        if not match:
            continue
        index = int(match.group(1))
        grouped.setdefault(index, {})[match.group(2)] = value.strip()
    loans = [{field: grouped[index].get(field, "") for field in LOAN_FIELDS} for index in sorted(grouped)]
    # 兼容 Phase 1.1 已发出的旧页面，不再作为新页面的数据结构。
    if not loans and any(form.get(name) for name in ("bank_name", "loan_amount_wan", "expire_date")):
        loans = [{
            "loan_id": form.get("loan_id", "").strip(),
            "bank_name": form.get("bank_name", "").strip(),
            "product_name": form.get("product_name", "公众号登记贷款").strip() or "公众号登记贷款",
            "loan_amount_wan": form.get("loan_amount_wan", "").strip(),
            "expire_date": form.get("expire_date", "").strip(),
            "repayment_type": form.get("repayment_type", "不确定").strip(),
            "status": form.get("loan_status", "正常").strip(),
        }]
    return loans


def _form_data_from_context(context: dict) -> dict:
    customer = context.get("customer") or {}
    loans = context.get("loans") or []
    annual_reverse = {value: label for label, value in Service.ANNUAL_REVENUE_VALUES.items()}
    card_value = customer.get("credit_card_usage")
    query_value = customer.get("credit_query_count")
    cashflows = [item for item in str(customer.get("cashflow_type") or "").replace(",", "、").split("、") if item]
    def yes_no_unknown(value):
        return "是" if value in (1, True) else "否" if value in (0, False) else "不确定"
    return {
        **customer,
        "profile_type": customer.get("profile_type") or "company",
        "annual_revenue_range": annual_reverse.get(float(customer.get("annual_revenue") or 0), ""),
        "cashflow_type": cashflows,
        "credit_card_usage_range": "70%以上" if card_value is not None and float(card_value) > 70 else "30%-70%" if card_value is not None and float(card_value) > 30 else "30%以下" if card_value is not None else "不确定",
        "credit_query_count_range": "40次以上" if query_value is not None and int(query_value) > 40 else "20-40次" if query_value is not None and int(query_value) > 20 else "10-20次" if query_value is not None and int(query_value) >= 10 else "10次以下" if query_value is not None else "不确定",
        "has_loan": "有" if any(loan.get("status") not in Service.CLOSED_LOAN_STATUSES for loan in loans) else "没有" if context.get("is_update") else "",
        "loans": [{
            "loan_id": loan.get("id", ""),
            "bank_name": loan.get("bank_name", ""),
            "product_name": loan.get("product_name", ""),
            "loan_amount_wan": float(loan.get("loan_amount") or 0) / 10000,
            "expire_date": str(loan.get("expire_date") or "")[:10],
            "repayment_type": loan.get("repayment_type", "不确定"),
            "status": loan.get("status", "正常"),
        } for loan in loans],
        "existing_open_loan_count": sum(1 for loan in loans if loan.get("status") not in Service.CLOSED_LOAN_STATUSES),
        "has_online_loans": yes_no_unknown(customer.get("has_online_loans")),
        "has_collateral": yes_no_unknown(customer.get("has_collateral")),
        "has_social_security": yes_no_unknown(customer.get("has_social_security")),
        "has_housing_fund": yes_no_unknown(customer.get("has_housing_fund")),
        "has_property": yes_no_unknown(customer.get("has_property")),
        "has_credit_card": yes_no_unknown(customer.get("has_credit_card")),
        "has_financing_need": yes_no_unknown(customer.get("has_financing_need")),
        "expected_financing_amount_wan": (
            float(customer["expected_financing_amount"]) / 10000
            if customer.get("expected_financing_amount") not in (None, "") else ""
        ),
    }


@cultivation_public_bp.after_request
def _secure_public_response(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@cultivation_public_bp.route("/register", methods=["GET", "POST"])
def register():
    token = (request.args.get("token") or request.form.get("registration_token") or "").strip()
    context = Service.registration_context(token)
    if not context:
        return render_template("cultivation_public/register_invalid.html"), 200

    if request.method == "GET":
        logger.info("[cultivation-wechat-register-open] wechat_user_id=%s", context["user"]["id"])
        return render_template(
            "cultivation_public/register.html",
            registration_token=token,
            is_update=context["is_update"],
            form_data=_form_data_from_context(context),
            error=None,
            service=Service,
        )

    form_data = {key: value.strip() for key, value in request.form.items()}
    form_data["cashflow_type"] = request.form.getlist("cashflow_type")
    form_data["_legacy_single_loan"] = not any(LOAN_FIELD_RE.match(key) for key in request.form.keys())
    form_data["loans"] = _loans_from_form(request.form)
    form_data["existing_open_loan_count"] = sum(
        1 for loan in (context.get("loans") or []) if loan.get("status") not in Service.CLOSED_LOAN_STATUSES
    )
    try:
        result = Service.submit_registration(token, form_data)
    except ValueError as exc:
        logger.info("[cultivation-wechat-register-validation] wechat_user_id=%s error=%s", context["user"]["id"], exc)
        return render_template(
            "cultivation_public/register.html",
            registration_token=token,
            is_update=context["is_update"],
            form_data=form_data,
            error=str(exc),
            service=Service,
        ), 400
    except Exception:
        logger.exception("[cultivation-wechat-register-error] wechat_user_id=%s", context["user"]["id"])
        return render_template(
            "cultivation_public/register.html",
            registration_token=token,
            is_update=context["is_update"],
            form_data=form_data,
            error="档案保存暂时失败，请稍后重试。",
            service=Service,
        ), 500

    return render_template(
        "cultivation_public/register_success.html",
        is_update=result["is_update"],
    ), 200
