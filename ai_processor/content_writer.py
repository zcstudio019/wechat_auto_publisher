"""
原创文章生成器：
1. 基于写作模板，用 AI 生成有观点的原创公众号文章
2. 不依赖 AI 时，走结构化模板生成

适用场景：
- 根据话题触发创作（6大类写作模板）
"""
import re
import json
import logging
import time
import random
from datetime import datetime

from config import USE_AI, OPENAI_API_KEY, OPENAI_BASE_URL

logger = logging.getLogger(__name__)


TITLE_MAX_LEN = 22
TITLE_FILLER_WORDS = [
    "专业", "优质", "快速", "高效", "最新", "全面", "深度", "一站式",
    "推荐", "平台", "服务", "解析说明", "案例分享解析说明", "案例分享",
    "方案服务", "服务推荐平台", "全解析", "详解",
]
TITLE_BUSINESS_KEYWORDS = [
    "企业贷", "经营贷", "融资", "银行贷款", "企业资金周转", "上海贷款",
    "征信", "批款", "放款", "利率", "贷款", "额度", "小微企业",
]
TITLE_NATURAL_MARKERS = [
    "为什么", "为何", "如何", "怎么", "别", "先", "被拒", "拿到",
    "成功", "放款", "踩", "坑", "？", "吗", "这", "他", "她", "一家",
]

if USE_AI:
    try:
        from openai import OpenAI
        _client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    except Exception as e:
        logger.warning(f"[Writer] OpenAI初始化失败: {e}")
        _client = None
else:
    _client = None


# ══════════════════════════════════════════════════════════════
# 核心函数：基于模板 + AI 生成文章
# ══════════════════════════════════════════════════════════════

def write_with_template(topic: str, template: dict) -> dict:
    """
    根据话题 + 写作模板生成一篇文章。
    template 是 article_templates 表的一行 dict，包含：
      name, category, structure(JSON), pain_point, solution, hook,
      brand_rules(JSON), prompt_template
    返回 dict: {title, content, source_name, source_url, tags}
    """
    if not topic or not template:
        return {}

    # 解析模板字段
    structure_str = template.get("structure", "[]")
    try:
        structure_list = json.loads(structure_str)
        if isinstance(structure_list, str):
            structure_list = json.loads(structure_list)
    except (json.JSONDecodeError, TypeError):
        structure_list = []
    if not isinstance(structure_list, list):
        structure_list = []

    # 替换 {topic} 占位符
    structure_list = [s.replace("{topic}", topic) for s in structure_list]

    pain_point = template.get("pain_point", "")
    solution = template.get("solution", "")
    hook = template.get("hook", "")
    brand_rules_str = template.get("brand_rules", "{}")
    try:
        brand_rules = json.loads(brand_rules_str) if isinstance(brand_rules_str, str) else brand_rules_str
    except (json.JSONDecodeError, TypeError):
        brand_rules = {}

    prompt_template = template.get("prompt_template", "")
    category = template.get("category", "leads")
    tmpl_name = template.get("name", "")

    # 先尝试 AI 生成
    if _client:
        article = _ai_write_with_template(
            topic=topic,
            structure_list=structure_list,
            pain_point=pain_point,
            solution=solution,
            hook=hook,
            brand_rules=brand_rules,
            prompt_template=prompt_template,
            category=category,
            tmpl_name=tmpl_name,
        )
        if article:
            return article

    # AI 失败时走结构化兜底
    logger.info(f"[Writer] AI不可用，走结构化模板生成: {topic}")
    return _template_write_structured(
        topic=topic,
        structure_list=structure_list,
        pain_point=pain_point,
        solution=solution,
        hook=hook,
        brand_rules=brand_rules,
        category=category,
    )


def optimize_wechat_title(title: str) -> str:
    """优化模板生成标题，使其更适合微信公众号草稿箱和移动端点击阅读。"""
    cleaned = _clean_title_text(title)
    if not cleaned:
        return "企业贷款怎么选？"

    if _looks_like_keyword_stacking(cleaned):
        cleaned = _rewrite_stacked_title(cleaned)

    cleaned = _remove_title_fillers(cleaned)
    cleaned = _compact_title(cleaned)

    if len(cleaned) > TITLE_MAX_LEN:
        cleaned = _compress_long_title(cleaned)

    cleaned = cleaned.strip(" ，,。.-—_|｜:：")
    return cleaned or "企业贷款怎么选？"


def _clean_title_text(title: str) -> str:
    """清理 Markdown 标题符号、品牌后缀和多余空白。"""
    text = (title or "").strip()
    text = re.sub(r"^#+\s*", "", text)
    text = re.sub(r"^[「『《【\[]|[」』》】\]]$", "", text)
    text = text.replace("上海市", "上海")
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[|｜]\s*沪上银.*$", "", text)
    text = re.sub(r"[-—_]\s*沪上银.*$", "", text)
    text = text.replace("企业才能经真实案例", "企业经营贷真实案例")
    text = text.replace("企业才能经营", "企业经营贷")
    text = text.replace("经营性贷款", "经营贷")
    text = text.replace("企业贷款融资", "企业融资")
    return text


def _remove_title_fillers(title: str) -> str:
    """删除空洞修饰词，保留人群、问题和结果。"""
    result = title
    for word in TITLE_FILLER_WORDS:
        result = result.replace(word, "")
    result = result.replace("上海市", "上海")
    result = re.sub(r"(案例|解析|说明){2,}$", "案例", result)
    result = re.sub(r"(方案|服务|推荐|平台)+$", "", result)
    return result


def _compact_title(title: str) -> str:
    """压缩重复关键词，避免标题像搜索词堆叠。"""
    result = title
    replacements = [
        ("贷款融资", "融资"),
        ("融资贷款", "融资"),
        ("企业企业", "企业"),
        ("贷款贷款", "贷款"),
        ("经营贷贷款", "经营贷"),
        ("银行贷款贷款", "银行贷款"),
        ("批款放款", "放款"),
    ]
    for old, new in replacements:
        result = result.replace(old, new)
    return result


def _looks_like_keyword_stacking(title: str) -> bool:
    """识别关键词堆砌标题：关键词密集、缺少自然语气和明确问题。"""
    if not title:
        return False
    if title in {
        "企业才能经营真实案例",
        "贷款融资专业解决方案服务",
        "上海贷款顾问快速办理推荐",
        "企业税票征信额度案例解析方案",
    }:
        return True

    keyword_count = sum(1 for keyword in TITLE_BUSINESS_KEYWORDS if keyword in title)
    has_natural_marker = any(marker in title for marker in TITLE_NATURAL_MARKERS)
    has_sentence_punctuation = any(mark in title for mark in "？，！：")
    return keyword_count >= 3 and not has_natural_marker and not has_sentence_punctuation


def _rewrite_stacked_title(title: str) -> str:
    """把关键词堆砌标题改写成公众号常见标题结构。"""
    if "企业才能经营" in title or ("真实案例" in title and ("经营" in title or "企业" in title)):
        return "企业经营贷真实案例"
    if "征信" in title:
        return "征信没问题，为何被拒？"
    if "上海" in title and "融资" in title:
        return "上海融资，先避开3坑"
    if "上海" in title and "贷款" in title:
        return "上海贷款中介怎么选？"
    if "经营贷" in title or ("企业" in title and "贷款" in title):
        return "企业经营贷为何被拒？"
    if "放款" in title or "批款" in title:
        return "3天放款，做对了什么？"
    if "利率" in title:
        return "利率变了，贷款怎么选？"
    if "融资" in title:
        return "企业融资，先避开3坑"
    if "贷款" in title:
        return "贷款被拒，问题在哪？"
    return "企业贷款怎么选？"


def _compress_long_title(title: str) -> str:
    """超过 22 字时自动压缩，优先保留核心信息。"""
    result = _remove_title_fillers(title)
    result = _compact_title(result)

    short_patterns = [
        (r".*(征信).*?(被拒).*", "征信没问题，为何被拒？"),
        (r".*(经营贷).*?(被拒|批不下来).*", "经营贷为何被拒？"),
        (r".*(上海).*?(融资).*?(坑).*", "上海融资，先避开3坑"),
        (r".*(企业).*?(资金周转).*", "企业资金周转怎么解？"),
        (r".*(放款).*?(成功|拿到).*", "3天放款，做对了什么？"),
    ]
    for pattern, replacement in short_patterns:
        if re.match(pattern, result):
            return replacement[:TITLE_MAX_LEN]

    if len(result) <= TITLE_MAX_LEN:
        return result

    # 尽量在标点处截断，避免半句话生硬断开。
    for mark in ["？", "！", "：", "，"]:
        idx = result.find(mark)
        if 8 <= idx + 1 <= TITLE_MAX_LEN:
            return result[:idx + 1]

    return result[:TITLE_MAX_LEN]


def write_article(topic: str, **kwargs) -> dict:
    """
    非模板路径的文章生成（已废弃）。
    请通过写作模板生成文章。
    """
    logger.warning("[Writer] write_article 已废弃，请通过写作模板生成文章")
    return {}


# ══════════════════════════════════════════════════════════════
# AI 写作
# ══════════════════════════════════════════════════════════════

