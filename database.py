"""
数据库模型 & 初始化
"""
import os
import sqlite3

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:  # pragma: no cover
    pymysql = None
    DictCursor = None

from config import DB_BACKEND, DB_CHARSET, DB_HOST, DB_NAME, DB_PASSWORD, DB_PATH, DB_PORT, DB_USER
from domain.article_status import PUBLISH_STATUS_NOT_READY, REVIEW_STATUS_DRAFT


def is_mysql():
    """判断当前是否使用 MySQL/RDS。"""
    return DB_BACKEND == "mysql"


def is_sqlite():
    """判断当前是否使用 SQLite。"""
    return DB_BACKEND in ("", "sqlite")


def get_placeholder():
    """返回当前数据库使用的 SQL 占位符。"""
    return "%s" if is_mysql() else "?"


def fetchone_dict(cursor):
    """统一读取单行 dict；SQLite Row 和 MySQL DictCursor 都可兼容。"""
    row = cursor.fetchone()
    return dict(row) if row is not None else None


def fetchall_dict(cursor):
    """统一读取多行 dict；便于后续 3D 逐步替换业务查询。"""
    return [dict(row) for row in cursor.fetchall()]


def get_lastrowid(cursor):
    """统一获取插入自增 ID，避免依赖 SQLite 专属 last_insert_rowid()。"""
    return cursor.lastrowid


class CompatRow(dict):
    """让 MySQL DictCursor 的结果兼容少量 SQLite Row 的数字下标读取。"""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class CompatCursor:
    """MySQL 游标轻量适配器，统一 fetchone/fetchall 返回形态。"""

    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def execute(self, sql, params=None):
        self._cursor.execute(_adapt_sql_for_mysql(sql), params or ())
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        return CompatRow(row) if isinstance(row, dict) else row

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [CompatRow(row) if isinstance(row, dict) else row for row in rows]


class MySQLConnectionAdapter:
    """为 PyMySQL 补齐项目中常用的 conn.execute(...) 形态。

    这是迁移期的薄适配层，不替代 3D 阶段对高风险 SQL 的显式修复。
    """

    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return CompatCursor(self._conn.cursor())

    def execute(self, sql, params=None):
        cursor = self.cursor()
        cursor.execute(sql, params or ())
        return cursor

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()


def _adapt_sql_for_mysql(sql: str) -> str:
    """将项目里最常见的 SQLite 写法显式降级为 MySQL 写法。"""
    adapted_sql = sql
    replacements = {
        "datetime('now','localtime','-10 minutes')": "DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 10 MINUTE)",
        "datetime('now','localtime','-30 minutes')": "DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 30 MINUTE)",
        "datetime('now','-7 days','localtime')": "DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 7 DAY)",
        "datetime('now','-30 days','localtime')": "DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 30 DAY)",
        "datetime('now','localtime')": "CURRENT_TIMESTAMP",
        "DATE('now','localtime')": "CURDATE()",
        "date('now','localtime')": "CURDATE()",
        "strftime('%Y-%m-%d %H:00:00', updated_at)": "DATE_FORMAT(updated_at, '%Y-%m-%d %H:00:00')",
        "strftime('%Y-%m-%d %H:00:00', created_at)": "DATE_FORMAT(created_at, '%Y-%m-%d %H:00:00')",
        "MAX(0, current_leads - 1)": "GREATEST(0, current_leads - 1)",
    }
    for sqlite_expr, mysql_expr in replacements.items():
        adapted_sql = adapted_sql.replace(sqlite_expr, mysql_expr)
    return adapted_sql.replace("?", "%s")


def get_db():
    """根据 DB_BACKEND 返回数据库连接。"""
    if is_mysql():
        if pymysql is None:
            raise RuntimeError("当前 DB_BACKEND=mysql，但未安装 pymysql，请先执行 pip install pymysql。")
        if not DB_NAME:
            raise RuntimeError("当前 DB_BACKEND=mysql，但 DB_NAME 未配置。")
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset=DB_CHARSET,
            cursorclass=DictCursor,
            autocommit=False,
        )
        return MySQLConnectionAdapter(conn)

    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """根据当前数据库后端分发初始化逻辑。"""
    if is_mysql():
        init_mysql_db()
    else:
        init_sqlite_db()


