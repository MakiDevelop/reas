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
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-infobars')
            chrome_options.binary_location = settings.CHROME_BIN
            
            service = Service(executable_path=settings.CHROME_DRIVER_PATH)
            
            logger.info(f"Setting up Chrome driver with options: {chrome_options.arguments}")
            logger.info(f"Chrome binary location: {settings.CHROME_BIN}")
            logger.info(f"ChromeDriver path: {settings.CHROME_DRIVER_PATH}")
            
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
                logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
    
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
    
    @abstractmethod
    async def crawl_list(self, page: int = 1) -> list:
        """爬取文章列表"""
        pass
    
    @abstractmethod
    async def crawl_article(self, url: str) -> dict:
        """爬取單篇文章"""
        pass
    
    async def run(self, max_pages: int = 1):
        """執行爬蟲"""
        try:
            self.setup_driver()
            articles = []
            
            for page in range(1, max_pages + 1):
                try:
                    page_articles = await self.crawl_list(page)
                    articles.extend(page_articles)
                    logger.info(f"Crawled page {page}, got {len(page_articles)} articles")
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"Error crawling page {page}: {str(e)}", exc_info=True)
                    continue
            
            results = []
            for article_url in articles:
                try:
                    article_data = await self.crawl_article(article_url)
                    results.append(article_data)
                    logger.info(f"Crawled article: {article_data.get('title', 'Unknown')}")
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"Error crawling article {article_url}: {str(e)}", exc_info=True)
                    continue
            
            return results
        finally:
            self.cleanup() 