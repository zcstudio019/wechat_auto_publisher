"""
24小时上线监控脚本 - 沪上银微信公众号自动发布系统
===================================================
功能：
  1. 持续监控系统关键指标（数据库/Web服务/磁盘/异常工单）
  2. 记录异常情况到结构化日志文件
  3. 支持控制台实时输出 + 文件持久化
  4. 单轮检查模式（--once）或持续循环模式（默认每30分钟检查一次）
  5. 按验收标准：无重大异常，系统稳定运行

用法：
  python monitor.py                   # 持续监控（每30分钟一次）
  python monitor.py --once            # 单次检查并输出报告
  python monitor.py --interval 15     # 每15分钟检查一次
  python monitor.py --once --json     # 单次检查，JSON格式输出（便于集成）
"""

import sqlite3
import os
import sys
import io
import json
import datetime
import time
import argparse
import shutil

# Windows UTF-8 输出修复
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from config import DB_PATH, WEB_HOST, WEB_PORT

# ─── 常量 ───────────────────────────────────────────────────
LOG_DIR  = os.path.join(ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "monitor.log")
ALERT_FILE = os.path.join(LOG_DIR, "monitor_alerts.log")

DISK_WARN_GB  = 2.0   # 磁盘可用空间 < 2GB 发出警告
DISK_ERR_GB   = 0.5   # 磁盘可用空间 < 0.5GB 发出严重告警
ORDER_TIMEOUT_HOURS = 48  # 工单超时阈值（小时）
LEADS_DROP_THRESHOLD = 0.5  # 线索量下降超过50%发出预警

# ─── 输出工具 ───────────────────────────────────────────────

def _c(code, msg): return msg  # Windows CMD 不支持ANSI，去掉颜色
def ok(msg):       print(f"  [OK] {msg}")
def warn(msg):     print(f"  [WARN] {msg}")
def err(msg):      print(f"  [ERR] {msg}")
def title(msg):    print(f"\n{'='*60}\n  {msg}\n{'='*60}")
def step(msg):     print(f"\n>> {msg}")
def info(msg):     print(f"  {msg}")


def ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_log(level, message, alert=False):
    """写入日志文件"""
    os.makedirs(LOG_DIR, exist_ok=True)
    line = f"[{ts()}] [{level.upper():5}] {message}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    if alert:
        with open(ALERT_FILE, "a", encoding="utf-8") as f:
            f.write(line)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── 检查项 ─────────────────────────────────────────────────

