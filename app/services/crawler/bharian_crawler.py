import logging
import random
import time
import re
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options

from app.services.crawler.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

class BHarianCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.source_name = "Berita Harian Property"
        self.base_url = "https://www.bharian.com.my"
        self.property_url = f"{self.base_url}/bisnes/hartanah"
        
        # 馬來文月份對應表
        self.malay_month_map = {
            'Jan': 1, 'Januari': 1, 
            'Feb': 2, 'Februari': 2, 
            'Mac': 3, 'March': 3,
            'Apr': 4, 'April': 4,
            'Mei': 5, 'May': 5,
            'Jun': 6, 'June': 6,
            'Jul': 7, 'Julai': 7, 'July': 7,
            'Ogos': 8, 'Aug': 8, 'August': 8,
            'Sep': 9, 'Sept': 9, 'September': 9,
            'Okt': 10, 'Oct': 10, 'Oktober': 10, 'October': 10,
            'Nov': 11, 'November': 11,
            'Dis': 12, 'Dec': 12, 'Disember': 12, 'December': 12
        }
    
    def setup_driver(self):
        """設置驅動程序"""
        options = Options()
        
        # 基本設置
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        # 模擬真實用戶
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # 設置用戶代理
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
        ]
        options.add_argument(f'user-agent={random.choice(user_agents)}')
        
        # 設置Chrome二進制文件的位置
        if os.path.exists('/usr/bin/chromium'):
            options.binary_location = '/usr/bin/chromium'
            logger.info(f"Chrome binary location: {options.binary_location}")
        
        # 直接創建驅動程序
        from selenium import webdriver
        self.driver = webdriver.Chrome(options=options)
        
        # 設置驅動程序的超時時間（秒）
        self.driver.set_script_timeout(30)
        self.driver.set_page_load_timeout(30)
        
        # 添加自定義JavaScript來繞過反爬蟲檢測
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            """
        })
        
        logger.info(f"{self.source_name} crawler driver setup completed")
        
    async def crawl(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """執行爬蟲主程序"""
        try:
            # 設定 Chrome Driver
            self.setup_driver()
            logger.info("Chrome Driver 設定完成")
            
            # 確保 start_date 和 end_date 是 datetime.date 物件
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            all_articles = []
            page = 1
            max_pages = 3  # 最多爬取3頁，減少時間
            should_stop = False
            
            while page <= max_pages and not should_stop:
                logger.info(f"正在爬取第 {page} 頁")
                articles_list = await self.crawl_list(page)
                
                if not articles_list:
                    logger.info(f"第 {page} 頁沒有找到文章，停止爬取")
                    break
                
                logger.info(f"從第 {page} 頁找到 {len(articles_list)} 篇文章")
                
                # 處理每篇文章
                for article_info in articles_list:
                    # 檢查文章日期是否在指定範圍內
                    if start_date and end_date and article_info.get('published_at'):
                        article_date = article_info['published_at'].date()
                        if not (start_date <= article_date <= end_date):
                            logger.debug(f"文章日期 {article_date} 不在指定範圍內，跳過")
                            # 如果文章日期早於起始日期，可以考慮停止爬取
                            if article_date < start_date:
                                should_stop = True
                            continue
                    
                    article_data = await self.crawl_article(article_info)
                    
                    if not article_data:
                        continue
                    
                    # 合併文章信息
                    full_article = {
                        'title': article_data['title'],
                        'url': article_info['url'],
                        'source': self.source_name,
                        'content': article_data['content'],
                        'description': article_data.get('description', ''),
                        'published_at': article_data['published_at'],
                        'image_url': article_data.get('image_url') or article_info.get('image_url', ''),
                        'category': article_data.get('category') or article_info.get('category', 'Hartanah'),
                        'reporter': article_data.get('author', '')
                    }
                    
                    all_articles.append(full_article)
                    logger.info(f"成功新增文章: {full_article['title']}")
                    
                    # 隨機等待，避免被檢測為機器人
                    time.sleep(random.uniform(1, 2))
                
                # 進入下一頁
                page += 1
                
            logger.info(f"成功爬取 {len(all_articles)} 篇文章")
            return all_articles
            
        except Exception as e:
            logger.error(f"執行 Berita Harian 爬蟲時發生錯誤: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
            
        finally:
            self.cleanup()
    
    def _handle_possible_popups(self):
        """處理可能的彈窗，如cookie通知或訂閱提示"""
        try:
            # 嘗試查找並點擊常見的彈窗按鈕
            for selector in ['button.accept-cookies', 'button.accept', '.cookie-notice .accept', 
                            '.gdpr-banner .accept', '.consent-banner .accept', 
                            'button:contains("Accept")', 'button:contains("OK")', 
                            'button:contains("Close")', '.modal .close']:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        for element in elements:
                            if element.is_displayed():
                                element.click()
                                logger.info(f"點擊了彈窗按鈕: {selector}")
                                time.sleep(1)
                except Exception as e:
                    logger.debug(f"嘗試點擊 {selector} 時出錯: {str(e)}")
            
            # 嘗試按ESC鍵關閉彈窗
            from selenium.webdriver.common.keys import Keys
            from selenium.webdriver.common.action_chains import ActionChains
            
            actions = ActionChains(self.driver)
            actions.send_keys(Keys.ESCAPE)
            actions.perform()
            logger.debug("發送了ESC鍵")
            
        except Exception as e:
            logger.warning(f"處理彈窗時發生錯誤: {str(e)}")
    
    def wait_and_get(self, url):
        """等待和獲取頁面"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                self.driver.get(url)
                
                # 等待頁面加載
                time.sleep(5)
                
                # 檢查頁面是否成功加載
                if len(self.driver.page_source) < 1000:
                    logger.warning(f"頁面內容太短，可能未成功加載: {len(self.driver.page_source)} 字符")
                    retry_count += 1
                    time.sleep(2)
                    continue
                
                # 處理可能的彈窗
                self._handle_possible_popups()
                
                return True
            except Exception as e:
                logger.error(f"訪問 {url} 時發生錯誤: {str(e)}")
                retry_count += 1
                if retry_count >= max_retries:
                    raise
                time.sleep(2)
    
    async def crawl_list(self, page: int = 1) -> List[Dict[str, Any]]:
        """爬取文章列表頁"""
        try:
            # 構建分頁URL
            if page == 1:
                url = self.property_url
            else:
                url = f"{self.property_url}?page={page-1}"
            
            logger.info(f"正在訪問列表頁: {url}")
            
            # 訪問頁面
            self.wait_and_get(url)
            
            # 等待頁面加載
            time.sleep(5)
            
            # 滾動頁面以加載更多內容
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            # 解析頁面
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 查找文章列表
            articles = []
            
            # 嘗試找到文章容器
            article_containers = soup.select('.views-row')
            
            if not article_containers:
                # 嘗試其他可能的選擇器
                article_containers = soup.select('.teaser, .article-teaser, .node--type-article')
            
            if not article_containers:
                # 直接查找所有可能是文章的鏈接
                links = soup.select('a[href*="/bisnes/hartanah/"]')
                
                if not links:
                    logger.warning("找不到文章容器或鏈接")
                    return []
                
                # 處理找到的鏈接
                for link in links:
                    url = link.get('href')
                    if not url:
                        continue
                    
                    # 確保URL是完整的
                    if not url.startswith('http'):
                        url = self.base_url + url if url.startswith('/') else self.base_url + '/' + url
                    
                    # 提取標題
                    title = link.get_text().strip()
                    
                    # 查找可能的圖片
                    img = link.select_one('img')
                    image_url = ''
                    if img:
                        image_url = img.get('src', '')
                        if image_url and not image_url.startswith('http'):
                            image_url = self.base_url + image_url if image_url.startswith('/') else self.base_url + '/' + image_url
                    
                    articles.append({
                        'title': title,
                        'url': url,
                        'image_url': image_url,
                        'category': 'Hartanah',
                        'published_at': None,
                        'description': ''
                    })
            else:
                # 處理找到的文章容器
                for container in article_containers:
                    # 查找鏈接
                    link = container.select_one('a')
                    if not link:
                        continue
                    
                    url = link.get('href')
                    if not url:
                        continue
                    
                    # 確保URL是完整的
                    if not url.startswith('http'):
                        url = self.base_url + url if url.startswith('/') else self.base_url + '/' + url
                    
                    # 查找標題
                    title_element = container.select_one('h3, h2, .title')
                    title = title_element.get_text().strip() if title_element else link.get_text().strip()
                    
                    # 查找圖片
                    img = container.select_one('img')
                    image_url = ''
                    if img:
                        image_url = img.get('src', '')
                        if image_url and not image_url.startswith('http'):
                            image_url = self.base_url + image_url if image_url.startswith('/') else self.base_url + '/' + image_url
                    
                    # 查找日期
                    date_element = container.select_one('.date, time, .meta')
                    published_at = None
                    if date_element:
                        date_text = date_element.get_text().strip()
                        published_at = self.parse_malay_date(date_text)
                    
                    # 查找描述
                    desc_element = container.select_one('.summary, .teaser-text, .field--name-field-summary')
                    description = desc_element.get_text().strip() if desc_element else ''
                    
                    articles.append({
                        'title': title,
                        'url': url,
                        'image_url': image_url,
                        'category': 'Hartanah',
                        'published_at': published_at,
                        'description': description
                    })
            
            logger.info(f"從列表頁找到 {len(articles)} 篇文章")
            return articles
            
        except Exception as e:
            logger.error(f"爬取文章列表時發生錯誤: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def crawl_article(self, article_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """爬取文章內容"""
        try:
            url = article_info.get('url')
            if not url:
                return None
            
            logger.info(f"正在爬取文章: {url}")
            
            # 訪問文章頁面
            self.wait_and_get(url)
            
            # 等待頁面加載
            time.sleep(5)
            
            # 滾動頁面以加載更多內容
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight*2/3);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # 解析頁面
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 提取標題
            title_element = soup.select_one('h1, .article-title, .page-title')
            title = title_element.get_text().strip() if title_element else article_info.get('title', '')
            
            # 提取作者
            author_element = soup.select_one('.author, .byline, [rel="author"]')
            author = author_element.get_text().strip() if author_element else ''
            
            # 提取發布日期
            date_element = soup.select_one('.date, time, .meta, .published')
            published_at = article_info.get('published_at')
            
            if date_element:
                date_text = date_element.get_text().strip()
                parsed_date = self.parse_malay_date(date_text)
                if parsed_date:
                    published_at = parsed_date
            
            if not published_at:
                published_at = datetime.now()
            
            # 提取文章圖片
            image_element = soup.select_one('.article-image img, .field--name-field-image img, figure img')
            image_url = article_info.get('image_url', '')
            
            if image_element:
                new_image_url = image_element.get('src', '') or image_element.get('data-src', '')
                if new_image_url:
                    if not new_image_url.startswith('http'):
                        new_image_url = self.base_url + new_image_url if new_image_url.startswith('/') else self.base_url + '/' + new_image_url
                    image_url = new_image_url
            
            # 提取文章內容
            content_element = soup.select_one('.article-body, .field--name-body, .content, article')
            content = ''
            
            if content_element:
                # 提取所有段落
                paragraphs = []
                
                for p in content_element.select('p'):
                    if p.text.strip():
                        paragraphs.append(p.text.strip())
                
                if paragraphs:
                    content = '\n\n'.join(paragraphs)
                else:
                    # 如果找不到段落，直接使用內容元素的文本
                    content = content_element.text.strip()
            
            # 如果仍然沒有內容，嘗試從整個頁面提取文本
            if not content:
                main_content = soup.select_one('main, article, .content, .article')
                if main_content:
                    # 排除一些不需要的元素
                    for el in main_content.select('header, footer, nav, aside, script, style'):
                        el.decompose()
                    
                    # 提取所有文本
                    content = main_content.get_text(separator='\n', strip=True)
            
            # 清理內容
            content = self._clean_content(content)
            
            if not content:
                logger.warning("無法提取文章內容")
                return None
            
            # 提取描述
            description = article_info.get('description', '') or content[:200]
            
            return {
                'title': title,
                'content': content,
                'description': description,
                'published_at': published_at,
                'image_url': image_url,
                'author': author,
                'category': article_info.get('category', 'Hartanah')
            }
            
        except Exception as e:
            logger.error(f"爬取文章內容時發生錯誤: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def parse_malay_date(self, date_text: str) -> Optional[datetime]:
        """解析馬來文日期格式"""
        try:
            # 移除可能的前後空格
            date_text = date_text.strip()
            
            # 檢查是否包含 "@" 符號，通常表示有時間部分
            if "@" in date_text:
                # 分割日期和時間部分
                date_part, time_part = date_text.split("@")
                date_part = date_part.strip()
                time_part = time_part.strip()
                
                # 解析日期部分
                match = re.match(r'(\w+)\s+(\d+),\s+(\d{4})', date_part)
                
                if match:
                    month_name, day, year = match.groups()
                    
                    # 將馬來文月份轉換為數字
                    if month_name in self.malay_month_map:
                        month = self.malay_month_map[month_name]
                        
                        # 解析時間部分
                        time_match = re.match(r'(\d+):(\d+)(am|pm)', time_part)
                        
                        if time_match:
                            hour, minute, am_pm = time_match.groups()
                            hour = int(hour)
                            minute = int(minute)
                            
                            # 處理 12 小時制
                            if am_pm.lower() == 'pm' and hour < 12:
                                hour += 12
                            elif am_pm.lower() == 'am' and hour == 12:
                                hour = 0
                            
                            return datetime(int(year), month, int(day), hour, minute)
                        else:
                            # 如果無法解析時間部分，只使用日期
                            return datetime(int(year), month, int(day))
            
            # 嘗試其他常見格式
            # 格式: "5 Mei 2025"
            match = re.match(r'(\d+)\s+(\w+)\s+(\d{4})', date_text)
            if match:
                day, month_name, year = match.groups()
                if month_name in self.malay_month_map:
                    month = self.malay_month_map[month_name]
                    return datetime(int(year), month, int(day))
            
            # 格式: "2025-05-06" (ISO格式)
            match = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_text)
            if match:
                year, month, day = match.groups()
                return datetime(int(year), int(month), int(day))
            
            logger.warning(f"無法解析馬來文日期: {date_text}")
            return None
            
        except Exception as e:
            logger.error(f"解析馬來文日期時發生錯誤: {str(e)}, 日期文本: {date_text}")
            return None
    
    def _clean_content(self, content: str) -> str:
        """清理文章內容"""
        # 移除多餘的空白行
        lines = [line.strip() for line in content.split('\n')]
        lines = [line for line in lines if line]
        
        # 移除重複的行
        lines = list(dict.fromkeys(lines))
        
        # 重新組合內容
        content = '\n'.join(lines)
        
        # 移除連續的空格
        content = re.sub(r'\s+', ' ', content).strip()
        
        # 移除常見的廣告文字或不需要的內容
        ad_texts = [
            "ARTIKEL BERKAITAN",  # 相關文章
            "BACA JUGA",          # 也讀
            "Ikuti kami di",      # 關注我們
            "Kongsi artikel",     # 分享文章
            "Berita Harian",      # 網站名稱
            "BERITA HARIAN",      # 網站名稱
            "ADVERTISEMENT",      # 廣告
            "Advertisement",      # 廣告
            "IKLAN",              # 廣告
            "Iklan",              # 廣告
            "Log In",             # 登錄
            "Log Masuk",          # 登錄
            "Subscribe",          # 訂閱
            "Langgan"             # 訂閱
        ]
        
        for ad in ad_texts:
            content = content.replace(ad, "")
        
        return content