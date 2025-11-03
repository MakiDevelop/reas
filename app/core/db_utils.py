"""
資料庫工具函數
提供批次操作和優化的資料庫操作方法
"""
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from app.models.article import Article
import logging

logger = logging.getLogger(__name__)


def batch_upsert_articles(
    session: Session,
    articles: List[Dict[str, Any]],
    batch_size: int = 100
) -> tuple[int, int]:
    """
    批次插入或更新文章

    Args:
        session: 資料庫 session
        articles: 文章資料列表
        batch_size: 每批次處理的數量

    Returns:
        tuple: (新增數量, 更新數量)
    """
    inserted_count = 0
    updated_count = 0

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]

        for article_data in batch:
            try:
                # 使用 PostgreSQL 的 ON CONFLICT 語法進行 upsert
                stmt = insert(Article).values(**article_data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['url'],  # 使用 url 作為唯一鍵
                    set_={
                        'title': stmt.excluded.title,
                        'content': stmt.excluded.content,
                        'description': stmt.excluded.description,
                        'published_at': stmt.excluded.published_at,
                        'image_url': stmt.excluded.image_url,
                        'category': stmt.excluded.category,
                        'reporter': stmt.excluded.reporter,
                        'updated_at': stmt.excluded.updated_at,
                    }
                )

                result = session.execute(stmt)

                # 判斷是插入還是更新
                # 注意：這個方法可能不夠準確，但足夠用於日誌記錄
                if result.rowcount > 0:
                    # 檢查是否為更新（通過查詢檢查記錄是否已存在）
                    existing = session.query(Article).filter(
                        Article.url == article_data['url']
                    ).first()
                    if existing and existing.created_at != existing.updated_at:
                        updated_count += 1
                    else:
                        inserted_count += 1

            except Exception as e:
                logger.error(f"Error upserting article {article_data.get('url', 'unknown')}: {str(e)}")
                continue

        # 每批次提交一次
        session.commit()
        logger.info(f"Batch {i//batch_size + 1}: Processed {len(batch)} articles")

    return inserted_count, updated_count


def bulk_insert_articles(
    session: Session,
    articles: List[Dict[str, Any]],
    batch_size: int = 100
) -> int:
    """
    批次插入文章（僅插入，不更新）
    適用於確定不會有重複的情況

    Args:
        session: 資料庫 session
        articles: 文章資料列表
        batch_size: 每批次處理的數量

    Returns:
        int: 插入的文章數量
    """
    inserted_count = 0

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]

        try:
            # 使用 bulk_insert_mappings 進行批次插入
            session.bulk_insert_mappings(Article, batch)
            session.commit()
            inserted_count += len(batch)
            logger.info(f"Batch {i//batch_size + 1}: Inserted {len(batch)} articles")
        except Exception as e:
            logger.error(f"Error in batch insert: {str(e)}")
            session.rollback()
            # 如果批次失敗，嘗試逐個插入
            for article_data in batch:
                try:
                    article = Article(**article_data)
                    session.add(article)
                    session.commit()
                    inserted_count += 1
                except Exception as e:
                    logger.error(f"Error inserting article {article_data.get('url', 'unknown')}: {str(e)}")
                    session.rollback()
                    continue

    return inserted_count


def cleanup_old_articles(
    session: Session,
    days: int = 365
) -> int:
    """
    清理舊文章

    Args:
        session: 資料庫 session
        days: 保留最近幾天的文章

    Returns:
        int: 刪除的文章數量
    """
    from datetime import datetime, timedelta

    cutoff_date = datetime.now() - timedelta(days=days)

    try:
        result = session.query(Article).filter(
            Article.published_at < cutoff_date
        ).delete()
        session.commit()
        logger.info(f"Cleaned up {result} articles older than {days} days")
        return result
    except Exception as e:
        logger.error(f"Error cleaning up old articles: {str(e)}")
        session.rollback()
        return 0
