"""
微信公众号 API 封装
- 获取 access_token
- 上传封面图片素材（含自动生成默认封面）
- 新增草稿
- 发布草稿（群发）
- 获取草稿列表
"""
import json
import logging
import time
import io
import requests
import os
from pathlib import Path
import sys
import struct
import zlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BASE_DIR, WECHAT_APP_ID, WECHAT_APP_SECRET

logger = logging.getLogger(__name__)

# access_token 缓存
_token_cache = {"token": "", "expire_at": 0}

# 默认封面的 media_id 缓存（避免重复上传）
_default_thumb_cache = {"media_id": None}  # 设为 None 可强制重新生成（改尺寸后需清缓存）

WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"


def _request_without_env_proxy(method: str, url: str, **kwargs):
    """微信相关请求忽略系统代理，避免坏代理导致接口完全无法连接。"""
    session = requests.Session()
    session.trust_env = False
    try:
        return session.request(method, url, **kwargs)
    finally:
        session.close()


def _http_get(url: str, **kwargs):
    """GET 请求封装，统一绕开失效环境代理。"""
    return _request_without_env_proxy("GET", url, **kwargs)


def _http_post(url: str, **kwargs):
    """POST 请求封装，统一绕开失效环境代理。"""
    return _request_without_env_proxy("POST", url, **kwargs)


def get_access_token(force_refresh=False) -> str:
    """获取（或刷新）access_token"""
    global _token_cache
    now = time.time()
    if not force_refresh and _token_cache["token"] and now < _token_cache["expire_at"] - 60:
        return _token_cache["token"]

    url = f"{WECHAT_API_BASE}/token"
    params = {
        "grant_type": "client_credential",
        "appid": WECHAT_APP_ID,
        "secret": WECHAT_APP_SECRET,
    }
    resp = _http_get(url, params=params, timeout=10)
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"获取access_token失败: {data}")

    _token_cache["token"] = data["access_token"]
    _token_cache["expire_at"] = now + data.get("expires_in", 7200)
    logger.info("[WeChat] access_token 已刷新")
    return _token_cache["token"]


def _guess_mime_from_name(filename: str) -> tuple[str, str]:
    """根据文件名推断上传文件名与 MIME。"""
    lower_name = (filename or "").lower()
    if lower_name.endswith(".png"):
        return "cover.png", "image/png"
    if lower_name.endswith(".webp"):
        return "cover.webp", "image/webp"
    if lower_name.endswith(".gif"):
        return "cover.gif", "image/gif"
    return "cover.jpg", "image/jpeg"


def _resolve_local_image_path(image_source: str) -> Path | None:
    """将本地封面路径或 /static 路径转换为绝对文件路径。"""
    if not image_source:
        return None

    source = image_source.strip().replace("\\", "/")
    if source.startswith("/static/"):
        return Path(BASE_DIR) / "web_ui" / source.lstrip("/")
    if source.startswith("static/"):
        return Path(BASE_DIR) / "web_ui" / source

    path = Path(image_source)
    if path.is_absolute():
        return path
    return Path(BASE_DIR) / image_source


def upload_image(image_source: str) -> str | None:
    """上传远程图片或本地生成图片到微信永久素材库。"""
    if not image_source:
        return None

    try:
        image_bytes = b""
        filename = "cover.jpg"
        content_type = "image/jpeg"

        if image_source.startswith("http://") or image_source.startswith("https://"):
            resp = _http_get(image_source, timeout=15)
            resp.raise_for_status()
            image_bytes = resp.content
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            filename, content_type = _guess_mime_from_name(image_source)
            if "png" in resp.headers.get("Content-Type", ""):
                filename, content_type = ("cover.png", "image/png")
        else:
            local_path = _resolve_local_image_path(image_source)
            if not local_path or not local_path.exists():
                logger.warning("[WeChat] 本地封面不存在: %s", image_source)
                return None
            image_bytes = local_path.read_bytes()
            filename, content_type = _guess_mime_from_name(local_path.name)

        token = get_access_token()
        url = f"{WECHAT_API_BASE}/material/add_material?access_token={token}&type=image"
        files = {"media": (filename, image_bytes, content_type)}
        upload_resp = _http_post(url, files=files, timeout=20)
        data = upload_resp.json()
        if "media_id" in data:
            logger.info("[WeChat] 封面图上传成功: %s", data["media_id"])
            return data["media_id"]

        logger.warning("[WeChat] 封面图上传失败: %s", data)
        return None
    except Exception as e:
        logger.warning("[WeChat] 上传图片异常: %s", e)
        return None


