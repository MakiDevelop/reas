import asyncio
import sys
from app.services.crawler.ltn_crawler import LTNCrawler
from app.services.crawler.udn_crawler import UDNCrawler
from app.services.crawler.nextapple_crawler import NextAppleCrawler
from app.core.database import SessionLocal
from app.models.article import Article
import pytest
from datetime import datetime, timedelta
import argparse
import logging
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# 設定日誌格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 資料庫連線設定
DATABASE_URL = "postgresql://user:password@db:5432/newsdb"

@pytest.mark.asyncio
async def test_crawler(crawler_type="ltn"):
    # 根據參數選擇爬蟲
    if crawler_type.lower() == "udn":
        crawler = UDNCrawler()
    elif crawler_type.lower() == "nextapple":
        crawler = NextAppleCrawler()
    else:
        crawler = LTNCrawler()
    
    try:
        # 只爬取前3頁
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

def test_udn_crawler():
    logging.info("開始測試 UDN 爬蟲...")
    
    # 建立資料庫連線
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        crawler = UDNCrawler()
        logging.info("爬蟲實例化完成，開始爬取文章...")
        
        articles = crawler.crawl()
        logging.info(f"爬取完成，共取得 {len(articles)} 篇文章")
        
        if not articles:
            logging.warning("沒有取得任何文章！")
            return
            
        # 檢查第一篇文章
        article = articles[0]
        logging.info(f"第一篇文章標題: {article.title}")
        logging.info(f"文章連結: {article.url}")
        logging.info(f"發布時間: {article.published_at}")
        
        # 檢查必要欄位是否存在且有值
        required_fields = ['url', 'title', 'source', 'published_at']
        for field in required_fields:
            value = getattr(article, field, None)
            logging.info(f"檢查欄位 {field}: {value}")
            assert hasattr(article, field), f"缺少必要欄位: {field}"
            assert value is not None, f"欄位 {field} 的值為空"
        
        # 檢查欄位值是否正確
        assert article.source == 'udn', f"來源錯誤: {article.source}"
        assert article.url.startswith('https://house.udn.com/'), f"URL格式錯誤: {article.url}"
        assert len(article.title) > 0, "標題不可為空"
        assert isinstance(article.published_at, datetime), f"發布時間格式錯誤: {type(article.published_at)}"
        
        # 儲存到資料庫
        new_count = 0
        update_count = 0
        for article in articles:
            # 檢查文章是否已存在
            existing = db.query(Article).filter(Article.url == article.url).first()
            if existing:
                # 更新現有文章
                existing.title = article.title
                existing.content = article.content
                existing.published_at = article.published_at
                existing.category = article.category
                existing.reporter = article.reporter
                existing.description = article.description
                existing.image_url = article.image_url
                update_count += 1
            else:
                # 新增文章
                db.add(article)
                new_count += 1
        
        db.commit()
        logging.info(f"資料儲存完成！新增 {new_count} 篇，更新 {update_count} 篇")
        
    except Exception as e:
        logging.error(f"測試過程發生錯誤: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()
        
    logging.info("UDN 爬蟲測試完成！")

def test_nextapple_crawler():
    """測試蘋果地產爬蟲"""
    logging.info("開始測試 NextApple 爬蟲...")
    
    # 建立資料庫連線
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # 實例化爬蟲
        crawler = NextAppleCrawler()
        logging.info("爬蟲實例化完成，開始爬取文章...")
        
        # 爬取文章
        articles = crawler.crawl()
        logging.info(f"爬取完成，共取得 {len(articles)} 篇文章")
        
        # 儲存文章並保持 session 連接
        for article in articles:
            db.add(article)
        db.commit()
        
        # 從資料庫讀取第一篇文章
        first_article = db.query(Article).first()
        if first_article:
            logging.info(f"第一篇文章標題: {first_article.title}")
            logging.info(f"文章內容: {first_article.content[:200]}...")  # 只顯示前200字
            
    except Exception as e:
        logging.error(f"測試過程發生錯誤: {str(e)}")
        db.rollback()  # 發生錯誤時回滾
        raise
    finally:
        db.close()

def crawl_historical_data(start_date=None, end_date=None):
    """回補指定日期範圍的文章"""
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
        
    logging.info(f"開始回補歷史文章 ({start_date} ~ {end_date})...")
    
    # 建立資料庫連線
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # 依序執行三個爬蟲
        logging.info("開始執行 UDN 爬蟲...")
        test_udn_crawler()
        
        logging.info("開始執行 NextApple 爬蟲...")
        test_nextapple_crawler()
        
        logging.info("開始執行 LTN 爬蟲...")
        asyncio.run(test_crawler('ltn'))
        
        logging.info("所有爬蟲執行完成")
                
    except Exception as e:
        logging.error(f"回補程序執行失敗: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('crawler', choices=['ltn', 'udn', 'nextapple', 'historical'], 
                       help='指定要測試的爬蟲或執行歷史回補')
    parser.add_argument('--start_date', 
                       help='回補起始日期 (YYYY-MM-DD)',
                       default=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    parser.add_argument('--end_date',
                       help='回補結束日期 (YYYY-MM-DD)',
                       default=datetime.now().strftime('%Y-%m-%d'))
    args = parser.parse_args()
    
    if args.crawler == 'historical':
        crawl_historical_data(args.start_date, args.end_date)
    elif args.crawler == 'udn':
        test_udn_crawler()
    elif args.crawler == 'nextapple':
        test_nextapple_crawler()
    else:
        asyncio.run(test_crawler(args.crawler)) 