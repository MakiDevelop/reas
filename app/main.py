from fastapi import FastAPI, Request, Depends, HTTPException
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
            "params": params
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