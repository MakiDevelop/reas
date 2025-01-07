import asyncio
import sys
from app.services.crawler.ltn_crawler import LTNCrawler
from app.services.crawler.udn_crawler import UDNCrawler
from app.services.crawler.nextapple_crawler import NextAppleCrawler
from app.services.crawler.base import BaseCrawler
from app.core.database import SessionLocal
from app.models.article import Article
import pytest
from datetime import datetime, timedelta
import argparse
import logging
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# 設定日誌格式
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s [%(levelname)s] %(message)s',
	datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

# 資料庫連線設定
DATABASE_URL = "postgresql://user:password@db:5432/newsdb"

def get_crawler(crawler_name: str):
	"""根據名稱取得對應的爬蟲實例"""
	crawlers = {
		'ltn': LTNCrawler(),
		'udn': UDNCrawler(),
		'nextapple': NextAppleCrawler()
	}
	return crawlers.get(crawler_name)

@pytest.mark.asyncio
async def test_crawler(crawler_type="ltn", start_date=None, end_date=None):
	"""測試爬蟲"""
	try:
		# 根據參數選擇爬蟲
		crawler = get_crawler(crawler_type.lower())
		if not crawler:
			raise ValueError(f"未知的爬蟲類型: {crawler_type}")

		logger.info(f"開始爬取 {crawler_type} 文章 (日期範圍: {start_date} ~ {end_date})...")
		
		# 初始化 driver (如果爬蟲需要的話)
		if hasattr(crawler, 'setup_driver'):
			crawler.setup_driver()
		
		try:
			# 根據不同爬蟲使用對應的方法
			if crawler_type.lower() == "ltn":
				articles = await crawler.run(max_pages=1, start_date=start_date, end_date=end_date)
			elif crawler_type.lower() == "udn":
				articles = await crawler.crawl(start_date=start_date, end_date=end_date)
			elif crawler_type.lower() == "nextapple":
				articles = crawler.crawl(start_date=start_date, end_date=end_date)
			
			logger.info(f"爬取到 {len(articles)} 篇文章")
			
			# 存入資料庫
			saved_count = 0
			updated_count = 0
			db = SessionLocal()
			try:
				for article in articles:
					# 檢查是否需要轉換成 Article 物件
					if isinstance(article, dict):
						article_obj = Article(
							url=article.get('url'),
							title=article.get('title'),
							content=article.get('content'),
							published_at=article.get('published_at'),
							source=crawler_type.lower(),
							image_url=article.get('image_url'),
							description=article.get('description')
						)
					else:
						article_obj = article
					
					# 檢查文章是否已存在
					existing = db.query(Article).filter(Article.url == article_obj.url).first()
					if existing:
						logger.info(f"更新文章: {article_obj.title}")
						for key, value in article_obj.__dict__.items():
							if key != '_sa_instance_state':
								setattr(existing, key, value)
						updated_count += 1
					else:
						logger.info(f"新增文章: {article_obj.title}")
						db.add(article_obj)
						saved_count += 1
					db.commit()
				
				logger.info(f"完成！新增: {saved_count} 篇，更新: {updated_count} 篇")
				return len(articles)
				
			except Exception as e:
				logger.error(f"資料庫操作失敗: {str(e)}")
				db.rollback()
				raise
			finally:
				db.close()
				
		finally:
			# 如果爬蟲有 cleanup 方法，就呼叫它
			if hasattr(crawler, 'cleanup'):
				crawler.cleanup()
				
	except Exception as e:
		logger.error(f"爬蟲執行失敗: {str(e)}")
		raise

def test_udn_crawler():
	"""測試 UDN 爬蟲"""
	logging.info("開始測試 UDN 爬蟲...")
	
	# 建立資料庫連線
	db = SessionLocal()
	
	try:
		crawler = UDNCrawler()
		logging.info("爬蟲實例化完成，開始爬取文章...")
		
		articles = crawler.crawl()
		logging.info(f"爬取完成，共取得 {len(articles)} 篇文章")
		
		if not articles:
			logging.warning("沒有取得任何文章！")
			return
			
		# 儲存到資料庫
		new_count = 0
		update_count = 0
		for article in articles:
			# 檢查文章是否已存在
			existing = db.query(Article).filter(Article.url == article.url).first()
			if existing:
				# 更新現有文章
				for key, value in article.__dict__.items():
					if not key.startswith('_'):
						setattr(existing, key, value)
				update_count += 1
			else:
				# 新增文章
				db.add(article)
				new_count += 1
		
		db.commit()
		logging.info(f"資料儲存完成！新增 {new_count} 篇，更新 {update_count} 篇")
		
	except Exception as e:
		logging.error(f"測試過程發生錯誤: {str(e)}")
		db.rollback()
		raise
	finally:
		db.close()
		
	logging.info("UDN 爬蟲測試完成！")

def test_nextapple_crawler():
	"""測試蘋果地產爬蟲"""
	logging.info("開始測試 NextApple 爬蟲...")
	
	# 建立資料庫連線
	db = SessionLocal()
	
	try:
		# 實例化爬蟲
		crawler = NextAppleCrawler()
		logging.info("爬蟲實例化完成，開始爬取文章...")
		
		# 爬取文章
		articles = crawler.crawl()
		logging.info(f"爬取完成，共取得 {len(articles)} 篇文章")
		
		# 儲存到資料庫
		new_count = 0
		update_count = 0
		for article in articles:
			# 檢查文章是否已存在
			existing = db.query(Article).filter(Article.url == article.url).first()
			if existing:
				# 更新現有文章
				for key, value in article.__dict__.items():
					if not key.startswith('_'):
						setattr(existing, key, value)
				update_count += 1
			else:
				# 新增文章
				db.add(article)
				new_count += 1
				
		db.commit()
		logging.info(f"資料儲存完成！新增 {new_count} 篇，更新 {update_count} 篇")
		
	except Exception as e:
		logging.error(f"測試過程發生錯誤: {str(e)}")
		db.rollback()
		raise
	finally:
		db.close()
		
	logging.info("NextApple 爬蟲測試完成！")

async def crawl_historical_data(start_date=None, end_date=None):
	"""回補指定日期範圍的文章"""
	if not start_date:
		start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
	if not end_date:
		end_date = datetime.now().strftime('%Y-%m-%d')
		
	logging.info(f"開始回補歷史文章 ({start_date} ~ {end_date})...")
	
	try:
		# 依序執行三個爬蟲
		for crawler_name in ['ltn', 'udn', 'nextapple']:
			logging.info(f"開始執行 {crawler_name.upper()} 爬蟲...")
			count = await test_crawler(crawler_name, start_date, end_date)
			logging.info(f"{crawler_name.upper()} 爬蟲完成，共取得 {count} 篇文章")
			
		logging.info("所有爬蟲執行完成")
				
	except Exception as e:
		logging.error(f"回補程序執行失敗: {str(e)}")
		raise

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('crawler', choices=['ltn', 'udn', 'nextapple'], 
					   help='指定要測試的爬蟲')
	parser.add_argument('--start_date', 
					   help='回補起始日期 (YYYY-MM-DD)',
					   default='2025-01-07')
	parser.add_argument('--end_date',
					   help='回補結束日期 (YYYY-MM-DD)',
					   default='2025-01-07')
	parser.add_argument('--debug', action='store_true',
					   help='開啟除錯模式')
	args = parser.parse_args()
	
	if args.debug:
		logging.getLogger().setLevel(logging.DEBUG)
		
	asyncio.run(test_crawler(args.crawler, args.start_date, args.end_date))