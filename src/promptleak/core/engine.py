"""Main extraction orchestrator - runs techniques and aggregates results."""
import asyncio
import logging
from datetime import datetime
from urllib.parse import urlparse

from .config import ExtractionConfig
from .browser import BrowserManager
from .cache import get_cached, set_cached
from ..targets.registry import detect_target
from ..targets.base import Target
from ..techniques.base import TechniqueResult
from ..techniques.direct_ask import DirectAskTechnique
from ..techniques.role_confusion import RoleConfusionTechnique
from ..techniques.translation_leak import TranslationLeakTechnique
from ..techniques.continuation_leak import ContinuationLeakTechnique
from ..techniques.encoding_trick import EncodingTrickTechnique
from ..techniques.token_analysis import TokenAnalysisTechnique
from ..techniques.api_probe import APIProbeTechnique
from ..output.formatter import clean_extraction, score_confidence, deduplicate, consensus_boost
from .. import __version__

logger = logging.getLogger("promptleak")

TECHNIQUE_MAP: dict[str, type] = {
    "api_probe": APIProbeTechnique,
    "direct_ask": DirectAskTechnique,
    "role_confusion": RoleConfusionTechnique,
    "translation_leak": TranslationLeakTechnique,
    "continuation_leak": ContinuationLeakTechnique,
    "encoding_trick": EncodingTrickTechnique,
    "token_analysis": TokenAnalysisTechnique,
}

ALL_TECHNIQUES = list(TECHNIQUE_MAP.keys())


class ExtractionReport:
    def __init__(
        self,
        url: str,
        domain: str,
        target_name: str,
        techniques_used: list[str],
        results: list[TechniqueResult],
        best_result: str,
        confidence: float,
        timestamp: str,
        version: str,
        metadata: dict = None,
    ):
        self.url = url
        self.domain = domain
        self.target_name = target_name
        self.techniques_used = techniques_used
        self.results = results
        self.best_result = best_result
        self.confidence = confidence
        self.timestamp = timestamp
        self.version = version
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "domain": self.domain,
            "target_name": self.target_name,
            "techniques_used": self.techniques_used,
            "confidence": self.confidence,
            "best_result": self.best_result,
            "timestamp": self.timestamp,
            "version": self.version,
            "metadata": self.metadata,
            "results": [
                {
                    "technique_name": r.technique_name,
                    "success": r.success,
                    "raw_output": r.raw_output,
                    "cleaned_output": r.cleaned_output,
                    "confidence": r.confidence,
                    "error": r.error,
                    "metadata": r.metadata,
                }
                for r in self.results
            ],
        }


class ExtractionEngine:
    def __init__(self, config: ExtractionConfig):
        self.config = config
        self.target: Target = None

    async def run(self) -> ExtractionReport:
        url = self.config.url
        domain = urlparse(url).netloc
        self.target = detect_target(url)
        logger.info(f"Target detected: {self.target.name} for {url}")

        technique_names = self.config.techniques or ALL_TECHNIQUES
        techniques = [TECHNIQUE_MAP[n] for n in technique_names if n in TECHNIQUE_MAP]

        if not techniques:
            logger.error(f"No valid techniques specified. Available: {', '.join(ALL_TECHNIQUES)}")
            techniques = [DirectAskTechnique]

        results: list[TechniqueResult] = []

        async with BrowserManager(
            headed=self.config.headed,
            proxy=self.config.proxy,
            screenshot_dir=self.config.screenshot_path,
        ) as browser_mgr:
            # Check for about-panel captured text (only for targets that support it)
            about_panel_func = getattr(self.target, "get_captured_about_text", None)
            if about_panel_func:
                probe_page = await browser_mgr.new_page()
                try:
                    await probe_page.goto(url, wait_until="load", timeout=120000)
                except Exception:
                    pass
                await asyncio.sleep(2)
                await self.target.pre_navigation_hook(probe_page)
                captured = about_panel_func()
                if captured:
                    c_conf = score_confidence(captured)
                    if c_conf < 0.6:
                        c_conf = max(0.6, c_conf)
                    logger.info(f"Captured about-panel text ({len(captured)} chars, conf={c_conf:.2f})")
                    results.append(TechniqueResult(
                        technique_name="about_panel",
                        success=True,
                        raw_output=captured,
                        cleaned_output=captured,
                        confidence=c_conf,
                        metadata={"source": "about_panel"},
                    ))
                await browser_mgr.close_page(probe_page)

            for technique_cls in techniques:
                technique = technique_cls()

                if not self.config.no_cache:
                    cached = get_cached(self.target.name, technique.name)
                    if cached:
                        logger.info(f"Using cached result for {technique.name}")
                        results.append(TechniqueResult(
                            technique_name=technique.name,
                            success=True,
                            raw_output=cached,
                            cleaned_output=cached,
                            confidence=0.5,
                            metadata={"cached": True},
                        ))
                        continue

                logger.info(f"Running technique: {technique.name}")
                try:
                    page = await browser_mgr.new_page()
                    try:
                        await page.goto(url, wait_until="load", timeout=120000)
                    except Exception:
                        pass
                    await asyncio.sleep(2)

                    await self.target.pre_navigation_hook(page)

                    if not await self.target.is_logged_in(page):
                        logger.warning(f"Login may be required for {url}")

                    result = await asyncio.wait_for(
                        technique.execute(page, self.target),
                        timeout=self.config.timeout,
                    )

                    cleaned = clean_extraction(result.raw_output, technique.last_prompt)
                    result.cleaned_output = cleaned

                    if result.confidence < 0.6:
                        result.confidence = score_confidence(cleaned)

                    set_cached(self.target.name, technique.name, result.raw_output, result.confidence)

                    results.append(result)

                    if self.config.screenshot_path:
                        await browser_mgr.take_screenshot(page, technique.name)

                    await browser_mgr.close_page(page)

                except asyncio.TimeoutError:
                    logger.error(f"Technique {technique.name} timed out")
                    results.append(TechniqueResult(
                        technique_name=technique.name,
                        success=False,
                        raw_output="",
                        cleaned_output="",
                        confidence=0.0,
                        error="Timeout",
                    ))
                except Exception as e:
                    logger.error(f"Technique {technique.name} failed: {e}")
                    results.append(TechniqueResult(
                        technique_name=technique.name,
                        success=False,
                        raw_output="",
                        cleaned_output="",
                        confidence=0.0,
                        error=str(e),
                    ))

        cleaned_results = [
            (r.cleaned_output, r.technique_name, r.confidence)
            for r in results if r.success and r.cleaned_output
        ]

        if cleaned_results:
            deduped = deduplicate(cleaned_results)
            boosts = consensus_boost(deduped)

            scored = []
            for text, source, conf in deduped:
                final_conf = min(1.0, conf + boosts.get(source, 0))
                scored.append((text, source, final_conf))

            scored.sort(key=lambda x: x[2], reverse=True)
            best_text, best_source, best_conf = scored[0]

            final_confidence = max(r.confidence for r in results) if results else 0.0
            if best_conf > final_confidence:
                final_confidence = best_conf
        else:
            best_text = ""
            final_confidence = 0.0

        report = ExtractionReport(
            url=url,
            domain=domain,
            target_name=self.target.name,
            techniques_used=[r.technique_name for r in results],
            results=results,
            best_result=best_text,
            confidence=final_confidence,
            timestamp=datetime.utcnow().isoformat(),
            version=__version__,
        )

        logger.info(f"Extraction complete. Best confidence: {final_confidence:.2f}")
        return report
