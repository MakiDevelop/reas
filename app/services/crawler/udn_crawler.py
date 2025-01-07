from .base import BaseCrawler
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import logging
import requests
import time
import re
import asyncio
from app.models.article import Article

logger = logging.getLogger(__name__)

class UDNCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.source_name = "udn"
        self.base_url = "https://house.udn.com"
        
    async def crawl(self, start_date: str = None, end_date: str = None) -> list:
        """
        同步爬取入口
        :param start_date: 起始日期 (YYYY-MM-DD)
        :param end_date: 結束日期 (YYYY-MM-DD)
        """
        return await self._crawl(start_date=start_date, end_date=end_date)
        
    async def _crawl(self, start_date: str = None, end_date: str = None, max_pages: int = 50) -> list:
        """非同步爬取主邏輯"""
        try:
            self.setup_driver()
            articles = []
            page = 1
            
            while page <= max_pages:
                logger.info(f"開始爬取第 {page} 頁的文章列表")
                article_list = await self.crawl_list(page)
                if not article_list:
                    break
                
                logger.info(f"第 {page} 頁找到 {len(article_list)} 篇文章")
                
                for index, article_info in enumerate(article_list, 1):
                    logger.info(f"正在爬取第 {page} 頁第 {index} 篇文章: {article_info.get('url')}")
                    article_data = await self.crawl_article(article_info)
                    if article_data:
                        # 將字典轉換為 Article 物件
                        article = Article(
                            title=article_data['title'],
                            content=article_data['content'],
                            url=article_data['url'],
                            published_at=article_data['published_at'],
                            source=article_data['source'],
                            category=article_data.get('category', '房地產'),
                            reporter=article_data.get('reporter', ''),
                            description=article_data['content'][:200] if article_data['content'] else None,  # 取前200字作為描述
                            image_url=article_info.get('image_url')  # 從文章列表中取得圖片URL
                        )
                        articles.append(article)
                        logger.info(f"成功爬取文章: {article.title}")
                
                page += 1
                
            logger.info(f"爬蟲完成，總共爬取 {len(articles)} 篇文章")
            return articles
            
        finally:
            self.cleanup()

    async def crawl_list(self, page: int = 1) -> list:
        """爬取文章列表"""
        try:
            timestamp = int(time.time() * 1000)
            ajax_url = f"{self.base_url}/house/api/newest?page={page}&_={timestamp}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(ajax_url, headers=headers)
            if response.status_code == 200:
                try:
                    data = response.json()
                    articles_data = []
                    
                    # 解析JSON回應取得文章資訊
                    for article in data.get("lists", []):
                        # 跳過影片內容
                        if article.get("is_video", False):
                            continue
                            
                        url = article.get("url")
                        if url:
                            if url.startswith("/"):
                                full_url = f"{self.base_url}{url}"
                            else:
                                full_url = url
                                
                            articles_data.append({
                                "url": full_url,
                                "image_url": article.get("image_url"),
                                "category": article.get("cate", {}).get("title")
                            })
                            
                    # 檢查是否還有下一頁
                    has_next = not data.get("end", True)
                    logger.info(f"Page {page} has next: {has_next}")
                            
                    return articles_data
                    
                except Exception as e:
                    logger.error(f"Error parsing JSON response: {str(e)}")
                    return []
            else:
                logger.error(f"AJAX request failed with status code: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error crawling list page {page}: {str(e)}", exc_info=True)
            return []
            
    async def crawl_article(self, article_info: dict) -> dict:
        """爬取文章內容"""
        try:
            url = article_info.get('url')
            if not isinstance(url, str):
                logger.error(f"Invalid URL type: {type(url)}")
                return None
            
            # 確保URL是完整的
            if url.startswith("/"):
                url = f"{self.base_url}{url}"
            
            self.wait_and_get(url)
            
            # 等待文章內容載入
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "article-content__title"))
            )
            
            # 取得文章內容
            title = self.driver.find_element(By.CLASS_NAME, "article-content__title").text
            
            # 取得發布時間
            time_element = self.driver.find_element(By.CLASS_NAME, "article-content__time")
            published_at = datetime.strptime(time_element.text, "%Y-%m-%d %H:%M")
            
            # 取得記者
            try:
                reporter = self.driver.find_element(By.CLASS_NAME, "article-content__author").text
            except:
                reporter = None
            
            # 取得內文
            content = self.driver.find_element(By.CLASS_NAME, "article-content__paragraph").text
            content = self._clean_content(content)
            
            return {
                "title": title,
                "content": content,
                "description": content[:100] if content else None,
                "published_at": published_at,
                "url": url,
                "source": self.source_name,
                "image_url": article_info.get('image_url'),
                "reporter": reporter,
                "category": article_info.get('category')
            }
            
        except Exception as e:
            logger.error(f"Error crawling article {url}: {str(e)}", exc_info=True)
            return None
    
    def _clean_content(self, content: str) -> str:
        """清理文章內容"""
        # 移除廣告相關文字
        ad_texts = [
            "googletag.cmd.push",
            "window.fbAsyncInit",
            "分享此文：",
            "延伸閱讀",
            "相關新聞"
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