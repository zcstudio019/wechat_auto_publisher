"""公众号正文留资入口卡片适配器。

后台预览可以继续保留真实表单，但微信公众号正文不支持可靠的 form/input
交互。本模块只在发布前把真实表单块替换成静态咨询入口卡片，不修改数据库
和文章原始内容。
"""

from __future__ import annotations

import logging
from pathlib import Path

from bs4 import BeautifulSoup
from bs4.element import Tag

from config import BASE_DIR, WECHAT_LEAD_QR_IMAGE

logger = logging.getLogger(__name__)


CARD_STYLE = (
    "margin:40px 0;padding:18px 20px;background:#F4F8FC;"
    "border:1px solid #DCE8F5;border-radius:16px;color:#1F2D3D;"
)
TITLE_STYLE = (
    "margin:0 0 10px 0;font-size:18px;font-weight:bold;"
    "color:#17324D;line-height:1.5;"
)
DESC_STYLE = "margin:0 0 10px 0;font-size:14px;line-height:1.85;color:#516173;"
TIP_STYLE = "margin:0 0 10px 0;font-size:13px;line-height:1.8;color:#66758A;"
QR_WRAP_STYLE = "margin:16px 0 0 0;text-align:center;"
QR_IMAGE_STYLE = "width:150px;max-width:60%;display:block;margin:0 auto;border-radius:12px;"
QR_FALLBACK_STYLE = "margin:14px 0 0 0;font-size:14px;line-height:1.8;color:#334155;text-align:center;"
LEGACY_CTA_MARKERS = (
    "场景案例",
    "上海企业融资规划咨询",
    "科学规划",
    "多渠道融资",
    "降低风险",
)
CTA_ACTION_MARKERS = (
    "场景案例",
    "一对一咨询",
    "融资规划咨询",
    "科学规划",
    "多渠道融资",
    "降低风险",
    "立即咨询",
    "获取方案",
    "联系顾问",
    "免费评估",
    "了解适合自己的资金方案",
)
OLD_GREEN_CTA_KEYWORDS = CTA_ACTION_MARKERS
DEEP_GREEN_STYLE_MARKERS = ("#0f5132", "#065f46", "#166534", "#0f5d2c", "green", "background")


def _safe_text(text: str) -> str:
    """清理文本两侧空白，避免卡片文案出现多余换行。"""
    return (text or "").strip()


def _safe_attrs(tag) -> dict:
    """Normalize BeautifulSoup attrs for malformed tags."""
    if not isinstance(tag, Tag):
        return {}
    attrs = getattr(tag, "attrs", None)
    return attrs if isinstance(attrs, dict) else {}


def _resolve_qr_image_src() -> str:
    """Resolve QR image for preview/upload; return empty string when local QR is missing."""
    configured = _safe_text(WECHAT_LEAD_QR_IMAGE)
    if not configured:
        logger.warning("[wechat-lead-card] WECHAT_LEAD_QR_IMAGE 未配置，CTA 将不展示二维码")
        return ""

    if configured.startswith(("http://", "https://")):
        return configured
    if configured.startswith(("/static/", "static/")):
        static_source = configured.lstrip("/")
        static_path = Path(BASE_DIR) / "web_ui" / static_source
        if static_path.exists():
            return f"/{static_source}"
        logger.warning("[wechat-lead-card] 留资二维码图片不存在: %s", configured)
        return ""

    qr_path = Path(configured)
    if not qr_path.is_absolute():
        qr_path = Path(BASE_DIR) / configured
    if not qr_path.exists():
        logger.warning("[wechat-lead-card] 留资二维码图片不存在: %s", configured)
        return ""

    normalized_parts = [part.lower() for part in qr_path.parts]
    if "static" in normalized_parts:
        static_index = normalized_parts.index("static")
        relative_parts = qr_path.parts[static_index + 1 :]
        if relative_parts:
            return "/static/" + "/".join(relative_parts).replace("\\", "/")
    return str(qr_path)


