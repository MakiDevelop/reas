from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

# 創建資料庫引擎
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # 自動偵測斷開的連接
    pool_size=5,         # 連接池大小
    max_overflow=10      # 超出 pool_size 時的最大連接數
)

# 創建 Session 類別
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# 創建 Base 類別，所有的 Model 都會繼承這個類別
Base = declarative_base()


def get_db():
    """
    獲取資料庫 session 的依賴函數
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
