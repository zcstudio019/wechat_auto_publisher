"""公众号关注用户与融资档案登记的最小闭环服务。"""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from database import get_db, get_lastrowid, get_placeholder
from services.cultivation_service import CustomerCultivationService

logger = logging.getLogger(__name__)


class CultivationWechatService:
    INDUSTRIES = CustomerCultivationService.INDUSTRIES
    CLOSED_LOAN_STATUSES = CustomerCultivationService.CLOSED_LOAN_STATUSES
    ANNUAL_REVENUE_VALUES = {
        "500万以下": 2_500_000,
        "500-2000万": 12_500_000,
        "2000万-1亿": 60_000_000,
        "1亿以上": 100_000_000,
    }
    CREDIT_CARD_VALUES = {"30%以下": 29, "30%-70%": 50, "70%以上": 71, "不确定": None}
    CREDIT_QUERY_VALUES = {"10次以下": 9, "10-20次": 15, "20-40次": 30, "40次以上": 41, "不确定": None}
    FINANCING_NEEDS = ("暂无需求", "续贷", "增额", "新贷款", "负债优化", "不确定")
    CASHFLOW_TYPES = ("对公账户", "银联码", "微信", "支付宝", "个人卡")

    @staticmethod
    def _row(row):
        return dict(row) if row is not None else None

    @staticmethod
    def _now() -> datetime:
        return datetime.now().replace(microsecond=0)

    @staticmethod
    def _dt(value) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        try:
            return datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _openid_ref(openid: str) -> str:
        """日志只记录不可逆短摘要，不输出完整 openid。"""
        return hashlib.sha256(openid.encode("utf-8")).hexdigest()[:12]

    @classmethod
    def issue_registration_link(
        cls,
        openid: str,
        register_url: str,
        token_hours: int = 24,
        mark_subscribed: bool = True,
    ) -> dict:
        openid = str(openid or "").strip()
        if not openid:
            raise ValueError("微信用户标识不能为空")
        if not str(register_url or "").lower().startswith("https://"):
            raise ValueError("融资档案登记地址必须使用 HTTPS")

        raw_token = secrets.token_urlsafe(32)
        token_hash = cls._token_hash(raw_token)
        now = cls._now()
        expires_at = now + timedelta(hours=max(1, int(token_hours or 24)))
        p = get_placeholder()
        conn = get_db()
        try:
            existing = cls._row(
                conn.execute(
                    f"SELECT * FROM cultivation_wechat_users WHERE openid={p}", (openid,)
                ).fetchone()
            )
            subscribed = 1 if mark_subscribed else int(existing.get("subscribe_status") or 0) if existing else 1
            if existing:
                assignments = [
                    f"subscribe_status={p}", f"registration_token_hash={p}",
                    f"token_expires_at={p}", "token_used_at=NULL",
                    f"updated_at={p}",
                ]
                values = [subscribed, token_hash, expires_at, now]
                if mark_subscribed:
                    assignments.extend([f"subscribe_time={p}", "unsubscribe_time=NULL"])
                    values.append(now)
                values.append(existing["id"])
                conn.execute(
                    f"UPDATE cultivation_wechat_users SET {','.join(assignments)} WHERE id={p}",
                    tuple(values),
                )
                user_id = int(existing["id"])
                customer_id = existing.get("customer_id")
            else:
                cursor = conn.execute(
                    f"""INSERT INTO cultivation_wechat_users
                    (openid,subscribe_status,subscribe_time,registration_token_hash,token_expires_at,created_at,updated_at)
                    VALUES ({','.join([p] * 7)})""",
                    (openid, subscribed, now if mark_subscribed else None, token_hash, expires_at, now, now),
                )
                user_id = int(get_lastrowid(cursor))
                customer_id = None
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        separator = "&" if "?" in register_url else "?"
        link = f"{register_url}{separator}{urlencode({'token': raw_token})}"
        logger.info(
            "[cultivation-wechat-token-created] wechat_user_id=%s openid_ref=%s expires_at=%s",
            user_id,
            cls._openid_ref(openid),
            expires_at.isoformat(sep=" "),
        )
        return {"url": link, "token": raw_token, "customer_id": customer_id, "expires_at": expires_at}

    @classmethod
    def resolve_registration_token(cls, token: str) -> dict | None:
        token = str(token or "").strip()
        if not token or len(token) > 256:
            return None
        p = get_placeholder()
        conn = get_db()
        try:
            row = cls._row(
                conn.execute(
                    f"SELECT * FROM cultivation_wechat_users WHERE registration_token_hash={p}",
                    (cls._token_hash(token),),
                ).fetchone()
            )
        finally:
            conn.close()
        if not row or not int(row.get("subscribe_status") or 0):
            return None
        expires_at = cls._dt(row.get("token_expires_at"))
        if not expires_at or expires_at < cls._now():
            return None
        return row

    @classmethod
    def unsubscribe(cls, openid: str) -> None:
        openid = str(openid or "").strip()
        if not openid:
            return
        now = cls._now()
        p = get_placeholder()
        conn = get_db()
        try:
            existing = conn.execute(
                f"SELECT id FROM cultivation_wechat_users WHERE openid={p}", (openid,)
            ).fetchone()
            if existing:
                conn.execute(
                    f"""UPDATE cultivation_wechat_users SET subscribe_status=0,unsubscribe_time={p},
                    registration_token_hash=NULL,token_expires_at=NULL,token_used_at=NULL,updated_at={p}
                    WHERE openid={p}""",
                    (now, now, openid),
                )
            else:
                conn.execute(
                    f"""INSERT INTO cultivation_wechat_users
                    (openid,subscribe_status,unsubscribe_time,created_at,updated_at)
                    VALUES ({','.join([p] * 5)})""",
                    (openid, 0, now, now, now),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        logger.info("[cultivation-wechat-unsubscribe] openid_ref=%s", cls._openid_ref(openid))

    @classmethod
    def registration_context(cls, token: str) -> dict | None:
        user = cls.resolve_registration_token(token)
        if not user:
            return None
        p = get_placeholder()
        conn = get_db()
        try:
            customer = None
            loan = None
            if user.get("customer_id"):
                customer = cls._row(
                    conn.execute(
                        f"SELECT * FROM cultivation_customers WHERE id={p} AND is_active=1",
                        (user["customer_id"],),
                    ).fetchone()
                )
            if user.get("registration_loan_id"):
                loan = cls._row(
                    conn.execute(
                        f"SELECT * FROM cultivation_loans WHERE id={p} AND is_active=1",
                        (user["registration_loan_id"],),
                    ).fetchone()
                )
            return {"user": user, "customer": customer, "loan": loan, "is_update": bool(customer)}
        finally:
            conn.close()

    @staticmethod
    def _bool_value(value):
        normalized = str(value or "").strip()
        if normalized in ("是", "有", "1", "true"):
            return 1
        if normalized in ("否", "没有", "0", "false"):
            return 0
        return None

    @classmethod
    def _normalize_form(cls, payload: dict) -> tuple[dict, dict | None]:
        company_name = str(payload.get("company_name") or "").strip()
        legal_person = str(payload.get("legal_person") or "").strip()
        phone = re.sub(r"[\s-]", "", str(payload.get("phone") or ""))
        industry = str(payload.get("industry") or "").strip()
        revenue_range = str(payload.get("annual_revenue_range") or "").strip()
        if not company_name or len(company_name) > 255:
            raise ValueError("请填写有效的企业名称")
        if not legal_person or len(legal_person) > 128:
            raise ValueError("请填写联系人姓名")
        if not re.fullmatch(r"1[3-9]\d{9}", phone):
            raise ValueError("请填写正确的11位手机号")
        if industry not in cls.INDUSTRIES:
            raise ValueError("请选择所属行业")
        if revenue_range not in cls.ANNUAL_REVENUE_VALUES:
            raise ValueError("请选择年营收区间")

        cashflow_values = payload.get("cashflow_type") or []
        if isinstance(cashflow_values, str):
            cashflow_values = [item for item in cashflow_values.split(",") if item]
        cashflow_values = [item for item in cashflow_values if item in cls.CASHFLOW_TYPES]
        card_range = str(payload.get("credit_card_usage_range") or "不确定").strip()
        query_range = str(payload.get("credit_query_count_range") or "不确定").strip()
        need = str(payload.get("financing_need") or "不确定").strip()
        if card_range not in cls.CREDIT_CARD_VALUES or query_range not in cls.CREDIT_QUERY_VALUES:
            raise ValueError("请选择有效的资质养护选项")
        if need not in cls.FINANCING_NEEDS:
            raise ValueError("请选择当前融资需求")

        customer_payload = {
            "company_name": company_name,
            "legal_person": legal_person,
            "phone": phone,
            "industry": industry,
            "annual_revenue": cls.ANNUAL_REVENUE_VALUES[revenue_range],
            "source": "wechat_official_account",
            "cashflow_type": "、".join(cashflow_values) or None,
            "credit_card_usage": cls.CREDIT_CARD_VALUES[card_range],
            "credit_query_count": cls.CREDIT_QUERY_VALUES[query_range],
            "has_online_loans": cls._bool_value(payload.get("has_online_loans")),
            "has_collateral": cls._bool_value(payload.get("has_collateral")),
            "tax_grade": str(payload.get("tax_grade") or "").strip()[:64] or None,
            "financing_need": need,
        }

        has_loan = str(payload.get("has_loan") or "").strip()
        if has_loan not in ("有", "没有"):
            raise ValueError("请选择当前是否有贷款")
        if has_loan == "没有":
            return customer_payload, None

        bank_name = str(payload.get("bank_name") or "").strip()
        amount_text = str(payload.get("loan_amount_wan") or "").strip()
        expire_text = str(payload.get("expire_date") or "").strip()
        repayment_type = str(payload.get("repayment_type") or "不确定").strip()
        if not bank_name or len(bank_name) > 255:
            raise ValueError("请填写当前贷款银行")
        try:
            amount = float(amount_text) * 10_000
        except (TypeError, ValueError):
            raise ValueError("请填写正确的贷款总额")
        if amount < 0:
            raise ValueError("贷款总额不能小于0")
        try:
            date.fromisoformat(expire_text)
        except ValueError:
            raise ValueError("请选择最近贷款到期日")
        if repayment_type not in CustomerCultivationService.REPAYMENT_TYPES:
            raise ValueError("请选择有效的还款方式")
        return customer_payload, {
            "bank_name": bank_name,
            "product_name": "公众号登记贷款",
            "loan_amount": amount,
            "loan_balance": amount,
            "expire_date": expire_text,
            "repayment_type": repayment_type,
            "status": "正常",
        }

    @classmethod
    def submit_registration(cls, token: str, payload: dict) -> dict:
        user = cls.resolve_registration_token(token)
        if not user:
            raise ValueError("登记链接已失效，请返回公众号回复“建档”重新获取。")
        customer_payload, loan_payload = cls._normalize_form(payload)
        p = get_placeholder()
        conn = get_db()
        try:
            customer = None
            if user.get("customer_id"):
                customer = cls._row(
                    conn.execute(
                        f"SELECT * FROM cultivation_customers WHERE id={p} AND is_active=1",
                        (user["customer_id"],),
                    ).fetchone()
                )
            if not customer:
                customer = cls._row(
                    conn.execute(
                        f"""SELECT * FROM cultivation_customers
                        WHERE company_name={p} AND phone={p} AND is_active=1 ORDER BY id LIMIT 1""",
                        (customer_payload["company_name"], customer_payload["phone"]),
                    ).fetchone()
                )
        finally:
            conn.close()

        is_update = bool(customer)
        if customer:
            customer_id = int(customer["id"])
            CustomerCultivationService.update_customer(customer_id, customer_payload)
        else:
            customer_id = CustomerCultivationService.create_customer(customer_payload)

        now = cls._now()
        conn = get_db()
        try:
            conn.execute(
                f"""UPDATE cultivation_wechat_users SET customer_id={p},token_used_at={p},updated_at={p}
                WHERE id={p}""",
                (customer_id, now, now, user["id"]),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        registration_loan_id = user.get("registration_loan_id")
        if registration_loan_id:
            conn = get_db()
            try:
                registered_loan = cls._row(
                    conn.execute(
                        f"SELECT * FROM cultivation_loans WHERE id={p} AND customer_id={p}",
                        (registration_loan_id, customer_id),
                    ).fetchone()
                )
            finally:
                conn.close()
            if not registered_loan:
                registration_loan_id = None

        # 弱去重绑定到已有客户时，复用该客户之前的公众号简化贷款，避免不同微信入口重复造贷款。
        if not registration_loan_id:
            conn = get_db()
            try:
                existing_registration_loan = cls._row(
                    conn.execute(
                        f"""SELECT * FROM cultivation_loans WHERE customer_id={p} AND is_active=1
                        AND product_name={p} ORDER BY id LIMIT 1""",
                        (customer_id, "公众号登记贷款"),
                    ).fetchone()
                )
            finally:
                conn.close()
            if existing_registration_loan:
                registration_loan_id = int(existing_registration_loan["id"])

        if loan_payload:
            if registration_loan_id:
                CustomerCultivationService.update_loan(int(registration_loan_id), loan_payload)
            else:
                registration_loan_id = CustomerCultivationService.add_loan(customer_id, loan_payload)
        elif registration_loan_id:
            CustomerCultivationService.update_loan(
                int(registration_loan_id), {"status": "已结清", "loan_balance": 0}
            )

        conn = get_db()
        try:
            conn.execute(
                f"UPDATE cultivation_wechat_users SET registration_loan_id={p},updated_at={p} WHERE id={p}",
                (registration_loan_id, now, user["id"]),
            )
            CustomerCultivationService._event(
                conn,
                customer_id,
                "register_completed",
                {"wechat_user_id": int(user["id"]), "mode": "updated" if is_update else "created"},
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        CustomerCultivationService.refresh_customer(customer_id, create_task=bool(loan_payload))
        logger.info(
            "[cultivation-wechat-register-success] wechat_user_id=%s customer_id=%s mode=%s loan_id=%s",
            user["id"], customer_id, "updated" if is_update else "created", registration_loan_id,
        )
        return {
            "customer_id": customer_id,
            "registration_loan_id": registration_loan_id,
            "is_update": is_update,
        }

    @classmethod
    def find_keyword_reply(cls, content: str) -> str | None:
        content = str(content or "").strip()
        if not content:
            return None
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM keyword_replies WHERE is_active=1 ORDER BY priority DESC,id"
            ).fetchall()
        except Exception:
            logger.exception("[cultivation-wechat-keyword-query-error]")
            return None
        finally:
            conn.close()
        for raw in rows:
            row = dict(raw)
            keyword = str(row.get("keyword") or "")
            mode = row.get("match_mode") or "contain"
            matched = content == keyword if mode == "exact" else content.startswith(keyword) if mode == "prefix" else keyword in content
            if matched and row.get("reply_type", "text") == "text":
                return str(row.get("reply_content") or "").strip() or None
        return None
