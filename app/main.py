from fastapi import FastAPI, Request, Depends, HTTPException, BackgroundTasks, APIRouter, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.core.database import engine, Base, get_db
from app.api.v1.api import api_router
from app.models.article import Article
import logging
from sqlalchemy import text, desc, or_, select
from app.core.config import settings
from math import ceil
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import subprocess
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse, StreamingResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Optional
import asyncio
from app.tests.test_crawler import test_crawler
import multiprocessing
from pytz import timezone
import pandas as pd
from tempfile import NamedTemporaryFile
import os
import shutil
import io
import csv
from app.services.crawler.ltn_crawler import LTNCrawler
from app.services.crawler.udn_crawler import UDNCrawler
from app.services.crawler.nextapple_crawler import NextAppleCrawler
from app.services.crawler.ettoday_crawler import EttodayCrawler
from app.services.crawler.edgeprop_crawler import EdgePropCrawler
from app.services.crawler.starproperty_crawler import StarPropertyCrawler
from app.services.crawler.freemalaysiatoday_crawler import FreeMalaysiaTodayCrawler
from app.services.crawler.hk852house_crawler import House852Crawler

# 設定日誌
from app.core.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="房地產新聞爬蟲 API",
    description="提供房地產新聞的搜尋和瀏覽功能",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# 註定模板和靜態檔案
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 註冊 API 路由
app.include_router(api_router, prefix=settings.API_V1_STR)

# 建立排程器
scheduler = AsyncIOScheduler(timezone=timezone('Asia/Taipei'))

async def run_crawler_in_background(crawler_type: str = "all", start_date: str = None, end_date: str = None):
    """在背景執行爬蟲"""
    try:
        # 如果沒有指定日期，使用今天
        if not start_date or not end_date:
            start_date = end_date = datetime.now().strftime("%Y-%m-%d")
            
        # 定義要爬取的新聞來源
        sources = ["udn", "ltn", "nextapple", "ettoday", "edgeprop", "starproperty", "freemalaysiatoday", "hk852house"] if crawler_type == "all" else [crawler_type]
        
        for source in sources:
            try:
                # 執行爬蟲指令
                subprocess.run([
                    "python", 
                    "-m", 
                    "app.tests.test_crawler",
                    source,
                    "--start_date", 
                    start_date,
                    "--end_date",
                    end_date
                ], check=True)
                logger.info(f"{source} 爬蟲完成: {datetime.now()}")
            except subprocess.CalledProcessError as e:
                logger.error(f"{source} 爬蟲執行失敗: {str(e)}")
                
    except Exception as e:
        logger.error(f"爬蟲執行失敗: {str(e)}")

async def crawl_yesterday():
    """排程爬蟲任務 - 爬取前一天的文章"""
    logger.info(f"開始執行排程爬蟲任務: {datetime.now()}")
    try:
        # 取得昨天日期
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        logger.info(f"準備爬取前一天 ({yesterday}) 的文章")

        # 建立新的 Process 來執行爬蟲
        process = multiprocessing.Process(
            target=run_crawler_process,
            args=(yesterday, yesterday)
        )
        process.start()

        logger.info(f"排程爬蟲任務已啟動: {datetime.now()}")

    except Exception as e:
        logger.error(f"排程爬蟲任務失敗: {str(e)}")

# 設定排程任務
def setup_scheduler():
    try:
        # 每天 8:00 執行 (台灣時間) - 爬取前一天的文章
        scheduler.add_job(
            crawl_yesterday,
            CronTrigger(hour=8, minute=0, timezone=timezone('Asia/Taipei')),
            id='crawl_yesterday_8am',
            replace_existing=True
        )

        # 啟動排程器
        scheduler.start()
        logger.info(f"排程器已啟動: {datetime.now(timezone('Asia/Taipei'))}")
        logger.info("已設定的排程任務:")
        for job in scheduler.get_jobs():
            logger.info(f"- {job.id}: 下次執行時間 {job.next_run_time}")

    except Exception as e:
        logger.error(f"設定排程器時發生錯誤: {str(e)}")

