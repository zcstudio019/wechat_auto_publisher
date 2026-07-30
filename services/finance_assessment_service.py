"""Enterprise finance assessment CTA and WeChat source URL helpers."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import config

logger = logging.getLogger(__name__)

FINANCE_ASSESSMENT_DOMAIN = "capital.linhongtech.com"
FINANCE_ASSESSMENT_CTA_MARKER = 'data-finance-assessment-cta="true"'
_FINANCE_TEMPLATE_CATEGORIES = {"industry_law", "finance", "leads"}


def validate_finance_assessment_url(url: str | None) -> str | None:
    """Validate an assessment URL before it can enter a WeChat payload."""
    candidate = str(url or "").strip()
    if not candidate:
        return None

    try:
        parsed = urlparse(candidate)
        valid = (
            parsed.scheme.lower() == "https"
            and (parsed.hostname or "").lower() == FINANCE_ASSESSMENT_DOMAIN
            and parsed.port is None
            and not parsed.username
            and not parsed.password
        )
    except (TypeError, ValueError):
        valid = False

    if not valid:
        logger.warning(
            "[finance-assessment-url-invalid] configured=true allowed_domain=%s",
            FINANCE_ASSESSMENT_DOMAIN,
        )
        return None
    return candidate


def get_finance_assessment_url() -> str | None:
    """Return the configured assessment URL only when it is safe for WeChat."""
    configured_url = getattr(config, "FINANCE_ASSESSMENT_URL", "")
    return validate_finance_assessment_url(configured_url)


def is_finance_article(article: dict | None) -> bool:
    """Identify only the financing template families enabled for this CTA."""
    data = article or {}
    category_values = {
        str(data.get(key) or "").strip().lower()
        for key in ("_template_category", "template_category", "category_key", "article_type")
    }
    if category_values & _FINANCE_TEMPLATE_CATEGORIES:
        return True

    text = " ".join(
        str(data.get(key) or "")
        for key in ("_template_name", "template_name", "category", "tags")
    )
    return any(
        marker in text
        for marker in (
            "贷款行业底层规律",
            "企业融资获客",
            "自动获客型融资",
            "融资规划",
        )
    )


def build_finance_assessment_cta_html() -> str:
    """Build a URL-free visual CTA; WeChat's 阅读原文 carries the real URL."""
    return """
<section data-finance-assessment-cta="true" style="margin:28px 0 0;padding:22px 18px;border-radius:12px;background:#f3f8ff;border:1px solid #cfe0f5;text-align:center;">
  <h2 style="margin:0 0 12px;color:#17365d;font-size:22px;line-height:1.5;">企业融资免费测评</h2>
  <p style="margin:0;color:#34495e;font-size:16px;line-height:1.9;">不知道企业能贷多少、问题卡在哪里？<br>点击文末“阅读原文”，完成免费融资测评。<br>系统将根据企业经营、现金流、负债和征信情况，帮你初步判断融资空间与优化方向。</p>
  <p style="display:inline-block;margin:18px 0 12px;padding:11px 26px;border-radius:24px;background:#1769aa;color:#ffffff;font-size:17px;font-weight:700;line-height:1.4;">立即免费测评</p>
  <p style="margin:0;color:#7f8c8d;font-size:12px;line-height:1.7;">测评结果仅用于融资条件初步分析，不构成银行授信或放款承诺。</p>
</section>
""".strip()


def append_finance_assessment_cta(html_content: str, article: dict | None) -> str:
    """Append the financing CTA once after the article content."""
    html = str(html_content or "").strip()
    if not html or not is_finance_article(article):
        return html
    if FINANCE_ASSESSMENT_CTA_MARKER in html:
        return move_finance_assessment_cta_to_end(html)
    return f"{html}\n{build_finance_assessment_cta_html()}"


def move_finance_assessment_cta_to_end(html_content: str) -> str:
    """Keep the assessment card as the final HTML block, even after QR processing."""
    html = str(html_content or "").strip()
    if FINANCE_ASSESSMENT_CTA_MARKER not in html:
        return html
    pattern = re.compile(
        r'<section\s+data-finance-assessment-cta="true"[^>]*>.*?</section>',
        re.IGNORECASE | re.DOTALL,
    )
    matches = pattern.findall(html)
    if not matches:
        return html
    cleaned = pattern.sub("", html).rstrip()
    return f"{cleaned}\n{matches[-1]}"
