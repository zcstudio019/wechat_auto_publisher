"""公众号正文留资入口卡片适配器。

后台预览可以继续保留真实表单，但微信公众号正文不支持可靠的 form/input
交互。本模块只在发布前把真实表单块替换成静态咨询入口卡片，不修改数据库
和文章原始内容。
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from config import WECHAT_LEAD_FORM_URL


CARD_STYLE = (
    "margin:20px 0;padding:18px;background-color:#eef8f3;"
    "border:1px solid #18b57b;border-radius:10px;"
)
TITLE_STYLE = (
    "margin:0 0 10px 0;font-size:20px;font-weight:bold;"
    "color:#0a8f62;line-height:1.5;"
)
DESC_STYLE = "margin:0 0 14px 0;font-size:15px;line-height:1.8;color:#555;"
TIP_STYLE = "margin:0 0 10px 0;font-size:14px;line-height:1.7;color:#333;"
ACTION_WRAP_STYLE = "margin:14px 0 0 0;"
ACTION_STYLE = (
    "display:inline-block;padding:10px 18px;background-color:#18b57b;"
    "color:#ffffff;text-decoration:none;border-radius:6px;font-size:14px;"
)


def _safe_text(text: str) -> str:
    """清理文本两侧空白，避免卡片文案出现多余换行。"""
    return (text or "").strip()


def _detect_card_copy(form, container) -> dict[str, str]:
    """根据原表单内容推断公众号卡片文案。"""
    form_type = _safe_text(form.get("data-form-type", "")) if form else ""
    text = _safe_text(container.get_text(" ", strip=True) if container else "")

    if form_type == "quota_calc" or "额度" in text or "测算" in text:
        return {
            "title": "免费融资评估",
            "description": "快速了解企业可申请额度与适合的融资方向。",
            "tip": "如需一对一评估，请点击下方入口联系顾问。",
            "action_text": "免费评估",
        }

    if "方案匹配" in text or "贷款方案" in text or "方案咨询" in text or "经营贷" in text:
        return {
            "title": "经营贷方案咨询",
            "description": "结合企业情况，匹配更合适的银行贷款与融资方案。",
            "tip": "有贷款问题？欢迎咨询沪上银顾问免费评估。",
            "action_text": "获取方案",
        }

    if "经营分析" in text or "企业经营" in text:
        return {
            "title": "企业经营分析",
            "description": "深度分析企业经营状况，提供优化建议与资金解决方案。",
            "tip": "如需一对一咨询，请点击下方入口联系我们。",
            "action_text": "立即咨询",
        }

    return {
        "title": "一对一贷款咨询",
        "description": "上海本地团队，结合征信、流水与经营情况提供专业评估。",
        "tip": "如需进一步了解方案，请点击下方入口联系顾问。",
        "action_text": "联系顾问",
    }


def _find_replace_target(form):
    """优先替换完整表单容器，避免残留字段说明造成公众号阅读干扰。"""
    for parent in form.parents:
        class_text = " ".join(parent.get("class", []))
        if "lead-form-container" in class_text or "work-order-form" in class_text:
            return parent
        if parent.name in {"body", "html"}:
            break
    return form


def _build_lead_card(soup: BeautifulSoup, copy: dict[str, str], lead_url: str) -> object:
    """构建微信公众号兼容的静态留资入口卡片。"""
    section = soup.new_tag("section")
    section["style"] = CARD_STYLE

    title = soup.new_tag("p")
    title["style"] = TITLE_STYLE
    title.string = copy["title"]
    section.append(title)

    description = soup.new_tag("p")
    description["style"] = DESC_STYLE
    description.string = copy["description"]
    section.append(description)

    tip = soup.new_tag("p")
    tip["style"] = TIP_STYLE
    tip.string = copy["tip"]
    section.append(tip)

    action_wrap = soup.new_tag("p")
    action_wrap["style"] = ACTION_WRAP_STYLE
    if lead_url:
        # 有咨询链接时输出可点击入口，真实跳转地址统一来自配置。
        action = soup.new_tag("a", href=lead_url)
    else:
        # 没有咨询链接时退化成静态按钮样式，避免正文里出现无效表单。
        action = soup.new_tag("span")
    action["style"] = ACTION_STYLE
    action.string = copy["action_text"]
    action_wrap.append(action)
    section.append(action_wrap)

    if not lead_url:
        fallback = soup.new_tag("p")
        fallback["style"] = "margin:10px 0 0 0;font-size:13px;line-height:1.7;color:#666;"
        fallback.string = "当前未配置咨询链接，请通过公众号菜单或后台联系方式联系我们。"
        section.append(fallback)

    return section


def adapt_lead_form_to_wechat_card(html_content: str, lead_url: str | None = None) -> str:
    """把真实留资表单替换为公众号兼容留资入口卡片。"""
    if not html_content or not html_content.strip():
        return ""

    soup = BeautifulSoup(html_content, "html.parser")
    # 未配置公网落地页时，先使用系统内置公开留资页，保证后台预览可点击。
    configured_url = _safe_text(WECHAT_LEAD_FORM_URL if lead_url is None else lead_url) or "/lead-form"

    forms = list(soup.find_all("form"))
    for form in forms:
        target = _find_replace_target(form)
        copy = _detect_card_copy(form, target)
        target.replace_with(_build_lead_card(soup, copy, configured_url))

    # 公众号正文不支持脚本和真实表单控件；即使控件不在 form 内，也统一清理。
    for tag in soup.find_all(["script", "form", "input", "textarea", "select", "button"]):
        tag.decompose()

    body = soup.body if soup.body else soup
    return "".join(str(child) for child in body.children).strip()