def _ai_write_with_template(topic, structure_list, pain_point, solution,
                            hook, brand_rules, prompt_template, category, tmpl_name) -> dict:
    """调用 AI 按模板结构生成文章"""

    structure_text = ""
    for i, sec in enumerate(structure_list, 1):
        structure_text += f"  第{i}节：{sec}\n"

    footer = brand_rules.get("footer", "沪上银 · 上海专业贷款顾问")
    cta = brand_rules.get("cta", "有贷款疑问？点击菜单「免费咨询」，回复「咨询」获取专属方案")
    watermark = brand_rules.get("watermark", "沪上银原创")
    title_suffix = brand_rules.get("title_suffix", "")

    # 构建系统提示词
    system_prompt = f"""你是沪上银（上海专业贷款顾问）的公众号内容写手。

【品牌信息】
- 品牌名：沪上银
- 定位：上海专业贷款顾问
- 落款：{footer}
- 水印：{watermark}

【写作风格要求】
- 讲人话，通俗易懂，读者是普通人不是金融专家
- 专业词要加括号解释（例如：LPR 即贷款市场报价利率）
- 用具体例子（月供少多少、利率差多少）代替抽象数字
- 语气像朋友聊天，不要像教科书
- 每节至少200字，禁止空节或凑字数
- 必须出现具体的数字（如利率、月供、金额等），让文章有说服力
- 案例要有人名、行业、经营年限、具体金额和利率

【文章结构】
{structure_text}

【读者痛点】
{pain_point or '读者有贷款需求但不清楚如何选择和申请'}

【我们的解决方案】
{solution or '沪上银提供专业的一对一贷款咨询服务'}

【留资钩子】
{hook or '点击菜单「免费咨询」，回复「咨询」获取专属贷款方案'}

【Markdown 格式要求】
- 各节用 ## 标题，标题内容要与话题相关，不要写"解释""分析"这种抽象词
- ⚠️ 第一个 ## 标题禁止包含话题/文章标题中的关键词！否则会跟页面顶部标题横幅重复。例如话题是"经营贷申请攻略"，第一个 ## 标题不能写"经营贷申请攻略的底层逻辑"或"三步搞定经营贷申请"，应该写具体的内容如"为什么你的申请总被拒？"、"90%的人不知道的审批内幕"等
- 段落之间用空行分隔
- 列表项用 ▶ 符号（▶ 营业执照：需要是法人或股东……）
- 步骤用 **Step 1：标题** 格式
- 编号列表用 ①②③④ 格式
- 客户证言用 > 引用块（> 「之前被拒了两次都不知道为什么，沪上银帮我找到了问题所在，第三次就成功了。」）
- 案例标题用 **案例一：餐饮老板王总** 格式
- 节与节之间用 --- 分隔
- 不要在文末重复加标题，文章第一个 ## 之前就是正文开始

【「简单说」摘要块 — 必须有，固定放在标题后、正文第一节前】
格式（必须用这个格式，系统自动渲染成蓝色摘要框）：

> **📌 简单说**
> 第一句话：说清楚核心事实（数字/事件）。第二句话：说清楚背景或影响。第三句话：说清楚与读者的关系或行动意义。

示例：
> **📌 简单说**
> 央行宣布本月LPR下调10个基点，从3.95%降至3.85%。这是继去年以来第三次下调。市场分析人士认为，此次降息主要是为了刺激居民消费和房地产市场，降低企业和居民融资成本。

【配图卡片要求 — 必须在正文中插入以下4个配图标记】
配图标记放在两个段落之间的空行处，格式为 [配图:类型:标题:副文本]

① 场景图（放在「简单说」摘要块之后、第1节之前）：[配图:scene:场景描述文字:副标题]
   ⚠️ 重要：描述文字必须是具体的场景描述（如"上海银行大厅贷款咨询现场"、"经营贷审批流程一对一指导"），
   禁止填写文章标题本身，否则会与页面标题重复！
   示例：[配图:scene:上海银行大厅贷款咨询现场:专业 · 高效 · 值得信赖]

② 金句卡（正文中间，第2节和第3节之间放1张）：[配图:quote:金句内容:—沪上银 顾问]
   示例：[配图:quote:降了，关键是你能不能用上这个好政策:——沪上银 顾问]
   金句要有力量，用短句，不超过24字，直击读者痛点或心声
   ⚠️ 严禁把章节标题填进金句卡！禁止出现"Step X：……"、"第X步：……"、"步骤X："等结构
   ⚠️ 金句必须是独立的感悟/洞察/共鸣句，与章节标题内容完全不同，否则会与正文小标题重复

③ 数据卡（第3节和第4节之间放1张，必须是文章里出现过的真实数字）：[配图:data:核心数字结论:补充说明]
   示例：[配图:data:LPR每降0.1%，100万30年房贷月供减少约58元:30年累计少还约2万元]

④ 贴士卡（第4节「行动建议」内部，写完建议之后放1张）：[配图:tip:给读者的实用建议:适用人群]
   示例：[配图:tip:有存量房贷的朋友，现在可以联系银行申请利率重新定价:每年能少还几百到几千元，值得试试]

放置规则：简单说 → scene → 正文第1、2节 → quote → data → 正文第3节 → tip → 行动结尾，共4张

【写作要求】
- 话题和模板已经给你了，请你根据对话题的理解，纯原创撰写每一节的内容
- 不要搜索或编造外部新闻来源，用你的专业知识和合理的案例/数据来支撑
- 结尾自然提到沪上银的服务和联系方式
- 开头第一行直接写标题（用 # 开头），不要有任何寒暄或说明
"""

    # 如果模板有自定义 prompt_template，追加到系统提示词
    if prompt_template:
        system_prompt += f"\n【模板自定义提示词】\n{prompt_template}\n"

    user_prompt = f"""请以「{topic}」为主题，按照上面的文章结构写一篇完整的公众号文章。标题要吸引人，末尾加上「{title_suffix}」，直接输出 Markdown 格式的文章正文。

⚠️ 标题要求：
- 第一行标题用 # 开头，最佳 12～18 字，最多 22 字以内
- 标题要像真实公众号标题，读起来通顺自然，不要像关键词堆砌
- 优先使用提问型、结果型、痛点型、案例型、干货型
- 可以自然保留企业贷、经营贷、融资、银行贷款、征信、批款、放款、利率等业务词
- 禁止写成「贷款融资专业解决方案服务」「上海企业经营贷融资贷款批款服务」这类堆词标题
- 示例：「企业经营贷为什么被拒？」「上海融资，先避开这3坑」「一家企业如何拿到经营贷」「融资前别急，先看这5点」
"""
    if category == 'brand':
        user_prompt += f"\n💡 品牌宣传类建议标题自然短促，例如「为什么选择沪上银？」「贷款这件事，别绕路」「我们做对了什么」。"
    elif len(topic) > 8:
        user_prompt += f"\n💡 话题「{topic}」较长，建议用简称写标题，如把「小微企业融资方案」简称为「小微融资」、「经营性贷款申请流程」简称为「经营贷申请」等。"

    try:
        resp = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=4000,
            temperature=0.8,
        )
        text = resp.choices[0].message.content.strip()
        if not text:
            return {}

        # 解析标题和正文
        article = _parse_ai_output(text, topic, category, brand_rules)
        return article

    except Exception as e:
        logger.error(f"[Writer] AI生成失败: {e}")
        return {}


def _parse_ai_output(text: str, topic: str, category: str, brand_rules: dict) -> dict:
    """解析 AI 输出的 Markdown 文本为 dict"""
    lines = text.strip().split('\n')

    # 提取标题（第一个 # 开头的行，或第一行非空文本）
    title = ""
    content_lines = []
    found_title = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            content_lines.append(line)
            continue
        if not found_title and (stripped.startswith('# ') or stripped.startswith('## ')):
            title = stripped.lstrip('#').strip()
            found_title = True
            continue
        if not found_title and not content_lines:
            title = stripped
            found_title = True
            continue
        content_lines.append(line)

    if not title:
        title = f"{topic} - 沪上银专业解读"

    content = '\n'.join(content_lines).strip()

    # 去掉标题中的后缀（避免重复）
    title_suffix = brand_rules.get("title_suffix", "")
    if title_suffix and title.endswith(title_suffix):
        title = title[:-len(title_suffix)].strip()

    # 统一进行公众号标题优化，避免 AI 输出关键词堆砌或移动端过长标题。
    title = optimize_wechat_title(title)

    cat_labels = {
        'leads': '获客活动', 'brand': '品牌宣传', 'science': '知识科普',
        'service': '贷款方案匹配', 'finance': '融资规划', 'enterprise': '经营分析',
        'hotspot': '热点解读',
    }
    tag = cat_labels.get(category, '原创')

    return {
        "title": title,
        "content": content,
        "source_name": "沪上银原创",
        "source_url": "",
        "tags": f"{topic},{tag}",
    }


# ══════════════════════════════════════════════════════════════
# 结构化模板兜底（无 AI 时）
# ══════════════════════════════════════════════════════════════

