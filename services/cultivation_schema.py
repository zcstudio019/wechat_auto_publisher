"""融资客户培育模块的独立、幂等数据库结构。"""

from __future__ import annotations

import logging

from database import ensure_column_exists, get_db, is_mysql

logger = logging.getLogger(__name__)


SQLITE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS cultivation_customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_type TEXT NOT NULL DEFAULT 'company',
        company_name TEXT,
        legal_person TEXT,
        phone TEXT,
        industry TEXT DEFAULT '其他',
        annual_revenue REAL,
        city TEXT,
        occupation_type TEXT,
        monthly_income_range TEXT,
        has_social_security INTEGER,
        has_housing_fund INTEGER,
        has_property INTEGER,
        has_credit_card INTEGER,
        credit_query_level TEXT,
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
        has_financing_need INTEGER,
        expected_financing_amount REAL,
        financing_purpose TEXT,
        expected_financing_time TEXT,
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
    """
    CREATE TABLE IF NOT EXISTS cultivation_wechat_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        openid TEXT NOT NULL UNIQUE,
        subscribe_status INTEGER DEFAULT 1,
        subscribe_time DATETIME,
        unsubscribe_time DATETIME,
        registration_token_hash TEXT,
        token_expires_at DATETIME,
        token_used_at DATETIME,
        last_interaction_at DATETIME,
        customer_id INTEGER,
        registration_loan_id INTEGER,
        created_at DATETIME DEFAULT (datetime('now','localtime')),
        updated_at DATETIME DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (customer_id) REFERENCES cultivation_customers(id),
        FOREIGN KEY (registration_loan_id) REFERENCES cultivation_loans(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cultivation_wechat_reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        loan_id INTEGER NOT NULL,
        followup_id INTEGER,
        reminder_type TEXT NOT NULL,
        trigger_date DATE NOT NULL,
        status TEXT DEFAULT 'pending',
        delivery_reason TEXT,
        wechat_errcode TEXT,
        wechat_errmsg TEXT,
        message_content TEXT,
        attempted_at DATETIME,
        sent_at DATETIME,
        created_at DATETIME DEFAULT (datetime('now','localtime')),
        updated_at DATETIME DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (customer_id) REFERENCES cultivation_customers(id),
        FOREIGN KEY (loan_id) REFERENCES cultivation_loans(id),
        FOREIGN KEY (followup_id) REFERENCES cultivation_followups(id),
        UNIQUE (customer_id, loan_id, reminder_type, trigger_date)
    )
    """,
]

