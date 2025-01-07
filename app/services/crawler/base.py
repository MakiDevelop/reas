from abc import ABC, abstractmethod
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app.core.config import settings
import logging
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class BaseCrawler(ABC):
    def __init__(self):
        self.driver = None
        self.source_name = ""
    
    def setup_driver(self):
        """設定 Selenium WebDriver"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.binary_location = settings.CHROME_BIN
            
            service = Service(executable_path=settings.CHROMEDRIVER_PATH)
            
            logger.info(f"Setting up Chrome driver with options: {chrome_options.arguments}")
            logger.info(f"Chrome binary location: {settings.CHROME_BIN}")
            logger.info(f"ChromeDriver path: {settings.CHROMEDRIVER_PATH}")
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.implicitly_wait(10)
            logger.info(f"{self.source_name} crawler driver setup completed")
            
        except Exception as e:
            logger.error(f"Failed to setup driver: {str(e)}", exc_info=True)
            raise
    
    def cleanup(self):
        """清理資源"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info(f"{self.source_name} crawler cleanup completed")
            except Exception as e:
                # 忽略關閉時的連接錯誤
                if "Connection refused" not in str(e):
                    logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
            finally:
                self.driver = None
    
    def wait_and_get(self, url: str, retry_count: int = 3):
        """安全的頁面載入方法"""
        for i in range(retry_count):
            try:
                self.driver.get(url)
                time.sleep(2)
                return True
            except Exception as e:
                logger.error(f"Attempt {i+1} failed to load {url}: {str(e)}")
                if i == retry_count - 1:
                    raise
                time.sleep(2)
    
    def parse_date_range(self, start_date: Optional[str], end_date: Optional[str]) -> Tuple[Optional[datetime], Optional[datetime]]:
        """解析日期範圍"""
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
        return start_datetime, end_datetime

    def is_within_date_range(self, article_date: datetime, start_datetime: Optional[datetime], end_datetime: Optional[datetime]) -> bool:
        """檢查文章日期是否在指定範圍內"""
        if not article_date:
            return False
        if start_datetime and article_date.date() < start_datetime.date():
            return False
        if end_datetime and article_date.date() > end_datetime.date():
            return False
        return True
    
    @abstractmethod
    async def crawl_list(self, page: int = 1) -> list:
        """爬取文章列表"""
        pass
    
    @abstractmethod
    async def crawl_article(self, url: str) -> dict:
        """爬取單篇文章"""
        pass
    
    async def run(self, max_pages=None, start_date=None, end_date=None):
        """執行爬蟲"""
        try:
            self.setup_driver()
            articles = []
            page = 1
            
            while True:
                # 爬取當前頁面的文章列表
                page_articles = await self.crawl_list(page)
                if not page_articles:
                    break
                    
                # 檢查日期範圍
                has_valid_article = False
                for article_info in page_articles:
                    published_at = article_info.get('published_at')
                    if not published_at:
                        continue
                        
                    article_date = published_at.date()
                    
                    # 如果文章日期在目標範圍內，爬取詳細內容
                    if start_date and article_date < datetime.strptime(start_date, '%Y-%m-%d').date():
                        continue
                    if end_date and article_date > datetime.strptime(end_date, '%Y-%m-%d').date():
                        continue
                        
                    has_valid_article = True
                    article = await self.crawl_article(article_info)
                    if article:
                        articles.append(article)
                
                # 如果這頁沒有任何符合日期的文章，就停止爬取
                if not has_valid_article:
                    logger.info("本頁沒有符合日期範圍的文章，停止爬取")
                    break
                    
                # 檢查是否達到最大頁數
                if max_pages and page >= max_pages:
                    break
                    
                page += 1
                
            return articles
            
        finally:
            self.cleanup()