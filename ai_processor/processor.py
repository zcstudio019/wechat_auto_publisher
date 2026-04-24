"""
AI内容优化模块：
- 优化标题
- 生成摘要
- 将文章内容格式化为微信公众号风格 HTML（精美排版）

品牌定位：沪上银 — 上海专业贷款顾问服务
内容方向：贷款知识科普 / 利率政策解读 / 融资方案 / 企业经营
"""
import logging
import re
import hashlib
from datetime import datetime
from config import USE_AI, OPENAI_API_KEY, OPENAI_BASE_URL

logger = logging.getLogger(__name__)

if USE_AI:
    try:
        from openai import OpenAI
        _client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    except Exception as e:
        logger.warning(f"[AI] OpenAI初始化失败: {e}")
        _client = None
else:
    _client = None

# 品牌常量（与config保持一致，避免循环依赖）
_BRAND = "沪上银"
_BRAND_SLOGAN = "上海本地贷款顾问 · 搞不清楚贷款的，来找我们聊聊"


def _call_ai(system_prompt: str, user_prompt: str, max_tokens=2000) -> str | None:
    if not _client:
        return None
    try:
        resp = _client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"[AI] 调用失败: {e}")
        return None


def optimize_title(title: str) -> str:
    """优化标题：通俗易懂，让普通用户一眼看懂跟自己有什么关系"""
    if not USE_AI:
        return title
    result = _call_ai(
        f"""你是「{_BRAND}」公众号的内容主笔，读者是普通老百姓——有房贷的上班族、需要贷款的个体户、想搞清楚融资的小老板。
他们不懂金融术语，但很关心"这事跟我的钱包有没有关系"。
你的标题风格：大白话、接地气、一眼看懂、让人想点进来。""",
        f"""请将以下标题改写，让普通人一看就懂、想点进来。
要求：
- 用大白话，避免"货币政策""MLF""逆回购"等专业词
- 直接说影响（月供少了多少、能省多少钱、手续变简单了等）
- 可以带一点口语感（"你知道吗""原来如此""快来看"等）
- 字数控制在20字以内
- 只输出改写后的标题，不加任何解释

原标题：{title}""",
        max_tokens=60
    )
    return result if result else title


def generate_summary(content: str) -> str:
    """生成80-120字摘要，用大白话说清楚这篇文章跟读者有什么关系"""
    if not USE_AI:
        text = re.sub(r'[#*\[\]()>]', '', content)
        text = re.sub(r'\n+', ' ', text).strip()
        return text[:120] + "…" if len(text) > 120 else text

    result = _call_ai(
        f"你是「{_BRAND}」公众号主笔，读者是普通人——上班族、个体户、小老板，不懂专业术语但很关心自己的钱。摘要要让他们一看就知道这篇文章值不值得点开。",
        f"""根据以下文章，写一段80-120字的摘要。
要求：
- 用大白话，不用专业金融术语（如要用，要马上解释）
- 先说发生了什么事（一句话讲清楚）
- 再说对普通人的钱袋子有什么影响（月供、贷款利率、额度等）
- 结尾可以来一句"有疑问可以问问我们"之类的轻松引导
- 语气像跟朋友聊天，不要太正式

文章内容：\n\n{content[:2000]}""",
        max_tokens=200
    )
    if result:
        return result
    text = re.sub(r'[#*\[\]()>]', '', content)
    text = re.sub(r'\n+', ' ', text).strip()
    return text[:120] + "…" if len(text) > 120 else text


def _enrich_content_with_ai(title: str, content: str, source_name: str) -> str | None:
    """
    用AI对内容进行深度加工——通俗易懂风格，像朋友聊天一样
    输出结构：核心要点 === 深度正文 === 对普通人的影响 === 沪上银说
    """
    return _call_ai(
        f"""你是「{_BRAND}」公众号的内容主笔。沪上银是上海的贷款顾问服务，专门帮普通人搞定贷款问题。

你的读者是谁：
- 有房贷的上班族，关心月供能不能少一点
- 想开店/扩张的小老板，需要流动资金
- 准备买房的年轻人，搞不清楚贷款怎么申请
- 总之：普通人，不是金融专家

你的写作原则（非常重要）：
1. 【讲人话】不用"货币宽松""流动性注入"这种词，换成"钱更好借了""银行放款更积极了"
2. 【举例子】说利率降了0.1%，不如说"100万房贷30年，每月能少还50多块"
3. 【有温度】写作像朋友在微信里聊天，不是新闻联播念稿子
4. 【给建议】不要总是"需根据个人情况"，要给出明确的方向（"如果你有这个情况，建议这样做"）
5. 【带品牌】结尾自然提一下沪上银能帮什么，但不要硬广

专业词汇替换参考（遇到这些词必须改写，不能直接用）：
金融术语：
- LPR → 贷款基准利率（各家银行定价的参考标准）
- MLF → 央行借钱给银行的利率
- 降准 → 央行让银行多放贷款（释放更多资金）
- 基点/bp → 0.01%（比如"10个基点"就是"0.1%"）
- 货币政策宽松 → 贷款环境变好了、利率可能下降
- 逆回购 → 央行向市场短期注资
- 存款准备金率 → 银行必须存在央行的钱的比例

股市/指数相关（普通人看不懂，要解释或省略）：
- 费城半导体指数 → 美国芯片股整体涨跌情况
- 纳斯达克 → 美国科技股市场
- 标普500 → 美国500家大公司的综合股价指数
- 道琼斯 → 美国30家龙头企业的股价指数
- 上证指数/沪深300 → A股整体涨跌情况
- 如果文章主要讲股市，要解释"这对贷款/利率有什么间接影响"，不然普通读者无感

重要原则：如果某段内容只是股市涨跌，跟贷款完全无关，可以缩写或省略，聚焦到跟读者钱袋子有关的部分。

严格按以下格式输出（用===分隔，不要加标题文字）：
[核心要点：2-3条，每条用大白话说，普通人一看就懂]===
[正文：结合真实生活场景分析，500-700字，用Markdown格式，语气自然亲切。

必须在正文中穿插 2-4 个配图标记，使用以下四种类型之一，放在合适的段落之间：

① 场景图（开头必须有一张）：[配图:scene:描述文字:副标题]
   示例：[配图:scene:上海陆家嘴贷款顾问:专业 · 高效 · 值得信赖]
   ↑ 描述=图片上显示的标题文字（8-15字），副标题=配合说明（5-12字）

② 金句卡（正文中间放1-2张）：[配图:quote:金句内容:—沪上银]
   示例：[配图:quote:利率降了，不代表你就能贷到更便宜的款——关键看你的条件:—沪上银贷款顾问]
   ↑ 用于强调核心观点、过渡到下一段，金句要有实质内容（15-30字）

③ 数据卡（有数字对比时用）：[配图:data:核心数字或对比结论:补充解释]
   示例：[配图:data:100万房贷，利率降0.1%，每月少还约55元:30年总共少还约2万元]
   ↑ 核心数字要具体，直接算出来写进去

④ 贴士卡（结尾前用1张）：[配图:tip:给读者的实用建议:适用人群或条件]
   示例：[配图:tip:现在是申请经营贷的好时机，准备好营业执照+流水就可以来咨询:适合有1年以上经营记录的小老板]

配图放置规则：
- 正文开头第一段之后：放 scene 类型
- 正文中间每隔2-3段：放 quote 或 data 类型
- 正文末尾段落前：放 tip 类型
- 切勿把配图放在段落中间，必须放在两个段落之间的空行处]===
[对你的影响：分"有房贷的人"和"需要贷款的人/小老板"两个角度，大白话，100-150字]===
[沪上银说：一句温馨提醒+沪上银能帮什么，30-50字，自然不生硬]""",
        f"标题：{title}\n\n原文：\n{content[:2000]}\n\n来源：{source_name}",
        max_tokens=1800
    )


def _parse_ai_enriched(ai_text: str):
    """解析AI返回的结构化内容"""
    parts = ai_text.split("===")
    if len(parts) >= 4:
        return {
            "key_points": parts[0].strip(),
            "body": parts[1].strip(),
            "impact": parts[2].strip(),
            "comment": parts[3].strip(),
        }
    return None


def format_to_wechat_html(title: str, content: str, source_name: str = "") -> str:
    """
    将 Markdown/纯文本内容转换为微信公众号风格 HTML（精美排版）
    """
    if USE_AI:
        # 先尝试AI深度加工内容结构
        enriched_text = _enrich_content_with_ai(title, content, source_name)
        if enriched_text:
            parsed = _parse_ai_enriched(enriched_text)
            if parsed:
                return _render_rich_html(title, parsed, source_name)

        # 退而求其次：让AI直接输出HTML
        html_result = _call_ai(
            f"""你是「{_BRAND}」公众号的排版编辑，风格：亲切、接地气、普通人看得懂。将给定文章转化为精美的微信公众号HTML。
要求：
1. 使用内联CSS样式
2. 蓝色渐变横幅（#1565C0到#1976D2）展示标题，白色字体，padding 20px
3. 正文段落字体16px，行高1.9，颜色#333
4. 利率/金额/百分比用红色加粗（#e74c3c）
5. 重要词（贷款/月供/利率等）蓝色加粗（#1565C0）
6. 如有专业术语，用括号加简单解释（例如：LPR（贷款基准利率））
7. 文末加「{_BRAND}」落款和日期
8. 只输出body内部HTML，不要外层标签""",
            f"文章标题：{title}\n\n文章内容：\n{content[:3000]}",
            max_tokens=2500
        )
        if html_result:
            return html_result

    return _basic_format_rich(title, content, source_name)