def is_old_green_cta_card(tag) -> bool:
    if not isinstance(tag, Tag):
        return False
    attrs = _safe_attrs(tag)
    if tag.name not in {"section", "div"}:
        return False

    text = _safe_text(tag.get_text(" ", strip=True))
    if not text:
        return False

    keyword_count = sum(1 for marker in OLD_GREEN_CTA_KEYWORDS if marker in text)
    if keyword_count == 0:
        return False

    paragraph_count = len(tag.find_all("p"))
    heading_count = len(tag.find_all(["h2", "h3"]))
    text_length = len(text)
    is_card_like = text_length <= 320 and paragraph_count <= 8 and heading_count <= 2
    if not is_card_like:
        return False

    style_text = str(attrs.get("style", "")).lower()
    has_deep_green_style = any(marker in style_text for marker in DEEP_GREEN_STYLE_MARKERS)
    return keyword_count >= 2 or (has_deep_green_style and keyword_count >= 1)


def _is_legacy_cta_card(tag) -> bool:
    return is_old_green_cta_card(tag)


def _remove_legacy_cta_cards(soup: BeautifulSoup) -> int:
    removed_count = 0
    for tag in list(soup.find_all(["section", "div"])):
        if not isinstance(tag, Tag):
            continue
        if _is_legacy_cta_card(tag):
            tag.decompose()
            removed_count += 1
    return removed_count


def remove_legacy_cta_cards(html_content: str) -> str:
    if not html_content or not html_content.strip():
        return html_content or ""

    before_len = len(html_content)
    soup = BeautifulSoup(html_content, "html.parser")
    removed_count = _remove_legacy_cta_cards(soup)
    body = soup.body if soup.body else soup
    cleaned_html = "".join(str(child) for child in body.children).strip()
    after_len = len(cleaned_html)
    logger.info("[cta] removed legacy cta count=%s", removed_count)
    logger.info("[cta] before_len=%s after_len=%s", before_len, after_len)

    if removed_count and before_len and after_len < before_len * 0.7:
        logger.warning("[cta] cleanup shortened html too much, fallback to original: before_len=%s after_len=%s", before_len, after_len)
        return html_content
    return cleaned_html or html_content


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
    form_attrs = _safe_attrs(form)
    form_type = _safe_text(form_attrs.get("data-form-type", ""))
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
    if not isinstance(form, Tag):
        return form
    for parent in form.parents:
        attrs = _safe_attrs(parent)
        class_value = attrs.get("class", [])
        if isinstance(class_value, str):
            class_value = [class_value]
        class_text = " ".join(class_value)
        if "lead-form-container" in class_text or "work-order-form" in class_text:
            return parent
        if parent.name in {"body", "html"}:
            break
    return form


def _build_lead_card(soup: BeautifulSoup, copy: dict[str, str], lead_url: str = "") -> object:
    """构建微信公众号兼容的静态留资入口卡片。"""
    section = soup.new_tag("div")
    section["style"] = CARD_STYLE

    title = soup.new_tag("p")
    title["style"] = TITLE_STYLE
    title.string = "想了解适合自己的资金方案？"
    section.append(title)

    description = soup.new_tag("p")
    description["style"] = DESC_STYLE
    description.string = "扫码添加顾问，获取企业融资规划建议。"
    section.append(description)

    tip = soup.new_tag("p")
    tip["style"] = TIP_STYLE
    tip.string = "根据企业实际情况做初步判断，不承诺结果，不夸大效果。"
    section.append(tip)

    qr_src = _resolve_qr_image_src()
    if qr_src:
        qr_wrap = soup.new_tag("div")
        qr_wrap["style"] = QR_WRAP_STYLE
        qr_img = soup.new_tag("img", src=qr_src)
        qr_img["alt"] = "扫码添加顾问"
        qr_img["style"] = QR_IMAGE_STYLE
        qr_wrap.append(qr_img)
        section.append(qr_wrap)
    else:
        fallback = soup.new_tag("p")
        fallback["style"] = QR_FALLBACK_STYLE
        fallback.string = "请联系顾问获取方案。"
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
        "",
    )
    return str(card)


