from datetime import datetime
from bs4 import BeautifulSoup
import logging
import time
import re
from typing import List, Optional, Dict, Any
from .base import BaseCrawler

logger = logging.getLogger(__name__)

class EdgePropCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.source_name = "EdgeProp Malaysia"
        self.base_url = "https://www.edgeprop.my"
        self.news_url = f"{self.base_url}/news"
        
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
                        'category': article_data.get('category', 'Property News')
                    }
                    
                    all_articles.append(full_article)
                    logger.info(f"成功新增文章: {full_article['title']}")
                
                # 進入下一頁
                page += 1
                
            logger.info(f"成功爬取 {len(all_articles)} 篇文章")
            return all_articles
            
        except Exception as e:
            logger.error(f"執行 EdgeProp 爬蟲時發生錯誤: {str(e)}")
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
                # 第一頁使用基本新聞頁
                url = f"{self.news_url}"
            else:
                # 第二頁開始使用搜索頁面並帶上page參數
                url = f"{self.base_url}/news/search?field_category_value=editorpick&combine=&page={page-1}"
            
            logger.info(f"正在訪問列表頁: {url}")
            self.wait_and_get(url)
            time.sleep(3)  # 等待頁面加載
            
            # 解析頁面
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 找到文章列表容器 - 根據頁面類型選擇不同的選擇器
            container = None
            if page == 1:
                container = soup.select_one('div.secondary')
            else:
                # 分頁頁面使用不同的容器選擇器
                container = soup.select_one('div.wrap.news-page div.main-content')
                
            if not container:
                logger.warning(f"找不到文章列表容器")
                return []
            
            # 找到所有文章項目 - 兩種頁面都使用相同的文章項目選擇器
            article_items = container.select('article.post-entry')
            
            logger.info(f"找到 {len(article_items)} 篇文章")
            
            articles = []
            for item in article_items:
                try:
                    # 兩種頁面都使用相同的標題選擇器
                    title_element = item.select_one('div.box-details h5.title a')
                    
                    if not title_element:
                        continue
                        
                    title = title_element.text.strip()
                    url = title_element.get('href', '')
                    
                    # 確保URL是完整的
                    if url:
                        if url.startswith('http'):
                            pass  # URL 已經是完整的
                        elif url.startswith('../'):
                            # 處理 "../content/..." 格式
                            url = url.replace('../', '/')
                            url = self.base_url + url
                        elif not url.startswith('/'):
                            # 如果不是以 / 開頭，加上 /
                            url = '/' + url
                            url = self.base_url + url
                        else:
                            # 以 / 開頭的情況
                            url = self.base_url + url
                    
                    # 提取縮圖 - 兩種頁面都使用相同的圖片選擇器
                    image_element = item.select_one('div.post-thumb img')
                    
                    image_url = ''
                    if image_element:
                        image_url = image_element.get('src', '')
                        if image_url and not image_url.startswith('http'):
                            image_url = 'https:' + image_url
                    
                    # 提取分類（如果有）
                    category_element = item.select_one('div.box-details span.category')
                    
                    category = category_element.text.strip() if category_element else 'Property News'
                    
                    articles.append({
                        'title': title,
                        'url': url,
                        'image_url': image_url,
                        'category': category
                    })
                    
                except Exception as e:
                    logger.error(f"解析文章項目時發生錯誤: {str(e)}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.error(f"爬取 EdgeProp 文章列表時發生錯誤: {str(e)}")
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
            title_element = soup.select_one('div#content-top h1')
            title = title_element.text.strip() if title_element else article_info.get('title', '')
            
            # 提取發布日期
            date_element = soup.select_one('div.entry-meta span.em-date')
            published_at = None
            if date_element:
                date_text = date_element.text.strip()
                logger.info(f"原始日期文本: {date_text}")
                
                # 如果日期包含 "|" 或 "Updated"，只取前半部分
                if "|" in date_text:
                    date_text = date_text.split("|")[0].strip()
                
                # 移除可能的 "Updated X days ago" 部分
                if "Updated" in date_text:
                    date_text = date_text.split("Updated")[0].strip()
                
                logger.info(f"處理後的日期文本: {date_text}")
                
                # 嘗試多種日期格式
                date_formats = [
                    '%d %b %Y',     # 01 Jan 2025
                    '%B %d, %Y',    # January 01, 2025
                    '%b %d, %Y',    # Jan 01, 2025
                    '%Y-%m-%d',     # 2025-01-01
                    '%d/%m/%Y',     # 01/01/2025
                    '%m/%d/%Y'      # 01/01/2025
                ]
                
                for date_format in date_formats:
                    try:
                        published_at = datetime.strptime(date_text, date_format)
                        logger.info(f"成功解析日期: {published_at}, 使用格式: {date_format}")
                        break
                    except ValueError:
                        continue
                
                if not published_at:
                    logger.warning(f"無法解析日期: {date_text}")
                    published_at = datetime.now()
            else:
                logger.warning(f"找不到日期元素")
                published_at = datetime.now()
            
            # 提取文章大圖
            image_element = soup.select_one('div.main-content div.news-body figure.caption.first img')
            image_url = ''
            if image_element:
                image_url = image_element.get('src', '')
                if image_url and not image_url.startswith('http'):
                    image_url = 'https:' + image_url
            
            # 提取文章內容
            content = ''
            # 使用更精確的選擇器
            content_element = soup.select_one('div.main-content div#article0.news-article.news-details div.news-body.content')

            # 如果找不到主要選擇器，嘗試備用選擇器
            if not content_element:
                logger.info("找不到主要內容選擇器，嘗試備用選擇器")
                content_selectors = [
                    'div.main-content div.news-body',
                    'div.main-content div.news-article div.news-body',
                    'div.post-content',
                    'div.entry-content',
                    'article.post-entry div.post-content',
                    'div.article-content'
                ]

                for selector in content_selectors:
                    content_element = soup.select_one(selector)
                    if content_element:
                        logger.info(f"使用備用選擇器找到內容: {selector}")
                        break

            if content_element:
                # 移除不需要的元素
                for unwanted in content_element.select('script, style, .related-articles, .social-share, .social-icons'):
                    unwanted.decompose()
                
                # 提取文本內容
                content = content_element.text.strip()
                # 清理內容
                content = self._clean_content(content)
                logger.info(f"成功提取文章內容，長度: {len(content)} 字符")
            else:
                logger.warning("無法找到文章內容元素")
                # 嘗試獲取所有段落作為備用方法
                paragraphs = []
                for p in soup.select('div.main-content p'):
                    if p.text.strip() and not p.select_one('.social-share, .social-icons'):
                        paragraphs.append(p.text.strip())
                
                if paragraphs:
                    content = '\n\n'.join(paragraphs)
                    content = self._clean_content(content)
                    logger.info(f"使用備用方法提取段落，共 {len(paragraphs)} 段，長度: {len(content)} 字符")
                # 如果仍然沒有內容，嘗試更通用的方法
                if not content:
                    logger.info("嘗試使用更通用的方法提取內容")
                    # 嘗試獲取所有可能的內容區域
                    all_text_blocks = []
                    
                    # 1. 嘗試獲取所有段落
                    for p in soup.select('p'):
                        if len(p.text.strip()) > 50:  # 只取較長的段落，避免菜單、頁腳等
                            all_text_blocks.append(p.text.strip())
                    
                    # 2. 嘗試獲取所有文章相關的 div
                    for div in soup.select('div.article, div.content, div.post'):
                        if len(div.text.strip()) > 200:  # 只取較長的內容
                            all_text_blocks.append(div.text.strip())
                    
                    if all_text_blocks:
                        content = '\n\n'.join(all_text_blocks)
                        content = self._clean_content(content)
                        logger.info(f"使用通用方法提取內容，長度: {len(content)} 字符")
            
            # 提取描述（如果有meta描述，否則使用內容的前200字）
            meta_desc = soup.find('meta', {'name': 'description'})
            description = meta_desc.get('content', '') if meta_desc else content[:200]
            
            # 提取分類
            category = article_info.get('category', 'Property News')
            category_element = soup.select_one('div.entry-meta span.em-cat')
            if category_element:
                category = category_element.text.strip()
            
            return {
                'title': title,
                'content': content,
                'description': description,
                'published_at': published_at,
                'image_url': image_url,
                'category': category
            }
            
        except Exception as e:
            logger.error(f"爬取 EdgeProp 文章內容時發生錯誤: {str(e)}")
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
            "Subscribe to our Telegram channel",
            "Click to subscribe",
            "Follow us on",
            "For the latest property news"
        ]
        
        for ad in ad_texts:
            content = content.replace(ad, "")
        
        return content