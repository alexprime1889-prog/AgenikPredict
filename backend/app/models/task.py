"""
Task status management
For tracking long-running tasks (e.g., graph building)
"""

import json
import os
import uuid
import threading
import socket
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field

from ..config import Config
from .user import DATABASE_URL, PH, get_db
from ..utils.logger import get_logger


logger = get_logger('agenikpredict.task')


class TaskStatus(str, Enum):
    """Task status enum"""
    PENDING = "pending"          # Pending
    PROCESSING = "processing"    # Processing
    COMPLETED = "completed"      # Completed
    FAILED = "failed"            # Failed


@dataclass
class Task:
    """Task data class"""
    task_id: str
    task_type: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    progress: int = 0              # Overall progress percentage 0-100
    message: str = ""              # Status message
    result: Optional[Dict] = None  # Task result
    error: Optional[str] = None    # Error info
    metadata: Dict = field(default_factory=dict)  # Additional metadata
    progress_detail: Dict = field(default_factory=dict)  # Detailed progress info
    execution_key: Optional[str] = None
    attempt_count: int = 0
    max_attempts: int = 1
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    dead_letter_reason: Optional[str] = None
    lease_owner: Optional[str] = None
    lease_token: Optional[str] = None
    lease_expires_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress": self.progress,
            "message": self.message,
            "progress_detail": self.progress_detail,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
            "execution_key": self.execution_key,
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "dead_letter_reason": self.dead_letter_reason,
            "lease_expires_at": self.lease_expires_at.isoformat() if self.lease_expires_at else None,
            "last_heartbeat_at": self.last_heartbeat_at.isoformat() if self.last_heartbeat_at else None,
        }