def init_sqlite_db():
    """保留原 SQLite 初始化路径，保证本地开发模式不被破坏。"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            content     TEXT NOT NULL,
            summary     TEXT,
            cover_url   TEXT,
            cover_image TEXT,
            cover_status TEXT DEFAULT 'pending',
            cover_prompt TEXT,
            source_name TEXT,
            source_url  TEXT,
            tags        TEXT,
status      TEXT DEFAULT 'draft',   -- draft / approved / published / rejected
            review_status TEXT DEFAULT 'draft', -- draft / approved / rejected
            publish_status TEXT DEFAULT 'not_ready', -- not_ready / draft_sent / published / failed
            media_id    TEXT,                   -- 微信素材media_id
            draft_id    TEXT,                   -- 微信草稿media_id
            created_at  DATETIME DEFAULT (datetime('now','localtime')),
            updated_at  DATETIME DEFAULT (datetime('now','localtime')),
            published_at DATETIME,
            is_original INTEGER DEFAULT 0,      -- 是否为原创内容：0=爬取，1=原创
            html_content TEXT                   -- 格式化后的HTML内容（AI处理后）
        );

        CREATE TABLE IF NOT EXISTS publish_tasks (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id          INTEGER NOT NULL,
            channel             TEXT NOT NULL,              -- 发布渠道，例如 wechat
            task_type           TEXT NOT NULL,              -- 任务类型，例如 wechat_draft
            status              TEXT DEFAULT 'queued',      -- queued / running / success / failed
            retry_count         INTEGER DEFAULT 0,          -- 已重试次数
            max_retries         INTEGER DEFAULT 3,          -- 最大重试次数
            payload_snapshot    TEXT,                       -- 创建任务时的文章快照
            result_payload      TEXT,                       -- 执行结果快照
            external_draft_id   TEXT,                       -- 外部草稿ID
            external_publish_id TEXT,                       -- 外部发布ID
            error_message       TEXT,                       -- 执行失败信息
            created_at          DATETIME DEFAULT (datetime('now','localtime')),
            updated_at          DATETIME DEFAULT (datetime('now','localtime')),
            executed_at         DATETIME,
            FOREIGN KEY (article_id) REFERENCES articles(id)
        );

        -- 写作模板表（6大定位）
        CREATE TABLE IF NOT EXISTS article_templates (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,           -- 模板名称
            category     TEXT NOT NULL,           -- 分类：science/brand/leads/service/finance/enterprise
            category_label TEXT,                  -- 分类显示名称
            structure    TEXT,                    -- 文章结构（JSON，段落顺序）
            pain_point   TEXT,                    -- 痛点描述
            solution     TEXT,                    -- 解决方案
            hook         TEXT,                    -- 留资钩子
            brand_rules  TEXT,                    -- 品牌植入规则（JSON）
            prompt_template TEXT,                 -- AI写作提示词模板
            is_active    INTEGER DEFAULT 1,
            created_at   DATETIME DEFAULT (datetime('now','localtime')),
            updated_at   DATETIME DEFAULT (datetime('now','localtime'))
        );

        -- 爬取规则配置表（支持动态管理）
        CREATE TABLE IF NOT EXISTS crawl_rules (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,           -- 来源名称
            type         TEXT NOT NULL,           -- eastmoney_api / pbc_web / custom_web
            url          TEXT NOT NULL,           -- 爬取URL
            base_url     TEXT,                    -- 基础URL（拼接相对路径）
            tags         TEXT,                    -- 关联标签（逗号分隔）
            tag_keywords TEXT,                    -- 自动打标关键词（JSON）
            filter_keywords TEXT,                 -- 过滤关键词（JSON，命中则丢弃）
            category_map TEXT,                    -- 关键词→分类映射（JSON）
            is_active    INTEGER DEFAULT 1,
            last_crawl   DATETIME,
            created_at   DATETIME DEFAULT (datetime('now','localtime'))
        );

        -- 格式化规则配置表
        CREATE TABLE IF NOT EXISTS format_rules (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL,           -- 规则名称
            rule_type    TEXT NOT NULL,           -- title_format / content_format / sensitive_word
            config       TEXT,                    -- 规则配置（JSON）
            is_active    INTEGER DEFAULT 1,
            created_at   DATETIME DEFAULT (datetime('now','localtime'))
        );

        -- 敏感词库表
        CREATE TABLE IF NOT EXISTS sensitive_words (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            word         TEXT NOT NULL UNIQUE,
            category     TEXT DEFAULT 'finance',  -- finance/political/spam
            action       TEXT DEFAULT 'block',    -- block（拦截）/ replace（替换）/ warn（警告）
            replace_with TEXT,                    -- 替换词（action=replace时使用）
            created_at   DATETIME DEFAULT (datetime('now','localtime'))
        );
        -- 品牌素材库
        CREATE TABLE IF NOT EXISTS brand_assets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,              -- 素材名称
            asset_type  TEXT NOT NULL,              -- logo / poster / slogan / case / icon / other
            category    TEXT DEFAULT 'brand',       -- brand / leads / service / general
            file_path   TEXT,                       -- 本地文件路径（相对于 static/assets/）
            url         TEXT,                       -- 外部URL或微信media_id
            description TEXT,                       -- 描述/用途说明
            tags        TEXT,                       -- 逗号分隔标签
            is_active   INTEGER DEFAULT 1,
            created_at  DATETIME DEFAULT (datetime('now','localtime'))
        );

        -- 资料中心（手册文档）
        CREATE TABLE IF NOT EXISTS resource_docs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,              -- 文档标题
            doc_type    TEXT DEFAULT 'manual',      -- manual / guide / checklist / template
            content     TEXT,                       -- HTML内容
            version     TEXT DEFAULT '1.0',
            created_at  DATETIME DEFAULT (datetime('now','localtime')),
            updated_at  DATETIME DEFAULT (datetime('now','localtime'))
        );

        -- 留资表单配置表
        CREATE TABLE IF NOT EXISTS lead_forms (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,              -- 表单名称（如：征信诊断表单、额度测算表单）
            form_type   TEXT NOT NULL,              -- credit_diagnosis / quota_calc / general
            fields      TEXT NOT NULL,              -- 表单字段JSON（字段名、类型、是否必填）
            template_categories TEXT,               -- 适用模板分类（JSON数组：leads,service等）
            html_template TEXT,                     -- 表单HTML模板
            crm_sync_config TEXT,                   -- CRM同步配置JSON
            is_active   INTEGER DEFAULT 1,
            created_at  DATETIME DEFAULT (datetime('now','localtime')),
            updated_at  DATETIME DEFAULT (datetime('now','localtime'))
        );

        -- 关键词自动回复配置表
        CREATE TABLE IF NOT EXISTS keyword_replies (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword     TEXT NOT NULL UNIQUE,       -- 关键词
            reply_type  TEXT DEFAULT 'text',        -- text / article / menu
            reply_content TEXT NOT NULL,            -- 回复内容
            match_mode  TEXT DEFAULT 'exact',       -- exact / contain / prefix
            priority    INTEGER DEFAULT 0,          -- 优先级（数字越大越优先）
            is_active   INTEGER DEFAULT 1,
            created_at  DATETIME DEFAULT (datetime('now','localtime')),
            updated_at  DATETIME DEFAULT (datetime('now','localtime'))
        );

        -- 线索数据表
        CREATE TABLE IF NOT EXISTS leads (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,              -- 客户姓名
            phone       TEXT NOT NULL,              -- 手机号
            loan_amount TEXT,                       -- 贷款金额
            credit_status TEXT,                     -- 征信情况
            source      TEXT,                       -- 来源（文章ID/关键词/直接访问）
            region      TEXT,                       -- 地区
            advisor_id  INTEGER,                    -- 分配的顾问ID
            status      TEXT DEFAULT 'new',         -- new / assigned / contacted / converted / lost
            form_data   TEXT,                       -- 完整表单数据JSON
            created_at  DATETIME DEFAULT (datetime('now','localtime')),
            updated_at  DATETIME DEFAULT (datetime('now','localtime'))
        );

        -- 顾问/业务员表
        CREATE TABLE IF NOT EXISTS advisors (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,              -- 顾问姓名
            phone       TEXT,                       -- 顾问电话
            regions     TEXT,                       -- 负责地区（JSON数组）
            specialties TEXT,                       -- 专长领域（JSON数组）
            max_leads   INTEGER DEFAULT 10,         -- 最大线索承载量
            current_leads INTEGER DEFAULT 0,        -- 当前线索数
            is_active   INTEGER DEFAULT 1,
            created_at  DATETIME DEFAULT (datetime('now','localtime'))
        );

        -- 工单系统表
        CREATE TABLE IF NOT EXISTS work_orders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no    TEXT UNIQUE NOT NULL,       -- 工单编号 WO-YYYYMMDD-XXXX
            customer_name TEXT NOT NULL,            -- 客户姓名
            customer_phone TEXT NOT NULL,           -- 客户联系方式
            order_type  TEXT NOT NULL,              -- loan_match(贷款方案匹配)/finance_plan(融资规划)/enterprise_analysis(企业经营分析)
            order_type_label TEXT,                  -- 类型显示名称
            description TEXT,                       -- 需求描述
            advisor_id  INTEGER,                    -- 分配的服务人员ID
            status      TEXT DEFAULT 'pending',     -- pending(待处理)/processing(处理中)/completed(已完成)/reviewed(已评价)
            priority    INTEGER DEFAULT 0,          -- 优先级 0=普通 1=高 2=紧急
            source      TEXT,                       -- 来源：article(文章)/menu(菜单)/keyword(关键词)
            source_id   INTEGER,                    -- 来源文章ID等
            created_at  DATETIME DEFAULT (datetime('now','localtime')),
            updated_at  DATETIME DEFAULT (datetime('now','localtime')),
            assigned_at DATETIME,                   -- 分配时间
            completed_at DATETIME,                  -- 完成时间
            reviewed_at DATETIME,                   -- 评价时间
            FOREIGN KEY (advisor_id) REFERENCES advisors(id)
        );

        -- 工单预警记录表
        CREATE TABLE IF NOT EXISTS work_order_alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id    INTEGER NOT NULL,
            alert_type  TEXT NOT NULL,              -- timeout(超时未处理)/reminder(提醒)
            alert_time  DATETIME DEFAULT (datetime('now','localtime')),
            is_resolved INTEGER DEFAULT 0,
            resolved_at DATETIME,
            FOREIGN KEY (order_id) REFERENCES work_orders(id)
        );

        -- 工单交付记录表
        CREATE TABLE IF NOT EXISTS work_order_deliveries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id    INTEGER NOT NULL,
            delivery_type TEXT NOT NULL,            -- report(报告)/plan(方案)/document(文档)
            title       TEXT NOT NULL,
            content     TEXT,                       -- 内容或文件路径
            file_url    TEXT,                       -- 附件URL
            is_auto_sent INTEGER DEFAULT 0,         -- 是否自动推送
            sent_at     DATETIME,
            created_at  DATETIME DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (order_id) REFERENCES work_orders(id)
        );

        -- 工单评价表
        CREATE TABLE IF NOT EXISTS work_order_reviews (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id    INTEGER NOT NULL UNIQUE,
            rating      INTEGER NOT NULL,           -- 1-5星评分
            comment     TEXT,                       -- 评价内容
            tags        TEXT,                       -- 评价标签JSON
            created_at  DATETIME DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (order_id) REFERENCES work_orders(id)
        );

        -- 工单表单配置表（文章/菜单嵌入用）
        CREATE TABLE IF NOT EXISTS work_order_forms (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,              -- 表单名称
            form_type   TEXT NOT NULL,              -- loan_match/finance_plan/enterprise_analysis
            form_type_label TEXT,                   -- 类型显示名称
            fields      TEXT NOT NULL,              -- 表单字段JSON
            html_template TEXT,                     -- HTML模板
            embed_code  TEXT,                       -- 嵌入代码
            is_active   INTEGER DEFAULT 1,
            created_at  DATETIME DEFAULT (datetime('now','localtime'))
        );

        -- AI 操作日志表：记录文章详情页各类 Agent 的只读/应用操作轨迹
        CREATE TABLE IF NOT EXISTS ai_operation_logs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id    INTEGER,
            agent_name    TEXT,
            action_type   TEXT,
            operator_id   INTEGER,
            operator_name TEXT,
            ok            INTEGER DEFAULT 0,
            summary       TEXT,
            result_json   TEXT,
            error_message TEXT,
            created_at    DATETIME DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (article_id) REFERENCES articles(id)
        );

        CREATE INDEX IF NOT EXISTS idx_ai_operation_logs_article_id ON ai_operation_logs(article_id);
        CREATE INDEX IF NOT EXISTS idx_ai_operation_logs_created_at ON ai_operation_logs(created_at);
    """)
    conn.commit()

    # 兼容已有数据库：若缺少拆分状态字段则补齐，并按旧 status 回填。
    _ensure_article_status_columns(conn)
    _ensure_article_cover_columns(conn)

    # 插入默认写作模板（6大定位）
    init_default_templates(conn)
    # 插入默认爬取规则
    # 插入默认格式化规则
    _insert_default_format_rules(conn)
    # 插入默认敏感词
    _insert_default_sensitive_words(conn)
    # 插入默认留资表单
    _insert_default_lead_forms(conn)
    # 插入默认关键词回复
    _insert_default_keyword_replies(conn)
    # 插入默认顾问数据
    _insert_default_advisors(conn)
    # 插入默认工单表单配置
    _insert_default_work_order_forms(conn)

    conn.close()
    print("[DB] 数据库初始化完成")


