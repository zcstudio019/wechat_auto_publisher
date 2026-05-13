"""微信公众号正文 HTML 兼容适配器。

这个模块只负责把后台预览用 HTML 降级为微信草稿箱更稳定的正文 HTML。
它不修改数据库、不上传图片、不改变发布流程，只在推送前动态清洗和补齐内联样式。
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Comment, NavigableString


# 微信正文中相对稳定的标签集合，其他标签会被降级或展开。
ALLOWED_TAGS = {
    "section", "p", "span", "strong", "b", "em", "img", "blockquote",
    "h2", "h3", "ul", "ol", "li", "br", "a",
}

# 明确删除的标签：这些在微信草稿箱里要么无效，要么有安全/展示风险。
DROP_TAGS = {"style", "script", "link", "iframe", "form", "input", "button", "textarea", "select"}

# 允许保留的内联样式属性，尽量选择微信里比较稳定的基础排版能力。
ALLOWED_STYLE_PROPS = {
    "color", "background", "background-color", "font-size", "line-height",
    "font-weight", "text-align", "padding", "padding-left", "padding-right",
    "padding-top", "padding-bottom", "margin", "margin-left", "margin-right",
    "margin-top", "margin-bottom", "border", "border-left", "border-radius",
    "letter-spacing", "display", "width", "max-width",
}

# 必须过滤的复杂网页样式，微信会清洗或导致展示失真。
BLOCKED_STYLE_PROPS = {
    "position", "flex", "grid", "box-shadow", "background-image", "animation",
    "transition", "transform", "filter", "backdrop-filter", "overflow", "z-index",
    "justify-content", "align-items", "gap", "float", "clear", "min-height",
    "height", "top", "left", "right", "bottom",
}

PARAGRAPH_STYLE = "font-size:16px;line-height:1.9;color:#333;margin:12px 0;"
SECTION_STYLE = "margin:16px 0;padding:0;"
TITLE_CARD_STYLE = (
    "background-color:#1565C0;color:#ffffff;padding:24px 22px;"
    "border-radius:10px;margin:16px 0 18px;line-height:1.6;"
)
TITLE_CARD_HEADING_STYLE = (
    "margin:0 0 16px 0;font-size:26px;line-height:1.35;"
    "font-weight:800;color:#ffffff;background-color:transparent;"
    "padding:0;border:0;"
)
TITLE_CARD_META_STYLE = (
    "margin:0 0 12px 0;font-size:14px;line-height:1.6;"
    "color:#dbeafe;background-color:transparent;padding:0;border:0;"
)
HEADING_STYLE = (
    "background-color:#EEF4FF;border-left:4px solid #1565C0;padding:10px 12px;"
    "border-radius:4px;color:#1565C0;font-size:17px;font-weight:bold;"
    "line-height:1.6;margin:22px 0 12px;"
)
QUOTE_STYLE = (
    "background-color:#FFF8E1;border-left:4px solid #FFA000;padding:12px 14px;"
    "border-radius:4px;color:#6B4E00;font-size:15px;line-height:1.8;margin:16px 0;"
)
IMAGE_STYLE = "max-width:100%;width:100%;display:block;margin:12px 0;"
ARTICLE_IMAGE_CONTAINER_STYLE = "margin:24px 0;padding:0;"
ARTICLE_IMAGE_STYLE = (
    "max-width:100%;width:100%;display:block;margin:0 auto;"
    "border-radius:12px;"
)


def _parse_style(style_text: str) -> dict[str, str]:
    """把 style 字符串解析为小写属性字典。"""
    styles: dict[str, str] = {}
    for item in (style_text or "").split(";"):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key and value:
            styles[key] = value
    return styles


def _style_dict_to_text(styles: dict[str, str]) -> str:
    """把样式字典重新拼成稳定的内联 style。"""
    return ";".join(f"{key}:{value}" for key, value in styles.items()) + (";" if styles else "")


def _sanitize_style(style_text: str) -> str:
    """只保留微信里相对稳定的基础 inline style。"""
    safe_styles: dict[str, str] = {}
    for key, value in _parse_style(style_text).items():
        if key in BLOCKED_STYLE_PROPS:
            continue
        if key not in ALLOWED_STYLE_PROPS:
            continue
        lower_value = value.lower()
        if "url(" in lower_value or "expression(" in lower_value:
            continue
        # 微信对渐变和复杂背景支持不稳定，这里降级为纯色背景。
        if key in {"background", "background-color"} and "linear-gradient" in lower_value:
            value = "#1565C0"
        # display 只保留 block，避免 flex/grid 等布局在微信中失真。
        if key == "display" and lower_value != "block":
            continue
        safe_styles[key] = value
    return _style_dict_to_text(safe_styles)


def _merge_styles(*style_texts: str) -> str:
    """后面的样式覆盖前面的样式，用于保留原有安全样式并补默认样式。"""
    merged: dict[str, str] = {}
    for style_text in style_texts:
        merged.update(_parse_style(style_text))
    return _style_dict_to_text(merged)


def _is_empty_block(tag) -> bool:
    """判断是否为空白占位块，用于减少微信里大面积留白。"""
    if getattr(tag, "name", None) == "img":
        return False
    text = tag.get_text("", strip=True).replace("\xa0", "")
    if text:
        return False
    meaningful_children = [
        child for child in tag.children
        if getattr(child, "name", None) not in {None, "br"}
        or (isinstance(child, NavigableString) and child.strip())
    ]
    return not meaningful_children


def _looks_like_title_card(tag) -> bool:
    """识别后台预览里的标题卡片/顶部横幅，并降级成微信兼容标题区。"""
    class_text = " ".join(tag.get("class", [])).lower() if tag.get("class") else ""
    style_text = (tag.get("style") or "").lower()
    text = tag.get_text("", strip=True)
    return (
        tag.name in {"section", "div"}
        and (
            "title" in class_text
            or "banner" in class_text
            or "hero" in class_text
            or "header" in class_text
            or "linear-gradient" in style_text
            or "#1667c7" in style_text
            or "#1565c0" in style_text
        )
        and len(text) > 0
    )


def _is_inside_title_card(tag) -> bool:
    """判断当前标题是否位于顶部标题卡片中，避免被套上普通章节浅色背景。"""
    for parent in getattr(tag, "parents", []):
        style_text = (parent.get("style") or "").lower()
        if "#1667c7" in style_text or "#1565c0" in style_text:
            return True
    return False


def _normalize_tag_name(tag) -> None:
    """把复杂或不稳定标签降级为微信更稳的标签。"""
    if tag.name == "div":
        tag.name = "section"
    elif tag.name == "h1":
        tag.name = "h2"
    elif tag.name in {"h4", "h5", "h6"}:
        tag.name = "h3"
    elif tag.name in {"article", "main", "header", "footer", "aside"}:
        tag.name = "section"
    elif tag.name not in ALLOWED_TAGS:
        # 不认识的标签尽量展开内容，避免把正文误删。
        tag.unwrap()


def _reset_attrs(tag) -> None:
    """删除 class、data-*、JS 事件等微信不需要的属性，只保留少量安全属性。"""
    if not getattr(tag, "attrs", None):
        return

    safe_attrs = {}
    if tag.name == "img":
        for attr in ("src", "alt"):
            if tag.get(attr):
                safe_attrs[attr] = tag.get(attr)
    if tag.name == "a" and tag.get("href"):
        # 留资入口卡片需要保留咨询链接，但不保留 onclick 等事件属性。
        safe_attrs["href"] = tag.get("href")
    if tag.get("style"):
        safe_style = _sanitize_style(tag.get("style", ""))
        if safe_style:
            safe_attrs["style"] = safe_style
    tag.attrs = safe_attrs


def _apply_wechat_default_style(tag, force_title_card: bool = False) -> None:
    """给常见正文标签补充微信兼容的基础内联样式。"""
    current_style = tag.get("style", "")
    if force_title_card or _looks_like_title_card(tag):
        tag["style"] = _merge_styles(current_style, TITLE_CARD_STYLE)
        return
    if tag.name == "img":
        tag["style"] = _merge_styles(current_style, IMAGE_STYLE)
    elif tag.name in {"h2", "h3"} and _is_inside_title_card(tag):
        tag["style"] = _merge_styles(current_style, TITLE_CARD_HEADING_STYLE)
    elif tag.name == "p" and _is_inside_title_card(tag):
        tag["style"] = _merge_styles(current_style, TITLE_CARD_META_STYLE)
    elif tag.name in {"h2", "h3"}:
        tag["style"] = _merge_styles(current_style, HEADING_STYLE)
    elif tag.name == "blockquote":
        tag["style"] = _merge_styles(current_style, QUOTE_STYLE)
    elif tag.name == "p":
        tag["style"] = _merge_styles(current_style, PARAGRAPH_STYLE)
    elif tag.name == "section":
        tag["style"] = _merge_styles(current_style, SECTION_STYLE)
    elif tag.name == "li":
        tag["style"] = _merge_styles(current_style, "font-size:16px;line-height:1.8;color:#333;margin:6px 0;")
    elif tag.name in {"ul", "ol"}:
        tag["style"] = _merge_styles(current_style, "margin:12px 0;padding-left:22px;")
    elif tag.name in {"strong", "b"}:
        tag["style"] = _merge_styles(current_style, "font-weight:bold;color:#1565C0;")
    elif tag.name == "a":
        tag["style"] = _merge_styles(
            current_style,
            "display:block;background-color:#18b57b;color:#ffffff;text-align:center;"
            "padding:10px 18px;border-radius:6px;text-decoration:none;font-size:14px;"
            "margin:14px 0 0;",
        )


def cleanup_empty_blocks(html_content: str) -> str:
    """清理空段落、空 div/section 和重复空白块。"""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in list(soup.find_all(["p", "div", "section"])):
        if _is_empty_block(tag):
            tag.decompose()
    cleaned = str(soup)
    cleaned = re.sub(r'(<br\s*/?>\s*){3,}', '<br/>', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'(&nbsp;|\s)+</p>', '</p>', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def inject_article_image_into_html(
    html_content: str,
    image_url: str,
    alt_text: str = "",
    insert_mode: str = "middle",
) -> str:
    """Inject one contextual article image into rendered HTML without touching markdown."""
    if not html_content or not html_content.strip():
        return html_content or ""

    safe_image_url = (image_url or "").strip()
    if not safe_image_url:
        return html_content

    soup = BeautifulSoup(html_content, "html.parser")
    if soup.find("img", attrs={"src": safe_image_url}):
        return html_content

    image_block = soup.new_tag(
        "section",
        attrs={"class": "article-image", "style": ARTICLE_IMAGE_CONTAINER_STYLE},
    )
    article_image = soup.new_tag(
        "img",
        attrs={
            "src": safe_image_url,
            "alt": (alt_text or "文章配图").strip() or "文章配图",
            "style": ARTICLE_IMAGE_STYLE,
        },
    )
    image_block.append(article_image)

    first_heading = next(
        (
            heading for heading in soup.find_all(["h2", "h3"])
            if not _is_inside_title_card(heading)
        ),
        None,
    )
    if first_heading is not None:
        first_heading.insert_after(image_block)
    else:
        paragraphs = [
            paragraph for paragraph in soup.find_all("p")
            if not _is_inside_title_card(paragraph)
        ]
        if len(paragraphs) < 3:
            return html_content
        paragraphs[2].insert_after(image_block)

    body = soup.body if soup.body else soup
    return "".join(str(child) for child in body.children).strip()


def inject_cover_into_html(html_content: str, cover_url: str) -> str:
    """Backward-compatible alias: cover images are now placed as mid-article visuals."""
    return inject_article_image_into_html(html_content, cover_url)


def sanitize_wechat_html(html_content: str) -> str:
    """删除微信不稳定标签、属性和复杂样式，保留正文结构。"""
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, "html.parser")

    for node in soup.find_all(string=lambda text: isinstance(text, Comment)):
        node.extract()

    for tag in soup.find_all(DROP_TAGS):
        tag.decompose()

    for tag in list(soup.find_all(True)):
        _normalize_tag_name(tag)

    for tag in list(soup.find_all(True)):
        # class/style 会在属性清理时被降级，标题卡片特征需要提前记录。
        is_title_card = _looks_like_title_card(tag)
        _reset_attrs(tag)
        _apply_wechat_default_style(tag, force_title_card=is_title_card)

    # 如果 BeautifulSoup 包了一层 html/body，只取正文内部内容。
    body = soup.body if soup.body else soup
    return "".join(str(child) for child in body.children).strip()


def adapt_html_for_wechat(html_content: str) -> str:
    """把后台预览 HTML 转为微信公众号草稿箱兼容 HTML。"""
    if not html_content or not html_content.strip():
        return ""

    sanitized = sanitize_wechat_html(html_content)
    cleaned = cleanup_empty_blocks(sanitized)
    if cleaned:
        return cleaned

    # 极端情况下避免返回空字符串，至少保留纯文本正文。
    plain_text = BeautifulSoup(html_content, "html.parser").get_text("\n", strip=True)
    if not plain_text:
        return ""
    paragraphs = [
        f'<p style="{PARAGRAPH_STYLE}">{line}</p>'
        for line in plain_text.splitlines()
        if line.strip()
    ]
    return "\n".join(paragraphs).strip()
