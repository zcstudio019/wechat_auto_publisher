"""
全局配置模块
"""
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv()

# 微信公众号
WECHAT_APP_ID = os.getenv("WECHAT_APP_ID", "")
WECHAT_APP_SECRET = os.getenv("WECHAT_APP_SECRET", "")
# 公众号正文里的留资入口链接；为空时发布内容会退化为静态引导卡片。
WECHAT_LEAD_FORM_URL = os.getenv("WECHAT_LEAD_FORM_URL", "").strip()

# AI 内容优化
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_IMAGE_API_KEY = os.getenv("OPENAI_IMAGE_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_IMAGE_BASE_URL = os.getenv("OPENAI_IMAGE_BASE_URL", OPENAI_BASE_URL or "https://api.openai.com/v1")
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2").strip() or "gpt-image-2"
USE_AI = bool(OPENAI_API_KEY)

# 发布设置
DAILY_ARTICLE_COUNT = int(os.getenv("DAILY_ARTICLE_COUNT", 3))

# 审核通过后是否立即同步执行发布任务。
# 默认保持立即执行，确保现有对外行为不变。
REVIEW_APPROVE_EXECUTE_IMMEDIATELY = os.getenv("REVIEW_APPROVE_EXECUTE_IMMEDIATELY", "true").lower() in ("1", "true", "yes", "on")

# 定时发布时段（支持多时段，如早8点、晚8点）
# 格式: [(小时, 分钟), ...]
PUBLISH_SCHEDULE = [
    (int(os.getenv("PUBLISH_HOUR_MORNING", 8)), 0),   # 早8点
    (int(os.getenv("PUBLISH_HOUR_EVENING", 20)), 0),  # 晚8点
]

# 兼容旧配置（单时段）
PUBLISH_HOUR = int(os.getenv("PUBLISH_HOUR", 9))
PUBLISH_MINUTE = int(os.getenv("PUBLISH_MINUTE", 0))

# Web 管理
WEB_USERNAME = os.getenv("WEB_USERNAME", "admin")
WEB_PASSWORD = os.getenv("WEB_PASSWORD", "admin123")
WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.getenv("WEB_PORT", "5000"))
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()

# 本地开发时是否开启 Flask 自动热更新。
# 开启后，修改 Python 或模板代码通常只需刷新页面即可看到最新效果。
WEB_AUTO_RELOAD = os.getenv("WEB_AUTO_RELOAD", "true").lower() in ("1", "true", "yes", "on")

# ── 角色账号表 ──────────────────────────────────────────────
# 角色说明:
#   editor  - 内容编辑  : 仅可编辑/提交稿件，不可审核/发布
#   operator - 运营专员  : 可审核文章 + 查看获客数据，不可修改系统设置
#   admin   - 管理员    : 全权限
#
# 格式: {"用户名": {"password": "密码", "role": "角色"}}
USERS = {
    os.getenv("WEB_USERNAME", "admin"): {
        "password": os.getenv("WEB_PASSWORD", "admin123"),
        "role": "admin",
        "display": "管理员",
    },
    os.getenv("EDITOR_USERNAME", "editor"): {
        "password": os.getenv("EDITOR_PASSWORD", "editor123"),
        "role": "editor",
        "display": "内容编辑",
    },
    os.getenv("OPERATOR_USERNAME", "operator"): {
        "password": os.getenv("OPERATOR_PASSWORD", "operator123"),
        "role": "operator",
        "display": "运营专员",
    },
}

# 各角色允许访问的功能
ROLE_PERMISSIONS = {
    "editor": {
        "can_approve": False,        # 不可审核
        "can_publish": False,        # 不可发布
        "can_delete": False,         # 不可删除
        "can_crawl": False,          # 不可触发爬取
        "can_view_leads": False,     # 不可查看获客数据
        "can_view_service": False,   # 不可查看服务数据
        "can_write": True,           # 可以原创写作
        "can_edit": True,            # 可以编辑文章
        "show_nav_publish": False,   # 不显示发布管理菜单
        "show_nav_business": False,  # 不显示业务模块菜单
    },
    "operator": {
        "can_approve": True,
        "can_publish": True,
        "can_delete": False,
        "can_crawl": True,
        "can_view_leads": True,
        "can_view_service": True,
        "can_write": False,
        "can_edit": False,
        "show_nav_publish": True,
        "show_nav_business": True,
    },
    "admin": {
        "can_approve": True,
        "can_publish": True,
        "can_delete": True,
        "can_crawl": True,
        "can_view_leads": True,
        "can_view_service": True,
        "can_write": True,
        "can_edit": True,
        "show_nav_publish": True,
        "show_nav_business": True,
    },
}

# 数据库
DB_BACKEND = os.getenv("DB_BACKEND", "sqlite").strip().lower()
DB_BACKEND = os.getenv("DB_BACKEND", "sqlite").strip().lower()
_DB_PATH_RAW = os.getenv("DB_PATH", os.path.join("data", "articles.db")).strip()
DB_PATH = _DB_PATH_RAW if os.path.isabs(_DB_PATH_RAW) else os.path.join(BASE_DIR, _DB_PATH_RAW)
# SQLite 支持绝对路径；相对路径按项目根目录解析，避免生产启动目录变化导致建错库。
DB_PATH = _DB_PATH_RAW if os.path.isabs(_DB_PATH_RAW) else os.path.join(BASE_DIR, _DB_PATH_RAW)
DB_HOST = os.getenv("DB_HOST", "127.0.0.1").strip()
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "").strip()
DB_USER = os.getenv("DB_USER", "").strip()
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4").strip() or "utf8mb4"

# ============================================================
# 品牌信息（用于文章落款、编辑署名）
# ============================================================
BRAND_NAME = "沪上银"
BRAND_SLOGAN = "上海本地贷款顾问 · 搞不清楚贷款的，来找我们聊聊"
BRAND_ACCOUNT = "沪上银"   # 公众号名称

# ============================================================
# 文章关键词过滤（命中才保留）
# 围绕「沪上银」6大定位设计：
#   1. 贷款获客   2. 品牌宣传   3. 贷款知识科普
#   4. 方案匹配   5. 融资规划   6. 企业经营分析
# ============================================================
KEYWORD_FILTER = [
    # ── 贷款核心词（获客 + 知识科普 + 方案匹配）──
    "贷款", "助贷", "信贷", "房贷", "消费贷", "信用贷",
    "小微贷", "抵押贷", "经营贷", "按揭", "借款", "授信",
    "个人贷款", "企业贷款", "信用评分", "征信",
    # ── 利率与成本（贷款方案匹配核心）──
    "利率", "利息", "LPR", "lpr", "降息", "加息",
    "贷款成本", "月供", "还款", "提前还款", "转贷",
    # ── 融资规划 + 企业经营 ──
    "融资", "股权融资", "债权融资", "供应链融资", "票据",
    "企业融资", "中小企业", "小微企业", "经营贷款", "流动资金",
    "企业经营", "营收", "现金流", "资金周转", "资产负债",
    # ── 银行/机构（品牌宣传背景词）──
    "银行", "存款", "银保监", "银行业", "商业银行",
    "国有银行", "股份制银行", "城商行", "农商行",
    # ── 宏观政策（影响贷款环境）──
    "人民银行", "央行", "货币政策", "金融政策", "普惠金融",
    "金融监管", "降准", "MLF", "逆回购", "公开市场",
    # ── 上海地方（地域定位）──
    "上海", "沪",
    # ── 通用财经（放宽抓取量）──
    "金融", "经济", "政策",
]

