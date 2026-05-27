"""Enqueue on-demand arq jobs from request handlers (Ch16).

Returns True if the job was enqueued, False if the queue is unavailable — the
caller then falls back to in-process BackgroundTasks.
"""
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


async def enqueue(task_name: str, *args) -> bool:
    if not (settings.use_task_queue and settings.redis_url):
        return False
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await pool.enqueue_job(task_name, *args)
        await pool.aclose()
        return True
    except Exception as e:  # noqa: BLE001 — any failure → caller falls back
        logger.warning("arq enqueue failed for %s: %s", task_name, e)
        return False
