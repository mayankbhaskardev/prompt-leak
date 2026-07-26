"""Grid worker node - receives tasks from the master, runs extractions, reports back."""
import asyncio
import json
import logging
import os
import platform
import socket
import time
import uuid
from typing import Optional

logger = logging.getLogger("promptleak.grid")


class GridWorker:
    """Worker node that receives and executes extraction tasks from the grid master."""

    def __init__(self, master_url: str = "redis://localhost:6379/0", worker_id: str = "", version: str = "4.0.0"):
        self.master_url = master_url
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:6]}"
        self.version = version
        self.hostname = platform.node() or socket.gethostname()
        self.running = False
        self.current_task: Optional[dict] = None
        self.tasks_completed = 0
        self.redis = None
        self._connect_redis()

    def _connect_redis(self):
        try:
            import redis.asyncio as redis_async
            self.redis = redis_async.from_url(self.master_url, decode_responses=True)
            logger.info(f"Worker {self.worker_id} connected to Redis at {self.master_url}")
        except ImportError:
            logger.warning("redis-py not installed - grid mode requires 'pip install prompt-leak[grid]'")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")

    async def _send_heartbeat(self):
        if not self.redis:
            return
        try:
            await self.redis.publish("grid:heartbeat", json.dumps({
                "worker_id": self.worker_id,
                "hostname": self.hostname,
                "status": "busy" if self.current_task else "idle",
                "current_task": self.current_task["task_id"] if self.current_task else "",
                "version": self.version,
                "timestamp": time.time(),
            }))
        except Exception as e:
            logger.debug(f"Heartbeat failed: {e}")

    async def _listen_for_dispatch(self):
        if not self.redis:
            return
        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe("grid:dispatch")
            async for message in pubsub.listen():
                if not self.running:
                    break
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                    if data.get("worker_id") == self.worker_id:
                        asyncio.create_task(self._execute_task(data))
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logger.warning(f"Dispatch listener error: {e}")

    async def _execute_task(self, task_data: dict):
        self.current_task = task_data
        task_id = task_data["task_id"]
        url = task_data["url"]
        technique = task_data["technique"]
        logger.info(f"Executing task {task_id}: {technique} on {url}")

        try:
            from ..core.config import ExtractionConfig
            from ..core.engine import ExtractionEngine

            config = ExtractionConfig(
                url=url,
                techniques=[technique],
                timeout=180,
                verbose=False,
            )
            engine = ExtractionEngine(config)
            report = await engine.run()

            result = {
                "best_result": report.best_result,
                "confidence": report.confidence,
                "techniques_used": report.techniques_used,
                "target_name": report.target_name,
                "domain": report.domain,
                "timestamp": report.timestamp,
            }

            if self.redis:
                await self.redis.publish("grid:complete", json.dumps({
                    "worker_id": self.worker_id,
                    "task_id": task_id,
                    "result": result,
                    "error": "",
                }))

            self.tasks_completed += 1
            logger.info(f"Task {task_id} completed (confidence: {report.confidence:.2f})")

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            if self.redis:
                await self.redis.publish("grid:complete", json.dumps({
                    "worker_id": self.worker_id,
                    "task_id": task_id,
                    "result": {},
                    "error": str(e),
                }))

        self.current_task = None

    async def start(self):
        self.running = True
        logger.info(f"Grid worker {self.worker_id} started ({self.hostname})")
        asyncio.create_task(self._listen_for_dispatch())
        while self.running:
            await self._send_heartbeat()
            await asyncio.sleep(10)

    async def stop(self):
        self.running = False
        logger.info(f"Grid worker {self.worker_id} stopped")