def _render_rich_html(title: str, parsed: dict, source_name: str) -> str:
    """
    将AI解析的结构化内容渲染为精美HTML
    """
    today = datetime.now().strftime("%Y年%m月%d日")

    # 处理要点
    key_points_html = ""
    key_points_text = parsed.get("key_points", "")
    bullets = []
    for line in key_points_text.split("\n"):
        line = line.strip().lstrip("-•*·▶►→123456789. \t")
        if len(line) > 5:
            bullets.append(line)
    if bullets:
        items_html = "".join(
            f'<div style="display:flex;align-items:flex-start;margin:8px 0;">'
            f'<span style="color:#1565C0;font-weight:bold;margin-right:8px;flex-shrink:0;">▶</span>'
            f'<span style="color:#333;font-size:15px;line-height:1.7;">{b}</span>'
            f'</div>'
            for b in bullets[:4]
        )
        key_points_html = f'''
<div style="background:#EEF4FF;border-left:4px solid #1565C0;border-radius:6px;padding:16px 18px;margin:20px 0;">
  <div style="color:#1565C0;font-weight:bold;font-size:14px;margin-bottom:10px;letter-spacing:1px;">📌 先看这几点</div>
  {items_html}
</div>'''

    # 处理正文（AI 已在正文中插入多个配图标记，_text_to_paragraphs 会自动渲染）
    body_text = parsed.get("body", "")
    # 如果 AI 没生成 scene 开头图（用户可能没有AI），兜底在正文前插一张场景卡
    if "[配图:" not in body_text and "[配图：" not in body_text:
        _seed_num = int(hashlib.md5(title.encode("utf-8")).hexdigest()[:4], 16) % 1000
        body_text = (
            f"[配图:scene:{title}:沪上银 · 上海专业贷款顾问]\n\n"
            + body_text
        )
    body_html = _text_to_paragraphs(body_text)

    # 对普通人的影响（区块前加一个视觉分隔卡）
    impact_text = parsed.get("impact", "")
    impact_html = ""
    if impact_text:
        impact_html = f'''
<div style="background:linear-gradient(135deg,#FFF8E1,#FFF3CD);border-left:4px solid #FFA000;border-radius:10px;padding:20px 20px 16px;margin:28px 0;">
  <div style="display:flex;align-items:center;margin-bottom:12px;">
    <span style="font-size:22px;margin-right:10px;">💰</span>
    <span style="color:#E65100;font-weight:bold;font-size:15px;letter-spacing:1px;">这跟你有什么关系？</span>
  </div>
  <p style="color:#555;font-size:15px;line-height:1.9;margin:0;">{impact_text}</p>
</div>'''

    # 沪上银说（前加一个金句/推荐卡作为视觉过渡）
    comment_text = parsed.get("comment", "")
    comment_html = ""
    if comment_text:
        # 从评论文字中提取关键词作为数据卡标题
        _short_tip = comment_text[:40] if len(comment_text) > 40 else comment_text
        comment_html = f'''
{_make_image_card(_short_tip, "tip", "点击下方联系沪上银顾问")}
<div style="background:linear-gradient(135deg,#EEF4FF,#E3EEFF);border:1px solid #C5D8FF;border-radius:12px;padding:16px 20px;margin:20px 0;display:flex;align-items:flex-start;gap:12px;">
  <div style="flex-shrink:0;width:40px;height:40px;background:#1565C0;border-radius:50%;display:flex;align-items:center;justify-content:center;">
    <span style="color:#fff;font-size:18px;">沪</span>
  </div>
  <div>
    <div style="color:#1565C0;font-size:13px;font-weight:bold;margin-bottom:6px;">{_BRAND}说</div>
    <p style="color:#333;font-size:14px;line-height:1.8;margin:0;">{comment_text}</p>
  </div>
</div>'''

    # 落款
    source_html = f'''
<div style="margin-top:30px;padding-top:16px;border-top:1px solid #eee;display:flex;justify-content:space-between;align-items:center;">
  <span style="color:#1565C0;font-size:12px;font-weight:bold;">{_BRAND} · 上海专业贷款顾问</span>
  <span style="color:#bbb;font-size:12px;">{today}</span>
</div>'''

    return f'''<div style="font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;max-width:100%;box-sizing:border-box;padding:0 4px;">

<!-- 标题横幅 -->
<div style="background:linear-gradient(135deg,#0D47A1,#1565C0,#1976D2);border-radius:12px;padding:24px 22px 20px;margin-bottom:6px;position:relative;overflow:hidden;">
  <div style="position:absolute;top:-30px;right:-30px;width:120px;height:120px;background:rgba(255,255,255,0.06);border-radius:50%;"></div>
  <div style="position:absolute;bottom:-20px;left:40%;width:80px;height:80px;background:rgba(255,255,255,0.04);border-radius:50%;"></div>
  <div style="color:rgba(255,255,255,0.65);font-size:11px;letter-spacing:2px;margin-bottom:10px;text-transform:uppercase;">沪上银 · 上海专业贷款顾问</div>
  <h1 style="color:#fff;font-size:20px;font-weight:bold;margin:0 0 10px;line-height:1.5;">{title}</h1>
  <div style="color:rgba(255,255,255,0.55);font-size:12px;">{today} {f"· 来源：{source_name}" if source_name else ""}</div>
</div>

{key_points_html}

<!-- 正文 -->
<div style="padding:4px 2px;">
{body_html}
</div>

{impact_html}

{comment_html}

{source_html}

</div>'''