@dataclass
class TaskLease:
    """A claimed task lease with background heartbeat support."""
    task_id: str
    lease_token: str
    worker_id: str
    lease_expires_at: datetime
    heartbeat_interval_seconds: int
    lease_seconds: int
    _stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    _thread: Optional[threading.Thread] = field(default=None, repr=False)

    def start_heartbeat(self, task_manager: "TaskManager"):
        """Extend the task lease periodically while work is still running."""
        if self._thread and self._thread.is_alive():
            return

        def _heartbeat():
            while not self._stop_event.wait(self.heartbeat_interval_seconds):
                if not task_manager.refresh_task_lease(
                    self.task_id,
                    self.lease_token,
                    lease_seconds=self.lease_seconds,
                ):
                    logger.warning(
                        "Stopping task heartbeat because lease refresh failed: task_id=%s worker_id=%s",
                        self.task_id,
                        self.worker_id,
                    )
                    break

        self._thread = threading.Thread(
            target=_heartbeat,
            name=f"task-heartbeat-{self.task_id[:8]}",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        """Stop the background heartbeat thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)


class TaskManager:
    """
    Task manager
    Thread-safe task status management
    """
    
    _instance = None
    _lock = threading.Lock()
    _reaper_lock = threading.Lock()
    _reaper_thread: Optional[threading.Thread] = None
    _reaper_stop_event = threading.Event()
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._tasks: Dict[str, Task] = {}
                    cls._instance._task_lock = threading.Lock()
        return cls._instance

    @staticmethod
    def init_db():
        """Create task persistence tables if they do not exist."""
        with get_db() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    message TEXT DEFAULT '',
                    result_json TEXT,
                    error TEXT,
                    metadata_json TEXT DEFAULT '{}',
                    progress_detail_json TEXT DEFAULT '{}',
                    owner_id TEXT,
                    project_id TEXT,
                    simulation_id TEXT,
                    report_id TEXT,
                    graph_id TEXT,
                    execution_key TEXT,
                    attempt_count INTEGER DEFAULT 0,
                    max_attempts INTEGER DEFAULT 1,
                    started_at TEXT,
                    finished_at TEXT,
                    next_retry_at TEXT,
                    dead_letter_reason TEXT,
                    lease_owner TEXT,
                    lease_token TEXT,
                    lease_expires_at TEXT,
                    last_heartbeat_at TEXT
                )"""
            )

            schema_probe = conn.execute("SELECT * FROM tasks LIMIT 0")
            existing_columns = {
                column[0] for column in (schema_probe.description or [])
            }
            additive_columns = {
                "execution_key": "TEXT",
                "attempt_count": "INTEGER DEFAULT 0",
                "max_attempts": "INTEGER DEFAULT 1",
                "started_at": "TEXT",
                "finished_at": "TEXT",
                "next_retry_at": "TEXT",
                "dead_letter_reason": "TEXT",
                "lease_owner": "TEXT",
                "lease_token": "TEXT",
                "lease_expires_at": "TEXT",
                "last_heartbeat_at": "TEXT",
            }
            for column_name, column_def in additive_columns.items():
                if column_name not in existing_columns:
                    conn.execute(f"ALTER TABLE tasks ADD COLUMN {column_name} {column_def}")

            duplicate_groups = conn.execute(
                f"SELECT task_type, execution_key FROM tasks "
                f"WHERE execution_key IS NOT NULL "
                f"AND status IN ({PH}, {PH}) "
                f"GROUP BY task_type, execution_key "
                f"HAVING COUNT(*) > 1",
                (TaskStatus.PENDING.value, TaskStatus.PROCESSING.value),
            ).fetchall()
            dedupe_now = datetime.now().isoformat()
            for group in duplicate_groups:
                rows = conn.execute(
                    f"SELECT task_id FROM tasks "
                    f"WHERE task_type = {PH} AND execution_key = {PH} "
                    f"AND status IN ({PH}, {PH}) "
                    f"ORDER BY created_at ASC",
                    (
                        group["task_type"],
                        group["execution_key"],
                        TaskStatus.PENDING.value,
                        TaskStatus.PROCESSING.value,
                    ),
                ).fetchall()
                for duplicate in rows[1:]:
                    conn.execute(
                        f"UPDATE tasks SET "
                        f"status = {PH}, "
                        f"updated_at = {PH}, "
                        f"finished_at = COALESCE(finished_at, {PH}), "
                        f"message = {PH}, "
                        f"error = {PH}, "
                        f"dead_letter_reason = {PH}, "
                        f"next_retry_at = NULL, "
                        f"lease_owner = NULL, "
                        f"lease_token = NULL, "
                        f"lease_expires_at = NULL, "
                        f"last_heartbeat_at = NULL "
                        f"WHERE task_id = {PH}",
                        (
                            TaskStatus.FAILED.value,
                            dedupe_now,
                            dedupe_now,
                            "Superseded by an older active task with the same execution key",
                            "Duplicate active execution key reconciled during startup",
                            "duplicate_active_execution_key",
                            duplicate["task_id"],
                        ),
                    )

            index_stmts = [
                "CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(owner_id)",
                "CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id)",
                "CREATE INDEX IF NOT EXISTS idx_tasks_simulation_id ON tasks(simulation_id)",
                "CREATE INDEX IF NOT EXISTS idx_tasks_report_id ON tasks(report_id)",
                "CREATE INDEX IF NOT EXISTS idx_tasks_graph_id ON tasks(graph_id)",
                "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
                "CREATE INDEX IF NOT EXISTS idx_tasks_execution_key ON tasks(execution_key)",
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_active_execution_key "
                "ON tasks(task_type, execution_key) "
                "WHERE execution_key IS NOT NULL AND status IN ('pending', 'processing')",
                "CREATE INDEX IF NOT EXISTS idx_tasks_next_retry_at ON tasks(next_retry_at)",
                "CREATE INDEX IF NOT EXISTS idx_tasks_lease_expires_at ON tasks(lease_expires_at)",
            ]
            for stmt in index_stmts:
                conn.execute(stmt)

    @staticmethod
    def _json_dumps(value: Any, default: Any) -> str:
        payload = default if value is None else value
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _json_loads(value: Optional[str], default: Any) -> Any:
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    @staticmethod
    def _extract_links(metadata: Optional[Dict[str, Any]]) -> Dict[str, Optional[str]]:
        metadata = metadata or {}
        return {
            "owner_id": metadata.get("owner_id"),
            "project_id": metadata.get("project_id"),
            "simulation_id": metadata.get("simulation_id"),
            "report_id": metadata.get("report_id"),
            "graph_id": metadata.get("graph_id"),
        }

    @staticmethod
    def _mode() -> str:
        return (Config.TASK_STORE_MODE or "dual").lower()

    @staticmethod
    def _read_source() -> str:
        return (Config.TASK_READ_SOURCE or "fallback").lower()

    @staticmethod
    def _lease_seconds() -> int:
        return max(30, int(getattr(Config, "TASK_LEASE_SECONDS", 180) or 180))

    @staticmethod
    def _heartbeat_interval_seconds() -> int:
        default_interval = max(10, TaskManager._lease_seconds() // 3)
        return max(5, int(getattr(Config, "TASK_HEARTBEAT_INTERVAL_SECONDS", default_interval) or default_interval))

    @staticmethod
    def default_worker_id() -> str:
        configured = getattr(Config, "TASK_WORKER_ID", None) or os.environ.get("TASK_WORKER_ID")
        if configured:
            return configured
        return f"{socket.gethostname()}:{os.getpid()}"

    @classmethod
    def _writes_memory(cls) -> bool:
        return cls._mode() in {"memory", "dual"}

    @classmethod
    def _writes_db(cls) -> bool:
        return cls._mode() in {"dual", "db"}

    @staticmethod
    def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _row_value(row: Any, key: str) -> Any:
        if row is None:
            return None
        try:
            return row[key]
        except Exception:
            return None

    @staticmethod
    def _is_terminal_status(status: TaskStatus) -> bool:
        return status in {TaskStatus.COMPLETED, TaskStatus.FAILED}

    @staticmethod
    def _matches_links(task: Task, links: Optional[Dict[str, Any]]) -> bool:
        if not links:
            return True
        metadata = task.metadata or {}
        for key, value in links.items():
            if value is None:
                continue
            if metadata.get(key) != value:
                return False
        return True

    def _store_memory_task(self, task: Task):
        with self._task_lock:
            self._tasks[task.task_id] = task

    @staticmethod
    def _is_unique_violation(exc: Exception) -> bool:
        message = str(exc or "").lower()
        return "unique constraint" in message or "duplicate key value" in message

    @classmethod
    def _upsert_task_db(cls, task: Task):
        links = cls._extract_links(task.metadata)
        sql = (
            f"INSERT INTO tasks ("
            f"task_id, task_type, status, created_at, updated_at, progress, message, "
            f"result_json, error, metadata_json, progress_detail_json, owner_id, project_id, "
            f"simulation_id, report_id, graph_id, execution_key, attempt_count, max_attempts, "
            f"started_at, finished_at, next_retry_at, dead_letter_reason, lease_owner, "
            f"lease_token, lease_expires_at, last_heartbeat_at"
            f") VALUES ("
            f"{', '.join([PH] * 27)}"
            f") ON CONFLICT(task_id) DO UPDATE SET "
            f"task_type = EXCLUDED.task_type, "
            f"status = EXCLUDED.status, "
            f"created_at = EXCLUDED.created_at, "
            f"updated_at = EXCLUDED.updated_at, "
            f"progress = EXCLUDED.progress, "
            f"message = EXCLUDED.message, "
            f"result_json = EXCLUDED.result_json, "
            f"error = EXCLUDED.error, "
            f"metadata_json = EXCLUDED.metadata_json, "
            f"progress_detail_json = EXCLUDED.progress_detail_json, "
            f"owner_id = EXCLUDED.owner_id, "
            f"project_id = EXCLUDED.project_id, "
            f"simulation_id = EXCLUDED.simulation_id, "
            f"report_id = EXCLUDED.report_id, "
            f"graph_id = EXCLUDED.graph_id, "
            f"execution_key = EXCLUDED.execution_key, "
            f"attempt_count = EXCLUDED.attempt_count, "
            f"max_attempts = EXCLUDED.max_attempts, "
            f"started_at = EXCLUDED.started_at, "
            f"finished_at = EXCLUDED.finished_at, "
            f"next_retry_at = EXCLUDED.next_retry_at, "
            f"dead_letter_reason = EXCLUDED.dead_letter_reason, "
            f"lease_owner = EXCLUDED.lease_owner, "
            f"lease_token = EXCLUDED.lease_token, "
            f"lease_expires_at = EXCLUDED.lease_expires_at, "
            f"last_heartbeat_at = EXCLUDED.last_heartbeat_at"
        )
        params = (
            task.task_id,
            task.task_type,
            task.status.value,
            task.created_at.isoformat(),
            task.updated_at.isoformat(),
            task.progress,
            task.message,
            cls._json_dumps(task.result, None),
            task.error,
            cls._json_dumps(task.metadata, {}),
            cls._json_dumps(task.progress_detail, {}),
            links["owner_id"],
            links["project_id"],
            links["simulation_id"],
            links["report_id"],
            links["graph_id"],
            task.execution_key,
            task.attempt_count,
            max(task.max_attempts or 1, 1),
            cls._serialize_datetime(task.started_at),
            cls._serialize_datetime(task.finished_at),
            cls._serialize_datetime(task.next_retry_at),
            task.dead_letter_reason,
            task.lease_owner,
            task.lease_token,
            cls._serialize_datetime(task.lease_expires_at),
            cls._serialize_datetime(task.last_heartbeat_at),
        )
        with get_db() as conn:
            conn.execute(sql, params)

    @classmethod
    def _row_to_task(cls, row: Any) -> Task:
        return Task(
            task_id=row["task_id"],
            task_type=row["task_type"],
            status=TaskStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            progress=row["progress"] or 0,
            message=row["message"] or "",
            result=cls._json_loads(row["result_json"], None),
            error=row["error"],
            metadata=cls._json_loads(row["metadata_json"], {}),
            progress_detail=cls._json_loads(row["progress_detail_json"], {}),
            execution_key=cls._row_value(row, "execution_key"),
            attempt_count=cls._row_value(row, "attempt_count") or 0,
            max_attempts=max(cls._row_value(row, "max_attempts") or 1, 1),
            started_at=cls._parse_datetime(cls._row_value(row, "started_at")),
            finished_at=cls._parse_datetime(cls._row_value(row, "finished_at")),
            next_retry_at=cls._parse_datetime(cls._row_value(row, "next_retry_at")),
            dead_letter_reason=cls._row_value(row, "dead_letter_reason"),
            lease_owner=cls._row_value(row, "lease_owner"),
            lease_token=cls._row_value(row, "lease_token"),
            lease_expires_at=cls._parse_datetime(cls._row_value(row, "lease_expires_at")),
            last_heartbeat_at=cls._parse_datetime(cls._row_value(row, "last_heartbeat_at")),
        )

    @classmethod
    def _get_task_db(cls, task_id: str) -> Optional[Task]:
        with get_db() as conn:
            row = conn.execute(
                f"SELECT * FROM tasks WHERE task_id = {PH}",
                (task_id,),
            ).fetchone()
        if not row:
            return None
        return cls._row_to_task(row)

    @classmethod
    def _get_active_task_by_execution_key_db(cls, task_type: str, execution_key: str) -> Optional[Task]:
        with get_db() as conn:
            row = conn.execute(
                f"SELECT * FROM tasks "
                f"WHERE task_type = {PH} AND execution_key = {PH} "
                f"AND status IN ({PH}, {PH}) "
                f"ORDER BY created_at ASC LIMIT 1",
                (
                    task_type,
                    execution_key,
                    TaskStatus.PENDING.value,
                    TaskStatus.PROCESSING.value,
                ),
            ).fetchone()
        if not row:
            return None
        return cls._row_to_task(row)

    @classmethod
    def _list_tasks_db(cls, task_type: Optional[str] = None) -> list[Task]:
        sql = "SELECT * FROM tasks"
        params = []
        if task_type:
            sql += f" WHERE task_type = {PH}"
            params.append(task_type)
        sql += " ORDER BY created_at DESC"
        with get_db() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [cls._row_to_task(row) for row in rows]

    @classmethod
    def _delete_old_tasks_db(cls, cutoff_iso: str):
        with get_db() as conn:
            conn.execute(
                f"DELETE FROM tasks WHERE created_at < {PH} AND status IN ({PH}, {PH})",
                (cutoff_iso, TaskStatus.COMPLETED.value, TaskStatus.FAILED.value),
            )
    
    def create_task(
        self,
        task_type: str,
        metadata: Optional[Dict] = None,
        execution_key: Optional[str] = None,
        max_attempts: int = 1,
    ) -> str:
        """
        Create new task
        
        Args:
            task_type: Task type
            metadata: Additional metadata
            execution_key: Stable idempotency key for the underlying job
            max_attempts: Maximum execution attempts before dead-letter failure
            
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        now = datetime.now()
        
        task = Task(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
            execution_key=execution_key,
            max_attempts=max(int(max_attempts or 1), 1),
        )
        
        if not task:
            return None

        if self._writes_memory():
            self._store_memory_task(task)
        if self._writes_db():
            self._upsert_task_db(task)
        
        return task_id

    def create_or_reuse_task(
        self,
        task_type: str,
        metadata: Optional[Dict] = None,
        execution_key: Optional[str] = None,
        max_attempts: int = 1,
    ) -> tuple[Task, bool]:
        """Atomically create a new task or reuse an existing active task for the same execution key."""
        metadata = metadata or {}
        if not execution_key:
            task_id = self.create_task(
                task_type=task_type,
                metadata=metadata,
                execution_key=execution_key,
                max_attempts=max_attempts,
            )
            task = self.get_task(task_id)
            return task, True

        if not self._writes_db():
            with self._task_lock:
                for existing in self._tasks.values():
                    if (
                        existing.task_type == task_type
                        and existing.execution_key == execution_key
                        and existing.status in {TaskStatus.PENDING, TaskStatus.PROCESSING}
                    ):
                        return existing, False
                task = Task(
                    task_id=str(uuid.uuid4()),
                    task_type=task_type,
                    status=TaskStatus.PENDING,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    metadata=metadata,
                    execution_key=execution_key,
                    max_attempts=max(int(max_attempts or 1), 1),
                )
                self._tasks[task.task_id] = task
                return task, True

        for _ in range(2):
            task_id = str(uuid.uuid4())
            now = datetime.now()
            task = Task(
                task_id=task_id,
                task_type=task_type,
                status=TaskStatus.PENDING,
                created_at=now,
                updated_at=now,
                metadata=metadata,
                execution_key=execution_key,
                max_attempts=max(int(max_attempts or 1), 1),
            )
            try:
                links = self._extract_links(task.metadata)
                with get_db() as conn:
                    conn.execute(
                        f"INSERT INTO tasks ("
                        f"task_id, task_type, status, created_at, updated_at, progress, message, "
                        f"result_json, error, metadata_json, progress_detail_json, owner_id, project_id, "
                        f"simulation_id, report_id, graph_id, execution_key, attempt_count, max_attempts, "
                        f"started_at, finished_at, next_retry_at, dead_letter_reason, lease_owner, "
                        f"lease_token, lease_expires_at, last_heartbeat_at"
                        f") VALUES ({', '.join([PH] * 27)})",
                        (
                            task.task_id,
                            task.task_type,
                            task.status.value,
                            task.created_at.isoformat(),
                            task.updated_at.isoformat(),
                            task.progress,
                            task.message,
                            self._json_dumps(task.result, None),
                            task.error,
                            self._json_dumps(task.metadata, {}),
                            self._json_dumps(task.progress_detail, {}),
                            links["owner_id"],
                            links["project_id"],
                            links["simulation_id"],
                            links["report_id"],
                            links["graph_id"],
                            task.execution_key,
                            task.attempt_count,
                            task.max_attempts,
                            self._serialize_datetime(task.started_at),
                            self._serialize_datetime(task.finished_at),
                            self._serialize_datetime(task.next_retry_at),
                            task.dead_letter_reason,
                            task.lease_owner,
                            task.lease_token,
                            self._serialize_datetime(task.lease_expires_at),
                            self._serialize_datetime(task.last_heartbeat_at),
                        ),
                    )
                if self._writes_memory():
                    self._store_memory_task(task)
                return task, True
            except Exception as exc:
                if not self._is_unique_violation(exc):
                    raise
                existing = self._get_active_task_by_execution_key_db(task_type, execution_key)
                if existing:
                    if self._writes_memory():
                        self._store_memory_task(existing)
                    return existing, False

        raise RuntimeError(
            f"Unable to create or reuse task for execution_key={execution_key}"
        )
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task"""
        read_source = self._read_source()
        if read_source == "memory":
            with self._task_lock:
                return self._tasks.get(task_id)
        if read_source == "db":
            return self._get_task_db(task_id)

        task = self._get_task_db(task_id)
        if task:
            return task
        with self._task_lock:
            return self._tasks.get(task_id)
    
    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result: Optional[Dict] = None,
        error: Optional[str] = None,
        progress_detail: Optional[Dict] = None,
        lease_token: Optional[str] = None,
        refresh_lease: bool = False,
        lease_seconds: Optional[int] = None,
    ) -> bool:
        """
        Update task status
        
        Args:
            task_id: Task ID
            status: New status
            progress: Progress
            message: Message
            result: Result
            error: Error info
            progress_detail: Detailed progress info
        """
        task = self._get_task_db(task_id) if self._writes_db() else None
        if task is None and self._writes_memory():
            with self._task_lock:
                task = self._tasks.get(task_id)

        if not task:
            return False

        if lease_token is not None and task.lease_token != lease_token:
            logger.warning(
                "Rejected task update because lease token no longer matches: task_id=%s",
                task_id,
            )
            return False

        now = datetime.now()
        task.updated_at = now
        if status is not None:
            task.status = status
        if progress is not None:
            task.progress = progress
        if message is not None:
            task.message = message
        if result is not None:
            task.result = result
        if error is not None:
            task.error = error
        if progress_detail is not None:
            task.progress_detail = progress_detail
        if refresh_lease and lease_token:
            task.last_heartbeat_at = now
            task.lease_expires_at = now + timedelta(seconds=lease_seconds or self._lease_seconds())
        if self._is_terminal_status(task.status):
            if not task.finished_at:
                task.finished_at = now
            if task.status == TaskStatus.COMPLETED:
                task.error = None
                task.next_retry_at = None
                task.dead_letter_reason = None
            else:
                task.next_retry_at = None
            task.lease_owner = None
            task.lease_token = None
            task.lease_expires_at = None
            task.last_heartbeat_at = None

        if self._writes_db():
            self._upsert_task_db(task)
        if self._writes_memory():
            self._store_memory_task(task)
        return True
    
    def complete_task(self, task_id: str, result: Dict, lease_token: Optional[str] = None, message: str = "Task completed") -> bool:
        """Mark task as completed"""
        return self.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            message=message,
            result=result,
            lease_token=lease_token,
        )
    
    def fail_task(self, task_id: str, error: str, lease_token: Optional[str] = None, message: str = "Task failed") -> bool:
        """Mark task as failed"""
        return self.update_task(
            task_id,
            status=TaskStatus.FAILED,
            message=message,
            error=error,
            lease_token=lease_token,
        )

    @staticmethod
    def _retry_base_delay_seconds() -> int:
        return max(5, int(getattr(Config, "TASK_RETRY_BASE_DELAY_SECONDS", 15) or 15))

    @staticmethod
    def _retry_max_delay_seconds() -> int:
        return max(
            TaskManager._retry_base_delay_seconds(),
            int(getattr(Config, "TASK_RETRY_MAX_DELAY_SECONDS", 300) or 300),
        )

    @classmethod
    def _compute_retry_delay_seconds(cls, attempt_count: int) -> int:
        exponent = max(int(attempt_count or 1) - 1, 0)
        delay = cls._retry_base_delay_seconds() * (2 ** exponent)
        return min(delay, cls._retry_max_delay_seconds())

    def fail_or_retry_task(
        self,
        task_id: str,
        error: str,
        lease_token: Optional[str] = None,
        message: str = "Task failed",
        retryable: bool = False,
        dead_letter_reason: Optional[str] = None,
    ) -> str:
        """Fail a task terminally or reschedule it with exponential backoff."""
        task = self._get_task_db(task_id) if self._writes_db() else None
        if task is None and self._writes_memory():
            with self._task_lock:
                task = self._tasks.get(task_id)

        if not task:
            return "missing"

        if lease_token is not None and task.lease_token != lease_token:
            logger.warning(
                "Rejected fail_or_retry because lease token no longer matches: task_id=%s",
                task_id,
            )
            return "lease_rejected"

        now = datetime.now()
        if retryable and (task.attempt_count or 0) < max(task.max_attempts or 1, 1):
            retry_delay_seconds = self._compute_retry_delay_seconds(task.attempt_count or 1)
            task.status = TaskStatus.PENDING
            task.updated_at = now
            task.message = message or f"Retrying after transient failure in {retry_delay_seconds}s"
            task.error = error
            task.next_retry_at = now + timedelta(seconds=retry_delay_seconds)
            task.dead_letter_reason = None
            task.finished_at = None
            task.lease_owner = None
            task.lease_token = None
            task.lease_expires_at = None
            task.last_heartbeat_at = None
            if self._writes_db():
                self._upsert_task_db(task)
            if self._writes_memory():
                self._store_memory_task(task)
            logger.warning(
                "Scheduled task retry: task_id=%s attempt=%s/%s retry_at=%s",
                task_id,
                task.attempt_count,
                task.max_attempts,
                task.next_retry_at.isoformat() if task.next_retry_at else None,
            )
            return "retry_scheduled"

        task.status = TaskStatus.FAILED
        task.updated_at = now
        task.message = message
        task.error = error
        task.dead_letter_reason = dead_letter_reason or "max_attempts_exhausted"
        task.next_retry_at = None
        if not task.finished_at:
            task.finished_at = now
        task.lease_owner = None
        task.lease_token = None
        task.lease_expires_at = None
        task.last_heartbeat_at = None
        if self._writes_db():
            self._upsert_task_db(task)
        if self._writes_memory():
            self._store_memory_task(task)
        return "failed"

    def find_active_task(
        self,
        task_type: str,
        execution_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Task]:
        """Find the newest non-terminal task for a job key or linked resources."""
        candidates = self.list_tasks(
            task_type=task_type,
            predicate=lambda task: task.status in {TaskStatus.PENDING, TaskStatus.PROCESSING},
        )
        for task in candidates:
            if execution_key and task.execution_key != execution_key:
                continue
            if self._matches_links(task, metadata):
                return task
        return None

    def claim_task(
        self,
        task_id: str,
        worker_id: Optional[str] = None,
        lease_seconds: Optional[int] = None,
    ) -> Optional[TaskLease]:
        """Claim a task for exclusive execution."""
        lease_seconds = max(30, int(lease_seconds or self._lease_seconds()))
        worker_id = worker_id or self.default_worker_id()
        now = datetime.now()
        lease_token = uuid.uuid4().hex
        lease_expires_at = now + timedelta(seconds=lease_seconds)

        if self._writes_db():
            with get_db() as conn:
                cursor = conn.execute(
                    f"UPDATE tasks SET "
                    f"status = {PH}, "
                    f"updated_at = {PH}, "
                    f"started_at = COALESCE(started_at, {PH}), "
                    f"attempt_count = COALESCE(attempt_count, 0) + 1, "
                    f"lease_owner = {PH}, "
                    f"lease_token = {PH}, "
                    f"lease_expires_at = {PH}, "
                    f"last_heartbeat_at = {PH} "
                    f"WHERE task_id = {PH} "
                    f"AND status IN ({PH}, {PH}) "
                    f"AND (lease_expires_at IS NULL OR lease_expires_at <= {PH}) "
                    f"AND (next_retry_at IS NULL OR next_retry_at <= {PH})",
                    (
                        TaskStatus.PROCESSING.value,
                        now.isoformat(),
                        now.isoformat(),
                        worker_id,
                        lease_token,
                        lease_expires_at.isoformat(),
                        now.isoformat(),
                        task_id,
                        TaskStatus.PENDING.value,
                        TaskStatus.PROCESSING.value,
                        now.isoformat(),
                        now.isoformat(),
                    ),
                )
                if getattr(cursor, "rowcount", 0) <= 0:
                    return None
            task = self._get_task_db(task_id)
        else:
            with self._task_lock:
                task = self._tasks.get(task_id)
                if not task:
                    return None
                lease_expired = not task.lease_expires_at or task.lease_expires_at <= now
                retry_ready = not task.next_retry_at or task.next_retry_at <= now
                if task.status not in {TaskStatus.PENDING, TaskStatus.PROCESSING} or not lease_expired or not retry_ready:
                    return None
                task.status = TaskStatus.PROCESSING
                task.updated_at = now
                task.started_at = task.started_at or now
                task.attempt_count = (task.attempt_count or 0) + 1
                task.next_retry_at = None
                task.dead_letter_reason = None
                task.lease_owner = worker_id
                task.lease_token = lease_token
                task.lease_expires_at = lease_expires_at
                task.last_heartbeat_at = now
                self._tasks[task.task_id] = task

        if self._writes_memory():
            self._store_memory_task(task)

        return TaskLease(
            task_id=task.task_id,
            lease_token=task.lease_token,
            worker_id=worker_id,
            lease_expires_at=task.lease_expires_at,
            heartbeat_interval_seconds=self._heartbeat_interval_seconds(),
            lease_seconds=lease_seconds,
        )

    def refresh_task_lease(self, task_id: str, lease_token: str, lease_seconds: Optional[int] = None) -> bool:
        """Extend a claimed task lease."""
        return self.update_task(
            task_id,
            lease_token=lease_token,
            refresh_lease=True,
            lease_seconds=lease_seconds,
        )

    def claim_next_task(
        self,
        task_types: Optional[list[str]] = None,
        worker_id: Optional[str] = None,
        batch_size: int = 10,
        lease_seconds: Optional[int] = None,
    ) -> Optional[TaskLease]:
        """Claim the next available task directly from persistent storage."""
        if not self._writes_db():
            candidates = self.list_tasks(
                predicate=lambda task: task.status in {TaskStatus.PENDING, TaskStatus.PROCESSING}
                and (not task.next_retry_at or task.next_retry_at <= datetime.now())
                and (not task_types or task.task_type in task_types),
            )[:batch_size]
            for task in candidates:
                lease = self.claim_task(task.task_id, worker_id=worker_id, lease_seconds=lease_seconds)
                if lease:
                    return lease
            return None

        now_iso = datetime.now().isoformat()
        params: list[Any] = [
            TaskStatus.PENDING.value,
            TaskStatus.PROCESSING.value,
            now_iso,
            now_iso,
        ]
        sql = (
            "SELECT task_id FROM tasks "
            f"WHERE status IN ({PH}, {PH}) "
            f"AND (lease_expires_at IS NULL OR lease_expires_at <= {PH}) "
            f"AND (next_retry_at IS NULL OR next_retry_at <= {PH})"
        )
        if task_types:
            placeholders = ", ".join([PH] * len(task_types))
            sql += f" AND task_type IN ({placeholders})"
            params.extend(task_types)
        sql += " ORDER BY created_at ASC"
        sql += f" LIMIT {max(batch_size, 1)}"

        with get_db() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()

        candidate_ids = [self._row_value(row, "task_id") for row in rows][: max(batch_size, 1)]
        for task_id in candidate_ids:
            if not task_id:
                continue
            lease = self.claim_task(task_id, worker_id=worker_id, lease_seconds=lease_seconds)
            if lease:
                return lease
        return None
    
    def list_tasks(
        self,
        task_type: Optional[str] = None,
        predicate: Optional[Callable[[Task], bool]] = None,
    ) -> list[Task]:
        """List tasks"""
        with self._task_lock:
            tasks = list(self._tasks.values())
        memory_tasks = tasks
        db_tasks = []
        read_source = self._read_source()
        if read_source in {"db", "fallback"}:
            db_tasks = self._list_tasks_db(task_type=task_type)
        elif task_type:
            memory_tasks = [t for t in memory_tasks if t.task_type == task_type]

        if read_source == "memory":
            tasks = memory_tasks
        elif read_source == "db":
            tasks = db_tasks
        else:
            merged = {task.task_id: task for task in db_tasks}
            for task in memory_tasks:
                merged.setdefault(task.task_id, task)
            tasks = list(merged.values())

        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]
        if predicate:
            tasks = [t for t in tasks if predicate(t)]
        return sorted(tasks, key=lambda x: x.created_at, reverse=True)
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Clean up old tasks"""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        if self._writes_memory():
            with self._task_lock:
                old_ids = [
                    tid for tid, task in self._tasks.items()
                    if task.created_at < cutoff and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
                ]
                for tid in old_ids:
                    del self._tasks[tid]
        if self._writes_db():
            self._delete_old_tasks_db(cutoff.isoformat())

    @classmethod
    def start_reaper(cls, interval_seconds: int = 60, grace_seconds: Optional[int] = None):
        """Start a lightweight background reaper for expired or abandoned tasks."""
        with cls._reaper_lock:
            if cls._reaper_thread and cls._reaper_thread.is_alive():
                return

            cls._reaper_stop_event.clear()
            reaper_grace = max(grace_seconds or cls._lease_seconds(), 30)

            def _reap():
                while not cls._reaper_stop_event.wait(interval_seconds):
                    try:
                        cls().recover_interrupted_tasks(grace_seconds=reaper_grace)
                    except Exception as exc:
                        logger.warning("Task reaper iteration failed: %s", exc)

            cls._reaper_thread = threading.Thread(
                target=_reap,
                name="task-reaper",
                daemon=True,
            )
            cls._reaper_thread.start()

    def recover_interrupted_tasks(self, grace_seconds: int = 30) -> Dict[str, int]:
        """
        Reconcile stale in-flight tasks after a process restart.

        This is intentionally conservative for in-flight work: queued pending tasks
        are left alone, while stale processing tasks are reconciled to terminal states.
        """
        from ..models.project import ProjectManager, ProjectStatus
        from ..services.simulation_manager import SimulationManager, SimulationStatus
        from ..services.report_agent import ReportManager, ReportStatus
        from ..models.user import (
            find_pending_report_generation_reservation,
            finalize_report_generation_reservation,
            release_report_generation_reservation,
        )

        if not self._writes_db() and self._read_source() == "memory":
            return {"scanned": 0, "failed": 0, "completed": 0, "released": 0, "finalized": 0}

        cutoff = datetime.now() - timedelta(seconds=max(grace_seconds, 0))
        summary = {"scanned": 0, "failed": 0, "completed": 0, "released": 0, "finalized": 0}
        simulation_manager = SimulationManager()
        interrupted_message = "Interrupted by server restart. Please retry."

        for task in self._list_tasks_db():
            if task.status != TaskStatus.PROCESSING:
                continue
            lease_expired = task.lease_expires_at and task.lease_expires_at <= datetime.now()
            if not lease_expired and task.updated_at > cutoff:
                continue

            summary["scanned"] += 1
            metadata = task.metadata or {}
            task_type = task.task_type

            if task_type == "graph_build":
                project_id = metadata.get("project_id")
                project = ProjectManager.get_project(project_id) if project_id else ProjectManager.find_project_by_graph_build_task_id(task.task_id)
                if project and project.status == ProjectStatus.GRAPH_COMPLETED and project.graph_id:
                    self.update_task(
                        task.task_id,
                        status=TaskStatus.COMPLETED,
                        progress=100,
                        message="Recovered completed graph build after restart",
                        result={
                            "project_id": project.project_id,
                            "graph_id": project.graph_id,
                            "recovered": True,
                        },
                    )
                    summary["completed"] += 1
                    continue

                if project:
                    project.status = ProjectStatus.FAILED
                    project.error = interrupted_message
                    project.graph_build_task_id = None
                    if project.status != ProjectStatus.GRAPH_COMPLETED:
                        project.graph_id = None
                    ProjectManager.save_project(project)

                self.update_task(
                    task.task_id,
                    status=TaskStatus.FAILED,
                    message=interrupted_message,
                    error=interrupted_message,
                )
                summary["failed"] += 1
                continue

            if task_type == "simulation_prepare":
                simulation_id = metadata.get("simulation_id")
                state = simulation_manager.get_simulation(simulation_id) if simulation_id else None

                if state and state.status == SimulationStatus.READY and state.config_generated:
                    self.update_task(
                        task.task_id,
                        status=TaskStatus.COMPLETED,
                        progress=100,
                        message="Recovered completed simulation preparation after restart",
                        result=state.to_simple_dict(),
                    )
                    summary["completed"] += 1
                    continue

                if state and state.status in {SimulationStatus.PREPARING, SimulationStatus.CREATED, SimulationStatus.RUNNING}:
                    state.status = SimulationStatus.FAILED
                    state.error = interrupted_message
                    simulation_manager._save_simulation_state(state)

                self.update_task(
                    task.task_id,
                    status=TaskStatus.FAILED,
                    message=interrupted_message,
                    error=interrupted_message,
                )
                summary["failed"] += 1
                continue

            if task_type == "report_generate":
                report_id = metadata.get("report_id")
                simulation_id = metadata.get("simulation_id")
                owner_id = metadata.get("owner_id")
                report = ReportManager.get_report(report_id) if report_id else None
                if not report and simulation_id:
                    report = ReportManager.get_report_by_simulation(simulation_id)

                reservation_id = None
                if owner_id:
                    reservation_id = find_pending_report_generation_reservation(
                        owner_id,
                        report_id=report_id,
                        simulation_id=simulation_id,
                    )

                if report and report.status == ReportStatus.COMPLETED:
                    if owner_id and reservation_id:
                        finalized = finalize_report_generation_reservation(
                            reservation_id,
                            owner_id,
                            usage=report.usage or {},
                            report_id=report.report_id,
                            simulation_id=report.simulation_id,
                            model="recovered_after_restart",
                        )
                        if finalized:
                            summary["finalized"] += 1

                    self.update_task(
                        task.task_id,
                        status=TaskStatus.COMPLETED,
                        progress=100,
                        message="Recovered completed report generation after restart",
                        result={
                            "report_id": report.report_id,
                            "simulation_id": report.simulation_id,
                            "recovered": True,
                        },
                    )
                    summary["completed"] += 1
                    continue

                if report:
                    report.status = ReportStatus.FAILED
                    report.error = interrupted_message
                    ReportManager.save_report(report)
                    ReportManager.update_progress(
                        report.report_id,
                        "failed",
                        -1,
                        interrupted_message,
                        completed_sections=ReportManager.get_progress(report.report_id).get("completed_sections", []) if ReportManager.get_progress(report.report_id) else [],
                    )

                if owner_id and reservation_id:
                    refunded = release_report_generation_reservation(reservation_id, owner_id)
                    if refunded >= 0:
                        summary["released"] += 1

                self.update_task(
                    task.task_id,
                    status=TaskStatus.FAILED,
                    message=interrupted_message,
                    error=interrupted_message,
                )
                summary["failed"] += 1

        if summary["scanned"]:
            logger.info("Recovered interrupted tasks on startup: %s", summary)
        return summary
