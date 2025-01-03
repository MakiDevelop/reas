import logging
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, distinct
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.article import Article
from app.schemas.article import ArticleInDB
from app.core.config import settings

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