"""数据库连接与初始化的最小验证脚本。

用法：
- 本地默认 SQLite：python test_db.py
- 生产 MySQL：先配置 DB_BACKEND=mysql 以及 RDS 连接环境变量，再执行 python test_db.py
"""
from database import fetchone_dict, get_db, init_db, is_mysql


def main():
    """执行一次轻量连接、初始化和查询验证。"""
    init_db()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM articles")
    row = fetchone_dict(cursor)
    conn.close()

    backend = "MySQL/RDS" if is_mysql() else "SQLite"
    print(f"[DB 验证] 当前数据库：{backend}")
    print(f"[DB 验证] articles 表可查询，当前文章数：{row.get('total', 0)}")


if __name__ == "__main__":
    main()
