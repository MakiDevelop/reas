import logging
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.orm import Session
from datetime import datetime
from app.core.database import get_db
from app.models.article import Article
from app.schemas.article import ArticleInDB
from app.core.config import settings
from app.services.crawler.ltn_crawler import LTNCrawler

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/sources", response_model=Dict[str, str])
def get_sources():
    """獲取所有支援的新聞來源"""
    return {
        source_id: source_info["name"]
        for source_id, source_info in settings.NEWS_SOURCES.items()
    }

@router.get("/", response_model=List[ArticleInDB])
def get_articles(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    days: Optional[int] = None
):
    query = select(Article).order_by(Article.published_at.desc())
    
    if days:
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        query = query.filter(Article.published_at >= cutoff_date)
    
    query = query.offset(skip).limit(limit)
    articles = db.execute(query).scalars().all()
    
    logger.info(f"Found {len(articles)} articles in database")
    for article in articles:
        logger.info(f"Article {article.id}: {article.title} ({article.published_at})")
    return articles

@router.get("/{article_id}", response_model=ArticleInDB)
def get_article(
    article_id: int,
    db: Session = Depends(get_db)
):
    query = select(Article).filter(Article.id == article_id)
    article = db.execute(query).scalar_one_or_none()
    
    if article is None:
        raise HTTPException(status_code=404, detail=f"Article {article_id} not found")
    
    logger.info(f"Retrieved article {article.id}: {article.title}")
    return article 

@router.post("/update-content")
async def update_articles_content(
    db: Session = Depends(get_db),
    limit: int = 5
):
    """更新文章內容"""
    crawler = LTNCrawler()
    try:
        # 設定 driver
        crawler.setup_driver()
        
        # 獲取沒有內容的文章
        query = select(Article).filter(Article.content == None)
        articles = db.execute(query).scalars().all()
        logger.info(f"Found {len(articles)} articles without content")
        
        if not articles:
            return {"message": "No articles need to be updated"}
        
        articles = articles[:limit]  # 限制處理數量
        logger.info(f"Will update {len(articles)} articles")
        
        updated_count = 0
        for article in articles:
            try:
                logger.info(f"Updating article {article.id}: {article.url}")
                # 爬取完整內容
                article_data = await crawler.crawl_article(article.url)
                if article_data:
                    # 更新文章
                    stmt = (
                        update(Article)
                        .where(Article.id == article.id)
                        .values(
                            content=article_data["content"],
                            image_urls=article_data.get("image_urls", []),
                            updated_at=datetime.utcnow()
                        )
                    )
                    db.execute(stmt)
                    updated_count += 1
                    logger.info(f"Successfully updated article {article.id}")
                else:
                    logger.warning(f"No content returned for article {article.id}")
            
            except Exception as e:
                logger.error(f"Error updating article {article.id}: {str(e)}")
                continue
        
        db.commit()
        return {"message": f"Updated {updated_count} articles"}
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error in batch update: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        crawler.cleanup()

@router.delete("/all")
async def delete_all_articles(
    db: Session = Depends(get_db),
    confirm: bool = False
):
    """清空所有文章"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Please confirm deletion by setting confirm=true"
        )
    
    try:
        stmt = delete(Article)
        db.execute(stmt)
        db.commit()
        return {"message": "All articles deleted"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting articles: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 

@router.post("/crawl")
async def crawl_articles(
    db: Session = Depends(get_db),
    pages: int = 1
):
    """爬取文章列表"""
    logger.info(f"Starting to crawl {pages} pages")
    crawler = LTNCrawler()
    try:
        logger.info("Setting up crawler driver")
        crawler.setup_driver()
        total_articles = 0
        
        for page in range(1, pages + 1):
            logger.info(f"Processing page {page}")
            try:
                # 爬取文章列表
                urls = await crawler.crawl_list(page=page)
                logger.info(f"Found {len(urls)} articles on page {page}")
                
                # 儲存到資料庫
                for i, url in enumerate(urls, 1):
                    logger.info(f"Processing article {i}/{len(urls)} on page {page}: {url}")
                    try:
                        article_data = await crawler.crawl_article(url)
                        if article_data:
                            # 檢查文章是否已存在
                            existing = db.execute(
                                select(Article).filter(Article.url == url)
                            ).scalar_one_or_none()
                            
                            if existing:
                                logger.info(f"Updating existing article: {url}")
                                logger.info(f"Current data: description={existing.description}, image_url={existing.image_url}, reporter={existing.reporter}")
                                logger.info(f"New data: description={article_data.get('description')}, image_url={article_data.get('image_url')}, reporter={article_data.get('reporter')}")
                                
                                # 更新現有文章的資料
                                existing.title = article_data["title"]
                                existing.content = article_data.get("content", "")
                                existing.description = article_data.get("description")
                                existing.image_url = article_data.get("image_url")
                                existing.reporter = article_data.get("reporter")
                                existing.category = article_data.get("category")
                                existing.published_at = article_data["published_at"]
                                existing.updated_at = datetime.utcnow()
                                
                                # 確保更新被提交
                                db.add(existing)
                                db.flush()
                                db.commit()  # 立即提交更改
                                
                                # 驗證更新
                                db.refresh(existing)
                                logger.info(f"After update and commit: description={existing.description}, image_url={existing.image_url}, reporter={existing.reporter}")
                                
                                total_articles += 1
                                logger.info(f"Updated article: {existing.title}")
                                continue
                                
                            # 確保所有必要欄位都有值
                            article = Article(
                                url=url,
                                title=article_data["title"],
                                source="ltn",
                                content=article_data.get("content", ""),
                                published_at=article_data["published_at"],
                                description=article_data.get("description"),
                                image_url=article_data.get("image_url"),
                                category=article_data.get("category"),
                                reporter=article_data.get("reporter")
                            )
                            db.add(article)
                            total_articles += 1
                            logger.info(f"Added new article: {article.title}")
                            
                            # 每 5 篇文章就提交一次
                            if total_articles % 5 == 0:
                                logger.info(f"Committing batch of articles (total: {total_articles})")
                                db.commit()
                        else:
                            logger.warning(f"No data returned for article: {url}")
                            
                    except Exception as e:
                        logger.error(f"Error processing article {url}: {str(e)}", exc_info=True)
                        continue
                
                # 提交剩餘的文章
                if total_articles % 5 != 0:
                    logger.info("Committing remaining articles")
                    db.commit()
                logger.info(f"Completed page {page}, total articles so far: {total_articles}")
                
            except Exception as e:
                logger.error(f"Error crawling page {page}: {str(e)}", exc_info=True)
                continue
        
        logger.info(f"Crawling completed. Total articles added: {total_articles}")
        return {"message": f"Successfully crawled {total_articles} articles"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error in crawling: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        logger.info("Cleaning up crawler")
        crawler.cleanup() 