# 前台頁面路由
@app.get("/", name="index")
async def index(
    request: Request, 
    page: int = 1,
    source: str = None,
    category: str = None,
    start_date: str = None,
    end_date: str = None,
    keyword: str = None,
    error: str = None,
    db: Session = Depends(get_db)
):
    # 設定每頁顯示數量
    per_page = 20
    
    # 建立基本查詢
    query = db.query(Article)
    
    # 加入搜尋條件
    if keyword:
        query = query.filter(
            or_(
                Article.title.ilike(f"%{keyword}%"),
                Article.content.ilike(f"%{keyword}%")
            )
        )
    
    if source:
        query = query.filter(Article.source == source)
    
    # 計算總數和頁數
    total = query.count()
    total_pages = ceil(total / per_page)
    
    # 取得分頁資料
    articles = query\
        .order_by(desc(Article.published_at))\
        .offset((page - 1) * per_page)\
        .limit(per_page)\
        .all()
    
    # 取得所有來源選項
    sources = db.query(Article.source).distinct().all()
    sources = [source[0] for source in sources]
    
    # 建立查詢參數字典
    params = {}
    if source:
        params['source'] = source
    if category:
        params['category'] = category
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date
    if keyword:
        params['keyword'] = keyword

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "articles": articles,
            "current_page": page,
            "total_pages": total_pages,
            "total": total,
            "keyword": keyword,
            "source": source,
            "sources": sources,
            "params": params,
            "error": error
        }
    )

@app.get("/article/{id}")
async def article_detail(
    request: Request,
    id: int,
    db: Session = Depends(get_db)
):
    # 取得文章詳細資料
    article = db.query(Article).filter(Article.id == id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # 取得相關文章（同一來源的最新5篇其他文章）
    related_articles = db.query(Article)\
        .filter(Article.source == article.source)\
        .filter(Article.id != article.id)\
        .order_by(desc(Article.published_at))\
        .limit(5)\
        .all()
    
    return templates.TemplateResponse(
        "detail.html",
        {
            "request": request,
            "article": article,
            "related_articles": related_articles
        }
    )

@app.on_event("startup")
async def startup_event():
    """
    應用啟動時執行的事件
    """
    try:
        # 嘗試創建所有資料表
        Base.metadata.create_all(bind=engine)
        # 測試資料庫連接
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("資料庫連接成功！")
    except Exception as e:
        logger.error(f"資料庫連接失敗：{str(e)}")
        raise e

    setup_scheduler()

# 在應用程式關閉時關閉排程器
@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    logger.info("排程器已關閉")

@app.get("/health")
def health_check():
    """
    健康檢查端點
    """
    try:
        # 測試資料庫連接
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": str(e)
        }

@app.get("/crawl/latest", name="crawl_latest")
async def crawl_latest(background_tasks: BackgroundTasks):
    """爬取最新一天的新聞"""
    try:
        # 在背景執行所有爬蟲
        background_tasks.add_task(run_crawler_in_background)
        return RedirectResponse(url="/?message=crawl_started", status_code=303)
    except Exception as e:
        logger.error(f"爬蟲執行失敗: {str(e)}")
        return RedirectResponse(url="/?error=crawl_failed", status_code=303)

@app.get("/crawl/last-week", name="crawl_last_week")
async def crawl_last_week(background_tasks: BackgroundTasks):
    """爬取最近七天的新聞"""
    try:
        # 計算日期範圍
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        # 在背景執行所有爬蟲
        background_tasks.add_task(
            run_crawler_in_background,
            start_date=start_date,
            end_date=end_date
        )
        
        return RedirectResponse(url="/?message=crawl_started", status_code=303)
    except Exception as e:
        logger.error(f"爬蟲執行失敗: {str(e)}")
        return RedirectResponse(url="/?error=crawl_failed", status_code=303)

# 建立一個新的 Process 來執行爬蟲
def run_crawler_process(start_date, end_date, parallel=True):
    """在新的 Process 中執行爬蟲（支援並行爬取）"""
    async def run_single_crawler(source: str):
        """執行單個爬蟲（帶異常處理）"""
        try:
            logger.info(f"開始爬取 {source} 文章...")
            count = await test_crawler(
                crawler_type=source,
                start_date=start_date,
                end_date=end_date
            )
            logger.info(f"✅ {source} 爬蟲完成，共爬取 {count} 篇文章")
            return {source: {'status': 'success', 'count': count}}
        except Exception as e:
            logger.error(f"❌ {source} 爬蟲失敗: {str(e)}", exc_info=True)
            return {source: {'status': 'failed', 'error': str(e)}}

    async def run():
        sources = ["ltn", "udn", "nextapple", "ettoday", "edgeprop", "starproperty", "freemalaysiatoday", "hk852house"]

        if parallel:
            # 並行爬取
            logger.info(f"並行爬取 {len(sources)} 個來源...")
            tasks = [run_single_crawler(source) for source in sources]
            results_list = await asyncio.gather(*tasks, return_exceptions=True)

            # 整合結果
            results = {}
            for result in results_list:
                if isinstance(result, dict):
                    results.update(result)
                elif isinstance(result, Exception):
                    logger.error(f"爬蟲任務異常: {str(result)}")
        else:
            # 串行爬取
            logger.info(f"串行爬取 {len(sources)} 個來源...")
            results = {}
            for source in sources:
                result = await run_single_crawler(source)
                results.update(result)
                await asyncio.sleep(2)  # 串行模式下添加延遲

        # 記錄總結
        success_count = sum(1 for r in results.values() if r.get('status') == 'success')
        failed_count = len(sources) - success_count
        total_articles = sum(r.get('count', 0) for r in results.values() if r.get('status') == 'success')

        logger.info(f"爬蟲執行完成：成功 {success_count} 個，失敗 {failed_count} 個，共爬取 {total_articles} 篇文章")

        return results

    asyncio.run(run())

