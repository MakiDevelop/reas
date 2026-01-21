from datetime import datetime
from bs4 import BeautifulSoup
import logging
import time
import re
import json
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
        self.needs_javascript = True

    async def crawl(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """執行爬蟲主程序 - 使用 Next.js __NEXT_DATA__ 解析"""
        try:
            # 設定 Chrome Driver（用於爬取文章內容）
            self.setup_driver()
            logger.info("Chrome Driver 設定完成")

            # 確保 start_date 和 end_date 是 datetime.date 物件
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

            all_articles = []

            # 從 __NEXT_DATA__ 獲取文章列表
            logger.info(f"正在從 __NEXT_DATA__ 獲取文章列表")
            article_list = await self.crawl_list(page=1)

            if not article_list:
                logger.warning("無法獲取文章列表")
                return []

            logger.info(f"從 __NEXT_DATA__ 找到 {len(article_list)} 篇文章")

            # 處理每篇文章
            for article_info in article_list:
                # 檢查文章日期是否在指定範圍內
                if start_date and end_date:
                    article_date = article_info['published_at'].date()
                    if not (start_date <= article_date <= end_date):
                        logger.debug(f"文章日期 {article_date} 不在指定範圍內，跳過")
                        # 如果文章日期早於起始日期，可以停止爬取
                        if article_date < start_date:
                            logger.info(f"文章日期 {article_date} 早於起始日期 {start_date}，停止爬取")
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
        """從 __NEXT_DATA__ 爬取文章列表"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }

            logger.info(f"正在訪問: {self.property_url}")
            response = requests.get(self.property_url, headers=headers, timeout=15)

            if response.status_code != 200:
                logger.error(f"請求失敗，狀態碼: {response.status_code}")
                return []

            # 解析 HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # 找到 __NEXT_DATA__ script 標籤
            script = soup.find('script', {'id': '__NEXT_DATA__'})
            if not script:
                logger.warning("找不到 __NEXT_DATA__")
                return []

            # 解析 JSON
            data = json.loads(script.string)
            props = data.get('props', {}).get('pageProps', {})

            # 從 posts.edges 獲取文章
            posts = props.get('posts', {})
            edges = posts.get('edges', [])

            logger.info(f"從 __NEXT_DATA__ 找到 {len(edges)} 篇文章")

            articles = []
            for edge in edges:
                try:
                    node = edge.get('node', {})

                    title = node.get('title', '')
                    slug = node.get('slug', '')
                    uri = node.get('uri', '')
                    date_str = node.get('date', '')

                    # 構建完整 URL
                    if uri:
                        url = self.base_url + uri
                    else:
                        url = ''

                    # 解析日期
                    published_at = datetime.now()
                    if date_str:
                        try:
                            # 格式: 2025-12-28T11:52:09
                            published_at = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        except ValueError:
                            logger.warning(f"無法解析日期: {date_str}")

                    # 提取圖片
                    featured_image = node.get('featuredImage', {})
                    image_node = featured_image.get('node', {}) if featured_image else {}
                    image_url = image_node.get('sourceUrl', '')

                    # 提取分類
                    categories = node.get('categories', {})
                    category_edges = categories.get('edges', []) if categories else []
                    category = 'Property'
                    if category_edges:
                        first_cat = category_edges[0].get('node', {})
                        category = first_cat.get('name', 'Property')

                    if url and title:
                        articles.append({
                            'title': title,
                            'url': url,
                            'image_url': image_url,
                            'published_at': published_at,
                            'category': category
                        })
                        logger.debug(f"添加文章: {title} ({published_at.date()})")

                except Exception as e:
                    logger.error(f"解析文章時發生錯誤: {str(e)}")
                    continue

            return articles

        except Exception as e:
            logger.error(f"爬取 Free Malaysia Today 文章列表時發生錯誤: {str(e)}")
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

            # 嘗試從 __NEXT_DATA__ 獲取文章內容
            script = soup.find('script', {'id': '__NEXT_DATA__'})
            if script:
                try:
                    data = json.loads(script.string)
                    post = data.get('props', {}).get('pageProps', {}).get('post', {})

                    if post:
                        title = post.get('title', article_info.get('title', ''))

                        # 解析日期
                        date_str = post.get('date', '')
                        published_at = article_info.get('published_at')
                        if date_str:
                            try:
                                published_at = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            except ValueError:
                                pass

                        # 提取內容
                        content_html = post.get('content', '')
                        if content_html:
                            content_soup = BeautifulSoup(content_html, 'html.parser')
                            # 移除不需要的元素
                            for unwanted in content_soup.select('script, style, iframe'):
                                unwanted.decompose()
                            content = content_soup.get_text(separator='\n', strip=True)
                            content = self._clean_content(content)
                        else:
                            content = ''

                        # 提取摘要
                        excerpt = post.get('excerpt', '')
                        if excerpt:
                            excerpt_soup = BeautifulSoup(excerpt, 'html.parser')
                            description = excerpt_soup.get_text(strip=True)
                        else:
                            description = content[:200] if content else ''

                        # 提取圖片
                        featured_image = post.get('featuredImage', {})
                        image_node = featured_image.get('node', {}) if featured_image else {}
                        image_url = image_node.get('sourceUrl', '') or article_info.get('image_url', '')

                        if content:
                            logger.info(f"成功從 __NEXT_DATA__ 提取文章內容，長度: {len(content)} 字符")
                            return {
                                'title': title,
                                'content': content,
                                'description': description,
                                'published_at': published_at,
                                'image_url': image_url,
                                'category': article_info.get('category', 'Property')
                            }
                except Exception as e:
                    logger.warning(f"從 __NEXT_DATA__ 解析文章失敗: {str(e)}")

            # 備用方法：從 HTML 解析
            article_container = soup.select_one('article[itemscope]')

            if not article_container:
                logger.warning(f"找不到文章容器")
                return None

            # 提取標題
            title_element = article_container.select_one('h1')
            title = title_element.text.strip() if title_element else article_info.get('title', '')

            # 提取發布日期
            time_element = article_container.select_one('time[datetime]')
            published_at = article_info.get('published_at')

            if time_element and time_element.get('datetime'):
                try:
                    published_at = datetime.fromisoformat(time_element.get('datetime').replace('Z', '+00:00'))
                except ValueError:
                    pass

            # 提取文章內容
            content_element = article_container.select_one('section[itemprop="articleBody"]')
            content = ''

            if content_element:
                # 移除不需要的元素
                for unwanted in content_element.select('script, style, iframe, figure'):
                    unwanted.decompose()

                # 提取所有段落
                paragraphs = []
                for p in content_element.select('p'):
                    if p.text.strip():
                        paragraphs.append(p.text.strip())

                if paragraphs:
                    content = '\n\n'.join(paragraphs)
                    content = self._clean_content(content)
                else:
                    content = content_element.text.strip()
                    content = self._clean_content(content)

                logger.info(f"使用備用方法提取內容，長度: {len(content)} 字符")

            if not content:
                logger.warning("無法提取文章內容")
                return None

            description = content[:200] if content else ''

            return {
                'title': title,
                'content': content,
                'description': description,
                'published_at': published_at,
                'image_url': article_info.get('image_url', ''),
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
