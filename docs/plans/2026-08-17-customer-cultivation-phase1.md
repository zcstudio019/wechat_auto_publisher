# Customer Cultivation Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在现有公众号后台旁路新增可投入使用的融资客户长期培育 MVP。

**Architecture:** 使用独立 Flask Blueprint、六张前缀表和单一领域 Service 接入现有数据库、顾问、文章库与 APScheduler。所有初始化和扫描异常隔离，不改动文章审核与微信发布主链路。

**Tech Stack:** Python 3、Flask 3、SQLite/MySQL、APScheduler、Jinja2、Bootstrap 5、unittest

---

### Task 1: 培育数据库结构

**Files:**
- Create: `services/cultivation_schema.py`
- Modify: `database.py`
- Test: `tests/test_cultivation_service.py`

1. 编写临时 SQLite 初始化失败测试。
2. 运行测试确认新表尚不存在。
3. 实现六张表、索引、唯一约束及 SQLite/MySQL DDL。
4. 在 `init_db()` 末尾隔离调用培育初始化。
5. 重复初始化两次并验证幂等。

### Task 2: 生命周期、标签、任务与推荐 Service

**Files:**
- Create: `services/cultivation_service.py`
- Test: `tests/test_cultivation_service.py`

1. 编写多贷款、90/60/30/15 天优先级和风险规则测试。
2. 实现客户/贷款 CRUD、实时剩余天数、生命周期和自动标签。
3. 实现风险最高级合并、事件日志和软停用。
4. 实现节点任务唯一幂等、推荐动作和扫描汇总。
5. 实现文章标签维护及规则推荐。
6. 连续扫描两次，验证同贷款同节点只有一项任务。

### Task 3: 培育 Blueprint 和后台页面

**Files:**
- Create: `web_ui/cultivation_routes.py`
- Create: `web_ui/templates/cultivation/*.html`
- Modify: `web_ui/app.py`
- Modify: `web_ui/templates/base.html`
- Test: `tests/test_cultivation_routes.py`

1. 编写登录保护和关键 URL 测试。
2. 注册 `/cultivation` Blueprint，并在模块内隔离业务异常。
3. 实现总览、客户列表/新增/编辑/详情、贷款列表/新增/编辑。
4. 实现今日跟进四个视图、筛选、状态更新和人工跟进记录。
5. 实现客户标签页及文章培育标签编辑页。
6. 在现有业务侧边栏加入一级入口和子菜单。
7. 用 Flask test client 验证完整表单闭环。

### Task 4: APScheduler 接入

**Files:**
- Modify: `scheduler_app.py`
- Test: `tests/test_cultivation_scheduler.py`

1. 编写 job 注册和异常隔离测试。
2. 新增 `job_scan_cultivation_customers()` 包装器。
3. 注册每天 09:00、Asia/Shanghai、单实例、合并执行的 cron job。
4. 验证扫描异常不会传播到 scheduler。

### Task 5: 集成与回归验证

**Files:**
- Modify: `tests/test_cultivation_service.py`
- Modify: `tests/test_cultivation_routes.py`

1. 执行培育模块全部测试。
2. 执行文章 Service、人工微信草稿、发布任务和 Scheduler 回归测试。
3. 编译所有新增 Python 文件。
4. 初始化临时数据库并检查六张表及唯一约束。
5. 启动本地 Web，登录后检查导航、总览、客户详情、跟进和内容页。
6. 汇总逐项验收结果及无法在本地真实调用外部微信 API 的边界。
