# Phase 1.4 融资档案双模式设计

## 目标与边界

在现有融资客户培育系统中增加企业与个人两种融资主体类型，同时继续使用同一套 `cultivation_customers` 客户主表、`cultivation_loans` 贷款表、微信用户绑定、提醒、跟进、事件和文章培育链路。本阶段不新增贷款分类，不重写风险评分模型，也不拆分个人资料子表。

## 方案选择

采用直接扩展 `cultivation_customers` 的方案。新增稳定枚举 `profile_type`，仅允许 `company` 和 `individual`，默认 `company`；新增个人 MVP 字段 `city`、`occupation_type`、`monthly_income_range`、`has_social_security`、`has_housing_fund`、`has_property`、`has_credit_card`、`credit_query_level`。已有通用字段继续复用：`legal_person` 作为联系人/姓名，`phone` 作为联系电话，`has_online_loans` 作为网贷状态，`financing_need` 作为当前融资需求。

不采用独立 `cultivation_customer_profiles` 表，因为当前客户表规模可控，拆表会扩大查询、迁移和事务范围，不能为本阶段带来直接业务收益。`company_name` 在新建表定义中改为可空；对已存在的 SQLite 表，通过幂等重建迁移去掉 `NOT NULL`，MySQL 通过幂等 `MODIFY` 调整。所有旧行补齐为 `company`。

## 数据流与校验

公众号登记和后台新增/编辑都提交 `profile_type`。企业模式要求企业名称、联系人、电话、行业和营收区间；个人模式要求姓名、电话、职业类型和月收入区间，企业字段不参与校验。切换类型时只更新 `profile_type` 与当前可见字段，另一模式的历史字段不清空。

统一展示名由服务层生成：企业取 `company_name`，个人取 `legal_person`。所有客户列表、重点客户、详情、贷款、跟进和标签页面使用装饰后的 `display_name`，并把主体类型映射为中文，避免出现空企业名或内部英文枚举。

公众号更新页从 `customer.profile_type` 恢复模式。新客户弱去重键按类型区分：企业使用企业名称和手机号，个人使用姓名和手机号。更新贷款时仍按贷款 ID 原位更新，新贷款继续插入，未提交的历史贷款不会被删除。

## 兼容、错误处理与测试

迁移必须可重复执行：新建库直接得到完整结构；旧库先加列、回填 `profile_type='company'`，再放宽企业名称约束。无效 `profile_type` 不写库，用户只看到中文校验信息。现有调用未传类型时按企业处理，因此旧测试和旧后台调用保持原行为。

测试覆盖企业/个人首次登记、条件必填、双模式多贷款、更新不覆盖贷款、统一展示、类型筛选、个人贷款提醒、旧客户默认值、中文状态与 Scheduler/微信提醒回归。UI 通过 Flask 测试客户端验证服务端渲染，并在本地运行页面做一次交互与视觉检查。
