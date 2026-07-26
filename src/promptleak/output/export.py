"""Export extraction reports in JSON, Markdown, and HTML formats."""
import json
import os
import difflib
from datetime import datetime
from typing import Optional

from .formatter import classify_status


def export_json(report: dict, path: Optional[str] = None) -> str:
    output = json.dumps(report, indent=2, default=str)
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(output)
    return output


def export_markdown(report: dict, path: Optional[str] = None) -> str:
    timestamp = report.get("timestamp", datetime.utcnow().isoformat())
    lines = [
        f"# PromptLeak Report",
        f"",
        f"- **Target**: `{report.get('url', 'N/A')}`",
        f"- **Domain**: `{report.get('domain', 'N/A')}`",
        f"- **Timestamp**: {timestamp}",
        f"- **Overall Confidence**: `{report.get('confidence', 0):.2f}`",
        f"- **Techniques Used**: {', '.join(report.get('techniques_used', []))}",
        f"",
        f"## Best Extraction",
        f"",
        f"```",
        f"{report.get('best_result', 'No extraction')}",
        f"```",
        f"",
        f"## Technique Details",
        f"",
    ]

    for result in report.get("results", []):
        lines.extend([
            f"### {result.get('technique_name', 'unknown')}",
            f"",
            f"- **Success**: {result.get('success', False)}",
            f"- **Confidence**: `{result.get('confidence', 0):.2f}`",
            f"- **Error**: {result.get('error', 'None')}",
            f"",
            f"```",
            f"{result.get('cleaned_output', 'No output')[:500]}",
            f"```",
            f"",
        ])

    output = "\n".join(lines)
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(output)
    return output