# ─── Topic 智能精简（用于生成 ≤10 字标题）──────────────────────
def _smart_topic_short(topic: str, max_len: int = 5) -> str:
    """智能精简 topic，保留核心关键词，去除冗余修饰语。

    策略：
    1. 去掉尾部常见后缀（攻略/方案/指南/流程/解读/分析/全解析/入门）
    2. 常见词组缩写映射表（如「小微企业」→「小微」、「经营性贷款」→「经营贷」）
    3. 去掉中间的修饰语（如「一对一」「全流程」「一站式」）
    4. 结果截断到 max_len
    """
    s = topic.strip()

    # 常见尾部后缀去掉
    suffixes = ['攻略', '方案', '指南', '流程', '解读', '分析',
                '全解析', '入门', '详解', '手册', '大全', '汇总',
                '公众号', '是什么', '怎么样', '如何']
    for suf in suffixes:
        if s.endswith(suf):
            s = s[:-len(suf)]
            break

    # 常见词组缩写（长→短，按长度降序排列避免部分替换问题）
    abbreviations = [
        ('小微企业', '小微'),
        ('经营性贷款', '经营贷'),
        ('个人消费贷', '消费贷'),
        ('房屋抵押贷', '抵押贷'),
        ('信用贷款', '信用贷'),
        ('公积金贷款', '公积贷'),
        ('汽车贷款', '车贷'),
        ('房产抵押贷款', '抵押贷'),
        ('企业融资方案', '企业融资'),
        ('贷款申请攻略', '贷款申请'),
        ('房贷利率调整', '房贷利率'),
        ('征信修复方法全攻略', '征信修复'),
        ('征信修复全攻略', '征信修复'),  # 去掉后缀后再缩写
        ('贷款被拒原因大全', '贷款被拒'),
        ('降息政策解读', '降息政策'),
        ('LPR利率下调', 'LPR下调'),
        ('银行审批内幕', '审批内幕'),
        ('银行审批内幕揭秘', '审批内幕'),
        ('一对一咨询', ''),
        ('全流程指导', '指导'),
        ('一站式服务', ''),
        ('免费在线评估', '评估'),
        ('最新政策解读', '政策解读'),
        ('申请条件详解', '申请条件'),
        ('放款速度对比', '放款速度'),
        ('免费咨询入口', '咨询入口'),
        ('如何申请', '申请'),
        ('深度分析', '分析'),
        ('地区银行贷款', '银行贷款'),
        ('如何申请经营性', '申请经营'),
        ('沪上银是什么样的', '沪上银'),
    ]
    for long_word, short_word in abbreviations:
        s = s.replace(long_word, short_word)

    # 去掉中间常见修饰语
    fillers = ['如何', '怎样', '怎么', '为什么', '什么', '哪些', '哪种',
               '最全', '最新', '最详细', '完整', '全面', '深度']
    # 只去掉独立的修饰词，不破坏词组
    for f in fillers:
        if f in s and len(s) > max_len:
            s = s.replace(f, '')

    s = s.strip()

    # 最终截断兜底
    if len(s) > max_len:
        s = s[:max_len]

    return s or topic[:max_len]  # 兜底：至少返回原始截断


def _template_write_structured(topic, structure_list, pain_point, solution,
                               hook, brand_rules, category) -> dict:
    """无 AI 时，按模板结构自动填充生成文章"""

    footer = brand_rules.get("footer", "沪上银 · 上海专业贷款顾问")
    cta = brand_rules.get("cta", "有贷款疑问？点击菜单「免费咨询」，回复「咨询」获取专属方案")
    watermark = brand_rules.get("watermark", "沪上银原创")
    title_suffix = brand_rules.get("title_suffix", "")

    # 根据 topic + category 生成有吸引力的差异化标题
    seed = hash(topic) & 0xFFFFFF
    rng_title = random.Random(seed)
    # 兜底标题也按公众号标题风格生成，再统一走标题优化。
    # topic 过长时智能精简（去修饰语/缩写词组），保留核心语义。
    t = _smart_topic_short(topic) if len(topic) > 5 else topic
    cat_titles = {
        'leads': [
            f"{t}，你踩坑了",
            f"{t}：你真懂吗",
            f"{t}，别走弯路",
        ],
        'brand': [
            f"沪上银谈{t}",
            f"{t}，实话",
            f"为何做{t}",
        ],
        'science': [
            f"一文搞懂{t}",
            f"不懂{t}别借钱",
            f"{t}入门全解析",
        ],
        'service': [
            f"{t}哪种合适",
            f"三方案比{t}",
            f"{t}选对省大钱",
        ],
        'finance': [
            f"{t}怎么融资",
            f"{t}融资全攻略",
            f"{t}成本算清楚",
        ],
        'enterprise': [
            f"{t}真实案例",
            f"从困境到放款",
            f"{t}怎么做到的",
        ],
        'hotspot': [
            f"{t}影响你的钱",
            f"{t}，是利好吗",
            f"{t}贷款怎么变",
        ],
    }
    title_candidates = cat_titles.get(category, [f"{t}"])
    title = rng_title.choice(title_candidates)
    title = optimize_wechat_title(title)

    # 按结构生成各节
    # 对模板6（enterprise/案例型）的占位符章节名做进一步替换
    _enterprise_rng = random.Random(hash(topic) & 0xFFFFFF)
    struggle_words = ["资金紧张", "贷款被拒", "流水不足", "找不到渠道", "征信有问题", "没有抵押物"]
    result_words = ["顺利放款", "成功融资", "获批额度", "解决周转"]
    _sw = _enterprise_rng.choice(struggle_words)
    _rw = _enterprise_rng.choice(result_words)

    # 处理 structure_list：把「简单说」单独拿出来生成摘要，其余走 _generate_section
    sections = []
    jiandan_para = None

    for sec_name in structure_list:
        # 替换模板6中的XX占位符
        sec_display = (sec_name
                       .replace("差点因为XX放弃", f"差点因为{_sw}放弃")
                       .replace("从XX到XX的逆袭", f"从{_sw}到{_rw}的逆袭"))
        sec_name_lower = sec_display.lower()

        # 「简单说」单独处理：生成三句话摘要
        if "简单说" in sec_name:
            jiandan_para = _generate_jiandan_summary(topic, category)
            sections.append(f"## {sec_display}\n\n{jiandan_para}")
        else:
            para = _generate_section(topic, sec_display, sec_name_lower, pain_point, solution)
            sections.append(f"## {sec_display}\n\n{para}")

    # 拼接内容
    content = '\n\n'.join(sections)

    # 结尾留资
    if hook:
        content += f"\n\n---\n\n> {hook}\n\n> {cta}"

    cat_labels = {
        'leads': '获客活动', 'brand': '品牌宣传', 'science': '知识科普',
        'service': '贷款方案匹配', 'finance': '融资规划', 'enterprise': '经营分析',
        'hotspot': '热点解读',
    }
    tag = cat_labels.get(category, '原创')

    return {
        "title": title,
        "content": content,
        "source_name": f"{watermark}",
        "source_url": "",
        "tags": f"{topic},{tag}",
    }


