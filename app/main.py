from fastapi import FastAPI
from app.core.database import engine, Base
from app.api.v1.api import api_router
import logging
from sqlalchemy import text
from app.core.config import settings

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="房地產新聞爬蟲 API",
    description="提供房地產新聞的搜尋和瀏覽功能",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# 註冊 API 路由（只需要一次）
app.include_router(api_router, prefix=settings.API_V1_STR)

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