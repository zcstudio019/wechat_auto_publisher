"""AI 封面图生成模块。

职责：
1. 根据文章标题、摘要和行业风格拼接微信公众号封面 Prompt
2. 调用 OpenAI gpt-image-2 生成图片
3. 将结果保存到本地 static/generated_covers 目录
4. 返回可直接写入 articles 表的封面字段
"""

import base64
import hashlib
import logging
import re
import time
import urllib.request
from pathlib import Path

from config import BASE_DIR, OPENAI_IMAGE_API_KEY, OPENAI_IMAGE_BASE_URL, OPENAI_IMAGE_MODEL

logger = logging.getLogger(__name__)

_client = None
if OPENAI_IMAGE_API_KEY:
    try:
        from openai import OpenAI

        _client = OpenAI(api_key=OPENAI_IMAGE_API_KEY, base_url=OPENAI_IMAGE_BASE_URL)
    except Exception as exc:  # pragma: no cover
        logger.warning("[Cover] OpenAI 图片客户端初始化失败: %s", exc)


GENERATED_COVER_DIR = Path(BASE_DIR) / "web_ui" / "static" / "generated_covers"
MAX_PROMPT_SUMMARY_LENGTH = 180
MAX_PROMPT_BODY_LENGTH = 300


def _slugify_title(title: str) -> str:
    """将标题转换为适合文件名的安全片段。"""
    safe_title = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", (title or "").strip())
    safe_title = re.sub(r"_+", "_", safe_title).strip("_")
    return safe_title[:24] or "cover"


def infer_cover_style(title: str, summary: str = "", style: str = "") -> str:
    """根据文章主题推断封面风格。"""
    if style:
        return style.strip()

    text = f"{title} {summary}".lower()
    if any(keyword in text for keyword in ["贷款", "融资", "助贷", "征信", "放款", "银行"]):
        return "金融行业公众号封面，高级商务风，深蓝金色，可信赖感强"
    if any(keyword in text for keyword in ["经营", "企业", "现金流", "营收"]):
        return "企业经营分析封面，专业咨询风，深蓝绿色，稳重理性"
    if any(keyword in text for keyword in ["案例", "复盘", "故事"]):
        return "真实案例封面，商务纪实风，层次感强，视觉聚焦"
    return "微信公众号封面，专业清晰，商务感强，简洁高级"


def _build_cover_prompt_legacy(title: str, summary: str = "", style: str = "", mode: str = "cover") -> str:
    """拼接适合微信公众号封面的高质量 Prompt。"""
    safe_title = (title or "").strip()
    safe_summary = (summary or "").strip()
    if len(safe_summary) > MAX_PROMPT_SUMMARY_LENGTH:
        safe_summary = safe_summary[:MAX_PROMPT_SUMMARY_LENGTH]

    industry_style = infer_cover_style(safe_title, safe_summary, style)
    mode_text = "朋友圈营销海报" if mode == "poster" else "微信公众号文章封面图"

    prompt_parts = [
        f"{mode_text}设计",
        industry_style,
        "横版构图，16:9 比例，适合公众号封面点击率",
        "主体集中，层次清晰，留白合理，适合移动端首屏浏览",
        "突出标题主题含义，但不要在图片中生成任何中文或英文文字",
        "不要乱码，不要水印，不要 Logo，不要二维码",
        "高级商务感，适合金融、融资、贷款、助贷行业传播",
        f"主题标题含义：{safe_title}",
    ]
    if safe_summary:
        prompt_parts.append(f"文章摘要关键信息：{safe_summary}")
    prompt_parts.append("画面干净、专业、可信赖、质感高级、利于传播")
    return "，".join(part for part in prompt_parts if part)


def _strip_html_text(text: str) -> str:
    """Reduce HTML/markdown snippets to plain text for image prompting."""
    stripped = re.sub(r"<[^>]+>", " ", text or "")
    stripped = re.sub(r"\s+", " ", stripped)
    return stripped.strip()


