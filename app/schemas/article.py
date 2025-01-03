from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class ArticleBase(BaseModel):
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    source: str
    category: Optional[str] = None
    published_at: datetime

class ArticleCreate(ArticleBase):
    pass

class ArticleUpdate(ArticleBase):
    pass

class ArticleInDB(ArticleBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)

class ArticleList(BaseModel):
    items: list[ArticleInDB]
    total: int
    skip: int
    limit: int

class ArticleSearch(BaseModel):
    keyword: Optional[str] = None
    source: Optional[str] = None
    category: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
