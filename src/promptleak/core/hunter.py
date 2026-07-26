"""Hunter mode - auto-discovers AI chat targets via DuckDuckGo search dorks."""
import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, unquote

import aiohttp
from bs4 import BeautifulSoup

from .config import ExtractionConfig
from .engine import ExtractionEngine, ExtractionReport
from ..output.formatter import classify_status, score_confidence
from .. import __version__

logger = logging.getLogger("promptleak")

DORK_TEMPLATES = [
    "{query} chat",
    "{query} talk to",
    "inurl:chat {query}",
    "{query} ask me anything",
    'site:github.io "{query}"',
]

SKIP_PATTERNS = [
    r"^https?://(www\.)?(google|facebook|twitter|instagram|linkedin|reddit|youtube)\.(com|org)",
    r"\.(pdf|png|jpg|jpeg|gif|svg|zip|tar|gz)$",
    r"(login|signup|register|account)",
]


class HuntResult:
    def __init__(self, url: str, domain: str, status: str, confidence: float,
                 best_prompt: str, techniques_used: list[str], error: Optional[str] = None):
        self.url = url
        self.domain = domain
        self.status = status
        self.confidence = confidence
        self.best_prompt = best_prompt
        self.techniques_used = techniques_used
        self.error = error


class Hunter:
    def __init__(self, limit: int = 20, timeout: int = 120):
        self.limit = limit
        self.timeout = timeout

    async def search(self, query: str) -> list[str]:
        urls = set()
        for template in DORK_TEMPLATES:
            dork = template.format(query=query)
            try:
                found = await self._search_ddg(dork)
                for url in found:
                    urls.add(url)
                    if len(urls) >= self.limit * 2:
                        break
            except Exception as e:
                logger.debug(f"Dork '{dork}' failed: {e}")
            if len(urls) >= self.limit * 2:
                break
        return list(urls)[:self.limit]

    async def _search_ddg(self, query: str) -> list[str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        data = {"q": query}
        urls = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post("https://html.duckduckgo.com/html/", headers=headers, data=data, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            seen = set()
            for a_tag in soup.select("a.result__a"):
                href = a_tag.get("href", "")
                if not href:
                    continue
                if href.startswith("https://duckduckgo.com/y.js") or href.startswith("//duckduckgo.com/y.js"):
                    continue
                if href.startswith("https://duckduckgo.com/duckduckgo-help-pages"):
                    continue
                real_url = self._extract_ddg_url(href)
                if real_url and real_url not in seen and not self._should_skip(real_url):
                    seen.add(real_url)
                    urls.append(real_url)
        except Exception as e:
            logger.error(f"DDG search failed for '{query}': {e}")
        return urls

    def _extract_ddg_url(self, href: str) -> Optional[str]:
        if href.startswith("//"):
            href = "https:" + href
        if href.startswith("/l/?uddg="):
            encoded = href.split("uddg=", 1)[1]
            if "&" in encoded:
                encoded = encoded.split("&", 1)[0]
            return unquote(encoded)
        if href.startswith("http://") or href.startswith("https://"):
            return href
        return None

    def _should_skip(self, url: str) -> bool:
        for pat in SKIP_PATTERNS:
            if re.search(pat, url):
                return True
        return False

    async def scan_url(self, url: str) -> HuntResult:
        domain = urlparse(url).netloc
        config = ExtractionConfig(url=url, techniques=[], timeout=self.timeout, headed=False)
        engine = ExtractionEngine(config)
        try:
            report = await engine.run()
            status = classify_status(report.confidence)
            return HuntResult(
                url=url,
                domain=domain,
                status=status,
                confidence=report.confidence,
                best_prompt=report.best_result,
                techniques_used=report.techniques_used,
            )
        except Exception as e:
            return HuntResult(
                url=url,
                domain=domain,
                status="ERROR",
                confidence=0.0,
                best_prompt="",
                techniques_used=[],
                error=str(e),
            )

    async def quick_scan_url(self, url: str) -> tuple[float, str]:
        config = ExtractionConfig(
            url=url,
            techniques=["direct_ask", "translation_leak"],
            timeout=60,
            headed=False,
        )
        engine = ExtractionEngine(config)
        try:
            report = await engine.run()
            return report.confidence, report.best_result
        except Exception:
            return 0.0, ""

    async def hunt(self, query: str) -> list[HuntResult]:
        urls = await self.search(query)
        logger.info(f"Hunter found {len(urls)} potential targets for '{query}'")

        results = []
        for url in urls:
            conf, prompt = await self.quick_scan_url(url)
            if conf > 0.3:
                logger.info(f"Quick scan passed for {url} (conf={conf:.2f}), running full scan")
                result = await self.scan_url(url)
            else:
                status = classify_status(conf)
                result = HuntResult(
                    url=url, domain=urlparse(url).netloc,
                    status=status, confidence=conf,
                    best_prompt=prompt, techniques_used=["direct_ask", "translation_leak"],
                )
            results.append(result)

        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def export_html(self, results: list[HuntResult], query: str, path: str) -> str:
        rows_html = ""
        for rank, r in enumerate(results, 1):
            status_badge = self._status_badge(r.status)
            conf_pct = int(r.confidence * 100)
            rows_html += f"""
            <tr>
                <td>{rank}</td>
                <td><a href="{r.url}" target="_blank">{r.domain}</a></td>
                <td>{status_badge}</td>
                <td>
                    <div class="conf-bar"><div class="conf-fill" style="width:{conf_pct}%;background:{self._conf_color(r.confidence)};"></div></div>
                    <span class="conf-text">{conf_pct}%</span>
                </td>
                <td>{', '.join(r.techniques_used[:2]) if r.techniques_used else '-'}</td>
                <td><a href="#" onclick="toggleRow(event, this)">expand</a></td>
            </tr>
            <tr class="expanded-row" style="display:none;">
                <td colspan="6"><pre class="code-block">{self._escape(r.best_prompt[:1000])}</pre></td>
            </tr>
            """

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PromptLeak Hunter Report - {self._escape(query)}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: #0d1117; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.6; padding: 20px; }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    h1 {{ color: #58a6ff; font-size: 24px; margin-bottom: 8px; }}
    .subtitle {{ color: #8b949e; font-size: 14px; margin-bottom: 24px; }}
    table {{ width: 100%; border-collapse: collapse; background: #161b22; border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }}
    th {{ background: #21262d; color: #8b949e; text-transform: uppercase; font-size: 12px; padding: 12px 16px; text-align: left; border-bottom: 1px solid #30363d; }}
    td {{ padding: 12px 16px; border-bottom: 1px solid #21262d; font-size: 14px; }}
    tr:hover {{ background: #1c2128; }}
    a {{ color: #58a6ff; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .badge {{ display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; }}
    .badge-leaked {{ background: rgba(63,185,80,0.15); color: #3fb950; }}
    .badge-partial {{ background: rgba(210,153,34,0.15); color: #d29922; }}
    .badge-secure {{ background: rgba(248,81,73,0.15); color: #f85149; }}
    .badge-changed {{ background: rgba(188,140,255,0.15); color: #bc8cff; }}
    .badge-error {{ background: rgba(248,81,73,0.15); color: #f85149; }}
    .conf-bar {{ height: 8px; background: #21262d; border-radius: 4px; width: 120px; display: inline-block; vertical-align: middle; }}
    .conf-fill {{ height: 100%; border-radius: 4px; }}
    .conf-text {{ margin-left: 8px; font-size: 13px; vertical-align: middle; }}
    .code-block {{ background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 16px; overflow-x: auto; font-size: 13px; max-height: 300px; overflow-y: auto; color: #c9d1d9; }}
    .expanded-row td {{ padding: 0 16px 16px 16px; }}
    .footer {{ text-align: center; color: #8b949e; font-size: 12px; margin-top: 40px; padding: 20px; }}
    .footer a {{ color: #58a6ff; }}
</style>
</head>
<body>
<div class="container">
    <h1>PromptLeak Hunter Report</h1>
    <div class="subtitle">Query: "{self._escape(query)}" &mdash; {len(results)} targets scanned &mdash; {datetime.utcnow().isoformat()}</div>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Domain</th>
                <th>Status</th>
                <th>Confidence</th>
                <th>Best Technique</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    <div class="footer">
        Generated by <a href="https://github.com/mayankbhaskardev/prompt-leak" target="_blank">PromptLeak</a> v{__version__}
    </div>
</div>
<script>
function toggleRow(event, link) {{
    event.preventDefault();
    var row = link.closest('tr').nextElementSibling;
    if (row && row.classList.contains('expanded-row')) {{
        var visible = row.style.display !== 'none';
        row.style.display = visible ? 'none' : 'table-row';
        link.textContent = visible ? 'expand' : 'collapse';
    }}
}}
</script>
</body>
</html>"""
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return html

    def export_json(self, results: list[HuntResult], path: str) -> str:
        data = [
            {
                "url": r.url,
                "domain": r.domain,
                "status": r.status,
                "confidence": r.confidence,
                "best_prompt": r.best_prompt,
                "techniques_used": r.techniques_used,
                "error": r.error,
            }
            for r in results
        ]
        output = json.dumps(data, indent=2, default=str)
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(output)
        return output

    @staticmethod
    def _status_badge(status: str) -> str:
        cls_map = {"LEAKED": "badge-leaked", "PARTIAL": "badge-partial", "SECURE": "badge-secure", "ERROR": "badge-error", "CHANGED": "badge-changed"}
        cls = cls_map.get(status.upper(), "badge-secure")
        return f'<span class="badge {cls}">{status}</span>'

    @staticmethod
    def _conf_color(conf: float) -> str:
        if conf >= 0.7: return "#3fb950"
        if conf >= 0.3: return "#d29922"
        return "#f85149"

    @staticmethod
    def _escape(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")
