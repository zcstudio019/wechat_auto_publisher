"""生成配图卡片效果预览 HTML"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from ai_processor.processor import _basic_format_rich, _replace_image_markers, _make_image_card

title = "LPR再降10个基点，你的房贷月供能少多少？"
content = """央行宣布本月LPR下调10个基点，从3.95%降至3.85%。这是继去年以来第三次下调。

市场分析人士认为，此次降息主要是为了刺激居民消费和房地产市场，降低企业和居民融资成本。

对于普通购房者来说，月供的变化取决于贷款金额和剩余期限。以100万元30年期房贷为例，利率每降0.1%，每月月供减少约55元，30年累计少还约2万元。

目前上海各大银行均已跟进调整，首套房贷款利率最低可做到3.85%，部分优质客户可以谈到更低。

经营贷方面，企业主融资成本也随之下降，短期经营贷利率已低至3.5%以内。

建议有存量房贷的朋友，可以考虑申请利率重新定价，或者评估是否有转换经营贷的空间。
"""

# 同时演示"AI 已在文章中嵌入多种配图标记"的效果
content_with_markers = """[配图:scene:上海银行大厅贷款咨询:专业 · 高效 · 值得信赖]

央行宣布本月LPR下调10个基点，从3.95%降至3.85%。这是继去年以来第三次下调。

市场分析人士认为，此次降息主要是为了刺激居民消费和房地产市场，降低企业和居民融资成本。

[配图:data:100万房贷每月少还约55元:30年累计节省约2万元]

对于普通购房者来说，月供的变化取决于贷款金额和剩余期限。以100万元30年期房贷为例，利率每降0.1%，每月月供减少约55元，30年累计少还约2万元。

[配图:quote:利率降了，关键是你能不能用上这个好政策:—沪上银贷款顾问]

目前上海各大银行均已跟进调整，首套房贷款利率最低可做到3.85%，部分优质客户可以谈到更低。

经营贷方面，企业主融资成本也随之下降，短期经营贷利率已低至3.5%以内。

[配图:tip:有存量房贷的朋友，现在可以联系银行申请利率重新定价:每年能少还几百到几千元，值得试试]

建议有存量房贷的朋友，可以考虑申请利率重新定价，或者评估是否有转换经营贷的空间。
"""

# 直接测试替换逻辑
from ai_processor.processor import _text_to_paragraphs

body_html = _text_to_paragraphs(content_with_markers)

page = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>配图卡片效果预览</title>
<style>
  body {{ margin:0; padding:20px; background:#f0f2f5; font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif; }}
  .wrapper {{ max-width:680px; margin:0 auto; background:#fff; border-radius:12px; padding:20px; box-shadow:0 2px 12px rgba(0,0,0,.08); }}
  h2 {{ color:#888; font-size:13px; border-bottom:1px solid #eee; padding-bottom:8px; margin:30px 0 16px; }}
</style>
</head>
<body>
<div class="wrapper">
  {_basic_format_rich(title, content, "东方财富")}

  <div style="font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;max-width:100%;box-sizing:border-box;padding:0 4px;">
    <div style="background:linear-gradient(135deg,#0D47A1,#1565C0,#1976D2);border-radius:12px;padding:24px 22px 20px;margin-bottom:6px;">
      <div style="color:rgba(255,255,255,0.65);font-size:11px;letter-spacing:2px;margin-bottom:10px;">沪上银 · 上海专业贷款顾问</div>
      <h1 style="color:#fff;font-size:20px;font-weight:bold;margin:0 0 10px;line-height:1.5;">{title}</h1>
    </div>
    {body_html}
  </div>
</div>
</body>
</html>"""

out = pathlib.Path(__file__).parent / "web_ui/static/preview_cards.html"
out.write_text(page, encoding="utf-8")
print(f"预览文件已生成：{out}")
