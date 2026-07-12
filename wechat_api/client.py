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
from config import BASE_DIR, WECHAT_APP_ID, WECHAT_APP_SECRET, WECHAT_LEAD_QR_IMAGE

logger = logging.getLogger(__name__)

DEFAULT_WECHAT_AUTHOR = "沪上银 · 有金"

# access_token 缓存
_token_cache = {"token": "", "expire_at": 0}

# 默认封面的 media_id 缓存（避免重复上传）
_default_thumb_cache = {"media_id": None}  # 设为 None 可强制重新生成（改尺寸后需清缓存）

WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"
WECHAT_DIGEST_MAX_CHARS = 54
class WechatPublishError(RuntimeError):
    def __init__(self, stage: str, message: str, errcode=None, errmsg: str = "", detail=None):
        self.stage = stage
        self.errcode = errcode
        self.errmsg = errmsg or ""
        self.detail = detail
        super().__init__(self._format_message(message))

    def _format_message(self, message: str) -> str:
        parts = [f"stage={self.stage}", message]
        if self.errcode is not None:
            parts.append(f"errcode={self.errcode}")
        if self.errmsg:
            parts.append(f"errmsg={self.errmsg}")
        return " | ".join(parts)

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "errcode": self.errcode,
            "errmsg": self.errmsg,
            "message": str(self),
        }


def _mask_secret(value: str) -> str:
    value = value or ""
    if not value:
        return "missing"
    if len(value) <= 8:
        return "set-short"
    return f"{value[:4]}****{value[-4:]}"


def _wechat_api_error(stage: str, message: str, data=None) -> WechatPublishError:
    data = data or {}
    errcode = data.get("errcode") if isinstance(data, dict) else None
    errmsg = data.get("errmsg", "") if isinstance(data, dict) else ""
    return WechatPublishError(stage, message, errcode=errcode, errmsg=errmsg, detail=data)


def validate_wechat_config() -> None:
    logger.info(
        "[publish-config-check] appid_present=%s appsecret=%s",
        bool(WECHAT_APP_ID),
        _mask_secret(WECHAT_APP_SECRET),
    )
    if not WECHAT_APP_ID:
        raise WechatPublishError("access_token", "微信 AppID 未配置")
    if not WECHAT_APP_SECRET:
        raise WechatPublishError("access_token", "微信 AppSecret 未配置")


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


def _sanitize_draft_digest(digest: str) -> str:
    """最终出站前强制清空草稿摘要，避免微信草稿箱副标题抓到品牌/Header。"""
    return ""


def get_access_token(force_refresh=False) -> str:
    """获取或刷新 access_token。"""
    global _token_cache
    validate_wechat_config()
    now = time.time()
    if not force_refresh and _token_cache["token"] and now < _token_cache["expire_at"] - 60:
        return _token_cache["token"]

    logger.info("[publish-access-token] requesting appid_present=%s", bool(WECHAT_APP_ID))
    url = f"{WECHAT_API_BASE}/token"
    params = {
        "grant_type": "client_credential",
        "appid": WECHAT_APP_ID,
        "secret": WECHAT_APP_SECRET,
    }
    try:
        resp = _http_get(url, params=params, timeout=10)
        data = resp.json()
    except Exception as exc:
        logger.error("[publish-error] stage=access_token error=%s", exc)
        raise WechatPublishError("access_token", f"获取微信 access_token 请求失败: {exc}") from exc

    if "access_token" not in data:
        logger.error(
            "[publish-error] stage=access_token errcode=%s errmsg=%s response=%s",
            data.get("errcode"),
            data.get("errmsg"),
            data,
        )
        raise _wechat_api_error("access_token", "获取微信 access_token 失败", data)

    _token_cache["token"] = data["access_token"]
    _token_cache["expire_at"] = now + data.get("expires_in", 7200)
    logger.info("[publish-access-token] success expires_in=%s", data.get("expires_in", 7200))
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
        candidate = Path(BASE_DIR) / "web_ui" / source.lstrip("/")
        if candidate.exists():
            return candidate
        qr_path = Path(WECHAT_LEAD_QR_IMAGE) if WECHAT_LEAD_QR_IMAGE else None
        if qr_path and qr_path.name and source.endswith(f"/{qr_path.name}") and qr_path.exists():
            return qr_path
        return candidate
    if source.startswith("static/"):
        candidate = Path(BASE_DIR) / "web_ui" / source
        if candidate.exists():
            return candidate
        qr_path = Path(WECHAT_LEAD_QR_IMAGE) if WECHAT_LEAD_QR_IMAGE else None
        if qr_path and qr_path.name and source.endswith(qr_path.name) and qr_path.exists():
            return qr_path
        return candidate

    path = Path(image_source)
    if path.is_absolute():
        return path
    return Path(BASE_DIR) / image_source