def _basic_format_rich(title: str, content: str, source_name: str = "") -> str:
    """
    无AI时使用的精美基础格式
    """
    today = datetime.now().strftime("%Y年%m月%d日")
    lines = content.split('\n')
    html_parts = []

    # ── 识别「简单说」摘要块 ──────────────────────────────────────────
    # 优先识别 AI 写的 > **📌 简单说** 引用块（以 > 开头，含"简单说"字样）
    # 失败时降级：取正文前两行非标题行
    jiandan_lines = []   # 简单说内容行
    rest_lines = []      # 剩余正文行
    in_jiandan = False
    jiandan_done = False

    for line in lines:
        stripped = line.strip()
        if not jiandan_done:
            if stripped.startswith('>') and '简单说' in stripped:
                in_jiandan = True
                # 本行只是标题行，跳过
                continue
            elif in_jiandan and stripped.startswith('>'):
                # 摘要内容行
                jiandan_lines.append(stripped.lstrip('>').strip())
                continue
            elif in_jiandan and not stripped.startswith('>') and stripped:
                # 离开引用块
                in_jiandan = False
                jiandan_done = True
                rest_lines.append(line)
            else:
                rest_lines.append(line)
        else:
            rest_lines.append(line)

    if jiandan_lines:
        # 有 AI 写的「简单说」
        intro_text = ' '.join(jiandan_lines)
        # 清理残留 Markdown（**...**）
        intro_text = re.sub(r'\*\*', '', intro_text)
        # 清理 AI 误输出的括号提示文字，如（核心摘要，3句话）（核心摘要）（共3句话）等
        intro_text = re.sub(r'^[（(][^）)]{0,20}[）)]\s*', '', intro_text).strip()
        html_parts.append(f'''
<div style="background:#EEF4FF;border-left:4px solid #1565C0;border-radius:6px;padding:14px 16px;margin:16px 0;">
  <div style="color:#1565C0;font-weight:bold;font-size:13px;margin-bottom:6px;">📌 简单说</div>
  <p style="color:#555;font-size:15px;line-height:1.8;margin:0;">{intro_text}</p>
</div>''')
        lines = rest_lines if rest_lines else lines
    else:
        # 降级：取前两行非标题行
        intro_lines = []
        body_lines = []
        filled = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if not filled and len(stripped) > 10 and not stripped.startswith('#'):
                intro_lines.append(stripped)
                if len(intro_lines) >= 2:
                    filled = True
            else:
                body_lines.append(line)

        if intro_lines:
            intro_text = " ".join(intro_lines)[:150]
            html_parts.append(f'''
<div style="background:#EEF4FF;border-left:4px solid #1565C0;border-radius:6px;padding:14px 16px;margin:16px 0;">
  <div style="color:#1565C0;font-weight:bold;font-size:13px;margin-bottom:6px;">📌 简单说</div>
  <p style="color:#555;font-size:15px;line-height:1.8;margin:0;">{intro_text}</p>
</div>''')
            lines = body_lines if body_lines else lines

    # 在导读区后插入场景卡（图片+浮层标题，不复用文章标题以免重复）
    _sc_cap, _sc_sub = _scene_caption(title)
    html_parts.append(_make_image_card(_sc_cap, "scene", _sc_sub))

    # 统计正文行数，用于在中间插图
    content_lines = [l.strip() for l in lines if l.strip()]
    total_lines = len(content_lines)
    mid_point = total_lines // 2
    line_count = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 在正文中间插入一张金句/数据卡
        line_count += 1
        if line_count == mid_point and total_lines > 4:
            # Quote 卡使用预设金句（不从正文取内容），彻底避免与正文重复
            _q_pool = [
                "专业的人做专业的事，贷款这件事，交给沪上银",
                "利率降了，关键是你能不能用上这个好政策",
                "每少一分利，都是你努力经营的回报",
                "专业顾问的价值，在于帮你少走弯路",
                "钱用对地方，才是真正的财务规划",
                "借得好，也是一种经营能力",
                "找对人，少走弯路——这才是贷款最值钱的地方",
                "贷款不是赌运气，是靠专业和经验",
                "每一笔融资背后，都需要一个懂你的顾问",
                "资金周转顺了，生意才能跑起来",
            ]
            import hashlib as _hqb
            _qib = int(_hqb.md5(title.encode()).hexdigest()[:4], 16) % len(_q_pool)
            html_parts.append(_make_image_card(
                _q_pool[_qib],
                "quote",
                f"— {_BRAND}"
            ))
        line = line.strip()
        if not line:
            continue
        if line.startswith('### '):
            html_parts.append(
                f'<h3 style="color:#1565C0;font-size:17px;font-weight:bold;margin:24px 0 10px;'
                f'padding-bottom:6px;border-bottom:1px solid #e0e8f5;">{line[4:]}</h3>'
            )
        elif line.startswith('## '):
            _h2_text = line[3:]
            # h2 去重：避免跟文章标题重复
            _title_core = re.sub(r'[\s|·\-—_|沪上银贷款顾问攻略指南解读分析详解全面深度一二三四五六七八九十]+', '', title)
            if len(_title_core) >= 2:
                _h2_core = re.sub(r'[\s|·\-—_的了一是]+', '', _h2_text)
                _overlap = sum(1 for c in _title_core if c in _h2_core)
                _overlap_ratio = _overlap / max(len(_title_core), 1)
                if _overlap_ratio > 0.6 and len(_h2_text) > 4:
                    _h2_alts = [
                        "这些关键点，90%的人都忽略了",
                        "不看这篇，你的申请可能白跑一趟",
                        "银行不会主动告诉你的那些事",
                        "为什么有人一次过，有人被拒三次？",
                        "读懂这些，少走一半弯路",
                    ]
                    import hashlib as _hh2
                    _ai = int(_hh2.md5(_h2_text.encode()).hexdigest()[:4], 16) % len(_h2_alts)
                    _h2_text = _h2_alts[_ai]
            html_parts.append(
                f'<h2 style="color:#1565C0;font-size:19px;font-weight:bold;margin:28px 0 12px;'
                f'padding-bottom:8px;border-bottom:2px solid #1565C0;">{_h2_text}</h2>'
            )
        elif line.startswith('# '):
            html_parts.append(
                f'<h1 style="color:#1565C0;font-size:21px;font-weight:bold;margin:28px 0 12px;">{line[2:]}</h1>'
            )
        elif line.startswith(('- ', '* ', '• ')):
            text = _md_inline(line[2:])
            text = _highlight_numbers(text)
            html_parts.append(
                f'<div style="display:flex;align-items:flex-start;margin:8px 0;">'
                f'<span style="color:#1565C0;margin-right:8px;flex-shrink:0;font-size:16px;">▶</span>'
                f'<span style="font-size:15px;line-height:1.8;color:#333;">{text}</span>'
                f'</div>'
            )
        elif re.match(r'^\d+\.', line):
            text = _md_inline(line)
            text = _highlight_numbers(text)
            html_parts.append(
                f'<p style="font-size:15px;line-height:1.8;margin:8px 0;padding-left:4px;color:#333;">{text}</p>'
            )
        elif line.startswith('>'):
            quote = _md_inline(line.lstrip('> ').strip())
            html_parts.append(
                f'<blockquote style="background:#F5F5F5;border-left:3px solid #999;padding:10px 14px;'
                f'margin:12px 0;color:#666;font-size:14px;line-height:1.7;">{quote}</blockquote>'
            )
        else:
            text = _md_inline(line)
            text = _highlight_numbers(text)
            html_parts.append(
                f'<p style="font-size:16px;line-height:1.9;margin:12px 0;color:#333;">{text}</p>'
            )

    # 底部品牌落款前加一张贴士卡（CTA）
    html_parts.append(_make_image_card(
        f"有贷款问题？欢迎找沪上银顾问免费咨询，帮你算清楚再决定",
        "tip",
        "上海本地团队 · 无中介费 · 专业评估"
    ))

    # 底部品牌落款
    html_parts.append(f'''
<div style="margin-top:32px;padding:16px 20px;background:linear-gradient(135deg,#0D47A1,#1565C0);border-radius:12px;display:flex;justify-content:space-between;align-items:center;">
  <div>
    <div style="color:#fff;font-size:14px;font-weight:bold;">{_BRAND} · 上海专业贷款顾问</div>
    <div style="color:rgba(255,255,255,0.65);font-size:12px;margin-top:3px;">搞不清楚贷款的，来找我们聊聊</div>
  </div>
  <span style="color:rgba(255,255,255,0.55);font-size:12px;">{today}</span>
</div>''')

    title_banner = (
        f'<div style="background:linear-gradient(135deg,#0D47A1,#1565C0,#1976D2);border-radius:12px;'
        f'padding:24px 22px 20px;margin-bottom:16px;position:relative;overflow:hidden;">'
        f'<div style="position:absolute;top:-30px;right:-30px;width:120px;height:120px;'
        f'background:rgba(255,255,255,0.06);border-radius:50%;"></div>'
        f'<div style="color:rgba(255,255,255,0.65);font-size:11px;letter-spacing:2px;margin-bottom:10px;">'
        f'沪上银 · 上海专业贷款顾问</div>'
        f'<h1 style="color:#fff;font-size:20px;font-weight:bold;margin:0 0 10px;line-height:1.5;">{title}</h1>'
        f'<div style="color:rgba(255,255,255,0.55);font-size:12px;">{today}</div>'
        f'</div>'
    )

    body_html = '\n'.join(html_parts)
    return (
        f'<div style="font-family:-apple-system,BlinkMacSystemFont,\'PingFang SC\',\'Hiragino Sans GB\','
        f'\'Microsoft YaHei\',sans-serif;max-width:100%;box-sizing:border-box;padding:0 4px;">\n'
        f'{title_banner}\n{body_html}\n</div>'
    )


def _highlight_numbers(text: str) -> str:
    """
    高亮数字、百分比、贷款关键词。
    关键：先把文本按 HTML 标签拆分，只处理标签外的纯文字部分，
    避免把 style="color:#e74c3c;" 里的数字也替换掉造成标签破坏。

    处理顺序（必须严格遵守）：
    1. 先做关键词高亮（在纯文字上替换，避免数字高亮时破坏新生成的标签属性值）
    2. 再做数字/百分比高亮（每次都重新拆标签，跳过已有 HTML 标签）
    """
    keywords = [
        "LPR", "MLF", "降息", "降准", "加息", "利率", "央行", "人民银行",
        "货币政策", "存款准备金", "逆回购", "公开市场操作",
        "贷款", "房贷", "经营贷", "消费贷", "信用贷", "抵押贷",
        "月供", "额度", "征信", "还款", "融资",
    ]

    def _process_plain(plain: str) -> str:
        """对一段纯文字（不含 HTML 标签）依次做关键词高亮、数字高亮"""
        # Step 1：关键词高亮（蓝色加粗）
        # 用正则边界保证不重复替换（关键词不在已处理的 <strong> 内）
        for kw in keywords:
            plain = plain.replace(kw, f'\x00KW_OPEN\x00{kw}\x00KW_CLOSE\x00')
        # 将占位符换成真正的 HTML（此时文字里不含任何 HTML 标签，数字安全）
        plain = plain.replace('\x00KW_OPEN\x00', '<strong style="color:#1565C0;">')
        plain = plain.replace('\x00KW_CLOSE\x00', '</strong>')

        # Step 2：现在文字里已有关键词的 <strong> 标签，再拆一次，只对纯文字做数字高亮
        sub_parts = re.split(r'(<[^>]+>)', plain)
        out = []
        for sp in sub_parts:
            if sp.startswith('<') and sp.endswith('>'):
                out.append(sp)
            else:
                # 高亮百分比（红色加粗）
                sp = re.sub(
                    r'(\d+\.?\d*\s*%)',
                    r'<strong style="color:#e74c3c;">\1</strong>',
                    sp
                )
                # 高亮独立小数（避免重复处理带%的）
                sp = re.sub(
                    r'(?<![%\d])(\d+\.\d+)(?!\d*%)',
                    r'<strong style="color:#e74c3c;">\1</strong>',
                    sp
                )
                out.append(sp)
        return ''.join(out)

    # 将输入文本按已有 HTML 标签拆分，只对纯文字片段处理
    parts = re.split(r'(<[^>]+>)', text)
    result = []
    for part in parts:
        if part.startswith('<') and part.endswith('>'):
            result.append(part)
        else:
            result.append(_process_plain(part))
    return ''.join(result)


