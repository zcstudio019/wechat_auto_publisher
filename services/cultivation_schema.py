"""融资客户培育模块的独立、幂等数据库结构。"""

from __future__ import annotations

import logging

from database import get_db, is_mysql

logger = logging.getLogger(__name__)


SQLITE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS cultivation_customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        legal_person TEXT,
        phone TEXT,
        industry TEXT DEFAULT '其他',
        annual_revenue REAL,
        source TEXT,
        advisor_id INTEGER,
        current_stage TEXT DEFAULT '待完善贷款信息',
        risk_level TEXT DEFAULT '正常',
        consultation_status TEXT DEFAULT '未咨询',
        cashflow_type TEXT,
        credit_card_usage REAL,
        credit_query_count INTEGER,
        has_online_loans INTEGER,
        bank_count INTEGER,
        has_collateral INTEGER,
        tax_grade TEXT,
        financing_need TEXT,
        is_active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT (datetime('now','localtime')),
        updated_at DATETIME DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (advisor_id) REFERENCES advisors(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cultivation_loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        bank_name TEXT NOT NULL,
        product_name TEXT,
        loan_amount REAL NOT NULL DEFAULT 0,
        loan_balance REAL DEFAULT 0,
        interest_rate REAL,
        start_date DATE,
        expire_date DATE NOT NULL,
        repayment_type TEXT DEFAULT '不确定',
        loan_term TEXT,
        status TEXT DEFAULT '正常',
        is_active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT (datetime('now','localtime')),
        updated_at DATETIME DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (customer_id) REFERENCES cultivation_customers(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cultivation_tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        tag_type TEXT NOT NULL,
        tag_name TEXT NOT NULL,
        source TEXT DEFAULT 'system',
        created_at DATETIME DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (customer_id) REFERENCES cultivation_customers(id),
        UNIQUE (customer_id, tag_type, tag_name, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cultivation_followups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        loan_id INTEGER,
        task_type TEXT DEFAULT '到期提醒',
        trigger_type TEXT NOT NULL,
        priority TEXT DEFAULT 'medium',
        due_date DATE NOT NULL,
        recommended_article_id INTEGER,
        advisor_id INTEGER,
        status TEXT DEFAULT '待处理',
        contact_method TEXT,
        followup_result TEXT,
        followup_note TEXT,
        next_followup_at DATETIME,
        created_at DATETIME DEFAULT (datetime('now','localtime')),
        completed_at DATETIME,
        FOREIGN KEY (customer_id) REFERENCES cultivation_customers(id),
        FOREIGN KEY (loan_id) REFERENCES cultivation_loans(id),
        FOREIGN KEY (recommended_article_id) REFERENCES articles(id),
        FOREIGN KEY (advisor_id) REFERENCES advisors(id),
        UNIQUE (customer_id, loan_id, trigger_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cultivation_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        event_data TEXT,
        created_at DATETIME DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (customer_id) REFERENCES cultivation_customers(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS article_cultivation_tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER NOT NULL,
        tag_type TEXT NOT NULL,
        tag_value TEXT NOT NULL,
        created_at DATETIME DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (article_id) REFERENCES articles(id),
        UNIQUE (article_id, tag_type, tag_value)
    )
    """,
]

SQLITE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_cultivation_customer_advisor ON cultivation_customers(advisor_id, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_cultivation_loan_expire ON cultivation_loans(expire_date, status, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_cultivation_followup_due ON cultivation_followups(due_date, status)",
    "CREATE INDEX IF NOT EXISTS idx_article_cultivation_lookup ON article_cultivation_tags(tag_type, tag_value)",
]

MYSQL_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS cultivation_customers (
        id BIGINT PRIMARY KEY AUTO_INCREMENT, company_name VARCHAR(255) NOT NULL,
        legal_person VARCHAR(128), phone VARCHAR(64), industry VARCHAR(64) DEFAULT '其他',
        annual_revenue DECIMAL(18,2), source VARCHAR(128), advisor_id BIGINT,
        current_stage VARCHAR(64) DEFAULT '待完善贷款信息', risk_level VARCHAR(32) DEFAULT '正常',
        consultation_status VARCHAR(32) DEFAULT '未咨询', cashflow_type VARCHAR(128),
        credit_card_usage DECIMAL(8,2), credit_query_count INT, has_online_loans TINYINT,
        bank_count INT, has_collateral TINYINT, tax_grade VARCHAR(64), financing_need TEXT,
        is_active TINYINT DEFAULT 1, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_cultivation_customer_advisor (advisor_id, is_active),
        CONSTRAINT fk_cultivation_customer_advisor FOREIGN KEY (advisor_id) REFERENCES advisors(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS cultivation_loans (
        id BIGINT PRIMARY KEY AUTO_INCREMENT, customer_id BIGINT NOT NULL, bank_name VARCHAR(255) NOT NULL,
        product_name VARCHAR(255), loan_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
        loan_balance DECIMAL(18,2) DEFAULT 0, interest_rate DECIMAL(10,4), start_date DATE,
        expire_date DATE NOT NULL, repayment_type VARCHAR(64) DEFAULT '不确定', loan_term VARCHAR(64),
        status VARCHAR(32) DEFAULT '正常', is_active TINYINT DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_cultivation_loan_expire (expire_date, status, is_active),
        CONSTRAINT fk_cultivation_loan_customer FOREIGN KEY (customer_id) REFERENCES cultivation_customers(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS cultivation_tags (
        id BIGINT PRIMARY KEY AUTO_INCREMENT, customer_id BIGINT NOT NULL, tag_type VARCHAR(32) NOT NULL,
        tag_name VARCHAR(128) NOT NULL, source VARCHAR(32) DEFAULT 'system',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_cultivation_tag (customer_id, tag_type, tag_name, source),
        CONSTRAINT fk_cultivation_tag_customer FOREIGN KEY (customer_id) REFERENCES cultivation_customers(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS cultivation_followups (
        id BIGINT PRIMARY KEY AUTO_INCREMENT, customer_id BIGINT NOT NULL, loan_id BIGINT,
        task_type VARCHAR(64) DEFAULT '到期提醒', trigger_type VARCHAR(64) NOT NULL,
        priority VARCHAR(16) DEFAULT 'medium', due_date DATE NOT NULL, recommended_article_id BIGINT,
        advisor_id BIGINT, status VARCHAR(32) DEFAULT '待处理', contact_method VARCHAR(32),
        followup_result VARCHAR(64), followup_note TEXT, next_followup_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP, completed_at DATETIME,
        UNIQUE KEY uniq_cultivation_trigger (customer_id, loan_id, trigger_type),
        INDEX idx_cultivation_followup_due (due_date, status),
        CONSTRAINT fk_cultivation_followup_customer FOREIGN KEY (customer_id) REFERENCES cultivation_customers(id),
        CONSTRAINT fk_cultivation_followup_loan FOREIGN KEY (loan_id) REFERENCES cultivation_loans(id),
        CONSTRAINT fk_cultivation_followup_article FOREIGN KEY (recommended_article_id) REFERENCES articles(id),
        CONSTRAINT fk_cultivation_followup_advisor FOREIGN KEY (advisor_id) REFERENCES advisors(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS cultivation_events (
        id BIGINT PRIMARY KEY AUTO_INCREMENT, customer_id BIGINT NOT NULL, event_type VARCHAR(64) NOT NULL,
        event_data LONGTEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_cultivation_event_customer (customer_id, created_at),
        CONSTRAINT fk_cultivation_event_customer FOREIGN KEY (customer_id) REFERENCES cultivation_customers(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS article_cultivation_tags (
        id BIGINT PRIMARY KEY AUTO_INCREMENT, article_id BIGINT NOT NULL, tag_type VARCHAR(64) NOT NULL,
        tag_value VARCHAR(128) NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_article_cultivation_tag (article_id, tag_type, tag_value),
        INDEX idx_article_cultivation_lookup (tag_type, tag_value),
        CONSTRAINT fk_article_cultivation_article FOREIGN KEY (article_id) REFERENCES articles(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]


def init_cultivation_tables(conn=None) -> bool:
    """创建培育模块表；失败返回 False，调用方可安全降级。"""
    owns_connection = conn is None
    connection = conn or get_db()
    try:
        statements = MYSQL_TABLES if is_mysql() else SQLITE_TABLES + SQLITE_INDEXES
        for statement in statements:
            connection.execute(statement)
        connection.commit()
        logger.info("[cultivation-db-init] tables ready")
        return True
    except Exception:
        try:
            connection.rollback()
        except Exception:
            pass
        logger.exception("[cultivation-db-init-error] cultivation module disabled until next successful init")
        return False
    finally:
        if owns_connection:
            connection.close()
