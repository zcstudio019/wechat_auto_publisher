"""
发布任务：将数据库中 approved 状态的文章推送为微信草稿
"""
import logging
import re
import sys
import os
from pathlib import Path
from bs4 import BeautifulSoup
from bs4.element import Tag
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db, is_mysql
from domain.article_status import (
    STATUS_APPROVED,
    STATUS_DRAFT_SENT,
    STATUS_ERROR,
    STATUS_PUBLISHED,
    split_legacy_status,
)
from ai_processor.processor import process_article, _render_original_html
from services.wechat_html_adapter import adapt_html_for_wechat, inject_article_image_into_html
from services.wechat_lead_card_adapter import adapt_lead_form_to_wechat_card, append_lead_qr_at_end
from services.wechat_title_optimizer import optimize_wechat_title
from services.title_guard import TitleGuard
from .client import WechatPublishError, ensure_thumb_media_id, add_draft, submit_draft_for_review, upload_content_image, validate_wechat_config

logger = logging.getLogger(__name__)

DEFAULT_WECHAT_AUTHOR = "沪上银 · 有金"

# 微信草稿字段限制（实测值，非官方文档值）
WECHAT_TITLE_MAX_BYTES = 96        # 标题上限（字节）：优先由 optimize_wechat_title 控制在 18~28 中文字
WECHAT_AUTHOR_MAX_BYTES = 8        # 作者上限（字节）：7通过/9失败
WECHAT_DIGEST_MAX_CHARS = 54        # 草稿箱摘要最多保留 54 个字符，避免微信卡片副标题异常截断。
WECHAT_CONTENT_MAX_BYTES = 20000   # 正文上限（字节）
WECHAT_TOP_NOISE_MARKERS = (
    "沪上银",
    "上海专业贷款顾问",
    "贷款顾问",
    "公众号",
)
MIN_PUBLISH_TEXT_LENGTH = 500
PUBLISH_DEBUG_DIR = Path("/tmp")
PUBLISH_CONTENT_ERROR_MESSAGE = "推送失败：最终正文内容异常，疑似正文被留资模块覆盖，请检查推送内容组装逻辑。"
PUBLISH_MISSING_QR_ERROR_MESSAGE = "推送失败：最终正文缺少留资二维码，请检查二维码配置或追加逻辑。"
PUBLISH_MISSING_QR_IMAGE_ERROR_MESSAGE = "推送失败：留资二维码图片未配置，无法插入二维码。"
PUBLISH_REQUIRE_LEAD_QR = os.getenv("PUBLISH_REQUIRE_LEAD_QR", "false").lower() in ("1", "true", "yes", "on")
LEAD_QR_WECHAT_IMAGE_URL = os.getenv("LEAD_QR_WECHAT_IMAGE_URL", "").strip()
_lead_qr_wechat_image_url_cache = LEAD_QR_WECHAT_IMAGE_URL
LEAD_ONLY_MARKERS = (
    "融资体检",
    "扫码",
    "二维码",
    "免费预约",
    "预约",
    "留资",
    "额度测算",
    "经营贷体检",
)
WECHAT_TOP_META_MARKERS = (
    "author",
    "digest",
    "summary",
    "header",
    "banner",
    "hero",
    "brand",
    "slogan",
    "source",
    "meta",
)


def _select_approved_articles(cursor):
    """查询所有已审核文章，显式区分 SQLite / MySQL 语法。"""
    if is_mysql():
        return cursor.execute(
            "SELECT * FROM articles WHERE status=%s ORDER BY created_at DESC",
            (STATUS_APPROVED,),
        ).fetchall()
    return cursor.execute(
        "SELECT * FROM articles WHERE status=? ORDER BY created_at DESC",
        (STATUS_APPROVED,),
    ).fetchall()


def _update_article_publish_status(cursor, article_id: int, status: str, review_status: str, publish_status: str, draft_id: str = ""):
    """回写微信推送后的文章状态，显式区分 SQLite / MySQL 时间函数与占位符。"""
    if is_mysql():
        cursor.execute(
            """
            UPDATE articles
            SET status=%s, review_status=%s, publish_status=%s, draft_id=%s, updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
            """,
            (status, review_status, publish_status, draft_id, article_id),
        )
        return

    cursor.execute(
        """
        UPDATE articles
        SET status=?, review_status=?, publish_status=?, draft_id=?, updated_at=datetime('now','localtime')
        WHERE id=?
        """,
        (status, review_status, publish_status, draft_id, article_id),
    )


def _mark_article_publish_error(cursor, article_id: int, review_status: str, publish_status: str):
    """回写微信推送失败状态，显式区分 SQLite / MySQL 时间函数与占位符。"""
    if is_mysql():
        cursor.execute(
            """
            UPDATE articles
            SET status=%s, review_status=%s, publish_status=%s, updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
            """,
            (STATUS_ERROR, review_status, publish_status, article_id),
        )
        return

    cursor.execute(
        """
        UPDATE articles
        SET status=?, review_status=?, publish_status=?, updated_at=datetime('now','localtime')
        WHERE id=?
        """,
        (STATUS_ERROR, review_status, publish_status, article_id),
    )


