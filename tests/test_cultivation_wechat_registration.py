import hashlib
import os
import re
import tempfile
import unittest
from datetime import date, timedelta
import database
from services.cultivation_schema import init_cultivation_tables
from web_ui.app import app


class CultivationWechatRegistrationTestCase(unittest.TestCase):
    callback_token = "callback-test-token"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir.name, "wechat-registration.db")
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
            CREATE TABLE keyword_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT, keyword TEXT NOT NULL UNIQUE,
                reply_type TEXT DEFAULT 'text', reply_content TEXT NOT NULL,
                match_mode TEXT DEFAULT 'contain', priority INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            );
            INSERT INTO advisors(name) VALUES ('测试顾问');
            INSERT INTO keyword_replies(keyword,reply_content,match_mode,priority)
            VALUES ('额度', '这是已有关键词回复', 'contain', 10);
            """
        )
        conn.commit()
        conn.close()
        self.assertTrue(init_cultivation_tables())
        app.config.update(
            TESTING=True,
            WECHAT_CALLBACK_TOKEN=self.callback_token,
            CULTIVATION_REGISTER_URL="https://wechat.example.com/public/cultivation/register",
        )
        self.client = app.test_client()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _signature(self, timestamp="1720000000", nonce="nonce"):
        raw = "".join(sorted((self.callback_token, timestamp, nonce)))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _callback(self, xml, timestamp="1720000000", nonce="nonce"):
        signature = self._signature(timestamp, nonce)
        return self.client.post(
            f"/wechat/callback?timestamp={timestamp}&nonce={nonce}&signature={signature}",
            data=xml.encode("utf-8"),
            content_type="application/xml",
        )

    @staticmethod
    def _event_xml(event, openid="openid-test-user"):
        return f"""<xml><ToUserName>gh_test</ToUserName><FromUserName>{openid}</FromUserName>
        <CreateTime>1720000000</CreateTime><MsgType>event</MsgType><Event>{event}</Event></xml>"""

    @staticmethod
    def _text_xml(content, openid="openid-test-user"):
        return f"""<xml><ToUserName>gh_test</ToUserName><FromUserName>{openid}</FromUserName>
        <CreateTime>1720000000</CreateTime><MsgType>text</MsgType><Content>{content}</Content></xml>"""

    def _subscribe_and_token(self, openid="openid-test-user"):
        response = self._callback(self._event_xml("subscribe", openid))
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        match = re.search(r"https://wechat\.example\.com/public/cultivation/register\?token=([A-Za-z0-9_-]+)", text)
        self.assertIsNotNone(match, text)
        return response, match.group(1)

    def _valid_form(self, **overrides):
        data = {
            "company_name": "上海公众号测试科技有限公司",
            "legal_person": "张总",
            "phone": "13800000000",
            "industry": "科技",
            "annual_revenue_range": "500-2000万",
            "has_loan": "有",
            "bank_name": "建设银行",
            "loan_amount_wan": "260",
            "expire_date": (date.today() + timedelta(days=55)).isoformat(),
            "repayment_type": "先息后本",
            "cashflow_type": ["微信", "支付宝"],
            "credit_card_usage_range": "70%以上",
            "credit_query_count_range": "40次以上",
            "has_online_loans": "是",
            "has_collateral": "否",
            "tax_grade": "B",
            "financing_need": "续贷",
        }
        data.update(overrides)
        return data

    def test_01_callback_get_signature_verification(self):
        timestamp, nonce = "1720000000", "abc"
        response = self.client.get(
            f"/wechat/callback?timestamp={timestamp}&nonce={nonce}&signature={self._signature(timestamp, nonce)}&echostr=verified"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "verified")
        self.assertEqual(self.client.get("/wechat/callback?echostr=no").status_code, 403)

    def test_02_subscribe_returns_welcome_and_secure_registration_url(self):
        response, token = self._subscribe_and_token()
        text = response.get_data(as_text=True)
        self.assertIn("欢迎关注", text)
        self.assertIn("填写融资档案", text)
        registration_url = re.search(r"https://[^<\s]+", text).group(0)
        self.assertNotIn("openid", registration_url.lower())
        conn = database.get_db()
        row = conn.execute("SELECT * FROM cultivation_wechat_users WHERE openid=?", ("openid-test-user",)).fetchone()
        conn.close()
        self.assertEqual(row["subscribe_status"], 1)
        self.assertNotEqual(row["registration_token_hash"], token)
        self.assertEqual(row["registration_token_hash"], hashlib.sha256(token.encode()).hexdigest())

    def test_03_valid_and_invalid_registration_token_pages(self):
        _, token = self._subscribe_and_token()
        valid = self.client.get(f"/public/cultivation/register?token={token}")
        self.assertEqual(valid.status_code, 200)
        self.assertIn("融资档案登记".encode(), valid.data)
        self.assertEqual(valid.headers.get("Cache-Control"), "no-store")
        invalid = self.client.get("/public/cultivation/register?token=invalid")
        self.assertEqual(invalid.status_code, 200)
        self.assertIn("链接已失效".encode(), invalid.data)
        conn = database.get_db()
        conn.execute(
            "UPDATE cultivation_wechat_users SET token_expires_at=datetime('now','-1 minute')"
        )
        conn.commit()
        conn.close()
        expired = self.client.get(f"/public/cultivation/register?token={token}")
        self.assertIn("链接已失效".encode(), expired.data)

    def test_04_submit_creates_customer_association_loan_and_risk(self):
        _, token = self._subscribe_and_token()
        response = self.client.post(f"/public/cultivation/register?token={token}", data=self._valid_form())
        self.assertEqual(response.status_code, 200)
        self.assertIn("档案已建立".encode(), response.data)
        conn = database.get_db()
        user = conn.execute("SELECT * FROM cultivation_wechat_users WHERE openid=?", ("openid-test-user",)).fetchone()
        customer = conn.execute("SELECT * FROM cultivation_customers WHERE id=?", (user["customer_id"],)).fetchone()
        loan = conn.execute("SELECT * FROM cultivation_loans WHERE id=?", (user["registration_loan_id"],)).fetchone()
        tags = {row[0] for row in conn.execute("SELECT tag_name FROM cultivation_tags WHERE customer_id=?", (customer["id"],)).fetchall()}
        events = {row[0] for row in conn.execute("SELECT event_type FROM cultivation_events WHERE customer_id=?", (customer["id"],)).fetchall()}
        conn.close()
        self.assertEqual(customer["source"], "wechat_official_account")
        self.assertEqual(customer["risk_level"], "高风险")
        self.assertEqual(float(loan["loan_amount"]), 2600000)
        self.assertEqual(loan["customer_id"], customer["id"])
        self.assertIn("信用卡高使用率", tags)
        self.assertIn("征信查询高风险", tags)
        self.assertIn("register_completed", events)
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["username"] = "admin"
            session["role"] = "admin"
        detail = self.client.get(f"/cultivation/customers/{customer['id']}")
        self.assertIn("微信公众号".encode(), detail.data)
        self.assertNotIn(b">wechat_official_account<", detail.data)

    def test_05_repeat_submit_updates_same_customer_and_same_registration_loan(self):
        _, token = self._subscribe_and_token()
        self.client.post(f"/public/cultivation/register?token={token}", data=self._valid_form())
        response = self.client.post(
            f"/public/cultivation/register?token={token}",
            data=self._valid_form(legal_person="李总", loan_amount_wan="300"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("档案已更新".encode(), response.data)
        conn = database.get_db()
        customer_count = conn.execute("SELECT COUNT(*) FROM cultivation_customers").fetchone()[0]
        loan_count = conn.execute("SELECT COUNT(*) FROM cultivation_loans").fetchone()[0]
        customer = conn.execute("SELECT * FROM cultivation_customers").fetchone()
        loan = conn.execute("SELECT * FROM cultivation_loans").fetchone()
        conn.close()
        self.assertEqual(customer_count, 1)
        self.assertEqual(loan_count, 1)
        self.assertEqual(customer["legal_person"], "李总")
        self.assertEqual(float(loan["loan_amount"]), 3000000)

    def test_06_company_and_phone_are_weak_deduplication_key(self):
        _, first_token = self._subscribe_and_token("openid-first")
        self.client.post(f"/public/cultivation/register?token={first_token}", data=self._valid_form())
        _, second_token = self._subscribe_and_token("openid-second")
        self.client.post(f"/public/cultivation/register?token={second_token}", data=self._valid_form())
        conn = database.get_db()
        customer_count = conn.execute("SELECT COUNT(*) FROM cultivation_customers").fetchone()[0]
        loan_count = conn.execute("SELECT COUNT(*) FROM cultivation_loans").fetchone()[0]
        customer_ids = {row[0] for row in conn.execute("SELECT customer_id FROM cultivation_wechat_users").fetchall()}
        conn.close()
        self.assertEqual(customer_count, 1)
        self.assertEqual(loan_count, 1)
        self.assertEqual(len(customer_ids), 1)

    def test_07_no_loan_submission_does_not_create_loan(self):
        _, token = self._subscribe_and_token("openid-no-loan")
        response = self.client.post(
            f"/public/cultivation/register?token={token}",
            data=self._valid_form(has_loan="没有", bank_name="", loan_amount_wan="", expire_date=""),
        )
        self.assertEqual(response.status_code, 200)
        conn = database.get_db()
        count = conn.execute("SELECT COUNT(*) FROM cultivation_loans").fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)

    def test_08_build_profile_and_consultation_keywords(self):
        build = self._callback(self._text_xml("建档", "openid-build"))
        self.assertEqual(build.status_code, 200)
        self.assertIn("填写融资档案", build.get_data(as_text=True))
        consult = self._callback(self._text_xml("咨询", "openid-build"))
        self.assertIn("已收到您的融资咨询", consult.get_data(as_text=True))
        existing = self._callback(self._text_xml("额度怎么提高", "openid-build"))
        self.assertIn("这是已有关键词回复", existing.get_data(as_text=True))

    def test_09_unsubscribe_keeps_customer_and_invalidates_token(self):
        _, token = self._subscribe_and_token()
        self.client.post(f"/public/cultivation/register?token={token}", data=self._valid_form())
        response = self._callback(self._event_xml("unsubscribe"))
        self.assertEqual(response.status_code, 200)
        conn = database.get_db()
        user = conn.execute("SELECT * FROM cultivation_wechat_users WHERE openid=?", ("openid-test-user",)).fetchone()
        customer_count = conn.execute("SELECT COUNT(*) FROM cultivation_customers WHERE id=?", (user["customer_id"],)).fetchone()[0]
        conn.close()
        self.assertEqual(user["subscribe_status"], 0)
        self.assertIsNotNone(user["unsubscribe_time"])
        self.assertEqual(customer_count, 1)
        invalid = self.client.get(f"/public/cultivation/register?token={token}")
        self.assertIn("链接已失效".encode(), invalid.data)

    def test_10_resubscribe_bound_customer_returns_update_profile_message(self):
        _, token = self._subscribe_and_token()
        self.client.post(f"/public/cultivation/register?token={token}", data=self._valid_form())
        self._callback(self._event_xml("unsubscribe"))
        response, new_token = self._subscribe_and_token()
        self.assertIn("欢迎回来", response.get_data(as_text=True))
        self.assertIn("更新融资档案", response.get_data(as_text=True))
        page = self.client.get(f"/public/cultivation/register?token={new_token}")
        self.assertIn("更新融资档案".encode(), page.data)
        self.assertIn("上海公众号测试科技有限公司".encode(), page.data)


if __name__ == "__main__":
    unittest.main()