def _md_inline(text: str) -> str:
    """
    将行内 Markdown 语法转为 HTML（仅处理 **bold** 和 `code`），
    必须在 _highlight_numbers 之前调用，避免 style 属性里的 # 颜色值被误处理。
    """
    # **bold** → <strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # `code` → <code>
    text = re.sub(r'`(.+?)`', r'<code style="background:#f0f0f0;padding:1px 4px;border-radius:3px;">\1</code>', text)
    return text


def _scene_caption(title: str) -> tuple:
    """
    根据文章标题生成 scene 图片卡的场景描述文字（大标题 + 副标题），
    避免与文章标题横幅内容重复。
    返回 (caption, subtitle) 两个字符串。
    """
    kw = title  # 原始标题，用于关键词匹配

    # 关键词 → (场景大标题, 场景副标题)
    rules = [
        (["经营贷", "企业贷"],      ("上海小微企业经营贷款咨询现场", "用好政策 · 少付利息 · 轻装前行")),
        (["房贷", "按揭", "公积金"], ("上海二手房按揭贷款审批流程", "专业评估 · 快速放款 · 全程跟进")),
        (["LPR", "利率", "降息", "降准"], ("上海银行贷款利率政策解读", "读懂政策 · 抓住时机 · 降低成本")),
        (["信用贷", "消费贷"],       ("上海信用贷款申请资料审核", "无抵押 · 放款快 · 利率透明")),
        (["抵押", "抵押贷"],         ("上海房产抵押贷款评估现场", "房产变流动资金 · 应急更从容")),
        (["融资", "资金"],           ("上海企业融资规划咨询", "科学规划 · 多渠道融资 · 降低风险")),
        (["征信", "信用"],           ("银行征信报告解读与修复指导", "了解自己的信用 · 贷款更顺利")),
        (["获客", "营销", "引流"],   ("沪上银 · 贷款顾问团队", "专业服务 · 精准获客 · 共创共赢")),
    ]

    for keywords, (caption, sub) in rules:
        if any(kw_item in kw for kw_item in keywords):
            return caption, sub

    # 兜底：通用场景
    return "上海专业贷款顾问一对一咨询", "量身定制方案 · 让借贷更简单"


def _make_image_card(desc: str, card_type: str = "scene", subtitle: str = "") -> str:
    """
    生成带文字的图文卡片组件。
    card_type:
      - scene  : 场景配图卡（图片+浮层文字标题）
      - quote  : 金句卡（深色背景+大字金句，不用图片）
      - data   : 数据卡（浅蓝背景+数字/对比展示）
      - tip    : 提示卡（橙色背景+小贴士）
    """
    seed = hashlib.md5(desc.encode("utf-8")).hexdigest()[:8]
    # 图片选主题色系：根据 seed 取余决定暖/冷调
    img_seed_num = int(seed[:4], 16) % 1000
    img_url = f"https://picsum.photos/seed/{img_seed_num}/900/420"

    if card_type == "quote":
        # 金句卡：无图片，蓝色渐变背景+大字（紧凑版）
        return f'''
<div style="background:linear-gradient(135deg,#1565C0,#0D47A1);border-radius:10px;padding:18px 20px;margin:16px 0;text-align:center;position:relative;overflow:hidden;">
  <div style="position:absolute;top:-15px;right:-15px;width:70px;height:70px;background:rgba(255,255,255,0.05);border-radius:50%;"></div>
  <div style="position:absolute;bottom:-20px;left:-20px;width:85px;height:85px;background:rgba(255,255,255,0.05);border-radius:50%;"></div>
  <div style="color:rgba(255,255,255,0.6);font-size:28px;line-height:1;margin-bottom:4px;">"</div>
  <p style="color:#ffffff;font-size:16px;font-weight:bold;line-height:1.6;margin:0 0 8px;letter-spacing:1px;">{desc}</p>
  {f'<p style="color:rgba(255,255,255,0.7);font-size:12px;margin:0;">— {subtitle}</p>' if subtitle else ''}
  <div style="color:rgba(255,255,255,0.6);font-size:28px;line-height:1;margin-top:2px;">"</div>
</div>'''

    elif card_type == "data":
        # 数据卡：浅蓝背景+图标+核心数据文字（紧凑版）
        return f'''
<div style="background:linear-gradient(135deg,#EEF4FF,#E3EEFF);border:1px solid #C5D8FF;border-radius:10px;padding:14px 18px;margin:16px 0;">
  <div style="display:flex;align-items:center;margin-bottom:8px;">
    <span style="font-size:18px;margin-right:8px;">📊</span>
    <span style="color:#1565C0;font-size:14px;font-weight:bold;">数据参考</span>
  </div>
  <p style="color:#1A3A6E;font-size:15px;font-weight:bold;line-height:1.7;margin:0 0 6px;">{desc}</p>
  {f'<p style="color:#5577AA;font-size:12px;margin:0;line-height:1.6;">{subtitle}</p>' if subtitle else ''}
</div>'''

    elif card_type == "tip":
        # 提示卡：橙色背景+实用建议（紧凑版）
        return f'''
<div style="background:linear-gradient(135deg,#FFF8E1,#FFF3C4);border:1px solid #FFD54F;border-left:4px solid #FF8F00;border-radius:6px;padding:12px 16px;margin:16px 0;">
  <div style="display:flex;align-items:center;margin-bottom:6px;">
    <span style="font-size:15px;margin-right:6px;">💡</span>
    <span style="color:#E65100;font-size:13px;font-weight:bold;">实用贴士</span>
  </div>
  <p style="color:#5D4037;font-size:14px;line-height:1.7;margin:0;">{desc}</p>
  {f'<p style="color:#8D6E63;font-size:12px;margin:6px 0 0;line-height:1.6;">{subtitle}</p>' if subtitle else ''}
</div>'''

    else:
        # scene：场景卡（纯色渐变背景+文字，不使用外链图片，兼容微信渲染）
        # 根据 seed 选取不同的渐变色组合（5组暖/冷色调交替）
        gradients = [
            ("135deg,#1565C0,#0D47A1", "rgba(255,255,255,0.12)"),   # 深蓝
            ("135deg,#00695C,#004D40", "rgba(255,255,255,0.12)"),   # 深绿
            ("135deg,#4527A0,#311B92", "rgba(255,255,255,0.12)"),   # 深紫
            ("135deg,#BF360C,#870000", "rgba(255,255,255,0.10)"),   # 深红
            ("135deg,#1B5E20,#0A3D0A", "rgba(255,255,255,0.10)"),   # 墨绿
        ]
        grad_dir, overlay = gradients[img_seed_num % len(gradients)]
        return f'''
<div style="background:linear-gradient({grad_dir});border-radius:10px;margin:16px 0;padding:28px 22px 24px;position:relative;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.15);">
  <div style="position:absolute;top:-30px;right:-30px;width:110px;height:110px;background:{overlay};border-radius:50%;"></div>
  <div style="position:absolute;bottom:-25px;left:20px;width:80px;height:80px;background:{overlay};border-radius:50%;"></div>
  <div style="position:relative;">
    <div style="color:rgba(255,255,255,0.5);font-size:11px;letter-spacing:2px;margin-bottom:10px;text-transform:uppercase;">场景案例</div>
    <p style="color:#ffffff;font-size:16px;font-weight:bold;margin:0 0 8px;line-height:1.5;text-shadow:0 1px 3px rgba(0,0,0,0.3);">{desc}</p>
    {f'<p style="color:rgba(255,255,255,0.75);font-size:13px;margin:0;line-height:1.6;">{subtitle}</p>' if subtitle else ''}
  </div>
</div>'''


