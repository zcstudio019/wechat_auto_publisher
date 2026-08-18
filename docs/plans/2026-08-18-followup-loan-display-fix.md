# 今日跟进贷款信息修复 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 今日跟进优先显示任务明确关联的贷款，并在 `loan_id` 为空时统一回退到客户最近到期的未结清贷款。

**Architecture:** 在培育 Service 中集中实现“明确贷款优先、最近未结清贷款兜底”的解析方法，客户档案与跟进列表共同复用。人工任务创建及人工后续任务生成时尽量持久化解析出的贷款 ID；页面仍保留查询时兜底，以兼容历史空数据。

**Tech Stack:** Flask、Jinja2、SQLite/MySQL 兼容查询、unittest。

---

### Task 1: 增加失败测试

**Files:**
- Modify: `tests/test_cultivation_service.py`
- Modify: `tests/test_cultivation_routes.py`

1. 验证生命周期任务绑定具体贷款。
2. 验证人工后续任务继承原任务贷款。
3. 验证空 `loan_id` 回退到最近未结清贷款。
4. 验证多笔贷款选择最近到期的一笔。
5. 验证无贷款及仅已结清贷款不显示伪造的零金额和空天数。

### Task 2: 集中贷款选择规则

**Files:**
- Modify: `services/cultivation_service.py`
- Modify: `web_ui/cultivation_routes.py`

1. 新增跟进任务展示贷款解析方法。
2. 有效 `loan_id` 优先返回对应贷款。
3. 空或失效 `loan_id` 调用现有 `get_nearest_open_loan()`。
4. 人工任务和人工后续任务写入解析出的贷款 ID。
5. 客户列表最近贷款继续复用同一未结清规则。

### Task 3: 修复模板空值语义

**Files:**
- Modify: `web_ui/templates/cultivation/followups.html`

1. 展示银行、产品、真实贷款金额和到期日。
2. 剩余天数按到期日实时计算。
3. 无贷款显示“暂无贷款 / — / —”。
4. 真实金额为零时才显示 `0.00万`。

### Task 4: 回归和页面验收

1. 运行培育服务、路由和 Scheduler 测试。
2. 运行文章服务及微信人工发布流程回归。
3. 浏览器检查明确贷款、空贷款兜底及无贷款展示。
