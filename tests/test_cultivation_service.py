import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

import database
from services.cultivation_schema import init_cultivation_tables
from services.cultivation_service import CustomerCultivationService as Service


class CultivationServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir.name, "cultivation.db")
        conn = database.get_db()
        conn.executescript("""
        CREATE TABLE articles (id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,content TEXT NOT NULL DEFAULT '',summary TEXT,review_status TEXT,publish_status TEXT,created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE advisors (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,is_active INTEGER DEFAULT 1);
        INSERT INTO advisors(name) VALUES ('测试顾问');
        """)
        conn.commit(); conn.close()
        self.assertTrue(init_cultivation_tables())

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def create_customer(self, **overrides):
        payload = {
            "company_name": "上海测试科技有限公司", "legal_person": "张总", "phone": "13800000000",
            "industry": "科技", "advisor_id": 1, "credit_card_usage": 75,
            "credit_query_count": 41, "bank_count": 5, "has_collateral": 0,
        }
        payload.update(overrides)
        return Service.create_customer(payload)

    def add_loan(self, customer_id, days, bank="建行", amount=3000000):
        return Service.add_loan(customer_id, {
            "bank_name": bank, "product_name": "科技贷", "loan_amount": amount,
            "loan_balance": amount, "start_date": date.today().isoformat(),
            "expire_date": (date.today() + timedelta(days=days)).isoformat(),
            "repayment_type": "先息后本", "status": "正常",
        })

    def test_schema_initialization_is_idempotent(self):
        self.assertTrue(init_cultivation_tables())
        conn = database.get_db()
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        self.assertTrue({"cultivation_customers", "cultivation_loans", "cultivation_tags", "cultivation_followups", "cultivation_events", "article_cultivation_tags"}.issubset(tables))

    def test_multiple_loans_choose_nearest_and_generate_risk_tags(self):
        customer_id = self.create_customer()
        self.add_loan(customer_id, 55, "建行", 3000000)
        self.add_loan(customer_id, 180, "浦发", 2000000)
        result = Service.refresh_customer(customer_id)
        self.assertEqual(result["nearest_loan"]["bank_name"], "建行")
        self.assertEqual(result["stage"], "到期前60天")
        self.assertEqual(result["risk_level"], "高风险")
        tag_names = {name for _, name in result["tags"]}
        self.assertTrue({"信用卡高使用率", "征信查询高风险", "多头贷款关注", "无抵押物"}.issubset(tag_names))

    def test_30_and_15_day_priority_and_idempotent_tasks(self):
        customer_30 = self.create_customer(company_name="25天客户", credit_card_usage=10, credit_query_count=1, bank_count=1)
        self.add_loan(customer_30, 25)
        result_30 = Service.refresh_customer(customer_30, create_task=True)
        self.assertEqual(result_30["stage"], "到期前30天")
        self.assertGreaterEqual(Service.RISK_RANK[result_30["risk_level"]], Service.RISK_RANK["高风险"])

        customer_15 = self.create_customer(company_name="10天客户", credit_card_usage=10, credit_query_count=1, bank_count=1)
        self.add_loan(customer_15, 10)
        first = Service.refresh_customer(customer_15, create_task=True)
        Service.scan_cultivation_customers(); Service.scan_cultivation_customers()
        self.assertEqual(first["stage"], "紧急续贷期")
        conn = database.get_db()
        rows = conn.execute("SELECT * FROM cultivation_followups WHERE customer_id=? AND trigger_type='15_day'", (customer_15,)).fetchall()
        conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["priority"], "urgent")

    def test_article_recommendation_prefers_customer_stage(self):
        customer_id = self.create_customer(credit_card_usage=10, credit_query_count=1, bank_count=1)
        self.add_loan(customer_id, 55)
        conn = database.get_db()
        stage_id = conn.execute("INSERT INTO articles(title,content) VALUES (?,?)", ("贷款到期前60天", "正文")).lastrowid
        general_id = conn.execute("INSERT INTO articles(title,content) VALUES (?,?)", ("通用融资知识", "正文")).lastrowid
        conn.commit(); conn.close()
        Service.set_article_tags(stage_id, {"cultivation_category":"续贷", "customer_stage":"到期前60天", "industry_tag":"通用"})
        Service.set_article_tags(general_id, {"cultivation_category":"融资", "industry_tag":"通用"})
        result = Service.recommend_article(customer_id)
        self.assertEqual(result["id"], stage_id)

    def test_complete_followup_updates_customer_history_and_consultation(self):
        customer_id = self.create_customer(credit_card_usage=10, credit_query_count=1, bank_count=1)
        self.add_loan(customer_id, 10)
        conn = database.get_db(); task_id = conn.execute("SELECT id FROM cultivation_followups WHERE customer_id=?", (customer_id,)).fetchone()[0]; conn.close()
        Service.update_followup(task_id, {"status":"已联系", "contact_method":"电话", "followup_result":"有需求", "followup_note":"预约明天诊断", "next_followup_at":(date.today()+timedelta(days=1)).isoformat()})
        conn = database.get_db()
        task = conn.execute("SELECT * FROM cultivation_followups WHERE id=?", (task_id,)).fetchone()
        customer = conn.execute("SELECT * FROM cultivation_customers WHERE id=?", (customer_id,)).fetchone(); conn.close()
        self.assertEqual(task["status"], "已联系")
        self.assertEqual(task["followup_note"], "预约明天诊断")
        self.assertEqual(customer["consultation_status"], "已产生咨询")


if __name__ == "__main__":
    unittest.main()
