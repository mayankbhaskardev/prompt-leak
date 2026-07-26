"""Shareable report links — generate self-contained HTML and upload to pastebins."""
import json
import os
import re
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("promptleak")


class ReportSharer:
    """Generate shareable links for extraction reports."""

    def __init__(self, method: str = "file", verbose: bool = False):
        self.method = method
        self.verbose = verbose

    async def share(self, result: dict, method: Optional[str] = None) -> str:
        """Share a report and return a URL."""
        method = method or self.method
        html = self._generate_standalone_html(result)

        if method == "file":
            return self._save_file(html, result)
        elif method == "dpaste":
            return await self._upload_dpaste(html)
        elif method == "transfer":
            return await self._upload_transfer(html)
        elif method == "0x0":
            return await self._upload_0x0(html)
        else:
            logger.warning(f"Unknown share method: {method}, falling back to file")
            return self._save_file(html, result)

    def _generate_standalone_html(self, result: dict) -> str:
        """Generate a completely self-contained HTML file with all CSS/JS inline."""
        from .. import __version__
        from .formatter import classify_status

        domain = result.get("domain", "unknown")
        url = result.get("url", "")
        best = result.get("best_result", "No extraction")
        conf = result.get("confidence", 0)
        techniques_used = result.get("techniques_used", [])
        timestamp = result.get("timestamp", datetime.utcnow().isoformat())
        status = classify_status(conf)
        version = result.get("version", __version__)

        results_data = json.dumps(result.get("results", []), default=str)

        conf_pct = int(conf * 100)
        status_color = {"LEAKED": "#3fb950", "PARTIAL": "#d29922", "SECURE": "#f85149"}.get(status, "#8b949e")

        results_rows = ""
        for i, r in enumerate(result.get("results", [])):
            rname = r.get("technique_name", "unknown")
            rsuccess = r.get("success", False)
            rconf = r.get("confidence", 0)
            rerror = r.get("error", "None")
            routput = r.get("cleaned_output", "No output")[:500]
            rcolor = "#3fb950" if rconf >= 0.7 else "#d29922" if rconf >= 0.3 else "#f85149"
            results_rows += f"""
            <div class="tech-card" onclick="toggleDetail({i})">
                <div class="tech-header">
                    <span class="tech-name" style="color:{rcolor}">{rname}</span>
                    <span class="tech-conf">{rconf:.0%}</span>
                    <span class="tech-status">{'✓' if rsuccess else '✗'}</span>
                </div>
                <div class="tech-detail" id="detail-{i}" style="display:none;">
                    <pre>{routput}</pre>
                    {f'<div class="error">{rerror}</div>' if rerror != "None" else ''}
                </div>
            </div>"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PromptLeak Report — {domain}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: #0d1117; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.6; padding: 20px; }}
    .container {{ max-width: 800px; margin: 0 auto; }}
    .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #30363d; }}
    .header h1 {{ color: #58a6ff; font-size: 22px; }}
    .header .ts {{ color: #8b949e; font-size: 12px; }}
    .badge {{ display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; }}
    .badge-leaked {{ background: rgba(63,185,80,0.15); color: #3fb950; }}
    .badge-partial {{ background: rgba(210,153,34,0.15); color: #d29922; }}
    .badge-secure {{ background: rgba(248,81,73,0.15); color: #f85149; }}
    .stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 24px; }}
    .stat {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }}
    .stat-label {{ color: #8b949e; font-size: 10px; text-transform: uppercase; }}
    .stat-value {{ font-size: 18px; font-weight: bold; margin-top: 4px; }}
    .conf-bar {{ height: 8px; background: #21262d; border-radius: 4px; margin-top: 8px; }}
    .conf-fill {{ height: 100%; border-radius: 4px; background: {status_color}; width: {conf_pct}%; }}
    .best-section {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 24px; }}
    .best-section h2 {{ color: #58a6ff; font-size: 16px; margin-bottom: 12px; }}
    .code-block {{ background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 16px; overflow-x: auto; font-size: 13px; font-family: 'SF Mono', Monaco, monospace; color: #c9d1d9; max-height: 400px; overflow-y: auto; white-space: pre-wrap; }}
    .techs {{ margin-bottom: 24px; }}
    .tech-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; margin-bottom: 8px; overflow: hidden; }}
    .tech-header {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; cursor: pointer; }}
    .tech-header:hover {{ background: #1c2128; }}
    .tech-name {{ font-weight: 600; font-size: 14px; }}
    .tech-conf {{ color: #8b949e; font-size: 13px; }}
    .tech-status {{ font-size: 14px; }}
    .tech-detail {{ padding: 12px 16px; border-top: 1px solid #21262d; }}
    .tech-detail pre {{ font-size: 12px; color: #c9d1d9; white-space: pre-wrap; }}
    .error {{ color: #f85149; margin-top: 8px; font-size: 12px; }}
    .share-section {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin-bottom: 24px; }}
    .share-section h3 {{ color: #8b949e; font-size: 12px; text-transform: uppercase; margin-bottom: 8px; }}
    .share-link {{ color: #58a6ff; word-break: break-all; font-size: 14px; }}
    .copy-btn {{ padding: 6px 14px; background: #238636; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; }}
    .copy-btn:hover {{ background: #2ea043; }}
    .footer {{ text-align: center; color: #8b949e; font-size: 12px; padding: 20px; }}
    .footer a {{ color: #58a6ff; }}
    .view-source-btn {{ background: #21262d; color: #8b949e; border: 1px solid #30363d; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 12px; }}
    @media (max-width: 600px) {{ .stats {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <div>
            <h1>PromptLeak Report</h1>
            <div class="ts">{timestamp}</div>
        </div>
        <div>
            <span class="badge badge-{status.lower()}">{status}</span>
        </div>
    </div>

    <div class="stats">
        <div class="stat">
            <div class="stat-label">Target</div>
            <div class="stat-value" style="font-size:15px;word-break:break-all;">{domain}</div>
        </div>
        <div class="stat">
            <div class="stat-label">Confidence</div>
            <div class="stat-value" style="color:{status_color};">{conf_pct}%</div>
            <div class="conf-bar"><div class="conf-fill"></div></div>
        </div>
        <div class="stat">
            <div class="stat-label">Techniques Run</div>
            <div class="stat-value">{len(techniques_used)}</div>
        </div>
        <div class="stat">
            <div class="stat-label">Version</div>
            <div class="stat-value">{version}</div>
        </div>
    </div>

    <div class="best-section">
        <h2>Extraction Result</h2>
        <div class="code-block" id="best-output">{best}</div>
        <div style="margin-top:12px;">
            <button class="copy-btn" onclick="copyText('best-output')">Copy</button>
            <button class="view-source-btn" onclick="toggleRaw()">View Source</button>
        </div>
        <div id="raw-data" style="display:none;margin-top:12px;">
            <pre class="code-block">{json.dumps(result, indent=2, default=str)}</pre>
        </div>
    </div>

    <div class="techs">
        <h2 style="color:#58a6ff;font-size:16px;margin-bottom:12px;">Technique Results</h2>
        {results_rows}
    </div>

    <div class="share-section">
        <h3>Share this report</h3>
        <p style="color:#8b949e;font-size:13px;margin-bottom:8px;">
            This is a self-contained HTML file. Save it and share via any file host.
        </p>
        <button class="copy-btn" onclick="shareViaClipboard()">Copy entire report as HTML</button>
        <p id="share-status" style="color:#3fb950;font-size:12px;margin-top:8px;"></p>
    </div>

    <div class="footer">
        Generated by <a href="https://github.com/mayankbhaskardev/prompt-leak" target="_blank">PromptLeak</a> v{version} &mdash;
        <a href="https://github.com/mayankbhaskardev/prompt-leak" target="_blank">github.com/mayankbhaskardev/prompt-leak</a>
    </div>
</div>

<script>
function copyText(id) {{
    var el = document.getElementById(id);
    var text = el.textContent;
    navigator.clipboard.writeText(text).then(function() {{
        var btn = event.target;
        btn.textContent = 'Copied!';
        setTimeout(function() {{ btn.textContent = 'Copy'; }}, 2000);
    }});
}}
function toggleDetail(id) {{
    var el = document.getElementById('detail-' + id);
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
}}
function toggleRaw() {{
    var el = document.getElementById('raw-data');
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
}}
function shareViaClipboard() {{
    var html = document.documentElement.outerHTML;
    navigator.clipboard.writeText(html).then(function() {{
        document.getElementById('share-status').textContent = '✓ HTML copied to clipboard! Paste anywhere to share.';
    }});
}}
</script>
</body>
</html>"""
        return html

    def _save_file(self, html: str, result: dict) -> str:
        """Save to a local file and return the path."""
        from .. import __version__
        domain = result.get("domain", "unknown")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"promptleak_report_{domain}_{timestamp}.html"

        output_dir = os.path.join(os.path.expanduser("~/.promptleak"), "shared")
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"Report saved to {filepath}")
        return f"file://{filepath}"

    async def _upload_dpaste(self, content: str) -> str:
        """Upload to dpaste.com."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                data = {"content": content, "syntax": "html", "expiry_days": "30"}
                async with session.post("https://dpaste.com/api/", data=data, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status in (200, 201, 302):
                        text = await resp.text()
                        url = text.strip()
                        if url:
                            logger.info(f"Uploaded to dpaste: {url}")
                            return url
                    logger.warning(f"dpaste upload failed: {resp.status}")
        except Exception as e:
            logger.warning(f"dpaste upload error: {e}")
        return ""

    async def _upload_transfer(self, content: str) -> str:
        """Upload to transfer.sh."""
        import aiohttp
        import tempfile
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
                f.write(content)
                tmp_path = f.name
            async with aiohttp.ClientSession() as session:
                with open(tmp_path, "rb") as f:
                    data = f.read()
                async with session.put(
                    "https://transfer.sh/promptleak_report.html",
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    os.unlink(tmp_path)
                    if resp.status == 200:
                        url = (await resp.text()).strip()
                        if url:
                            logger.info(f"Uploaded to transfer.sh: {url}")
                            return url
        except Exception as e:
            logger.warning(f"transfer.sh upload error: {e}")
        return ""

    async def _upload_0x0(self, content: str) -> str:
        """Upload to 0x0.st."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field("file", content.encode(), filename="report.html", content_type="text/html")
                async with session.post("https://0x0.st", data=data, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        url = (await resp.text()).strip()
                        if url:
                            logger.info(f"Uploaded to 0x0.st: {url}")
                            return url
                    logger.warning(f"0x0.st upload failed: {resp.status}")
        except Exception as e:
            logger.warning(f"0x0.st upload error: {e}")
        return ""