def _strip_html(html: str) -> str:
    """将 HTML 转为纯文本（去除标签、实体解码）"""
    if not html:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', html)
    text = re.sub(r'<p[^>]*>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)  # 去除所有标签
    # 常见 HTML 实体
    entities = {
        '&amp;': '&', '&lt;': '<', '&gt;': '>',
        '&quot;': '"', '&#39;': "'", '&nbsp;': ' ',
        '&hellip;': '\u2026', '&mdash;': '\u2014',
        '&ndash;': '\u2013',
    }
    for k, v in entities.items():
        text = text.replace(k, v)
    # 清理多余空白
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def _truncate_bytes(text: str, max_bytes: int) -> str:
    """按字节截断任意文本"""
    encoded = text.encode('utf-8')
    if len(encoded) <= max_bytes:
        return text
    ellipsis = "…"
    limit = max_bytes - len(ellipsis.encode('utf-8'))
    for i in range(len(text), 0, -1):
        if len(text[:i].encode('utf-8')) <= limit:
            return text[:i] + ellipsis
    return text[:limit] + ellipsis


def _truncate_title(title: str, max_bytes: int = WECHAT_TITLE_MAX_BYTES) -> str:
    """按字节截断标题，并在推送前做最终完整性保护。"""
    guarded_title = TitleGuard.sanitize_title(title)["title"]
    return _truncate_bytes(optimize_wechat_title(guarded_title), max_bytes)


def _make_digest(summary: str, content: str = "", max_chars: int = WECHAT_DIGEST_MAX_CHARS) -> str:
    """只使用文章摘要生成微信草稿 digest；摘要为空时返回空字符串，不从正文或品牌兜底。"""
    text = _strip_html(summary) if summary else ""
    text = re.sub(r"\s+", " ", text).strip()
    for brand_text in [
        "沪上银 · 上海专业贷款顾问",
        "沪上银·上海专业贷款顾问",
        "上海专业贷款顾问",
        "沪上银",
        "贷款顾问",
    ]:
        text = text.replace(brand_text, "")
    text = re.sub(r"\s+", " ", text).strip(" ｜|·-—_:：")
    if not text:
        return ""
    return text[:max_chars]











def _strip_title_banner(html: str) -> str:
    """
    推送微信前，移除正文开头的品牌标题横幅（大蓝色渐变 div）。
    微信草稿箱已有封面图+标题，正文里的横幅是多余的且显示太大。
    匹配特征：background:linear-gradient(135deg,#0D47A1 开头的第一个顶层 div。
    """
    if not html:
        return html
    # 匹配正文最开头的标题横幅 div（含嵌套子元素），用简单字符串定位
    # 特征：第一个 <div style="background:linear-gradient(135deg,#0D47A1
    import re
    # 找到横幅 div 的起始位置
    pattern = r'<div[^>]*background:linear-gradient\(135deg,#0D47A1[^>]*>.*?</div>\s*</div>\s*</div>'
    # 由于 div 嵌套深，用更可靠的方式：找到后手动数括号深度
    start_marker = 'background:linear-gradient(135deg,#0D47A1'
    idx = html.find(start_marker)
    if idx == -1:
        return html
    # 找到这个 div 的开始 <
    div_start = html.rfind('<div', 0, idx)
    if div_start == -1:
        return html
    # 从 div_start 往后数 <div 和 </div>，找到匹配的关闭标签
    depth = 0
    i = div_start
    while i < len(html):
        if html[i:i+4] == '<div':
            depth += 1
            i += 4
        elif html[i:i+6] == '</div>':
            depth -= 1
            i += 6
            if depth == 0:
                # 找到了结束位置，移除整个横幅
                stripped = html[:div_start] + html[i:]
                return stripped.lstrip()
        else:
            i += 1
    return html


def _fix_wechat_images(html: str) -> str:
    """
    推送微信前，将无法在微信中加载的外链图片替换为纯色渐变色块。
    主要处理 scene 配图卡里的 picsum.photos 外链 <img>。
    微信不支持 picsum/外链图片，会显示为灰色空白。
    替换策略：找到包含 picsum.photos 的 <img> 标签，
    将整个 scene 卡 <div>...</div> 替换为纯 CSS 渐变色块。
    """
    if not html or 'picsum.photos' not in html:
        return html

    import hashlib

    GRADIENTS = [
        ("135deg,#1565C0,#0D47A1", "rgba(255,255,255,0.12)"),
        ("135deg,#00695C,#004D40", "rgba(255,255,255,0.12)"),
        ("135deg,#4527A0,#311B92", "rgba(255,255,255,0.12)"),
        ("135deg,#BF360C,#870000", "rgba(255,255,255,0.10)"),
        ("135deg,#1B5E20,#0A3D0A", "rgba(255,255,255,0.10)"),
    ]

    def _replace_scene_card(m):
        block = m.group(0)
        # 提取 alt 属性作为 desc
        alt_m = re.search(r'alt="([^"]*)"', block)
        desc = alt_m.group(1) if alt_m else "场景案例"
        # 用 desc 的 hash 选渐变色
        seed = int(hashlib.md5(desc.encode('utf-8')).hexdigest()[:4], 16) % len(GRADIENTS)
        grad_dir, overlay = GRADIENTS[seed]
        return (
            f'<div style="background:linear-gradient({grad_dir});border-radius:10px;margin:16px 0;'
            f'padding:28px 22px 24px;position:relative;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.15);">'
            f'<div style="position:absolute;top:-30px;right:-30px;width:110px;height:110px;'
            f'background:{overlay};border-radius:50%;"></div>'
            f'<div style="position:relative;">'
            f'<div style="color:rgba(255,255,255,0.5);font-size:11px;letter-spacing:2px;margin-bottom:10px;">场景案例</div>'
            f'<p style="color:#ffffff;font-size:16px;font-weight:bold;margin:0 0 8px;line-height:1.5;">{desc}</p>'
            f'</div></div>'
        )

    # 匹配包含 picsum.photos 的 <div>...<img src="...picsum...">...</div> 块
    # 用宽松正则：从最近的 <div 开始到最近包含 picsum img 的 </div> 结束块
    html = re.sub(
        r'<div[^>]*>(?:(?!</div>).)*?picsum\.photos(?:(?!</div>).)*?</div>\s*</div>',
        _replace_scene_card,
        html,
        flags=re.DOTALL
    )
    return html


def _tag_attrs_text(tag: Tag) -> str:
    attrs = getattr(tag, "attrs", None) or {}
    parts: list[str] = []
    for value in attrs.values():
        if isinstance(value, (list, tuple)):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value))
    return " ".join(parts).lower()


def _is_hidden_tag(tag: Tag) -> bool:
    attrs_text = _tag_attrs_text(tag)
    return (
        "display:none" in attrs_text.replace(" ", "")
        or "visibility:hidden" in attrs_text.replace(" ", "")
        or "opacity:0" in attrs_text.replace(" ", "")
    )


