from typing import List, Optional
from bs4 import BeautifulSoup
import logging
from datetime import datetime
from app.models.article import Article
import requests
from app.core.database import SessionLocal

class NextAppleCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def crawl(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Article]:
        """
        爬取指定日期範圍的新聞文章並存入資料庫
        :param start_date: 起始日期 (YYYY-MM-DD)
        :param end_date: 結束日期 (YYYY-MM-DD)
        """
        logging.info(f"開始爬取新聞 (日期範圍: {start_date or '無限制'} ~ {end_date or '無限制'})...")
        
        # 解析日期範圍
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
        
        all_articles = []
        page = 1
        max_pages = 50
        should_stop = False
        
        while page <= max_pages and not should_stop:
            articles = self.get_news_list(page)
            
            if not articles:
                logging.info(f"第 {page} 頁沒有找到任何文章，停止爬取")
                break
                
            # 檢查文章日期範圍
            has_valid_article = False
            
            for article in articles:
                # 檢查文章日期是否在範圍內
                if (not start_datetime or article.published_at.date() >= start_datetime.date()) and \
                   (not end_datetime or article.published_at.date() <= end_datetime.date()):
                    has_valid_article = True
                    all_articles.append(article)
                    logging.info(f"找到符合日期的文章: {article.title}")
                elif start_datetime and article.published_at.date() < start_datetime.date():
                    should_stop = True
                    break
            
            if not has_valid_article or should_stop:
                logging.info(f"已達到目標起始日期 {start_date}，停止爬取")
                break
                
            page += 1
        
        logging.info(f"共爬取到 {len(all_articles)} 篇符合日期範圍的文章")
        return all_articles

    def get_article_content(self, url: str) -> str:
        """
        爬取文章內容
        """
        try:
            logging.info(f"正在爬取文章內容: {url}")
            response = self.session.get(url)
            
            if response.status_code != 200:
                logging.error(f"取得文章內容失敗: {response.status_code}")
                return ""
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 找到文章內容區塊
            content_blocks = []
            
            # 先找摘要
            summary = soup.select_one("blockquote div")
            if summary:
                content_blocks.append(summary.text.strip())
            
            # 找主要內容
            content_div = soup.select_one("div.post-content")
            if content_div:
                # 取得所有段落
                paragraphs = content_div.select("p")
                for p in paragraphs:
                    # 過濾廣告相關內容
                    if not any(ad_text in p.text for ad_text in ["廣告", "taboola", "AD"]):
                        content_blocks.append(p.text.strip())
            
            content = "\n".join(block for block in content_blocks if block)
            
            if not content:
                logging.warning(f"無法找到文章內容: {url}")
                return ""
            
            return content
            
        except Exception as e:
            logging.error(f"爬取文章內容發生錯誤: {str(e)}")
            return ""

    def get_news_list(self, page: int = 1) -> List[Article]:
        try:
            api_url = f"https://tw.nextapple.com/realtime/property/{page}?infinitescroll=1"
            logging.info(f"正在請求 API: {api_url}")
            
            response = self.session.get(api_url)
            
            if response.status_code != 200:
                logging.error(f"API請求失敗: {response.status_code}")
                return []

            logging.info("成功取得 API 回應")
            
            articles = []
            soup = BeautifulSoup(response.text, "html.parser")
            article_elements = soup.find_all("article", attrs={"articleid": True})
            
            logging.info(f"找到 {len(article_elements)} 篇文章")
            
            for element in article_elements:
                try:
                    title_element = element.select_one("h3 a.post-title")
                    if not title_element:
                        continue
                        
                    url = title_element["href"]
                    title = title_element.text.strip()
                    logging.debug(f"解析文章: {title}")
                    
                    description = element.find("p").text.strip() if element.find("p") else ""
                    image_element = element.find("img")
                    image_url = image_element["data-src"] if image_element else None
                    
                    time_element = element.find("time")
                    if not time_element:
                        continue
                        
                    published_at = datetime.strptime(
                        time_element["datetime"].split("+")[0], 
                        "%Y-%m-%dT%H:%M:%S"
                    )
                    
                    category_element = element.find("div", class_="category")
                    category = category_element.text.strip() if category_element else None
                    
                    # 爬取文章內容
                    content = self.get_article_content(url)
                    if not content:
                        logging.warning(f"無法取得文章內容，跳過: {url}")
                        continue
                    
                    article = Article(
                        url=url,
                        source="nextapple",
                        category=category,
                        title=title,
                        description=description,
                        image_url=image_url,
                        content=content,  # 加入文章內容
                        published_at=published_at
                    )
                    articles.append(article)
                    logging.debug(f"成功解析文章: {title}")
                    
                except Exception as e:
                    logging.warning(f"解析文章失敗: {str(e)}")
                    continue
                    
            return articles
            
        except Exception as e:
            logging.error(f"取得新聞列表失敗: {str(e)}")
            return [] 