def inject_cta_into_html(html_content: str, cta_html: str) -> str:
    """Insert prepared CTA HTML into the late article section only."""
    try:
        if not html_content or not html_content.strip():
            return html_content or ""
        if not cta_html or not cta_html.strip():
            return remove_legacy_cta_cards(html_content)

        cleaned_html = remove_legacy_cta_cards(html_content)
        soup = BeautifulSoup(cleaned_html, "html.parser")
        cta_soup = BeautifulSoup(cta_html, "html.parser")
        cta_node = next((node for node in cta_soup.contents if isinstance(node, Tag)), None)
        if cta_node is None:
            return html_content

        if not _insert_card_late_in_article(soup, cta_node):
            body = soup.body if soup.body else soup
            body.append(cta_node)

        body = soup.body if soup.body else soup
        return "".join(str(child) for child in body.children).strip()
    except Exception as exc:
        logger.warning("[wechat-lead-card] CTA 插入失败，已跳过: %s", exc)
        return html_content or ""


def _is_after_content_midpoint(soup: BeautifulSoup, target: Tag) -> bool:
    all_blocks = [node for node in soup.find_all(["h2", "h3", "p", "section", "div"]) if isinstance(node, Tag)]
    if not all_blocks:
        return True
    try:
        index = all_blocks.index(target)
    except ValueError:
        return True
    return index >= int(len(all_blocks) * 0.6)


def _insert_card_late_in_article(soup: BeautifulSoup, card) -> bool:
    """Place CTA in the late article section, never in the first 60%."""
    headings = [tag for tag in soup.find_all(["h2", "h3"]) if isinstance(tag, Tag)]
    if len(headings) >= 2:
        target = headings[-2]
        if _is_after_content_midpoint(soup, target):
            target.insert_before(card)
            return True

    paragraphs = [tag for tag in soup.find_all("p") if isinstance(tag, Tag)]
    if len(paragraphs) >= 5:
        target = paragraphs[-3]
        if _is_after_content_midpoint(soup, target):
            target.insert_after(card)
            return True

    body = soup.body if soup.body else soup
    tag_children = [child for child in body.children if isinstance(child, Tag)]
    if tag_children:
        tag_children[-1].insert_before(card)
    else:
        body.append(card)
    return True


def adapt_lead_form_to_wechat_card(html_content: str, lead_url: str | None = None) -> str:
    """把真实留资表单替换为公众号兼容留资入口卡片。"""
    if not html_content or not html_content.strip():
        return ""

    original_length = len(html_content)
    soup = BeautifulSoup(html_content, "html.parser")
    # 未配置公网落地页时，先使用系统内置公开留资页，保证后台预览可点击。
    forms = [tag for tag in soup.find_all("form") if isinstance(tag, Tag)]
    pending_copy = None
    for form in forms:
        target = _find_replace_target(form)
        if pending_copy is None:
            pending_copy = _refine_card_copy(_detect_card_copy(form, target))
        target.decompose()

    if pending_copy:
        card = _build_lead_card(soup, pending_copy, "")
        body = soup.body if soup.body else soup
        html_without_cta = "".join(str(child) for child in body.children).strip()
        if html_without_cta:
            injected_html = inject_cta_into_html(html_without_cta, str(card))
            soup = BeautifulSoup(injected_html, "html.parser")
        else:
            body.append(card)

    # 公众号正文不支持脚本和真实表单控件；即使控件不在 form 内，也统一清理。
    for tag in soup.find_all(["script", "form", "input", "textarea", "select", "button"]):
        if not isinstance(tag, Tag):
            continue
        tag.decompose()

    body = soup.body if soup.body else soup
    final_html = "".join(str(child) for child in body.children).strip()
    final_length = len(final_html)
    logger.info("[wechat-lead-card] html length before=%s after=%s", original_length, final_length)
    if original_length and final_length < original_length * 0.5 and not forms:
        logger.warning(
            "[wechat-lead-card] processed html is too short, fallback to original: before=%s after=%s",
            original_length,
            final_length,
        )
        return html_content
    return final_html
