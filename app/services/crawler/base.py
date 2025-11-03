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
from selenium.common.exceptions import TimeoutException
import random
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

logger = logging.getLogger(__name__)

class BaseCrawler(ABC):
    def __init__(self):
        self.driver = None
        self.source_name = ""
        self.needs_javascript = True  # 預設需要 JavaScript，子類可以覆寫
    
    def setup_driver(self):
        """設置 Chrome Driver"""
        try:
            chrome_options = webdriver.ChromeOptions()
            
            # 基本設定
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            
            # 效能優化
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-infobars')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--disable-logging')
            chrome_options.add_argument('--disable-software-rasterizer')
            # 只在不需要 JavaScript 時才禁用
            if not self.needs_javascript:
                chrome_options.add_argument('--disable-javascript')
            chrome_options.add_argument('--blink-settings=imagesEnabled=false')  # 不載入圖片
            
            # 記憶體優化
            chrome_options.add_argument('--disable-features=site-per-process')
            chrome_options.add_argument('--disable-features=TranslateUI')
            chrome_options.add_argument('--disable-features=BlinkGenPropertyTrees')
            
            # 設定頁面載入策略
            chrome_options.set_capability('pageLoadStrategy', 'none')
            
            # 記錄設定
            logger.info(f"Setting up Chrome driver with options: {chrome_options.arguments}")
            
            # 設定 Chrome 二進制檔案位置
            chrome_binary_location = "/usr/bin/chromium"
            chrome_options.binary_location = chrome_binary_location
            logger.info(f"Chrome binary location: {chrome_binary_location}")
            
            # 設定 ChromeDriver 路徑
            chromedriver_path = "/usr/bin/chromedriver"
            logger.info(f"ChromeDriver path: {chromedriver_path}")
            
            # 建立 Service 物件
            service = Service(executable_path=chromedriver_path)
            
            # 建立 WebDriver
            self.driver = webdriver.Chrome(
                service=service,
                options=chrome_options
            )
            
            # 設定較短的超時時間
            self.driver.set_page_load_timeout(20)  # 縮短到 20 秒
            self.driver.set_script_timeout(20)
            
            logger.info(f"{self.source_name} crawler driver setup completed")
            
        except Exception as e:
            logger.error(f"Error setting up Chrome driver: {str(e)}", exc_info=True)
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
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((TimeoutException, ConnectionError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def wait_and_get(self, url: str) -> None:
        """等待頁面載入完成（帶重試機制）"""
        try:
            # 加入隨機延遲
            delay = random.uniform(
                settings.CRAWLER_DELAY_MIN,
                settings.CRAWLER_DELAY_MAX
            )
            time.sleep(delay)

            self.driver.get(url)

            # 等待頁面主要元素載入
            WebDriverWait(self.driver, 5).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )

        except TimeoutException as e:
            logger.warning(f"Timeout loading URL: {url}")
            # 重試前清除快取
            try:
                self.driver.execute_script("window.localStorage.clear();")
                self.driver.execute_script("window.sessionStorage.clear();")
                self.driver.delete_all_cookies()
            except:
                pass
            raise

        except Exception as e:
            logger.error(f"Error loading page {url}: {str(e)}")
            raise
    
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

    @staticmethod
    def parse_flexible_date(date_text: str) -> Optional[datetime]:
        """
        統一的日期解析邏輯，支援多種日期格式

        Args:
            date_text: 日期文字

        Returns:
            datetime 物件或 None
        """
        if not date_text:
            return None

        # 清理日期文字
        date_text = date_text.strip()

        # 移除可能的干擾文字
        for remove_text in ["|", "Updated", "發布", "更新"]:
            if remove_text in date_text:
                date_text = date_text.split(remove_text)[0].strip()

        # 嘗試多種日期格式
        date_formats = [
            '%Y-%m-%d %H:%M:%S',  # 2025-01-01 12:00:00
            '%Y-%m-%d %H:%M',     # 2025-01-01 12:00
            '%Y-%m-%d',           # 2025-01-01
            '%Y/%m/%d %H:%M:%S',  # 2025/01/01 12:00:00
            '%Y/%m/%d %H:%M',     # 2025/01/01 12:00
            '%Y/%m/%d',           # 2025/01/01
            '%d %b %Y',           # 01 Jan 2025
            '%B %d, %Y',          # January 01, 2025
            '%b %d, %Y',          # Jan 01, 2025
            '%d/%m/%Y',           # 01/01/2025
            '%m/%d/%Y',           # 01/01/2025
        ]

        for date_format in date_formats:
            try:
                return datetime.strptime(date_text, date_format)
            except ValueError:
                continue

        logger.warning(f"無法解析日期: {date_text}")
        return None

    @staticmethod
    def clean_content(content: str, ad_texts: List[str] = None) -> str:
        """
        統一的內容清理邏輯

        Args:
            content: 原始內容
            ad_texts: 要移除的廣告文字列表

        Returns:
            清理後的內容
        """
        import re

        if not content:
            return ""

        # 預設廣告文字
        default_ads = [
            "不用抽 不用搶 現在用APP看新聞 保證天天中獎",
            "點我下載APP",
            "按我看活動辦法",
            "請繼續往下閱讀...",
            "Subscribe to our Telegram channel",
            "Click to subscribe",
            "Follow us on",
            "For the latest property news",
        ]

        ad_texts = ad_texts or []
        all_ads = default_ads + ad_texts

        # 移除廣告文字
        for ad in all_ads:
            content = content.replace(ad, "")

        # 移除多餘的空白行
        lines = [line.strip() for line in content.split('\n')]
        lines = [line for line in lines if line]

        # 移除重複的行
        lines = list(dict.fromkeys(lines))

        # 重新組合內容
        content = '\n'.join(lines)

        # 移除連續的空格
        content = re.sub(r'\s+', ' ', content).strip()

        return content
    
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
                # 在請求之間加入隨機延遲
                time.sleep(random.uniform(1, 3))
                
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