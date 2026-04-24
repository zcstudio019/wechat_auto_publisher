# 微信公众号内容自动发布系统

## 功能概述

自动爬取助贷、贷款、银行政策等金融资讯，经过 AI 优化排版后推送为微信公众号草稿，人工审核确认后一键发布。

**工作流程：**
```
爬取多个资讯源 → 关键词过滤 → AI优化标题&排版 → 存入数据库
     ↓
Web管理界面审核 → 通过/拒绝
     ↓
推送到微信草稿箱 → 登录公众号后台确认发布
```

---

## 目录结构

```
wechat_auto_publisher/
├── main.py              # 主程序入口（调度器 + Web启动）
├── config.py            # 全局配置
├── database.py          # SQLite数据库
├── requirements.txt     # 依赖
├── .env.example         # 配置模板
├── start.bat            # 一键启动（Windows）
├── register_task.ps1    # 注册Windows定时任务
├── crawler/
│   ├── base.py          # 爬虫基类
│   ├── crawlers.py      # 各平台爬虫实现
│   └── scheduler.py     # 爬取调度器
├── ai_processor/
│   └── processor.py     # AI内容优化（标题/摘要/排版）
├── wechat_api/
│   ├── client.py        # 微信公众号API封装
│   └── publisher.py     # 草稿发布逻辑
├── web_ui/
│   ├── app.py           # Flask Web管理界面
│   └── templates/       # HTML模板
├── data/                # SQLite数据库文件
└── logs/                # 运行日志
```

---

## 快速开始

### 1. 配置公众号信息

```bash
# 复制配置文件
cp .env.example .env

# 编辑 .env，填入以下信息：
WECHAT_APP_ID=你的AppID
WECHAT_APP_SECRET=你的AppSecret

# 可选：填入 OpenAI API Key 启用 AI 内容优化
OPENAI_API_KEY=sk-xxxx
# 如使用国内模型（如智谱/通义），修改 OPENAI_BASE_URL
```

### 2. 启动程序

**方式一：双击 `start.bat`**（推荐，自动安装依赖）

**方式二：命令行**
```bash
pip install -r requirements.txt
python main.py
```

### 3. 打开管理界面

浏览器访问：http://127.0.0.1:5000
- 默认账号：`admin`
- 默认密码：`admin123`
（在 .env 中修改 WEB_USERNAME / WEB_PASSWORD）

### 4. 注册开机自启（可选）

以管理员身份运行 PowerShell：
```powershell
.\register_task.ps1
```

---

## 使用流程

1. **爬取内容**：程序每天 08:00、14:00 自动爬取，也可在管理界面手动触发
2. **审核文章**：在 Web 界面查看草稿，通过/拒绝/编辑
3. **推送草稿**：点击"推送已审核文章"，将文章推送到微信草稿箱
4. **发布**：登录微信公众号后台 → 草稿箱 → 发布

---

## 内容来源

| 来源 | 类型 | 标签 |
|------|------|------|
| 融360贷款 | 网页 | 助贷、贷款资讯 |
| 第一财经-银行 | 网页 | 银行、金融 |
| 21世纪经济报道-金融 | 网页 | 银行、金融政策 |
| 零壹财经 | 网页 | 金融科技、助贷 |
| 网贷之家 | 网页 | 网贷、贷款 |
| 中国人民银行 | 网页 | 央行政策 |

> 可在 `config.py` 的 `CRAWL_SOURCES` 中添加更多来源

---

## 常见问题

**Q: access_token 获取失败**
- 检查 AppID 和 AppSecret 是否正确
- 确认公众号已开通开发者功能
- 服务器 IP 需加入微信公众号白名单

**Q: 草稿发布失败**
- 订阅号需要认证才能使用群发接口
- 确认 thumb_media_id 有效（封面图已上传）

**Q: 没有 AI 优化**
- 不填 OPENAI_API_KEY 也能正常运行，只是使用基础格式化
- 推荐使用国内模型（智谱GLM、通义千问等），修改 OPENAI_BASE_URL 即可
