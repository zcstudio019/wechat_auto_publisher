import sys
import os
sys.path.insert(0, r"C:\Users\beicheng\WorkBuddy\Claw\wechat_auto_publisher")

try:
    import requests
except ImportError:
    sys.stderr.write("requests not installed\n")
    sys.exit(1)

import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*",
    "Referer": "https://finance.eastmoney.com/",
}

url = "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_20_1_.html"
sys.stdout.write("Testing: " + url + "\n")
try:
    resp = requests.get(url, headers=headers, timeout=15)
    sys.stdout.write("Status: " + str(resp.status_code) + "\n")
    raw = resp.text
    sys.stdout.write("Length: " + str(len(raw)) + "\n")
    sys.stdout.write("First 400 chars: " + repr(raw[:400]) + "\n")
except Exception as e:
    sys.stdout.write("Error: " + str(e) + "\n")