def init_mysql_db():
    """初始化 MySQL/RDS 表结构。

    说明：
    - 这里只创建等价表结构和必要索引，不复用 SQLite 默认数据插入函数。
    - 默认数据函数当前依赖 INSERT OR IGNORE、? 占位符和 conn.execute，3D 阶段会逐个显式兼容。
    """
    conn = get_db()
    cursor = conn.cursor()

    statements = [
        """
        CREATE TABLE IF NOT EXISTS articles (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            title VARCHAR(255) NOT NULL,
            content LONGTEXT NOT NULL,
            summary TEXT,
            cover_url TEXT,
            cover_image TEXT,
            cover_status VARCHAR(32) DEFAULT 'pending',
            cover_prompt LONGTEXT,
            source_name VARCHAR(255),
            source_url TEXT,
            tags TEXT,
            status VARCHAR(32) DEFAULT 'draft',
            review_status VARCHAR(32) DEFAULT 'draft',
            publish_status VARCHAR(32) DEFAULT 'not_ready',
            media_id VARCHAR(255),
            draft_id VARCHAR(255),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            published_at DATETIME,
            is_original TINYINT DEFAULT 0,
            html_content LONGTEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS publish_tasks (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            article_id BIGINT NOT NULL,
            channel VARCHAR(64) NOT NULL,
            task_type VARCHAR(64) NOT NULL,
            status VARCHAR(32) DEFAULT 'queued',
            retry_count INT DEFAULT 0,
            max_retries INT DEFAULT 3,
            payload_snapshot LONGTEXT,
            result_payload LONGTEXT,
            external_draft_id VARCHAR(255),
            external_publish_id VARCHAR(255),
            error_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            executed_at DATETIME,
            CONSTRAINT fk_publish_tasks_article FOREIGN KEY (article_id) REFERENCES articles(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS article_templates (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(255) NOT NULL,
            category VARCHAR(64) NOT NULL,
            category_label VARCHAR(255),
            structure LONGTEXT,
            pain_point TEXT,
            solution TEXT,
            hook TEXT,
            brand_rules LONGTEXT,
            prompt_template LONGTEXT,
            is_active TINYINT DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS crawl_rules (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(255) NOT NULL,
            type VARCHAR(64) NOT NULL,
            url TEXT NOT NULL,
            base_url TEXT,
            tags TEXT,
            tag_keywords LONGTEXT,
            filter_keywords LONGTEXT,
            category_map LONGTEXT,
            is_active TINYINT DEFAULT 1,
            last_crawl DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS format_rules (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(255) NOT NULL,
            rule_type VARCHAR(64) NOT NULL,
            config LONGTEXT,
            is_active TINYINT DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS sensitive_words (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            word VARCHAR(255) NOT NULL UNIQUE,
            category VARCHAR(64) DEFAULT 'finance',
            action VARCHAR(32) DEFAULT 'block',
            replace_with VARCHAR(255),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS brand_assets (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(255) NOT NULL,
            asset_type VARCHAR(64) NOT NULL,
            category VARCHAR(64) DEFAULT 'brand',
            file_path TEXT,
            url TEXT,
            description TEXT,
            tags TEXT,
            is_active TINYINT DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS resource_docs (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            title VARCHAR(255) NOT NULL,
            doc_type VARCHAR(64) DEFAULT 'manual',
            content LONGTEXT,
            version VARCHAR(64) DEFAULT '1.0',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS lead_forms (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(255) NOT NULL,
            form_type VARCHAR(64) NOT NULL,
            fields LONGTEXT NOT NULL,
            template_categories LONGTEXT,
            html_template LONGTEXT,
            crm_sync_config LONGTEXT,
            is_active TINYINT DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS keyword_replies (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            keyword VARCHAR(255) NOT NULL UNIQUE,
            reply_type VARCHAR(64) DEFAULT 'text',
            reply_content LONGTEXT NOT NULL,
            match_mode VARCHAR(32) DEFAULT 'exact',
            priority INT DEFAULT 0,
            is_active TINYINT DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS leads (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(255) NOT NULL,
            phone VARCHAR(64) NOT NULL,
            loan_amount VARCHAR(255),
            credit_status VARCHAR(255),
            source VARCHAR(255),
            region VARCHAR(255),
            advisor_id BIGINT,
            status VARCHAR(32) DEFAULT 'new',
            form_data LONGTEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS advisors (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(255) NOT NULL,
            phone VARCHAR(64),
            regions LONGTEXT,
            specialties LONGTEXT,
            max_leads INT DEFAULT 10,
            current_leads INT DEFAULT 0,
            is_active TINYINT DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS work_orders (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            order_no VARCHAR(64) UNIQUE NOT NULL,
            customer_name VARCHAR(255) NOT NULL,
            customer_phone VARCHAR(64) NOT NULL,
            order_type VARCHAR(64) NOT NULL,
            order_type_label VARCHAR(255),
            description TEXT,
            advisor_id BIGINT,
            status VARCHAR(32) DEFAULT 'pending',
            priority INT DEFAULT 0,
            source VARCHAR(64),
            source_id BIGINT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            assigned_at DATETIME,
            completed_at DATETIME,
            reviewed_at DATETIME,
            CONSTRAINT fk_work_orders_advisor FOREIGN KEY (advisor_id) REFERENCES advisors(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS work_order_alerts (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            order_id BIGINT NOT NULL,
            alert_type VARCHAR(64) NOT NULL,
            alert_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_resolved TINYINT DEFAULT 0,
            resolved_at DATETIME,
            CONSTRAINT fk_work_order_alerts_order FOREIGN KEY (order_id) REFERENCES work_orders(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS work_order_deliveries (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            order_id BIGINT NOT NULL,
            delivery_type VARCHAR(64) NOT NULL,
            title VARCHAR(255) NOT NULL,
            content LONGTEXT,
            file_url TEXT,
            is_auto_sent TINYINT DEFAULT 0,
            sent_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_work_order_deliveries_order FOREIGN KEY (order_id) REFERENCES work_orders(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS work_order_reviews (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            order_id BIGINT NOT NULL UNIQUE,
            rating INT NOT NULL,
            comment TEXT,
            tags LONGTEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_work_order_reviews_order FOREIGN KEY (order_id) REFERENCES work_orders(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS work_order_forms (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(255) NOT NULL,
            form_type VARCHAR(64) NOT NULL,
            form_type_label VARCHAR(255),
            fields LONGTEXT NOT NULL,
            html_template LONGTEXT,
            embed_code LONGTEXT,
            is_active TINYINT DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS ai_operation_logs (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            article_id BIGINT,
            agent_name VARCHAR(128),
            action_type VARCHAR(64),
            operator_id BIGINT NULL,
            operator_name VARCHAR(128),
            ok TINYINT DEFAULT 0,
            summary VARCHAR(512),
            result_json LONGTEXT,
            error_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_ai_operation_logs_article FOREIGN KEY (article_id) REFERENCES articles(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
    ]

    for statement in statements:
        cursor.execute(statement)

    _ensure_mysql_index(cursor, "idx_articles_status", "articles", "status")
    _ensure_mysql_index(cursor, "idx_articles_review_status", "articles", "review_status")
    _ensure_mysql_index(cursor, "idx_articles_publish_status", "articles", "publish_status")
    _ensure_mysql_index(cursor, "idx_publish_tasks_status", "publish_tasks", "status")
    _ensure_mysql_index(cursor, "idx_publish_tasks_article_id", "publish_tasks", "article_id")
    _ensure_mysql_index(cursor, "idx_publish_tasks_updated_at", "publish_tasks", "updated_at")
    _ensure_mysql_index(cursor, "idx_publish_tasks_created_at", "publish_tasks", "created_at")
    _ensure_mysql_index(cursor, "idx_leads_status", "leads", "status")
    _ensure_mysql_index(cursor, "idx_work_orders_status", "work_orders", "status")
    _ensure_mysql_index(cursor, "idx_ai_operation_logs_article_id", "ai_operation_logs", "article_id")
    _ensure_mysql_index(cursor, "idx_ai_operation_logs_created_at", "ai_operation_logs", "created_at")

    _ensure_article_cover_columns(conn)
    init_default_templates(conn)
    conn.commit()
    conn.close()
    print("[DB] MySQL/RDS 表结构初始化完成；默认数据兼容将在 3D 阶段显式处理")


def _ensure_mysql_index(cursor, index_name, table_name, columns, unique=False):
    """MySQL 不稳定支持 CREATE INDEX IF NOT EXISTS，因此先查再建。"""
    cursor.execute(
        """
        SELECT COUNT(*) AS index_count
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND index_name = %s
        """,
        (table_name, index_name),
    )
    row = cursor.fetchone()
    exists = (row or {}).get("index_count", 0) > 0
    if exists:
        return

    unique_sql = "UNIQUE " if unique else ""
    cursor.execute(f"CREATE {unique_sql}INDEX {index_name} ON {table_name} ({columns})")


def _ensure_article_status_columns(conn):
    """确保 articles 表存在 review_status 与 publish_status 字段。"""
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(articles)").fetchall()
    }

    # 旧库缺字段时安全补齐，保持旧 status 字段不变。
    if "review_status" not in columns:
        conn.execute(
            f"ALTER TABLE articles ADD COLUMN review_status TEXT DEFAULT '{REVIEW_STATUS_DRAFT}'"
        )

    if "publish_status" not in columns:
        conn.execute(
            f"ALTER TABLE articles ADD COLUMN publish_status TEXT DEFAULT '{PUBLISH_STATUS_NOT_READY}'"
        )

    # 统一以旧 status 为准回填新字段，保证双写兼容的一致性。
    conn.execute(
        """
        UPDATE articles
        SET
            review_status = CASE status
                WHEN 'draft' THEN 'draft'
                WHEN 'approved' THEN 'approved'
                WHEN 'draft_sent' THEN 'approved'
                WHEN 'published' THEN 'approved'
                WHEN 'rejected' THEN 'rejected'
                WHEN 'error' THEN 'approved'
                ELSE 'draft'
            END,
            publish_status = CASE status
                WHEN 'draft' THEN 'not_ready'
                WHEN 'approved' THEN 'not_ready'
                WHEN 'draft_sent' THEN 'draft_sent'
                WHEN 'published' THEN 'published'
                WHEN 'rejected' THEN 'not_ready'
                WHEN 'error' THEN 'failed'
                ELSE 'not_ready'
            END
        """
    )
    conn.commit()


def _ensure_article_cover_columns(conn):
    """确保 articles 表具备封面图字段，兼容旧库增量升级。"""
    if is_mysql():
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COLUMN_NAME AS column_name
            FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = %s
            """,
            ("articles",),
        )
        columns = {row["column_name"] for row in cursor.fetchall()}

        if "cover_image" not in columns:
            conn.execute("ALTER TABLE articles ADD COLUMN cover_image TEXT")
        if "cover_status" not in columns:
            conn.execute("ALTER TABLE articles ADD COLUMN cover_status VARCHAR(32) DEFAULT 'pending'")
        if "cover_prompt" not in columns:
            conn.execute("ALTER TABLE articles ADD COLUMN cover_prompt LONGTEXT")

        conn.execute(
            """
            UPDATE articles
            SET cover_status = CASE
                WHEN COALESCE(cover_status, '') <> '' THEN cover_status
                WHEN COALESCE(cover_image, '') <> '' OR COALESCE(cover_url, '') <> '' THEN 'success'
                ELSE 'pending'
            END
            """
        )
        conn.commit()
        return

    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(articles)").fetchall()
    }
    if "cover_image" not in columns:
        conn.execute("ALTER TABLE articles ADD COLUMN cover_image TEXT")
    if "cover_status" not in columns:
        conn.execute("ALTER TABLE articles ADD COLUMN cover_status TEXT DEFAULT 'pending'")
    if "cover_prompt" not in columns:
        conn.execute("ALTER TABLE articles ADD COLUMN cover_prompt TEXT")

    conn.execute(
        """
        UPDATE articles
        SET cover_status = CASE
            WHEN IFNULL(cover_status, '') <> '' THEN cover_status
            WHEN IFNULL(cover_image, '') <> '' OR IFNULL(cover_url, '') <> '' THEN 'success'
            ELSE 'pending'
        END
        """
    )
    conn.commit()


