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

logger = logging.getLogger(__name__)

class LTNCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.source_name = "ltn"
        self.base_url = "https://estate.ltn.com.tw"
        
    async def crawl_list(self, page: int = 1) -> list:
        """爬取文章列表"""
        try:
            # 所有頁面都使用 AJAX 請求
            ajax_url = f"{self.base_url}/ajaxList/news/{page}"
            logger.info(f"Fetching AJAX page: {ajax_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(ajax_url, headers=headers)
            if response.status_code == 200:
                try:
                    articles_data = response.json()
                    logger.info(f"Found {len(articles_data)} articles in JSON response")
                    
                    article_data = []
                    for article in articles_data:
                        url = article.get('url', '').replace('\/', '/')
                        date_str = article.get('A_PublishDT', '')
                        
                        if url and url.startswith('http'):
                            try:
                                published_at = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                published_at = None
                                logger.warning(f"無法解析日期: {date_str}")
                            
                            article_data.append({
                                'url': url,
                                'published_at': published_at
                            })
                            logger.info(f"Added URL: {url}")
                            
                except Exception as e:
                    logger.error(f"Error parsing JSON response: {str(e)}")
                    return []
            else:
                logger.error(f"AJAX request failed with status code: {response.status_code}")
                return []
            
            # 移除重複的文章
            seen_urls = set()
            unique_articles = []
            for article in article_data:
                if article['url'] not in seen_urls:
                    seen_urls.add(article['url'])
                    unique_articles.append(article)
            
            logger.info(f"Found {len(unique_articles)} unique articles on page {page}")
            return unique_articles
            
        except Exception as e:
            logger.error(f"Error crawling list page {page}: {str(e)}", exc_info=True)
            return []
    
    async def crawl_article(self, article_info: dict) -> dict:
        """爬取文章內容"""
        try:
            url = article_info['url']
            logger.info(f"Crawling article: {url}")
            self.wait_and_get(url)
            
            # 等待文章內容載入
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "whitecon"))
            )
            
            # 取得標題
            title = self.driver.find_element(By.CSS_SELECTOR, "div.whitecon > h1").text.strip()
            
            # 取得發布時間和記者
            author_element = self.driver.find_element(By.CSS_SELECTOR, "div.whitecon div.boxTitle p.author")
            author_text = author_element.text.strip()
            
            # 解析時間和記者
            published_text = ""
            reporter = None
            if "文/" in author_text:
                parts = author_text.split("文/")
                published_text = parts[0].strip()
                reporter = parts[1].strip() if len(parts) > 1 else None
            else:
                published_text = author_text
            
            # 使用列表頁的發布時間，如果沒有則從文章內容解析
            published_at = article_info.get('published_at')
            if not published_at:
                try:
                    published_at = datetime.strptime(published_text, "%Y/%m/%d %H:%M")
                except ValueError:
                    logger.error(f"無法解析日期: {published_text}")
                    published_at = None
            
            # 取得內文
            content_div = self.driver.find_element(By.CSS_SELECTOR, "div.whitecon div.text")
            content = content_div.text
            content = self._clean_content(content)
            
            # 取得摘要（取內文前 100 字）
            description = content[:100] if content else None
            
            # 取得主要圖片 URL
            image_url = None
            try:
                images = content_div.find_elements(By.TAG_NAME, "img")
                if images:
                    image_url = images[0].get_attribute("src")
            except Exception as e:
                logger.warning(f"取得圖片時發生錯誤: {str(e)}")
            
            return {
                "title": title,
                "content": content,
                "description": description,
                "published_at": published_at,
                "url": url,
                "source": self.source_name,
                "image_url": image_url,
                "reporter": reporter,
                "category": None  # 目前沒有類別資訊
            }
            
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