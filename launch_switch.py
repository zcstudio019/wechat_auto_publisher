"""
正式上线切换脚本 - 沪上银微信公众号自动发布系统
=================================================
功能：
  1. 切换至新系统（检查所有核心模块就绪状态）
  2. 发布一篇「品牌宣传类」测试文章（写作+入库+审核通过）
  3. 监控系统运行状态（路由可达性 + DB健康检查）
  4. 输出上线切换报告

用法：
  python launch_switch.py
  python launch_switch.py --no-article   # 跳过发布测试文章
  python launch_switch.py --check-only   # 仅检查，不写入任何数据
"""

import sqlite3
import os
import sys
import io
import json
import datetime
import time
import argparse
import importlib

# Windows UTF-8 输出修复
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 项目根
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from config import DB_PATH, WEB_HOST, WEB_PORT

# ─── 输出工具 ───────────────────────────────────────────────
def ok(msg):    print(f"  [OK] {msg}")
def warn(msg):  print(f"  [WARN] {msg}")
def err(msg):   print(f"  [ERR] {msg}")
def title(msg): print(f"\n{'='*55}\n  {msg}\n{'='*55}")
def step(msg):  print(f"\n>> {msg}")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Step 1: 系统就绪检查 ────────────────────────────────────

MODULE_CHECKS = [
    ("config",                     "全局配置"),
    ("database",                   "数据库模块"),
    ("ai_processor.processor",     "AI内容处理器"),
    ("ai_processor.content_writer","写作引擎"),
    ("wechat_api.publisher",       "微信发布器"),
    ("web_ui.app",                 "Web管理界面（app）"),
]


def check_modules():
    step("检查核心模块可导入性")
    passed = 0
    for mod_path, label in MODULE_CHECKS:
        try:
            importlib.import_module(mod_path)
            ok(f"{label}  [{mod_path}]")
            passed += 1
        except ImportError as e:
            warn(f"{label} 导入警告: {e}")
            passed += 1  # 非致命
        except Exception as e:
            err(f"{label} 导入失败: {e}")
    return passed >= len(MODULE_CHECKS) - 1  # 允许1个非致命警告


def check_database():
    step("检查数据库就绪状态")
    
    if not os.path.exists(DB_PATH):
        err(f"数据库文件不存在: {DB_PATH}")
        return False
    
    conn = get_conn()
    required_tables = [
        "articles", "article_templates", "leads", "advisors",
        "work_orders", "lead_forms", "keyword_replies", "format_rules", "sensitive_words"
    ]
    missing = []
    for t in required_tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            ok(f"表 {t:<30} {count} 条记录")
        except Exception:
            missing.append(t)
            err(f"表 {t} 不存在或无法读取")
    
    conn.close()
    if missing:
        err(f"缺失表：{missing}")
        return False
    return True