def _insert_default_lead_forms(conn):
    """插入默认留资表单配置"""
    existing = conn.execute("SELECT COUNT(*) FROM lead_forms").fetchone()[0]
    if existing > 0:
        return
    
    import json
    forms = [
        {
            "name": "征信诊断表单",
            "form_type": "credit_diagnosis",
            "fields": json.dumps([
                {"name": "name", "label": "姓名", "type": "text", "required": True},
                {"name": "phone", "label": "手机号", "type": "tel", "required": True},
                {"name": "loan_amount", "label": "意向贷款金额", "type": "select", "options": ["30万以下", "30-100万", "100-300万", "300万以上"], "required": True},
                {"name": "credit_status", "label": "征信情况", "type": "select", "options": ["征信良好", "有少量逾期", "逾期较多", "不清楚"], "required": True}
            ], ensure_ascii=False),
            "template_categories": json.dumps(["leads", "service"], ensure_ascii=False),
            "html_template": '''<div class="lead-form-container" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:24px;margin:24px 0;">
    <h3 style="color:#1e40af;margin-bottom:16px;">📋 免费征信诊断</h3>
    <p style="color:#64748b;margin-bottom:20px;">填写以下信息，专业顾问将在24小时内为您评估贷款可行性</p>
    <form class="lead-form" data-form-type="credit_diagnosis">
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;">姓名 *</label>
            <input type="text" name="name" required style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;">手机号 *</label>
            <input type="tel" name="phone" required pattern="1[3-9]\\d{9}" style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;">意向贷款金额 *</label>
            <select name="loan_amount" required style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;">
                <option value="">请选择</option>
                <option value="30万以下">30万以下</option>
                <option value="30-100万">30-100万</option>
                <option value="100-300万">100-300万</option>
                <option value="300万以上">300万以上</option>
            </select>
        </div>
        <div style="margin-bottom:20px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;">征信情况 *</label>
            <select name="credit_status" required style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;">
                <option value="">请选择</option>
                <option value="征信良好">征信良好</option>
                <option value="有少量逾期">有少量逾期</option>
                <option value="逾期较多">逾期较多</option>
                <option value="不清楚">不清楚</option>
            </select>
        </div>
        <button type="submit" style="width:100%;background:#1e40af;color:white;padding:12px 24px;border:none;border-radius:8px;font-size:16px;cursor:pointer;font-weight:500;">提交申请</button>
        <p style="color:#94a3b8;font-size:12px;margin-top:12px;text-align:center;">信息严格保密，仅用于贷款评估</p>
    </form>
</div>''',
            "crm_sync_config": json.dumps({"enabled": True, "crm_type": "qiyeweixin", "auto_assign": True}, ensure_ascii=False)
        },
        {
            "name": "额度测算表单",
            "form_type": "quota_calc",
            "fields": json.dumps([
                {"name": "name", "label": "姓名", "type": "text", "required": True},
                {"name": "phone", "label": "手机号", "type": "tel", "required": True},
                {"name": "loan_amount", "label": "期望贷款金额", "type": "text", "placeholder": "例如：100万", "required": True},
                {"name": "credit_status", "label": "当前征信状况", "type": "select", "options": ["无逾期", "1-2次逾期", "3次以上逾期", "有当前逾期"], "required": True}
            ], ensure_ascii=False),
            "template_categories": json.dumps(["leads", "service", "finance"], ensure_ascii=False),
            "html_template": '''<div class="lead-form-container" style="background:linear-gradient(135deg,#1e40af 0%,#3b82f6 100%);border-radius:12px;padding:24px;margin:24px 0;color:white;">
    <h3 style="margin-bottom:12px;">💰 免费额度测算</h3>
    <p style="opacity:0.9;margin-bottom:20px;">1分钟填写，快速了解您可申请的贷款额度</p>
    <form class="lead-form" data-form-type="quota_calc">
        <div style="margin-bottom:14px;">
            <input type="text" name="name" placeholder="您的姓名" required style="width:100%;padding:12px 16px;border:none;border-radius:8px;box-sizing:border-box;color:#333;">
        </div>
        <div style="margin-bottom:14px;">
            <input type="tel" name="phone" placeholder="手机号" required pattern="1[3-9]\\d{9}" style="width:100%;padding:12px 16px;border:none;border-radius:8px;box-sizing:border-box;color:#333;">
        </div>
        <div style="margin-bottom:14px;">
            <input type="text" name="loan_amount" placeholder="期望贷款金额（如：100万）" required style="width:100%;padding:12px 16px;border:none;border-radius:8px;box-sizing:border-box;color:#333;">
        </div>
        <div style="margin-bottom:18px;">
            <select name="credit_status" required style="width:100%;padding:12px 16px;border:none;border-radius:8px;box-sizing:border-box;color:#333;">
                <option value="">当前征信状况</option>
                <option value="无逾期">无逾期</option>
                <option value="1-2次逾期">1-2次逾期</option>
                <option value="3次以上逾期">3次以上逾期</option>
                <option value="有当前逾期">有当前逾期</option>
            </select>
        </div>
        <button type="submit" style="width:100%;background:#f59e0b;color:#1e3a5f;padding:14px 24px;border:none;border-radius:8px;font-size:16px;cursor:pointer;font-weight:600;">立即测算额度</button>
    </form>
</div>''',
            "crm_sync_config": json.dumps({"enabled": True, "crm_type": "qiyeweixin", "auto_assign": True}, ensure_ascii=False)
        }
    ]
    
    for f in forms:
        if is_mysql():
            # MySQL 分支显式使用 INSERT IGNORE；重复插入仍主要依赖前面的整表 count 守卫。
            conn.execute(
                """
                INSERT IGNORE INTO lead_forms (name, form_type, fields, template_categories, html_template, crm_sync_config)
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (f["name"], f["form_type"], f["fields"], f["template_categories"], f["html_template"], f["crm_sync_config"]),
            )
        else:
            conn.execute(
                """
                INSERT OR IGNORE INTO lead_forms (name, form_type, fields, template_categories, html_template, crm_sync_config)
                VALUES (?,?,?,?,?,?)
                """,
                (f["name"], f["form_type"], f["fields"], f["template_categories"], f["html_template"], f["crm_sync_config"]),
            )
    conn.commit()
    print("[DB] 默认留资表单已插入")


def _insert_default_keyword_replies(conn):
    """插入默认关键词回复配置"""
    existing = conn.execute("SELECT COUNT(*) FROM keyword_replies").fetchone()[0]
    if existing > 0:
        return
    
    replies = [
        ("贷款", "text", "您这边大概需要多少额度的贷款？我可以根据您的需求，帮您申请最低利率、最优还款方式的方案～", "contain", 10),
        ("融资", "text", "您计划融资多少资金？我帮您对接最合适的银行 / 机构，争取最优的融资条件～", "contain", 10),
        ("征信", "text", "您的征信情况怎么样？如果有小瑕疵我也可以帮您优化，提高审批通过率～", "contain", 10),
        ("企业经营", "text", "您企业主要是做什么业务的呢？我可以根据您的行业特性，帮您申请利率最优、额度最高的企业经营贷方案～", "contain", 10),
    ]
    
    for keyword, reply_type, content, match_mode, priority in replies:
        if is_mysql():
            # keyword 字段本身有唯一约束，MySQL 下可安全使用 INSERT IGNORE。
            conn.execute(
                """
                INSERT IGNORE INTO keyword_replies (keyword, reply_type, reply_content, match_mode, priority)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (keyword, reply_type, content, match_mode, priority),
            )
        else:
            conn.execute(
                """
                INSERT OR IGNORE INTO keyword_replies (keyword, reply_type, reply_content, match_mode, priority)
                VALUES (?,?,?,?,?)
                """,
                (keyword, reply_type, content, match_mode, priority),
            )
    conn.commit()
    print("[DB] 默认关键词回复已插入")