def _infer_scene_guidance(context_text: str) -> str:
    """Return a focused visual scene based on the article theme."""
    text = (context_text or "").lower()
    if any(keyword in text for keyword in ["现金流", "周转", "资金压力", "资金链"]):
        return "画面表现企业老板查看现金流报表、办公室决策场景、资金流动与稳健规划感。"
    if any(keyword in text for keyword in ["贷款申请", "材料准备", "被拒", "拒贷", "征信", "申请失败"]):
        return "画面表现企业资料、合同、征信报告与顾问分析，不制造夸张焦虑。"
    if any(keyword in text for keyword in ["融资规划", "资金规划", "融资节奏", "预算安排"]):
        return "画面表现企业资金路线图、老板与顾问讨论方案、稳健增长阶梯。"
    if any(keyword in text for keyword in ["经营分析", "利润", "成本", "应收账款", "负债结构", "财务报表"]):
        return "画面表现财务报表、成本利润分析、经营仪表盘与结构化判断。"
    if any(keyword in text for keyword in ["品牌宣传", "顾问团队", "品牌", "服务案例"]):
        return "画面表现专业顾问团队、商务咨询场景与可信服务感。"
    return "画面围绕文章核心问题构建具体业务场景，不要生成泛化商业图库风。"


def build_cover_prompt(
    title: str,
    summary: str = "",
    style: str = "",
    mode: str = "cover",
    category: str = "",
    tags: str = "",
    body_preview: str = "",
) -> str:
    """Build a theme-bound prompt for mid-article images."""
    safe_title = (title or "").strip()
    safe_summary = (summary or "").strip()
    if len(safe_summary) > MAX_PROMPT_SUMMARY_LENGTH:
        safe_summary = safe_summary[:MAX_PROMPT_SUMMARY_LENGTH]
    safe_category = (category or "").strip()
    safe_tags = (tags or "").strip()
    safe_body_preview = _strip_html_text(body_preview)
    if len(safe_body_preview) > MAX_PROMPT_BODY_LENGTH:
        safe_body_preview = safe_body_preview[:MAX_PROMPT_BODY_LENGTH]

    industry_style = infer_cover_style(safe_title, safe_summary, style)
    mode_text = "朋友圈营销海报" if mode == "poster" else "微信公众号正文中段配图"
    scene_guidance = _infer_scene_guidance(
        " ".join(part for part in [safe_title, safe_summary, safe_category, safe_tags, safe_body_preview] if part)
    )

    prompt_parts = [
        f"{mode_text}设计",
        industry_style,
        "16:9 横向构图，适合公众号正文中段阅读，不做夸张大海报。",
        "目标读者：企业老板 / 小微企业主。行业定位：企业融资顾问、资金规划、助贷服务。",
        "图片必须紧扣文章主题，不要生成无关商业大图。",
        "画面高级商务、可信、克制、干净，主体明确，留白合理，适合移动端阅读。",
        "不要出现乱码文字、可读文字、水印、Logo、二维码。",
        "不要生成品牌名、城市名、贷款顾问、副标题或 slogan。",
        "不要出现具体贷款利率，不要暗示包过、秒批、低息、无视征信等违规金融承诺。",
        scene_guidance,
        f"文章标题：{safe_title}",
    ]
    if safe_summary:
        prompt_parts.append(f"文章摘要：{safe_summary}")
    if safe_category:
        prompt_parts.append(f"文章分类：{safe_category}")
    if safe_tags:
        prompt_parts.append(f"关键词标签：{safe_tags}")
    if safe_body_preview:
        prompt_parts.append(f"正文前 300 字要点：{safe_body_preview}")
    prompt_parts.append("最终画面应表达文章核心场景，而不是泛化商业背景图。")
    return "；".join(part for part in prompt_parts if part)


def _save_base64_image(image_b64: str, title: str) -> tuple[str, str]:
    """保存 base64 图片到本地，并返回绝对路径和静态访问路径。"""
    GENERATED_COVER_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.md5(f"{title}-{time.time()}".encode("utf-8")).hexdigest()[:10]
    filename = f"{time.strftime('%Y%m%d_%H%M%S')}_{_slugify_title(title)}_{digest}.png"
    file_path = GENERATED_COVER_DIR / filename
    file_path.write_bytes(base64.b64decode(image_b64))
    web_path = f"/static/generated_covers/{filename}"
    return str(file_path), web_path


def _save_remote_image(image_url: str, title: str) -> tuple[str, str]:
    """下载远程图片并保存到本地。"""
    GENERATED_COVER_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.md5(f"{title}-{time.time()}-{image_url}".encode("utf-8")).hexdigest()[:10]
    filename = f"{time.strftime('%Y%m%d_%H%M%S')}_{_slugify_title(title)}_{digest}.png"
    file_path = GENERATED_COVER_DIR / filename
    with urllib.request.urlopen(image_url, timeout=60) as response:
        file_path.write_bytes(response.read())
    web_path = f"/static/generated_covers/{filename}"
    return str(file_path), web_path


