from datetime import datetime
from bs4 import BeautifulSoup
import logging
from .base import BaseCrawler
import time
import asyncio
import random
from selenium import webdriver

logger = logging.getLogger(__name__)

class EbcCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.source_name = "EBC地產王"
        self.base_url = "https://house.ebc.net.tw"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://house.ebc.net.tw/'
        }

    def get_chrome_options(self):
        """設定 Chrome 選項"""
        options = webdriver.ChromeOptions()
        
        # 移除一些可能會被偵測的選項
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # 加入必要的 headers
        options.add_argument(f'user-agent={self.headers["User-Agent"]}')
        
        # 啟用 JavaScript (移除 --disable-javascript)
        options.add_argument('--enable-javascript')
        
        # 啟用圖片載入 (移除 --blink-settings=imagesEnabled=false)
        options.add_argument('--blink-settings=imagesEnabled=true')
        
        return options

    async def get_page_source(self, url):
        """取得網頁原始碼"""
        try:
            # 加入延遲，避免被偵測為爬蟲
            await asyncio.sleep(random.uniform(2, 5))
            
            # 使用 selenium 取得頁面
            async with self.get_driver() as driver:
                await driver.get(url)
                
                # 等待頁面載入
                await asyncio.sleep(3)
                
                # 捲動頁面以載入更多內容
                await driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                await asyncio.sleep(2)
                
                return await driver.page_source
                
        except Exception as e:
            logger.error(f"取得頁面失敗: {str(e)}")
            return None

    async def crawl_list(self, page=1):
        """爬取文章列表"""
        try:
            html = await self.get_page_source(self.base_url)
            if not html:
                return []
                
            soup = BeautifulSoup(html, 'html.parser')
            articles = []
            
            # 處理輪播區塊
            for item in soup.select('.hero_slider .swiper-slide'):
                article = self.parse_list_item(item)
                if article:
                    articles.append(article)
                    
            # 處理列表區塊
            for item in soup.select('.list .item'):
                article = self.parse_list_item(item)
                if article:
                    articles.append(article)
                    
            return articles
            
        except Exception as e:
            logger.error(f"爬取列表失敗: {str(e)}")
            return []

    async def crawl_article(self, url):
        """爬取文章內容"""
        try:
            html = await self.get_page_source(url)
            if not html:
                return None
                
            soup = BeautifulSoup(html, 'html.parser')
            
            # 找文章內容
            content_block = soup.select_one('.article-content')
            if not content_block:
                logger.warning(f"找不到文章內容區塊: {url}")
                return None

            # 設定預設圖片
            DEFAULT_IMAGE = "https://house.ebc.net.tw/images/logo.png"
            
            # 取得圖片
            image_url = None
            img = soup.select_one('.article-content img')
            if img:
                image_url = img.get('src', '')
                if image_url and not image_url.startswith('http'):
                    image_url = 'https:' + image_url
            else:
                image_url = DEFAULT_IMAGE

            # 取得內文
            for ad in content_block.select('.ad_block, script, iframe'):
                ad.decompose()
            content = content_block.text.strip()
            
            # 取得描述
            meta_desc = soup.find('meta', {'name': 'description'})
            description = meta_desc.get('content', '') if meta_desc else ""
            
            # 取得發布時間
            time_element = soup.select_one('.article-info time')
            if time_element:
                try:
                    time_text = time_element.text.strip()
                    published_at = datetime.strptime(time_text, '%Y/%m/%d')
                except Exception as e:
                    logger.error(f"解析時間發生錯誤: {str(e)}")
                    published_at = datetime.now()
            else:
                published_at = datetime.now()

            # 取得分類
            category = "房市動態"  # 預設分類
            category_element = soup.select_one('.breadcrumb li:last-child')
            if category_element:
                category = category_element.text.strip()

            return {
                'content': content,
                'description': description,
                'published_at': published_at,
                'image_url': image_url,
                'category': category
            }

        except Exception as e:
            logger.error(f"爬取 EBC 文章內容時發生錯誤: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    async def crawl(self, start_date=None, end_date=None):
        """執行爬蟲"""
        try:
            self.setup_driver()
            logger.debug("Chrome Driver 設定完成")
            
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            articles_list = await self.crawl_list()
            logger.debug(f"從列表頁找到 {len(articles_list)} 篇文章")
            
            articles = []
            for article in articles_list:
                article_content = await self.crawl_article(article['url'])
                if article_content:
                    if start_date and end_date:
                        article_date = article_content['published_at'].date()
                        if not (start_date <= article_date <= end_date):
                            continue
                            
                    articles.append({
                        'title': article['title'],
                        'url': article['url'],
                        'source': self.source_name,
                        'content': article_content['content'],
                        'description': article_content['description'],
                        'published_at': article_content['published_at'],
                        'image_url': article_content['image_url'],
                        'category': article_content['category']
                    })
                    
            logger.debug(f"成功爬取 {len(articles)} 篇文章")
            return articles
            
        except Exception as e:
            logger.error(f"執行 EBC 爬蟲時發生錯誤: {str(e)}")
            return []
            
        finally:
            if hasattr(self, 'driver'):
                self.driver.quit() 

    def parse_article(self, response):
        """解析文章內頁"""
        
        # ... 現有的程式碼 ...
        
        # 取得文章標題
        title = response.css('div.article_header h1::text').get()
        
        # 取得發布時間
        date = response.css('div.article_info_date .date::text').get()
        time = response.css('div.article_info_date .time::text').get()
        publish_time = f"{date} {time}"
        
        # 取得作者/編輯
        author = response.css('div.article_info_editor::text').get()
        
        # 取得文章內容
        content = response.css('div.article_content').get()
        
        # 取得文章分類
        breadcrumb = response.css('div.breadcrumb div:nth-child(2) a::text').get()
        
        # 建立文章資料
        article = {
            'title': title,
            'publish_time': publish_time,
            'author': author,
            'content': content,
            'category': breadcrumb,
            'url': response.url
        }
        
        return article 