def _insert_default_advisors(conn):
    """插入默认顾问数据"""
    existing = conn.execute("SELECT COUNT(*) FROM advisors").fetchone()[0]
    if existing > 0:
        return
    
    import json
    advisors = [
        ("张顾问", "13800138001", json.dumps(["浦东新区", "黄浦区", "徐汇区"], ensure_ascii=False), json.dumps(["个人信贷", "房产抵押", "贷款方案匹配"], ensure_ascii=False), 15),
        ("李顾问", "13800138002", json.dumps(["静安区", "长宁区", "普陀区"], ensure_ascii=False), json.dumps(["企业经营贷", "信用贷款", "企业经营分析"], ensure_ascii=False), 12),
        ("王顾问", "13800138003", json.dumps(["虹口区", "杨浦区", "宝山区"], ensure_ascii=False), json.dumps(["融资规划", "大额贷款", "融资规划"], ensure_ascii=False), 10),
        ("陈顾问", "13800138004", json.dumps(["闵行区", "松江区", "青浦区"], ensure_ascii=False), json.dumps(["个人信贷", "企业经营贷", "贷款方案匹配"], ensure_ascii=False), 10),
        ("刘顾问", "13800138005", json.dumps(["嘉定区", "金山区", "奉贤区", "崇明区"], ensure_ascii=False), json.dumps(["房产抵押", "信用贷款", "融资规划"], ensure_ascii=False), 8),
    ]
    
    for name, phone, regions, specialties, max_leads in advisors:
        if is_mysql():
            # advisors 表当前没有唯一键，防重仍依赖前面的 count 守卫；INSERT IGNORE 仅用于显式 MySQL 分支。
            conn.execute(
                """
                INSERT IGNORE INTO advisors (name, phone, regions, specialties, max_leads)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (name, phone, regions, specialties, max_leads),
            )
        else:
            conn.execute(
                """
                INSERT OR IGNORE INTO advisors (name, phone, regions, specialties, max_leads)
                VALUES (?,?,?,?,?)
                """,
                (name, phone, regions, specialties, max_leads),
            )
    conn.commit()
    print("[DB] 默认顾问数据已插入")


def _insert_default_work_order_forms(conn):
    """插入默认工单表单配置"""
    existing = conn.execute("SELECT COUNT(*) FROM work_order_forms").fetchone()[0]
    if existing > 0:
        return
    
    import json
    forms = [
        {
            "name": "贷款方案匹配表单",
            "form_type": "loan_match",
            "form_type_label": "贷款方案匹配",
            "fields": json.dumps([
                {"name": "name", "label": "姓名", "type": "text", "required": True, "placeholder": "请输入您的姓名"},
                {"name": "phone", "label": "联系方式", "type": "tel", "required": True, "placeholder": "请输入手机号"},
                {"name": "loan_amount", "label": "贷款需求", "type": "select", "required": True, "options": ["30万以下", "30-100万", "100-300万", "300万以上"]},
                {"name": "description", "label": "详细需求", "type": "textarea", "required": True, "placeholder": "请描述您的贷款用途、还款能力等情况"}
            ], ensure_ascii=False),
            "html_template": '''<div class="work-order-form" data-form-type="loan_match" style="background:#f0f9ff;border:2px solid #0ea5e9;border-radius:12px;padding:24px;margin:20px 0;">
    <h3 style="color:#0369a1;margin-bottom:8px;">📝 贷款方案匹配</h3>
    <p style="color:#64748b;margin-bottom:20px;font-size:14px;">填写需求，专业顾问为您定制最优贷款方案</p>
    <form onsubmit="submitWorkOrder(event, 'loan_match')">
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">姓名 *</label>
            <input type="text" name="name" required placeholder="请输入您的姓名" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">联系方式 *</label>
            <input type="tel" name="phone" required pattern="1[3-9]\\d{9}" placeholder="请输入手机号" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">贷款需求 *</label>
            <select name="loan_amount" required style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;background:white;">
                <option value="">请选择贷款金额</option>
                <option value="30万以下">30万以下</option>
                <option value="30-100万">30-100万</option>
                <option value="100-300万">100-300万</option>
                <option value="300万以上">300万以上</option>
            </select>
        </div>
        <div style="margin-bottom:20px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">详细需求 *</label>
            <textarea name="description" required rows="4" placeholder="请描述您的贷款用途、还款能力、征信情况等" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;resize:vertical;"></textarea>
        </div>
        <button type="submit" style="width:100%;background:#0ea5e9;color:white;padding:14px;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;">提交申请</button>
        <p style="color:#94a3b8;font-size:12px;margin-top:12px;text-align:center;">信息严格保密，仅用于方案匹配</p>
    </form>
</div>''',
            "embed_code": '''<a href="javascript:void(0)" onclick="document.getElementById('work-order-loan-match').style.display='block';this.style.display='none';" class="work-order-btn" style="display:inline-block;padding:10px 20px;background:#0ea5e9;color:white;text-decoration:none;border-radius:6px;font-size:14px;">申请贷款方案匹配</a><div id="work-order-loan-match" style="display:none;margin-top:16px;">''' + '''<div class="work-order-form" data-form-type="loan_match" style="background:#f0f9ff;border:2px solid #0ea5e9;border-radius:12px;padding:24px;margin:20px 0;">
    <h3 style="color:#0369a1;margin-bottom:8px;">📝 贷款方案匹配</h3>
    <p style="color:#64748b;margin-bottom:20px;font-size:14px;">填写需求，专业顾问为您定制最优贷款方案</p>
    <form onsubmit="submitWorkOrder(event, 'loan_match')">
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">姓名 *</label>
            <input type="text" name="name" required placeholder="请输入您的姓名" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">联系方式 *</label>
            <input type="tel" name="phone" required pattern="1[3-9]\\d{9}" placeholder="请输入手机号" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">贷款需求 *</label>
            <select name="loan_amount" required style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;background:white;">
                <option value="">请选择贷款金额</option>
                <option value="30万以下">30万以下</option>
                <option value="30-100万">30-100万</option>
                <option value="100-300万">100-300万</option>
                <option value="300万以上">300万以上</option>
            </select>
        </div>
        <div style="margin-bottom:20px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">详细需求 *</label>
            <textarea name="description" required rows="4" placeholder="请描述您的贷款用途、还款能力、征信情况等" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;resize:vertical;"></textarea>
        </div>
        <button type="submit" style="width:100%;background:#0ea5e9;color:white;padding:14px;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;">提交申请</button>
        <p style="color:#94a3b8;font-size:12px;margin-top:12px;text-align:center;">信息严格保密，仅用于方案匹配</p>
    </form>
</div></div>'''
        },
        {
            "name": "融资规划表单",
            "form_type": "finance_plan",
            "form_type_label": "融资规划",
            "fields": json.dumps([
                {"name": "name", "label": "姓名", "type": "text", "required": True, "placeholder": "请输入您的姓名"},
                {"name": "phone", "label": "联系方式", "type": "tel", "required": True, "placeholder": "请输入手机号"},
                {"name": "company_type", "label": "企业类型", "type": "select", "required": True, "options": ["个体工商户", "小微企业", "中型企业", "其他"]},
                {"name": "description", "label": "融资需求", "type": "textarea", "required": True, "placeholder": "请描述您的企业情况、融资用途、期望额度等"}
            ], ensure_ascii=False),
            "html_template": '''<div class="work-order-form" data-form-type="finance_plan" style="background:#f5f3ff;border:2px solid #8b5cf6;border-radius:12px;padding:24px;margin:20px 0;">
    <h3 style="color:#5b21b6;margin-bottom:8px;">📊 融资规划咨询</h3>
    <p style="color:#64748b;margin-bottom:20px;font-size:14px;">为企业量身定制融资方案，降低融资成本</p>
    <form onsubmit="submitWorkOrder(event, 'finance_plan')">
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">姓名 *</label>
            <input type="text" name="name" required placeholder="请输入您的姓名" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">联系方式 *</label>
            <input type="tel" name="phone" required pattern="1[3-9]\\d{9}" placeholder="请输入手机号" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">企业类型 *</label>
            <select name="company_type" required style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;background:white;">
                <option value="">请选择企业类型</option>
                <option value="个体工商户">个体工商户</option>
                <option value="小微企业">小微企业</option>
                <option value="中型企业">中型企业</option>
                <option value="其他">其他</option>
            </select>
        </div>
        <div style="margin-bottom:20px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">融资需求 *</label>
            <textarea name="description" required rows="4" placeholder="请描述您的企业情况、融资用途、期望额度、还款来源等" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;resize:vertical;"></textarea>
        </div>
        <button type="submit" style="width:100%;background:#8b5cf6;color:white;padding:14px;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;">获取融资方案</button>
        <p style="color:#94a3b8;font-size:12px;margin-top:12px;text-align:center;">专业顾问将在2小时内与您联系</p>
    </form>
</div>''',
            "embed_code": '''<a href="javascript:void(0)" onclick="document.getElementById('work-order-finance-plan').style.display='block';this.style.display='none';" class="work-order-btn" style="display:inline-block;padding:10px 20px;background:#8b5cf6;color:white;text-decoration:none;border-radius:6px;font-size:14px;">申请融资规划</a><div id="work-order-finance-plan" style="display:none;margin-top:16px;">''' + '''<div class="work-order-form" data-form-type="finance_plan" style="background:#f5f3ff;border:2px solid #8b5cf6;border-radius:12px;padding:24px;margin:20px 0;">
    <h3 style="color:#5b21b6;margin-bottom:8px;">📊 融资规划咨询</h3>
    <p style="color:#64748b;margin-bottom:20px;font-size:14px;">为企业量身定制融资方案，降低融资成本</p>
    <form onsubmit="submitWorkOrder(event, 'finance_plan')">
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">姓名 *</label>
            <input type="text" name="name" required placeholder="请输入您的姓名" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">联系方式 *</label>
            <input type="tel" name="phone" required pattern="1[3-9]\\d{9}" placeholder="请输入手机号" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">企业类型 *</label>
            <select name="company_type" required style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;background:white;">
                <option value="">请选择企业类型</option>
                <option value="个体工商户">个体工商户</option>
                <option value="小微企业">小微企业</option>
                <option value="中型企业">中型企业</option>
                <option value="其他">其他</option>
            </select>
        </div>
        <div style="margin-bottom:20px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">融资需求 *</label>
            <textarea name="description" required rows="4" placeholder="请描述您的企业情况、融资用途、期望额度、还款来源等" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;resize:vertical;"></textarea>
        </div>
        <button type="submit" style="width:100%;background:#8b5cf6;color:white;padding:14px;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;">获取融资方案</button>
        <p style="color:#94a3b8;font-size:12px;margin-top:12px;text-align:center;">专业顾问将在2小时内与您联系</p>
    </form>
</div></div>'''
        },
        {
            "name": "企业经营分析表单",
            "form_type": "enterprise_analysis",
            "form_type_label": "企业经营分析",
            "fields": json.dumps([
                {"name": "name", "label": "姓名", "type": "text", "required": True, "placeholder": "请输入您的姓名"},
                {"name": "phone", "label": "联系方式", "type": "tel", "required": True, "placeholder": "请输入手机号"},
                {"name": "industry", "label": "所属行业", "type": "text", "required": True, "placeholder": "如：餐饮、制造、零售等"},
                {"name": "description", "label": "经营情况", "type": "textarea", "required": True, "placeholder": "请描述您的经营现状、遇到的问题、资金需求等"}
            ], ensure_ascii=False),
            "html_template": '''<div class="work-order-form" data-form-type="enterprise_analysis" style="background:#ecfdf5;border:2px solid #10b981;border-radius:12px;padding:24px;margin:20px 0;">
    <h3 style="color:#047857;margin-bottom:8px;">📈 企业经营分析</h3>
    <p style="color:#64748b;margin-bottom:20px;font-size:14px;">深度分析企业经营状况，提供优化建议与资金解决方案</p>
    <form onsubmit="submitWorkOrder(event, 'enterprise_analysis')">
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">姓名 *</label>
            <input type="text" name="name" required placeholder="请输入您的姓名" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">联系方式 *</label>
            <input type="tel" name="phone" required pattern="1[3-9]\\d{9}" placeholder="请输入手机号" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">所属行业 *</label>
            <input type="text" name="industry" required placeholder="如：餐饮、制造、零售、科技等" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:20px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">经营情况 *</label>
            <textarea name="description" required rows="4" placeholder="请描述您的经营现状、遇到的问题（现金流、成本、营收等）、资金需求等" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;resize:vertical;"></textarea>
        </div>
        <button type="submit" style="width:100%;background:#10b981;color:white;padding:14px;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;">申请经营分析</button>
        <p style="color:#94a3b8;font-size:12px;margin-top:12px;text-align:center;">专业分析师将在24小时内出具诊断报告</p>
    </form>
</div>''',
            "embed_code": '''<a href="javascript:void(0)" onclick="document.getElementById('work-order-enterprise-analysis').style.display='block';this.style.display='none';" class="work-order-btn" style="display:inline-block;padding:10px 20px;background:#10b981;color:white;text-decoration:none;border-radius:6px;font-size:14px;">申请经营分析</a><div id="work-order-enterprise-analysis" style="display:none;margin-top:16px;">''' + '''<div class="work-order-form" data-form-type="enterprise_analysis" style="background:#ecfdf5;border:2px solid #10b981;border-radius:12px;padding:24px;margin:20px 0;">
    <h3 style="color:#047857;margin-bottom:8px;">📈 企业经营分析</h3>
    <p style="color:#64748b;margin-bottom:20px;font-size:14px;">深度分析企业经营状况，提供优化建议与资金解决方案</p>
    <form onsubmit="submitWorkOrder(event, 'enterprise_analysis')">
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">姓名 *</label>
            <input type="text" name="name" required placeholder="请输入您的姓名" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">联系方式 *</label>
            <input type="tel" name="phone" required pattern="1[3-9]\\d{9}" placeholder="请输入手机号" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">所属行业 *</label>
            <input type="text" name="industry" required placeholder="如：餐饮、制造、零售、科技等" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:20px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">经营情况 *</label>
            <textarea name="description" required rows="4" placeholder="请描述您的经营现状、遇到的问题（现金流、成本、营收等）、资金需求等" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;resize:vertical;"></textarea>
        </div>
        <button type="submit" style="width:100%;background:#10b981;color:white;padding:14px;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;">申请经营分析</button>
        <p style="color:#94a3b8;font-size:12px;margin-top:12px;text-align:center;">专业分析师将在24小时内出具诊断报告</p>
    </form>
</div></div>'''
        }
    ]
    
    for f in forms:
        if is_mysql():
            # work_order_forms 表当前没有唯一键，防重仍依赖前面的 count 守卫；INSERT IGNORE 仅用于显式 MySQL 分支。
            conn.execute(
                """
                INSERT IGNORE INTO work_order_forms (name, form_type, form_type_label, fields, html_template, embed_code)
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (f["name"], f["form_type"], f["form_type_label"], f["fields"], f["html_template"], f["embed_code"]),
            )
        else:
            conn.execute(
                """
                INSERT OR IGNORE INTO work_order_forms (name, form_type, form_type_label, fields, html_template, embed_code)
                VALUES (?,?,?,?,?,?)
                """,
                (f["name"], f["form_type"], f["form_type_label"], f["fields"], f["html_template"], f["embed_code"]),
            )
    conn.commit()
    print("[DB] 默认工单表单配置已插入")


def init_default_templates(conn=None):
    """初始化六大默认写作模板，已存在同名模板时跳过。

    这个函数用于新部署和老库补齐。它不会覆盖用户已经编辑过的模板。
    """
    import json

    owns_connection = conn is None
    if conn is None:
        conn = get_db()

    templates = [
        {
            "name": "品牌宣传型模板",
            "category": "brand",
            "category_label": "品牌宣传",
            "description": "用于展示沪上银品牌故事、服务亮点、客户证言和可信赖形象。",
            "structure": ["品牌故事/案例", "服务亮点", "客户证言", "品牌价值观", "联系方式"],
            "pain_point": "读者不了解沪上银是谁、能帮什么、靠不靠谱",
            "hook": "关注我们，每周分享贷款干货｜私信「了解」获取服务介绍",
            "prompt_template": "请以「{topic}」为主题，写一篇品牌宣传型公众号文章。文章要围绕沪上银的专业能力、服务亮点、真实案例和可信赖感展开，语气真诚、稳重、有温度，结尾自然引导读者关注或咨询。",
        },
        {
            "name": "企业经营分析型模板",
            "category": "enterprise",
            "category_label": "企业经营分析",
            "description": "用于分析企业经营痛点、现金流压力、营收成本和资金解决方案。",
            "structure": ["经营痛点", "数据分析", "行业对标", "优化建议", "资金解决方案"],
            "pain_point": "小微企业主遇到现金流、营收、成本等经营难题，不知如何改善",
            "hook": "经营遇到资金问题？沪上银帮你找到最合适的融资方式",
            "prompt_template": "请以「{topic}」为主题，写一篇企业经营分析型公众号文章。文章要先指出经营痛点，再结合数据或行业常识分析原因，给出可操作建议，并自然延伸到资金周转或融资解决方案。",
        },
        {
            "name": "融资规划型模板",
            "category": "finance",
            "category_label": "融资规划",
            "description": "用于帮助企业或个体户判断融资需求、测算成本并规划融资路径。",
            "structure": ["融资需求判断", "融资方式选择", "成本测算", "风险提示", "规划建议"],
            "pain_point": "企业/个体户不知道如何规划融资，股权稀释vs债务负担怎么取舍",
            "hook": "需要专业融资规划？回复「规划」，沪上银融资顾问为你量身定制",
            "prompt_template": "请以「{topic}」为主题，写一篇融资规划型公众号文章。内容要比较不同融资方式，解释成本、周期、风险和适用场景，帮助企业主形成清晰的融资规划。",
        },
        {
            "name": "自动获客型模板",
            "category": "leads",
            "category_label": "自动获客",
            "description": "用于承接读者贷款咨询需求，引导读者留言、私信或点击咨询入口。",
            "structure": ["痛点共鸣", "问题分析", "解决方案", "成功案例", "行动号召"],
            "pain_point": "读者正在为贷款问题发愁，不知道找谁、怎么申请、利率高不高",
            "hook": "点击下方菜单「免费咨询」，或直接回复「咨询」，顾问24小时内联系你",
            "prompt_template": "请以「{topic}」为主题，写一篇自动获客型公众号文章。开头制造强共鸣，中间分析读者贷款申请中的困惑，给出解决方案和案例，结尾明确引导咨询。",
        },
        {
            "name": "贷款知识科普型模板",
            "category": "science",
            "category_label": "贷款知识科普",
            "description": "用于用大白话解释贷款概念、申请规则、常见误区和避坑知识。",
            "structure": ["提问切入", "概念解释（大白话）", "实际案例计算", "常见误区", "沪上银小结"],
            "pain_point": "读者对贷款知识一知半解，容易被忽悠或踩坑",
            "hook": "看完还有疑问？回复这篇文章的关键词，获取专属解答",
            "prompt_template": "请以「{topic}」为主题，写一篇贷款知识科普型公众号文章。用大白话解释概念，加入实际案例或简单计算，列出常见误区，最后用沪上银小结帮助读者做判断。",
        },
        {
            "name": "贷款方案匹配模板",
            "category": "service",
            "category_label": "贷款方案匹配",
            "description": "用于根据不同读者画像对比贷款方案，推荐合适申请路径。",
            "structure": ["读者画像（你是哪种情况）", "不同方案对比", "推荐方案", "申请攻略", "免费咨询入口"],
            "pain_point": "读者不知道哪种贷款产品适合自己，市场产品眼花缭乱",
            "hook": "不确定哪个方案适合你？点击菜单「方案匹配」，填写基本信息，顾问帮你一对一分析",
            "prompt_template": "请以「{topic}」为主题，写一篇贷款方案匹配型公众号文章。先区分不同读者画像，再对比方案优劣，给出推荐路径、申请攻略和免费咨询入口。",
        },
    ]

    inserted_count = 0
    for template in templates:
        if is_mysql():
            existing = conn.execute(
                "SELECT id FROM article_templates WHERE name=%s LIMIT 1",
                (template["name"],),
            ).fetchone()
        else:
            existing = conn.execute(
                "SELECT id FROM article_templates WHERE name=? LIMIT 1",
                (template["name"],),
            ).fetchone()
        if existing:
            continue

        structure_json = json.dumps(template["structure"], ensure_ascii=False)
        brand_rules = json.dumps(
            {
                "title_suffix": "",
                "footer": "沪上银｜上海专业贷款顾问",
                "cta": template["hook"],
                "watermark": "沪上银原创",
                "description": template["description"],
                "status": "enabled",
            },
            ensure_ascii=False,
        )
        solution = template["description"]
        params = (
            template["name"],
            template["category"],
            template["category_label"],
            structure_json,
            template["pain_point"],
            solution,
            template["hook"],
            brand_rules,
            template["prompt_template"],
            1,
        )

        if is_mysql():
            conn.execute(
                """
                INSERT INTO article_templates
                (name, category, category_label, structure, pain_point, solution, hook, brand_rules, prompt_template, is_active)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                params,
            )
        else:
            conn.execute(
                """
                INSERT INTO article_templates
                (name, category, category_label, structure, pain_point, solution, hook, brand_rules, prompt_template, is_active)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                params,
            )
        inserted_count += 1

    conn.commit()
    if owns_connection:
        conn.close()
    print(f"[DB] 默认写作模板检查完成，补齐 {inserted_count} 个")


def _insert_default_templates(conn):
    """插入6大定位的默认写作模板（已存在则跳过）"""
    existing = conn.execute("SELECT COUNT(*) FROM article_templates").fetchone()[0]
    if existing > 0:
        return

    import json
    templates = [
        {
            "name": "自动获客型模板",
            "category": "leads",
            "category_label": "自动获客",
            "structure": json.dumps(["痛点共鸣", "问题分析", "解决方案", "成功案例", "行动号召"], ensure_ascii=False),
            "pain_point": "读者正在为贷款问题发愁，不知道找谁、怎么申请、利率高不高",
            "solution": "沪上银专业顾问一对一梳理方案，帮你找到最合适的贷款产品",
            "hook": "点击下方菜单「免费咨询」，或直接回复「咨询」，顾问24小时内联系你",
            "brand_rules": json.dumps({
                "title_suffix": "",
                "footer": "沪上银 · 上海专业贷款顾问",
                "cta": "有贷款疑问？回复「咨询」，我们帮你搞定",
                "watermark": "沪上银原创"
            }, ensure_ascii=False),
            "prompt_template": "请以「{topic}」为主题，写一篇引导读者留资咨询的文章。开头用一个真实场景引发共鸣，中间分析问题，结尾明确告诉读者下一步行动。结尾自然提到沪上银。"
        },
        {
            "name": "品牌宣传型模板",
            "category": "brand",
            "category_label": "品牌宣传",
            "structure": json.dumps(["品牌故事/案例", "服务亮点", "客户证言", "品牌价值观", "联系方式"], ensure_ascii=False),
            "pain_point": "读者不了解沪上银是谁、能帮什么、靠不靠谱",
            "solution": "通过真实案例和服务详情，展示沪上银专业、靠谱、有温度的品牌形象",
            "hook": "关注我们，每周分享贷款干货 | 私信「了解」获取服务介绍",
            "brand_rules": json.dumps({
                "title_suffix": "",
                "footer": "沪上银 · 上海本地贷款顾问 · 搞不清楚贷款的，来找我们聊聊",
                "cta": "关注沪上银，贷款问题不用愁",
                "watermark": "沪上银原创"
            }, ensure_ascii=False),
            "prompt_template": "请以「{topic}」为主题，写一篇展示沪上银品牌形象的文章。语气真诚、有温度，通过案例或故事让读者感受到沪上银的专业与用心。"
        },
        {
            "name": "贷款知识科普型模板",
            "category": "science",
            "category_label": "贷款知识科普",
            "structure": json.dumps(["提问切入", "概念解释（大白话）", "实际案例计算", "常见误区", "沪上银小结"], ensure_ascii=False),
            "pain_point": "读者对贷款知识一知半解，容易被忽悠或错失优惠",
            "solution": "用大白话+真实例子，把复杂的贷款知识讲得简单易懂",
            "hook": "看完还有疑问？回复这篇文章的关键词，获取专属解答",
            "brand_rules": json.dumps({
                "title_suffix": "",
                "footer": "沪上银 · 专业贷款科普",
                "cta": "有疑问欢迎留言或私信，沪上银为你解答",
                "watermark": "沪上银科普"
            }, ensure_ascii=False),
            "prompt_template": "请以「{topic}」为主题，写一篇贷款知识科普文章。要求：①用大白话解释专业术语 ②举具体数字例子（月供变化等）③澄清常见误区 ④结尾沪上银小结。"
        },
        {
            "name": "贷款方案匹配型模板",
            "category": "service",
            "category_label": "贷款方案匹配",
            "structure": json.dumps(["读者画像（你是哪种情况）", "不同方案对比", "推荐方案", "申请攻略", "免费咨询入口"], ensure_ascii=False),
            "pain_point": "读者不知道哪种贷款产品适合自己，市场产品眼花缭乱",
            "solution": "按照读者的情况（职业、资产、需求），推荐最适合的贷款方案",
            "hook": "不确定哪个方案适合你？点击菜单「方案匹配」，填写基本信息，顾问帮你一对一分析",
            "brand_rules": json.dumps({
                "title_suffix": "",
                "footer": "沪上银 · 专属方案顾问",
                "cta": "不确定哪种方案适合你？回复「方案」，免费为你匹配",
                "watermark": "沪上银方案"
            }, ensure_ascii=False),
            "prompt_template": "请以「{topic}」为主题，写一篇帮读者选择贷款方案的文章。要有清晰的对比表格或条件判断（如：如果你是XXX，推荐YYY），结尾引导去沪上银做免费方案匹配。"
        },
        {
            "name": "融资规划型模板",
            "category": "finance",
            "category_label": "融资规划",
            "structure": json.dumps(["融资需求判断", "融资方式选择", "成本测算", "风险提示", "规划建议"], ensure_ascii=False),
            "pain_point": "企业/个体户不知道如何规划融资，股权稀释vs债务负担怎么取舍",
            "solution": "提供系统化融资规划思路，帮助企业主做出更明智的融资决策",
            "hook": "需要专业融资规划？回复「规划」，沪上银融资顾问为你量身定制",
            "brand_rules": json.dumps({
                "title_suffix": " | 融资规划",
                "footer": "沪上银 · 企业融资顾问",
                "cta": "企业融资规划，找沪上银专业团队",
                "watermark": "沪上银融资"
            }, ensure_ascii=False),
            "prompt_template": "请以「{topic}」为主题，写一篇面向小微企业主的融资规划文章。包含：融资方式对比（股权/债权/银行贷款）、成本分析、风险提示、适用场景。语气专业但不晦涩。"
        },
        {
            "name": "企业经营分析型模板",
            "category": "enterprise",
            "category_label": "企业经营分析",
            "structure": json.dumps(["经营痛点", "数据分析", "行业对标", "优化建议", "资金解决方案"], ensure_ascii=False),
            "pain_point": "小微企业主遇到现金流、营收、成本等经营难题，不知从何改善",
            "solution": "从财务角度分析企业经营问题，给出可操作的改善建议和资金解决方案",
            "hook": "经营遇到资金问题？沪上银帮你找到最合适的融资方式",
            "brand_rules": json.dumps({
                "title_suffix": " | 经营分析",
                "footer": "沪上银 · 小微企业经营顾问",
                "cta": "经营遇到资金瓶颈？来找沪上银，专业解决方案等你",
                "watermark": "沪上银经营"
            }, ensure_ascii=False),
            "prompt_template": "请以「{topic}」为主题，写一篇面向小微企业主的经营分析文章。要有数据支撑、行业对比，给出切实可行的经营优化建议，结尾自然提到资金/融资解决方案。"
        }
    ]

    for t in templates:
        if is_mysql():
            # article_templates 表当前没有唯一键，防重仍依赖前面的 count 守卫；INSERT IGNORE 仅用于显式 MySQL 分支。
            conn.execute(
                """
                INSERT IGNORE INTO article_templates
                (name, category, category_label, structure, pain_point, solution, hook, brand_rules, prompt_template)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (t["name"], t["category"], t["category_label"], t["structure"],
                 t["pain_point"], t["solution"], t["hook"], t["brand_rules"], t["prompt_template"]),
            )
        else:
            conn.execute(
                """
                INSERT OR IGNORE INTO article_templates
                (name, category, category_label, structure, pain_point, solution, hook, brand_rules, prompt_template)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (t["name"], t["category"], t["category_label"], t["structure"],
                 t["pain_point"], t["solution"], t["hook"], t["brand_rules"], t["prompt_template"]),
            )
    conn.commit()
    print("[DB] 默认写作模板已插入")


