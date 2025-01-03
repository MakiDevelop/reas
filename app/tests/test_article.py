from datetime import datetime
from sqlalchemy.orm import Session
from app.models.article import Article
from app.core.database import engine, Base, SessionLocal

def test_create_article():
    # 建立資料表
    Base.metadata.create_all(bind=engine)
    
    # 在測試開始前清空資料表
    db = SessionLocal()
    try:
        db.query(Article).delete()
        db.commit()
    except:
        db.rollback()
    finally:
        db.close()
    
    # 建立測試資料
    test_article = Article(
        url="https://test.com/news/1",
        source="test",
        category="測試分類",
        reporter="測試記者",
        title="測試標題",
        description="這是一個測試描述",
        image_url="https://test.com/image.jpg",
        content="這是測試內容",
        published_at=datetime.now()
    )
    
    # 新增資料
    db = SessionLocal()
    try:
        db.add(test_article)
        db.commit()
        
        # 驗證資料
        saved_article = db.query(Article).first()
        assert saved_article is not None
        assert saved_article.url == test_article.url
    finally:
        db.close()

if __name__ == "__main__":
    test_create_article() 