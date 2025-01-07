from fastapi import FastAPI, Request, Depends, HTTPException, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.core.database import engine, Base, get_db
from app.api.v1.api import api_router
from app.models.article import Article
import logging
from sqlalchemy import text, desc, or_
from app.core.config import settings
from math import ceil
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import subprocess
from fastapi.responses import RedirectResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Optional
import asyncio
from app.tests.test_crawler import test_crawler

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="房地產新聞爬蟲 API",
    description="提供房地產新聞的搜尋和瀏覽功能",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# 註定模板和靜態檔案
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 註冊 API 路由
app.include_router(api_router, prefix=settings.API_V1_STR)

# 建立排程器
scheduler = AsyncIOScheduler()

async def run_crawler_in_background(crawler_type: str = "all", start_date: str = None, end_date: str = None):
    """在背景執行爬蟲"""
    try:
        # 如果沒有指定日期，使用今天
        if not start_date or not end_date:
            start_date = end_date = datetime.now().strftime("%Y-%m-%d")
            
        # 定義要爬取的新聞來源
        sources = ["udn", "ltn", "nextapple"] if crawler_type == "all" else [crawler_type]
        
        for source in sources:
            try:
                # 執行爬蟲指令
                subprocess.run([
                    "python", 
                    "-m", 
                    "app.tests.test_crawler",
                    source,
                    "--start_date", 
                    start_date,
                    "--end_date",
                    end_date
                ], check=True)
                logger.info(f"{source} 爬蟲完成: {datetime.now()}")
            except subprocess.CalledProcessError as e:
                logger.error(f"{source} 爬蟲執行失敗: {str(e)}")
                
    except Exception as e:
        logger.error(f"爬蟲執行失敗: {str(e)}")

async def crawl_today():
    """排程爬蟲任務"""
    background_tasks = BackgroundTasks()
    background_tasks.add_task(run_crawler_in_background)
    await background_tasks()

# 設定排程任務
def setup_scheduler():
    # 每天 8:00 執行
    scheduler.add_job(
        crawl_today,
        CronTrigger(hour=8, minute=0)
    )
    
    # 每天 12:00 執行
    scheduler.add_job(
        crawl_today,
        CronTrigger(hour=12, minute=0)
    )
    
    # 每天 16:00 執行
    scheduler.add_job(
        crawl_today,
        CronTrigger(hour=16, minute=0)
    )
    
    # 每天 20:00 執行
    scheduler.add_job(
        crawl_today,
        CronTrigger(hour=20, minute=0)
    )
    
    # 啟動排程器
    scheduler.start()
    logger.info("排程器已啟動")

# 前台頁面路由
@app.get("/", name="index")
async def index(
    request: Request, 
    page: int = 1,
    source: str = None,
    category: str = None,
    start_date: str = None,
    end_date: str = None,
    keyword: str = None,
    error: str = None,
    db: Session = Depends(get_db)
):
    # 設定每頁顯示數量
    per_page = 20
    
    # 建立基本查詢
    query = db.query(Article)
    
    # 加入搜尋條件
    if keyword:
        query = query.filter(
            or_(
                Article.title.ilike(f"%{keyword}%"),
                Article.content.ilike(f"%{keyword}%")
            )
        )
    
    if source:
        query = query.filter(Article.source == source)
    
    # 計算總數和頁數
    total = query.count()
    total_pages = ceil(total / per_page)
    
    # 取得分頁資料
    articles = query\
        .order_by(desc(Article.published_at))\
        .offset((page - 1) * per_page)\
        .limit(per_page)\
        .all()
    
    # 取得所有來源選項
    sources = db.query(Article.source).distinct().all()
    sources = [source[0] for source in sources]
    
    # 建立查詢參數字典
    params = {}
    if source:
        params['source'] = source
    if category:
        params['category'] = category
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date
    if keyword:
        params['keyword'] = keyword

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "articles": articles,
            "current_page": page,
            "total_pages": total_pages,
            "total": total,
            "keyword": keyword,
            "source": source,
            "sources": sources,
            "params": params,
            "error": error
        }
    )

@app.get("/article/{id}")
async def article_detail(
    request: Request,
    id: int,
    db: Session = Depends(get_db)
):
    # 取得文章詳細資料
    article = db.query(Article).filter(Article.id == id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # 取得相關文章（同一來源的最新5篇其他文章）
    related_articles = db.query(Article)\
        .filter(Article.source == article.source)\
        .filter(Article.id != article.id)\
        .order_by(desc(Article.published_at))\
        .limit(5)\
        .all()
    
    return templates.TemplateResponse(
        "detail.html",
        {
            "request": request,
            "article": article,
            "related_articles": related_articles
        }
    )

@app.on_event("startup")
async def startup_event():
    """
    應用啟動時執行的事件
    """
    try:
        # 嘗試創建所有資料表
        Base.metadata.create_all(bind=engine)
        # 測試資料庫連接
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("資料庫連接成功！")
    except Exception as e:
        logger.error(f"資料庫連接失敗：{str(e)}")
        raise e

    setup_scheduler()

# 在應用程式關閉時關閉排程器
@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    logger.info("排程器已關閉")

@app.get("/health")
def health_check():
    """
    健康檢查端點
    """
    try:
        # 測試資料庫連接
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": str(e)
        }

@app.get("/crawl/latest", name="crawl_latest")
async def crawl_latest(background_tasks: BackgroundTasks):
    """爬取最新一天的新聞"""
    try:
        # 在背景執行所有爬蟲
        background_tasks.add_task(run_crawler_in_background)
        return RedirectResponse(url="/?message=crawl_started", status_code=303)
    except Exception as e:
        logger.error(f"爬蟲執行失敗: {str(e)}")
        return RedirectResponse(url="/?error=crawl_failed", status_code=303)

@app.get("/crawl/last-week", name="crawl_last_week")
async def crawl_last_week(background_tasks: BackgroundTasks):
    """爬取最近七天的新聞"""
    try:
        # 計算日期範圍
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        # 在背景執行所有爬蟲
        background_tasks.add_task(
            run_crawler_in_background,
            start_date=start_date,
            end_date=end_date
        )
        
        return RedirectResponse(url="/?message=crawl_started", status_code=303)
    except Exception as e:
        logger.error(f"爬蟲執行失敗: {str(e)}")
        return RedirectResponse(url="/?error=crawl_failed", status_code=303)

@app.post("/api/crawl")
async def crawl_articles(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    crawler_type: Optional[str] = None
):
    """爬取文章"""
    try:
        results = []
        crawlers = ["ltn", "udn", "nextapple"] if not crawler_type else [crawler_type]
        
        for source in crawlers:
            try:
                logger.info(f"開始爬取 {source} 文章...")
                count = await test_crawler(
                    crawler_type=source,
                    start_date=start_date,
                    end_date=end_date
                )
                results.append({
                    "source": source,
                    "status": "success",
                    "count": count,
                    "message": f"成功爬取 {count} 篇文章"
                })
                logger.info(f"{source} 爬蟲完成，共爬取 {count} 篇文章")
                
            except Exception as e:
                logger.error(f"{source} 爬蟲失敗: {str(e)}")
                results.append({
                    "source": source,
                    "status": "error",
                    "count": 0,
                    "message": f"爬取失敗: {str(e)}"
                })
                
            # 每個爬蟲之間暫停一下
            await asyncio.sleep(2)
        
        return {
            "status": "success",
            "message": "爬蟲執行完成",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"爬蟲執行失敗: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )