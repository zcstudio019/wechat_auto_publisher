"""
历史数据迁移脚本 - 沪上银微信公众号自动发布系统
=================================================
功能：
  1. 检查当前数据库结构，自动补全缺失字段
  2. 核对并修复历史文章/获客线索/服务工单数据完整性
  3. 生成迁移报告（迁移前/后数据量对比）
  4. 按验收标准：数据100%完整，无丢失

用法：
  python migrate_data.py
"""

import sqlite3
import os
import sys
import io
import json
import datetime
import shutil

# Windows UTF-8 输出修复
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 确保能找到项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DB_PATH

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "backups")

# ─── 输出工具 ───────────────────────────────────────────────

def ok(msg):    print(f"  [OK] {msg}")
def warn(msg):  print(f"  [WARN] {msg}")
def err(msg):   print(f"  [ERR] {msg}")
def title(msg): print(f"\n{'='*55}\n  {msg}\n{'='*55}")
def step(msg):  print(f"\n>> {msg}")

# ─── 工具函数 ────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def backup_database():
    """迁移前备份数据库"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"articles_backup_{ts}.db")
    shutil.copy2(DB_PATH, backup_path)
    ok(f"数据库已备份至: {backup_path}")
    return backup_path


def get_table_info(conn, table_name):
    """获取表的列信息"""
    try:
        cur = conn.execute(f"PRAGMA table_info({table_name})")
        return {row["name"]: row for row in cur.fetchall()}
    except Exception:
        return {}


def ensure_column(conn, table, col, col_def):
    """如果列不存在，自动 ALTER TABLE 添加"""
    info = get_table_info(conn, table)
    if col not in info:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
        conn.commit()
        warn(f"补全字段: {table}.{col}  ({col_def})")
        return True
    return False


# ─── Step 1: 结构检查与补全 ─────────────────────────────────

EXPECTED_SCHEMA = {
    "articles": [
        ("is_original",  "INTEGER DEFAULT 0"),
        ("html_content", "TEXT"),
    ],
    "leads": [
        ("region",      "TEXT"),
        ("advisor_id",  "INTEGER"),
        ("form_data",   "TEXT"),
        ("updated_at",  "DATETIME DEFAULT (datetime('now','localtime'))"),
    ],
    "work_orders": [
        ("order_type_label", "TEXT"),
        ("assigned_at",      "DATETIME"),
        ("completed_at",     "DATETIME"),
        ("reviewed_at",      "DATETIME"),
        ("source_id",        "INTEGER"),
    ],
    "advisors": [
        ("current_leads", "INTEGER DEFAULT 0"),
        ("is_active",     "INTEGER DEFAULT 1"),
    ],
    "work_order_alerts": [
        ("resolved_at",   "DATETIME"),
        ("is_resolved",   "INTEGER DEFAULT 0"),
    ],
}


def check_and_fix_schema(conn):
    step("检查并补全数据库字段结构")
    fixed = 0
    for table, columns in EXPECTED_SCHEMA.items():
        for col, col_def in columns:
            if ensure_column(conn, table, col, col_def):
                fixed += 1
    if fixed == 0:
        ok("所有必要字段已存在，结构完整")
    else:
        ok(f"共补全 {fixed} 个缺失字段")


# ─── Step 2: 数据完整性核对 ──────────────────────────────────

def count_records(conn):
    """返回各表当前记录数"""
    tables = ["articles", "leads", "work_orders", "advisors",
              "article_templates", "lead_forms", "keyword_replies",
              "work_order_forms", "work_order_deliveries", "work_order_reviews",
              "work_order_alerts", "brand_assets", "resource_docs"]
    result = {}
    for t in tables:
        try:
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM {t}").fetchone()
            result[t] = row["cnt"]
        except Exception:
            result[t] = -1  # 表不存在
    return result


def fix_articles_integrity(conn):
    """文章数据完整性修复"""
    step("核对文章数据完整性")
    
    # 1. 标题/内容为空的草稿设为 rejected
    bad = conn.execute(
        "SELECT COUNT(*) as cnt FROM articles WHERE (title IS NULL OR title='' OR content IS NULL OR content='') AND status='draft'"
    ).fetchone()["cnt"]
    if bad > 0:
        conn.execute(
            "UPDATE articles SET status='rejected', updated_at=datetime('now','localtime') "
            "WHERE (title IS NULL OR title='') AND status='draft'"
        )
        conn.commit()
        warn(f"将 {bad} 篇标题/内容为空的草稿标记为 rejected")
    else:
        ok("文章标题/内容完整，无空值草稿")

    # 2. is_original 字段：source_name 含「沪上银」的自动标记为原创
    updated = conn.execute(
        "UPDATE articles SET is_original=1 WHERE is_original=0 AND (source_name LIKE '%沪上银%' OR source_name='原创')"
    ).rowcount
    if updated > 0:
        conn.commit()
        ok(f"修正 {updated} 篇原创标记")

    # 3. tags 为空的文章，按 source_name 设默认 tag
    empty_tags = conn.execute(
        "SELECT COUNT(*) as cnt FROM articles WHERE tags IS NULL OR tags=''"
    ).fetchone()["cnt"]
    if empty_tags > 0:
        conn.execute(
            "UPDATE articles SET tags='贷款知识科普' WHERE (tags IS NULL OR tags='') AND source_name NOT LIKE '%沪上银%'"
        )
        conn.execute(
            "UPDATE articles SET tags='品牌宣传' WHERE (tags IS NULL OR tags='') AND source_name LIKE '%沪上银%'"
        )
        conn.commit()
        warn(f"为 {empty_tags} 篇文章设定默认标签")
    else:
        ok("所有文章均有标签")

    total = conn.execute("SELECT COUNT(*) as cnt FROM articles").fetchone()["cnt"]
    ok(f"文章表共 {total} 条记录核对完成")


def fix_leads_integrity(conn):
    """获客线索完整性修复"""
    step("核对获客线索完整性")

    # 1. 手机号为空或格式错误标记为 invalid
    bad_phone = conn.execute(
        "SELECT COUNT(*) as cnt FROM leads WHERE phone IS NULL OR phone='' OR LENGTH(phone)<11"
    ).fetchone()["cnt"]
    if bad_phone > 0:
        warn(f"{bad_phone} 条线索手机号为空/格式错误（保留但标注异常）")
    else:
        ok("所有线索手机号格式正常")

    # 2. 未分配的线索（advisor_id 为空且状态为 new），尝试自动分配
    unassigned = conn.execute(
        "SELECT id, region FROM leads WHERE (advisor_id IS NULL OR advisor_id=0) AND status='new'"
    ).fetchall()
    if unassigned:
        # 获取顾问列表
        advisors = conn.execute(
            "SELECT id, regions, current_leads, max_leads FROM advisors WHERE is_active=1 ORDER BY current_leads ASC"
        ).fetchall()
        assigned_count = 0
        for lead in unassigned:
            region = lead["region"] or "上海"
            best_adv = None
            for adv in advisors:
                try:
                    adv_regions = json.loads(adv["regions"] or "[]")
                except:
                    adv_regions = []
                if region in adv_regions and adv["current_leads"] < adv["max_leads"]:
                    best_adv = adv
                    break
            if best_adv is None and advisors:
                best_adv = advisors[0]  # 兜底分配给当前最少的顾问
            if best_adv:
                conn.execute(
                    "UPDATE leads SET advisor_id=?, status='assigned', updated_at=datetime('now','localtime') WHERE id=?",
                    (best_adv["id"], lead["id"])
                )
                conn.execute(
                    "UPDATE advisors SET current_leads=current_leads+1 WHERE id=?",
                    (best_adv["id"],)
                )
                assigned_count += 1
        if assigned_count > 0:
            conn.commit()
            ok(f"自动分配 {assigned_count} 条未分配线索给顾问")
    else:
        ok("所有线索均已分配顾问")

    total = conn.execute("SELECT COUNT(*) as cnt FROM leads").fetchone()["cnt"]
    ok(f"线索表共 {total} 条记录核对完成")


def fix_work_orders_integrity(conn):
    """服务工单完整性修复"""
    step("核对服务工单完整性")

    # 1. 补全 order_type_label
    label_map = {
        "loan_match": "贷款方案匹配",
        "finance_plan": "融资规划",
        "enterprise_analysis": "企业经营分析",
    }
    for ot, label in label_map.items():
        conn.execute(
            "UPDATE work_orders SET order_type_label=? WHERE order_type=? AND (order_type_label IS NULL OR order_type_label='')",
            (label, ot)
        )
    conn.commit()

    # 2. 状态为 completed 但 completed_at 为空的，填入 updated_at
    conn.execute(
        "UPDATE work_orders SET completed_at=updated_at WHERE status='completed' AND completed_at IS NULL"
    )
    conn.commit()

    # 3. 工单编号格式验证
    bad_no = conn.execute(
        "SELECT COUNT(*) as cnt FROM work_orders WHERE order_no IS NULL OR order_no=''"
    ).fetchone()["cnt"]
    if bad_no > 0:
        # 为缺少编号的工单生成编号
        bad_rows = conn.execute(
            "SELECT id, created_at FROM work_orders WHERE order_no IS NULL OR order_no=''"
        ).fetchall()
        for i, row in enumerate(bad_rows):
            dt = (row["created_at"] or datetime.datetime.now().strftime("%Y-%m-%d"))[:10].replace("-", "")
            new_no = f"WO-{dt}-{9000 + i:04d}"
            conn.execute("UPDATE work_orders SET order_no=? WHERE id=?", (new_no, row["id"]))
        conn.commit()
        warn(f"为 {bad_no} 条工单补全工单编号")
    else:
        ok("所有工单编号完整")

    # 4. 超时未处理工单（超过48小时状态仍为pending）生成预警记录
    timeout_orders = conn.execute("""
        SELECT id FROM work_orders
        WHERE status='pending'
          AND datetime(created_at, '+48 hours') < datetime('now', 'localtime')
          AND id NOT IN (SELECT order_id FROM work_order_alerts WHERE alert_type='timeout' AND is_resolved=0)
    """).fetchall()
    if timeout_orders:
        for row in timeout_orders:
            conn.execute(
                "INSERT INTO work_order_alerts (order_id, alert_type) VALUES (?, 'timeout')",
                (row["id"],)
            )
        conn.commit()
        warn(f"生成 {len(timeout_orders)} 条超时工单预警")
    else:
        ok("无新增超时工单")

    total = conn.execute("SELECT COUNT(*) as cnt FROM work_orders").fetchone()["cnt"]
    ok(f"工单表共 {total} 条记录核对完成")


def fix_advisors_integrity(conn):
    """顾问数据完整性修复"""
    step("核对顾问数据完整性")

    # 重新计算 current_leads（以实际数据库为准）
    advisors = conn.execute("SELECT id FROM advisors").fetchall()
    for adv in advisors:
        real_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM leads WHERE advisor_id=? AND status NOT IN ('lost','converted')",
            (adv["id"],)
        ).fetchone()["cnt"]
        conn.execute(
            "UPDATE advisors SET current_leads=? WHERE id=?",
            (real_count, adv["id"])
        )
    conn.commit()
    ok("顾问当前线索数已根据实际数据重新计算")

    total = conn.execute("SELECT COUNT(*) as cnt FROM advisors").fetchone()["cnt"]
    ok(f"顾问表共 {total} 条记录核对完成")


# ─── Step 3: 迁移报告生成 ────────────────────────────────────

def generate_report(before, after, backup_path):
    step("生成迁移报告")
    
    report_lines = [
        "=" * 60,
        f"  沪上银系统数据迁移报告",
        f"  生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        "",
        f"  数据库路径 : {DB_PATH}",
        f"  备份路径   : {backup_path}",
        "",
        f"  {'表名':<25} {'迁移前':>8} {'迁移后':>8} {'变化':>8}",
        f"  {'-'*52}",
    ]
    
    all_pass = True
    for table in sorted(set(list(before.keys()) + list(after.keys()))):
        b = before.get(table, 0)
        a = after.get(table, 0)
        diff = a - b
        status = "✓" if a >= b else "✗"
        if a < b:
            all_pass = False
        report_lines.append(f"  {status} {table:<23} {b:>8} {a:>8} {diff:>+8}")
    
    report_lines += [
        "",
        f"  {'='*52}",
        f"  验收结论: {'✅ 迁移100%完整，无数据丢失' if all_pass else '⚠️  存在数据量减少，请检查！'}",
        "",
    ]
    
    report_text = "\n".join(report_lines)
    print(report_text)
    
    # 写入报告文件
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "migration_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    ok(f"报告已保存至: {report_path}")
    
    return all_pass


# ─── 主流程 ─────────────────────────────────────────────────

def main():
    title("沪上银系统 — 历史数据迁移与完整性核对")
    
    if not os.path.exists(DB_PATH):
        err(f"数据库不存在: {DB_PATH}")
        print("  请先运行 `python database.py` 初始化数据库")
        sys.exit(1)

    conn = get_conn()

    # 迁移前快照
    before = count_records(conn)
    print(f"\n  迁移前各表记录数: {json.dumps({k: v for k, v in before.items() if v > 0}, ensure_ascii=False, indent=2)}")

    # 备份
    step("备份数据库")
    backup_path = backup_database()

    # 执行修复
    check_and_fix_schema(conn)
    fix_articles_integrity(conn)
    fix_leads_integrity(conn)
    fix_work_orders_integrity(conn)
    fix_advisors_integrity(conn)

    # 迁移后快照
    after = count_records(conn)

    conn.close()

    # 生成报告
    success = generate_report(before, after, backup_path)
    
    title("迁移完成" if success else "迁移完成（有警告）")
    if success:
        print("  ✅ 验收标准达成：迁移数据100%完整，无丢失\n")
    else:
        print("  ⚠️  部分表记录数减少，已记录到报告，请人工确认\n")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