def upload_image(image_source: str) -> str | None:
    """上传封面图片到微信永久素材库，返回 thumb media_id。"""
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
            filename, content_type = _guess_mime_from_name(image_source)
            if "png" in resp.headers.get("Content-Type", ""):
                filename, content_type = ("cover.png", "image/png")
        else:
            local_path = _resolve_local_image_path(image_source)
            if not local_path or not local_path.exists():
                logger.error("[publish-error] stage=cover_upload missing_image=%s", image_source)
                raise WechatPublishError("cover_upload", "封面图上传失败，封面文件不存在")
            image_bytes = local_path.read_bytes()
            filename, content_type = _guess_mime_from_name(local_path.name)

        token = get_access_token()
        logger.info("[publish-cover-upload] source=%s bytes=%s content_type=%s", image_source, len(image_bytes), content_type)
        url = f"{WECHAT_API_BASE}/material/add_material?access_token={token}&type=image"
        files = {"media": (filename, image_bytes, content_type)}
        upload_resp = _http_post(url, files=files, timeout=20)
        data = upload_resp.json()
        if "media_id" in data:
            logger.info("[publish-cover-upload] success media_id_present=%s", bool(data.get("media_id")))
            return data["media_id"]

        logger.error(
            "[publish-error] stage=cover_upload errcode=%s errmsg=%s response=%s",
            data.get("errcode"),
            data.get("errmsg"),
            data,
        )
        raise _wechat_api_error("cover_upload", "封面图上传失败，缺少 thumb_media_id，无法推送草稿箱", data)
    except WechatPublishError:
        raise
    except Exception as exc:
        logger.error("[publish-error] stage=cover_upload error=%s", exc)
        raise WechatPublishError("cover_upload", f"封面图上传失败，缺少 thumb_media_id，无法推送草稿箱: {exc}") from exc