def _make_png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """生成 PNG 数据块，作为无 Pillow 环境下的默认封面兜底。"""
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def _generate_solid_png(width: int = 900, height: int = 383) -> bytes:
    """使用标准库生成纯色 PNG，避免默认封面依赖 Pillow。"""
    # 每行以 0 作为过滤类型，后面是 RGB 像素数据。
    row = b"\x00" + bytes([26, 86, 219]) * width
    raw = row * height
    png_signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        png_signature
        + _make_png_chunk(b"IHDR", ihdr)
        + _make_png_chunk(b"IDAT", zlib.compress(raw, level=6))
        + _make_png_chunk(b"IEND", b"")
    )


def _guess_image_upload_meta(image_bytes: bytes) -> tuple[str, str]:
    """根据图片头判断上传文件名和 MIME 类型。"""
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "default_cover.png", "image/png"
    return "default_cover.jpg", "image/jpeg"


def _generate_default_cover() -> bytes:
    """生成沪上银品牌默认封面图（900x120 紧凑型蓝色渐变 + 品牌文字）"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        W, H = 900, 120
        img = Image.new("RGB", (W, H))
        draw = ImageDraw.Draw(img)
        # 蓝色渐变背景（从深蓝到主蓝）
        for y in range(H):
            r = int(26 + (26 - 26) * y / H)
            g = int(86 + (86 - 46) * y / H)
            b = int(219 + (219 - 140) * y / H)
            draw.line([(0, y), (W, y)], fill=(r, g, b))
        # 绘制品牌名
        try:
            font_large = ImageFont.truetype("msyh.ttc", 36)
            font_small = ImageFont.truetype("msyh.ttc", 16)
        except OSError:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
        # 主标题
        title = "沪上银"
        bbox = draw.textbbox((0, 0), title, font=font_large)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(((W - tw) // 2, (H - th) // 2 - 5), title, fill=(255, 255, 255), font=font_large)
        # 副标题
        subtitle = "上海专业贷款顾问服务"
        bbox2 = draw.textbbox((0, 0), subtitle, font=font_small)
        sw = bbox2[2] - bbox2[0]
        draw.text(((W - sw) // 2, (H - th) // 2 + th + 3), subtitle, fill=(245, 158, 11), font=font_small)
        # 输出为 JPEG bytes
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue()
    except ImportError:
        logger.warning("[WeChat] Pillow 未安装，使用纯色默认封面")
        # 使用标准库生成一张 900x383 蓝色 PNG，保证没有 Pillow 也能上传封面素材。
        return _generate_solid_png()
    except Exception as e:
        logger.error(f"[WeChat] 默认封面生成失败: {e}")
        return b''


def get_or_create_default_thumb() -> str | None:
    """
    获取或创建默认封面的 media_id。
    如果已有缓存则直接返回，否则生成默认封面图并上传到微信素材库。
    返回 media_id 或 None（全部失败时）。
    """
    if _default_thumb_cache.get("media_id"):
        logger.info(f"[WeChat] 使用缓存的默认封面: {_default_thumb_cache['media_id']}")
        return _default_thumb_cache["media_id"]

    try:
        cover_bytes = _generate_default_cover()
        if not cover_bytes:
            logger.error("[WeChat] 默认封面生成为空")
            return None

        token = get_access_token()
        url = f"{WECHAT_API_BASE}/material/add_material?access_token={token}&type=image"
        filename, content_type = _guess_image_upload_meta(cover_bytes)
        files = {"media": (filename, cover_bytes, content_type)}
        resp = _http_post(url, files=files, timeout=20)
        data = resp.json()

        if "media_id" in data:
            _default_thumb_cache["media_id"] = data["media_id"]
            logger.info(f"[WeChat] 默认封面上传成功: {data['media_id']}")
            return data["media_id"]
        else:
            logger.error(f"[WeChat] 默认封面上传失败: {data}")
            return None
    except Exception as e:
        logger.error(f"[WeChat] 默认封面创建异常: {e}")
        return None


def ensure_thumb_media_id(cover_image: str | None = None, cover_url: str | None = None) -> str | None:
    """
    确保 thumb_media_id 可用：
    1. 有 cover_image（本地生成图）→ 优先上传
    2. 否则尝试 cover_url（远程或旧字段）
    3. 上传失败或无封面 → 使用默认封面
    全部失败返回 None
    """
    for image_source in [cover_image, cover_url]:
        if not image_source:
            continue
        mid = upload_image(image_source)
        if mid:
            return mid
        logger.warning("[WeChat] 封面图上传失败，回退到默认封面")

    # 回退到默认封面
    return get_or_create_default_thumb()





def add_draft(articles: list[dict]) -> str | None:
    """
    新增草稿
    articles: [{"title", "author", "digest", "content", "thumb_media_id", "need_open_comment"}]
    返回: media_id (草稿ID) 或 None
    """
    token = get_access_token()
    url = f"{WECHAT_API_BASE}/draft/add?access_token={token}"

    articles_payload = []
    for art in articles:
        articles_payload.append({
            "title": art.get("title", ""),
            "author": art.get("author", ""),
            "digest": art.get("digest", ""),
            "content": art.get("content", ""),
            "thumb_media_id": art.get("thumb_media_id", ""),
            "need_open_comment": art.get("need_open_comment", 0),
            "only_fans_can_comment": art.get("only_fans_can_comment", 0),
        })

    payload = {"articles": articles_payload}
    # 手动序列化 JSON：ensure_ascii=False 防止中文被转义为 \uXXXX
    resp = _http_post(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=20
    )
    data = resp.json()
    if "media_id" in data:
        logger.info(f"[WeChat] 草稿创建成功: {data['media_id']}")
        return data["media_id"]
    else:
        logger.error(f"[WeChat] 草稿创建失败: {data}")
        return None


def submit_draft_for_review(media_id: str) -> bool:
    """
    提交草稿进行发布（发布接口，需公众号有发布权限）
    """
    token = get_access_token()
    url = f"{WECHAT_API_BASE}/freepublish/submit?access_token={token}"
    payload = {"media_id": media_id}
    resp = _http_post(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=20
    )
    data = resp.json()
    if data.get("errcode", -1) == 0:
        logger.info(f"[WeChat] 发布提交成功")
        return True
    else:
        logger.error(f"[WeChat] 发布失败: {data}")
        return False


def get_draft_list(offset=0, count=20) -> dict:
    """获取草稿列表"""
    token = get_access_token()
    url = f"{WECHAT_API_BASE}/draft/batchget?access_token={token}"
    payload = {"offset": offset, "count": count, "no_content": 0}
    resp = _http_post(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=20
    )
    return resp.json()


def mass_send_by_openid(media_id: str, openid_list: list) -> dict:
    """按openid群发（测试用）"""
    token = get_access_token()
    url = f"{WECHAT_API_BASE}/message/mass/send?access_token={token}"
    payload = {
        "touser": openid_list,
        "mpnews": {"media_id": media_id},
        "msgtype": "mpnews",
        "send_ignore_reprint": 0,
    }
    resp = _http_post(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=20
    )
    return resp.json()