def _replace_image_markers(text: str) -> str:
    """
    将文本中的配图标记替换为丰富的图文卡片组件。
    支持格式：
      [配图:描述]                        → scene 类型（场景配图卡）
      [配图:scene:标题:副文本]           → 场景配图卡
      [配图:quote:金句文字:署名]         → 金句卡（蓝色背景+大字）
      [配图:data:核心数据:补充说明]      → 数据卡（蓝底）
      [配图:tip:建议内容:说明]           → 提示卡（橙色）
    """
    def _card(match):
        raw = match.group(1).strip()
        # 解析格式：类型:标题:副文本
        parts = [p.strip() for p in raw.split(':')]
        known_types = {"scene", "quote", "data", "tip"}
        if len(parts) >= 3 and parts[0] in known_types:
            card_type = parts[0]
            desc = parts[1]
            subtitle = parts[2] if len(parts) > 2 else ""
        elif len(parts) == 2 and parts[0] in known_types:
            card_type = parts[0]
            desc = parts[1]
            subtitle = ""
        else:
            # 仅有描述，默认 scene
            card_type = "scene"
            desc = raw
            subtitle = ""
        if not desc:
            return ""
        # scene 卡防重复：如果描述文字过短（≤12字）且缺少场景感词汇，
        # 视为直接复用了标题，用 _scene_caption 自动生成场景描述替换
        _scene_sense = ["现场", "咨询", "审核", "审批", "流程", "解读", "评估",
                        "指导", "团队", "服务", "银行", "大厅", "申请", "顾问"]
        if card_type == "scene" and len(desc) <= 12 and not any(w in desc for w in _scene_sense):
            desc, subtitle = _scene_caption(desc)

        # quote 卡防标题混入：如果内容像章节标题（含 Step/步骤/第X步/冒号分隔结构）
        # 说明 AI 误把章节标题填进了金句卡，自动替换为有力量的金融顾问金句
        _quote_fallbacks = [
            "专业的人做专业的事，贷款这件事，交给沪上银",
            "利率降了，关键是你能不能用上这个好政策",
            "每少一分利，都是你努力经营的回报",
            "专业顾问的价值，在于帮你少走弯路",
            "钱用对地方，才是真正的财务规划",
            "借得好，也是一种经营能力",
        ]
        import hashlib as _hs
        _is_step_title = (
            re.search(r'Step\s*\d', desc, re.IGNORECASE) or
            re.search(r'第[一二三四五六七八九十\d]+步', desc) or
            re.search(r'步骤\s*[：:一二三四五六七八九十\d]', desc) or
            (re.search(r'[：:]', desc) and len(desc) <= 16)
        )
        if card_type == "quote" and _is_step_title:
            _idx = int(_hs.md5(desc.encode()).hexdigest()[:4], 16) % len(_quote_fallbacks)
            desc = _quote_fallbacks[_idx]
            subtitle = subtitle or "沪上银 顾问"

        return _make_image_card(desc, card_type, subtitle)

    return re.sub(r'\[配图[：:](.+?)\]', _card, text)


def _text_to_paragraphs(text: str) -> str:
    """将多行文本转为HTML段落，同时处理 [配图:描述] 标记"""
    html_parts = []
    # 先处理配图标记，替换为 <img> 标签行
    text = _replace_image_markers(text)
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        # 配图 <img> 标签行：原样输出，不做 Markdown/高亮处理
        if line.startswith('<img'):
            html_parts.append(line)
            continue
        line = _md_inline(line)   # 先转 Markdown，再高亮数字
        line = _highlight_numbers(line)
        if line.startswith(('- ', '* ', '• ')):
            body = _md_inline(line[2:])
            body = _highlight_numbers(body)
            html_parts.append(
                f'<div style="display:flex;align-items:flex-start;margin:8px 0;">'
                f'<span style="color:#1565C0;margin-right:8px;flex-shrink:0;">▶</span>'
                f'<span style="font-size:15px;line-height:1.8;color:#333;">{body}</span>'
                f'</div>'
            )
        else:
            text = _md_inline(line)
            text = _highlight_numbers(text)
            html_parts.append(
                f'<p style="font-size:16px;line-height:1.9;margin:12px 0;color:#333;">{text}</p>'
            )
    return '\n'.join(html_parts)


def _clean_raw_content(content: str) -> str:
    """
    清洗爬虫原始内容：
    - Markdown图片 ![alt](url) → 保留为 [配图:alt描述]
    - 去除残留的K图/股票图片引用（无效链接）
    - 去除"文章来源：xxx"尾部
    - 合并多余空行
    """
    # Markdown 图片 → 配图标记（仅保留含http链接的）
    content = re.sub(r'!\[([^\]]*)\]\((https?://[^)]+)\)', r'[配图:\1]', content)
    # 去除无效图片引用（非http链接的图片、K图等）
    content = re.sub(r'!\[.*?\]\([^)]*\)', '', content)
    content = re.sub(r'!K图\s*\S+', '', content)
    content = re.sub(r'!\S*图\s*\S*', '', content)
    content = re.sub(r'\[([^\]]+)\]\(http[^\)]+\)', r'\1', content)
    content = re.sub(r'https?://\S+', '', content)
    content = re.sub(r'[（(]\s*文章来源[：:][^）)]*[）)]', '', content)
    content = re.sub(r'\(\s*\)', '', content)
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content.strip()


def process_article(article: dict) -> dict:
    """
    对文章进行AI增强处理
    article: {'title', 'content', 'source_name', ...}
    返回: 增强后的article dict（html_content字段含格式化后的HTML）
    """
    title = article.get("title", "")
    raw_content = article.get("content", "")
    source_name = article.get("source_name", "")

    content = _clean_raw_content(raw_content)
    article["title"] = optimize_title(title)
    article["summary"] = generate_summary(content)
    article["html_content"] = format_to_wechat_html(article["title"], content, source_name)

    return article


def format_original_article(article: dict) -> dict:
    """
    专门处理原创模板文章（write_with_template / _template_write_structured 生成的长文）。
    - 内容已经是完整 Markdown，无需再走 _enrich_content_with_ai 的四分区解析
    - 直接用 _render_original_html 生成与预览页一致的样式
    - 不走 optimize_title（模板标题已由AI精心生成，不必再改）
    """
    title = article.get("title", "")
    content = article.get("content", "")
    source_name = article.get("source_name", "沪上银原创")

    article["summary"] = generate_summary(content)
    article["html_content"] = _render_original_html(title, content, source_name, category=article.get("category", ""))
    return article