def upload_content_image(image_source: str) -> str | None:
    """上传公众号正文图片，返回微信可长期展示的 mmbiz 图片 URL。"""
    if not image_source:
        return None

    try:
        image_bytes = b""
        filename = "content_image.jpg"
        content_type = "image/jpeg"

        if image_source.startswith("http://") or image_source.startswith("https://"):
            resp = _http_get(image_source, timeout=15)
            resp.raise_for_status()
            image_bytes = resp.content
            filename, content_type = _guess_mime_from_name(image_source)
            if "png" in resp.headers.get("Content-Type", ""):
                filename, content_type = ("content_image.png", "image/png")
        else:
            local_path = _resolve_local_image_path(image_source)
            if not local_path or not local_path.exists():
                logger.error("[publish-error] stage=content_img_upload missing_image=%s", image_source)
                raise WechatPublishError("content_img_upload", "正文图片 uploadimg 失败，图片文件不存在")
            image_bytes = local_path.read_bytes()
            filename, content_type = _guess_mime_from_name(local_path.name)

        token = get_access_token()
        logger.info("[publish-content-img-upload] source=%s bytes=%s content_type=%s", image_source, len(image_bytes), content_type)
        url = f"{WECHAT_API_BASE}/media/uploadimg?access_token={token}"
        files = {"media": (filename, image_bytes, content_type)}
        upload_resp = _http_post(url, files=files, timeout=20)
        data = upload_resp.json()
        if data.get("url"):
            logger.info("[publish-content-img-upload] success url_present=%s", bool(data.get("url")))
            return data["url"]

        logger.error(
            "[publish-error] stage=content_img_upload errcode=%s errmsg=%s response=%s",
            data.get("errcode"),
            data.get("errmsg"),
            data,
        )
        raise _wechat_api_error("content_img_upload", "正文图片 uploadimg 失败", data)
    except WechatPublishError:
        raise
    except Exception as exc:
        logger.error("[publish-error] stage=content_img_upload error=%s", exc)
        raise WechatPublishError("content_img_upload", f"正文图片 uploadimg 失败: {exc}") from exc

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
    """生成无文字默认封面图，避免微信卡片裁切出品牌副标题。"""
    try:
        from PIL import Image, ImageDraw
        W, H = 900, 120
        img = Image.new("RGB", (W, H))
        draw = ImageDraw.Draw(img)
        # 默认封面只保留抽象商务背景，不写入品牌名、城市或贷款顾问副标题。
        for y in range(H):
            r = int(26 + (26 - 26) * y / H)
            g = int(86 + (86 - 46) * y / H)
            b = int(219 + (219 - 140) * y / H)
            draw.line([(0, y), (W, y)], fill=(r, g, b))
        draw.ellipse((W - 220, -90, W + 70, 190), fill=(37, 99, 235))
        draw.ellipse((-80, 48, 160, 210), fill=(30, 64, 175))
        draw.rectangle((0, H - 10, W, H), fill=(219, 234, 254))
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
    返回 media_id；失败时抛出 cover_upload 阶段错误。
    """
    if _default_thumb_cache.get("media_id"):
        logger.info("[publish-cover-upload] using_cached_default media_id_present=True")
        return _default_thumb_cache["media_id"]

    try:
        cover_bytes = _generate_default_cover()
        if not cover_bytes:
            logger.error("[publish-error] stage=cover_upload default_cover_empty=True")
            raise WechatPublishError("cover_upload", "封面图上传失败，缺少 thumb_media_id，无法推送草稿箱")

        token = get_access_token()
        logger.info("[publish-cover-upload] default_cover bytes=%s", len(cover_bytes))
        url = f"{WECHAT_API_BASE}/material/add_material?access_token={token}&type=image"
        filename, content_type = _guess_image_upload_meta(cover_bytes)
        files = {"media": (filename, cover_bytes, content_type)}
        resp = _http_post(url, files=files, timeout=20)
        data = resp.json()

        if "media_id" in data:
            _default_thumb_cache["media_id"] = data["media_id"]
            logger.info("[publish-cover-upload] default_cover_success media_id_present=True")
            return data["media_id"]

        logger.error(
            "[publish-error] stage=cover_upload errcode=%s errmsg=%s response=%s",
            data.get("errcode"),
            data.get("errmsg"),
            data,
        )
        raise _wechat_api_error("cover_upload", "封面图上传失败，缺少 thumb_media_id，无法推送草稿箱", data)
    except WechatPublishError:
        raise
    except Exception as exc:
        logger.error("[publish-error] stage=cover_upload error=%s", exc)
        raise WechatPublishError("cover_upload", f"封面图上传失败，缺少 thumb_media_id，无法推送草稿箱: {exc}") from exc

def ensure_thumb_media_id(cover_image: str | None = None, cover_url: str | None = None) -> str | None:
    """
    确保 thumb_media_id 可用。
    有封面来源时必须上传成功；没有封面来源时尝试默认封面。
    """
    attempted = False
    for image_source in [cover_image, cover_url]:
        if not image_source:
            continue
        attempted = True
        mid = upload_image(image_source)
        if mid:
            return mid

    if attempted:
        raise WechatPublishError("cover_upload", "封面图上传失败，缺少 thumb_media_id，无法推送草稿箱")

    return get_or_create_default_thumb()

def add_draft(articles: list[dict]) -> str | None:
    """
    新增草稿。
    articles: [{"title", "author", "digest", "content", "thumb_media_id", "need_open_comment"}]
    返回 media_id，失败时抛出 add_draft 阶段错误。
    """
    token = get_access_token()
    url = f"{WECHAT_API_BASE}/draft/add?access_token={token}"

    articles_payload = []
    for art in articles:
        digest_value = _sanitize_draft_digest(art.get("digest", ""))
        logger.info("[wechat-draft] digest=%s", digest_value)
        if not art.get("thumb_media_id"):
            raise WechatPublishError("cover_upload", "封面图上传失败，缺少 thumb_media_id，无法推送草稿箱")
        if not art.get("content"):
            raise WechatPublishError("add_draft", "final_content 为空，无法推送草稿箱")
        articles_payload.append({
            "title": art.get("title", ""),
            "author": art.get("author") or DEFAULT_WECHAT_AUTHOR,
            "digest": digest_value,
            "content": art.get("content", ""),
            "thumb_media_id": art.get("thumb_media_id", ""),
            "need_open_comment": art.get("need_open_comment", 0),
            "only_fans_can_comment": art.get("only_fans_can_comment", 0),
        })

    payload = {"articles": articles_payload}
    logger.info("[publish-add-draft] articles=%s first_content_length=%s", len(articles_payload), len(articles_payload[0].get("content", "") if articles_payload else ""))
    try:
        resp = _http_post(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=20
        )
        data = resp.json()
    except Exception as exc:
        logger.error("[publish-error] stage=add_draft error=%s", exc)
        raise WechatPublishError("add_draft", f"微信草稿创建请求失败: {exc}") from exc

    if "media_id" in data:
        logger.info("[publish-add-draft] success media_id_present=True")
        return data["media_id"]

    logger.error(
        "[publish-error] stage=add_draft errcode=%s errmsg=%s response=%s",
        data.get("errcode"),
        data.get("errmsg"),
        data,
    )
    raise _wechat_api_error("add_draft", "微信草稿创建失败", data)

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
