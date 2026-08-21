# 融资客户培育 Phase 1.1：公众号关注建档入口

## 现状定位

- 微信出站能力位于 `wechat_api/` 与发布 Service，只负责草稿和发布，不接收公众号事件。
- `web_ui/app.py` 现有 `/api/keyword-reply` 仅返回关键词 JSON，不能处理微信签名、XML 或关注事件。
- 项目没有 `subscribe`、`unsubscribe`、粉丝 `openid` 持久化或微信服务器回调路由。
- 培育后台由 `/cultivation` Blueprint 统一登录保护，公开登记不能直接放入该 Blueprint。
- 现有 `CustomerCultivationService` 已提供客户、贷款、生命周期、风险标签和跟进任务能力，应直接复用。

## 低侵入设计

1. 新增独立微信入站 Blueprint，提供 `/wechat/callback`：
   - GET 校验微信签名并返回 `echostr`；
   - POST 校验签名并解析标准 XML；
   - 处理 `subscribe`、`unsubscribe`、文本“建档”“咨询”；
   - 其他文本复用现有 `keyword_replies`，无匹配返回 `success`；
   - 单条消息异常降级，不传播到文章草稿、发布或其他后台路由。
2. 新增公开登记 Blueprint，提供 `/public/cultivation/register`：
   - 不要求后台登录；
   - 只凭限时随机 token 访问登记能力；
   - 页面手机单列、无外部资源、禁止缓存和搜索索引。
3. 新增 `cultivation_wechat_users`：
   - `openid` 唯一；
   - URL 使用 256 位随机 token，数据库只保存 SHA-256 摘要；
   - token 默认 24 小时过期，退订时立即失效；
   - 保存 `customer_id` 与公众号简化贷款 `registration_loan_id`。
4. 登记提交：
   - 首选已绑定 `customer_id`；否则按“企业名 + 手机号”弱去重；
   - 创建或更新 `cultivation_customers`，来源保存为 `wechat_official_account`；
   - 有贷款时创建或更新同一笔“公众号登记贷款”，无贷款时不新建；
   - 调用现有培育 Service 刷新生命周期、标签、风险与到期任务；
   - 记录 `register_completed` 事件。
5. 展示层把 `wechat_official_account` 映射为“微信公众号”，不回显技术枚举。

## 配置与迁移

- 新增 `WECHAT_CALLBACK_TOKEN`：微信后台服务器配置使用的校验 Token。
- 新增 `CULTIVATION_REGISTER_URL`：生产登记页 HTTPS 地址，默认同现有公众号留资域名。
- 新表同时提供 SQLite/MySQL 建表语句，并纳入现有幂等 `init_cultivation_tables()`。
- 不修改微信 AppSecret、access_token、文章审核、草稿或发布代码。

## 测试

- 微信签名验证、subscribe 欢迎链接、无效签名、建档/咨询关键词。
- 有效/无效/过期 token 的公开页面。
- 客户创建、微信关联、重复提交更新、企业+手机号弱去重。
- 简化贷款创建与重复更新、无贷款分支。
- 高信用卡使用率和高查询次数触发现有风险规则。
- unsubscribe 保留客户、重新 subscribe 显示更新文案。
- 原培育测试、文章服务/发布关键测试和页面浏览器回归。

## 风险与上线条件

- 生产环境必须配置 `WECHAT_CALLBACK_TOKEN` 和可公网访问的 HTTPS `CULTIVATION_REGISTER_URL`。
- 微信公众平台需把服务器 URL 指向 `/wechat/callback`；这是部署后的外部配置，不由本地代码自动修改。
- 真实关注联调需要一个测试微信号与生产公众号后台配置；本地自动化只能验证协议、页面和数据库闭环。
