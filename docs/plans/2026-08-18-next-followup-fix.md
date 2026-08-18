# 下次跟进完整链路修复 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** 确保 `datetime-local` 提交值被规范保存、可见展示，并以幂等的未来人工任务重新进入今日/逾期/未来7天列表。

**Architecture:** 保留原跟进任务作为本次联系历史；设置下次跟进时，在同一事务中按原任务 ID 幂等创建或更新一条 `人工后续跟进` 待处理任务。沿用现有 `cultivation_followups` 表和 `due_date` 分页逻辑，不新增数据库服务或修改文章链路。

**Tech Stack:** Flask、Jinja2、SQLite/MySQL 兼容 SQL、unittest、APScheduler。

---

### Task 1: 固化问题与预期行为

**Files:**
- Modify: `tests/test_cultivation_service.py`
- Modify: `tests/test_cultivation_routes.py`

1. 增加 `2026-08-20T10:30` 解析及数据库规范值测试。
2. 增加空值保存为 `NULL` 的测试。
3. 增加未来任务生成、到期进入今日/逾期以及重复保存不重复的测试。
4. 增加今日跟进和客户详情展示测试。

### Task 2: 修复服务层保存与重排

**Files:**
- Modify: `services/cultivation_service.py`

1. 新增统一的可空 ISO 本地时间解析方法。
2. `record_followup` 和 `update_followup` 保存规范化后的 DATETIME。
3. 设置下次跟进时，按 `manual_followup:<source_followup_id>` 幂等创建/更新未来待处理任务。
4. 保留原任务的本次联系状态和历史，不将“已联系”等同于永不再跟进。

### Task 3: 修复路由反馈与页面展示

**Files:**
- Modify: `web_ui/cultivation_routes.py`
- Modify: `web_ui/templates/cultivation/followups.html`
- Modify: `web_ui/templates/cultivation/customer_detail.html`

1. 查询结果统一生成 `YYYY-MM-DD HH:MM` 展示值，空值为破折号。
2. 今日跟进任务行显示下次跟进。
3. 客户详情历史显示规范化后的下次跟进。
4. 保存后 Flash 明确反馈已保存的下次跟进时间。

### Task 4: 回归验证

1. 运行培育路由、服务、Scheduler 测试。
2. 运行文章服务和微信人工发布流程回归。
3. 执行 Python 编译和 `git diff --check`。
4. 浏览器验证今日跟进与客户详情页面。
