"""Real-time monitor mode — continuously monitors targets for prompt changes."""
import asyncio
import difflib
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .config import ExtractionConfig
from .engine import ExtractionEngine
from .notifications import NotificationManager

logger = logging.getLogger("promptleak")


@dataclass
class MonitorTarget:
    url: str
    interval_seconds: int = 300
    last_prompt_text: str = ""
    last_prompt_hash: str = ""
    change_count: int = 0
    last_scan: float = 0.0
    scanning: bool = False
    notify_channels: list = field(default_factory=list)
    webhook_url: str = ""


class RealtimeMonitor:
    """Continuously monitors targets and alerts on prompt changes."""

    def __init__(self, notifier: Optional[NotificationManager] = None):
        self.targets: list[MonitorTarget] = []
        self.notifier = notifier
        self.running = True

    def add_target(self, url: str, interval_seconds: int = 300,
                   notify_channels: list = None, webhook_url: str = ""):
        self.targets.append(MonitorTarget(
            url=url,
            interval_seconds=interval_seconds,
            notify_channels=notify_channels or [],
            webhook_url=webhook_url,
        ))

    def load_from_file(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                parts = stripped.split()
                url = parts[0]
                interval = int(parts[1]) if len(parts) > 1 else 300
                self.add_target(url, interval)

    async def start(self):
        if not self.targets:
            logger.warning("No targets to monitor")
            return

        print(f"\nMonitoring {len(self.targets)} targets...")
        for t in self.targets:
            print(f"  Target: {t.url} (interval: {t.interval_seconds}s)")
            asyncio.create_task(self._monitor_loop(t))

        while self.running:
            await asyncio.sleep(1)

    async def stop(self):
        self.running = False

    async def _monitor_loop(self, target: MonitorTarget):
        while self.running:
            now = time.time()
            if now - target.last_scan < target.interval_seconds:
                await asyncio.sleep(5)
                continue
            if target.scanning:
                await asyncio.sleep(5)
                continue
            target.scanning = True
            await self._scan_target(target)
            target.last_scan = time.time()
            target.scanning = False
            await asyncio.sleep(target.interval_seconds)

    async def _scan_target(self, target: MonitorTarget):
        try:
            print(f"  Scanning: {target.url}")
            config = ExtractionConfig(url=target.url, techniques=["direct_ask", "translation_leak", "encoding_trick"], timeout=60, verbose=False)
            engine = ExtractionEngine(config)
            report = await engine.run()

            current_hash = hashlib.sha256(report.best_result.encode()).hexdigest() if report.best_result else ""

            if not target.last_prompt_hash:
                target.last_prompt_hash = current_hash
                target.last_prompt_text = report.best_result
                print(f"  Baseline established: {target.url} (hash: {current_hash[:12]}...)")
                return

            if current_hash != target.last_prompt_hash:
                target.change_count += 1
                similarity = difflib.SequenceMatcher(None, target.last_prompt_text, report.best_result).ratio()

                change = {
                    "url": target.url,
                    "timestamp": datetime.now().isoformat(),
                    "old_hash": target.last_prompt_hash[:12],
                    "new_hash": current_hash[:12],
                    "similarity": round(similarity, 3),
                    "change_number": target.change_count,
                    "old_prompt": target.last_prompt_text[:500],
                    "new_prompt": report.best_result[:500],
                    "confidence": report.confidence,
                    "technique": report.techniques_used[0] if report.techniques_used else "unknown",
                }

                differ = list(difflib.unified_diff(
                    target.last_prompt_text.splitlines(keepends=True),
                    report.best_result.splitlines(keepends=True),
                    fromfile="old", tofile="new",
                ))
                change["diff"] = "".join(differ)[:2000]

                await self._alert(target, change)

                target.last_prompt_hash = current_hash
                target.last_prompt_text = report.best_result

            target.last_scan = time.time()

        except Exception as e:
            print(f"  Error scanning {target.url}: {e}")
        finally:
            target.scanning = False

    async def _alert(self, target: MonitorTarget, change: dict):
        print(f"\n{'='*60}")
        print(f"PROMPT CHANGE DETECTED #{change['change_number']}")
        print(f"   Target: {target.url}")
        print(f"   Time:   {change['timestamp']}")
        print(f"   Similarity: {change['similarity']:.1%}")
        if change["similarity"] < 0.5:
            print(f"   Type:   MAJOR REWRITE")
        elif change["similarity"] < 0.8:
            print(f"   Type:   MODIFICATION")
        else:
            print(f"   Type:   MINOR TWEAK")
        print(f"   Diff preview:")
        for line in change["diff"].split("\n")[:10]:
            if line.startswith("+"):
                print(f"   + {line[1:]}")
            elif line.startswith("-"):
                print(f"   - {line[1:]}")
            else:
                print(f"   {line}")
        print(f"{'='*60}\n")

        if self.notifier:
            for channel in target.notify_channels:
                try:
                    if channel.startswith("discord:"):
                        webhook = channel.split(":", 1)[1]
                        await self.notifier.send_discord(webhook,
                            f"PROMPT CHANGE DETECTED on {target.url}\nSimilarity: {change['similarity']:.1%}\nChange #{change['change_number']}")
                    elif channel.startswith("telegram:"):
                        parts = channel.split(":")
                        await self.notifier.send_telegram(parts[1], parts[2],
                            f"PROMPT CHANGE DETECTED on {target.url}\nSimilarity: {change['similarity']:.1%}\nChange #{change['change_number']}")
                    elif channel.startswith("slack:"):
                        webhook = channel.split(":", 1)[1]
                        await self.notifier.send_slack(webhook,
                            f"PROMPT CHANGE DETECTED on {target.url} (similarity: {change['similarity']:.1%})")
                except Exception as e:
                    logger.warning(f"Notification failed for {channel}: {e}")