def _insert_default_format_rules(conn):
    """插入默认格式化规则（已存在则跳过）"""
    existing = conn.execute("SELECT COUNT(*) FROM format_rules").fetchone()[0]
    if existing > 0:
        return

    import json
    rules = [
        {
            "name": "标题格式规范",
            "rule_type": "title_format",
            "config": json.dumps({
                "max_length": 30,
                "min_length": 8,
                "forbidden_suffixes": ["。", "！", "？", "……"],
                "preferred_patterns": ["数字+效果", "疑问式", "对比式"],
                "brand_append": False
            }, ensure_ascii=False)
        },
        {
            "name": "正文排版规范",
            "rule_type": "content_format",
            "config": json.dumps({
                "paragraph_min_chars": 50,
                "paragraph_max_chars": 200,
                "heading_style": "蓝色加粗",
                "highlight_numbers": True,
                "highlight_keywords": True,
                "add_brand_footer": True,
                "font_size_body": 16,
                "line_height": 1.9
            }, ensure_ascii=False)
        },
        {
            "name": "封面尺寸规范",
            "rule_type": "cover_format",
            "config": json.dumps({
                "width": 900,
                "height": 500,
                "ratio": "9:5",
                "brand_watermark": True,
                "watermark_position": "bottom-right"
            }, ensure_ascii=False)
        }
    ]

    for r in rules:
        if is_mysql():
            # format_rules 表当前没有唯一键，防重仍依赖前面的 count 守卫；INSERT IGNORE 仅用于显式 MySQL 分支。
            conn.execute(
                """
                INSERT IGNORE INTO format_rules (name, rule_type, config, is_active)
                VALUES (%s,%s,%s,1)
                """,
                (r["name"], r["rule_type"], r["config"]),
            )
        else:
            conn.execute(
                """
                INSERT OR IGNORE INTO format_rules (name, rule_type, config, is_active)
                VALUES (?,?,?,1)
                """,
                (r["name"], r["rule_type"], r["config"]),
            )
    conn.commit()
    print("[DB] 默认格式化规则已插入")


def _insert_default_sensitive_words(conn):
    """插入默认敏感词库（已存在则跳过）"""
    existing = conn.execute("SELECT COUNT(*) FROM sensitive_words").fetchone()[0]
    if existing > 0:
        return

    words = [
        # 金融合规敏感词（拦截）
        ("保本保息", "finance", "block", None),
        ("无风险收益", "finance", "block", None),
        ("稳赚不赔", "finance", "block", None),
        ("100%通过", "finance", "block", None),
        ("秒批", "finance", "block", None),
        ("零门槛贷款", "finance", "block", None),
        ("洗白征信", "finance", "block", None),
        ("征信修复", "finance", "replace", "征信管理"),
        ("高息", "finance", "warn", None),
        ("利滚利", "finance", "warn", None),
        ("暴利", "finance", "block", None),
        ("黑户也能贷", "finance", "block", None),
        # 夸大宣传（替换）
        ("最低利率", "finance", "replace", "较低利率"),
        ("全网最低", "finance", "block", None),
        ("一定能贷", "finance", "block", None),
        ("100%审批通过", "finance", "block", None),
        # 政治敏感（拦截）
        ("政治", "political", "block", None),
        ("体制", "political", "warn", None),
        # 垃圾广告词（拦截）
        ("点击领取", "spam", "block", None),
        ("限时免费", "spam", "warn", None),
        ("私下联系", "spam", "block", None),
    ]

    for word, category, action, replace_with in words:
        if is_mysql():
            # sensitive_words.word 字段有唯一约束，MySQL 下可安全使用 INSERT IGNORE。
            conn.execute(
                """
                INSERT IGNORE INTO sensitive_words (word, category, action, replace_with)
                VALUES (%s,%s,%s,%s)
                """,
                (word, category, action, replace_with),
            )
        else:
            conn.execute(
                """
                INSERT OR IGNORE INTO sensitive_words (word, category, action, replace_with)
                VALUES (?,?,?,?)
                """,
                (word, category, action, replace_with),
            )
    conn.commit()
    print("[DB] 默认敏感词库已插入")


if __name__ == "__main__":
    init_db()
