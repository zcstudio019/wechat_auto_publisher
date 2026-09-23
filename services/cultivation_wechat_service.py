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
    PROFILE_TYPES = CustomerCultivationService.PROFILE_TYPES
    OCCUPATION_TYPES = CustomerCultivationService.OCCUPATION_TYPES
    MONTHLY_INCOME_RANGES = CustomerCultivationService.MONTHLY_INCOME_RANGES
    CREDIT_QUERY_LEVELS = CustomerCultivationService.CREDIT_QUERY_LEVELS
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
    FINANCING_TIME_VALUES = ("1个月内", "1-3个月", "3-6个月", "6个月以上", "不确定")
    LOAN_STATUSES = CustomerCultivationService.LOAN_STATUSES
    REPAYMENT_TYPES = CustomerCultivationService.REPAYMENT_TYPES
    MAX_PUBLIC_LOANS = 10

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
                    assignments.extend([f"subscribe_time={p}", f"last_interaction_at={p}", "unsubscribe_time=NULL"])
                    values.extend([now, now])
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
                    (openid,subscribe_status,subscribe_time,last_interaction_at,registration_token_hash,token_expires_at,created_at,updated_at)
                    VALUES ({','.join([p] * 8)})""",
                    (openid, subscribed, now if mark_subscribed else None, now if mark_subscribed else None, token_hash, expires_at, now, now),
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
    def record_interaction(cls, openid: str) -> None:
        """记录入站互动时间，供客服消息48小时窗口做保守预判。"""
        openid = str(openid or "").strip()
        if not openid:
            return
        p = get_placeholder()
        now = cls._now()
        conn = get_db()
        try:
            existing = conn.execute(
                f"SELECT id FROM cultivation_wechat_users WHERE openid={p}", (openid,)
            ).fetchone()
            if existing:
                conn.execute(
                    f"UPDATE cultivation_wechat_users SET subscribe_status=1,last_interaction_at={p},updated_at={p} WHERE openid={p}",
                    (now, now, openid),
                )
            else:
                conn.execute(
                    f"""INSERT INTO cultivation_wechat_users
                    (openid,subscribe_status,subscribe_time,last_interaction_at,created_at,updated_at)
                    VALUES ({','.join([p] * 6)})""",
                    (openid, 1, now, now, now, now),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

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
            loans = []
            if user.get("customer_id"):
                customer = cls._row(
                    conn.execute(
                        f"SELECT * FROM cultivation_customers WHERE id={p} AND is_active=1",
                        (user["customer_id"],),
                    ).fetchone()
                )
            if customer:
                loans = [dict(row) for row in conn.execute(
                    f"""SELECT * FROM cultivation_loans WHERE customer_id={p} AND is_active=1
                    ORDER BY expire_date ASC,id ASC""",
                    (customer["id"],),
                ).fetchall()]
            return {"user": user, "customer": customer, "loans": loans, "is_update": bool(customer)}
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
    def _normalize_form(cls, payload: dict) -> tuple[dict, str, list[dict], bool]:
        profile_type = CustomerCultivationService.normalize_profile_type(payload.get("profile_type"))
        company_name = str(payload.get("company_name") or "").strip()
        legal_person = str(payload.get("legal_person") or "").strip()
        phone = re.sub(r"[\s-]", "", str(payload.get("phone") or ""))
        industry = str(payload.get("industry") or "").strip()
        revenue_range = str(payload.get("annual_revenue_range") or "").strip()
        if not legal_person or len(legal_person) > 128:
            raise ValueError("请填写联系人姓名" if profile_type == "company" else "请填写姓名")
        if not re.fullmatch(r"1[3-9]\d{9}", phone):
            raise ValueError("请填写正确的11位手机号")

        customer_payload = {
            "profile_type": profile_type,
            "legal_person": legal_person,
            "phone": phone,
            "source": "wechat_official_account",
        }
        if profile_type == "company":
            if not company_name or len(company_name) > 255:
                raise ValueError("请填写有效的企业名称")
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
            customer_payload.update({
                "company_name": company_name,
                "industry": industry,
                "annual_revenue": cls.ANNUAL_REVENUE_VALUES[revenue_range],
                "cashflow_type": "、".join(cashflow_values) or None,
                "credit_card_usage": cls.CREDIT_CARD_VALUES[card_range],
                "credit_query_count": cls.CREDIT_QUERY_VALUES[query_range],
                "has_online_loans": cls._bool_value(payload.get("has_online_loans")),
                "has_collateral": cls._bool_value(payload.get("has_collateral")),
                "tax_grade": str(payload.get("tax_grade") or "").strip()[:64] or None,
                "financing_need": need,
            })
        else:
            occupation_type = str(payload.get("occupation_type") or "").strip()
            income_range = str(payload.get("monthly_income_range") or "").strip()
            credit_query_level = str(payload.get("credit_query_level") or "不确定").strip()
            if occupation_type not in cls.OCCUPATION_TYPES:
                raise ValueError("请选择职业类型")
            if income_range not in cls.MONTHLY_INCOME_RANGES:
                raise ValueError("请选择月收入区间")
            if credit_query_level not in cls.CREDIT_QUERY_LEVELS:
                raise ValueError("请选择近期征信查询情况")
            has_financing_need = cls._bool_value(payload.get("has_financing_need"))
            amount_text = str(payload.get("expected_financing_amount_wan") or "").strip()
            try:
                expected_amount = float(amount_text) * 10_000 if amount_text else None
            except ValueError as exc:
                raise ValueError("请填写正确的期望融资金额") from exc
            if expected_amount is not None and expected_amount < 0:
                raise ValueError("期望融资金额不能小于0")
            expected_time = str(payload.get("expected_financing_time") or "").strip()
            if expected_time and expected_time not in cls.FINANCING_TIME_VALUES:
                raise ValueError("请选择有效的期望时间")
            customer_payload.update({
                "city": str(payload.get("city") or "").strip()[:128] or None,
                "occupation_type": occupation_type,
                "monthly_income_range": income_range,
                "has_social_security": cls._bool_value(payload.get("has_social_security")),
                "has_housing_fund": cls._bool_value(payload.get("has_housing_fund")),
                "has_property": cls._bool_value(payload.get("has_property")),
                "has_credit_card": cls._bool_value(payload.get("has_credit_card")),
                "has_online_loans": cls._bool_value(
                    payload.get("individual_has_online_loans", payload.get("has_online_loans"))
                ),
                "credit_query_level": credit_query_level,
                "has_financing_need": has_financing_need,
                "expected_financing_amount": expected_amount,
                "financing_purpose": str(payload.get("financing_purpose") or "").strip()[:255] or None,
                "expected_financing_time": expected_time or None,
                "financing_need": "有融资需求" if has_financing_need == 1 else "暂无需求" if has_financing_need == 0 else "不确定",
            })

        has_loan = str(payload.get("has_loan") or "").strip()
        if has_loan not in ("有", "没有"):
            raise ValueError("请选择当前是否有贷款")
        if has_loan == "没有":
            return customer_payload, has_loan, [], str(payload.get("confirm_all_loans_closed") or "") == "1"

        raw_loans = payload.get("loans") or []
        if not isinstance(raw_loans, list) or not raw_loans:
            raise ValueError("请至少填写一笔贷款")
        if len(raw_loans) > cls.MAX_PUBLIC_LOANS:
            raise ValueError("最多可登记10笔贷款")
        normalized_loans = []
        seen_ids = set()
        for index, raw in enumerate(raw_loans, 1):
            raw_id = str(raw.get("loan_id") or "").strip()
            try:
                loan_id = int(raw_id) if raw_id else None
            except ValueError:
                raise ValueError(f"贷款{index}编号无效")
            if loan_id is not None and (loan_id <= 0 or loan_id in seen_ids):
                raise ValueError(f"贷款{index}编号无效或重复")
            if loan_id is not None:
                seen_ids.add(loan_id)
            bank_name = str(raw.get("bank_name") or "").strip()
            product_name = str(raw.get("product_name") or "").strip()[:255] or None
            amount_text = str(raw.get("loan_amount_wan") or "").strip()
            expire_text = str(raw.get("expire_date") or "").strip()
            repayment_type = str(raw.get("repayment_type") or "不确定").strip()
            status = str(raw.get("status") or "正常").strip()
            if not bank_name or len(bank_name) > 255:
                raise ValueError(f"请填写贷款{index}的贷款银行")
            try:
                amount = float(amount_text) * 10_000
            except (TypeError, ValueError):
                raise ValueError(f"请填写贷款{index}的正确金额")
            if amount <= 0:
                raise ValueError(f"贷款{index}金额必须大于0")
            try:
                date.fromisoformat(expire_text)
            except ValueError:
                raise ValueError(f"请选择贷款{index}的到期日")
            if repayment_type not in cls.REPAYMENT_TYPES:
                raise ValueError(f"贷款{index}还款方式无效")
            if status not in cls.LOAN_STATUSES:
                raise ValueError(f"贷款{index}状态无效")
            normalized_loans.append({
                "loan_id": loan_id, "bank_name": bank_name, "product_name": product_name,
                "loan_amount": amount, "loan_balance": 0 if status in cls.CLOSED_LOAN_STATUSES else amount,
                "expire_date": expire_text, "repayment_type": repayment_type, "status": status,
            })
        return customer_payload, has_loan, normalized_loans, False

    @classmethod
    def _sync_registration_loans(
        cls, customer_id: int, has_loan: str, loans: list[dict], confirm_all_closed: bool,
    ) -> list[int]:
        """原位更新已有贷款、插入新贷款；不删除、不替换既有记录。"""
        p = get_placeholder()
        now = cls._now()
        conn = get_db()
        try:
            existing_rows = [dict(row) for row in conn.execute(
                f"SELECT * FROM cultivation_loans WHERE customer_id={p} AND is_active=1 ORDER BY id",
                (customer_id,),
            ).fetchall()]
            existing_by_id = {int(row["id"]): row for row in existing_rows}
            submitted_ids = {int(loan["loan_id"]) for loan in loans if loan.get("loan_id") is not None}
            unknown_ids = submitted_ids.difference(existing_by_id)
            if unknown_ids:
                raise ValueError("贷款记录不存在或不属于当前客户")

            if has_loan == "没有":
                open_rows = [row for row in existing_rows if row.get("status") not in cls.CLOSED_LOAN_STATUSES]
                if open_rows and not confirm_all_closed:
                    raise ValueError(f"您当前档案中存在{len(open_rows)}笔贷款，请确认全部已结清后再保存。")
                if open_rows:
                    open_ids = [int(row["id"]) for row in open_rows]
                    placeholders = ",".join([p] * len(open_ids))
                    conn.execute(
                        f"""UPDATE cultivation_loans SET status={p},loan_balance=0,updated_at={p}
                        WHERE customer_id={p} AND id IN ({placeholders})""",
                        ("已结清", now, customer_id, *open_ids),
                    )
                conn.commit()
                return [int(row["id"]) for row in existing_rows]

            result_ids: list[int] = []
            for loan in loans:
                values = (
                    loan["bank_name"], loan.get("product_name"), loan["loan_amount"],
                    loan["loan_balance"], loan["expire_date"], loan["repayment_type"],
                    loan["status"], now,
                )
                if loan.get("loan_id") is not None:
                    loan_id = int(loan["loan_id"])
                    conn.execute(
                        f"""UPDATE cultivation_loans SET bank_name={p},product_name={p},loan_amount={p},
                        loan_balance={p},expire_date={p},repayment_type={p},status={p},updated_at={p}
                        WHERE id={p} AND customer_id={p} AND is_active=1""",
                        (*values, loan_id, customer_id),
                    )
                else:
                    cursor = conn.execute(
                        f"""INSERT INTO cultivation_loans
                        (customer_id,bank_name,product_name,loan_amount,loan_balance,expire_date,repayment_type,status)
                        VALUES ({','.join([p] * 8)})""",
                        (customer_id, loan["bank_name"], loan.get("product_name"), loan["loan_amount"],
                         loan["loan_balance"], loan["expire_date"], loan["repayment_type"], loan["status"]),
                    )
                    loan_id = int(get_lastrowid(cursor))
                    CustomerCultivationService._event(
                        conn, customer_id, "loan_created", {"loan_id": loan_id, "bank_name": loan["bank_name"]}
                    )
                result_ids.append(loan_id)
            conn.commit()
            return result_ids
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @classmethod
    def submit_registration(cls, token: str, payload: dict) -> dict:
        user = cls.resolve_registration_token(token)
        if not user:
            raise ValueError("登记链接已失效，请返回公众号回复“建档”重新获取。")
        customer_payload, has_loan, loan_payloads, confirm_all_closed = cls._normalize_form(payload)
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
                if customer_payload["profile_type"] == "individual":
                    customer = cls._row(
                        conn.execute(
                            f"""SELECT * FROM cultivation_customers
                            WHERE profile_type='individual' AND legal_person={p} AND phone={p}
                            AND is_active=1 ORDER BY id LIMIT 1""",
                            (customer_payload["legal_person"], customer_payload["phone"]),
                        ).fetchone()
                    )
                else:
                    customer = cls._row(
                        conn.execute(
                            f"""SELECT * FROM cultivation_customers
                            WHERE COALESCE(profile_type,'company')='company' AND company_name={p} AND phone={p}
                            AND is_active=1 ORDER BY id LIMIT 1""",
                            (customer_payload["company_name"], customer_payload["phone"]),
                        ).fetchone()
                    )
        finally:
            conn.close()

        is_update = bool(customer)
        if customer and payload.get("_legacy_single_loan") and len(loan_payloads) == 1 and loan_payloads[0].get("loan_id") is None:
            conn = get_db()
            try:
                legacy_loan = conn.execute(
                    f"""SELECT id FROM cultivation_loans WHERE customer_id={p} AND is_active=1
                    AND product_name={p} ORDER BY id LIMIT 1""",
                    (customer["id"], "公众号登记贷款"),
                ).fetchone()
            finally:
                conn.close()
            if legacy_loan:
                loan_payloads[0]["loan_id"] = int(legacy_loan["id"])
        if not customer and any(loan.get("loan_id") is not None for loan in loan_payloads):
            raise ValueError("新建档案不能引用已有贷款")
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

        loan_ids = cls._sync_registration_loans(
            customer_id, has_loan, loan_payloads, confirm_all_closed
        )
        registration_loan_id = loan_ids[0] if loan_ids else None

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
        CustomerCultivationService.refresh_customer(customer_id, create_task=has_loan == "有")
        logger.info(
            "[cultivation-wechat-register-success] wechat_user_id=%s customer_id=%s mode=%s loan_count=%s",
            user["id"], customer_id, "updated" if is_update else "created", len(loan_ids),
        )
        return {
            "customer_id": customer_id,
            "registration_loan_id": registration_loan_id,
            "loan_ids": loan_ids,
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
