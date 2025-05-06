from datetime import datetime
from bs4 import BeautifulSoup
import logging
import time
import re
import requests
from typing import List, Optional, Dict, Any
from .base import BaseCrawler

logger = logging.getLogger(__name__)

class FreeMalaysiaTodayCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.source_name = "Free Malaysia Today Property"
        self.base_url = "https://www.freemalaysiatoday.com"
        self.property_url = f"{self.base_url}/category/category/leisure/property"
        self.api_url = f"{self.base_url}/api/more-vertical-posts"
        
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
            should_stop = False
            
            # 先爬取首頁的文章（前5篇特殊排版 + 後續文章）
            logger.info(f"正在爬取首頁文章")
            first_page_articles = await self.crawl_list(page=1)
            
            if first_page_articles:
                logger.info(f"從首頁找到 {len(first_page_articles)} 篇文章")
                
                # 處理首頁文章
                for article_info in first_page_articles:
                    # 檢查文章日期是否在指定範圍內
                    if start_date and end_date:
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
                        'category': article_data.get('category') or article_info.get('category', 'Property')
                    }
                    
                    all_articles.append(full_article)
                    logger.info(f"成功新增文章: {full_article['title']}")
            
            # 如果需要繼續爬取更多文章（使用API）
            if not should_stop:
                offset = len(first_page_articles)  # 從首頁文章數量開始
                max_offset = 500  # 設定最大爬取數量限制
                batch_size = 20  # 每次API請求的文章數量（根據網站實際情況調整）
                
                while offset < max_offset:
                    logger.info(f"正在使用API爬取更多文章，offset: {offset}")
                    more_articles = await self.fetch_more_articles(offset)
                    
                    if not more_articles or len(more_articles) == 0:
                        logger.info("沒有更多文章了，停止爬取")
                        break
                    
                    logger.info(f"透過API找到 {len(more_articles)} 篇文章")
                    
                    # 處理API返回的文章
                    for article_info in more_articles:
                        # 檢查文章日期是否在指定範圍內
                        if start_date and end_date:
                            article_date = article_info['published_at'].date()
                            if not (start_date <= article_date <= end_date):
                                logger.debug(f"文章日期 {article_date} 不在指定範圍內，跳過")
                                # 如果文章日期早於起始日期，可以考慮停止爬取
                                if article_date < start_date:
                                    should_stop = True
                                    break
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
                            'category': article_data.get('category') or article_info.get('category', 'Property')
                        }
                        
                        all_articles.append(full_article)
                        logger.info(f"成功新增文章: {full_article['title']}")
                    
                    if should_stop or len(more_articles) < batch_size:
                        # 如果返回的文章數量小於批次大小，說明可能沒有更多文章了
                        break
                    
                    offset += len(more_articles)
            
            logger.info(f"成功爬取 {len(all_articles)} 篇文章")
            return all_articles
            
        except Exception as e:
            logger.error(f"執行 Free Malaysia Today 爬蟲時發生錯誤: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
            
        finally:
            self.cleanup()
    
    async def crawl_list(self, page: int = 1) -> List[Dict[str, Any]]:
        """爬取文章列表頁（實現抽象方法）
        
        對於 FMT Property，我們需要特殊處理：
        1. 當 page=1 時，爬取首頁
        2. 當 page>1 時，使用API獲取更多文章
        """
        if page == 1:
            # 爬取首頁
            return await self.crawl_first_page()
        else:
            # 計算API的offset
            # 假設首頁有大約20篇文章，後續每頁20篇
            offset = (page - 1) * 20
            return await self.fetch_more_articles(offset)
    
    async def crawl_first_page(self) -> List[Dict[str, Any]]:
        """爬取首頁文章列表"""
        try:
            logger.info(f"正在訪問首頁: {self.property_url}")
            self.wait_and_get(self.property_url)
            time.sleep(3)  # 等待頁面加載
            
            # 解析頁面
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 找到文章列表容器
            main_container = soup.select_one('main.lg\\:w-2\\/3')
            
            if not main_container:
                logger.warning("找不到文章列表容器")
                return []
            
            articles = []
            
            # 處理第一篇特殊排版的文章
            try:
                first_section = main_container.select('section')[0] if main_container.select('section') else None
                
                if first_section:
                    # 提取第一篇文章信息
                    link_element = first_section.select_one('div > figure > a')
                    url = link_element.get('href', '') if link_element else ''
                    
                    # 確保URL是完整的
                    if url and not url.startswith('http'):
                        url = self.base_url + url if url.startswith('/') else self.base_url + '/' + url
                    
                    # 提取縮圖
                    img_element = first_section.select_one('div > figure > a > div > img')
                    image_url = img_element.get('src', '') if img_element else ''
                    
                    # 提取分類
                    category_element = first_section.select_one('div > div > span:nth-of-type(1)')
                    category = category_element.text.strip() if category_element else 'Property'
                    
                    # 提取發布時間
                    time_element = first_section.select_one('div > div > span:nth-of-type(2) > div > time.hidden')
                    published_at = datetime.now()
                    if time_element and time_element.get('datetime'):
                        try:
                            published_at = datetime.fromisoformat(time_element.get('datetime').replace('Z', '+00:00'))
                        except ValueError:
                            logger.warning(f"無法解析日期: {time_element.get('datetime')}")
                    
                    # 提取標題
                    title_element = first_section.select_one('div > div > a > h1')
                    title = title_element.text.strip() if title_element else ''
                    
                    if url and title:
                        articles.append({
                            'title': title,
                            'url': url,
                            'image_url': image_url,
                            'published_at': published_at,
                            'category': category
                        })
            except Exception as e:
                logger.error(f"解析第一篇文章時發生錯誤: {str(e)}")
            
            # 處理第2-5篇文章
            try:
                second_section = main_container.select('section')[1] if len(main_container.select('section')) > 1 else None
                
                if second_section:
                    article_elements = second_section.select('div > article')
                    
                    for article_element in article_elements:
                        # 提取連結
                        link_element = article_element.select_one('figure > a')
                        url = link_element.get('href', '') if link_element else ''
                        
                        # 確保URL是完整的
                        if url and not url.startswith('http'):
                            url = self.base_url + url if url.startswith('/') else self.base_url + '/' + url
                        
                        # 提取縮圖
                        img_element = article_element.select_one('figure > a > div > img')
                        image_url = img_element.get('src', '') if img_element else ''
                        
                        # 提取分類
                        category_element = article_element.select_one('a > h2 > span:nth-of-type(1)')
                        category = category_element.text.strip() if category_element else 'Property'
                        
                        # 提取發布時間
                        time_element = article_element.select_one('a > h2 > span:nth-of-type(2) > div > div > time.hidden')
                        published_at = datetime.now()
                        if time_element and time_element.get('datetime'):
                            try:
                                published_at = datetime.fromisoformat(time_element.get('datetime').replace('Z', '+00:00'))
                            except ValueError:
                                logger.warning(f"無法解析日期: {time_element.get('datetime')}")
                        
                        # 提取標題
                        title_element = article_element.select_one('a > h1')
                        title = title_element.text.strip() if title_element else ''
                        
                        if url and title:
                            articles.append({
                                'title': title,
                                'url': url,
                                'image_url': image_url,
                                'published_at': published_at,
                                'category': category
                            })
            except Exception as e:
                logger.error(f"解析第2-5篇文章時發生錯誤: {str(e)}")
            
            # 處理第6篇開始的文章
            try:
                grid_container = main_container.select_one('div > div.mt-8 > div.grid')
                
                if grid_container:
                    article_elements = grid_container.select('article')
                    
                    for article_element in article_elements:
                        # 提取連結
                        link_element = article_element.select_one('figure > a')
                        url = link_element.get('href', '') if link_element else ''
                        
                        # 確保URL是完整的
                        if url and not url.startswith('http'):
                            url = self.base_url + url if url.startswith('/') else self.base_url + '/' + url
                        
                        # 提取縮圖
                        img_element = article_element.select_one('figure > a > div > img')
                        image_url = img_element.get('src', '') if img_element else ''
                        
                        # 提取分類
                        category_element = article_element.select_one('a > h2 > span:nth-of-type(1)')
                        category = category_element.text.strip() if category_element else 'Property'
                        
                        # 提取發布時間
                        time_element = article_element.select_one('a > h2 > span:nth-of-type(2) > div > time.hidden')
                        published_at = datetime.now()
                        if time_element and time_element.get('datetime'):
                            try:
                                published_at = datetime.fromisoformat(time_element.get('datetime').replace('Z', '+00:00'))
                            except ValueError:
                                logger.warning(f"無法解析日期: {time_element.get('datetime')}")
                        
                        # 提取標題
                        title_element = article_element.select_one('a > h1')
                        title = title_element.text.strip() if title_element else ''
                        
                        if url and title:
                            articles.append({
                                'title': title,
                                'url': url,
                                'image_url': image_url,
                                'published_at': published_at,
                                'category': category
                            })
            except Exception as e:
                logger.error(f"解析第6篇開始的文章時發生錯誤: {str(e)}")
            
            return articles
            
        except Exception as e:
            logger.error(f"爬取 Free Malaysia Today 首頁文章列表時發生錯誤: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def fetch_more_articles(self, offset: int = 0) -> List[Dict[str, Any]]:
        """使用API獲取更多文章"""
        try:
            logger.info(f"使用API獲取更多文章，offset: {offset}")
            
            payload = {
                "categorySlug": "property",
                "offset": offset
            }
            
            # 使用requests庫發送POST請求
            response = requests.post(self.api_url, json=payload)
            
            if response.status_code != 200:
                logger.error(f"API請求失敗，狀態碼: {response.status_code}")
                return []
            
            # 解析API返回的JSON數據
            data = response.json()
            
            if not data or not isinstance(data, dict):
                logger.warning("API返回的數據格式不正確")
                return []
            
            # 從API響應中提取文章列表
            html_content = data.get('html', '')
            
            if not html_content:
                logger.warning("API返回的HTML內容為空")
                return []
            
            # 解析HTML內容
            soup = BeautifulSoup(html_content, 'html.parser')
            article_elements = soup.select('article')
            
            articles = []
            for article_element in article_elements:
                try:
                    # 提取連結
                    link_element = article_element.select_one('figure > a')
                    url = link_element.get('href', '') if link_element else ''
                    
                    # 確保URL是完整的
                    if url and not url.startswith('http'):
                        url = self.base_url + url if url.startswith('/') else self.base_url + '/' + url
                    
                    # 提取縮圖
                    img_element = article_element.select_one('figure > a > div > img')
                    image_url = img_element.get('src', '') if img_element else ''
                    
                    # 提取分類
                    category_element = article_element.select_one('a > h2 > span:nth-of-type(1)')
                    category = category_element.text.strip() if category_element else 'Property'
                    
                    # 提取發布時間
                    time_element = article_element.select_one('a > h2 > span:nth-of-type(2) > div > time.hidden')
                    published_at = datetime.now()
                    if time_element and time_element.get('datetime'):
                        try:
                            published_at = datetime.fromisoformat(time_element.get('datetime').replace('Z', '+00:00'))
                        except ValueError:
                            logger.warning(f"無法解析日期: {time_element.get('datetime')}")
                    
                    # 提取標題
                    title_element = article_element.select_one('a > h1')
                    title = title_element.text.strip() if title_element else ''
                    
                    if url and title:
                        articles.append({
                            'title': title,
                            'url': url,
                            'image_url': image_url,
                            'published_at': published_at,
                            'category': category
                        })
                except Exception as e:
                    logger.error(f"解析API返回的文章時發生錯誤: {str(e)}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.error(f"使用API獲取更多文章時發生錯誤: {str(e)}")
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
            self.wait_and_get(url)
            time.sleep(2)  # 等待頁面加載
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 找到文章容器
            article_container = soup.select_one('article[itemscope][itemtype="https://schema.org/NewsArticle"]')
            
            if not article_container:
                logger.warning(f"找不到文章容器")
                return None
            
            # 提取標題
            title_element = article_container.select_one('h1')
            title = title_element.text.strip() if title_element else article_info.get('title', '')
            
            # 提取發布日期
            time_element = article_container.select_one('div > main > header > p > div > div > time')
            published_at = article_info.get('published_at')
            
            if time_element and time_element.get('datetime'):
                try:
                    published_at = datetime.fromisoformat(time_element.get('datetime').replace('Z', '+00:00'))
                    logger.info(f"從文章頁面解析日期: {published_at}, 原始文本: {time_element.get('datetime')}")
                except ValueError:
                    logger.warning(f"無法從文章頁面解析日期: {time_element.get('datetime')}")
            
            # 提取作者
            author_element = article_container.select_one('div > main > header > div > div > div > div > a > span[itemprop="name"]')
            author = author_element.text.strip() if author_element else ''
            
            # 提取描述
            description_element = article_container.select_one('div > main > header > div:nth-of-type(2) > h2[itemprop="description"]')
            description = description_element.text.strip() if description_element else ''
            
            # 提取文章大圖
            image_element = article_container.select_one('div > main > section[itemprop="articleBody"] > article > figure > div[itemprop="image"] > img')
            image_url = article_info.get('image_url', '')
            
            if image_element:
                new_image_url = image_element.get('src', '')
                if new_image_url:
                    if not new_image_url.startswith('http'):
                        new_image_url = 'https:' + new_image_url if new_image_url.startswith('//') else self.base_url + new_image_url
                    image_url = new_image_url
            
            # 提取文章內容
            content_element = article_container.select_one('div > main > section[itemprop="articleBody"] > article')
            content = ''
            
            if content_element:
                # 移除不需要的元素
                for unwanted in content_element.select('script, style, iframe'):
                    unwanted.decompose()
                
                # 提取所有段落
                paragraphs = []
                for p in content_element.select('p'):
                    if p.text.strip():
                        paragraphs.append(p.text.strip())
                
                if paragraphs:
                    content = '\n\n'.join(paragraphs)
                    content = self._clean_content(content)
                    logger.info(f"成功提取文章內容，長度: {len(content)} 字符")
                else:
                    # 如果找不到段落，直接使用內容元素的文本
                    content = content_element.text.strip()
                    content = self._clean_content(content)
                    logger.info(f"使用備用方法提取內容，長度: {len(content)} 字符")
            
            if not content:
                logger.warning("無法提取文章內容")
                return None
            
            # 如果沒有描述，使用內容的前200字
            if not description:
                description = content[:200] if content else ''
            
            return {
                'title': title,
                'content': content,
                'description': description,
                'published_at': published_at,
                'image_url': image_url,
                'author': author,
                'category': article_info.get('category', 'Property')
            }
            
        except Exception as e:
            logger.error(f"爬取 Free Malaysia Today 文章內容時發生錯誤: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
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
            "Subscribe to our Telegram channel",
            "Click to subscribe",
            "Follow us on",
            "For the latest property news",
            "Click here for more property stories",
            "SUBSCRIBE TO OUR NEWSLETTER"
        ]
        
        for ad in ad_texts:
            content = content.replace(ad, "")
        
        return content