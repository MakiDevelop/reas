from datetime import datetime
from bs4 import BeautifulSoup
import logging
from .base import BaseCrawler
import time

logger = logging.getLogger(__name__)

class EttodayCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.source_name = "ETtoday房產雲"
        self.base_url = "https://house.ettoday.net/"

    async def get_page_source(self, url):
        """使用 Selenium 獲取頁面內容"""
        try:
            logger.debug(f"正在訪問頁面: {url}")
            self.driver.get(url)
            time.sleep(2)  # 等待頁面加載
            return self.driver.page_source
        except Exception as e:
            logger.error(f"獲取頁面內容時發生錯誤: {str(e)}")
            return None

    async def crawl_list(self, page=1):
        """爬取文章列表"""
        try:
            html = await self.get_page_source(self.base_url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            articles = []

            # 1. 爬取房產焦點區塊
            focus_articles = soup.select('.block_1 .gallery_3 .piece')
            logger.debug(f"找到 {len(focus_articles)} 篇焦點文章")
            
            for piece in focus_articles:
                link = piece.find('a')
                if not link:
                    continue
                    
                title = link.get('title', '')
                if '【廣編】' in title:
                    continue
                    
                url = link.get('href', '')
                if not url.startswith('http'):
                    url = self.base_url.rstrip('/') + url

                # 找到圖片
                img = piece.find('img')
                image_url = img.get('src', '') if img else ''
                if image_url and not image_url.startswith('http'):
                    image_url = 'https:' + image_url

                articles.append({
                    'title': title,
                    'url': url,
                    'image_url': image_url,
                    'category': '房產焦點'
                })

            # 2. 爬取房產最新區塊
            latest_blocks = soup.select('.part_txt_1')
            logger.debug(f"找到 {len(latest_blocks)} 個最新文章區塊")
            
            for block in latest_blocks:
                # 找出區塊標題（分類）
                category = '房產最新'
                block_title = block.find_previous('h2', class_='block_title_3')
                if block_title:
                    category = block_title.text.strip()

                # 處理區塊中的所有文章
                for article in block.select('h3 a'):
                    if '【廣編】' in article.text:
                        continue
                        
                    url = article.get('href', '')
                    if not url.startswith('http'):
                        url = 'https://house.ettoday.net' + url

                    # 找到對應的圖片
                    article_parent = article.find_parent('div', class_='col')
                    if article_parent:
                        pic_div = article_parent.find('div', class_='part_pic')
                        if pic_div:
                            img = pic_div.find('img')
                            image_url = img.get('src', '') if img else ''
                            if image_url and not image_url.startswith('http'):
                                image_url = 'https:' + image_url
                        else:
                            image_url = ''
                    else:
                        image_url = ''

                    articles.append({
                        'title': article.text.strip(),
                        'url': url,
                        'image_url': image_url,
                        'category': category
                    })

            # 移除重複的文章
            unique_articles = []
            seen_urls = set()
            for article in articles:
                if article['url'] not in seen_urls:
                    seen_urls.add(article['url'])
                    unique_articles.append(article)

            logger.debug(f"總共找到 {len(unique_articles)} 篇不重複文章")
            for article in unique_articles:
                logger.debug(f"文章: {article['title']}")
                logger.debug(f"分類: {article['category']}")
                logger.debug(f"圖片: {article['image_url']}")
                logger.debug("---")
            
            return unique_articles

        except Exception as e:
            logger.error(f"爬取 ETtoday 文章列表時發生錯誤: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    async def crawl_article(self, url):
        """爬取文章內容"""
        try:
            html = await self.get_page_source(url)
            if not html:
                return None
                
            soup = BeautifulSoup(html, 'html.parser')
            
            # 嘗試不同的內文區塊�擇器
            story = soup.select_one('.story, .story-content, article')
            if not story:
                logger.warning(f"找不到文章內容區塊: {url}")
                return None

            # 設定預設圖片
            DEFAULT_IMAGE = "https://cdn2.ettoday.net/style/ettoday2017/images/logo_ettoday.png"
            
            # 取得圖片 (嘗試多種可能的結構)
            image_url = None
            img_selectors = [
                'p.no_margin img',  # 一般新聞圖片
                'figure img',       # 某些版型的圖片
                '.story img',       # 其他版型的圖片
                '.pic img',         # 舊版型的圖片
                'article img',      # 新版型的圖片
                'img[alt*="圖"]'    # 含有「�」字的圖片
            ]
            
            for selector in img_selectors:
                img = soup.select_one(selector)
                if img:
                    image_url = img.get('src', '')
                    if image_url:
                        if not image_url.startswith('http'):
                            image_url = 'https:' + image_url.lstrip('//')
                        logger.debug(f"從 {selector} 找到圖片: {image_url}")
                        break
            
            # 如果都找不到圖片，使用預設圖片
            if not image_url:
                logger.warning(f"找不到圖片，使用預設圖片: {url}")
                image_url = DEFAULT_IMAGE

            # 取得內文 (移除廣告)
            for ad in story.select('.ad_in_news, .ad_readmore, script, iframe'):
                ad.decompose()
            content = story.text.strip()
            
            # 取得描述
            meta_desc = soup.find('meta', {'name': 'description'})
            description = meta_desc.get('content', '') if meta_desc else ""
            
            # 取得發布時間 (嘗試多種可能的格式)
            time_element = soup.select_one('time.date, .date, .news-time')
            if time_element:
                try:
                    time_text = time_element.text.strip()
                    logger.debug(f"解析時間: {time_text}")
                    # 處理多種可能的時間格式
                    try:
                        published_at = datetime.strptime(time_text, '%Y-%m-%d %H:%M')
                    except ValueError:
                        try:
                            published_at = datetime.strptime(time_text, '%Y/%m/%d %H:%M')
                        except ValueError:
                            published_at = datetime.now()
                except Exception as e:
                    logger.error(f"解析時間發生錯誤: {str(e)}")
                    published_at = datetime.now()
            else:
                logger.warning(f"找不到發布時間: {url}")
                published_at = datetime.now()

            # 取得分類 (嘗試多種可能的結構)
            category = "房產新聞"  # �設分類
            category_selectors = [
                '.menu_bread_crumb span',  # 一般麵包屑
                '.breadcrumb span',        # 新版麵包屑
                '.nav a'                   # 導航列分類
            ]
            
            for selector in category_selectors:
                elements = soup.select(selector)
                if elements and len(elements) > 2:
                    category = elements[-1].text.strip()
                    break

            logger.debug(f"文章分類: {category}")

            return {
                'content': content,
                'description': description,
                'published_at': published_at,
                'image_url': image_url,
                'category': category
            }

        except Exception as e:
            logger.error(f"爬取 ETtoday 文章內容時發生錯誤: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    async def crawl(self, start_date=None, end_date=None):
        """執行爬蟲"""
        try:
            # 設定 Chrome Driver
            self.setup_driver()
            logger.debug("Chrome Driver 設定完成")
            
            # 確保 start_date 和 end_date 是 datetime.date 物件
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
                    # 檢查文章日期是否在指定範圍內
                    if start_date and end_date:
                        article_date = article_content['published_at'].date()
                        logger.debug(f"文章日期: {article_date}, 範圍: {start_date} ~ {end_date}")
                        if not (start_date <= article_date <= end_date):
                            logger.debug(f"文章日期 {article_date} 不在指定範圍內，跳過")
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
                    logger.debug(f"成功新增文章: {article['title']}")
                    logger.debug(f"圖片: {article_content['image_url']}")
                    logger.debug(f"分類: {article_content['category']}")
                    
            logger.debug(f"成功爬取 {len(articles)} 篇文章")
            return articles
            
        except Exception as e:
            logger.error(f"執行 ETtoday 爬蟲時發生錯誤: {str(e)}")
            return []
            
        finally:
            if hasattr(self, 'driver'):
                self.driver.quit() 