from datetime import datetime
from bs4 import BeautifulSoup
import logging
import time
import re
from typing import List, Optional, Dict, Any
from .base import BaseCrawler

logger = logging.getLogger(__name__)

class House852Crawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.source_name = "852HOUSE"
        self.base_url = "https://852.house"
        self.news_url = f"{self.base_url}/zh/newses"
        
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
            max_pages = 10  # 最多爬取10頁
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
                    article_data = await self.crawl_article(article_info)
                    
                    if not article_data:
                        continue
                    
                    # 檢查文章日期是否在指定範圍內
                    if start_date and end_date:
                        article_date = article_data['published_at'].date()
                        if not (start_date <= article_date <= end_date):
                            logger.debug(f"文章日期 {article_date} 不在指定範圍內，跳過")
                            # 如果文章日期早於起始日期，可以考慮停止爬取
                            if article_date < start_date:
                                should_stop = True
                            continue
                    
                    # 合併文章信息
                    full_article = {
                        'title': article_data['title'],
                        'url': article_info['url'],
                        'source': self.source_name,
                        'content': article_data['content'],
                        'description': article_data['description'],
                        'published_at': article_data['published_at'],
                        'image_url': article_data.get('image_url') or article_info.get('image_url', ''),
                        'category': article_data.get('category', '房產新聞')
                    }
                    
                    all_articles.append(full_article)
                    logger.info(f"成功新增文章: {full_article['title']}")
                
                # 進入下一頁
                page += 1
                
            logger.info(f"成功爬取 {len(all_articles)} 篇文章")
            return all_articles
            
        except Exception as e:
            logger.error(f"執行 852HOUSE 爬蟲時發生錯誤: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
            
        finally:
            self.cleanup()
    
    async def crawl_list(self, page: int = 1) -> List[Dict[str, Any]]:
        """爬取文章列表頁"""
        try:
            # 構建分頁URL
            if page == 1:
                url = self.news_url
            else:
                url = f"{self.news_url}?page={page}"
            
            logger.info(f"正在訪問列表頁: {url}")
            self.wait_and_get(url)
            time.sleep(3)  # 等待頁面加載
            
            # 解析頁面
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 找到文章列表容器
            container = soup.select_one('div.tab-content.pt-2.px-2')
            
            if not container:
                logger.warning(f"找不到文章列表容器")
                return []
            
            # 找到所有文章項目
            article_items = container.select('div.link-element.list-group')
            
            logger.info(f"找到 {len(article_items)} 篇文章")
            
            articles = []
            for item in article_items:
                try:
                    # 提取標題和連結
                    title_element = item.select_one('div > div:nth-of-type(1) > div:nth-of-type(1) > h5 > a')
                    
                    if not title_element:
                        continue
                        
                    title = title_element.text.strip()
                    url = title_element.get('href', '')
                    
                    # 確保URL是完整的
                    if url and not url.startswith('http'):
                        url = self.base_url + url
                    
                    # 提取預覽文本
                    preview_element = item.select_one('div > p > span')
                    preview = preview_element.text.strip() if preview_element else ''
                    
                    # 提取發布日期
                    date_element = item.select_one('div > div:nth-of-type(1) > div:nth-of-type(2) > small')
                    published_at = None
                    if date_element:
                        date_text = date_element.text.strip()
                        try:
                            # 日期格式範例：2025-05-03
                            published_at = datetime.strptime(date_text, '%Y-%m-%d')
                            logger.info(f"成功解析日期: {published_at}, 原始文本: {date_text}")
                        except ValueError as e:
                            logger.warning(f"無法解析日期: {date_text}, 錯誤: {e}")
                            published_at = datetime.now()
                    else:
                        published_at = datetime.now()
                    
                    # 提取作者
                    author_element = item.select_one('div > div:nth-of-type(2) > i')
                    author = author_element.text.strip() if author_element else ''
                    
                    articles.append({
                        'title': title,
                        'url': url,
                        'preview': preview,
                        'published_at': published_at,
                        'author': author
                    })
                    
                except Exception as e:
                    logger.error(f"解析文章項目時發生錯誤: {str(e)}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.error(f"爬取 852HOUSE 文章列表時發生錯誤: {str(e)}")
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
            
            # 提取標題
            title_element = soup.select_one('main > div.detail-content-wrapper > div.container > div > div > h1')
            title = title_element.text.strip() if title_element else article_info.get('title', '')
            
            # 提取發布日期
            date_element = soup.select_one('main > div.detail-content-wrapper > div.container > div > div:nth-of-type(2) > small > span:nth-of-type(1)')
            published_at = article_info.get('published_at')
            
            if date_element:
                date_text = date_element.text.strip()
                try:
                    # 日期格式範例：" 2025-05-03 "
                    published_at = datetime.strptime(date_text.strip(), '%Y-%m-%d')
                    logger.info(f"從文章頁面解析日期: {published_at}, 原始文本: {date_text}")
                except ValueError:
                    logger.warning(f"無法從文章頁面解析日期: {date_text}")
                    # 使用列表頁提供的日期作為備用
            
            # 提取作者
            author_element = soup.select_one('main > div.detail-content-wrapper > div.container > div > div:nth-of-type(2) > small > span:nth-of-type(2)')
            author = author_element.text.strip() if author_element else article_info.get('author', '')
            
            # 提取文章內容
            content_element = soup.select_one('main > div.detail-content-wrapper > div.container > div:nth-of-type(2)')
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
            
            # 提取圖片（如果有）
            image_element = soup.select_one('main > div.detail-content-wrapper img')
            image_url = ''
            if image_element:
                image_url = image_element.get('src', '')
                if image_url and not image_url.startswith('http'):
                    image_url = self.base_url + image_url if image_url.startswith('/') else self.base_url + '/' + image_url
            
            # 提取描述（使用文章預覽或內容的前200字）
            description = article_info.get('preview', '') or content[:200]
            
            return {
                'title': title,
                'content': content,
                'description': description,
                'published_at': published_at,
                'image_url': image_url,
                'author': author,
                'category': '房產新聞'
            }
            
        except Exception as e:
            logger.error(f"爬取 852HOUSE 文章內容時發生錯誤: {str(e)}")
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
        
        # 移除常見的廣告文字或不需要的內容（根據實際情況調整）
        ad_texts = [
            "訂閱我們的通訊",
            "關注我們",
            "最新房產新聞"
        ]
        
        for ad in ad_texts:
            content = content.replace(ad, "")
        
        return content