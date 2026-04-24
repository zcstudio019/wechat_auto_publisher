import sqlite3, re
conn = sqlite3.connect('data/articles.db')
r = conn.execute('SELECT content FROM articles WHERE id=61').fetchone()
if not r:
    print("ID=61 not found!")
    conn.close()
    exit()
content = r[0]

# 检查 quote 卡
idx = content.find('linear-gradient(135deg,#1565C0,#0D47A1')
if idx >= 0:
    snippet = content[idx:idx+700]
    print("=== QUOTE CARD HTML ===")
    print(snippet)
else:
    print("No quote card found")

# 检查是否还有 Step 3
if 'Step 3' in content:
    print("\n\nWARNING: Step 3 still in content!")
    pos = content.find('Step 3')
    print(content[max(0,pos-100):pos+200])
else:
    print("\n\nStep 3 not in content (good)")

conn.close()
