import os
import tempfile
import unittest
from datetime import date, datetime, timedelta

import database
from services.cultivation_schema import init_cultivation_tables
from services.cultivation_service import CustomerCultivationService as Service
from web_ui.app import app
from web_ui.cultivation_routes import (
    format_article_status,
    format_cultivation_tag_type,
    format_followup_trigger,
)


class CultivationRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir.name, "routes.db")
        conn = database.get_db()
        conn.executescript("""
        CREATE TABLE articles (id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,content TEXT NOT NULL DEFAULT '',summary TEXT,review_status TEXT DEFAULT 'approved',publish_status TEXT DEFAULT 'published',created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE advisors (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,is_active INTEGER DEFAULT 1);
        INSERT INTO advisors(name) VALUES ('测试顾问'); INSERT INTO articles(title,content) VALUES ('续贷文章','正文');
        """); conn.commit(); conn.close()
        init_cultivation_tables()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def login(self):
        with self.client.session_transaction() as session:
            session["logged_in"] = True; session["username"] = "admin"; session["role"] = "admin"

    def test_login_required_and_navigation_pages(self):
        self.assertEqual(self.client.get("/cultivation").status_code, 302)
        self.login()
        for path in ("/cultivation", "/cultivation/customers", "/cultivation/loans", "/cultivation/followups", "/cultivation/tags", "/cultivation/content"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn("融资客户培育".encode(), response.data)

    def test_customer_loan_followup_flow(self):
        self.login()
        response = self.client.post("/cultivation/customers/new", data={
            "company_name":"上海测试科技有限公司", "legal_person":"张总", "phone":"13800000000",
            "industry":"科技", "advisor_id":"1", "credit_card_usage":"75", "credit_query_count":"41",
            "bank_count":"5", "has_collateral":"0",
        })
        self.assertEqual(response.status_code, 302)
        customer_id = int(response.headers["Location"].rstrip("/").split("/")[-1])
        response = self.client.post(f"/cultivation/customers/{customer_id}/loans/new", data={
            "bank_name":"建行", "product_name":"科技贷", "loan_amount":"3000000", "loan_balance":"3000000",
            "expire_date":"2099-12-31", "repayment_type":"先息后本", "status":"正常",
        })
        self.assertEqual(response.status_code, 302)
        detail = self.client.get(f"/cultivation/customers/{customer_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("上海测试科技有限公司".encode(), detail.data)
        self.assertIn("建行".encode(), detail.data)

    def test_article_status_formatter_covers_real_and_legacy_states(self):
        cases = [
            (("approved", "wechat_draft", ""), "已审核 · 已推送草稿箱", "bg-info text-dark"),
            (("approved", "not_ready", ""), "已审核 · 待推送", "bg-warning text-dark"),
            (("pending_review", "not_ready", ""), "待审核", "bg-warning text-dark"),
            (("rejected", "not_ready", ""), "审核未通过", "bg-danger"),
            (("approved", "published", ""), "已发布", "bg-success"),
            (("approved", "failed", ""), "推送失败", "bg-danger"),
            (("", "", "approved"), "已审核 · 待推送", "bg-warning text-dark"),
            (("unexpected", "internal_state", "mystery"), "状态待确认", "bg-secondary"),
        ]
        for inputs, label, badge in cases:
            with self.subTest(inputs=inputs):
                self.assertEqual(format_article_status(*inputs), {"label": label, "badge": badge})

    def test_other_internal_enums_are_never_echoed(self):
        self.assertEqual(format_followup_trigger("15_day"), "到期前15天紧急提醒")
        self.assertEqual(format_followup_trigger("manual_202608180900"), "人工跟进")
        self.assertEqual(format_followup_trigger("internal_trigger"), "触发原因待确认")
        self.assertEqual(format_cultivation_tag_type("risk"), "风险")
        self.assertEqual(format_cultivation_tag_type("internal_tag"), "标签类型待确认")

    def test_content_page_renders_only_chinese_article_statuses(self):
        self.login()
        conn = database.get_db()
        conn.execute("UPDATE articles SET review_status=?,publish_status=? WHERE id=1", ("approved", "wechat_draft"))
        conn.execute(
            "INSERT INTO articles(title,content,review_status,publish_status) VALUES (?,?,?,?)",
            ("未知状态文章", "正文", "unexpected", "internal_state"),
        )
        conn.commit(); conn.close()

        response = self.client.get("/cultivation/content")
        self.assertEqual(response.status_code, 200)
        page_text = response.get_data(as_text=True)
        self.assertIn("已审核 · 已推送草稿箱", page_text)
        self.assertIn("状态待确认", page_text)
        self.assertNotIn(">approved<", page_text)
        self.assertNotIn(">wechat_draft<", page_text)
        self.assertNotIn(">internal_state<", page_text)

    def test_next_followup_save_feedback_and_page_display(self):
        self.login()
        customer_id = Service.create_customer({
            "company_name": "下次跟进测试客户", "legal_person": "李总", "phone": "13900000000",
            "industry": "制造", "advisor_id": 1,
        })
        Service.add_loan(customer_id, {
            "bank_name": "测试银行", "product_name": "续贷产品", "loan_amount": 1000000,
            "loan_balance": 1000000, "start_date": date.today().isoformat(),
            "expire_date": (date.today() + timedelta(days=10)).isoformat(),
            "repayment_type": "先息后本", "status": "正常",
        })
        conn = database.get_db()
        source_id = conn.execute("SELECT id FROM cultivation_followups WHERE customer_id=?", (customer_id,)).fetchone()[0]
        conn.close()
        scheduled = datetime.combine(date.today() + timedelta(days=2), datetime.min.time()).replace(hour=10, minute=30)
        display_value = scheduled.strftime("%Y-%m-%d %H:%M")

        response = self.client.post(
            f"/cultivation/followups/{source_id}/update",
            data={
                "status": "已联系", "contact_method": "电话", "followup_result": "已联系",
                "followup_note": "月底再确认", "next_followup_at": scheduled.strftime("%Y-%m-%dT%H:%M"),
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(f"跟进记录已保存，下次跟进：{display_value}".encode(), response.data)

        future_page = self.client.get("/cultivation/followups?view=future")
        self.assertIn("下次跟进测试客户".encode(), future_page.data)
        self.assertIn(display_value.encode(), future_page.data)
        self.assertIn("人工后续跟进".encode(), future_page.data)

        detail_page = self.client.get(f"/cultivation/customers/{customer_id}")
        self.assertIn("下次跟进".encode(), detail_page.data)
        self.assertIn(display_value.encode(), detail_page.data)

        conn = database.get_db()
        conn.execute(
            "UPDATE cultivation_followups SET due_date=? WHERE trigger_type=?",
            (date.today().isoformat(), f"manual_followup:{source_id}"),
        )
        conn.commit(); conn.close()
        Service.scan_cultivation_customers(today=date.today())
        today_page = self.client.get("/cultivation/followups?view=today")
        self.assertIn("下次跟进测试客户".encode(), today_page.data)

        conn = database.get_db()
        conn.execute(
            "UPDATE cultivation_followups SET due_date=? WHERE trigger_type=?",
            ((date.today() - timedelta(days=1)).isoformat(), f"manual_followup:{source_id}"),
        )
        conn.commit(); conn.close()
        overdue_page = self.client.get("/cultivation/followups?view=overdue")
        self.assertIn("下次跟进测试客户".encode(), overdue_page.data)


if __name__ == "__main__":
    unittest.main()
