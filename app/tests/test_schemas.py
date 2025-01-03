from datetime import datetime
from app.schemas.article import ArticleBase, ArticleCreate, ArticleInDB, ArticleList, ArticleSearch
from app.models.article import Article
from app.core.database import SessionLocal

def test_article_schemas():
    # 測試 ArticleCreate
    article_data = {
        "url": "https://test.com/news/2",
        "source": "test",
        "category": "測試分類",
        "reporter": "測試記者",
        "title": "測試標題 2",
        "description": "這是第二個測試描述",
        "image_url": "https://test.com/image2.jpg",
        "content": "這是第二個測試內容",
        "published_at": datetime.now()
    }
    
    try:
        # 測試建立文章模型
        article_create = ArticleCreate(**article_data)
        print("ArticleCreate 驗證成功！")
        print(f"標題: {article_create.title}")
        
        # 測試資料庫模型轉換為 schema
        db = SessionLocal()
        db_article = Article(**article_data)
        db.add(db_article)
        db.commit()
        db.refresh(db_article)
        
        # 測試 ArticleInDB
        article_in_db = ArticleInDB.model_validate(db_article)
        print("\nArticleInDB 轉換成功！")
        print(f"ID: {article_in_db.id}")
        print(f"建立時間: {article_in_db.created_at}")
        
        # 測試 ArticleList
        article_list = ArticleList.model_validate(db_article)
        print("\nArticleList 轉換成功！")
        print(f"列表標題: {article_list.title}")
        
        # 測試 ArticleSearch
        search_params = {
            "source": "test",
            "keyword": "測試",
            "page": 1,
            "page_size": 10
        }
        search = ArticleSearch(**search_params)
        print("\nArticleSearch 驗證成功！")
        print(f"搜尋參數: {search.model_dump()}")
        
    except Exception as e:
        print(f"測試失敗: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    test_article_schemas() 