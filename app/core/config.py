import os
from typing import Optional, Dict, Any, List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "News API"
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: List[str] = ["*"]
    SECRET_KEY: str = "your-secret-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    
    # Selenium 設定
    SELENIUM_HOST: str = os.getenv("SELENIUM_HOST", "selenium")
    SELENIUM_PORT: int = int(os.getenv("SELENIUM_PORT", "4444"))
    
    # 新聞來源設定
    NEWS_SOURCES: Dict[str, Dict[str, Any]] = {
        "ltn": {
            "name": "自由時報",
            "base_url": "https://estate.ltn.com.tw"
        }
    }
    
    # 資料庫設定
    DATABASE_URL: str = (
        f"postgresql://"
        f"{os.getenv('POSTGRES_USER', 'user')}:"
        f"{os.getenv('POSTGRES_PASSWORD', 'password')}@"
        f"{os.getenv('POSTGRES_SERVER', 'db')}/"
        f"{os.getenv('POSTGRES_DB', 'newsdb')}"
    )

    # Chrome 設定
    CHROME_BIN: str = "/usr/bin/chromium"
    CHROMEDRIVER_PATH: str = "/usr/bin/chromedriver"

    class Config:
        case_sensitive = True

settings = Settings()