def _is_non_retryable_error(error_message: str) -> bool:
    """判断是否属于不需要继续重试的永久性错误。"""
    lowered = (error_message or "").lower()
    keywords = [
        "organization must be verified",
        "invalid_request_error",
        "insufficient_quota",
        "billing",
        "model_not_found",
        "does not exist",
        "permission",
    ]
    return any(keyword in lowered for keyword in keywords)


def generate_cover_image(
    title: str,
    summary: str = "",
    style: str = "",
    mode: str = "cover",
    category: str = "",
    tags: str = "",
    body_preview: str = "",
) -> dict:
    """生成封面图并返回可直接落库的数据。"""
    prompt = build_cover_prompt(
        title=title,
        summary=summary,
        style=style,
        mode=mode,
        category=category,
        tags=tags,
        body_preview=body_preview,
    )

    if not OPENAI_IMAGE_API_KEY or _client is None:
        logger.info("[Cover] 未配置 OPENAI_IMAGE_API_KEY，跳过封面生成: %s", title)
        return {
            "ok": False,
            "status": "skipped",
            "file_path": "",
            "cover_image": "",
            "cover_prompt": prompt,
            "error": "",
        }

    last_error = ""
    for attempt in range(1, 4):
        try:
            try:
                response = _client.images.generate(
                    model=OPENAI_IMAGE_MODEL,
                    prompt=prompt,
                    size="1536x1024",
                    quality="high",
                    output_format="png",
                    background="opaque",
                )
            except TypeError:
                # 兼容部分较旧的 SDK 参数集
                response = _client.images.generate(
                    model=OPENAI_IMAGE_MODEL,
                    prompt=prompt,
                    size="1536x1024",
                )

            image_b64 = ""
            image_url = ""
            response_data = getattr(response, "data", None)
            if response_data is None and isinstance(response, dict):
                response_data = response.get("data")
            first_item = response_data[0] if isinstance(response_data, (list, tuple)) and response_data else None
            if isinstance(first_item, dict):
                image_b64 = first_item.get("b64_json", "") or ""
                image_url = first_item.get("url", "") or ""
            elif first_item is not None:
                image_b64 = getattr(first_item, "b64_json", "") or ""
                image_url = getattr(first_item, "url", "") or ""
            logger.info("[image-response-debug] model=%s has_data=%s has_b64=%s has_url=%s", OPENAI_IMAGE_MODEL, bool(response_data), bool(image_b64), bool(image_url))

            if image_b64:
                file_path, cover_image = _save_base64_image(image_b64, title)
            elif image_url:
                file_path, cover_image = _save_remote_image(image_url, title)
            else:
                raise RuntimeError("图片接口未返回 base64 数据")
            logger.info("[Cover] 封面生成成功: %s -> %s", title, cover_image)
            return {
                "ok": True,
                "status": "success",
                "file_path": file_path,
                "cover_image": cover_image,
                "cover_prompt": prompt,
                "error": "",
            }
        except Exception as exc:  # pragma: no cover
            last_error = str(exc)
            logger.warning("[Cover-warning] 第 %s 次生成失败，已保留文章保存流程: %s", attempt, exc)
            if _is_non_retryable_error(last_error):
                break
            time.sleep(1)

    return {
        "ok": False,
        "status": "failed",
        "file_path": "",
        "cover_image": "",
        "cover_prompt": prompt,
        "error": last_error,
    }


def generate_cover_for_article(article: dict, style: str = "", mode: str = "cover") -> dict:
    """根据文章对象生成封面，并返回可直接写回文章的字段。"""
    result = generate_cover_image(
        title=(article or {}).get("title", ""),
        summary=(article or {}).get("summary", ""),
        style=style or (article or {}).get("tags", ""),
        mode=mode,
        category=(article or {}).get("category", ""),
        tags=(article or {}).get("tags", ""),
        body_preview=(article or {}).get("html_content") or (article or {}).get("content", ""),
    )
    return {
        "cover_image": result.get("cover_image", ""),
        "cover_url": result.get("cover_image", ""),
        "cover_status": result.get("status", "pending"),
        "cover_prompt": result.get("cover_prompt", ""),
        "cover_error": result.get("error", ""),
        "cover_file_path": result.get("file_path", ""),
    }
