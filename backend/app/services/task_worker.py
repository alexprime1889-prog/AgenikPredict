"""
Task worker loop and local dispatch helpers.
"""

from __future__ import annotations

import json
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from ..config import Config
from ..models.task import TaskManager
from ..utils.logger import get_logger
from .task_handlers import TASK_HANDLERS


logger = get_logger("agenikpredict.task_worker")


class WorkerDispatchUnavailable(RuntimeError):
    """Raised when web services cannot safely enqueue tasks for a worker."""


def ensure_worker_dispatch_ready():
    """Fail fast when worker-mode dispatch is configured without a live consumer."""
    mode = (Config.TASK_EXECUTION_MODE or "inline").lower()
    if mode != "worker":
        return None

    if (Config.SERVICE_ROLE or "web").lower() == "worker":
        return {
            "role": "worker",
            "task_execution_mode": "worker",
            "worker_consumer_active": True,
            "task_store_mode": Config.TASK_STORE_MODE,
            "task_read_source": Config.TASK_READ_SOURCE,
        }

    worker_healthcheck_url = (Config.WORKER_HEALTHCHECK_URL or "").strip()
    if not worker_healthcheck_url:
        raise WorkerDispatchUnavailable(
            "Worker dispatch is not configured: WORKER_HEALTHCHECK_URL is required when TASK_EXECUTION_MODE=worker"
        )

    timeout_seconds = max(float(Config.WORKER_HEALTHCHECK_TIMEOUT_SECONDS or 2.5), 0.1)
    try:
        with urlopen(worker_healthcheck_url, timeout=timeout_seconds) as response:
            status_code = getattr(response, "status", None) or response.getcode()
            if status_code != 200:
                raise WorkerDispatchUnavailable(
                    f"Worker healthcheck returned HTTP {status_code} from {worker_healthcheck_url}"
                )
            payload = json.loads(response.read().decode("utf-8"))
    except WorkerDispatchUnavailable:
        raise
    except HTTPError as exc:
        raise WorkerDispatchUnavailable(
            f"Worker healthcheck returned HTTP {exc.code} from {worker_healthcheck_url}"
        ) from exc
    except URLError as exc:
        raise WorkerDispatchUnavailable(
            f"Worker healthcheck request failed for {worker_healthcheck_url}: {exc.reason}"
        ) from exc
    except Exception as exc:
        raise WorkerDispatchUnavailable(
            f"Worker healthcheck request failed for {worker_healthcheck_url}: {exc}"
        ) from exc

    if payload.get("role") != "worker":
        raise WorkerDispatchUnavailable(
            f"Worker healthcheck responded with unexpected role={payload.get('role')!r}"
        )
    if payload.get("task_execution_mode") != "worker":
        raise WorkerDispatchUnavailable(
            f"Worker healthcheck reported task_execution_mode={payload.get('task_execution_mode')!r}"
        )
    if payload.get("worker_consumer_active") is not True:
        raise WorkerDispatchUnavailable("Worker healthcheck reported no active consumer")
    if payload.get("task_store_mode") != "db":
        raise WorkerDispatchUnavailable(
            f"Worker healthcheck reported task_store_mode={payload.get('task_store_mode')!r}"
        )
    if payload.get("task_read_source") != "db":
        raise WorkerDispatchUnavailable(
            f"Worker healthcheck reported task_read_source={payload.get('task_read_source')!r}"
        )
    return payload


def execute_task(task_id: str, lease=None) -> bool:
    task = TaskManager().get_task(task_id)
    if not task:
        logger.warning("Task not found for execution: %s", task_id)
        return False

    handler = TASK_HANDLERS.get(task.task_type)
    if not handler:
        logger.warning("No task handler registered for task_type=%s", task.task_type)
        return False

    return handler(task_id, lease=lease)


def dispatch_task(task_id: str):
    """Dispatch a task according to the configured execution mode."""
    mode = (Config.TASK_EXECUTION_MODE or "inline").lower()
    if mode == "inline":
        thread = threading.Thread(
            target=execute_task,
            args=(task_id,),
            name=f"task-dispatch-{task_id[:8]}",
            daemon=True,
        )
        thread.start()
        return True
    if mode == "worker":
        ensure_worker_dispatch_ready()
        logger.info("Task enqueued without local dispatch because TASK_EXECUTION_MODE=%s: %s", mode, task_id)
        return False

    raise RuntimeError(f"Unsupported TASK_EXECUTION_MODE: {mode}")


class TaskWorker:
    """Polling worker for persistent background task execution."""

    def __init__(self, app=None):
        self.app = app
        self.task_manager = TaskManager()
        self.poll_interval_seconds = max(float(Config.TASK_WORKER_POLL_INTERVAL_SECONDS or 2), 0.25)
        self.batch_size = max(int(Config.TASK_WORKER_BATCH_SIZE or 10), 1)
        self.worker_id = f"worker:{TaskManager.default_worker_id()}"
        self.task_types = list(TASK_HANDLERS.keys())

    def run_once(self) -> bool:
        lease = self.task_manager.claim_next_task(
            task_types=self.task_types,
            worker_id=self.worker_id,
            batch_size=self.batch_size,
        )
        if not lease:
            return False

        logger.info("Worker claimed task: task_id=%s worker_id=%s", lease.task_id, self.worker_id)
        if self.app is None:
            return execute_task(lease.task_id, lease=lease)

        with self.app.app_context():
            return execute_task(lease.task_id, lease=lease)

    def run_forever(self):
        logger.info(
            "Task worker started: mode=%s poll_interval=%ss batch_size=%s",
            Config.TASK_EXECUTION_MODE,
            self.poll_interval_seconds,
            self.batch_size,
        )
        while True:
            worked = False
            try:
                worked = self.run_once()
            except Exception as exc:
                logger.exception("Task worker iteration failed: %s", exc)
            if not worked:
                time.sleep(self.poll_interval_seconds)