@app.post("/api/crawl")
async def crawl_articles(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    crawler_type: Optional[str] = None
):
    """啟動爬蟲（使用新的 Process）"""
    try:
        # 建立新的 Process 來執行爬蟲
        process = multiprocessing.Process(
            target=run_crawler_process,
            args=(start_date, end_date)
        )
        process.start()
        
        return {
            "status": "success",
            "message": "爬蟲已在背景開始執行",
            "results": [{
                "source": source,
                "status": "started",
                "message": "開始執行爬蟲"
            } for source in ["ltn", "udn", "nextapple", "ettoday", "edgeprop", "starproperty", "freemalaysiatoday", "hk852house"]]
        }
        
    except Exception as e:
        logger.error(f"啟動爬蟲失敗: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.get("/scheduler/status")
async def check_scheduler_status():
    """檢查排程器狀態"""
    try:
        taipei_tz = timezone('Asia/Taipei')
        current_time = datetime.now(taipei_tz)
        
        jobs = []
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "next_run_time": str(job.next_run_time.astimezone(taipei_tz)),
                "trigger": str(job.trigger)
            })
        
        return JSONResponse({
            "status": "running" if scheduler.running else "stopped",
            "jobs": jobs,
            "current_time": str(current_time)
        })
    except Exception as e:
        logger.error(f"檢查排程器狀態時發生錯誤: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"檢查排程器狀態時發生錯誤: {str(e)}"
        )

@app.get("/scheduler/test")
async def test_scheduler():
    """立即執行排程任務進行測試"""
    try:
        logger.info("開始測試排程任務")
        await crawl_yesterday()
        return JSONResponse({
            "message": "排程任務測試已啟動（爬取前一天文章），請查看日誌",
            "time": str(datetime.now())
        })
    except Exception as e:
        logger.error(f"測試排程任務時發生錯誤: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"測試排程任務時發生錯誤: {str(e)}"
        )

@app.get("/export/latest")
async def export_latest(source: str = None, db: Session = Depends(get_db)):
	"""匯出最新1000筆文章為Excel，可以指定來源"""
	try:
		# 建立查詢
		query = db.query(Article).order_by(desc(Article.published_at))
		
		# 如果指定了來源且不是 'all'，則進行過濾
		if source and source != 'all':
			query = query.filter(Article.source == source)
		
		# 限制最多1000筆
		articles = query.limit(1000).all()
		
		# 準備資料
		data = []
		for article in articles:
			data.append({
				'ID': article.id,
				'標題': article.title,
				'來源': article.source,
				'網址': article.url,
				'發布時間': article.published_at,
				'建立時間': article.created_at,
				'更新時間': article.updated_at,
				'內容': article.content,
				'描述': article.description or ''
			})
		
		# 建立 DataFrame
		df = pd.DataFrame(data)
		
		# 建立 BytesIO 物件
		output = io.BytesIO()
		
		# 寫入 Excel
		with pd.ExcelWriter(output, engine='openpyxl') as writer:
			df.to_excel(writer, index=False, sheet_name='文章列表')
		
		# 將指針移到開頭
		output.seek(0)
		
		# 建立檔案名稱，如果有指定來源，則加入來源名稱
		source_text = f"_{source}" if source and source != 'all' else ""
		filename = f"articles_export{source_text}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
		
		# 回傳串流響應
		headers = {
			'Content-Disposition': f'attachment; filename="{filename}"',
			'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
		}
		
		return StreamingResponse(
			output,
			headers=headers,
			media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
		)
			
	except Exception as e:
		logger.error(f"匯出Excel時發生錯誤: {str(e)}")
		raise HTTPException(
			status_code=500,
			detail=f"匯出失敗: {str(e)}"
		)

@app.get("/export")
async def export_page(request: Request, source: str = None):
	"""匯出資料頁面，可以預設指定來源"""
	# 取得所有可用的新聞來源
	db = next(get_db())
	sources = db.query(Article.source).distinct().all()
	sources = [s[0] for s in sources]
	
	return templates.TemplateResponse(
		"export.html",
		{
			"request": request,
			"selected_source": source,  # 傳遞預選的來源
			"sources": sources  # 傳遞所有可用的來源
		}
	)