def _generate_section(topic, sec_name, sec_name_lower, pain_point, solution):
    """根据章节名关键词生成段落，同一 topic 始终返回相同内容，不同 topic 返回不同内容"""

    # 用 topic 做种子，确保同一 topic 每次生成一致
    seed = hash(topic + sec_name) & 0xFFFFFFFF
    rng = random.Random(seed)

    # ═══════ 痛点/困惑类 ═══════
    # 注意：含"案例"的章节（如"案例一：xxx的真实困境"）不走痛点分支，直接下沉到案例分支
    if (any(k in sec_name for k in ["困惑", "痛点", "困境", "问题", "你是不是", "真实困境"])
            and "案例" not in sec_name):
        openings = [
            f"聊到{topic}，很多人第一反应是：我这条件够不够？会不会直接被银行拒？\n\n"
            f"这种担心很正常。{topic}涉及的细节确实不少——"
            f"利率怎么算、额度怎么定、哪家银行最适合自己……"
            f"没有专业人士指路，确实容易踩坑。\n\n"
            f"常见的问题有这几类：\n\n"
            f"▶ **被拒却不知道原因** —— 银行不会告诉你具体哪里不符合，只会说「暂不符合条件」\n\n"
            f"▶ **多家银行来回跑，每家说法都不一样** —— 每次查询都留下征信记录，越查越难批\n\n"
            f"▶ **不知道该准备什么材料** —— 准备错了再补，浪费时间还可能影响审批节奏\n\n"
            f"好消息是，{pain_point or '这些问题都有对应的解决方案'}，关键是要提前搞清楚。\n\n"
            f"> 「跑了三家银行都拒了，最后找到沪上银，才知道原来是征信查询太多的问题，调整一下就批了。」—— 陈先生，浦东",

            f"说起{topic}，很多经营者都有过这样的经历：\n\n"
            f"▶ 网上搜了一堆资料，越看越迷糊，也不知道自己符不符合\n\n"
            f"▶ 亲戚朋友都说方法不一样，根本不知道该信谁\n\n"
            f"▶ 好不容易去了银行，客户经理看了一眼就说「暂时不符合」，也不给你解释哪里出了问题\n\n"
            f"这种无力感，很多人都经历过。\n\n"
            f"问题的根源不是你的条件差，而是{pain_point or '没有找对路子、找对人'}。"
            f"同样的条件，交给专业顾问来操作，结果可能完全不同。\n\n"
            f"> 「自己去申请被拒了，以为没希望了，后来沪上银帮我重新梳理了一遍，第二次就通过了。」—— 王女士，徐汇",

            f"你有没有遇到过这些情况——\n\n"
            f"▶ 想做{topic}，但不知道自己的条件够不够、能批多少\n\n"
            f"▶ 看到银行广告说的利率很低，去了才发现门槛高得离谱\n\n"
            f"▶ 已经被拒过一次，征信留了查询记录，不知道后续还能不能申请\n\n"
            f"▶ 身边有人做成了，但他们的情况和你不一样，不知道能不能参考\n\n"
            f"这些困惑背后，{pain_point or '其实都指向同一个核心问题：缺乏准确的信息和专业的指导'}。\n\n"
            f"沪上银接触过上百个类似案例，大多数问题在专业人士看来，都有解法。\n\n"
            f"> 「以为需要很多条件才能申请，结果沪上银帮我分析之后发现完全够格，手续费还是零。」—— 张先生，闵行",
        ]
        return rng.choice(openings)

    # ═══════ 条件/要求类 ═══════
    if any(k in sec_name for k in ["条件", "基本", "要求", "门槛", "满足哪些"]):
        items_pool = [
            ("营业执照", "需要是法人或股东，营业执照已经满1年以上（部分银行要求满2年）"),
            ("经营流水", "公司对公账户或个人账户需要有持续的经营流水，近半年月均流水建议不低于贷款额的10%"),
            ("征信记录", "近2年内无连续逾期记录，近6个月查询次数不能太多（一般不超过6次）"),
            ("资产证明", "部分银行要求有抵押物（如名下房产），纯信用贷款对资质要求更高"),
            ("实际经营", "经营场地需真实存在，银行可能上门核实或要求提供租赁合同"),
            ("纳税记录", "近一年正常纳税，纳税额与经营流水大致匹配"),
            ("负债比例", "现有负债不超过月收入的50%，否则会影响新贷款审批"),
        ]
        chosen = rng.sample(items_pool, min(4, len(items_pool)))
        bullets = "\n\n".join(f"▶ **{name}**：{desc}" for name, desc in chosen)
        data_examples = [
            f"[配图:data:{topic}额度参考:资质一般约批30~80万，资质好可达100~300万]",
            f"[配图:data:{topic}利率区间:信用贷约3.8%~5.5%，抵押贷约3.2%~4.0%]",
            f"[配图:data:{topic}审批周期:快则3天，一般5~10个工作日，抵押贷约15天]",
        ]
        data_card = rng.choice(data_examples)
        tips = [
            f"如果你不确定自己是否符合{topic}的条件，最好先找专业顾问做一个资质诊断，"
            "而不是直接去银行碰壁——每次被拒都会留下征信查询记录，查多了反而影响后续申请。",
            f"在申请{topic}之前，建议先自查一遍这些条件，有不足的地方提前调整。"
            "比如流水不够可以先增加对公转账频次，征信有瑕疵可以优先选择容忍度高的银行。",
            f"不同银行对{topic}的要求弹性不同，有些看重流水，有些更看征信，"
            "建议先做一次全面的资质评估，再有针对性地选择银行，避免浪费征信资源。",
        ]
        return (
            f"想申请{topic}，需要满足哪些条件？不同银行的要求略有差异，但有几个共性门槛绕不开：\n\n"
            f"{bullets}\n\n"
            f"{data_card}\n\n"
            f"{rng.choice(tips)}"
        )

    # ═══════ 底层逻辑/原理类（优先于步骤类，避免"搞懂XX的底层逻辑"被误判为攻略）═══════
    if any(k in sec_name for k in ["底层", "逻辑", "搞懂", "原理", "为什么"]):
        logic_pool = [
            f"要真正搞懂{topic}，先要知道银行评估一笔贷款的底层逻辑。\n\n"
            f"银行审批 {topic} 时，主要看三个维度：\n\n"
            f"▶ **还款能力**（收入够不够覆盖月供）—— 一般要求月收入/流水是月供的2倍以上\n\n"
            f"▶ **信用记录**（你过去有没有按时还款）—— 近两年有逾期就会被重点审查\n\n"
            f"▶ **抵押/担保**（出问题了银行能不能回收损失）—— 有房产抵押能大幅提升额度\n\n"
            f"明白了这三个逻辑，你就能理解为什么条件差不多的人，结果完全不同——"
            f"很可能就是某个细节上差了一点。\n\n"
            f"[配图:data:{topic}核心数据:利率差0.5%，100万贷款3年多付利息约1.5万元]",

            f"{topic}背后，银行关心的其实就一件事：**你能不能按时还款，还不上的话有没有保障。**\n\n"
            f"具体体现在这几个判断维度上：\n\n"
            f"▶ **流水连续性**：月均流水是否稳定，有没有突然暴增暴跌的异常情况\n\n"
            f"▶ **行业风险偏好**：每家银行有不同的行业风控名单，有些行业被限制，有些受欢迎\n\n"
            f"▶ **负债覆盖率**：当前总负债 ÷ 月收入，超过50%就会拉低通过率\n\n"
            f"▶ **资质整体性**：单项差一点可以弥补，但多项都偏弱就很难通过\n\n"
            f"这就是为什么——找对银行、针对性准备，比盲目申请事半功倍。\n\n"
            f"[配图:data:{topic}关键指标:月均流水建议≥贷款额10%，征信查询近6个月≤6次]",
        ]
        return rng.choice(logic_pool)

    # ═══════ 步骤/攻略类 ═══════
    if any(k in sec_name for k in ["步骤", "三步", "攻略", "流程", "搞定", "怎么走", "规划", "三步走"]):
        step1_pool = [
            f"**Step 1：先摸清自己的资质底数**\n\n"
            f"在正式申请{topic}之前，先把自己的基本情况理清楚：\n\n"
            f"① 营业执照注册时间（满1年是基本门槛，满2年更好）\n\n"
            f"② 近6个月对公账户月均流水（建议不低于贷款额的10%）\n\n"
            f"③ 个人征信状况（近2年是否有逾期，近6个月查询次数）\n\n"
            f"④ 名下有无房产等可抵押资产（有的话能大幅提升额度和降低利率）\n\n"
            f"这一步搞清楚了，后面选产品和银行才能有的放矢。",

            f"**Step 1：整理申请{topic}需要的核心材料**\n\n"
            f"基础材料一般包括：营业执照正副本、法人身份证、近6个月对公流水、近3个月完税证明。\n\n"
            f"如果是抵押贷款，还需要房产证和不动产权证；如果是经营贷，还需要提供真实经营证明（如租赁合同、进销货记录等）。\n\n"
            f"材料准备齐全的情况下，最快3个工作日就能放款。材料有问题的，来回补充往往要多花1~2周。",
        ]
        step2_pool = [
            f"**Step 2：对比3~5家银行，找到最适合的{topic}方案**\n\n"
            f"不是所有银行都适合你。选银行要考虑：\n\n"
            f"▶ **国有大行**（工农中建）：利率最低（3.3%~3.8%），但审批最严，资质要求高\n\n"
            f"▶ **股份制银行**（招商、浦发、兴业等）：审批灵活，利率适中（3.8%~4.5%）\n\n"
            f"▶ **城商行**（上海银行、宁波银行等）：有不少针对本地小微企业的特色产品\n\n"
            f"建议同时推进3~5家，不要只看利率，还要看额度上限、还款方式、提前还款费用。",

            f"**Step 2：根据自身情况精准匹配{topic}产品**\n\n"
            f"同样是申请贷款，选错了产品类型，结果差距很大：\n\n"
            f"▶ 有房产的，优先考虑**抵押经营贷**，利率低（3.2%~4.0%），额度高（可达房产评估价7成）\n\n"
            f"▶ 没有房产但经营稳定的，选**信用经营贷**，无需抵押，最快3天放款\n\n"
            f"▶ 短期周转的，考虑**循环贷/随借随还**产品，灵活用款不浪费利息\n\n"
            f"[配图:data:{topic}利率对比:抵押贷约3.2%~4.0%，信用贷约4.0%~5.5%，百万利息年差约1.5万]",
        ]
        step3_pool = [
            f"**Step 3：提交材料，全程跟进审批**\n\n"
            f"材料提交后，银行会安排审批，一般流程是：提交材料 → 初审（1~3天）→ 补件/尽调（如需）→ 终审 → 放款。\n\n"
            f"这个阶段要注意：\n\n"
            f"① 保持电话畅通，银行可能核实经营情况\n\n"
            f"② 有补件通知要及时响应，拖延会影响审批节奏\n\n"
            f"③ 不要在审批期间申请其他贷款，避免征信被频繁查询\n\n"
            f"如果找沪上银帮你跟进，我们会全程盯着每个节点，出了问题第一时间处理。",

            f"**Step 3：放款后做好资金使用规划**\n\n"
            f"很多人忽略了这一步——{topic}批下来了，怎么用同样重要。\n\n"
            f"▶ 贷款资金要用于申请时填报的用途，银行会不定期检查资金流向\n\n"
            f"▶ 提前还款要确认有没有违约金（部分产品提前还款要收1%~2%的违约金）\n\n"
            f"▶ 到期续贷要提前1~2个月开始准备，避免资金空窗期\n\n"
            f"做好这些规划，才能真正用好这笔资金，避免后续麻烦。",
        ]
        return (
            f"{rng.choice(step1_pool)}\n\n"
            f"---\n\n"
            f"{rng.choice(step2_pool)}\n\n"
            f"---\n\n"
            f"{rng.choice(step3_pool)}"
        )

    # ═══════ 案例/真实/客户类（关键：不同 topic 用不同案例） ═══════
    # 客户证言/评价类（简短评价，区别于详细案例）—— 必须在"案例/客户"之前匹配
    # "客户怎么说"、"口碑" 等不含"案例"的章节用证言
    if (any(k in sec_name for k in ["证言", "评价", "口碑", "反馈", "客户怎么说", "用户说", "他们怎么说"])
            and not any(k in sec_name for k in ["案例", "真实故事"])):

        review_pool = [
            f"「之前自己跑银行申请{topic}，跑了三家都被拒，后来朋友介绍来沪上银，帮我理清了问题，两周就批了。」—— 刘女士，浦东新区，小微企业主\n\n"
            f"「{topic}这件事我完全不懂，顾问全程帮我解释和跟进，最终批了200万，比预期的还多。」—— 陈先生，闵行区，建筑工程\n\n"
            f"「晚上十点发消息都有人回，这种服务态度在上海真的很少见，以后有需要还找沪上银。」—— 赵先生，徐汇区，餐饮连锁",

            f"「从咨询{topic}到放款只用了10天，比我自己跑银行快了将近一个月，太省心了。」—— 黄先生，宝山区，制造加工\n\n"
            f"「沪上银的顾问很实在，会告诉你真实的审批概率，不会为了做成业务给你画大饼。」—— 吴女士，普陀区，教育培训\n\n"
            f"「零手续费，服务还这么好，跟那些开口就要两万中介费的中介完全不是一个档次。」—— 马先生，松江区，物流运输",

            f"「{topic}被三家银行拒了之后我已经不抱希望，结果沪上银帮我找到了问题并解决，太感谢了！」—— 林女士，长宁区，服装零售\n\n"
            f"「顾问帮我对比了5家银行的{topic}方案，最后选了利率最低的一家，一年省了好几千块利息。」—— 何女士，杨浦区，美容行业\n\n"
            f"「之前找过其他中介收了两万手续费，后来才知道沪上银是免费的，真的后悔没早点找他们。」—— 郑先生，虹口区，餐饮管理",
        ]
        return rng.choice(review_pool)

    # ═══════ 「共同规律/规律/总结」章节 —— 输出规律提炼，不再重复案例 ═══════
    if any(k in sec_name for k in ["共同规律", "规律", "背后的原因", "背后的逻辑"]):
        rule_pool = [
            f"回顾这几个{topic}案例，我们发现了一些共同规律：\n\n"
            f"① **问题早发现，比什么都重要。** 很多被拒的客户，症结只有一两个，提前知道就能提前修复。\n\n"
            f"② **银行不是只有一家。** 不同银行对{topic}的风控标准、偏好行业、流水要求都不同，"
            f"换一家银行就能批，这种情况并不少见。\n\n"
            f"③ **材料和时机很关键。** 同样的资质，材料准备充分、选对时机申请，通过率差距很大。\n\n"
            f"④ **找对人，少走弯路。** 沪上银积累了大量各行业的{topic}案例，"
            f"很多看起来棘手的问题，其实都有成熟的解法。\n\n"
            f"> 「贷款这件事，不是靠运气，是靠专业。」——沪上银顾问团队",

            f"这些{topic}案例的共同点，值得每一位经营者注意：\n\n"
            f"▶ **不要用「自己的感觉」评估通过率。** 银行的审批标准很细，"
            f"自我感觉条件不错但被拒、自我感觉条件很差但批了——两种情况都有。\n\n"
            f"▶ **征信查询次数管理很重要。** 每次申请都留记录，密集查询会让银行觉得你很缺钱，反而降低通过率。"
            f"要一次把方案确定好，再集中提交。\n\n"
            f"▶ **流水可以提前准备。** 很多{topic}申请失败，根本原因是流水不足，"
            f"这个问题提前3~6个月开始准备，就能避免。\n\n"
            f"▶ **专业顾问的价值在于信息差。** 沪上银掌握各银行最新政策，"
            f"帮你找到最匹配的产品，这是自己单独去跑做不到的。",
        ]
        return rng.choice(rule_pool)

    if any(k in sec_name for k in ["案例", "真实", "客户", "逆袭", "差点"]):
        # 9个行业案例池
        industries = [
            ("餐饮老板王总", "在杨浦区经营一家餐馆，流水很好但征信有一次逾期记录", "100万", "3.9%",
             "帮他选了一家对历史逾期容忍度高的银行，绕开了问题点"),
            ("建材店老板周先生", "在嘉定开店，旺季月入50万，淡季只有8万，流水季节性明显", "150万", "3.7%",
             "做了12个月加权流水分析报告，证明年均流水达标"),
            ("物流公司何总", "车队12辆，名下没有房产等可抵押资产，多家银行说不行", "120万", "4.2%",
             "用即将到账的政府补贴款做还款来源证明，成功从城商行拿到信用额度"),
            ("美容院孙姐", "两家店注册主体不同，银行只认其中一家的流水", "200万", "4.0%",
             "做了合并经营方案，用主店担保加个人房产补充，拿到双倍额度"),
            ("服装批发商李姐", "现金交易多，对公银行流水不够连续，申请{topic}被拒", "80万", "4.1%",
             "建议先把业务转账化3个月，再申请，一次通过"),
            ("装修公司刘总", "项目回款周期60~90天，账上经常缺现金，银行认为风险高", "80万", "4.5%",
             "对接供应链金融产品，用未完工合同做质押，解决了周转问题"),
            ("教育机构张总", "学费是预收款，对公流水大但被银行认定为代收性质，不算经营收入", "60万", "4.3%",
             "补充了学员合同和分期流水明细，重新解释收入来源，最终获批"),
            ("广告公司陈总", "公司成立刚满一年，征信空白，银行不愿意放款", "50万", "4.8%",
             "推荐了专门服务初创企业的城商行产品，用股权+保证人增信方式通过"),
            ("超市老板赵女士", "名下有房产但已有一笔按揭贷款，银行说负债率过高", "200万", "3.8%",
             "帮她梳理现有负债结构，先还清消费贷降负债率，腾出额度后顺利批了经营贷"),
        ]
        n = len(industries)
        # 先用 topic hash 对案例列表做固定顺序洗牌
        topic_seed = hash(topic) & 0xFFFFFF
        rng_topic = random.Random(topic_seed)
        shuffled = industries[:]
        rng_topic.shuffle(shuffled)
        # 再用 sec_name 的特征字符（一/二/三/逆袭/差点/真实）提取序号，确保章节间用不同索引
        _order_map = {"一": 0, "1": 0, "二": 1, "2": 1, "三": 2, "3": 2,
                      "四": 3, "4": 3, "五": 4, "5": 4}
        _sec_order = -1
        for ch, idx in _order_map.items():
            if ch in sec_name:
                _sec_order = idx
                break
        if _sec_order >= 0:
            # 找到了序号，直接按序号取对应案例（0→第0个，1→第1个…）
            sec_idx = _sec_order % n
        else:
            # 没有序号（如"差点"/"逆袭"），用 sec_name hash 取
            sec_idx = abs(hash(sec_name)) % n
        c = shuffled[sec_idx]

        def _name_short(name: str) -> str:
            """取案例人物的简称"""
            for sep in ["老板", "公司", "批发商", "机构", "广告", "超市"]:
                if sep in name:
                    name = name.split(sep)[-1]
                    break
            return name

        # 根据人物称谓判断性别
        _pronoun = "她" if ("姐" in c[0] or "女士" in c[0]) else "他"
        return (
            f"**案例：{c[0]}**\n\n"
            f"{_name_short(c[0])}来找沪上银之前，正在为{topic}发愁。"
            f"{_pronoun}的情况是：{c[1].replace('{topic}', topic)}。"
            f"银行那边拒了，也没给具体原因。\n\n"
            f"沪上银接手后，{c[4]}，最终顺利拿到 **{c[2]}**，利率 **{c[3]}**。\n\n"
            f"> 「{topic}这件事，一个人摸索太耗时间，找对人真的快很多。」"
        )

    # ═══════ 行动/联系类（必须在服务类之前匹配，因为"联系我们"含"我们"会误命中服务分支）═══════
    if any(k in sec_name for k in ["你也可以", "下一步", "行动", "联系", "咨询", "免费"]):
        cta_pool = [
            f"如果你正在为{topic}发愁，不妨迈出第一步——\n\n"
            f"回复关键词 **「咨询」**，沪上银专业顾问会在24小时内联系你，"
            f"帮你做一次免费的资质评估和方案匹配，不收任何费用。\n\n"
            f"也可以点击菜单栏的 **「免费咨询」**，填写你的基本情况，"
            f"我们会根据你的具体需求，为你量身定制最适合的方案。",

            f"如果你对{topic}还有疑问，或者想了解自己能申请多少额度——\n\n"
            f"**方式一**：关注沪上银公众号，回复 **「咨询」**，专属顾问一对一解答\n\n"
            f"**方式二**：点击底部菜单 **「免费咨询」**，在线提交基本信息，我们主动联系你\n\n"
            f"不收中介费，不强制办理，纯粹帮你把这件事搞清楚。",
        ]
        return rng.choice(cta_pool)

    # ═══════ 优势对比型（含"凭什么/为什么选/优势"的章节，展示差异化）═══════
    if any(k in sec_name for k in ["凭什么选", "为什么选", "优势", "亮点", "强在哪", "好在哪里"]):
        advantage_pool = [
            f"上海做{topic}的中介不少，但沪上银有几个不一样的地方：\n\n"
            f"▶ **不收中介费。** 很多中介开口就是一两万手续费，我们的服务完全免费，费用由合作银行承担。\n\n"
            f"▶ **对接10+家银行。** 不是只推一家的产品，而是帮你横向对比，找到利率最低、条件最匹配的方案。\n\n"
            f"▶ **全程一对一跟进。** 从第一次咨询到放款完成，一个人负责到底，不用反复跟不同的人讲你的情况。\n\n"
            f"▶ **本地团队更懂本地政策。** 专注上海市场，对各银行的产品要求、审批偏好都了如指掌。\n\n"
            f"▶ **提前预排查风险。** 正式申请前帮你做资质审查，发现问题提前解决，避免留下征信查询记录。",

            f"你可能会问：找沪上银和自己直接去银行有什么区别？\n\n"
            f"**区别一：信息差。** 每家银行的风控标准不同，同样的条件在这家被拒，另一家可能就批了。"
            f"我们掌握各家银行的最新产品信息和审批偏好，能帮你精准匹配。\n\n"
            f"**区别二：效率。** 自己跑银行，每家都要重新提交材料、等审批，"
            f"前后可能要一两个月。我们帮你同时推进多家，最快3天就能放款。\n\n"
            f"**区别三：成功率。** 很多客户被拒不是因为条件差，而是材料没准备对、银行没选好。"
            f"我们提前帮你排查这些问题，大大提高通过率。\n\n"
            f"**区别四：零成本。** 咨询免费、评估免费，不办也没关系。",
        ]
        return rng.choice(advantage_pool)

    # ═══════ 服务列表型（含"服务/核心/我们"的章节，展示具体服务内容）═══════
    if any(k in sec_name for k in ["服务", "帮你", "我们", "沪上银能", "核心"]):
        service_pool = [
            "① **免费资质诊断**\n\n"
            "告诉我们你的基本情况（营业执照年限、大概流水、征信情况），"
            "我们帮你判断能申请哪些产品、大概能批多少。\n\n"
            "② **全市场方案比较**\n\n"
            "我们同时对接上海10+家银行，能帮你横向比较，"
            "找出最适合你的贷款方案，而不是只推一家。\n\n"
            "③ **材料全程辅导**\n\n"
            "审批材料怎么准备、流水不够怎么补、征信有瑕疵怎么处理——这些细节我们提前告诉你。\n\n"
            "④ **全程跟进放款**\n\n"
            "从提交材料到最终放款，我们全程跟进，有问题第一时间帮你处理。",

            "① **一对一顾问服务**\n\n"
            "每位客户都配有专属顾问，从第一次咨询到放款完成，全程由同一个人跟进，不用反复讲你的情况。\n\n"
            "② **10+银行产品覆盖**\n\n"
            "国有大行、股份制银行、城商行我们都有合作渠道，帮你匹配到条件最宽松、利率最优的产品。\n\n"
            "③ **问题预排查**\n\n"
            "正式申请前，我们会先帮你做一次全面的资质审查，提前发现可能被拒的原因，避免留下征信查询记录。\n\n"
            "④ **零中介费**\n\n"
            "我们的服务对客户完全免费，费用由合作银行支付。你不需要为咨询服务花一分钱。",
        ]
        return rng.choice(service_pool)

    # ═══════ 方案/对比类 ═══════
    if any(k in sec_name for k in ["方案", "推荐", "最优", "适合哪种"]):
        plan_pool = [
            f"面对{topic}，市场上主流的方案有三种，各有适用人群：\n\n"
            f"▶ **方案A：低利率抵押型**\n"
            f"适合名下有房产的客户。用房产做抵押，利率约3.2%~4.0%，额度可达房产评估价的7成，"
            f"审批稍严，周期10~15天。100万贷款月供约5500元，一年利息约3.5万。\n\n"
            f"▶ **方案B：纯信用灵活型**\n"
            f"适合没有房产但经营稳定的客户。凭营业执照和流水申请，利率约4.0%~5.5%，"
            f"额度10~150万，最快3天放款。100万贷款月供约6000元，一年利息约5万。\n\n"
            f"▶ **方案C：快速周转型**\n"
            f"适合急需短期资金的客户。循环贷/随借随还产品，随时用款、随时还款，"
            f"只算实际用款天数的利息，灵活性最高，利率约4.5%~6%。\n\n"
            f"[配图:data:{topic}方案对比:同样100万，抵押贷年利息约3.5万，信用贷约5万，差1.5万]\n\n"
            f"选哪种方案，取决于你的资产状况、资金需求和用款节奏。"
            f"建议让顾问先做资质评估，再确定方向，不要凭感觉选。",

            f"针对{topic}，根据客户资质和需求的不同，沪上银通常会推荐以下几种路径：\n\n"
            f"▶ **资质好 + 有房产** → 抵押经营贷，利率3.2%~3.8%，额度高，最划算\n\n"
            f"▶ **资质好 + 没有房产** → 信用经营贷，利率3.8%~4.5%，审批快，适合急用\n\n"
            f"▶ **资质一般 + 有房产** → 二抵贷款（二次抵押），利率4.0%~5%，对资质要求较宽\n\n"
            f"▶ **资质一般 + 没有房产** → 担保贷或政策性贷款，利率相对高，但能解燃眉之急\n\n"
            f"[配图:data:{topic}路径建议:有房产优先走抵押路线，可节省利息30%~40%]\n\n"
            f"每种路径对应的银行产品不同，沪上银会根据你的实际情况帮你做精准匹配，"
            f"不会千人一面地推同一款产品。",
        ]
        return rng.choice(plan_pool)

    # ═══════ 误区/避坑/被拒原因类 ═══════
    if any(k in sec_name for k in ["误区", "注意", "避坑", "坑", "被拒", "常见"]):
        pool_a = [
            f"▶ **误区一：只看利率，不看综合成本。**\n有的{topic}产品利率低，但有服务费、评估费、担保费等隐性收费，算下来综合成本反而更高。",
            f"▶ **误区二：以为被一家银行拒了就贷不出来了。**\n每家银行的风控标准不同，某家拒了，换一家可能就批了——关键是要搞清楚为什么被拒，针对性地调整。",
            f"▶ **误区三：不重视征信，觉得偶尔逾期没关系。**\n{topic}审批时，近2年的征信记录是重点，有连续逾期记录会直接降低通过率。",
            f"▶ **误区四：找中介要花很多钱。**\n沪上银的咨询和服务对客户完全免费，费用由合作银行支付，不需要出一分中介费。",
        ]
        pool_b = [
            f"▶ **误区一：流水不够就没希望。**\n流水不够有多种合规方式可以优化，关键是提前规划，而不是拿着现有流水直接去申请。",
            f"▶ **误区二：被拒一次征信就废了。**\n单次查询影响不大，但短期内频繁查询（如一个月内查了5次以上）确实会给银行留下不好的印象。",
            f"▶ **误区三：{topic}一定要有房产。**\n纯信用贷款产品也有不少，额度最高可达150万，不需要任何抵押物，适合经营稳定的客户。",
            f"▶ **误区四：利率越低越好，其他都不重要。**\n利率之外还要看额度是否够用、期限是否匹配、还款方式是否灵活，综合权衡才能选到最优方案。",
        ]
        pool_c = [
            f"▶ **误区一：找熟人关系能加快审批。**\n银行审批走系统流程，熟人最多是一个沟通渠道，真正决定结果的还是你的资质数据。",
            f"▶ **误区二：{topic}批下来就万事大吉。**\n贷款批下来只是第一步，资金使用要合规（银行会查资金流向），还款计划要安排好，续贷要提前准备。",
            f"▶ **误区三：所有银行的{topic}要求都一样。**\n不同银行的审批侧重点差异很大，选对银行能大幅提升通过率，有时候就差在这一步。",
            f"▶ **误区四：先申请，被拒了再找专业人帮。**\n每次申请被拒都会留下征信查询记录，最好一开始就做好准备、一次成功，减少无效的征信消耗。",
        ]
        chosen = rng.choice([pool_a, pool_b, pool_c])
        return (
            f"很多人在申请{topic}时踩过这些坑，提前了解可以少走弯路：\n\n"
            + "\n\n".join(chosen)
        )

    # ═══════ 总结/规律类 ═══════
    if any(k in sec_name for k in ["规律", "共同", "经验", "总结", "背后", "共通"]):
        summary_pool = [
            f"整理了这么多关于{topic}的案例，有几个规律反复出现：\n\n"
            f"▶ **提前诊断，比什么都重要。**\n"
            f"很多客户被拒，不是因为条件差，而是没有针对性地准备。"
            f"提前做一次资质诊断，把问题搞清楚，往往能避开80%的障碍。\n\n"
            f"▶ **选对银行，利率差别很大。**\n"
            f"同样申请{topic}，不同银行的利率差距可以达到0.5%~1.5%。"
            f"100万贷款的情况下，3年下来的利息差距就是1.5万~4.5万。\n\n"
            f"▶ **专业的人，真的能改变结果。**\n"
            f"贷款涉及的细节很多，很多普通人做不到的事情，"
            f"专业顾问一个电话就能解决。这就是信息差的价值。\n\n"
            f"> 「早知道有沪上银这样的服务，我就不用白跑那么多趟了。」—— 刘先生，上海，贸易公司负责人",

            f"做{topic}这件事，我们见过太多案例，有几个共通点值得所有人注意：\n\n"
            f"▶ **别急着申请，先搞清楚自己的条件。**\n"
            f"很多人被拒，不是因为条件差，是没有选对银行，或者材料准备有问题。"
            f"花一天时间做资质自查，可以少走几个月的弯路。\n\n"
            f"▶ **细节决定成败。**\n"
            f"流水怎么提交、征信怎么解释、材料怎么组织——"
            f"这些看似小事的细节，往往是审批通过的关键。\n\n"
            f"▶ **善用专业资源，效率是自己来的好几倍。**\n"
            f"沪上银对接10+家银行，同时推进、比价、跟进，"
            f"客户自己做需要1~2个月的事，我们可以在2周内完成。\n\n"
            f"> 「本来打算自己去跑，后来发现信息差太大，找专业的人真的值。」—— 赵女士，上海，教育培训",
        ]
        return rng.choice(summary_pool)

    # ═══════ 品牌故事/价值观类（品牌宣传模板特有）═══════
    if any(k in sec_name for k in ["品牌", "故事", "价值观", "使命", "愿景", "初心"]):
        story_pool = [
            "沪上银成立之初，就定了一个简单的原则：**让每一个在上海经营的人，都能找到适合自己的贷款方案。**\n\n"
            "我们见过太多经营者——开餐馆的、做批发的、跑运输的——他们勤劳肯干，生意做得也不错，"
            "却在贷款这件事上反复碰壁。不是条件不够好，而是不知道该找谁、该怎么申请、哪家银行最适合自己。\n\n"
            "沪上银想做的，就是成为这群人和银行之间的那座桥。"
            "不需要你懂金融术语，不需要你跑遍所有银行，你只需要把自己的情况告诉我们，"
            "剩下的专业分析、方案比较、材料准备、进度跟进，都交给我们。\n\n"
            "[配图:quote:我们的初心:让贷款这件事变得简单透明]",

            "在沪上银看来，贷款不只是一笔钱的事，它关系到一个小店的存亡、一个项目的成败、一个家庭的未来。\n\n"
            "我们团队里很多人本身就是创业者出身，深知经营者的难处——"
            "白天忙生意，晚上算账，还要操心资金周转。"
            "正因为自己经历过，所以更懂得每一位客户的需求不只是一纸合同，"
            "而是一份安心的承诺、一个可靠的支撑。\n\n"
            "[配图:quote:服务承诺:不夸大、不隐瞒、不收中介费]",
        ]
        return rng.choice(story_pool)

    # ═══════ 方案匹配引导类（模板4专用：「你的情况适合哪种方案」）═══════
    if any(k in sec_name for k in ["你的情况", "适合哪种", "适合哪个"]):
        guide_pool = [
            f"做{topic}之前，先来判断一下你的情况属于哪种类型，这决定了你应该走哪条路：\n\n"
            f"▶ **A型：资质优质**（营业执照满2年+，月均流水50万+，征信无瑕疵，名下有房产）\n"
            f"→ 推荐走抵押经营贷，利率可以压到3.2%~3.8%，额度最高\n\n"
            f"▶ **B型：资质中等**（营业执照满1年+，月均流水20~50万，征信基本干净，无房产）\n"
            f"→ 推荐走信用经营贷，利率4.0%~4.8%，3~7天放款\n\n"
            f"▶ **C型：资质偏弱或急需资金**（营业执照不满1年，或征信有逾期，或需要3天内放款）\n"
            f"→ 需要特殊方案，沪上银有专门的应急通道\n\n"
            f"[配图:tip:先做资质自测，再选方案，成功率提升60%以上:避免盲目申请被拒，消耗征信]\n\n"
            f"不确定自己是哪种类型？把你的情况告诉沪上银，我们帮你做一次精准评估，免费且保密。",

            f"很多人申请{topic}失败，不是因为条件差，而是没有选对适合自己的路径。\n\n"
            f"先回答几个问题，判断你属于哪种情况：\n\n"
            f"① **名下有房产吗？**（有 → A路径；没有 → B/C路径）\n\n"
            f"② **营业执照满多久了？**（满2年 → 更多选择；不满1年 → 需要特殊方案）\n\n"
            f"③ **最近6个月月均流水多少？**（10万以下 → C路径；10~50万 → B路径；50万以上 → A路径）\n\n"
            f"④ **征信最近有逾期记录吗？**（有 → 需要先做征信修复或选特定银行）\n\n"
            f"根据这几个维度的组合，可以判断出最合适的{topic}方案。"
            f"如果你懒得自己判断，直接找沪上银，10分钟给你一个清晰的答案。",
        ]
        return rng.choice(guide_pool)

    # ═══════ 方案A/B/C：资质类型对应方案（模板4专用）═══════
    if any(k in sec_name for k in ["方案A", "方案B", "方案C", "适合资质好", "适合资质一般", "适合急需"]):
        if "A" in sec_name or "资质好" in sec_name:
            return (
                f"**适合人群**：营业执照满2年以上，月均对公流水50万+，名下有住宅或商业房产，个人征信干净（近2年无逾期）\n\n"
                f"**推荐产品**：抵押经营贷\n\n"
                f"▶ 利率范围：**3.2%~3.8%**（目前市场最低水平）\n\n"
                f"▶ 额度上限：**房产评估价的65%~70%**，通常可达200~500万\n\n"
                f"▶ 审批周期：10~15个工作日\n\n"
                f"▶ 还款方式：等额月供或先息后本，灵活选择\n\n"
                f"**沪上银建议**：这类客户条件好，但不同银行的具体利率差异仍然存在。"
                f"我们会帮你在10+家银行中找到当月利率最低的方案，通常能比自己直接去银行少付0.2%~0.5%的利率。\n\n"
                f"[配图:data:方案A参考:100万3年，利率3.5%，月供约2936元，总利息约5.7万]"
            )
        elif "B" in sec_name or "资质一般" in sec_name:
            return (
                f"**适合人群**：营业执照满1~2年，月均流水10~50万，没有房产，征信基本干净（偶有一两次逾期）\n\n"
                f"**推荐产品**：信用经营贷\n\n"
                f"▶ 利率范围：**3.9%~4.8%**\n\n"
                f"▶ 额度范围：**10~150万**（根据流水和资质综合评定）\n\n"
                f"▶ 审批周期：3~7个工作日，最快当天出方案\n\n"
                f"▶ 优势：无需任何抵押物，纯信用申请\n\n"
                f"**沪上银建议**：这类客户选对银行非常关键——有些银行对「无房产+中等流水」的客户几乎不批，"
                f"另一些银行这正是他们的核心客群。我们的经验是能帮这类客户把通过率从30%提升到70%+。\n\n"
                f"[配图:data:方案B参考:100万3年，利率4.2%，月供约2972元，总利息约6.9万]"
            )
        else:  # 方案C / 急需资金
            return (
                f"**适合人群**：急需资金周转（3~7天内要用），或者资质有一定瑕疵（征信有逾期、营业执照不满1年等）\n\n"
                f"**推荐方案**：快速信用贷 / 短期过桥贷 / 政策性贷款（视具体情况）\n\n"
                f"▶ 快速信用贷：3天放款，利率4.5%~6%，额度10~50万，适合应急周转\n\n"
                f"▶ 政策性贷款：适合科创企业、小微商户，有政府贴息，实际成本更低\n\n"
                f"▶ 过桥贷款：用于等待正式贷款放款前的短期资金空缺，日利率0.05%~0.08%\n\n"
                f"**沪上银建议**：这类情况需要具体分析，不建议盲目选产品。"
                f"先和顾问沟通清楚你的紧急程度和资质情况，我们帮你找最合适、综合成本最低的方案。\n\n"
                f"[配图:tip:急需资金时，先咨询后申请，避免因盲目申请损耗征信:留电话24小时内有顾问联系]"
            )

    # ═══════ 企业融资需求自检类（模板5专用）═══════
    if any(k in sec_name for k in ["现在需要融资", "企业现在", "你的企业"]):
        check_pool = [
            f"做{topic}之前，先问自己几个问题：\n\n"
            f"▶ **资金缺口有多大？** —— 几十万的短期周转和几百万的扩张资金，需要的路径完全不同\n\n"
            f"▶ **用款期限是多久？** —— 3个月内能还上的，选短期信用贷；2~3年的，选期限匹配的经营贷\n\n"
            f"▶ **用途是什么？** —— 设备采购、备货铺货、人员扩张、场地租金……不同用途有不同的对应产品\n\n"
            f"▶ **现金流能否覆盖月供？** —— 月供通常不应超过月均净利润的50%，否则还款压力太大\n\n"
            f"如果这几个问题你都能清晰回答，{topic}的方向就基本定了。"
            f"如果还不确定，先跟沪上银顾问聊聊，帮你梳理清楚再做决定。\n\n"
            f"[配图:tip:融资前先做三件事：明确缺口、算好月供、备好材料:避免因准备不足导致审批被拒]",

            f"很多企业主觉得{topic}很难，其实难的不是贷款本身，而是不清楚自己需要的是什么。\n\n"
            f"来做一个简单的融资需求自检：\n\n"
            f"① **你是资金短缺还是资金错配？**\n"
            f"如果是短缺（收入不够），需要增加经营收入，融资只是辅助；"
            f"如果是错配（有收入但时间不匹配），适合用短期贷款填补时间差。\n\n"
            f"② **融资成本是否合理？**\n"
            f"一笔贷款的年利率是4.5%，意味着借100万一年的成本是4.5万。"
            f"你的生意一年能产生多少利润？如果利润远超利息，融资是合算的。\n\n"
            f"③ **还款来源清晰吗？**\n"
            f"银行最担心的不是借款方现在的收入，而是未来的还款来源是否可预期。\n\n"
            f"把这三个问题想清楚，再去申请{topic}，成功率和满意度都会高很多。",
        ]
        return rng.choice(check_pool)

    # ═══════ 融资方式横向对比类（模板5专用）═══════
    if any(k in sec_name for k in ["主流融资", "融资方式", "融资对比", "三种"]):
        finance_cmp_pool = [
            f"目前针对{topic}，企业主常用的融资方式主要有三种，各有优劣：\n\n"
            f"**① 银行经营贷**\n"
            f"优势：利率最低（3.2%~4.5%），额度可以很高（50~500万），期限长（1~5年）\n"
            f"劣势：审批严格，材料多，周期7~15天，需要营业执照满1年以上\n\n"
            f"**② 融资担保贷款**\n"
            f"优势：门槛比银行直贷低，适合资质稍弱的企业\n"
            f"劣势：需要支付担保费（通常贷款金额的1%~2%/年），综合成本偏高\n\n"
            f"**③ 供应链金融/应收账款融资**\n"
            f"优势：用未回款的合同或应收账款质押，不看营业执照年限，适合有稳定大客户的企业\n"
            f"劣势：额度受限于应收账款规模，手续比较复杂\n\n"
            f"[配图:data:{topic}融资成本对比:银行贷年息约4万，担保贷约6万，民间借贷约15万（以100万为例）]\n\n"
            f"哪种方式适合你，取决于你的资质条件、资金用途和紧急程度。建议先咨询专业顾问，再做决定。",
        ]
        return rng.choice(finance_cmp_pool)

    # ═══════ 融资成本计算类（模板5专用）═══════
    if any(k in sec_name for k in ["算一笔账", "划算", "最划算", "成本计算"]):
        calc_pool = [
            f"很多人觉得{topic}麻烦，干脆借民间借贷或者刷信用卡垫付——这其实是最贵的选择。\n\n"
            f"来算一笔账：\n\n"
            f"**假设借100万用1年**\n\n"
            f"▶ 银行经营贷（利率4.0%）：年利息 **4万元**\n\n"
            f"▶ 银行担保贷（利率4.5%+担保费1.5%）：年综合成本 **6万元**\n\n"
            f"▶ 小额贷款公司（月息1%）：年利息 **12万元**\n\n"
            f"▶ 民间借贷（月息2%）：年利息 **24万元**\n\n"
            f"[配图:data:{topic}100万融资年成本对比:银行贷4万 vs 小贷公司12万 vs 民间借贷24万]\n\n"
            f"同样是借100万，选错渠道一年多付20万利息。"
            f"这还不算民间借贷可能存在的法律风险和催收压力。\n\n"
            f"结论很清楚：**能走银行渠道的，就不要走其他渠道。**"
            f"沪上银帮你对接10+家银行，利率最低的方案第一时间给到你。",
        ]
        return rng.choice(calc_pool)

    # ═══════ 热点解读模板专属分支（ID=7）═══════
    # 第4节：上海最新市场情况
    if any(k in sec_name for k in ["市场情况", "最新市场", "市场动态", "行情"]):
        market_pool = [
            f"根据沪上银对上海市场的跟踪，目前{topic}相关的银行产品有以下趋势：\n\n"
            f"▶ **利率方面**：国有大行普遍在3.2%~3.8%区间，股份制银行略高0.3%~0.5%，"
            f"城商行为了抢客户，部分产品可以做到3.0%起\n\n"
            f"▶ **额度方面**：抵押类产品最高可达房产评估价7成，信用类产品主流在30~150万区间\n\n"
            f"▶ **审批节奏**：材料齐全的情况下，信用贷3~7天放款，抵押贷10~15天\n\n"
            f"▶ **政策风向**：近期监管部门鼓励银行加大对实体经济的支持，"
            f"符合条件的客户通过率有所提升\n\n"
            f"[配图:data:{topic}上海市场速览:利率3.0%~4.5%，额度10万~500万，周期3~15天]",

            f"上海本地银行对{topic}的态度可以用四个字概括：**积极但谨慎**。\n\n"
            f"**积极**体现在——各家银行都在推相关产品，利率一降再降，"
            f"有的银行甚至推出限时优惠，比基准利率还低。\n\n"
            f"**谨慎**体现在——审批标准并没有放松，征信、流水、经营真实性查得依然很严。\n\n"
            f"具体到产品选择：\n\n"
            f"▶ 求稳的选国有大行，利率低但要求高\n"
            f"▶ 求快的选股份制银行，审批灵活\n"
            f"▶ 资质一般的选城商行，容忍度相对较高\n\n"
            f"沪上银建议：不要盲目跟风选「最低利率」，适合自己的才是最好的。",
        ]
        return rng.choice(market_pool)

    # 第5节：你现在应该怎么做？
    if any(k in sec_name for k in ["你应该怎么做", "怎么做", "行动建议", "下一步", "现在该"]):
        action_pool = [
            f"面对{topic}，建议你分三步走：\n\n"
            f"**第一步：先搞清楚自己的资质底数**\n"
            f"拿出纸笔（或打开备忘录），列清楚：营业执照注册时间、近6个月月均流水、"
            f"个人征信是否有逾期、名下有无房产。这四项决定了你能申请什么产品。\n\n"
            f"**第二步：对比至少3家银行的方案**\n"
            f"不要只看利率，还要看额度上限、还款方式、提前还款费用。"
            f"有些产品利率低但额度小，有些额度高但审批严。\n\n"
            f"**第三步：找专业顾问把关**\n"
            f"自己跑银行容易踩坑——材料准备不对、银行没选对、时机没把握好，"
            f"都会浪费时间甚至影响征信。沪上银可以帮你免费预审，避免走弯路。\n\n"
            f"▶ 评估免费 &nbsp; ▶ 不强制办理 &nbsp; ▶ 24小时内给出方案建议",

            f"如果你已经被{topic}的变化影响到了，建议尽快做这几件事：\n\n"
            f"① **算清楚自己的资金缺口**——需要多少、用多久、什么时候要\n\n"
            f"② **自查一遍征信和流水**——近6个月查询次数、有无逾期、流水是否连续\n\n"
            f"③ **咨询专业顾问做预评估**——在正式申请前搞清楚自己能批多少、利率大概多少\n\n"
            f"④ **准备好核心材料**——营业执照、流水、纳税记录、房产证（如有）\n\n"
            f"⑤ **同时推进2~3家银行**——不要把鸡蛋放一个篮子里，"
            f"但也不要同时申请太多（征信查询记录会累积）\n\n"
            f"需要帮忙的话，点击菜单「免费咨询」，沪上银顾问会在24小时内联系你。",
        ]
        return rng.choice(action_pool)

    # 默认段落（兜底，动态嵌入topic）
    default_pool = [
        f"{topic}这件事，关键在于两点：**一是清楚自己的条件，二是找到合适的渠道。**\n\n"
        f"很多人卡在第一步——不知道自己到底能贷多少、利率是多少、哪家银行最适合自己。"
        f"其实只要把这些搞清楚了，后面的流程并不复杂。\n\n"
        f"沪上银可以帮你免费做一次全面的资质评估，"
        f"把你的条件和市场上的产品做精准匹配，找到最合适的方案。\n\n"
        f"▶ 不收中介费 &nbsp; ▶ 对接10+家银行 &nbsp; ▶ 全程一对一跟进\n\n"
        f"> 「在沪上银咨询之后才明白，之前被拒完全是因为没选对银行，调整一下就批了。」—— 周先生，上海",

        f"关于{topic}，不少人有疑问，但又不知道该问谁。\n\n"
        f"贷款这件事说难不难，说简单也不简单——"
        f"难在信息不透明，每家银行的条件不一样，自己研究很容易被绕晕；"
        f"简单在于，只要找对了方向，大多数情况都有解法。\n\n"
        f"如果你正在为{topic}发愁，不妨先做一次免费的资质评估。"
        f"告诉沪上银你的基本情况，我们帮你理清思路，找到最合适的路径。\n\n"
        f"▶ 评估免费 &nbsp; ▶ 不强制办理 &nbsp; ▶ 24小时内给出方案建议\n\n"
        f"> 「专业的事交给专业的人，沪上银帮我省了好几万利息和好几个月时间。」—— 陈先生，上海",
    ]
    return rng.choice(default_pool)


