import os
import tempfile
import unittest

import database
from services.cultivation_schema import init_cultivation_tables
from web_ui.app import app


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


if __name__ == "__main__":
    unittest.main()