def check_database_health():
    """数据库健康检查"""
    result = {"name": "数据库健康", "status": "ok", "details": [], "alerts": []}
    
    if not os.path.exists(DB_PATH):
        result["status"] = "critical"
        result["alerts"].append("数据库文件不存在！")
        return result
    
    try:
        conn = get_conn()
        
        # 基础统计
        stats = {}
        for t in ["articles", "leads", "work_orders", "advisors"]:
            stats[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        
        result["details"].append(f"文章:{stats['articles']} 线索:{stats['leads']} 工单:{stats['work_orders']} 顾问:{stats['advisors']}")
        
        # 待审文章
        pending = conn.execute("SELECT COUNT(*) FROM articles WHERE status='draft'").fetchone()[0]
        if pending > 10:
            result["alerts"].append(f"待审文章积压 {pending} 篇，请及时处理")
        else:
            result["details"].append(f"待审文章: {pending} 篇")
        
        # 未处理工单
        pending_orders = conn.execute(
            "SELECT COUNT(*) FROM work_orders WHERE status='pending'"
        ).fetchone()[0]
        if pending_orders > 5:
            result["alerts"].append(f"待处理工单 {pending_orders} 个，请分配跟进")
        else:
            result["details"].append(f"待处理工单: {pending_orders}")
        
        # 超时工单
        timeout_count = conn.execute("""
            SELECT COUNT(*) FROM work_orders
            WHERE status='pending'
              AND datetime(created_at, '+48 hours') < datetime('now', 'localtime')
        """).fetchone()[0]
        if timeout_count > 0:
            result["status"] = "warning"
            result["alerts"].append(f"超时工单 {timeout_count} 个（>48小时未处理）")
        
        conn.close()
        
    except Exception as e:
        result["status"] = "critical"
        result["alerts"].append(f"数据库读取失败: {e}")
    
    return result


def check_web_server():
    """Web服务器可达性检查"""
    result = {"name": "Web服务器", "status": "ok", "details": [], "alerts": []}
    
    try:
        import urllib.request
        import urllib.error
        
        url = f"http://{WEB_HOST}:{WEB_PORT}/"
        req = urllib.request.Request(url, headers={"User-Agent": "monitor/1.0"})
        start = time.time()
        with urllib.request.urlopen(req, timeout=5) as resp:
            elapsed = (time.time() - start) * 1000
            code = resp.getcode()
            result["details"].append(f"HTTP {code} ({elapsed:.0f}ms) → {url}")
            
            if elapsed > 3000:
                result["status"] = "warning"
                result["alerts"].append(f"响应时间过慢: {elapsed:.0f}ms（阈值3000ms）")
    except Exception as e:
        result["status"] = "warning"
        result["alerts"].append(f"Web服务器不可达: {e}")
        result["details"].append("提示: 使用 python web_ui/app.py 启动")
    
    return result


def check_disk_space():
    """磁盘空间检查"""
    result = {"name": "磁盘空间", "status": "ok", "details": [], "alerts": []}
    
    try:
        usage = shutil.disk_usage(ROOT)
        free_gb = usage.free / (1024**3)
        total_gb = usage.total / (1024**3)
        used_pct = (usage.used / usage.total) * 100
        
        result["details"].append(f"可用: {free_gb:.1f}GB / 总计: {total_gb:.1f}GB (已用 {used_pct:.0f}%)")
        
        db_size_mb = os.path.getsize(DB_PATH) / (1024**2) if os.path.exists(DB_PATH) else 0
        result["details"].append(f"数据库文件大小: {db_size_mb:.2f}MB")
        
        if free_gb < DISK_ERR_GB:
            result["status"] = "critical"
            result["alerts"].append(f"磁盘空间严重不足！仅剩 {free_gb:.1f}GB")
        elif free_gb < DISK_WARN_GB:
            result["status"] = "warning"
            result["alerts"].append(f"磁盘空间不足: {free_gb:.1f}GB（建议清理日志/备份）")
    except Exception as e:
        result["status"] = "warning"
        result["alerts"].append(f"磁盘检查失败: {e}")
    
    return result


def check_leads_trend():
    """获客线索趋势检查（防突然下降预警）"""
    result = {"name": "线索趋势", "status": "ok", "details": [], "alerts": []}
    
    try:
        conn = get_conn()
        
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        two_days_ago = today - datetime.timedelta(days=2)
        
        count_today = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE date(created_at)=?",
            (today.isoformat(),)
        ).fetchone()[0]
        
        count_yesterday = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE date(created_at)=?",
            (yesterday.isoformat(),)
        ).fetchone()[0]
        
        count_total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        count_new = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status='new'"
        ).fetchone()[0]
        count_converted = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status='converted'"
        ).fetchone()[0]
        
        result["details"].append(
            f"今日新增: {count_today} | 昨日: {count_yesterday} | 总计: {count_total} | 待跟进: {count_new} | 已转化: {count_converted}"
        )
        
        # 线索下降50%以上预警
        if count_yesterday > 0 and count_today < count_yesterday * (1 - LEADS_DROP_THRESHOLD):
            result["status"] = "warning"
            drop_pct = (1 - count_today / count_yesterday) * 100
            result["alerts"].append(
                f"今日获客线索相比昨日下降 {drop_pct:.0f}% (今日:{count_today} 昨日:{count_yesterday})"
            )
        
        conn.close()
    except Exception as e:
        result["status"] = "warning"
        result["alerts"].append(f"线索趋势检查失败: {e}")
    
    return result


def check_recent_articles():
    """近期文章发布情况"""
    result = {"name": "文章发布情况", "status": "ok", "details": [], "alerts": []}
    
    try:
        conn = get_conn()
        
        last_7d = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        
        published = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE status='published' AND date(published_at)>=?",
            (last_7d,)
        ).fetchone()[0]
        
        approved = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE status='approved'"
        ).fetchone()[0]
        
        draft = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE status='draft'"
        ).fetchone()[0]
        
        result["details"].append(f"近7天已发布: {published} | 已审核待发: {approved} | 草稿: {draft}")
        
        # 7天内没有发布文章的预警
        if published == 0:
            result["status"] = "warning"
            result["alerts"].append("近7天内没有文章发布，请检查发布计划")
        
        conn.close()
    except Exception as e:
        result["status"] = "warning"
        result["alerts"].append(f"文章检查失败: {e}")
    
    return result


def check_log_errors():
    """检查日志文件中的错误"""
    result = {"name": "系统日志", "status": "ok", "details": [], "alerts": []}
    
    error_count = 0
    for log_name in ["flask_err.txt", "flask_out.txt"]:
        log_path = os.path.join(ROOT, log_name)
        if not os.path.exists(log_path):
            continue
        try:
            # 只读最后50行
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                recent = lines[-50:] if len(lines) > 50 else lines
            
            errs = [l.strip() for l in recent if "error" in l.lower() or "traceback" in l.lower() or "exception" in l.lower()]
            if errs:
                error_count += len(errs)
                result["details"].append(f"{log_name}: {len(errs)} 条错误行（最近50行中）")
        except Exception as e:
            result["details"].append(f"{log_name}: 读取失败 ({e})")
    
    if error_count > 5:
        result["status"] = "warning"
        result["alerts"].append(f"系统日志中发现 {error_count} 条错误，请检查 Flask 日志")
    elif error_count > 0:
        result["details"].append(f"日志中有 {error_count} 条错误行（可能为正常INFO级别）")
    else:
        result["details"].append("近期日志无明显错误")
    
    return result


# ─── 汇总输出 ────────────────────────────────────────────────

