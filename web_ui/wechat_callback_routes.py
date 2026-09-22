"""微信公众号服务器入站回调，仅处理 Phase 1.1 所需事件。"""

from __future__ import annotations

import hashlib
import logging
import time
import xml.etree.ElementTree as ET

from flask import Blueprint, Response, current_app, request

from config import (
    CULTIVATION_CONTACT_NAME,
    CULTIVATION_CONTACT_PHONE,
    CULTIVATION_CONTACT_WECHAT,
    CULTIVATION_REGISTER_URL,
    CULTIVATION_REGISTRATION_TOKEN_HOURS,
    WECHAT_CALLBACK_TOKEN,
)
from services.cultivation_wechat_service import CultivationWechatService

logger = logging.getLogger(__name__)
wechat_callback_bp = Blueprint("wechat_callback", __name__, url_prefix="/wechat")


def verify_wechat_signature(token: str, timestamp: str, nonce: str, signature: str) -> bool:
    if not token or not timestamp or not nonce or not signature:
        return False
    expected = hashlib.sha1("".join(sorted((token, timestamp, nonce))).encode("utf-8")).hexdigest()
    return secrets_compare(expected, signature)


def secrets_compare(left: str, right: str) -> bool:
    """使用标准库常量时间比较，单独封装便于协议测试。"""
    import hmac

    return hmac.compare_digest(left, str(right or ""))


def _text_reply(to_user: str, from_user: str, content: str) -> Response:
    root = ET.Element("xml")
    ET.SubElement(root, "ToUserName").text = to_user
    ET.SubElement(root, "FromUserName").text = from_user
    ET.SubElement(root, "CreateTime").text = str(int(time.time()))
    ET.SubElement(root, "MsgType").text = "text"
    ET.SubElement(root, "Content").text = content
    return Response(ET.tostring(root, encoding="utf-8", xml_declaration=False), content_type="application/xml; charset=utf-8")


def _config(name: str, fallback):
    value = current_app.config.get(name)
    return value if value not in (None, "") else fallback


def _registration_message(openid: str, returning: bool = False) -> str:
    issued = CultivationWechatService.issue_registration_link(
        openid,
        register_url=_config("CULTIVATION_REGISTER_URL", CULTIVATION_REGISTER_URL),
        token_hours=int(_config("CULTIVATION_REGISTRATION_TOKEN_HOURS", CULTIVATION_REGISTRATION_TOKEN_HOURS)),
        mark_subscribed=True,
    )
    if returning or issued.get("customer_id"):
        return (
            "欢迎回来！\n\n您的融资档案已存在。\n\n"
            "如需更新最新贷款、到期时间或融资需求，请点击：\n\n"
            f"【更新融资档案】\n{issued['url']}\n\n如有紧急融资问题，可直接回复“咨询”。"
        )
    return (
        "欢迎关注【融资管家】！\n\n"
        "为了给您提供更精准的融资资质养护、贷款到期提醒和融资建议，请花1分钟完善您的融资档案。\n\n"
        "完成后可获得：\n"
        "✅ 融资资质初步诊断\n✅ 贷款到期提醒\n✅ 征信/流水/负债养护建议\n✅ 后续融资机会提醒\n\n"
        f"【填写融资档案】\n{issued['url']}\n\n如有紧急融资问题，可直接回复“咨询”。"
    )


@wechat_callback_bp.route("/callback", methods=["GET", "POST"])
def callback():
    callback_token = str(_config("WECHAT_CALLBACK_TOKEN", WECHAT_CALLBACK_TOKEN) or "")
    valid = verify_wechat_signature(
        callback_token,
        request.args.get("timestamp", ""),
        request.args.get("nonce", ""),
        request.args.get("signature", ""),
    )
    if not valid:
        logger.warning("[wechat-callback-signature-rejected] method=%s", request.method)
        return Response("forbidden", status=403, content_type="text/plain; charset=utf-8")
    if request.method == "GET":
        return Response(request.args.get("echostr", ""), content_type="text/plain; charset=utf-8")

    body = request.get_data(cache=False)
    if not body or len(body) > 65536:
        return Response("success", content_type="text/plain; charset=utf-8")
    try:
        root = ET.fromstring(body)
        message = {child.tag: child.text or "" for child in root}
    except ET.ParseError:
        logger.warning("[wechat-callback-invalid-xml]")
        return Response("success", content_type="text/plain; charset=utf-8")

    openid = message.get("FromUserName", "").strip()
    account_id = message.get("ToUserName", "").strip()
    msg_type = message.get("MsgType", "").strip().lower()
    try:
        if msg_type == "event":
            event = message.get("Event", "").strip().lower()
            if event == "subscribe":
                content = _registration_message(openid)
                logger.info("[cultivation-wechat-subscribe] openid_ref=%s", CultivationWechatService._openid_ref(openid))
                return _text_reply(openid, account_id, content)
            if event == "unsubscribe":
                CultivationWechatService.unsubscribe(openid)
                return Response("success", content_type="text/plain; charset=utf-8")
        elif msg_type == "text":
            content = message.get("Content", "").strip()
            try:
                CultivationWechatService.record_interaction(openid)
            except Exception:
                # 互动时间只用于客服消息窗口预判，写入失败不能中断原有关键词回复。
                logger.exception(
                    "[cultivation-wechat-interaction-record-error] openid_ref=%s",
                    CultivationWechatService._openid_ref(openid),
                )
            if content in {"建档", "档案", "更新档案"}:
                return _text_reply(openid, account_id, _registration_message(openid))
            if content == "咨询":
                name = str(_config("CULTIVATION_CONTACT_NAME", CULTIVATION_CONTACT_NAME) or "暂未配置")
                phone = str(_config("CULTIVATION_CONTACT_PHONE", CULTIVATION_CONTACT_PHONE) or "暂未配置")
                wechat = str(_config("CULTIVATION_CONTACT_WECHAT", CULTIVATION_CONTACT_WECHAT) or "暂未配置")
                reply = (
                    "【融资顾问】\n\n您好，如需咨询续贷、增额、新贷款或负债优化，可以直接联系：\n\n"
                    f"顾问：{name}\n电话：{phone}\n微信：{wechat}\n\n"
                    "为了方便判断，也可以回复：\n“企业名称 + 当前资金需求 + 联系电话”"
                )
                logger.info("[wechat-consult-reply] openid_ref=%s", CultivationWechatService._openid_ref(openid))
                return _text_reply(openid, account_id, reply)
            existing_reply = CultivationWechatService.find_keyword_reply(content)
            if existing_reply:
                return _text_reply(openid, account_id, existing_reply)
    except Exception:
        logger.exception("[wechat-callback-handler-error] msg_type=%s", msg_type)
        if msg_type == "event" and message.get("Event", "").strip().lower() == "subscribe":
            fallback = "欢迎关注融资管家！\n\n融资档案登记服务暂时繁忙，请稍后回复“建档”获取登记入口。"
            return _text_reply(openid, account_id, fallback)
    return Response("success", content_type="text/plain; charset=utf-8")
