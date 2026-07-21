# 贷款行业底层规律文章生成器隔离设计

日期：2026-07-21

## 决策

为 `industry_law` 新增独立的 `LoanIndustryLawArticleGenerator`，写作中心与文章增长中心仅在识别到该类型时分流。其他模板继续使用原有模板 writer 或 `ArticleGenerationAgent`。

专用生成器不使用 JSON mode，AI 只返回 `TITLE/SUMMARY/CONTENT/CTA` 标签文本；标签缺失、结构不完整、空响应、超时或调用异常时，生成器直接返回固定七段式本地文章。

## 原因与取舍

- 独立策略类比继续扩展通用 Agent 风险更低，旧模板不经过新解析逻辑。
- 复用现有文章结果字典和保存服务，不增加数据库表或新任务系统。
- 标签文本比长 JSON 更能容忍正文换行和引号，但结构自由度较低；本类型本身需要固定结构，因此这个限制可接受。
- 本地 fallback 保证生成可用，但 AI 不可用时内容个性化程度会下降，响应通过 `fallback_used` 和日志明确标记。

## 失败边界

正文先落库，封面仅在正文成功后创建后台任务。封面任务创建失败时记录 `cover_status=failed`，正文仍保持 `article_status=generated`，接口继续返回成功。

## 验证

- 专用生成器普通文本解析与无 `response_format` 请求。
- AI 超时、空响应和结构不完整时固定结构 fallback。
- 写作中心 `industry_law` 分流与非行业模板回归。
- 文章增长中心 `industry_law` 分流与通用 Agent 不被调用。
- 封面任务失败不回滚正文。