def run_checks():
    """执行所有检查并返回汇总结果"""
    checks = [
        check_database_health,
        check_web_server,
        check_disk_space,
        check_leads_trend,
        check_recent_articles,
        check_log_errors,
    ]
    
    results = []
    overall_status = "ok"
    
    for check_fn in checks:
        try:
            r = check_fn()
            results.append(r)
            if r["status"] == "critical":
                overall_status = "critical"
            elif r["status"] == "warning" and overall_status == "ok":
                overall_status = "warning"
        except Exception as e:
            results.append({
                "name": check_fn.__name__,
                "status": "error",
                "details": [],
                "alerts": [f"检查脚本异常: {e}"]
            })
            overall_status = "warning"
    
    return results, overall_status


def print_results(results, overall_status):
    """格式化打印检查结果"""
    icon_map = {"ok": "✅", "warning": "⚠️", "critical": "❌", "error": "🔥"}
    
    all_alerts = []
    for r in results:
        icon = icon_map.get(r["status"], "?")
        print(f"\n  {icon} {r['name']}")
        for d in r.get("details", []):
            info(d)
        for a in r.get("alerts", []):
            warn(a)
            all_alerts.append(f"[{r['name']}] {a}")
    
    print(f"\n  {'─'*54}")
    overall_icon = icon_map.get(overall_status, "?")
    
    if overall_status == "ok":
        print(f"  {overall_icon} 整体状态：\033[32m系统正常运行\033[0m")
    elif overall_status == "warning":
        print(f"  {overall_icon} 整体状态：\033[33m存在警告，请关注\033[0m")
    elif overall_status == "critical":
        print(f"  {overall_icon} 整体状态：\033[31m严重异常，需立即处理！\033[0m")
    
    return all_alerts


def log_check_result(results, overall_status, all_alerts):
    """将结果写入日志文件"""
    level = "INFO" if overall_status == "ok" else ("WARN" if overall_status == "warning" else "CRIT")
    write_log(level, f"监控检查完成 | 整体状态: {overall_status} | 告警数: {len(all_alerts)}")
    
    for alert in all_alerts:
        write_log("ALERT", alert, alert=True)


def output_json(results, overall_status):
    """JSON格式输出（便于第三方集成）"""
    output = {
        "timestamp": ts(),
        "overall_status": overall_status,
        "checks": results,
        "alerts": [a for r in results for a in r.get("alerts", [])],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ─── 主流程 ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="沪上银系统24小时监控")
    parser.add_argument("--once",       action="store_true", help="单次检查后退出")
    parser.add_argument("--interval",   type=int, default=30,  help="检查间隔（分钟，默认30）")
    parser.add_argument("--json",       action="store_true", help="JSON格式输出")
    args = parser.parse_args()

    os.makedirs(LOG_DIR, exist_ok=True)

    if args.once:
        # 单次检查模式
        if not args.json:
            title(f"沪上银系统监控快照 — {ts()}")
        
        results, overall_status = run_checks()
        
        if args.json:
            output_json(results, overall_status)
        else:
            all_alerts = print_results(results, overall_status)
            log_check_result(results, overall_status, all_alerts)
            
            print(f"\n  📝 监控日志: {LOG_FILE}")
            if all_alerts:
                print(f"  🚨 告警日志: {ALERT_FILE}")
            
            # 验收标准输出
            print(f"\n  {'─'*54}")
            if overall_status == "ok":
                print(f"  \033[32m验收结论: ✅ 无重大异常，系统稳定运行\033[0m\n")
            else:
                print(f"  \033[33m验收结论: ⚠️  存在 {len(all_alerts)} 条告警，请及时处理\033[0m\n")
        
        return 0 if overall_status in ("ok", "warning") else 1
    
    else:
        # 持续监控模式
        title(f"沪上银系统24小时监控 — 间隔 {args.interval} 分钟")
        write_log("INFO", f"监控服务启动 | 间隔: {args.interval}分钟")
        
        check_count = 0
        try:
            while True:
                check_count += 1
                print(f"\n{'─'*60}")
                print(f"  第 {check_count} 次检查 — {ts()}")
                print(f"{'─'*60}")
                
                results, overall_status = run_checks()
                all_alerts = print_results(results, overall_status)
                log_check_result(results, overall_status, all_alerts)
                
                if all_alerts:
                    print(f"\n  ⚠️  本次发现 {len(all_alerts)} 条告警，已记录到 {ALERT_FILE}")
                
                print(f"\n  ⏰ 下次检查: {(datetime.datetime.now() + datetime.timedelta(minutes=args.interval)).strftime('%H:%M:%S')} (间隔 {args.interval} 分钟)")
                print(f"  按 Ctrl+C 停止监控")
                
                time.sleep(args.interval * 60)
        
        except KeyboardInterrupt:
            write_log("INFO", f"监控服务停止 | 共执行 {check_count} 次检查")
            print(f"\n\n  监控服务已停止（共执行 {check_count} 次检查）")
            print(f"  日志文件: {LOG_FILE}\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
