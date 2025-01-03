import asyncio
from app.services.crawler.ltn_crawler import LTNCrawler
from app.core.database import SessionLocal
from app.models.article import Article
import pytest

@pytest.mark.asyncio
async def test_crawler():
    crawler = LTNCrawler()
    try:
        # 只爬取第一頁
        articles = await crawler.run(max_pages=3)
        
        if articles:
            print(f"成功爬取 {len(articles)} 篇文章")
            
            # 儲存到資料庫
            db = SessionLocal()
            try:
                for article_data in articles:
                    # 檢查文章是否已存在
                    exists = db.query(Article).filter(Article.url == article_data["url"]).first()
                    if not exists:
                        article = Article(**article_data)
                        db.add(article)
                        print(f"新增文章: {article.title}")
                
                db.commit()
                print("資料儲存完成")
                
            finally:
                db.close()
                
    except Exception as e:
        print(f"爬蟲執行失敗: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_crawler()) 