def _looks_like_top_noise(tag: Tag) -> bool:
    text = tag.get_text(" ", strip=True)
    attrs_text = _tag_attrs_text(tag)
    lower_text = text.lower()
    has_brand = any(marker in text for marker in WECHAT_TOP_NOISE_MARKERS)
    has_meta_attr = any(marker in attrs_text for marker in WECHAT_TOP_META_MARKERS)
    has_meta_text = any(marker in lower_text for marker in ("summary", "digest", "author"))
    is_card_like = tag.name in {"div", "section", "header", "p", "span", "h1", "h2", "h3"}

    if _is_hidden_tag(tag):
        return True
    if has_brand and is_card_like:
        return True
    if has_meta_attr and is_card_like and len(text) <= 260:
        return True
    if has_meta_text and is_card_like and len(text) <= 260:
        return True
    if "linear-gradient" in attrs_text and is_card_like and len(text) <= 360:
        # 老的蓝色标题/品牌 Header 会被微信拿去做摘要，发布前必须去掉。
        return True
    return False


def _strip_wechat_top_noise(html: str) -> str:
    """发布到微信前移除正文顶部品牌/Header/隐藏摘要，避免草稿箱自动抓取出“沪...”。"""
    if not html or not html.strip():
        return html or ""
    try:
        before_len = len(html)
        soup = BeautifulSoup(html, "html.parser")
        removed_count = 0

        for tag in list(soup.find_all(True)):
            if isinstance(tag, Tag) and _is_hidden_tag(tag):
                tag.decompose()
                removed_count += 1

        body = soup.body if soup.body else soup
        scan_count = 0
        while scan_count < 10:
            first_tag = next((child for child in body.children if isinstance(child, Tag)), None)
            if first_tag is None or not _looks_like_top_noise(first_tag):
                break
            first_tag.decompose()
            removed_count += 1
            scan_count += 1

        cleaned = "".join(str(child) for child in body.children).strip()
        after_len = len(cleaned)
        cleaned_text = BeautifulSoup(cleaned, "html.parser").get_text("", strip=True)
        if removed_count:
            logger.info("[wechat-draft] removed_top_noise=%s before_len=%s after_len=%s", removed_count, before_len, after_len)
        if removed_count and before_len and after_len < before_len * 0.15 and len(cleaned_text) < 8:
            logger.warning("[wechat-draft] top noise cleanup shortened html too much, fallback to original")
            return html
        return cleaned or html
    except Exception as exc:
        logger.warning("[wechat-draft] top noise cleanup failed, skipped: %s", exc)
        return html


