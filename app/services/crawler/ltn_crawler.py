from .base import BaseCrawler
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import logging
import requests
from bs4 import BeautifulSoup
import time

logger = logging.getLogger(__name__)

class LTNCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.source_name = "ltn"
        self.base_url = "https://estate.ltn.com.tw"
        
    async def crawl_list(self, page: int = 1) -> list:
        """爬取文章列表"""
        try:
            if page == 1:
                logger.info(f"Crawling first page: {self.base_url}/news")
                self.wait_and_get(f"{self.base_url}/news")
                
                # 等待文章列表載入
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "list_box"))
                )
                
                # 找到所有文章連結（跳過第一個空的 li）
                articles = self.driver.find_elements(By.CSS_SELECTOR, "li.listbox:not(:first-child) a.ph")
                urls = []
                for article in articles:
                    try:
                        url = article.get_attribute("href")
                        if url and url.startswith("http"):
                            urls.append(url)
                    except Exception as e:
                        logger.error(f"Error getting article URL: {str(e)}")
                        continue
                    
            else:
                # 其他頁面使用 AJAX 請求
                ajax_url = f"{self.base_url}/ajaxList/news/{page}"
                logger.info(f"Fetching AJAX page: {ajax_url}")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                response = requests.get(ajax_url, headers=headers)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    articles = soup.select("li.listbox a.ph")
                    urls = [a.get('href') for a in articles if a.get('href') and a.get('href').startswith('http')]
                else:
                    logger.error(f"AJAX request failed with status code: {response.status_code}")
                    return []
            
            # 移除重複的 URL
            urls = list(set(urls))
            logger.info(f"Found {len(urls)} unique articles on page {page}")
            return urls
            
        except Exception as e:
            logger.error(f"Error crawling list page {page}: {str(e)}", exc_info=True)
            return []
    
    async def crawl_article(self, url: str) -> dict:
        """爬取文章內容"""
        try:
            logger.info(f"Crawling article: {url}")
            self.wait_and_get(url)
            
            # 等待文章內容載入
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "whitecon"))
            )
            
            # 取得標題
            title = self.driver.find_element(By.CSS_SELECTOR, "div.whitecon > h1").text.strip()
            
            # 取得發布時間
            time_element = self.driver.find_element(By.CSS_SELECTOR, "div.whitecon span.time")
            published_at = time_element.text.strip()
            
            # 取得內文 (所有 p 標籤的文字)
            content_div = self.driver.find_element(By.CSS_SELECTOR, "div.whitecon div.text")
            paragraphs = content_div.find_elements(By.TAG_NAME, "p")
            content = "\n".join([p.text.strip() for p in paragraphs if p.text.strip()])
            
            # 移除廣告相關文字
            content = content.replace("不用抽 不用搶 現在用APP看新聞 保證天天中獎", "")
            content = content.replace("點我下載APP", "")
            content = content.replace("按我看活動辦法", "")
            
            return {
                "title": title,
                "content": content,
                "published_at": published_at,
                "url": url,
                "source": "ltn"
            }
            
        except Exception as e:
            logger.error(f"Error crawling article {url}: {str(e)}", exc_info=True)
            return None 