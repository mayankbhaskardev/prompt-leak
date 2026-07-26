"""Distributed grid orchestrator - master node that coordinates workers across machines."""
import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("promptleak.grid")


@dataclass
class GridTask:
    id: str
    url: str
    technique: str
    status: str = "pending"
    worker_id: str = ""
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    result: dict = field(default_factory=dict)
    error: str = ""
    retries: int = 0
    max_retries: int = 3
    priority: int = 0


@dataclass
class GridWorker:
    id: str
    hostname: str
    last_heartbeat: float = 0.0
    status: str = "idle"
    current_task: str = ""
    tasks_completed: int = 0
    version: str = ""


class GridMaster:
    """Master node for distributed prompt extraction grid."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0", max_workers: int = 10):
        self.redis_url = redis_url
        self.max_workers = max_workers
        self.workers: dict[str, GridWorker] = {}
        self.tasks: dict[str, GridTask] = {}
        self.running = False
        self.redis = None
        self._connect_redis()

    def _connect_redis(self):
        try:
            import redis.asyncio as redis_async
            self.redis = redis_async.from_url(self.redis_url, decode_responses=True)
            logger.info(f"Connected to Redis at {self.redis_url}")
        except ImportError:
            logger.warning("redis-py not installed - grid mode requires 'pip install prompt-leak[grid]'")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")

    async def submit_task(self, url: str, technique: str, priority: int = 0) -> str:
        task_id = str(uuid.uuid4())[:8]
        task = GridTask(
            id=task_id,
            url=url,
            technique=technique,
            created_at=time.time(),
            priority=priority,
        )
        self.tasks[task_id] = task
        if self.redis:
            await self.redis.lpush("grid:tasks:pending", json.dumps({
                "id": task_id, "url": url, "technique": technique,
                "priority": priority, "created_at": task.created_at,
            }))
        logger.info(f"Task {task_id} submitted: {technique} on {url}")
        return task_id

    async def get_task_result(self, task_id: str, timeout: float = 300) -> Optional[dict]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            task = self.tasks.get(task_id)
            if task and task.status in ("completed", "failed"):
                return {"id": task.id, "status": task.status, "result": task.result, "error": task.error}
            await asyncio.sleep(1)
        return None

    async def process_heartbeat(self, worker_id: str, hostname: str, status: str, current_task: str = "", version: str = ""):
        if worker_id not in self.workers:
            self.workers[worker_id] = GridWorker(id=worker_id, hostname=hostname, version=version)
            logger.info(f"Worker {worker_id} registered ({hostname}) v{version}")
        worker = self.workers[worker_id]
        worker.last_heartbeat = time.time()
        worker.status = status
        worker.current_task = current_task
        if status == "idle" and not current_task:
            await self._dispatch_to_worker(worker_id)

    async def _dispatch_to_worker(self, worker_id: str):
        pending = sorted(
            [t for t in self.tasks.values() if t.status == "pending"],
            key=lambda x: (-x.priority, x.created_at),
        )
        if not pending:
            return
        task = pending[0]
        task.status = "assigned"
        task.worker_id = worker_id
        task.started_at = time.time()
        if self.redis:
            await self.redis.publish("grid:dispatch", json.dumps({
                "worker_id": worker_id, "task_id": task.id,
                "url": task.url, "technique": task.technique,
            }))
        logger.info(f"Dispatched task {task.id} to worker {worker_id}")

    async def complete_task(self, worker_id: str, task_id: str, result: dict, error: str = ""):
        task = self.tasks.get(task_id)
        if not task:
            logger.warning(f"Unknown task {task_id} completed by {worker_id}")
            return
        task.completed_at = time.time()
        if error:
            task.status = "failed"
            task.error = error
            task.retries += 1
            if task.retries < task.max_retries:
                task.status = "pending"
                task.worker_id = ""
                logger.info(f"Task {task_id} will be retried ({task.retries}/{task.max_retries})")
        else:
            task.status = "completed"
            task.result = result
            logger.info(f"Task {task_id} completed by {worker_id}")
        if worker_id in self.workers:
            self.workers[worker_id].tasks_completed += 1
            self.workers[worker_id].current_task = ""
            self.workers[worker_id].status = "idle"

    async def start(self):
        self.running = True
        logger.info(f"Grid master started (max workers: {self.max_workers})")
        while self.running:
            await asyncio.sleep(5)
            await self._prune_stale_workers()
            await self._retry_stale_tasks()

    async def stop(self):
        self.running = False

    async def _prune_stale_workers(self, timeout: float = 30):
        now = time.time()
        stale = [wid for wid, w in self.workers.items() if now - w.last_heartbeat > timeout]
        for wid in stale:
            worker = self.workers.pop(wid, None)
            if worker and worker.current_task:
                task = self.tasks.get(worker.current_task)
                if task and task.status == "assigned":
                    task.status = "pending"
                    task.worker_id = ""
                    logger.info(f"Task {task.id} unassigned from stale worker {wid}")
            logger.info(f"Pruned stale worker {wid}")

    async def _retry_stale_tasks(self, timeout: float = 120):
        now = time.time()
        for task in self.tasks.values():
            if task.status == "assigned" and task.started_at > 0 and now - task.started_at > timeout:
                task.status = "pending"
                task.worker_id = ""
                logger.info(f"Task {task.id} re-queued (stale assignment)")

    def get_status(self) -> dict:
        status_counts = {"pending": 0, "assigned": 0, "completed": 0, "failed": 0}
        for t in self.tasks.values():
            status_counts[t.status] = status_counts.get(t.status, 0) + 1
        return {
            "workers": len(self.workers),
            "total_tasks": len(self.tasks),
            "status_counts": status_counts,
            "max_workers": self.max_workers,
            "running": self.running,
        }

    def get_leaderboard(self) -> list[dict]:
        return sorted(
            [{"id": w.id, "hostname": w.hostname, "tasks_completed": w.tasks_completed, "status": w.status}
             for w in self.workers.values()],
            key=lambda x: -x["tasks_completed"],
        )