def _render_original_html(title: str, content: str, source_name: str = "", category: str = "") -> str:
    """
    将原创长文 Markdown 渲染为与 preview_cards.html 完全一致的排版：
    - 深蓝渐变标题横幅（与 _render_rich_html 一致）
    - 正文 h2/h3/列表/引用/段落全部渲染（与 _basic_format_rich 一致）
    - 每隔若干 h2 章节后自动插入 quote / data 配图卡
    - 文末加 tip 贴士卡 + 蓝色品牌落款
    - 如果内容里已有 [配图:xxx] 标记则直接渲染
    - 同时检查已有标记是否涵盖 scene/quote/data/tip 四种类型，缺失的自动补齐
    """
    today = datetime.now().strftime("%Y年%m月%d日")
    all_markers = re.findall(r'\[配图[：:](\w+)', content)
    has_scene = 'scene' in all_markers
    has_quote = 'quote' in all_markers
    has_data = 'data' in all_markers
    has_tip = 'tip' in all_markers
    has_markers = bool(all_markers)

    # ── 智能提取 data 卡文案（从文章中找含数字/金额/利率的句子）──
    def _extract_data_card_lines(text, max_chars=55):
        """从正文中提取含有贷款相关数字的短句，优先利率/金额/年限"""
        # 先清理 HTML 标签和 Markdown 标记（content 可能已被渲染过或仍是 Markdown）
        clean_text = re.sub(r'<[^>]+>', '', text)
        clean_text = re.sub(r'\*\*(.+?)\*\*', r'\1', clean_text)  # 去掉 **粗体**
        lines = clean_text.replace('\r', '').split('\n')
        candidates = []
        seen = set()  # 去重
        # 优先级关键词（越靠前越优先）
        priority_kw = ['利率', '月供', '年化', '利息', '放款', '额度',
                       '万元', '万块', '万', '%', '期限', '年']
        for line in lines:
            line = line.strip()
            # 跳过标题行、引用块、分隔线、空行、短行
            if (not line or line.startswith('#') or line.startswith('>') or
                    line.startswith('-') or line.startswith('*') or
                    line.startswith('▶') or line.startswith('①') or
                    line.startswith('Step') or line.startswith('[') or
                    line.startswith('---') or line.startswith('**案例') or
                    len(line) < 10):
                continue
            # 跳过案例相关行（避免 data 卡与后面的案例段落重复）
            # 匹配：案例标题行、含具体人物/场景的叙述行（暗示是案例故事而非数据）
            if re.search(r'案例|客户.*故事|真实.*案例|案例一|案例二|案例三', line):
                continue
            # 跳过含具体人物+地点/行业的叙述句（通常是案例故事而非数据）
            if re.search(r'王总|张总|李总|刘总|陈总|赵总|周总|吴总|孙总|杨总|黄总', line):
                continue
            if re.search(r'老板.*说|某.*企业|老板.*在|在.*区开了一家|在.*区经营', line):
                continue
            # 必须含数字
            if not re.search(r'[\d％%一二三四五六七八九十百千万亿]', line):
                continue
            # 跳过标题横幅（含品牌名+日期的组合）
            if _BRAND in line and ('年' in line and re.search(r'\d{4}年', line)):
                continue
            # 截取合适的长度
            if len(line) > max_chars:
                # 尝试在标点处断句
                line = re.split(r'[。！？；\n]', line)[0].strip()
            if len(line) > max_chars:
                line = line[:max_chars - 1] + '…'
            if 10 <= len(line) <= max_chars:
                # 去重
                if line in seen:
                    continue
                seen.add(line)
                # 计算优先级分数
                score = sum(3 if i < 4 else 1 for i, kw in enumerate(priority_kw) if kw in line)
                # 含有阿拉伯数字加分
                if re.search(r'\d+', line):
                    score += 2
                if score > 0:
                    candidates.append((score, line))
        # 按分数降序排列
        candidates.sort(key=lambda x: -x[0])
        return candidates

    data_candidates = _extract_data_card_lines(content)

    parts = []

    # ── 标题横幅 ──────────────────────────────────────────────
    parts.append(
        f'<div style="background:linear-gradient(135deg,#0D47A1,#1565C0,#1976D2);border-radius:12px;'
        f'padding:24px 22px 20px;margin-bottom:16px;position:relative;overflow:hidden;">'
        f'<div style="position:absolute;top:-30px;right:-30px;width:120px;height:120px;'
        f'background:rgba(255,255,255,0.06);border-radius:50%;"></div>'
        f'<div style="position:absolute;bottom:-20px;left:40%;width:80px;height:80px;'
        f'background:rgba(255,255,255,0.04);border-radius:50%;"></div>'
        f'<div style="color:rgba(255,255,255,0.65);font-size:11px;letter-spacing:2px;margin-bottom:10px;">'
        f'沪上银 · 上海专业贷款顾问</div>'
        f'<h1 style="color:#fff;font-size:20px;font-weight:bold;margin:0 0 10px;line-height:1.5;">{title}</h1>'
        f'<div style="color:rgba(255,255,255,0.55);font-size:12px;">{today}</div>'
        f'</div>'
    )

    # ── 识别并渲染「简单说」摘要块（AI 写的 > **📌 简单说** 引用块）──
    lines_raw = content.split('\n')
    jiandan_lines_r = []
    rest_lines_r = []
    in_js = False
    js_done = False
    for _ln in lines_raw:
        _s = _ln.strip()
        if not js_done:
            if _s.startswith('>') and '简单说' in _s:
                in_js = True
                continue
            elif in_js and _s.startswith('>'):
                jiandan_lines_r.append(_s.lstrip('>').strip())
                continue
            elif in_js and not _s.startswith('>') and _s:
                in_js = False
                js_done = True
                rest_lines_r.append(_ln)
            else:
                rest_lines_r.append(_ln)
        else:
            rest_lines_r.append(_ln)

    if jiandan_lines_r:
        intro_text_r = ' '.join(jiandan_lines_r)
        intro_text_r = re.sub(r'\*\*', '', intro_text_r)
        # 清理 AI 误输出的括号提示文字，如（核心摘要，3句话）等
        intro_text_r = re.sub(r'^[（(][^）)]{0,20}[）)]\s*', '', intro_text_r).strip()
        parts.append(f'''
<div style="background:#EEF4FF;border-left:4px solid #1565C0;border-radius:6px;padding:14px 16px;margin:16px 0;">
  <div style="color:#1565C0;font-weight:bold;font-size:13px;margin-bottom:6px;">📌 简单说</div>
  <p style="color:#555;font-size:15px;line-height:1.8;margin:0;">{intro_text_r}</p>
</div>''')
        content_for_render = '\n'.join(rest_lines_r)
    else:
        content_for_render = content

    # ── 无 scene 标记时，在开头自动加 scene 卡（场景描述，不复用标题）──
    if not has_scene:
        _sc_cap, _sc_sub = _scene_caption(title)
        parts.append(_make_image_card(_sc_cap, "scene", _sc_sub))

    # ── 正文逐行渲染 ──────────────────────────────────────────
    lines = content_for_render.split('\n')
    h2_count = 0          # h2 章节计数，用于自动插图
    quote_inserted = False  # 中间金句卡只插一次
    data_inserted = False   # 数据卡只插一次
    total_h2 = sum(1 for l in lines if l.strip().startswith('## '))
    mid_h2 = max(total_h2 // 2, 1)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 配图标记 → 直接渲染
        if re.search(r'\[配图[：:]', stripped):
            parts.append(_replace_image_markers(stripped))
            continue

        # 标题行
        if stripped.startswith('## '):
            h2_count += 1
            heading_text = stripped[3:]
            # 清理 AI 误写的括号提示文字，如「简单说（核心摘要，3句话）」→「简单说」
            heading_text = re.sub(r'\s*[（(][^）)]{0,30}[）)]\s*$', '', heading_text).strip()
            # h2 去重：如果 h2 标题跟文章标题关键词高度重复，自动替换为更有差异化的表达
            # 提取文章标题的核心词（去掉常见后缀/前缀）
            _title_core = re.sub(r'[\s|·\-—_|沪上银贷款顾问攻略指南解读分析详解全面深度一二三四五六七八九十]+', '', title)
            if len(_title_core) >= 2:
                _h2_core = re.sub(r'[\s|·\-—_的了一是]+', '', heading_text)
                # 计算 h2 中包含文章标题核心词的数量
                _overlap = sum(1 for c in _title_core if c in _h2_core)
                _overlap_ratio = _overlap / max(len(_title_core), 1)
                if _overlap_ratio > 0.6 and len(heading_text) > 4:
                    # 标题高度重复，替换为预设的有差异化标题
                    _h2_alternatives = [
                        "这些关键点，90%的人都忽略了",
                        "不看这篇，你的申请可能白跑一趟",
                        "银行不会主动告诉你的那些事",
                        "为什么有人一次过，有人被拒三次？",
                        "读懂这些，少走一半弯路",
                    ]
                    import hashlib as _hh
                    _alt_idx = int(_hh.md5(heading_text.encode()).hexdigest()[:4], 16) % len(_h2_alternatives)
                    heading_text = _h2_alternatives[_alt_idx]
            # 自动补缺失的配图类型
            if total_h2 >= 3:
                if h2_count == mid_h2 and h2_count > 1 and not has_quote and not quote_inserted:
                    # Quote 卡固定使用预设金句（不从正文取内容），彻底避免与正文重复
                    # 用文章标题的 hash 值选句，保证同一篇文章每次用同一句
                    _quote_pool = [
                        "专业的人做专业的事，贷款这件事，交给沪上银",
                        "利率降了，关键是你能不能用上这个好政策",
                        "每少一分利，都是你努力经营的回报",
                        "专业顾问的价值，在于帮你少走弯路",
                        "钱用对地方，才是真正的财务规划",
                        "借得好，也是一种经营能力",
                        "找对人，少走弯路——这才是贷款最值钱的地方",
                        "贷款不是赌运气，是靠专业和经验",
                        "每一笔融资背后，都需要一个懂你的顾问",
                        "资金周转顺了，生意才能跑起来",
                    ]
                    import hashlib as _hq
                    _qi = int(_hq.md5(title.encode()).hexdigest()[:4], 16) % len(_quote_pool)
                    recent_para = _quote_pool[_qi]
                    parts.append(_make_image_card(recent_para, "quote", f"— {_BRAND}"))
                    quote_inserted = True
                if h2_count == mid_h2 + 1 and not has_data and not data_inserted:
                    # Data 卡使用预设内容池（不从正文取内容），彻底避免与正文重复
                    # 用文章标题的 hash 选一组，保证同一篇文章每次用同一组
                    _data_pool = [
                        ("上海经营贷利率最低 3.1% 起", "额度最高 2000万，最快当天放款"),
                        ("抵押经营贷利率 3.1%~4.5%", "额度 50万~3000万，还款方式灵活"),
                        ("信用贷额度 10万~100万", "无需抵押，凭流水和征信即可申请"),
                        ("企业税贷额度最高 500万", "按纳税评级授信，利率低至 3.6%"),
                        ("房产抵押贷利率 3.1% 起", "住宅/商铺/办公均可，评估价 7 成放款"),
                        ("装修贷利率低至 3.5%", "额度最高 100万，最长 10 年分期"),
                        ("商户流水贷额度 10万~200万", "月流水 5万以上即可申请，当天审批"),
                        ("科技型企业专享贷", "利率优惠 30bps，最高额度 1000万"),
                    ]
                    import hashlib as _hd
                    _di = int(_hd.md5((title + "data").encode()).hexdigest()[:4], 16) % len(_data_pool)
                    data_title, data_sub = _data_pool[_di]
                    parts.append(_make_image_card(data_title, "data", data_sub))
                    data_inserted = True

            parts.append(
                f'<h2 style="color:#1565C0;font-size:19px;font-weight:bold;margin:32px 0 14px;'
                f'padding:10px 16px;background:linear-gradient(90deg,#EEF4FF,transparent);'
                f'border-left:4px solid #1565C0;border-radius:0 6px 6px 0;">{heading_text}</h2>'
            )
            continue

        if stripped.startswith('### '):
            parts.append(
                f'<h3 style="color:#1565C0;font-size:16px;font-weight:bold;margin:22px 0 10px;'
                f'padding-bottom:5px;border-bottom:1px dashed #C5D8FF;">{stripped[4:]}</h3>'
            )
            continue

        if stripped.startswith('# '):
            parts.append(
                f'<h1 style="color:#1565C0;font-size:21px;font-weight:bold;margin:28px 0 12px;">{stripped[2:]}</h1>'
            )
            continue

        # 引用块 > 用作客户证言
        if stripped.startswith('>'):
            quote_text = _md_inline(stripped.lstrip('> ').strip())
            parts.append(
                f'<blockquote style="background:linear-gradient(135deg,#F8F9FA,#EEF4FF);'
                f'border-left:3px solid #1565C0;border-radius:0 8px 8px 0;'
                f'padding:12px 16px;margin:16px 0 8px;color:#555;font-size:14px;line-height:1.8;'
                f'font-style:italic;">{quote_text}</blockquote>'
            )
            continue

        # 无序列表
        if re.match(r'^[-*•]\s', stripped):
            text = _md_inline(stripped[2:])
            text = _highlight_numbers(text)
            parts.append(
                f'<div style="display:flex;align-items:flex-start;margin:8px 0;padding-left:4px;">'
                f'<span style="color:#1565C0;margin-right:10px;flex-shrink:0;font-size:16px;line-height:1.6;">▶</span>'
                f'<span style="font-size:15px;line-height:1.8;color:#333;">{text}</span>'
                f'</div>'
            )
            continue

        # 有序列表
        if re.match(r'^\d+[.)]\s', stripped):
            text = _md_inline(stripped)
            text = _highlight_numbers(text)
            parts.append(
                f'<p style="font-size:15px;line-height:1.8;margin:8px 0;padding-left:8px;color:#333;">{text}</p>'
            )
            continue

        # Step / 数字开头小标题（如 **Step 1：xxx**）
        if re.match(r'^\*\*Step\s*\d', stripped) or re.match(r'^\*\*[①②③④⑤]', stripped):
            text = _md_inline(stripped)
            text = _highlight_numbers(text)
            parts.append(
                f'<p style="font-size:15px;font-weight:bold;line-height:1.8;margin:16px 0 6px;'
                f'color:#1565C0;">{text}</p>'
            )
            continue

        # 普通段落
        text = _md_inline(stripped)
        text = _highlight_numbers(text)
        parts.append(
            f'<p style="font-size:16px;line-height:1.9;margin:12px 0;color:#333;">{text}</p>'
        )

    # ── 结尾无 tip 标记时自动加贴士卡 ──────────────────────
    if not has_tip:
        parts.append(_make_image_card(
            "有贷款问题？欢迎找沪上银顾问免费咨询，帮你算清楚再决定",
            "tip",
            "上海本地团队 · 无中介费 · 专业评估"
        ))

    # ── 工单表单（服务类文章优先使用工单系统）────────────────────────
    # 根据文章标题判断是否需要嵌入工单表单
    work_order_html = _get_work_order_form_html(title, category)
    if work_order_html:
        parts.append(work_order_html)
    else:
        #  fallback：留资表单（获客/方案匹配类文章）
        form_html = _get_lead_form_html(source_name, title)
        if form_html:
            parts.append(form_html)

    # ── 品牌落款 ──────────────────────────────────────────────
    parts.append(f'''
<div style="margin-top:36px;padding:18px 22px;background:linear-gradient(135deg,#0D47A1,#1565C0);
border-radius:12px;display:flex;justify-content:space-between;align-items:center;">
  <div>
    <div style="color:#fff;font-size:14px;font-weight:bold;">{_BRAND} · 上海专业贷款顾问</div>
    <div style="color:rgba(255,255,255,0.65);font-size:12px;margin-top:4px;">搞不清楚贷款的，来找我们聊聊</div>
  </div>
  <span style="color:rgba(255,255,255,0.55);font-size:12px;">{today}</span>
</div>''')

    # ── 后处理：去除重复的 Step 块 ─────────────────────────────────────
    # AI 可能生成两套相同的 Step 1/2/3（不同 h2 下内容完全一致），自动去重
    # 策略：收集每个 h2 章节中的 Step 标题序列，如果两个章节的 Step 序列完全相同，删除后一个
    _dedup_parts = []
    _section_step_seqs = {}  # "Step1标题|||Step2标题|||..." -> index in _dedup_parts
    _current_h2 = ""
    _current_steps = []
    _current_h2_start = 0

    for part in parts:
        _h2_match = re.match(r'<h2[^>]*>(.+)</h2>', part)
        if _h2_match:
            # Save previous section's step sequence if any
            if _current_h2 and _current_steps:
                _seq_key = '|||'.join(_current_steps)
                if _seq_key in _section_step_seqs:
                    # Duplicate found - remove the previous h2 section
                    _dup_start = _section_step_seqs[_seq_key]
                    _dedup_parts[_dup_start:_current_h2_start] = []
                    # Keep the current one (later occurrence is usually more detailed)
                else:
                    _section_step_seqs[_seq_key] = _current_h2_start
            _current_h2 = _h2_match.group(1)
            _current_steps = []
            _current_h2_start = len(_dedup_parts)
            _dedup_parts.append(part)
        else:
            # Check if this part contains a Step title
            _step_m = re.search(r'<strong>Step\s*\d[^<]*</strong>', part)
            if _step_m:
                _current_steps.append(_step_m.group())
            _dedup_parts.append(part)

    # Handle last section
    if _current_h2 and _current_steps:
        _seq_key = '|||'.join(_current_steps)
        if _seq_key in _section_step_seqs:
            _dup_start = _section_step_seqs[_seq_key]
            _dedup_parts[_dup_start:_current_h2_start] = []

    parts = _dedup_parts

    body_html = '\n'.join(parts)
    return (
        f'<div style="font-family:-apple-system,BlinkMacSystemFont,\'PingFang SC\','
        f'\'Hiragino Sans GB\',\'Microsoft YaHei\',sans-serif;'
        f'max-width:100%;box-sizing:border-box;padding:0 4px;">\n'
        f'{body_html}\n</div>'
    )


def _get_lead_form_html(source_name: str, title: str) -> str:
    """
    根据文章来源/标题判断是否需要嵌入留资表单
    返回表单HTML或空字符串
    """
    # 判断是否为获客/方案匹配类文章
    # source_name 包含 "沪上银原创" 且标题或标签匹配特定关键词
    is_leads_article = False
    form_type = "credit_diagnosis"  # 默认表单类型
    
    # 通过标题关键词判断
    leads_keywords = ["获客", "方案匹配", "贷款方案", "免费咨询", "额度", "征信诊断"]
    for kw in leads_keywords:
        if kw in title:
            is_leads_article = True
            if "额度" in title or "测算" in title:
                form_type = "quota_calc"
            break
    
    # 通过 source_name 判断
    if "沪上银原创" in source_name or "沪上银" in source_name:
        is_leads_article = True
    
    if not is_leads_article:
        return ""
    
    # 返回对应的表单HTML
    if form_type == "quota_calc":
        return '''<div class="lead-form-container" style="background:linear-gradient(135deg,#1e40af 0%,#3b82f6 100%);border-radius:12px;padding:24px;margin:24px 0;color:white;">
    <h3 style="margin-bottom:12px;">💰 免费额度测算</h3>
    <p style="opacity:0.9;margin-bottom:20px;">1分钟填写，快速了解您可申请的贷款额度</p>
    <form class="lead-form" data-form-type="quota_calc" onsubmit="return submitLeadForm(this);">
        <div style="margin-bottom:14px;">
            <input type="text" name="name" placeholder="您的姓名" required style="width:100%;padding:12px 16px;border:none;border-radius:8px;box-sizing:border-box;color:#333;">
        </div>
        <div style="margin-bottom:14px;">
            <input type="tel" name="phone" placeholder="手机号" required pattern="1[3-9]\\d{9}" style="width:100%;padding:12px 16px;border:none;border-radius:8px;box-sizing:border-box;color:#333;">
        </div>
        <div style="margin-bottom:14px;">
            <input type="text" name="loan_amount" placeholder="期望贷款金额（如：100万）" required style="width:100%;padding:12px 16px;border:none;border-radius:8px;box-sizing:border-box;color:#333;">
        </div>
        <div style="margin-bottom:18px;">
            <select name="credit_status" required style="width:100%;padding:12px 16px;border:none;border-radius:8px;box-sizing:border-box;color:#333;">
                <option value="">当前征信状况</option>
                <option value="无逾期">无逾期</option>
                <option value="1-2次逾期">1-2次逾期</option>
                <option value="3次以上逾期">3次以上逾期</option>
                <option value="有当前逾期">有当前逾期</option>
            </select>
        </div>
        <button type="submit" style="width:100%;background:#f59e0b;color:#1e3a5f;padding:14px 24px;border:none;border-radius:8px;font-size:16px;cursor:pointer;font-weight:600;">立即测算额度</button>
    </form>
</div>
<script>
function submitLeadForm(form) {
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    data.source = window.location.href;
    data.article_title = "''' + title + '''";
    
    fetch('/api/leads/submit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    }).then(r => r.json()).then(res => {
        if (res.ok) {
            alert('提交成功！顾问将在24小时内联系您');
            form.reset();
        } else {
            alert('提交失败：' + (res.msg || '请稍后重试'));
        }
    }).catch(e => {
        alert('提交失败，请稍后重试');
    });
    return false;
}
</script>'''
    else:
        # 默认征信诊断表单
        return '''<div class="lead-form-container" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:24px;margin:24px 0;">
    <h3 style="color:#1e40af;margin-bottom:16px;">📋 免费征信诊断</h3>
    <p style="color:#64748b;margin-bottom:20px;">填写以下信息，专业顾问将在24小时内为您评估贷款可行性</p>
    <form class="lead-form" data-form-type="credit_diagnosis" onsubmit="return submitLeadForm(this);">
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;">姓名 *</label>
            <input type="text" name="name" required style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;">手机号 *</label>
            <input type="tel" name="phone" required pattern="1[3-9]\\d{9}" style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;">意向贷款金额 *</label>
            <select name="loan_amount" required style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;">
                <option value="">请选择</option>
                <option value="30万以下">30万以下</option>
                <option value="30-100万">30-100万</option>
                <option value="100-300万">100-300万</option>
                <option value="300万以上">300万以上</option>
            </select>
        </div>
        <div style="margin-bottom:20px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;">征信情况 *</label>
            <select name="credit_status" required style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;">
                <option value="">请选择</option>
                <option value="征信良好">征信良好</option>
                <option value="有少量逾期">有少量逾期</option>
                <option value="逾期较多">逾期较多</option>
                <option value="不清楚">不清楚</option>
            </select>
        </div>
        <button type="submit" style="width:100%;background:#1e40af;color:white;padding:12px 24px;border:none;border-radius:8px;font-size:16px;cursor:pointer;font-weight:500;">提交申请</button>
        <p style="color:#94a3b8;font-size:12px;margin-top:12px;text-align:center;">信息严格保密，仅用于贷款评估</p>
    </form>
</div>
<script>
function submitLeadForm(form) {
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    data.source = window.location.href;
    data.article_title = "''' + title + '''";
    
    fetch('/api/leads/submit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    }).then(r => r.json()).then(res => {
        if (res.ok) {
            alert('提交成功！顾问将在24小时内联系您');
            form.reset();
        } else {
            alert('提交失败：' + (res.msg || '请稍后重试'));
        }
    }).catch(e => {
        alert('提交失败，请稍后重试');
    });
    return false;
}
</script>'''


def _get_work_order_form_html(title: str, category: str = "") -> str:
    """
    根据文章标题/分类判断是否需要嵌入工单表单
    返回工单表单HTML或空字符串
    """
    # 工单类型关键词匹配
    order_types = {
        "loan_match": {
            "keywords": ["贷款方案", "方案匹配", "贷款选择", "怎么选", "哪个银行"],
            "label": "贷款方案匹配",
            "color": "#0ea5e9",
            "bg": "#f0f9ff"
        },
        "finance_plan": {
            "keywords": ["融资规划", "企业融资", "融资方案", "资金周转"],
            "label": "融资规划",
            "color": "#8b5cf6",
            "bg": "#f5f3ff"
        },
        "enterprise_analysis": {
            "keywords": ["经营分析", "企业经营", "现金流", "营收", "成本"],
            "label": "企业经营分析",
            "color": "#10b981",
            "bg": "#ecfdf5"
        }
    }
    
    matched_type = None
    for order_type, config in order_types.items():
        for kw in config["keywords"]:
            if kw in title:
                matched_type = order_type
                break
        if matched_type:
            break
    
    # 通过分类匹配
    if not matched_type and category:
        category_map = {
            "service": "loan_match",
            "finance": "finance_plan",
            "enterprise": "enterprise_analysis"
        }
        matched_type = category_map.get(category)
    
    if not matched_type:
        return ""
    
    config = order_types[matched_type]
    
    # 根据类型返回对应表单
    if matched_type == "loan_match":
        return _get_loan_match_form_html(config)
    elif matched_type == "finance_plan":
        return _get_finance_plan_form_html(config)
    else:
        return _get_enterprise_analysis_form_html(config)


def _get_loan_match_form_html(config) -> str:
    """贷款方案匹配表单"""
    return f'''<div class="work-order-form" style="background:{config['bg']};border:2px solid {config['color']};border-radius:12px;padding:24px;margin:20px 0;">
    <h3 style="color:{config['color']};margin-bottom:8px;">📝 贷款方案匹配</h3>
    <p style="color:#64748b;margin-bottom:20px;font-size:14px;">填写需求，专业顾问为您定制最优贷款方案</p>
    <form onsubmit="return submitWorkOrderForm(this, 'loan_match');">
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">姓名 *</label>
            <input type="text" name="name" required placeholder="请输入您的姓名" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">联系方式 *</label>
            <input type="tel" name="phone" required pattern="1[3-9]\\d{{9}}" placeholder="请输入手机号" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">贷款需求 *</label>
            <select name="loan_amount" required style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;background:white;">
                <option value="">请选择贷款金额</option>
                <option value="30万以下">30万以下</option>
                <option value="30-100万">30-100万</option>
                <option value="100-300万">100-300万</option>
                <option value="300万以上">300万以上</option>
            </select>
        </div>
        <div style="margin-bottom:20px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">详细需求 *</label>
            <textarea name="description" required rows="4" placeholder="请描述您的贷款用途、还款能力、征信情况等" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;resize:vertical;"></textarea>
        </div>
        <button type="submit" style="width:100%;background:{config['color']};color:white;padding:14px;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;">提交申请</button>
        <p style="color:#94a3b8;font-size:12px;margin-top:12px;text-align:center;">信息严格保密，仅用于方案匹配</p>
    </form>
</div>'''


def _get_finance_plan_form_html(config) -> str:
    """融资规划表单"""
    return f'''<div class="work-order-form" style="background:{config['bg']};border:2px solid {config['color']};border-radius:12px;padding:24px;margin:20px 0;">
    <h3 style="color:{config['color']};margin-bottom:8px;">📊 融资规划咨询</h3>
    <p style="color:#64748b;margin-bottom:20px;font-size:14px;">为企业量身定制融资方案，降低融资成本</p>
    <form onsubmit="return submitWorkOrderForm(this, 'finance_plan');">
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">姓名 *</label>
            <input type="text" name="name" required placeholder="请输入您的姓名" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">联系方式 *</label>
            <input type="tel" name="phone" required pattern="1[3-9]\\d{{9}}" placeholder="请输入手机号" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">企业类型 *</label>
            <select name="company_type" required style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;background:white;">
                <option value="">请选择企业类型</option>
                <option value="个体工商户">个体工商户</option>
                <option value="小微企业">小微企业</option>
                <option value="中型企业">中型企业</option>
                <option value="其他">其他</option>
            </select>
        </div>
        <div style="margin-bottom:20px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">融资需求 *</label>
            <textarea name="description" required rows="4" placeholder="请描述您的企业情况、融资用途、期望额度、还款来源等" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;resize:vertical;"></textarea>
        </div>
        <button type="submit" style="width:100%;background:{config['color']};color:white;padding:14px;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;">获取融资方案</button>
        <p style="color:#94a3b8;font-size:12px;margin-top:12px;text-align:center;">专业顾问将在2小时内与您联系</p>
    </form>
</div>'''


def _get_enterprise_analysis_form_html(config) -> str:
    """企业经营分析表单"""
    return f'''<div class="work-order-form" style="background:{config['bg']};border:2px solid {config['color']};border-radius:12px;padding:24px;margin:20px 0;">
    <h3 style="color:{config['color']};margin-bottom:8px;">📈 企业经营分析</h3>
    <p style="color:#64748b;margin-bottom:20px;font-size:14px;">深度分析企业经营状况，提供优化建议与资金解决方案</p>
    <form onsubmit="return submitWorkOrderForm(this, 'enterprise_analysis');">
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">姓名 *</label>
            <input type="text" name="name" required placeholder="请输入您的姓名" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">联系方式 *</label>
            <input type="tel" name="phone" required pattern="1[3-9]\\d{{9}}" placeholder="请输入手机号" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:16px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">所属行业 *</label>
            <input type="text" name="industry" required placeholder="如：餐饮、制造、零售、科技等" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;">
        </div>
        <div style="margin-bottom:20px;">
            <label style="display:block;color:#374151;font-weight:500;margin-bottom:6px;font-size:14px;">经营情况 *</label>
            <textarea name="description" required rows="4" placeholder="请描述您的经营现状、遇到的问题（现金流、成本、营收等）、资金需求等" style="width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;box-sizing:border-box;font-size:14px;resize:vertical;"></textarea>
        </div>
        <button type="submit" style="width:100%;background:{config['color']};color:white;padding:14px;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;">申请经营分析</button>
        <p style="color:#94a3b8;font-size:12px;margin-top:12px;text-align:center;">专业分析师将在24小时内出具诊断报告</p>
    </form>
</div>'''









