import sqlite3
from config import DB_PATH

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print('检查标签分布：')
cursor.execute("SELECT DISTINCT tags FROM articles WHERE tags IS NOT NULL AND tags != ''")
for row in cursor.fetchall():
    print(f'  标签: {row[0]}')

print('\n检查品牌标签：')
cursor.execute("SELECT COUNT(*) FROM articles WHERE tags LIKE '%品牌%'")
print(f'  品牌标签文章: {cursor.fetchone()[0]}篇')

print('检查获客标签：')
cursor.execute("SELECT COUNT(*) FROM articles WHERE tags LIKE '%获客%'")
print(f'  获客标签文章: {cursor.fetchone()[0]}篇')

print('检查服务标签：')
cursor.execute("SELECT COUNT(*) FROM articles WHERE tags LIKE '%服务%'")
print(f'  服务标签文章: {cursor.fetchone()[0]}篇')

print('检查科普/知识标签：')
cursor.execute("SELECT COUNT(*) FROM articles WHERE tags LIKE '%科普%' OR tags LIKE '%知识%'")
print(f'  科普/知识标签文章: {cursor.fetchone()[0]}篇')

conn.close()