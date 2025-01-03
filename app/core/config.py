from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 專案基本設定
    PROJECT_NAME: str = "房地產新聞爬蟲"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # 資料庫設定
    DATABASE_URL: str = "postgresql://user:password@db:5432/newsdb"
    
    # 爬蟲設定
    CHROME_DRIVER_PATH: Optional[str] = None
    CRAWLER_DELAY: int = 3  # 爬蟲延遲秒數
    MAX_RETRIES: int = 3    # 最大重試次數
    
    # 新聞來源網站
    NEWS_SOURCES = {
        "ltn": "https://estate.ltn.com.tw/news",
        "chinatimes": "https://house.chinatimes.com/",
        "udn": "https://house.udn.com/house/index",
        "appledaily": "https://tw.nextapple.com/realtime/property"
    }

    class Config:
        case_sensitive = True
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    """
    獲取設定實例，使用 lru_cache 裝飾器來避免重複讀取
    """
    return Settings()


# 建立設定實例
settings = get_settings()