SQLITE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_cultivation_customer_advisor ON cultivation_customers(advisor_id, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_cultivation_loan_expire ON cultivation_loans(expire_date, status, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_cultivation_followup_due ON cultivation_followups(due_date, status)",
    "CREATE INDEX IF NOT EXISTS idx_article_cultivation_lookup ON article_cultivation_tags(tag_type, tag_value)",
    "CREATE INDEX IF NOT EXISTS idx_cultivation_wechat_token ON cultivation_wechat_users(registration_token_hash, token_expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_cultivation_wechat_reminder_status ON cultivation_wechat_reminders(status, trigger_date)",
]

MYSQL_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS cultivation_customers (
        id BIGINT PRIMARY KEY AUTO_INCREMENT, profile_type VARCHAR(16) NOT NULL DEFAULT 'company',
        company_name VARCHAR(255) NULL,
        legal_person VARCHAR(128), phone VARCHAR(64), industry VARCHAR(64) DEFAULT '其他',
        annual_revenue DECIMAL(18,2), city VARCHAR(128), occupation_type VARCHAR(64),
        monthly_income_range VARCHAR(64), has_social_security TINYINT, has_housing_fund TINYINT,
        has_property TINYINT, has_credit_card TINYINT, credit_query_level VARCHAR(64),
        source VARCHAR(128), advisor_id BIGINT,
        current_stage VARCHAR(64) DEFAULT '待完善贷款信息', risk_level VARCHAR(32) DEFAULT '正常',
        consultation_status VARCHAR(32) DEFAULT '未咨询', cashflow_type VARCHAR(128),
        credit_card_usage DECIMAL(8,2), credit_query_count INT, has_online_loans TINYINT,
        bank_count INT, has_collateral TINYINT, tax_grade VARCHAR(64), financing_need TEXT,
        has_financing_need TINYINT, expected_financing_amount DECIMAL(18,2),
        financing_purpose VARCHAR(255), expected_financing_time VARCHAR(64),
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
    """
    CREATE TABLE IF NOT EXISTS cultivation_wechat_users (
        id BIGINT PRIMARY KEY AUTO_INCREMENT, openid VARCHAR(128) NOT NULL,
        subscribe_status TINYINT DEFAULT 1, subscribe_time DATETIME, unsubscribe_time DATETIME,
        registration_token_hash CHAR(64), token_expires_at DATETIME, token_used_at DATETIME,
        last_interaction_at DATETIME,
        customer_id BIGINT, registration_loan_id BIGINT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_cultivation_wechat_openid (openid),
        INDEX idx_cultivation_wechat_token (registration_token_hash, token_expires_at),
        CONSTRAINT fk_cultivation_wechat_customer FOREIGN KEY (customer_id) REFERENCES cultivation_customers(id),
        CONSTRAINT fk_cultivation_wechat_registration_loan FOREIGN KEY (registration_loan_id) REFERENCES cultivation_loans(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS cultivation_wechat_reminders (
        id BIGINT PRIMARY KEY AUTO_INCREMENT, customer_id BIGINT NOT NULL, loan_id BIGINT NOT NULL,
        followup_id BIGINT, reminder_type VARCHAR(64) NOT NULL, trigger_date DATE NOT NULL,
        status VARCHAR(32) DEFAULT 'pending', delivery_reason VARCHAR(128),
        wechat_errcode VARCHAR(32), wechat_errmsg TEXT, message_content TEXT,
        attempted_at DATETIME, sent_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_cultivation_wechat_reminder (customer_id, loan_id, reminder_type, trigger_date),
        INDEX idx_cultivation_wechat_reminder_status (status, trigger_date),
        CONSTRAINT fk_cultivation_reminder_customer FOREIGN KEY (customer_id) REFERENCES cultivation_customers(id),
        CONSTRAINT fk_cultivation_reminder_loan FOREIGN KEY (loan_id) REFERENCES cultivation_loans(id),
        CONSTRAINT fk_cultivation_reminder_followup FOREIGN KEY (followup_id) REFERENCES cultivation_followups(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]

CUSTOMER_PROFILE_COLUMNS = {
    "profile_type": ("VARCHAR(16) NOT NULL DEFAULT 'company'", "TEXT NOT NULL DEFAULT 'company'"),
    "city": ("VARCHAR(128)", "TEXT"),
    "occupation_type": ("VARCHAR(64)", "TEXT"),
    "monthly_income_range": ("VARCHAR(64)", "TEXT"),
    "has_social_security": ("TINYINT", "INTEGER"),
    "has_housing_fund": ("TINYINT", "INTEGER"),
    "has_property": ("TINYINT", "INTEGER"),
    "has_credit_card": ("TINYINT", "INTEGER"),
    "credit_query_level": ("VARCHAR(64)", "TEXT"),
    "has_financing_need": ("TINYINT", "INTEGER"),
    "expected_financing_amount": ("DECIMAL(18,2)", "REAL"),
    "financing_purpose": ("VARCHAR(255)", "TEXT"),
    "expected_financing_time": ("VARCHAR(64)", "TEXT"),
}


def _migrate_customer_profiles(connection) -> None:
    """扩展客户主表，并让旧企业名称约束兼容个人档案。"""
    mysql = is_mysql()
    for column_name, definitions in CUSTOMER_PROFILE_COLUMNS.items():
        ensure_column_exists(
            connection,
            "cultivation_customers",
            column_name,
            definitions[0] if mysql else definitions[1],
        )
    connection.execute(
        "UPDATE cultivation_customers SET profile_type='company' "
        "WHERE profile_type IS NULL OR profile_type NOT IN ('company','individual')"
    )
    connection.commit()

    if mysql:
        column = connection.execute("SHOW COLUMNS FROM cultivation_customers LIKE 'company_name'").fetchone()
        if column and str(dict(column).get("Null") or "").upper() == "NO":
            connection.execute("ALTER TABLE cultivation_customers MODIFY company_name VARCHAR(255) NULL")
            connection.commit()
        return

    company_column = next(
        (dict(row) for row in connection.execute("PRAGMA table_info(cultivation_customers)").fetchall()
         if dict(row).get("name") == "company_name"),
        None,
    )
    if not company_column or not int(company_column.get("notnull") or 0):
        return

    # SQLite 不能直接移除 NOT NULL；保留主键与所有历史列重建父表。
    connection.commit()
    connection.execute("PRAGMA foreign_keys=OFF")
    try:
        connection.execute("DROP TABLE IF EXISTS cultivation_customers_phase14")
        create_sql = SQLITE_TABLES[0].replace(
            "CREATE TABLE IF NOT EXISTS cultivation_customers (",
            "CREATE TABLE cultivation_customers_phase14 (",
            1,
        )
        connection.execute(create_sql)
        old_columns = [dict(row)["name"] for row in connection.execute("PRAGMA table_info(cultivation_customers)").fetchall()]
        new_columns = {dict(row)["name"] for row in connection.execute("PRAGMA table_info(cultivation_customers_phase14)").fetchall()}
        shared = [name for name in old_columns if name in new_columns]
        quoted = ",".join(f'"{name}"' for name in shared)
        connection.execute(
            f"INSERT INTO cultivation_customers_phase14 ({quoted}) SELECT {quoted} FROM cultivation_customers"
        )
        connection.execute("DROP TABLE cultivation_customers")
        connection.execute("ALTER TABLE cultivation_customers_phase14 RENAME TO cultivation_customers")
        connection.commit()
    finally:
        connection.execute("PRAGMA foreign_keys=ON")


def _migrate_reminder_idempotency(connection) -> None:
    """把旧的三字段唯一约束升级为按贷款到期日区分的提醒周期。"""
    if is_mysql():
        rows = connection.execute(
            "SHOW INDEX FROM cultivation_wechat_reminders WHERE Key_name='uniq_cultivation_wechat_reminder'"
        ).fetchall()
        columns = [str(dict(row).get("Column_name") or "") for row in sorted(rows, key=lambda row: int(dict(row).get("Seq_in_index") or 0))]
        if columns == ["customer_id", "loan_id", "reminder_type"]:
            connection.execute(
                """UPDATE cultivation_wechat_reminders r JOIN cultivation_loans l ON l.id=r.loan_id
                SET r.trigger_date=l.expire_date"""
            )
            connection.execute(
                "ALTER TABLE cultivation_wechat_reminders DROP INDEX uniq_cultivation_wechat_reminder, "
                "ADD UNIQUE KEY uniq_cultivation_wechat_reminder (customer_id,loan_id,reminder_type,trigger_date)"
            )
        return

    old_unique_found = False
    for index_row in connection.execute("PRAGMA index_list(cultivation_wechat_reminders)").fetchall():
        index = dict(index_row)
        if not int(index.get("unique") or 0):
            continue
        name = str(index.get("name") or "").replace('"', '""')
        columns = [dict(row).get("name") for row in connection.execute(f'PRAGMA index_info("{name}")').fetchall()]
        if columns == ["customer_id", "loan_id", "reminder_type"]:
            old_unique_found = True
            break
    if not old_unique_found:
        return

    connection.commit()
    connection.execute("PRAGMA foreign_keys=OFF")
    try:
        connection.execute("ALTER TABLE cultivation_wechat_reminders RENAME TO cultivation_wechat_reminders_phase12")
        connection.execute(SQLITE_TABLES[-1])
        connection.execute(
            """INSERT INTO cultivation_wechat_reminders
            (id,customer_id,loan_id,followup_id,reminder_type,trigger_date,status,delivery_reason,
             wechat_errcode,wechat_errmsg,message_content,attempted_at,sent_at,created_at,updated_at)
            SELECT r.id,r.customer_id,r.loan_id,r.followup_id,r.reminder_type,
                   COALESCE(l.expire_date,r.trigger_date),r.status,r.delivery_reason,
                   r.wechat_errcode,r.wechat_errmsg,r.message_content,r.attempted_at,r.sent_at,r.created_at,r.updated_at
            FROM cultivation_wechat_reminders_phase12 r
            LEFT JOIN cultivation_loans l ON l.id=r.loan_id"""
        )
        connection.execute("DROP TABLE cultivation_wechat_reminders_phase12")
        connection.commit()
    finally:
        connection.execute("PRAGMA foreign_keys=ON")


def init_cultivation_tables(conn=None) -> bool:
    """创建培育模块表；失败返回 False，调用方可安全降级。"""
    owns_connection = conn is None
    connection = conn or get_db()
    try:
        statements = MYSQL_TABLES if is_mysql() else SQLITE_TABLES
        for statement in statements:
            connection.execute(statement)
        _migrate_customer_profiles(connection)
        _migrate_reminder_idempotency(connection)
        if not is_mysql():
            for statement in SQLITE_INDEXES:
                connection.execute(statement)
        ensure_column_exists(connection, "cultivation_wechat_users", "last_interaction_at", "DATETIME")
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
