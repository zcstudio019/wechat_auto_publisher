"""
批量给文章添加标签
根据来源和内容自动分类
"""
import sqlite3
from config import DB_PATH

def categorize_by_source(source_name, content):
    """根据来源和内容判断文章分类"""
    if not source_name:
        return "知识科普"
    
    source_lower = source_name.lower()
    content_lower = content.lower() if content else ""
    
    # 沪上银原创文章：可能是品牌宣传、服务方案或获客活动
    if "沪上银" in source_name or "原创" in source_name:
        # 根据内容关键词判断
        if any(word in content_lower for word in ["品牌", "宣传", "营销", "推广"]):
            return "品牌宣传"
        elif any(word in content_lower for word in ["获客", "客户", "引流", "营销", "活动"]):
            return "获客活动"
        elif any(word in content_lower for word in ["服务", "方案", "流程", "咨询", "指导"]):
            return "服务方案"
        else:
            return "知识科普"
    
    # 爬取文章：默认都是知识科普
    else:
        return "知识科普"

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取所有文章
    cursor.execute("SELECT id, title, content, source_name, tags FROM articles")
    articles = cursor.fetchall()
    
    print(f"总共 {len(articles)} 篇文章需要重新分类")
    
    updated_count = 0
    for article_id, title, content, source_name, current_tags in articles:
        # 确定分类（即使已有标签也重新分类）
        category = categorize_by_source(source_name, content)
        
        # 生成标签
        if category == "知识科普":
            # 科普类文章：保留原有内容相关标签，加上"知识科普"
            tags = "知识科普"
        elif category == "品牌宣传":
            tags = "品牌宣传"
        elif category == "获客活动":
            tags = "获客活动"
        elif category == "服务方案":
            tags = "服务方案"
        else:
            tags = "知识科普"
        
        # 更新数据库
        cursor.execute(
            "UPDATE articles SET tags=? WHERE id=?",
            (tags, article_id)
        )
        
        updated_count += 1
        print(f"  ID {article_id}: '{title[:30]}...' -> 标签: {tags}")
    
    conn.commit()
    conn.close()
    
    print(f"\\n更新完成：重新分类了 {updated_count} 篇文章")
    print("分类统计：")
    if updated_count > 0:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT tags, COUNT(*) FROM articles WHERE tags IS NOT NULL AND tags != '' GROUP BY tags")
        for tags, count in cursor.fetchall():
            print(f"  {tags}: {count}篇")
        conn.close()

if __name__ == "__main__":
    main()