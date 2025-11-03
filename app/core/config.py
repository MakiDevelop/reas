import os
from typing import Optional, Dict, Any, List
from pydantic_settings import BaseSettings
from pydantic import validator

class Settings(BaseSettings):
    PROJECT_NAME: str = "News API"
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: List[str] = ["*"]
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8

    # Selenium 設定
    SELENIUM_HOST: str = "selenium"
    SELENIUM_PORT: int = 4444

    # 新聞來源設定
    NEWS_SOURCES: Dict[str, Dict[str, Any]] = {
        "ltn": {
            "name": "自由時報",
            "base_url": "https://estate.ltn.com.tw"
        }
    }

    # 資料庫設定
    POSTGRES_USER: str = "user"
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str = "db"
    POSTGRES_DB: str = "newsdb"
    DATABASE_URL: Optional[str] = None

    # Chrome 設定
    CHROME_BIN: str = "/usr/bin/chromium"
    CHROMEDRIVER_PATH: str = "/usr/bin/chromedriver"

    # 爬蟲設定
    CRAWLER_MAX_RETRIES: int = 3
    CRAWLER_TIMEOUT: int = 30
    CRAWLER_DELAY_MIN: int = 1
    CRAWLER_DELAY_MAX: int = 3

    # 日誌設定
    LOG_LEVEL: str = "INFO"

    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if isinstance(v, str):
            return v
        return (
            f"postgresql://"
            f"{values.get('POSTGRES_USER')}:"
            f"{values.get('POSTGRES_PASSWORD')}@"
            f"{values.get('POSTGRES_SERVER')}/"
            f"{values.get('POSTGRES_DB')}"
        )

    @validator("SECRET_KEY")
    def validate_secret_key(cls, v: str) -> str:
        if v == "your-secret-key" or v == "your-secret-key-change-this-in-production":
            raise ValueError("Please change SECRET_KEY in production environment")
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v

    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