def export_html(report: dict, path: Optional[str] = None, previous_report: Optional[dict] = None) -> str:
    timestamp = report.get("timestamp", datetime.utcnow().isoformat())
    best = report.get("best_result", "No extraction")
    conf = report.get("confidence", 0)
    domain = report.get("domain", "N/A")
    url = report.get("url", "")
    techniques_used = report.get("techniques_used", [])
    status = classify_status(conf)

    if previous_report:
        prev_best = previous_report.get("best_result", "")
        sim = difflib.SequenceMatcher(None, prev_best[:1000], best[:1000]).ratio()
        changed = sim < 0.8
    else:
        changed = False

    stat_boxes = f"""
    <div class="stat-box"><span class="stat-label">Target</span><span class="stat-value">{_escape_html(domain)}</span></div>
    <div class="stat-box"><span class="stat-label">Status</span><span class="status-pill {status.lower()}">{status}</span></div>
    <div class="stat-box"><span class="stat-label">Confidence</span>
        <div class="conf-row">
            <span class="conf-pct">{conf*100:.0f}%</span>
            <div class="conf-bar"><div class="conf-fill" style="width:{conf*100:.0f}%;background:{_conf_color(conf)};"></div></div>
        </div>
    </div>
    <div class="stat-box"><span class="stat-label">Techniques Run</span><span class="stat-value">{len(techniques_used)}/7</span></div>
    """

    col = _conf_color(conf)
    best_html = ""
    if conf > 0:
        best_html = f"""
        <div class="section best-section">
            <div class="section-header"><h2>Best Extraction</h2><button class="copy-btn" onclick="copyText('best-output')">Copy</button></div>
            <pre class="code-block" id="best-output"><code>{_escape_html(best)}</code></pre>
            <div class="conf-row" style="margin-top:8px;">
                <span class="conf-pct" style="color:{col};">{conf*100:.0f}% confidence</span>
                <div class="conf-bar"><div class="conf-fill" style="width:{conf*100:.0f}%;background:{col};"></div></div>
            </div>
        </div>"""

    results_html = ""
    for i, r in enumerate(report.get("results", [])):
        name = r.get("technique_name", "unknown")
        success = r.get("success", False)
        confidence = r.get("confidence", 0)
        error = r.get("error", "None")
        output = r.get("cleaned_output", "No output")
        meta = r.get("metadata", {})
        status_icon = "&#9679;"
        status_color = _conf_color(confidence)
        response_len = len(output)

        meta_html = ""
        if meta:
            for k, v in meta.items():
                if isinstance(v, dict):
                    safe = {kk: vv for kk, vv in v.items() if kk.lower() not in ("authorization", "cookie", "token", "auth")}
                    meta_html += f"<div class='meta-item'><strong>{k}:</strong> {_escape_html(json.dumps(safe, default=str))}</div>"
                elif isinstance(v, list) and len(v) > 0:
                    items = [_escape_html(str(x)) for x in v[:3]]
                    meta_html += f"<div class='meta-item'><strong>{k}:</strong> {', '.join(items)}</div>"
                else:
                    meta_html += f"<div class='meta-item'><strong>{k}:</strong> {_escape_html(str(v)[:200])}</div>"

        results_html += f"""
        <tr class="tech-row" onclick="toggleTech(this)">
            <td><span class="status-dot" style="color:{status_color};">{status_icon}</span></td>
            <td>{_escape_html(name)}</td>
            <td>{'Pass' if success else 'Fail'}</td>
            <td>{confidence:.2f}</td>
            <td>{response_len}</td>
        </tr>
        <tr class="tech-detail" style="display:none;">
            <td colspan="5">
                <pre class="code-block"><code>{_escape_html(output[:2000])}</code></pre>
                {meta_html}
                {f'<div class="meta-item" style="color:#f85149;"><strong>Error:</strong> {_escape_html(error)}</div>' if error and error != "None" else ''}
            </td>
        </tr>"""

    api_endpoints = []
    for r in report.get("results", []):
        meta = r.get("metadata", {})
        if meta.get("api_endpoint"):
            api_endpoints.append({
                "endpoint": meta["api_endpoint"],
                "method": meta.get("method", "POST"),
                "format": meta.get("response_format", "json"),
            })
        for ep in meta.get("discovered_endpoints", []):
            api_endpoints.append({"endpoint": ep, "method": "?", "format": "?"})

    api_html = ""
    if api_endpoints:
        api_rows = "".join(
            f"<tr><td>{_escape_html(e['endpoint'])}</td><td>{e['method']}</td><td>{e['format']}</td></tr>"
            for e in api_endpoints[:10]
        )
        api_html = f"""
        <div class="section">
            <h2>Discovered API Endpoints</h2>
            <table class="tech-table"><thead><tr><th>Endpoint</th><th>Method</th><th>Format</th></tr></thead><tbody>{api_rows}</tbody></table>
        </div>"""

    changed_badge = '<span class="status-pill changed">CHANGED</span>' if changed else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PromptLeak Report - {_escape_html(domain)}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: #0d1117; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.6; }}
    .container {{ max-width: 960px; margin: 0 auto; padding: 20px; }}
    .header {{ display: flex; align-items: center; justify-content: space-between; padding: 16px 24px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; margin-bottom: 20px; }}
    .header h1 {{ color: #58a6ff; font-size: 20px; }}
    .header .ts {{ color: #8b949e; font-size: 12px; }}
    .header a {{ color: #58a6ff; text-decoration: none; font-size: 14px; margin-left: 12px; }}
    .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }}
    .stat-box {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }}
    .stat-label {{ display: block; color: #8b949e; font-size: 10px; text-transform: uppercase; margin-bottom: 6px; }}
    .stat-value {{ font-size: 14px; color: #c9d1d9; word-break: break-all; }}
    .status-pill {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; }}
    .leaked {{ background: rgba(63,185,80,0.15); color: #3fb950; }}
    .partial {{ background: rgba(210,153,34,0.15); color: #d29922; }}
    .secure {{ background: rgba(248,81,73,0.15); color: #f85149; }}
    .changed {{ background: rgba(188,140,255,0.15); color: #bc8cff; }}
    .conf-row {{ display: flex; align-items: center; gap: 8px; }}
    .conf-pct {{ font-size: 16px; font-weight: bold; }}
    .conf-bar {{ flex: 1; height: 8px; background: #21262d; border-radius: 4px; }}
    .conf-fill {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
    .section {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 16px; }}
    .section-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
    .section h2 {{ color: #58a6ff; font-size: 16px; }}
    .copy-btn {{ padding: 6px 14px; background: #238636; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; }}
    .copy-btn:hover {{ background: #2ea043; }}
    .code-block {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 16px; overflow-x: auto; font-size: 13px; font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; color: #c9d1d9; max-height: 400px; overflow-y: auto; }}
    .tech-table {{ width: 100%; border-collapse: collapse; }}
    .tech-table th {{ background: #21262d; color: #8b949e; text-transform: uppercase; font-size: 11px; padding: 10px 12px; text-align: left; border-bottom: 1px solid #30363d; }}
    .tech-table td {{ padding: 10px 12px; border-bottom: 1px solid #21262d; font-size: 13px; }}
    .tech-row {{ cursor: pointer; }}
    .tech-row:hover {{ background: #1c2128; }}
    .tech-detail td {{ padding: 12px; background: #0d1117; }}
    .status-dot {{ font-size: 18px; line-height: 1; }}
    .meta-item {{ font-size: 12px; color: #8b949e; padding: 4px 0; }}
    .meta-item strong {{ color: #c9d1d9; }}
    .footer {{ text-align: center; color: #8b949e; font-size: 12px; padding: 20px; }}
    .footer a {{ color: #58a6ff; text-decoration: none; }}
    @media (max-width: 600px) {{ .summary-grid {{ grid-template-columns: 1fr 1fr; }} }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>PromptLeak Report</h1>
        <div>
            <span class="ts">{timestamp}</span>
            <a href="https://github.com/mayankbhaskardev/prompt-leak" target="_blank">github</a>
        </div>
    </div>
    <div class="summary-grid">{stat_boxes}</div>
    {changed_badge if changed_badge else ''}
    {best_html}
    <div class="section">
        <h2>Technique Comparison</h2>
        <table class="tech-table">
            <thead><tr><th></th><th>Technique</th><th>Status</th><th>Confidence</th><th>Response Length</th></tr></thead>
            <tbody>{results_html}</tbody>
        </table>
    </div>
    {api_html}
    <div class="footer">
        Generated by <a href="https://github.com/mayankbhaskardev/prompt-leak" target="_blank">PromptLeak</a> v{report.get('version', '0.1.0')}
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
function toggleTech(row) {{
    var detail = row.nextElementSibling;
    if (detail && detail.classList.contains('tech-detail')) {{
        detail.style.display = detail.style.display === 'none' ? 'table-row' : 'none';
    }}
}}
</script>
</body>
</html>"""

    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
    return html


def export_report(report: dict, fmt: str = "json", path: Optional[str] = None, previous_report: Optional[dict] = None) -> str:
    exporters = {
        "json": export_json,
        "markdown": export_markdown,
        "html": export_html,
    }
    exporter = exporters.get(fmt, export_json)
    if fmt == "html":
        return exporter(report, path, previous_report)
    return exporter(report, path)


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")


def _conf_color(conf: float) -> str:
    if conf >= 0.7:
        return "#3fb950"
    elif conf >= 0.3:
        return "#d29922"
    return "#f85149"