def _upload_content_images_for_wechat(html: str) -> str:
    """推送草稿前把正文 img 上传到微信 uploadimg，并替换为 mmbiz URL。"""
    if not html or "<img" not in html.lower():
        return html

    uploaded_cache = {}

    def _replace_img_src(match):
        quote = match.group(1)
        image_src = (match.group(2) or "").strip()
        if not image_src:
            return match.group(0)
        if image_src.startswith("https://mmbiz.qpic.cn/") or image_src.startswith("http://mmbiz.qpic.cn/"):
            return match.group(0)
        if image_src.startswith("data:"):
            logger.warning("[Publish] 跳过 data URI 正文图片，微信草稿箱不支持直接保存")
            return match.group(0)

        if image_src not in uploaded_cache:
            uploaded_cache[image_src] = upload_content_image(image_src)

        wechat_url = uploaded_cache.get(image_src)
        if not wechat_url:
            logger.warning("[Publish] 正文图片 uploadimg 失败，保留原始 src: %s", image_src)
            return match.group(0)

        return match.group(0).replace(image_src, wechat_url, 1)

    replaced_html = re.sub(
        r'<img\b[^>]*?\bsrc=(["\'])(.*?)\1[^>]*>',
        _replace_img_src,
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if uploaded_cache:
        success_count = sum(1 for value in uploaded_cache.values() if value)
        logger.info("[Publish] 正文图片 uploadimg 完成 success=%s total=%s", success_count, len(uploaded_cache))
    return replaced_html



def _is_wechat_content_image_url(src: str) -> bool:
    src = (src or "").strip().lower()
    return src.startswith("https://mmbiz.qpic.cn/") or src.startswith("http://mmbiz.qpic.cn/")


def _is_lead_qr_tag(tag: Tag) -> bool:
    if not isinstance(tag, Tag):
        return False
    attrs = getattr(tag, "attrs", None) or {}
    if str(attrs.get("data-lead-qr", "")).lower() == "true":
        return True
    if str(attrs.get("data-role", "")).lower() == "lead-qr":
        return True
    attr_text = _tag_attrs_text(tag)
    text = tag.get_text(" ", strip=True)
    if any(marker in attr_text for marker in ("lead-qr", "qrcode", "qr-code", "lead_qr")):
        return tag.name in {"section", "div"} or bool(tag.find_parent(["section", "div"]))
    if tag.name in {"section", "div"} and any(marker in text for marker in ("企业融资体检", "扫码", "二维码")) and tag.find("img"):
        return True
    return False


def _find_lead_qr_img_src(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for container in soup.find_all(True):
        if isinstance(container, Tag) and _is_lead_qr_tag(container):
            img = container.find("img") if container.name != "img" else container
            if isinstance(img, Tag):
                return str((img.get("src") or "")).strip()
    for img in soup.find_all("img"):
        attrs = getattr(img, "attrs", {}) or {}
        img_text = " ".join(str(attrs.get(name, "")) for name in ("src", "alt", "class", "id")).lower()
        if any(marker in img_text for marker in ("qr", "qrcode", "lead", "二维码", "融资体检")):
            return str((img.get("src") or "")).strip()
    return ""


def _remove_lead_qr_blocks_for_publish(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in list(soup.find_all(True)):
        if isinstance(tag, Tag) and _is_lead_qr_tag(tag):
            tag.decompose()
    body = soup.body if soup.body else soup
    return "".join(str(child) for child in body.children).strip()


def _configured_lead_qr_sources() -> list[str]:
    sources: list[str] = []
    for name in (
        "LEAD_QR_WECHAT_IMAGE_URL",
        "LEAD_QR_IMAGE_PATH",
        "LEAD_QR_IMAGE_URL",
        "WECHAT_LEAD_QR_IMAGE",
    ):
        value = os.getenv(name, "").strip()
        if value and value not in sources:
            sources.append(value)
    try:
        import config as app_config
        for name in (
            "LEAD_QR_WECHAT_IMAGE_URL",
            "LEAD_QR_IMAGE_PATH",
            "LEAD_QR_IMAGE_URL",
            "WECHAT_LEAD_QR_IMAGE",
        ):
            value = str(getattr(app_config, name, "") or "").strip()
            if value and value not in sources:
                sources.append(value)
    except Exception as exc:
        logger.warning("[publish-lead-qr-image-missing] failed to read qr config: %s", exc)
    return sources


def _qr_img_src_type(src: str) -> str:
    src = (src or "").strip()
    lower_src = src.lower()
    if not src:
        return "empty"
    if _is_wechat_content_image_url(src):
        return "wechat_url"
    if lower_src.startswith("data:"):
        return "base64"
    if lower_src.startswith(("http://", "https://")):
        return "external_url"
    if lower_src.startswith(("/", "static/")) or re.match(r"^[A-Za-z]:[\\/]", src):
        return "local_path"
    return "relative_path"


def _lead_qr_final_img_src(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for container in soup.find_all(True):
        if isinstance(container, Tag) and _is_lead_qr_tag(container):
            img = container.find("img") if container.name != "img" else container
            if isinstance(img, Tag):
                return str((img.get("src") or "")).strip()
    return ""


def build_lead_qr_html(qr_url: str) -> str:
    return _build_wechat_lead_qr_section(qr_url)

def _get_wechat_lead_qr_image_url(html_with_qr: str) -> tuple[str, bool, bool, str, str]:
    global _lead_qr_wechat_image_url_cache
    if _lead_qr_wechat_image_url_cache:
        if _is_wechat_content_image_url(_lead_qr_wechat_image_url_cache):
            return _lead_qr_wechat_image_url_cache, False, True, _lead_qr_wechat_image_url_cache, "wechat_url"
        logger.warning("[publish-lead-qr-image-missing] cached lead qr url is not a WeChat content image url")

    candidates: list[str] = []
    html_src = _find_lead_qr_img_src(html_with_qr)
    if html_src:
        candidates.append(html_src)
    for configured_src in _configured_lead_qr_sources():
        if configured_src not in candidates:
            candidates.append(configured_src)

    if not candidates:
        logger.warning("[publish-lead-qr-image-missing] lead qr image source is not configured")
        return "", False, False, "", "empty"

    for qr_src in candidates:
        src_type = _qr_img_src_type(qr_src)
        if src_type == "wechat_url":
            _lead_qr_wechat_image_url_cache = qr_src
            return qr_src, False, True, qr_src, src_type
        if src_type in {"empty", "base64", "relative_path"}:
            logger.warning("[publish-lead-qr-image-missing] unsupported lead qr img src_type=%s src=%s", src_type, qr_src)
            continue

        try:
            wechat_url = upload_content_image(qr_src)
        except WechatPublishError as exc:
            logger.warning("[publish-lead-qr-image-missing] lead qr uploadimg failed stage=%s errcode=%s errmsg=%s", exc.stage, exc.errcode, exc.errmsg)
            wechat_url = ""
        if not wechat_url:
            logger.warning("[publish-lead-qr-image-missing] lead qr uploadimg failed src_type=%s src=%s", src_type, qr_src)
            continue
        if not _is_wechat_content_image_url(wechat_url):
            logger.warning("[publish-lead-qr-image-missing] lead qr uploadimg returned non-WeChat url=%s", wechat_url)
            continue
        _lead_qr_wechat_image_url_cache = wechat_url
        logger.info("[wechat-draft-content] lead_qr_uploadimg_url=%s", wechat_url)
        return wechat_url, True, True, qr_src, src_type

    logger.warning("[publish-lead-qr-image-missing] no usable lead qr image source candidates=%s", len(candidates))
    return "", False, False, candidates[0] if candidates else "", _qr_img_src_type(candidates[0]) if candidates else "empty"

def _build_wechat_lead_qr_section(qr_url: str) -> str:
    if not qr_url:
        return ""
    soup = BeautifulSoup("", "html.parser")
    section = soup.new_tag("section")
    section["data-role"] = "lead-qr"
    section["data-lead-qr"] = "true"
    section["style"] = "margin:32px 0 0;padding:20px;text-align:center;background:#f6f9ff;border-radius:12px;"

    top = soup.new_tag("p")
    top["style"] = "font-size:16px;line-height:1.8;color:#1f2937;"
    top.string = "如果你最近准备申请经营贷、续贷、降息或提高额度，可以扫码做一次企业融资体检。"
    section.append(top)

    img = soup.new_tag("img", src=qr_url)
    img["alt"] = "企业融资体检二维码"
    img["style"] = "max-width:240px;width:240px;display:block;margin:16px auto;"
    section.append(img)

    bottom = soup.new_tag("p")
    bottom["style"] = "font-size:14px;line-height:1.8;color:#64748b;"
    bottom.string = "先看清楚自己属于：能批、难批、可优化，还是暂缓申请。"
    section.append(bottom)
    return str(section)


def _append_wechat_safe_lead_qr_at_end(html_with_qr: str) -> tuple[str, dict]:
    cleaned_html = _remove_lead_qr_blocks_for_publish(html_with_qr or "")
    qr_url, upload_used, upload_success, source_src, source_type = _get_wechat_lead_qr_image_url(html_with_qr or "")
    qr_html = _build_wechat_lead_qr_section(qr_url)
    meta = {
        "qr_img_src": qr_url,
        "qr_img_src_type": _qr_img_src_type(qr_url),
        "qr_source_src": source_src,
        "qr_source_src_type": source_type,
        "qr_upload_used": upload_used,
        "qr_upload_success": upload_success,
    }
    if not qr_html:
        return cleaned_html, meta
    return cleaned_html + qr_html, meta

def _mask_url_query_for_log(html: str) -> str:
    text = html or ""
    result = []
    i = 0
    while i < len(text):
        if text.startswith("http://", i) or text.startswith("https://", i):
            start = i
            while i < len(text) and text[i] not in " \n\r\t\"'<>":
                i += 1
            url = text[start:i]
            result.append(url.split("?", 1)[0] + "?[redacted]" if "?" in url else url)
        else:
            result.append(text[i])
            i += 1
    return "".join(result)

def _content_without_lead_qr(html: str) -> str:
    return _remove_lead_qr_blocks_for_publish(html or "")

def has_lead_qr(html: str) -> bool:
    if not html or not html.strip():
        return False
    soup = BeautifulSoup(html or "", "html.parser")
    if any(isinstance(tag, Tag) and _is_lead_qr_tag(tag) for tag in soup.find_all(True)):
        return True
    marker_text = soup.get_text(" ", strip=True)
    marker_attrs = " ".join(
        " ".join(str(value) for value in getattr(tag, "attrs", {}).values())
        for tag in soup.find_all(True)
    ).lower()
    if any(marker in marker_attrs for marker in ("lead-qr", "qrcode", "qr-code", "lead_qr")):
        return True
    if any(marker in marker_text for marker in ("企业融资体检", "扫码", "二维码")):
        return True
    for img in soup.find_all("img"):
        attrs = getattr(img, "attrs", {}) or {}
        img_text = " ".join(str(attrs.get(name, "")) for name in ("src", "alt", "class", "id")).lower()
        if any(marker in img_text for marker in ("qr", "qrcode", "lead", "二维码", "融资体检")):
            return True
    return False


def _lead_qr_index(html: str) -> int:
    positions = [
        (html or "").rfind("data-lead-qr"),
        (html or "").lower().rfind("lead-qr"),
        (html or "").lower().rfind("qrcode"),
        (html or "").rfind("融资体检"),
        (html or "").rfind("扫码"),
    ]
    return max(positions)


def _body_block_count(html: str) -> int:
    soup = BeautifulSoup(_content_without_lead_qr(html or ""), "html.parser")
    return len([tag for tag in soup.find_all(["p", "h2", "h3", "section"]) if isinstance(tag, Tag) and tag.get_text(" ", strip=True)])

def _plain_text_for_publish(html: str) -> str:
    return re.sub(r"\s+", " ", _strip_html(html or "")).strip()


def _paragraph_like_count(html: str) -> int:
    if not html:
        return 0
    if "<" not in html:
        return len([block for block in re.split(r"\n\s*\n+", html) if _plain_text_for_publish(block)])
    return _body_block_count(html)


def _looks_like_lead_only_text(text: str) -> bool:
    compact = re.sub(r"\s+", "", text or "")
    if not compact:
        return True
    marker_hits = sum(1 for marker in LEAD_ONLY_MARKERS if marker in compact)
    return marker_hits >= 2 and len(compact) < MIN_PUBLISH_TEXT_LENGTH


def _is_effective_article_body(raw_content: str) -> bool:
    text = _plain_text_for_publish(_content_without_lead_qr(raw_content or ""))
    if len(text) < MIN_PUBLISH_TEXT_LENGTH:
        return False
    if _paragraph_like_count(_content_without_lead_qr(raw_content or "")) < 3:
        return False
    return not _looks_like_lead_only_text(text)


def _title_keywords(title: str) -> list[str]:
    text = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", " ", title or "")
    words = [word for word in re.split(r"\s+", text) if len(word) >= 2]
    stop_words = {"老板", "文章", "标题", "这个", "哪些", "为什么", "怎么", "如何", "之前", "以后"}
    result: list[str] = []
    for word in words:
        if word not in stop_words and word not in result:
            result.append(word)
    return result[:6]


def _contains_article_signal(article: dict, content_html: str) -> bool:
    text = _plain_text_for_publish(_content_without_lead_qr(content_html or ""))
    keywords = _title_keywords(str(article.get("title") or ""))
    if keywords and any(keyword in text for keyword in keywords):
        return True
    if any(marker in text for marker in ("案例", "小标题", "解决", "建议", "风险", "申请", "银行", "经营贷")):
        return True
    return _paragraph_like_count(content_html) >= 3 and len(text) >= MIN_PUBLISH_TEXT_LENGTH


def _content_source_candidates(article: dict) -> list[tuple[str, str]]:
    return [
        ("html_content", str(article.get("html_content") or "").strip()),
        ("content", str(article.get("content") or "").strip()),
        ("body", str(article.get("body") or "").strip()),
    ]


def _select_article_publish_content(article: dict) -> tuple[str, str]:
    for source, value in _content_source_candidates(article):
        if value and _is_effective_article_body(value):
            return source, value
    raise ValueError("推送失败：未找到有效正文内容，无法推送到微信草稿箱。")


def get_article_publish_content(article: dict) -> str:
    """Return the best persisted body for publishing, preferring valid html_content/content/body."""
    return _select_article_publish_content(article)[1]


def _content_to_publish_html(article: dict, content: str, source: str) -> str:
    if source in {"content", "body"} and not str(content or "").lstrip().startswith("<"):
        return _render_original_html(
            article.get("title", ""),
            content,
            article.get("source_name", ""),
            category=article.get("category", ""),
        )
    return content or ""


def _save_wechat_publish_debug_html(article: dict, final_content: str) -> None:
    article_id = article.get("id", "unknown")
    debug_dirs = [PUBLISH_DEBUG_DIR]
    try:
        import tempfile
        fallback_dir = Path(tempfile.gettempdir())
        if fallback_dir not in debug_dirs:
            debug_dirs.append(fallback_dir)
    except Exception:
        pass
    last_error = None
    for debug_dir in debug_dirs:
        try:
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_path = debug_dir / f"wechat_publish_debug_article_{article_id}.html"
            debug_path.write_text(final_content or "", encoding="utf-8")
            logger.info("[wechat-draft-content] debug_html=%s", debug_path)
            return
        except Exception as exc:
            last_error = exc
    logger.warning("[wechat-draft-content] debug html save failed article_id=%s error=%s", article_id, last_error)

def _validate_wechat_final_content(article: dict, final_content: str, content_before_qr: str, qr_html_length: int) -> tuple[bool, str]:
    final_content = final_content or ""
    content_before_qr = content_before_qr or ""
    body_without_qr = _content_without_lead_qr(final_content)
    body_text = _plain_text_for_publish(body_without_qr)
    final_text = _plain_text_for_publish(final_content)
    body_ok = bool(body_text) and len(body_text) >= MIN_PUBLISH_TEXT_LENGTH and _paragraph_like_count(body_without_qr) >= 3
    qr_present = has_lead_qr(final_content)
    qr_img_src = _lead_qr_final_img_src(final_content)
    qr_img_src_type = _qr_img_src_type(qr_img_src)
    qr_img_ok = bool(qr_img_src) and qr_img_src_type == "wechat_url"
    effective_qr_present = qr_present and qr_img_ok and qr_html_length > 0 and len(final_content) > len(content_before_qr)
    if not final_content.strip() or not body_ok:
        return False, PUBLISH_CONTENT_ERROR_MESSAGE
    if len(final_text) <= MIN_PUBLISH_TEXT_LENGTH:
        return False, PUBLISH_CONTENT_ERROR_MESSAGE
    if _looks_like_lead_only_text(body_text):
        return False, PUBLISH_CONTENT_ERROR_MESSAGE
    if effective_qr_present and _lead_qr_index(final_content) < max(0, len(final_content) - 1800):
        return False, PUBLISH_CONTENT_ERROR_MESSAGE
    if not _contains_article_signal(article, body_without_qr):
        return False, PUBLISH_CONTENT_ERROR_MESSAGE
    if not qr_present:
        logger.warning(
            "[publish-final-content-missing-qr] article_id=%s title=%s final_content_length=%s",
            article.get("id", ""),
            article.get("title", ""),
            len(final_content),
        )
        return False, PUBLISH_MISSING_QR_ERROR_MESSAGE
    if not qr_img_ok:
        logger.warning(
            "[publish-lead-qr-image-missing] article_id=%s title=%s qr_img_src_type=%s qr_img_src=%s",
            article.get("id", ""),
            article.get("title", ""),
            qr_img_src_type,
            _mask_url_query_for_log(qr_img_src),
        )
        return False, PUBLISH_MISSING_QR_IMAGE_ERROR_MESSAGE
    return True, ""

def _log_wechat_content_debug(
    article: dict,
    original_content: str,
    content_before_qr: str,
    final_content: str,
    selected_source: str,
    qr_html_length: int,
    qr_meta: dict | None = None,
) -> None:
    qr_meta = qr_meta or {}
    safe_start = _mask_url_query_for_log((final_content or "")[:300])
    safe_end = _mask_url_query_for_log((final_content or "")[-800:])
    body_text = _plain_text_for_publish(_content_without_lead_qr(final_content or ""))
    has_body_text = len(body_text) >= MIN_PUBLISH_TEXT_LENGTH and _paragraph_like_count(_content_without_lead_qr(final_content or "")) >= 3
    lead_qr_text = _plain_text_for_publish(final_content or "")
    has_lead_qr_text = any(marker in lead_qr_text for marker in ("企业融资体检", "扫码", "二维码"))
    has_img_tag = bool(re.search(r"<img\b", final_content or "", flags=re.IGNORECASE))
    qr_img_src = qr_meta.get("qr_img_src") or _lead_qr_final_img_src(final_content or "")
    qr_img_src_type = qr_meta.get("qr_img_src_type") or _qr_img_src_type(qr_img_src)
    qr_present = has_lead_qr(final_content) and qr_html_length > 0 and len(final_content or "") > len(content_before_qr or "")
    logger.info(
        "[wechat-draft-content] article_id=%s title=%s selected_content_source=%s "
        "selected_content_length=%s qr_html_length=%s final_content_length=%s "
        "has_body_text=%s has_lead_qr=%s has_lead_qr_text=%s has_img_tag=%s "
        "qr_img_src=%s qr_img_src_type=%s qr_upload_used=%s qr_upload_success=%s "
        "final_content_start=%s final_content_end=%s",
        article.get("id", ""),
        article.get("title", ""),
        selected_source,
        len(original_content or ""),
        qr_html_length,
        len(final_content or ""),
        bool(has_body_text),
        bool(qr_present),
        bool(has_lead_qr_text),
        bool(has_img_tag),
        _mask_url_query_for_log(qr_img_src),
        qr_img_src_type,
        bool(qr_meta.get("qr_upload_used")),
        bool(qr_meta.get("qr_upload_success")),
        safe_start,
        safe_end,
    )

def _text_len_without_qr(html: str) -> int:
    return len(_plain_text_for_publish(_content_without_lead_qr(html or "")))


def _preserve_body_transform(label: str, before_html: str, after_html: str) -> str:
    before_len = _text_len_without_qr(before_html)
    after_len = _text_len_without_qr(after_html)
    if before_len >= MIN_PUBLISH_TEXT_LENGTH and after_len < max(MIN_PUBLISH_TEXT_LENGTH, before_len * 0.6):
        logger.warning(
            "[wechat-draft-content] %s shortened body too much, fallback before_text_len=%s after_text_len=%s",
            label,
            before_len,
            after_len,
        )
        return before_html
    return after_html

def _finalize_wechat_content_for_draft(article: dict, raw_content: str, selected_source: str = "") -> tuple[str, dict]:
    original_content = raw_content or ""
    raw_content = _content_to_publish_html(article, original_content, selected_source or "html_content")
    candidate = _strip_title_banner(raw_content)
    raw_content = _preserve_body_transform("strip_title_banner", raw_content, candidate)
    candidate = _strip_wechat_top_noise(raw_content)
    raw_content = _preserve_body_transform("strip_top_noise_before_adapt", raw_content, candidate)
    candidate = inject_article_image_into_html(
        raw_content,
        (article.get("cover_image") or article.get("cover_url") or "").strip(),
        alt_text=article.get("title", ""),
    )
    raw_content = _preserve_body_transform("inject_cover", raw_content, candidate)
    candidate = _fix_wechat_images(raw_content)
    raw_content = _preserve_body_transform("fix_images", raw_content, candidate)
    candidate = adapt_lead_form_to_wechat_card(raw_content)
    raw_content = _preserve_body_transform("adapt_lead_form", raw_content, candidate)
    candidate = adapt_html_for_wechat(raw_content)
    raw_content = _preserve_body_transform("adapt_html", raw_content, candidate)
    candidate = _strip_wechat_top_noise(raw_content)
    raw_content = _preserve_body_transform("strip_top_noise_after_adapt", raw_content, candidate)

    selected_body = _content_without_lead_qr(raw_content)
    draft_with_qr = append_lead_qr_at_end(raw_content)
    final_content, qr_meta = _append_wechat_safe_lead_qr_at_end(draft_with_qr)
    final_content = _upload_content_images_for_wechat(final_content)
    parsed_qr_img_src = _lead_qr_final_img_src(final_content)
    if parsed_qr_img_src:
        qr_meta["qr_img_src"] = parsed_qr_img_src
        qr_meta["qr_img_src_type"] = _qr_img_src_type(parsed_qr_img_src)
    else:
        qr_meta["qr_img_src"] = qr_meta.get("qr_img_src", "")
        qr_meta["qr_img_src_type"] = qr_meta.get("qr_img_src_type") or _qr_img_src_type(qr_meta.get("qr_img_src", ""))
    content_before_qr = _content_without_lead_qr(final_content)
    qr_html_length = max(0, len(final_content or "") - len(content_before_qr or ""))
    _log_wechat_content_debug(article, original_content, content_before_qr, final_content, selected_source, qr_html_length, qr_meta)
    if not qr_meta.get("qr_img_src"):
        logger.error("[wechat-draft-content-error] article_id=%s title=%s error=%s", article.get("id", ""), article.get("title", ""), PUBLISH_MISSING_QR_IMAGE_ERROR_MESSAGE)
        raise ValueError(PUBLISH_MISSING_QR_IMAGE_ERROR_MESSAGE)
    ok, error_message = _validate_wechat_final_content(article, final_content, selected_body, qr_html_length)
    if not ok:
        logger.error("[wechat-draft-content-error] article_id=%s title=%s error=%s", article.get("id", ""), article.get("title", ""), error_message)
        raise ValueError(error_message)
    _save_wechat_publish_debug_html(article, final_content)
    return final_content, qr_meta

def _guard_and_save_add_draft_payload(article: dict, final_content: str, qr_meta=None) -> str:
    content_before_qr = _content_without_lead_qr(final_content or "")
    qr_html_length = max(0, len(final_content or "") - len(content_before_qr or ""))
    ok, error_message = _validate_wechat_final_content(article, final_content, content_before_qr, qr_html_length)
    if not ok:
        meta_has_qr_img = bool((qr_meta or {}).get("qr_img_src"))
        if not (meta_has_qr_img and error_message == PUBLISH_MISSING_QR_IMAGE_ERROR_MESSAGE):
            logger.error("[wechat-draft-content-error] article_id=%s title=%s error=%s", article.get("id", ""), article.get("title", ""), error_message)
            raise ValueError(error_message)
    _save_wechat_publish_debug_html(article, final_content)
    return final_content or ""

def _validate_publish_payload_before_add_draft(article: dict, thumb_media_id: str, final_content: str, qr_meta=None) -> None:
    validate_wechat_config()
    if not thumb_media_id:
        raise WechatPublishError("cover_upload", "封面图上传失败，缺少 thumb_media_id，无法推送草稿箱")
    if not final_content or not final_content.strip():
        raise WechatPublishError("add_draft", "final_content 为空，无法推送草稿箱")

    body_without_qr = _content_without_lead_qr(final_content)
    body_text = _plain_text_for_publish(body_without_qr)
    if not body_text or len(body_text) < MIN_PUBLISH_TEXT_LENGTH:
        raise WechatPublishError("add_draft", "final_content 缺少正文，无法推送草稿箱")
    if not _contains_article_signal(article, body_without_qr):
        raise WechatPublishError("add_draft", "final_content 未检测到正文内容，无法推送草稿箱")

    qr_present = has_lead_qr(final_content)
    qr_img_src = ""
    if qr_meta:
        qr_img_src = qr_meta.get("qr_img_src", "")
    if not qr_img_src:
        qr_img_src = _lead_qr_final_img_src(final_content)
    logger.info(
        "[publish-qr-final-check] article_id=%s qr_meta_exists=%s qr_img_src=%s qr_img_src_type=%s",
        article.get("id", ""),
        bool(qr_meta),
        _mask_url_query_for_log(qr_img_src),
        _qr_img_src_type(qr_img_src),
    )
    if not qr_img_src:
        raise WechatPublishError("add_draft", "final_content 缺少二维码 img，无法推送草稿箱")
    if PUBLISH_REQUIRE_LEAD_QR and not qr_present:
        raise WechatPublishError("add_draft", "final_content 缺少二维码 img，无法推送草稿箱")

    logger.info(
        "[publish-content-final] article_id=%s final_content_length=%s body_text_length=%s thumb_media_id_present=%s qr_present=%s qr_img_present=%s",
        article.get("id", ""),
        len(final_content or ""),
        len(body_text),
        bool(thumb_media_id),
        bool(qr_present),
        bool(qr_img_src),
    )


def _save_and_log_final_wechat_send(article: dict, final_content: str) -> None:
    """Persist and verify the exact HTML that will be sent to add_draft."""
    qr_img_src = _lead_qr_final_img_src(final_content)
    qr_present = has_lead_qr(final_content)
    has_img_tag = bool(re.search(r"<img\b", final_content or "", flags=re.IGNORECASE))
    logger.info(
        "[wechat-final-send] article_id=%s content_length=%s has_lead_qr=%s "
        "has_img_tag=%s qr_img_src=%s qr_img_src_type=%s",
        article.get("id", ""),
        len(final_content or ""),
        bool(qr_present),
        bool(has_img_tag),
        _mask_url_query_for_log(qr_img_src),
        _qr_img_src_type(qr_img_src),
    )
    if not qr_present or not qr_img_src:
        raise WechatPublishError("add_draft", "final_content 缺少二维码 img，禁止推送草稿箱")
    assert has_lead_qr(final_content)
    assert _lead_qr_final_img_src(final_content)

    send_dir = PUBLISH_DEBUG_DIR if os.name != "nt" else Path(os.getenv("TEMP") or os.getenv("TMP") or str(PUBLISH_DEBUG_DIR))
    send_path = send_dir / f"wechat_final_send_article_{article.get('id', '')}.html"
    try:
        send_path.parent.mkdir(parents=True, exist_ok=True)
        send_path.write_text(final_content, encoding="utf-8")
    except Exception as exc:
        raise WechatPublishError("add_draft", f"最终发送内容保存失败，禁止推送草稿箱: {exc}") from exc


def publish_single_article(article: dict, auto_submit: bool = False) -> str:
    """
    将单篇文章推送到微信草稿箱
    返回: media_id 或 None

    内容优先级（保证推送与预览一致）：
      1. article["html_content"] — 数据库已存的格式化HTML（最优先，不做任何修改）
      2. article["content"]       — 如果已经是HTML格式（<div开头）直接使用
      3. 以上都没有 → 调用 process_article() 生成兜底内容（仅此情况走AI）
    """
    try:
        logger.info("[publish-start] article_id=%s title=%s", article.get("id", ""), article.get("title", ""))
        validate_wechat_config()
        # ════════════════════════════════════════
        # 步骤1：确定推送内容（优先用已存储的格式化结果）
        # ════════════════════════════════════════
        selected_source, selected_content = _select_article_publish_content(article)
        logger.info(
            "[Publish] selected publish content source=%s length=%s",
            selected_source,
            len(selected_content),
        )
        draft_title = _truncate_title(article.get("title", "Untitled"))
        # 上传封面图（无封面时自动使用默认封面）
        thumb_media_id = ensure_thumb_media_id(article.get("cover_image"), article.get("cover_url"))
        final_content, qr_meta = _finalize_wechat_content_for_draft(article, selected_content, selected_source)
        article["_qr_meta"] = qr_meta

        if not thumb_media_id:
            raise WechatPublishError("cover_upload", "封面图上传失败，缺少 thumb_media_id，无法推送草稿箱")

        # 构建草稿payload
        draft_title = _truncate_title(draft_title)
        author_name = article.get("author") or DEFAULT_WECHAT_AUTHOR

        draft_digest = article.get("summary") or ""
        logger.info("[wechat-draft] digest=%s", draft_digest)
        final_content = _guard_and_save_add_draft_payload(article, final_content, article.get("_qr_meta"))
        _validate_publish_payload_before_add_draft(article, thumb_media_id, final_content, article.get("_qr_meta"))
        draft_article = {
            "title": draft_title,
            "author": author_name,
            "digest": draft_digest,
            "content": final_content,
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 1,
        }

        _save_and_log_final_wechat_send(article, draft_article["content"])
        media_id = add_draft([draft_article])
        if media_id and auto_submit:
            submit_draft_for_review(media_id)

        logger.info(f"[Publish] 「{article['title']}」推送草稿成功 media_id={media_id}")
        return media_id
    except WechatPublishError as e:
        logger.error("[publish-error] article_id=%s title=%s stage=%s errcode=%s errmsg=%s error=%s", article.get("id", ""), article.get("title", ""), e.stage, e.errcode, e.errmsg, e)
        raise
    except ValueError as e:
        logger.error(f"[Publish] 「{article['title']}」发布失败: {e}")
        return None
    except Exception as e:
        logger.error(f"[Publish] 「{article['title']}」发布失败: {e}")
        return None


def publish_approved_articles(auto_submit=False) -> int:
    """
    将所有 approved 状态文章推送为微信草稿
    auto_submit: 是否自动提交发布（False=只推草稿，True=直接群发）
    返回: 成功数量
    """
    conn = get_db()
    cursor = conn.cursor()

    rows = _select_approved_articles(cursor)

    success = 0
    for row in rows:
        article = dict(row)
        try:
            logger.info("[publish-start] article_id=%s title=%s", article.get("id", ""), article.get("title", ""))
            validate_wechat_config()
            # ════════════════════════════════════════
            # 内容优先级：html_content > content(HTML) > AI处理
            # ════════════════════════════════════════
            selected_source, selected_content = _select_article_publish_content(article)
            logger.info(
                "[Publish] selected publish content source=%s length=%s",
                selected_source,
                len(selected_content),
            )
            draft_title = _truncate_title(article.get("title", "Untitled"))
            # 上传封面图（无封面时自动使用默认封面）
            thumb_media_id = ensure_thumb_media_id(article.get("cover_image"), article.get("cover_url"))
            final_content, qr_meta = _finalize_wechat_content_for_draft(article, selected_content, selected_source)
            article["_qr_meta"] = qr_meta

            if not thumb_media_id:
                raise WechatPublishError("cover_upload", "封面图上传失败，缺少 thumb_media_id，无法推送草稿箱")

            # 构建草稿payload（注意：上面已经确定了 draft_title / final_content）
            author_name = article.get("author") or DEFAULT_WECHAT_AUTHOR

            draft_digest = article.get("summary") or ""
            logger.info("[wechat-draft] digest=%s", draft_digest)
            final_content = _guard_and_save_add_draft_payload(article, final_content, article.get("_qr_meta"))
            _validate_publish_payload_before_add_draft(article, thumb_media_id, final_content, article.get("_qr_meta"))
            draft_article = {
                "title": draft_title,
                "author": author_name,
                "digest": draft_digest,
                "content": final_content,
                "thumb_media_id": thumb_media_id,
                "need_open_comment": 1,
            }

            _save_and_log_final_wechat_send(article, draft_article["content"])
            media_id = add_draft([draft_article])
            if media_id:
                update_status = STATUS_PUBLISHED if auto_submit else STATUS_DRAFT_SENT
                review_status, publish_status = split_legacy_status(update_status)
                _update_article_publish_status(
                    cursor,
                    article["id"],
                    update_status,
                    review_status,
                    publish_status,
                    media_id,
                )
                if auto_submit:
                    submit_draft_for_review(media_id)
                conn.commit()
                success += 1
                logger.info(f"[Publish] 「{article['title']}」推送草稿成功 media_id={media_id}")
        except Exception as e:
            logger.error("[publish-error] article_id=%s title=%s error=%s", article.get("id", ""), article.get("title", ""), e)
            review_status, publish_status = split_legacy_status(STATUS_ERROR)
            _mark_article_publish_error(
                cursor,
                article["id"],
                review_status,
                publish_status,
            )
            conn.commit()

    conn.close()
    logger.info(f"[Publish] 本次共发布 {success} 篇")
    return success
