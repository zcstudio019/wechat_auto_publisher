"""
发布任务：将数据库中 approved 状态的文章推送为微信草稿
"""
import logging
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db, is_mysql
from domain.article_status import (
    STATUS_APPROVED,
    STATUS_DRAFT_SENT,
    STATUS_ERROR,
    STATUS_PUBLISHED,
    split_legacy_status,
)
from ai_processor.processor import process_article
from services.wechat_html_adapter import adapt_html_for_wechat
from services.wechat_lead_card_adapter import adapt_lead_form_to_wechat_card
from .client import ensure_thumb_media_id, add_draft, submit_draft_for_review

logger = logging.getLogger(__name__)

# 微信草稿字段限制（实测值，非官方文档值）
WECHAT_TITLE_MAX_BYTES = 30        # 标题上限（字节）：30通过/33失败
WECHAT_AUTHOR_MAX_BYTES = 8        # 作者上限（字节）：7通过/9失败
WECHAT_DIGEST_MAX_BYTES = 60        # 摘要上限（字节）：实测纯中文20字=60字节通过，21字=63字节失败。官方文档称120字符，实际远严于此。
WECHAT_CONTENT_MAX_BYTES = 20000   # 正文上限（字节）


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
    """按字节截断标题，确保不超过微信限制"""
    if not title:
        return "Untitled"
    return _truncate_bytes(title, max_bytes)