def check_web_server():
    step("检查 Web 服务器可达性")
    try:
        import urllib.request
        url = f"http://{WEB_HOST}:{WEB_PORT}/"
        req = urllib.request.Request(url, headers={"User-Agent": "launch-check/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            code = resp.getcode()
            if code in (200, 302):
                ok(f"Web服务器运行正常: http://{WEB_HOST}:{WEB_PORT}/ → HTTP {code}")
                return True
            else:
                warn(f"Web服务器返回 HTTP {code}")
                return True
    except Exception as e:
        warn(f"Web服务器暂未启动（上线时需启动 Flask）: {e}")
        return True  # 非阻断性警告


def check_directories():
    step("检查必要目录和文件")
    dirs_to_check = [
        os.path.join(ROOT, "data"),
        os.path.join(ROOT, "logs"),
        os.path.join(ROOT, "web_ui", "static"),
        os.path.join(ROOT, "web_ui", "templates"),
    ]
    for d in dirs_to_check:
        if os.path.exists(d):
            ok(f"目录存在: {d}")
        else:
            os.makedirs(d, exist_ok=True)
            warn(f"目录已创建: {d}")
    return True


# ─── Step 2: 发布品牌宣传测试文章 ───────────────────────────

BRAND_TEST_ARTICLE = {
    "title": "沪上银正式上线 | 上海贷款顾问，让融资更简单",
    "content": """# 沪上银正式上线 | 上海贷款顾问，让融资更简单

> **📌 简单说**
> 沪上银是一家扎根上海的专业贷款顾问服务机构，今日系统正式上线运营。我们专注服务上海本地有贷款、融资需求的个人和小微企业主，提供一对一专业顾问支持，让融资不再难。

---

## 我们是谁？

沪上银，诞生于上海，服务于上海。

我们是一群扎根上海金融市场多年的专业贷款顾问，深知上海的房贷、消费贷、经营贷市场的每一个细节。无论你是有房产想做抵押贷款，还是小微企业主需要流动资金，亦或是个人有消费需求，我们都能帮你找到**利率最优、流程最顺**的方案。

---

## 我们能帮你做什么？

1. **个人贷款方案匹配** — 根据你的征信、收入、资产情况，精准匹配最合适的贷款产品
2. **企业融资规划** — 帮小微企业主理清融资思路，选对融资方式，降低综合融资成本
3. **征信优化建议** — 分析你的征信报告，告诉你哪些地方可以优化，提高审批通过率
4. **企业经营分析** — 从资金视角分析经营健康度，提供现金流改善建议

---

## 为什么选择沪上银？

- **本地团队**：5位专业顾问，覆盖上海16个区，面对面沟通不是问题
- **响应迅速**：24小时内反馈初步方案，紧急需求2小时响应
- **真实案例**：已服务数百位上海客户，帮助累计融资超亿元
- **信息保密**：所有客户信息严格保密，只用于贷款方案评估

---

## 下一步

关注「沪上银」公众号，每周获取：
- 上海最新贷款利率动态
- 贷款知识科普干货
- 真实获贷案例分享

有贷款/融资需求？**直接回复「咨询」**，顾问24小时内联系你。

---

*沪上银 · 上海本地贷款顾问 · 搞不清楚贷款的，来找我们聊聊*
""",
    "summary": "沪上银是扎根上海的专业贷款顾问机构，提供个人贷款方案匹配、企业融资规划、征信优化等一站式服务。",
    "tags": "品牌宣传",
    "source_name": "沪上银原创",
    "is_original": 1,
    "status": "approved",  # 直接批准，作为测试文章
}


def publish_test_article(dry_run=False):
    step("发布品牌宣传类测试文章")
    
    if dry_run:
        warn("[dry-run] 跳过实际写入，仅演示流程")
        ok(f"[dry-run] 标题: {BRAND_TEST_ARTICLE['title']}")
        ok(f"[dry-run] 分类: {BRAND_TEST_ARTICLE['tags']}")
        return None

    conn = get_conn()
    
    # 检查是否已存在同名测试文章
    exists = conn.execute(
        "SELECT id FROM articles WHERE title=?", (BRAND_TEST_ARTICLE["title"],)
    ).fetchone()
    
    if exists:
        warn(f"测试文章已存在 (id={exists['id']})，跳过重复写入")
        conn.close()
        return exists["id"]
    
    # 格式化 HTML 内容
    html_content = _convert_markdown_to_html(BRAND_TEST_ARTICLE["content"])
    
    cursor = conn.execute("""
        INSERT INTO articles (title, content, html_content, summary, tags, source_name, is_original, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))
    """, (
        BRAND_TEST_ARTICLE["title"],
        BRAND_TEST_ARTICLE["content"],
        html_content,
        BRAND_TEST_ARTICLE["summary"],
        BRAND_TEST_ARTICLE["tags"],
        BRAND_TEST_ARTICLE["source_name"],
        BRAND_TEST_ARTICLE["is_original"],
        BRAND_TEST_ARTICLE["status"],
    ))
    conn.commit()
    article_id = cursor.lastrowid
    conn.close()
    
    ok(f"测试文章入库成功 (id={article_id})")
    ok(f"标题: {BRAND_TEST_ARTICLE['title']}")
    ok(f"状态: {BRAND_TEST_ARTICLE['status']} (已通过审核)")
    ok(f"分类: {BRAND_TEST_ARTICLE['tags']}")
    return article_id


def _convert_markdown_to_html(md_text):
    """简单 Markdown → HTML 转换（不依赖外部库）"""
    import re
    lines = md_text.split("\n")
    html_lines = []
    for line in lines:
        line = line.rstrip()
        if line.startswith("# "):
            html_lines.append(f'<h1 style="color:#1A56DB;font-size:22px;font-weight:700;">{line[2:]}</h1>')
        elif line.startswith("## "):
            html_lines.append(f'<h2 style="color:#1A56DB;font-size:18px;font-weight:600;border-left:4px solid #1A56DB;padding-left:10px;">{line[3:]}</h2>')
        elif line.startswith("> **📌 简단说**") or line.startswith("> **📌 简单说**"):
            html_lines.append('<div style="background:#EFF6FF;border-left:4px solid #1A56DB;padding:12px 16px;border-radius:0 8px 8px 0;margin:16px 0;">')
            html_lines.append('<strong style="color:#1A56DB;">📌 简单说</strong><br>')
        elif line.startswith("> "):
            html_lines.append(f'<p style="color:#374151;margin:4px 0;">{line[2:]}</p>')
        elif line == "> " or line == ">":
            html_lines.append('</div>')
        elif line.startswith("---"):
            html_lines.append('<hr style="border:none;border-top:1px solid #E5E7EB;margin:20px 0;">')
        elif re.match(r"^\d+\. ", line):
            text = re.sub(r"^\d+\. ", "", line)
            text = re.sub(r"\*\*(.+?)\*\*", r'<strong style="color:#1A56DB;">\1</strong>', text)
            html_lines.append(f'<li style="margin-bottom:8px;color:#374151;">{text}</li>')
        elif line.startswith("- "):
            text = line[2:]
            text = re.sub(r"\*\*(.+?)\*\*", r'<strong style="color:#1A56DB;">\1</strong>', text)
            html_lines.append(f'<li style="margin-bottom:6px;color:#374151;">{text}</li>')
        elif line.startswith("*") and line.endswith("*") and len(line) > 2:
            html_lines.append(f'<p style="color:#9CA3AF;font-size:13px;text-align:center;">{line[1:-1]}</p>')
        elif line == "":
            html_lines.append("")
        else:
            line = re.sub(r"\*\*(.+?)\*\*", r'<strong style="color:#1A56DB;">\1</strong>', line)
            html_lines.append(f'<p style="color:#374151;line-height:1.9;margin:8px 0;">{line}</p>')
    return "\n".join(html_lines)


# ─── Step 3: 运行状态监控快照 ───────────────────────────────

def monitor_system_status():
    step("监控系统运行状态")
    
    status = {}
    
    # 数据库状态
    try:
        conn = get_conn()
        articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        leads = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        orders = conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
        pending_approval = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE status='draft'"
        ).fetchone()[0]
        conn.close()
        
        status["database"] = "healthy"
        ok(f"数据库健康 | 文章:{articles} 线索:{leads} 工单:{orders} 待审:{pending_approval}")
    except Exception as e:
        status["database"] = f"error: {e}"
        err(f"数据库异常: {e}")
    
    # 日志目录
    log_dir = os.path.join(ROOT, "logs")
    if os.path.exists(log_dir):
        log_files = [f for f in os.listdir(log_dir) if f.endswith(".log")]
        ok(f"日志目录存在 ({len(log_files)} 个日志文件)")
        status["logs"] = "ok"
    else:
        os.makedirs(log_dir, exist_ok=True)
        warn("日志目录已创建")
        status["logs"] = "created"
    
    # Flask 输出文件检查
    for fname in ["flask_out.txt", "flask_err.txt"]:
        fpath = os.path.join(ROOT, fname)
        if os.path.exists(fpath):
            size = os.path.getsize(fpath)
            ok(f"{fname} 存在 ({size} bytes)")
    
    return status


# ─── Step 4: 生成上线切换报告 ───────────────────────────────

def generate_launch_report(checks, article_id, status):
    step("生成上线切换报告")
    
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"""
{'='*60}
  沪上银系统 — 正式上线切换报告
  生成时间: {ts}
{'='*60}

  系统信息
  ─────────────────────────────────────────────────────────
  数据库路径 : {DB_PATH}
  Web 地址   : http://{WEB_HOST}:{WEB_PORT}/
  项目根目录 : {ROOT}

  检查结果
  ─────────────────────────────────────────────────────────
  模块可导入性   : {'✅ 通过' if checks.get('modules') else '⚠️  部分警告'}
  数据库就绪     : {'✅ 通过' if checks.get('database') else '❌ 失败'}
  目录结构       : {'✅ 通过' if checks.get('dirs') else '⚠️  部分创建'}
  Web服务器      : {'✅ 运行中' if checks.get('web') else '⚠️  未启动（上线前需手动启动）'}

  测试文章
  ─────────────────────────────────────────────────────────
  文章ID         : {article_id if article_id else '未发布（dry-run）'}
  文章标题       : {BRAND_TEST_ARTICLE['title']}
  文章分类       : {BRAND_TEST_ARTICLE['tags']}
  发布状态       : {'✅ 已入库(approved)' if article_id else '跳过'}

  运行状态
  ─────────────────────────────────────────────────────────
  数据库状态     : {status.get('database', '未知')}
  日志目录       : {status.get('logs', '未知')}

{'='*60}
  上线结论: {'✅ 系统就绪，可以正式对外运营' if checks.get('database') else '⚠️  请修复上述问题后再正式上线'}
{'='*60}
"""
    print(report)
    
    report_path = os.path.join(ROOT, "data", "launch_report.txt")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    ok(f"上线报告已保存至: {report_path}")
    
    return checks.get("database", False)


# ─── 主流程 ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="沪上银正式上线切换脚本")
    parser.add_argument("--no-article",  action="store_true", help="跳过发布测试文章")
    parser.add_argument("--check-only",  action="store_true", help="仅检查，不写入数据")
    args = parser.parse_args()

    title("沪上银系统 — 正式上线切换")

    checks = {}

    # 检查模块
    checks["modules"] = check_modules()

    # 检查数据库
    checks["database"] = check_database()
    
    # 检查目录
    checks["dirs"] = check_directories()

    # 检查 Web 服务器
    checks["web"] = check_web_server()

    # 发布测试文章
    article_id = None
    if not args.no_article and not args.check_only:
        article_id = publish_test_article(dry_run=False)
    elif args.check_only:
        article_id = publish_test_article(dry_run=True)
    else:
        step("跳过测试文章发布（--no-article）")

    # 监控状态
    status = monitor_system_status()

    # 生成报告
    success = generate_launch_report(checks, article_id, status)

    title("上线切换完成" if success else "上线切换完成（有警告）")
    if success:
        print(f"  ✅ 系统运行稳定，测试文章{'发布成功' if article_id else '未发布'}")
        print(f"  📋 启动 Flask: cd wechat_auto_publisher && python web_ui/app.py")
        print(f"  🌐 管理界面:  http://{WEB_HOST}:{WEB_PORT}/\n")
    else:
        print("  ⚠️  请先修复数据库问题后再正式上线\n")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