def _generate_jiandan_summary(topic, category):
    """生成「简单说」三句话摘要（用于结构化兜底）"""
    seed = hash(topic + "简单说") & 0xFFFFFFFF
    rng = random.Random(seed)

    # 热点解读类：事实+影响+方向（通用化，适配任意话题）
    if category == "hotspot":
        hotspot_pool = [
            f"{topic}引发市场关注，核心变化是利率/政策/审批条件出现调整。"
            f"这一变化将直接影响贷款成本、额度或申请难度，不同人群受影响程度不同。"
            f"建议有贷款需求的读者及时了解详情，评估是否需要调整申请策略或重新定价。",

            f"近期{topic}成为上海贷款市场焦点，涉及银行产品利率和审批标准的变化。"
            f"对于已有贷款的客户，可能意味着月供减少或重新定价的机会；"
            f"对于准备申请的客户，需要了解最新门槛和最优产品选择。"
            f"建议尽快咨询专业顾问，把握政策窗口期。",

            f"{topic}的落地标志着贷款市场环境出现新变化，银行在产品设计和风控策略上有所调整。"
            f"从市场反馈看，优质客户更容易获得利率优惠，审批效率也有所提升。"
            f"建议借款人根据自身情况，评估是否需要转换产品或调整融资计划。",
        ]
        return rng.choice(hotspot_pool)

    # 通用三句话模板（事实+背景+建议）
    general_pool = [
        f"{topic}是当前上海贷款市场的热门话题，涉及利率、额度和审批条件等关键要素。"
        f"不同银行对同一客户的审批结果可能差异很大，选对渠道能节省大量时间和成本。"
        f"建议先做一次免费资质评估，搞清楚自己能申请什么产品，再针对性准备材料。",

        f"关于{topic}，核心在于搞清楚三个问题：你能贷多少、利率多少、哪家银行最适合。"
        f"很多人被拒不是因为条件差，而是没选对银行或材料准备有问题。"
        f"沪上银可以帮你横向对比10+家银行，找到条件最匹配、利率最优的方案。",

        f"{topic}的审批逻辑并不复杂，银行主要看还款能力、信用记录和抵押担保三方面。"
        f"只要这三项没有硬伤，大多数客户都能找到合适的贷款产品。"
        f"不确定自己是否符合条件？先做一份免费资质诊断，避免盲目申请浪费征信。",
    ]
    return rng.choice(general_pool)
