"""贷款到期节点的微信提醒决策、投递与审计。"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from database import get_db, get_lastrowid, get_placeholder, is_mysql
from wechat_api.client import WechatPublishError, send_customer_text_message

logger = logging.getLogger(__name__)


class CultivationWechatReminderService:
    MANUAL_ERRCODES = {43004, 45015, 45047, 48001}
    STATUS_DISPLAYS = {
        "not_required": {
            "label": "无需提醒", "badge": "bg-light text-dark",
            "title": "当前贷款无需发送微信到期提醒",
        },
        "pending": {
            "label": "待发送", "badge": "bg-info text-dark",
            "title": "微信提醒已生成，等待发送",
        },
        "sent": {
            "label": "已发送", "badge": "bg-success",
            "title": "已通过公众号发送",
        },
        "manual_required": {
            "label": "需人工联系", "badge": "bg-warning text-dark",
            "title": "微信当前无法自动触达，请销售人工电话或微信联系客户",
        },
        "failed": {
            "label": "发送失败", "badge": "bg-danger",
            "title": "微信接口发送失败",
        },
        "not_created": {
            "label": "未生成提醒", "badge": "bg-secondary",
            "title": "该贷款尚未生成微信提醒记录",
        },
        "not_bound": {
            "label": "未绑定公众号", "badge": "bg-secondary",
            "title": "客户尚未绑定公众号 OpenID，请人工联系",
        },
    }
    REMINDER_ACTIONS = {
        "loan_60_days": ("60_day", "medium", "联系客户确认续贷需求"),
        "loan_30_days": ("30_day", "high", "尽快完成续贷/转贷方案评估"),
        "loan_15_days": ("15_day", "urgent", "立即人工介入，确认续贷及资金安排"),
        "loan_due_today": ("due_today", "urgent", "今日到期，请立即确认还款或续贷安排"),
        "loan_overdue": ("overdue", "urgent", "已超过登记到期日，请确认贷款最新状态并人工联系"),
    }

    @staticmethod
    def _row(row):
        return dict(row) if row is not None else None

    @staticmethod
    def _parse_datetime(value) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        try:
            return datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def reminder_type_for_days(days_to_expire: int | None) -> str | None:
        if days_to_expire is None or days_to_expire > 60:
            return None
        if days_to_expire < 0:
            return "loan_overdue"
        if days_to_expire == 0:
            return "loan_due_today"
        if days_to_expire <= 15:
            return "loan_15_days"
        if days_to_expire <= 30:
            return "loan_30_days"
        return "loan_60_days"

    @staticmethod
    def build_message(reminder_type: str, loan: dict) -> str:
        bank = str(loan.get("bank_name") or "未填写")
        amount = float(loan.get("loan_amount") or 0) / 10_000
        expire_date = str(loan.get("expire_date") or "")[:10]
        detail = f"银行：{bank}\n金额：{amount:.2f}万元\n到期日：{expire_date}"
        messages = {
            "loan_60_days": (
                "【融资管家·贷款到期提醒】\n\n您的贷款还有60天左右到期。\n\n"
                f"贷款{detail}\n\n建议现在开始确认续贷政策，并提前准备流水、征信和相关材料。"
                "\n\n如需评估续贷方案，可回复“咨询”联系融资顾问。"
            ),
            "loan_30_days": (
                "【融资管家·重要提醒】\n\n您的贷款将在30天内到期：\n\n"
                f"{detail}\n\n建议尽快确认续贷、转贷或还款资金安排，避免临近到期被动处理。"
                "\n\n需要帮助，请回复“咨询”。"
            ),
            "loan_15_days": (
                "【融资管家·紧急提醒】\n\n您的贷款距离到期只剩约15天：\n\n"
                f"{detail}\n\n建议立即确认续贷及还款资金安排。\n\n如尚未确定方案，请回复“咨询”。"
            ),
            "loan_due_today": (
                "【融资管家·今日到期提醒】\n\n您登记的一笔贷款今天到期：\n\n"
                f"{detail}\n\n请确认还款或续贷安排。\n\n如需协助，请回复“咨询”。"
            ),
            "loan_overdue": (
                "【融资管家·贷款状态提醒】\n\n系统显示您登记的一笔贷款已超过原登记到期日。\n\n"
                f"{detail.replace('到期日：', '原到期日：')}\n\n如您已经续贷、结清或日期发生变化，请及时更新融资档案。"
                "\n\n如需协助，可回复“咨询”。"
            ),
        }
        if reminder_type not in messages:
            raise ValueError("未知贷款提醒节点")
        return messages[reminder_type]

    @classmethod
    def format_status(cls, status: str | None, reason: str | None = None) -> dict[str, str]:
        if reason == "openid_not_bound":
            return dict(cls.STATUS_DISPLAYS["not_bound"])
        display = cls.STATUS_DISPLAYS.get(str(status or ""))
        if display:
            return dict(display)
        return {"label": "状态待确认", "badge": "bg-secondary", "title": "提醒状态需要后台确认"}

    @classmethod
    def _has_openid_binding(cls, conn, loan_id: int | None, customer_id: int | None = None) -> bool:
        p = get_placeholder()
        resolved_customer_id = customer_id
        if resolved_customer_id is None and loan_id:
            loan = conn.execute(f"SELECT customer_id FROM cultivation_loans WHERE id={p}", (loan_id,)).fetchone()
            resolved_customer_id = int(loan["customer_id"]) if loan else None
        if resolved_customer_id is None:
            return False
        row = conn.execute(
            f"""SELECT id FROM cultivation_wechat_users
            WHERE customer_id={p} AND openid IS NOT NULL AND openid<>''
            ORDER BY id DESC LIMIT 1""",
            (resolved_customer_id,),
        ).fetchone()
        return row is not None

    @staticmethod
    def reminder_type_label(reminder_type: str | None) -> str:
        return {
            "loan_60_days": "到期前60天",
            "loan_30_days": "到期前30天",
            "loan_15_days": "到期前15天",
            "loan_due_today": "到期当天",
            "loan_overdue": "已逾期",
        }.get(str(reminder_type or ""), "提醒节点待确认")

    @classmethod
    def display_for_followup(
        cls, conn, followup_id: int, loan_id: int | None,
        days_to_expire: int | None, customer_id: int | None = None,
    ) -> dict[str, str]:
        if not cls._has_openid_binding(conn, loan_id, customer_id):
            return dict(cls.STATUS_DISPLAYS["not_bound"])
        p = get_placeholder()
        row = cls._row(conn.execute(
            f"SELECT status,delivery_reason FROM cultivation_wechat_reminders WHERE followup_id={p} ORDER BY id DESC LIMIT 1",
            (followup_id,),
        ).fetchone())
        if row:
            return cls.format_status(row.get("status"), row.get("delivery_reason"))
        return cls.display_for_loan(conn, loan_id, days_to_expire, customer_id)

    @classmethod
    def _ensure_followup(cls, conn, customer_id: int, loan: dict, reminder_type: str, today: date) -> int:
        trigger_type, priority, action = cls.REMINDER_ACTIONS[reminder_type]
        p = get_placeholder()
        existing = conn.execute(
            f"SELECT id FROM cultivation_followups WHERE customer_id={p} AND loan_id={p} AND trigger_type={p}",
            (customer_id, loan["id"], trigger_type),
        ).fetchone()
        if existing:
            return int(existing["id"])
        customer = cls._row(
            conn.execute(f"SELECT advisor_id FROM cultivation_customers WHERE id={p}", (customer_id,)).fetchone()
        )
        cursor = conn.execute(
            f"""INSERT INTO cultivation_followups
            (customer_id,loan_id,task_type,trigger_type,priority,due_date,advisor_id,status,followup_note)
            VALUES ({','.join([p] * 9)})""",
            (customer_id, loan["id"], "到期提醒", trigger_type, priority, today.isoformat(),
             customer.get("advisor_id") if customer else None, "待处理", action),
        )
        return int(get_lastrowid(cursor))

    @classmethod
    def _update_reminder(cls, reminder_id: int, status: str, reason: str, errcode=None, errmsg="") -> None:
        p = get_placeholder()
        now_sql = "CURRENT_TIMESTAMP" if is_mysql() else "datetime('now','localtime')"
        sent_sql = now_sql if status == "sent" else "NULL"
        conn = get_db()
        try:
            conn.execute(
                f"""UPDATE cultivation_wechat_reminders SET status={p},delivery_reason={p},
                wechat_errcode={p},wechat_errmsg={p},attempted_at={now_sql},sent_at={sent_sql},updated_at={now_sql}
                WHERE id={p}""",
                (status, reason, str(errcode) if errcode is not None else None, str(errmsg or "")[:1000], reminder_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @classmethod
    def process_loan(cls, customer_id: int, loan: dict, today: date | None = None) -> dict:
        today = today or date.today()
        expire_date = loan.get("expire_date")
        parsed_expire = expire_date if isinstance(expire_date, date) else date.fromisoformat(str(expire_date)[:10])
        reminder_type = cls.reminder_type_for_days((parsed_expire - today).days)
        if not reminder_type:
            return {"created": False, "status": "not_required", "reminder_type": None}
        message = cls.build_message(reminder_type, loan)
        p = get_placeholder()
        conn = get_db()
        try:
            existing = cls._row(
                conn.execute(
                    f"""SELECT * FROM cultivation_wechat_reminders
                    WHERE customer_id={p} AND loan_id={p} AND reminder_type={p}""",
                    (customer_id, loan["id"], reminder_type),
                ).fetchone()
            )
            if existing:
                return {"created": False, "status": existing["status"], "reminder_type": reminder_type, "id": existing["id"]}
            followup_id = cls._ensure_followup(conn, customer_id, loan, reminder_type, today)
            cursor = conn.execute(
                f"""INSERT INTO cultivation_wechat_reminders
                (customer_id,loan_id,followup_id,reminder_type,trigger_date,status,message_content)
                VALUES ({','.join([p] * 7)})""",
                (customer_id, loan["id"], followup_id, reminder_type, today.isoformat(), "pending", message),
            )
            reminder_id = int(get_lastrowid(cursor))
            conn.commit()
            logger.info("[wechat-reminder-created] reminder_id=%s customer_id=%s loan_id=%s type=%s", reminder_id, customer_id, loan["id"], reminder_type)
            wechat_rows = [dict(row) for row in conn.execute(
                f"SELECT * FROM cultivation_wechat_users WHERE customer_id={p} ORDER BY subscribe_status DESC,updated_at DESC,id DESC",
                (customer_id,),
            ).fetchall()]
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        if not wechat_rows:
            cls._update_reminder(reminder_id, "manual_required", "openid_not_bound")
            logger.info("[wechat-reminder-manual-required] reminder_id=%s reason=openid_not_bound", reminder_id)
            return {"created": True, "status": "manual_required", "reminder_type": reminder_type, "id": reminder_id}
        wechat_user = next((row for row in wechat_rows if int(row.get("subscribe_status") or 0)), None)
        if not wechat_user:
            cls._update_reminder(reminder_id, "manual_required", "unsubscribed")
            logger.info("[wechat-reminder-manual-required] reminder_id=%s reason=unsubscribed", reminder_id)
            return {"created": True, "status": "manual_required", "reminder_type": reminder_type, "id": reminder_id}
        interaction_at = cls._parse_datetime(wechat_user.get("last_interaction_at") or wechat_user.get("subscribe_time"))
        if not interaction_at or interaction_at < datetime.now() - timedelta(hours=48):
            cls._update_reminder(reminder_id, "manual_required", "interaction_window_expired")
            logger.info("[wechat-reminder-manual-required] reminder_id=%s reason=interaction_window_expired", reminder_id)
            return {"created": True, "status": "manual_required", "reminder_type": reminder_type, "id": reminder_id}
        try:
            send_customer_text_message(wechat_user["openid"], message)
            cls._update_reminder(reminder_id, "sent", "api_confirmed")
            logger.info("[wechat-reminder-sent] reminder_id=%s customer_id=%s loan_id=%s", reminder_id, customer_id, loan["id"])
            return {"created": True, "status": "sent", "reminder_type": reminder_type, "id": reminder_id}
        except WechatPublishError as exc:
            if exc.errcode in cls.MANUAL_ERRCODES:
                cls._update_reminder(reminder_id, "manual_required", "wechat_window_or_permission_limited", exc.errcode, exc.errmsg)
                logger.info("[wechat-reminder-manual-required] reminder_id=%s errcode=%s", reminder_id, exc.errcode)
                return {"created": True, "status": "manual_required", "reminder_type": reminder_type, "id": reminder_id}
            cls._update_reminder(reminder_id, "failed", "send_failed", exc.errcode, exc.errmsg or str(exc))
        except Exception as exc:
            cls._update_reminder(reminder_id, "failed", "send_failed", None, str(exc))
        logger.error("[wechat-reminder-failed] reminder_id=%s customer_id=%s loan_id=%s", reminder_id, customer_id, loan["id"])
        return {"created": True, "status": "failed", "reminder_type": reminder_type, "id": reminder_id}

    @classmethod
    def display_for_loan(
        cls, conn, loan_id: int | None, days_to_expire: int | None = None,
        customer_id: int | None = None,
    ) -> dict[str, str]:
        if not cls._has_openid_binding(conn, loan_id, customer_id):
            return dict(cls.STATUS_DISPLAYS["not_bound"])
        if loan_id:
            p = get_placeholder()
            row = cls._row(conn.execute(
                f"SELECT status,delivery_reason FROM cultivation_wechat_reminders WHERE loan_id={p} ORDER BY id DESC LIMIT 1",
                (loan_id,),
            ).fetchone())
            if row:
                return cls.format_status(row.get("status"), row.get("delivery_reason"))
        return dict(cls.STATUS_DISPLAYS["not_created"])
