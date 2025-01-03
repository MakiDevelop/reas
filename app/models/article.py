from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.sql import func
from app.core.database import Base


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(255), unique=True, nullable=False, index=True)
    source = Column(String(50), nullable=False, index=True)
    category = Column(String(100))
    reporter = Column(String(100))
    title = Column(String(255), nullable=False)
    description = Column(Text)
    image_url = Column(Text)
    content = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 複合索引
    __table_args__ = (
        # 標題 + 來源的複合索引，用於搜尋
        Index('idx_title_source', 'title', 'source'),
        # 發布日期 + 來源的複合索引，用於排序和過濾
        Index('idx_published_source', 'published_at', 'source'),
    )

    def __repr__(self):
        return f"<Article {self.title}>"
