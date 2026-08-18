# 融资客户培育中心 Phase 1 设计

## 现状审计

项目是 Flask 单体后台，`web_ui/app.py` 承载现有路由，`database.py` 提供 SQLite/MySQL 双后端兼容和幂等初始化，生产环境由 `run_web.py` 与 `run_scheduler.py` 分别托管 Web 和 APScheduler。文章主表为 `articles`，审核、微信草稿推送分别由现有 Review/Publish Service 和 `wechat_api` 完成。现有 `leads` 是一次性获客表，无法安全表达企业、多笔贷款、生命周期和长期跟进；`advisors` 可直接作为负责人表复用。后台 UI 使用 `base.html` 的 Bootstrap 5 侧边栏、卡片、Badge、表格和表单。

## 方案选择

采用旁路 Blueprint：新增独立 `cultivation_` 数据表、业务 Service、路由模块和模板，只在数据库统一初始化、Flask Blueprint 注册、侧边栏和 Scheduler 注册点做小改动。文章不增加字段，使用 `article_cultivation_tags` 关联现有 `articles.id`。相比复用 `leads`，此方案不会改变既有获客状态语义；相比继续向 `web_ui/app.py` 堆叠路由，独立 Blueprint 更容易隔离异常和整体回滚。

## 数据与业务流

客户保存后执行状态重算；贷款保存后重算最近未结清贷款、生命周期、自动标签、风险等级，并按 90/60/30/15 天节点幂等生成任务。每日 09:00 扫描执行相同流程。`cultivation_followups` 同时保存自动任务和人工跟进记录；自动任务以 `(customer_id, loan_id, trigger_type)` 唯一约束防重。剩余天数只通过 `expire_date - today` 实时计算，不持久化。自动标签更新时只替换 `source=system` 的记录，保留人工标签。

推荐从 `article_cultivation_tags` 聚合标签，按生命周期、风险标签、行业、通用内容逐级计分，返回最高匹配文章并写入跟进任务。正文、审核、草稿、发布仍完全沿用现有文章链路。

## 权限、异常与兼容

页面沿用现有登录会话和 `show_nav_business/can_view_leads/can_edit` 权限。当前账号配置与 `advisors` 没有稳定映射，因此 Phase 1 不强行引入顾问行级权限；负责人筛选和归属字段完整保留。新表同时提供 SQLite/MySQL DDL，全部 `CREATE TABLE IF NOT EXISTS`，不删除或改写原表。培育表初始化和 Scheduler job 均使用独立 try/except，失败只记录日志，不阻断 Web、文章或其他定时任务。

## 测试策略

使用临时 SQLite 数据库覆盖客户、多贷款最近到期、生命周期优先级、风险标签、15/30 天任务、重复扫描、文章推荐和跟进完成。使用 Flask test client 验证登录保护、页面和表单主流程；运行现有文章、审核、发布与 Scheduler 相关测试作回归。UI 启动本地服务后实际访问关键页面并检查导航与中文展示。
