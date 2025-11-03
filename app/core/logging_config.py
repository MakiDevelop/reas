"""
日誌配置模組
提供結構化日誌和監控功能
"""
import logging
import sys
from typing import Any
from app.core.config import settings
from datetime import datetime
import json


class StructuredFormatter(logging.Formatter):
    """結構化日誌格式器"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        # 添加額外的上下文信息
        if hasattr(record, 'crawler_type'):
            log_data['crawler_type'] = record.crawler_type
        if hasattr(record, 'url'):
            log_data['url'] = record.url
        if hasattr(record, 'duration'):
            log_data['duration'] = record.duration

        # 添加異常信息
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """彩色日誌格式器（用於控制台）"""

    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        levelname = record.levelname
        if levelname in self.COLORS:
            levelname_color = f"{self.COLORS[levelname]}{levelname:8}{self.RESET}"
            record.levelname = levelname_color

        return super().format(record)


def setup_logging():
    """設置日誌配置"""

    # 設定日誌級別
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # 創建根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除現有的處理器
    root_logger.handlers.clear()

    # 控制台處理器（彩色輸出）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = ColoredFormatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 文件處理器（結構化日誌）
    try:
        import os
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.FileHandler(
            f'{log_dir}/crawler_{datetime.now().strftime("%Y%m%d")}.log',
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_formatter = StructuredFormatter()
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        root_logger.warning(f"無法創建文件日誌處理器: {str(e)}")

    # 設置第三方庫的日誌級別
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('selenium').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)

    root_logger.info("日誌系統已初始化")


class CrawlerLogger:
    """爬蟲專用日誌工具"""

    def __init__(self, crawler_name: str):
        self.logger = logging.getLogger(f"crawler.{crawler_name}")
        self.crawler_name = crawler_name
        self.start_time = None

    def start_crawl(self):
        """記錄爬取開始"""
        self.start_time = datetime.now()
        self.logger.info(f"開始爬取 {self.crawler_name}")

    def end_crawl(self, article_count: int, success: bool = True):
        """記錄爬取結束"""
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
            if success:
                self.logger.info(
                    f"✅ {self.crawler_name} 爬取完成：{article_count} 篇文章，耗時 {duration:.2f}秒"
                )
            else:
                self.logger.error(
                    f"❌ {self.crawler_name} 爬取失敗，耗時 {duration:.2f}秒"
                )

    def log_article(self, title: str, url: str):
        """記錄文章"""
        self.logger.debug(f"爬取文章: {title[:50]} - {url}")

    def log_error(self, error: Exception, url: str = None):
        """記錄錯誤"""
        extra = {'url': url} if url else {}
        self.logger.error(
            f"爬取錯誤: {str(error)}",
            exc_info=True,
            extra=extra
        )
