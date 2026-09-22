import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch

import database
from services.cultivation_schema import init_cultivation_tables
from services.cultivation_service import CustomerCultivationService
from services.cultivation_wechat_reminder_service import CultivationWechatReminderService
from wechat_api.client import WechatPublishError, send_customer_text_message


class CultivationWechatReminderTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir.name, "wechat-reminders.db")
        conn = database.get_db()
        conn.executescript(
            """
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '', summary TEXT,
                review_status TEXT, publish_status TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE advisors (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            );
            INSERT INTO advisors(name) VALUES ('测试顾问');
            """
        )
        conn.commit()
        conn.close()
        self.assertTrue(init_cultivation_tables())

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _customer_with_loan(self, days: int, company="提醒测试企业"):
        customer_id = CustomerCultivationService.create_customer(
            {"company_name": company, "legal_person": "周总", "phone": "13800000000", "industry": "科技"}
        )
        loan_id = CustomerCultivationService.add_loan(
            customer_id,
            {
                "bank_name": "建设银行",
                "product_name": "经营贷",
                "loan_amount": 2_000_000,
                "loan_balance": 2_000_000,
                "expire_date": (date.today() + timedelta(days=days)).isoformat(),
                "repayment_type": "先息后本",
                "status": "正常",
            },
        )
        return customer_id, loan_id

    def _bind_wechat(self, customer_id: int, *, active=True, hours_ago=1):
        interaction = datetime.now() - timedelta(hours=hours_ago)
        conn = database.get_db()
        conn.execute(
            """INSERT INTO cultivation_wechat_users
            (openid,subscribe_status,subscribe_time,last_interaction_at,customer_id)
            VALUES (?,?,?,?,?)""",
            (f"openid-{customer_id}", 1 if active else 0, datetime.now(), interaction, customer_id),
        )
        conn.commit()
        conn.close()

    def test_due_today_creates_followup_and_sends_once(self):
        customer_id, loan_id = self._customer_with_loan(0)
        self._bind_wechat(customer_id)
        with patch(
            "services.cultivation_wechat_reminder_service.send_customer_text_message",
            return_value={"errcode": 0, "errmsg": "ok"},
        ) as sender:
            first = CustomerCultivationService.scan_cultivation_customers(today=date.today())
            second = CustomerCultivationService.scan_cultivation_customers(today=date.today())

        self.assertEqual(sender.call_count, 1)
        self.assertEqual(first["wechat_reminders_sent"], 1)
        self.assertEqual(second["wechat_reminders_sent"], 0)
        conn = database.get_db()
        reminder = conn.execute(
            "SELECT * FROM cultivation_wechat_reminders WHERE customer_id=? AND loan_id=?",
            (customer_id, loan_id),
        ).fetchone()
        followups = conn.execute(
            "SELECT * FROM cultivation_followups WHERE customer_id=? AND loan_id=? AND trigger_type='due_today'",
            (customer_id, loan_id),
        ).fetchall()
        conn.close()
        self.assertEqual(reminder["reminder_type"], "loan_due_today")
        self.assertEqual(reminder["status"], "sent")
        self.assertIsNotNone(reminder["sent_at"])
        self.assertEqual(len(followups), 1)

    def test_platform_time_limit_becomes_manual_required_not_sent(self):
        customer_id, loan_id = self._customer_with_loan(15)
        self._bind_wechat(customer_id)
        error = WechatPublishError(
            "customer_message", "客服消息发送失败", errcode=45015, errmsg="response out of time limit"
        )
        with patch(
            "services.cultivation_wechat_reminder_service.send_customer_text_message",
            side_effect=error,
        ):
            CustomerCultivationService.scan_cultivation_customers(today=date.today())
        conn = database.get_db()
        reminder = conn.execute(
            "SELECT * FROM cultivation_wechat_reminders WHERE customer_id=? AND loan_id=?",
            (customer_id, loan_id),
        ).fetchone()
        conn.close()
        self.assertEqual(reminder["status"], "manual_required")
        self.assertEqual(reminder["delivery_reason"], "wechat_window_or_permission_limited")
        self.assertNotEqual(reminder["status"], "sent")

    def test_missing_openid_and_expired_window_degrade_without_api_call(self):
        unbound_customer, unbound_loan = self._customer_with_loan(30, "未绑定企业")
        old_customer, old_loan = self._customer_with_loan(60, "超时企业")
        self._bind_wechat(old_customer, hours_ago=49)
        with patch("services.cultivation_wechat_reminder_service.send_customer_text_message") as sender:
            CustomerCultivationService.scan_cultivation_customers(today=date.today())
        self.assertFalse(sender.called)
        conn = database.get_db()
        unbound = conn.execute(
            "SELECT * FROM cultivation_wechat_reminders WHERE customer_id=? AND loan_id=?",
            (unbound_customer, unbound_loan),
        ).fetchone()
        old = conn.execute(
            "SELECT * FROM cultivation_wechat_reminders WHERE customer_id=? AND loan_id=?",
            (old_customer, old_loan),
        ).fetchone()
        conn.close()
        self.assertEqual((unbound["status"], unbound["delivery_reason"]), ("manual_required", "openid_not_bound"))
        self.assertEqual((old["status"], old["delivery_reason"]), ("manual_required", "interaction_window_expired"))

    def test_node_selection_and_message_copy(self):
        expected = {
            61: None,
            60: "loan_60_days",
            30: "loan_30_days",
            15: "loan_15_days",
            0: "loan_due_today",
            -1: "loan_overdue",
        }
        loan = {"bank_name": "建设银行", "loan_amount": 2_000_000, "expire_date": "2026-09-22"}
        for days, reminder_type in expected.items():
            with self.subTest(days=days):
                self.assertEqual(CultivationWechatReminderService.reminder_type_for_days(days), reminder_type)
                if reminder_type:
                    message = CultivationWechatReminderService.build_message(reminder_type, loan)
                    self.assertIn("建设银行", message)
                    self.assertIn("200.00万元", message)
                    self.assertIn("2026-09-22", message)
                    self.assertIn("回复“咨询”", message)
        self.assertIn("今天到期", CultivationWechatReminderService.build_message("loan_due_today", loan))
        self.assertIn("超过原登记到期日", CultivationWechatReminderService.build_message("loan_overdue", loan))

    def test_unexpected_api_error_is_failed(self):
        customer_id, loan_id = self._customer_with_loan(30)
        self._bind_wechat(customer_id)
        with patch(
            "services.cultivation_wechat_reminder_service.send_customer_text_message",
            side_effect=RuntimeError("network down"),
        ):
            CustomerCultivationService.scan_cultivation_customers(today=date.today())
        conn = database.get_db()
        reminder = conn.execute(
            "SELECT * FROM cultivation_wechat_reminders WHERE customer_id=? AND loan_id=?",
            (customer_id, loan_id),
        ).fetchone()
        conn.close()
        self.assertEqual(reminder["status"], "failed")
        self.assertEqual(reminder["delivery_reason"], "send_failed")

    def test_status_labels_never_expose_internal_values(self):
        self.assertEqual(
            CultivationWechatReminderService.format_status("manual_required", "openid_not_bound")["label"],
            "未绑定公众号",
        )
        self.assertEqual(CultivationWechatReminderService.format_status("sent", None)["label"], "已发送")
        self.assertEqual(CultivationWechatReminderService.format_status("mystery", None)["label"], "状态待确认")

    @patch("wechat_api.client._http_post")
    @patch("wechat_api.client.get_access_token", return_value="token-value")
    def test_customer_text_sender_uses_existing_client_and_requires_errcode_zero(self, _token, http_post):
        http_post.return_value = Mock(json=lambda: {"errcode": 0, "errmsg": "ok"})
        result = send_customer_text_message("openid-test", "提醒内容")
        self.assertEqual(result["errcode"], 0)
        kwargs = http_post.call_args.kwargs
        payload = json.loads(kwargs["data"].decode("utf-8"))
        self.assertEqual(payload, {"touser": "openid-test", "msgtype": "text", "text": {"content": "提醒内容"}})
        self.assertIn("/message/custom/send?access_token=", http_post.call_args.args[0])
        http_post.return_value = Mock(json=lambda: {"errcode": 45015, "errmsg": "response out of time limit"})
        with self.assertRaises(WechatPublishError):
            send_customer_text_message("openid-test", "提醒内容")


if __name__ == "__main__":
    unittest.main()