def _make_digest(summary: str, content: str, max_bytes: int = WECHAT_DIGEST_MAX_BYTES) -> str:
    """
    生成纯文本摘要（按字节截断）。
    实测微信 digest 限制为 60 字节（约20个中文字），远严于官方文档的120字符。
    """
    text = _strip_html(summary) if summary else ""
    if not text and content:
        plain = _strip_html(content)
        lines = [l.strip() for l in plain.split('\n') if l.strip()][:3]
        text = ' '.join(lines)

    # 按字节截断（兼容中英文混合）
    return _truncate_bytes(text or "沪上银贷款服务", max_bytes)











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
        # ════════════════════════════════════════
        # 步骤1：确定推送内容（优先用已存储的格式化结果）
        # ════════════════════════════════════════
        stored_html = (article.get("html_content") or "").strip()
        stored_content = (article.get("content") or "").strip()

        if stored_html:
            # 情况A：已有格式化HTML → 直接使用，不走AI（保证与预览页一致）
            raw_content = stored_html
            logger.info(f"[Publish] 使用已存储的 html_content ({len(stored_html)} chars)")
        elif stored_content and stored_content.strip().startswith("<"):
            # 情况B：content 字段存的是HTML（旧文章兼容）→ 直接使用
            raw_content = stored_content
            logger.info(f"[Publish] 使用 content 字段的 HTML ({len(stored_content)} chars)")
        else:
            # 情况C：没有任何格式化内容 → 调用AI处理（兜底）
            logger.warning(f"[Publish] 无已存储HTML，将重新AI处理（可能与预览不一致）")
            processed = process_article(article)
            raw_content = processed.get("html_content", "") or ""

        # 仅在走了 AI 兜底路径时才用 optimize_title；否则保持原标题不变
        if stored_html or (stored_content and stored_content.strip().startswith("<")):
            draft_title = article.get("title", "Untitled")
            summary_text = article.get("summary", "")
        else:
            # AI路径：标题可能被优化过，需要截断
            if 'processed' not in dir():
                processed = process_article(article)
            draft_title = _truncate_title(processed.get("title", article.get("title", "Untitled")))
            summary_text = processed.get("summary", "")

        # 推送前移除正文开头的品牌标题横幅（微信已有封面+标题，横幅在草稿箱里显示太大）
        raw_content = _strip_title_banner(raw_content)
        # 推送前将外链图片（picsum等）替换为纯CSS渐变色块（微信不支持外链图片）
        raw_content = _fix_wechat_images(raw_content)
        # 推送到公众号前，把后台可交互留资表单替换为公众号兼容的静态咨询入口卡片。
        raw_content = adapt_lead_form_to_wechat_card(raw_content)
        # 最终提交微信前转为公众号兼容 HTML，降低草稿箱清洗后排版失真的概率。
        raw_content = adapt_html_for_wechat(raw_content)

        # 上传封面图（无封面时自动使用默认封面）
        thumb_media_id = ensure_thumb_media_id(article.get("cover_image"), article.get("cover_url"))

        if not thumb_media_id:
            logger.error(f"[Publish] 文章「{article['title']}」无法获取任何封面 media_id")
            return None

        # 构建草稿payload
        draft_title = _truncate_title(draft_title)
        digest = _make_digest(summary_text, raw_content)
        author_name = _truncate_bytes("沪上银", WECHAT_AUTHOR_MAX_BYTES)

        content_bytes = len(raw_content.encode('utf-8'))
        if content_bytes > WECHAT_CONTENT_MAX_BYTES:
            raw_content = _truncate_bytes(raw_content, WECHAT_CONTENT_MAX_BYTES)
            logger.warning(f"[Publish] 正文超长({content_bytes}字节)，截断到{WECHAT_CONTENT_MAX_BYTES}字节")

        draft_article = {
            "title": draft_title,
            "author": author_name,
            "digest": digest,
            "content": raw_content,
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 1,
        }

        media_id = add_draft([draft_article])
        if media_id and auto_submit:
            submit_draft_for_review(media_id)

        logger.info(f"[Publish] 「{article['title']}」推送草稿成功 media_id={media_id}")
        return media_id
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
            # ════════════════════════════════════════
            # 内容优先级：html_content > content(HTML) > AI处理
            # ════════════════════════════════════════
            stored_html = (article.get("html_content") or "").strip()
            stored_content = (article.get("content") or "").strip()

            if stored_html:
                raw_content = stored_html
                use_ai = False
            elif stored_content and stored_content.strip().startswith("<"):
                raw_content = stored_content
                use_ai = False
            else:
                processed = process_article(article)
                raw_content = processed.get("html_content", "") or ""
                use_ai = True

            # 标题处理
            if not use_ai:
                draft_title = _truncate_title(article.get("title", "Untitled"))
                summary_text = article.get("summary", "")
            else:
                draft_title = _truncate_title(processed["title"])
                summary_text = processed.get("summary", "")

            # 推送前移除正文开头的品牌标题横幅
            raw_content = _strip_title_banner(raw_content)
            # 推送前将外链图片替换为纯CSS渐变色块
            raw_content = _fix_wechat_images(raw_content)
            # 推送到公众号前，把后台可交互留资表单替换为公众号兼容的静态咨询入口卡片。
            raw_content = adapt_lead_form_to_wechat_card(raw_content)
            # 最终提交微信前转为公众号兼容 HTML，后台预览 HTML 不写回数据库。
            raw_content = adapt_html_for_wechat(raw_content)

            # 上传封面图（无封面时自动使用默认封面）
            thumb_media_id = ensure_thumb_media_id(article.get("cover_image"), article.get("cover_url"))

            if not thumb_media_id:
                logger.error(f"[Publish] 文章「{article['title']}」无法获取封面，跳过")
                continue

            # 构建草稿payload（注意：上面已经确定了 draft_title / raw_content）
            digest = _make_digest(summary_text, raw_content)
            author_name = _truncate_bytes("沪上银", WECHAT_AUTHOR_MAX_BYTES)

            content_bytes = len(raw_content.encode('utf-8'))
            if content_bytes > WECHAT_CONTENT_MAX_BYTES:
                raw_content = _truncate_bytes(raw_content, WECHAT_CONTENT_MAX_BYTES)
                logger.warning(f"[Publish] 正文超长({content_bytes}字节)，截断到{WECHAT_CONTENT_MAX_BYTES}字节")

            draft_article = {
                "title": draft_title,
                "author": author_name,
                "digest": digest,
                "content": raw_content,
                "thumb_media_id": thumb_media_id,
                "need_open_comment": 1,
            }

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
            logger.error(f"[Publish] 「{article['title']}」发布失败: {e}")
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
