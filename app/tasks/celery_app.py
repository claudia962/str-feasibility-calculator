"""Celery app stub — Phase 2 will move pipeline tasks here."""
from celery import Celery
from app.config import get_settings
settings = get_settings()
celery_app = Celery("feasibility", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_serializer="json", accept_content=["json"], timezone="UTC")
