"""测试东方财富API实际返回格式"""
import requests
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://finance.eastmoney.com/",
}

urls = [
    "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_20_1_.html",
    "https://newsapi.eastmoney.com/kuaixun/v1/getlist_1_ajaxResult_20_1_.html",
    "https://newsapi.eastmoney.com/kuaixun/v1/getlist_180_ajaxResult_20_1_.html",
]

for url in urls:
    print(f"\n{'='*60}")
    print(f"URL: {url}")
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        print(f"状态码: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('content-type', '')}")
        raw = resp.text
        print(f"内容前300字符: {repr(raw[:300])}")
        print(f"内容总长度: {len(raw)}")
        
        # 尝试直接解析
        try:
            data = json.loads(raw)
            lives = data.get("LivesList", [])
            print(f"✅ 直接JSON解析成功，LivesList有 {len(lives)} 条")
            if lives:
                print(f"   第一条标题: {lives[0].get('title', '')[:50]}")
        except json.JSONDecodeError as e:
            print(f"❌ 直接JSON解析失败: {e}")
    except Exception as e:
        print(f"请求失败: {e}")

print("\n完成")