@app.post("/export/articles")
async def export_articles(
	request: Request,
	start_date: str = Form(...),
	end_date: str = Form(...),
	keyword: str = Form(None),
	source: str = Form(None),  # 添加來源參數
	file_format: str = Form("csv")
):
	"""匯出文章資料"""
	try:
		db = next(get_db())
		
		# 建立查詢
		query = select(Article).order_by(Article.published_at.desc())
		
		# 如果有日期範圍
		if start_date and end_date:
			start = datetime.strptime(f"{start_date} 00:00:00", '%Y-%m-%d %H:%M:%S')
			end = datetime.strptime(f"{end_date} 23:59:59", '%Y-%m-%d %H:%M:%S')
			query = query.where(Article.published_at.between(start, end))
		
		# 如果有關鍵字
		if keyword:
			query = query.where(Article.title.ilike(f'%{keyword}%'))
		
		# 如果有指定來源且不是 'all'
		if source and source != 'all':
			query = query.where(Article.source == source)
		
		# 執行查詢
		result = db.execute(query)
		articles = result.scalars().all()
		
		if not articles:
			raise HTTPException(status_code=404, detail="找不到符合條件的文章")
		
		# 準備 CSV 資料
		output = io.StringIO()
		writer = csv.writer(output)
		
		# 寫入標題列
		writer.writerow([
			'ID', '標題', '來源', '分類', '記者', 
			'發布時間', '內容', '連結', '圖片連結'
		])
		
		# 寫入資料列
		for article in articles:
			writer.writerow([
				str(article.id),
				str(article.title or ''),
				str(article.source or ''),
				str(article.category or ''),
				str(article.reporter or ''),
				article.published_at.strftime('%Y-%m-%d %H:%M:%S'),
				str(article.content or ''),
				str(article.url or ''),
				str(article.image_url or '')
			])
		
		# 設定檔案名稱 - 加入來源資訊
		timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
		source_text = f"_{source}" if source and source != 'all' else ""
		
		if keyword:
			filename = f"news_search{source_text}_{timestamp}.csv"
		else:
			filename = f"news{source_text}_{start_date}_to_{end_date}_{timestamp}.csv"
		
		# 準備回應
		output.seek(0)
		output_str = output.getvalue()
		output_bytes = output_str.encode('utf-8-sig')
		
		return StreamingResponse(
			io.BytesIO(output_bytes),
			media_type="text/csv",
			headers={
				"Content-Disposition": f"attachment; filename={filename}",
				"Content-Type": "text/csv; charset=utf-8-sig"
			}
		)
		
	except HTTPException as he:
		raise he
	except Exception as e:
		logger.error(f"匯出文章時發生錯誤: {str(e)}")
		raise HTTPException(status_code=500, detail=f"匯出失敗: {str(e)}")

@app.get("/rescrape")
async def rescrape_page(request: Request):
    """回補爬蟲頁面"""
    return templates.TemplateResponse(
        "rescrape.html",
        {"request": request}
    )

@app.post("/api/rescrape")
async def rescrape_articles(
    request: Request,
    start_date: str = Form(...),
    end_date: str = Form(...),
    source: str = Form(None)
):
    """執行回補爬蟲"""
    try:
        all_results = []
        messages = [f"開始爬取新聞，日期範圍：{start_date} 到 {end_date}"]
        
        # 決定要爬取的來源
        sources = ["ltn", "udn", "nextapple", "ettoday", "edgeprop", "starproperty", "freemalaysiatoday", "hk852house"]
        crawlers_to_run = sources if source == 'all' else [source]
        
        # 執行每個爬蟲
        for source_name in crawlers_to_run:
            try:
                messages.append(f"\n開始爬取 {source_name} 新聞...")
                
                # 使用 test_crawler 執行爬蟲
                count = await test_crawler(
                    crawler_type=source_name,
                    start_date=start_date,
                    end_date=end_date
                )
                
                messages.append(f"成功爬取 {count} 篇文章")
                
            except Exception as e:
                error_msg = f"爬取 {source_name} 時發生錯誤: {str(e)}"
                messages.append(error_msg)
                logger.error(error_msg)
                continue  # 繼續執行其他爬蟲
        
        # 加入總結資訊
        messages.append(f"\n爬取完成")
        
        return {
            "status": "success",
            "message": "\n".join(messages)
        }
        
    except Exception as e:
        logger.error(f"回補爬蟲失敗: {str(e)}")
        return {
            "status": "error",
            "message": f"爬蟲失敗: {str(e)}"
        }