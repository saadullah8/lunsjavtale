import logging
import socket
from urllib.parse import urlparse

from django.conf import settings

logger = logging.getLogger(__name__)


def broker_is_available(timeout=0.2):
    broker_url = getattr(settings, "CELERY_BROKER_URL", "")
    parsed = urlparse(broker_url)
    if parsed.scheme != "redis":
        return True
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def dispatch_task(task, *args, **kwargs):
    if not broker_is_available():
        logger.warning("Celery broker unavailable. Running task '%s' synchronously.", task.name)
        try:
            task(*args, **kwargs)
        except Exception as e:
            logger.error("Failed to run task '%s' synchronously: %s", task.name, str(e))
        return None
    return task.apply_async(args=args, kwargs=kwargs, retry=False)
