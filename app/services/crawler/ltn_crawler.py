from .base import BaseCrawler
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import logging
import requests
from bs4 import BeautifulSoup
import time
import re
from typing import Optional
from app.models.article import Article

logger = logging.getLogger(__name__)

class LTNCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.source_name = "ltn"
        self.base_url = "https://estate.ltn.com.tw"

    async def crawl(self, start_date: str = None, end_date: str = None) -> list:
        """
        爬取入口
        :param start_date: 起始日期 (YYYY-MM-DD)
        :param end_date: 結束日期 (YYYY-MM-DD)
        """
        try:
            # 只在 driver 尚未設置時才初始化
            if not self.driver:
                self.setup_driver()
            articles = []
            page = 1

            # 解析日期範圍
            start_datetime, end_datetime = self.parse_date_range(start_date, end_date)

            # 設定最大頁數
            if not start_date or (start_date == end_date == datetime.now().strftime("%Y-%m-%d")):
                max_pages = 2
            else:
                max_pages = 10

            logger.info(f"開始爬取 LTN，日期範圍: {start_date} ~ {end_date}，最大頁數: {max_pages}")

            while page <= max_pages:
                logger.info(f"開始爬取第 {page} 頁的文章列表")
                article_list = await self.crawl_list(page)

                if not article_list:
                    logger.info(f"第 {page} 頁沒有文章，停止爬取")
                    break

                logger.info(f"第 {page} 頁找到 {len(article_list)} 篇文章")

                has_valid_article = False
                for index, article_info in enumerate(article_list, 1):
                    published_at = article_info.get('published_at')

                    # 檢查日期範圍
                    if published_at:
                        if not self.is_within_date_range(published_at, start_datetime, end_datetime):
                            logger.debug(f"文章日期 {published_at} 不在範圍內，跳過")
                            continue

                    has_valid_article = True
                    logger.info(f"正在爬取第 {page} 頁第 {index} 篇文章: {article_info.get('url')}")

                    article_data = await self.crawl_article(article_info)
                    if article_data:
                        article = Article(
                            title=article_data['title'],
                            content=article_data['content'],
                            url=article_data['url'],
                            published_at=article_data['published_at'],
                            source=article_data['source'],
                            category='房地產',
                            description=article_data.get('description'),
                            image_url=article_data.get('image_url')
                        )
                        articles.append(article)
                        logger.info(f"成功爬取文章: {article.title}")

                # 如果這頁沒有符合日期範圍的文章，停止爬取
                if not has_valid_article:
                    logger.info("本頁沒有符合日期範圍的文章，停止爬取")
                    break

                page += 1

            logger.info(f"LTN 爬蟲完成，總共爬取 {len(articles)} 篇文章")
            return articles

        finally:
            self.cleanup()

    async def crawl_list(self, page: int = 1) -> list:
        """爬取文章列表"""
        try:
            ajax_url = f"{self.base_url}/ajaxList/news/{page}"
            logger.info(f"Fetching AJAX page: {ajax_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(ajax_url, headers=headers)
            if response.status_code == 200:
                articles_data = response.json()
                logger.info(f"Found {len(articles_data)} articles in JSON response")
                
                article_data = []
                for article in articles_data:
                    url = article.get('url', '').replace('\\/', '/')
                    date_str = article.get('A_PublishDT', '')
                    title = article.get('title', '')
                    summary = article.get('summary', '')
                    
                    if url and url.startswith('http'):
                        try:
                            published_at = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            published_at = None
                            logger.warning(f"無法解析日期: {date_str}")
                        
                        article_data.append({
                            'url': url,
                            'title': title,
                            'description': summary,
                            'published_at': published_at
                        })
                        logger.info(f"Added URL: {url}")
            
                return article_data
            else:
                logger.error(f"AJAX request failed with status code: {response.status_code}")
                return []
            
        except Exception as e:
            logger.error(f"Error crawling list page {page}: {str(e)}", exc_info=True)
            return []
    
    async def crawl_article(self, article_info: dict) -> Optional[dict]:
        """爬取單篇文章"""
        url = article_info.get('url')
        if not url:
            return None
        
        logger.info(f"Crawling article: {url}")
        
        try:
            # 載入頁面
            self.driver.get(url)
            time.sleep(3)  # 等待頁面載入
            
            # 取得標題 (使用 h1 標籤)
            try:
                title = self.driver.find_element(By.TAG_NAME, "h1").text.strip()
                logger.info(f"Found title: {title}")
            except:
                title = article_info.get('title', '')
                logger.warning(f"Could not find title element for {url}")
            
            # 取得內文 (使用 class="text boxTitle")
            try:
                content_element = self.driver.find_element(By.CLASS_NAME, "text")
                content = content_element.text.strip()
                
                # 移除不需要的文字
                content = content.replace("請繼續往下閱讀...", "")
                content = content.replace("不用抽 不用搶 現在用APP看新聞 保證天天中獎", "")
                content = content.replace("點我下載APP", "")
                content = content.replace("按我看活動辦法", "")
                
                logger.info(f"Found content with length: {len(content)}")
            except:
                content = ''
                logger.warning(f"Could not find content element for {url}")
                
            # 取得圖片
            try:
                image_element = self.driver.find_element(By.CSS_SELECTOR, ".ph_i img")
                image_url = image_element.get_attribute('src')
            except:
                image_url = None
                
            article_data = {
                'url': url,
                'title': title,
                'content': content,
                'published_at': article_info.get('published_at'),
                'source': 'ltn',
                'image_url': image_url,
                'description': content[:200] if content else None
            }
            
            return article_data
            
        except Exception as e:
            logger.error(f"Error crawling article {url}: {str(e)}", exc_info=True)
            return None
    
    def _clean_content(self, content: str) -> str:
        """清理文章內容"""
        # 移除廣告相關文字
        ad_texts = [
            "不用抽 不用搶 現在用APP看新聞 保證天天中獎",
            "點我下載APP",
            "按我看活動辦法",
            "相關新聞影音",
            "更多房產新聞",
        ]
        
        # 移除廣告文字
        for ad in ad_texts:
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