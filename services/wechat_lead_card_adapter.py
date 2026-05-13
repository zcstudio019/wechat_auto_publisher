"""公众号正文留资入口卡片适配器。

后台预览可以继续保留真实表单，但微信公众号正文不支持可靠的 form/input
交互。本模块只在发布前把真实表单块替换成静态咨询入口卡片，不修改数据库
和文章原始内容。
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from config import WECHAT_LEAD_FORM_URL


CARD_STYLE = (
    "margin:42px 0 24px;padding:18px 20px;background-color:#F7FAFD;"
    "border:1px solid #E2ECF6;border-radius:16px;"
)
TITLE_STYLE = (
    "margin:0 0 10px 0;font-size:18px;font-weight:bold;"
    "color:#17324D;line-height:1.5;"
)
DESC_STYLE = "margin:0 0 10px 0;font-size:14px;line-height:1.85;color:#516173;"
TIP_STYLE = "margin:0 0 10px 0;font-size:13px;line-height:1.8;color:#66758A;"
ACTION_WRAP_STYLE = "margin:14px 0 0 0;"
ACTION_STYLE = (
    "display:inline-block;padding:9px 16px;background-color:#EDF4FB;"
    "border:1px solid #C9D9EA;color:#24527A;text-decoration:none;"
    "border-radius:999px;font-size:13px;font-weight:bold;"
)
LEGACY_CTA_MARKERS = (
    "场景案例",
    "上海企业融资规划咨询",
    "科学规划",
    "多渠道融资",
    "降低风险",
)


def _safe_text(text: str) -> str:
    """清理文本两侧空白，避免卡片文案出现多余换行。"""
    return (text or "").strip()


def _is_legacy_cta_card(tag) -> bool:
    text = _safe_text(tag.get_text(" ", strip=True) if tag else "")
    style_text = (tag.get("style") or "").lower() if tag else ""
    has_marker = any(marker in text for marker in LEGACY_CTA_MARKERS)
    has_green_style = "#0f5d2c" in style_text or "green" in style_text
    return has_marker or has_green_style


def _remove_legacy_cta_cards(soup: BeautifulSoup) -> None:
    for tag in list(soup.find_all(["section", "div"])):
        if _is_legacy_cta_card(tag):
            tag.decompose()


def _refine_card_copy(copy: dict[str, str]) -> dict[str, str]:
    """Downgrade CTA copy into softer editorial guidance."""
    action_text = copy.get("action_text", "")
    title = copy.get("title", "")

    if "额度" in title or "评估" in title:
        return {
            **copy,
            "description": "结合企业经营情况，梳理更适合的资金安排与评估方向。",
            "tip": "如需继续了解，可查看适合自身阶段的资金方案建议。",
            "action_text": "了解适合自己的资金方案",
        }
    if "方案" in title or "经营贷" in title:
        return {
            **copy,
            "description": "围绕企业实际情况，整理更清晰的融资思路与方案比较。",
            "tip": "如果想进一步判断适配方向，可继续查看规划建议。",
            "action_text": "获取融资规划建议",
        }
    if "经营分析" in title:
        return {
            **copy,
            "description": "从现金流、成本与资金节奏出发，延伸阅读更多经营分析思路。",
            "tip": "希望继续理解类似案例时，可查看更多内容参考。",
            "action_text": "查看更多案例",
        }
    if action_text in {"一对一咨询", "立即咨询", "联系顾问", "获取方案", "免费评估"}:
        return {
            **copy,
            "description": "延伸了解企业融资与资金规划中的常见判断框架。",
            "tip": "如需继续阅读相关内容，可查看更适合当前阶段的建议。",
            "action_text": "了解适合自己的资金方案",
        }
    return copy


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
        fallback["style"] = "margin:12px 0 0 0;font-size:13px;line-height:1.8;color:#7A8797;"
        fallback.string = "当前未配置咨询链接，请通过公众号菜单或后台联系方式联系我们。"
        section.append(fallback)

    return section


def build_cta_html(cta: dict[str, str] | str | None) -> str:
    """Build the single late-stage CTA block used by fresh article rendering."""
    if cta is None:
        return ""
    if isinstance(cta, str):
        safe_title = "需要融资规划建议？"
        safe_description = _safe_text(cta)
        safe_button = "了解适合自己的资金方案"
    elif isinstance(cta, dict):
        safe_title = _safe_text(cta.get("title") or "需要融资规划建议？")
        safe_description = _safe_text(cta.get("description") or cta.get("text") or "")
        safe_button = _safe_text(cta.get("button_text") or "了解适合自己的资金方案")
    else:
        return ""

    if not safe_description:
        return ""

    soup = BeautifulSoup("", "html.parser")
    card = _build_lead_card(
        soup,
        {
            "title": safe_title,
            "description": safe_description,
            "tip": "如果希望继续延伸理解，可以从这里查看更贴近当前需求的内容。",
            "action_text": safe_button,
        },
        _safe_text(WECHAT_LEAD_FORM_URL) or "/lead-form",
    )
    return str(card)


def inject_cta_into_html(html_content: str, cta_html: str) -> str:
    """Insert prepared CTA HTML into the late article section only."""
    if not html_content or not html_content.strip():
        return html_content or ""
    if not cta_html or not cta_html.strip():
        return html_content

    soup = BeautifulSoup(html_content, "html.parser")
    _remove_legacy_cta_cards(soup)
    cta_soup = BeautifulSoup(cta_html, "html.parser")
    cta_node = next(iter(cta_soup.contents), None)
    if cta_node is None:
        return html_content

    if not _insert_card_late_in_article(soup, cta_node):
        body = soup.body if soup.body else soup
        body.append(cta_node)

    body = soup.body if soup.body else soup
    return "".join(str(child) for child in body.children).strip()


def _insert_card_late_in_article(soup: BeautifulSoup, card) -> bool:
    """Place CTA after value is established, closer to the article ending."""
    headings = soup.find_all(["h2", "h3"])
    if headings:
        headings[-1].insert_after(card)
        return True

    paragraphs = soup.find_all("p")
    if len(paragraphs) >= 5:
        insert_index = max(0, len(paragraphs) - 3)
        paragraphs[insert_index].insert_after(card)
        return True
    return False


def adapt_lead_form_to_wechat_card(html_content: str, lead_url: str | None = None) -> str:
    """把真实留资表单替换为公众号兼容留资入口卡片。"""
    if not html_content or not html_content.strip():
        return ""

    soup = BeautifulSoup(html_content, "html.parser")
    # 未配置公网落地页时，先使用系统内置公开留资页，保证后台预览可点击。
    configured_url = _safe_text(WECHAT_LEAD_FORM_URL if lead_url is None else lead_url) or "/lead-form"

    forms = list(soup.find_all("form"))
    pending_copy = None
    for form in forms:
        target = _find_replace_target(form)
        if pending_copy is None:
            pending_copy = _refine_card_copy(_detect_card_copy(form, target))
        target.decompose()

    if pending_copy:
        card = _build_lead_card(soup, pending_copy, configured_url)
        body = soup.body if soup.body else soup
        html_without_cta = "".join(str(child) for child in body.children).strip()
        injected_html = inject_cta_into_html(html_without_cta, str(card))
        soup = BeautifulSoup(injected_html, "html.parser")

    # 公众号正文不支持脚本和真实表单控件；即使控件不在 form 内，也统一清理。
    for tag in soup.find_all(["script", "form", "input", "textarea", "select", "button"]):
        tag.decompose()

    body = soup.body if soup.body else soup
    return "".join(str(child) for child in body.children).strip()
