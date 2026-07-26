"""Click-based CLI interface for PromptLeak."""
import asyncio
import json
import os
import sys
from typing import Optional
from urllib.parse import urlparse

import click

from .core.config import ExtractionConfig
from .core.engine import ExtractionEngine
from .core.hunter import Hunter
from .output.export import export_report, export_json, _escape_html
from .output.gallery import add_to_gallery, list_gallery as list_gallery_entries
from .utils.logger import setup_logger, console


@click.command()
@click.argument("url", required=False)
@click.option("-t", "--techniques", default="", help="Comma-separated techniques (default: all)")
@click.option("-o", "--output", default=None, type=click.Path(), help="Output file path (default: stdout)")
@click.option("-f", "--format", "output_format", default="json", type=click.Choice(["json", "markdown", "html"]), help="Output format")
@click.option("--headed", is_flag=True, help="Run browser in headed mode (visible)")
@click.option("--proxy", default=None, help="Proxy URL (http://ip:port)")
@click.option("--no-cache", is_flag=True, help="Skip cached results")
@click.option("--screenshot", default=None, type=click.Path(), help="Save screenshot on completion")
@click.option("--timeout", default=120, type=int, help="Global timeout in seconds")
@click.option("--gallery", is_flag=True, help="Add to local gallery after extraction")
@click.option("--list-gallery", "show_gallery", is_flag=True, help="List all gallery entries and exit")
@click.option("--hunt", default=None, help="Auto-discovery search query (e.g. 'AI chatbot')")
@click.option("--limit", default=20, type=int, help="Max targets for hunt mode (default: 20)")
@click.option("--batch", default=None, type=click.Path(exists=True), help="File with URLs for batch mode")
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging")
def main(
    url: str,
    techniques: str,
    output: Optional[str],
    output_format: str,
    headed: bool,
    proxy: Optional[str],
    no_cache: bool,
    screenshot: Optional[str],
    timeout: int,
    gallery: bool,
    show_gallery: bool,
    hunt: Optional[str],
    limit: int,
    batch: Optional[str],
    verbose: bool,
):
    """Extract system prompts from AI chat applications.

    URL is the target AI chat application URL (e.g. https://chat.openai.com).
    """
    setup_logger(verbose)

    if show_gallery:
        entries = list_gallery_entries()
        if not entries:
            console.print("[yellow]No gallery entries found[/]")
        else:
            console.print(f"[bold cyan]Gallery ({len(entries)} entries)[/]")
            for e in entries:
                console.print(f"  {e['filename']}")
        return

    mode_count = sum(1 for x in [url, hunt, batch] if x)
    if mode_count == 0:
        console.print("[red]Error: Provide a URL, --hunt QUERY, or --batch FILE[/]")
        sys.exit(1)
    if mode_count > 1:
        console.print("[red]Error: URL, --hunt, and --batch are mutually exclusive[/]")
        sys.exit(1)

    if hunt:
        console.print(f"[bold cyan]PromptLeak[/] hunting for [bold]{hunt}[/] (limit: {limit})")
        asyncio.run(_run_hunt(hunt, limit, output, output_format, verbose))
        return

    if batch:
        console.print(f"[bold cyan]PromptLeak[/] batch mode: [bold]{batch}[/]")
        asyncio.run(_run_batch(batch, output, output_format, headed, proxy, no_cache, screenshot, timeout, verbose))
        return

    technique_list = [t.strip() for t in techniques.split(",") if t.strip()] if techniques else []

    config = ExtractionConfig(
        url=url,
        techniques=technique_list,
        output_path=output,
        output_format=output_format,
        headed=headed,
        proxy=proxy,
        no_cache=no_cache,
        screenshot_path=screenshot,
        timeout=timeout,
        gallery=gallery,
        verbose=verbose,
    )

    engine = ExtractionEngine(config)

    console.print(f"[bold cyan]PromptLeak[/] targeting [bold]{url}[/]")
    console.print(f"[dim]Techniques: {', '.join(config.techniques) if config.techniques else 'all'}[/]")

    try:
        report = asyncio.run(engine.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)

    report_dict = report.to_dict()

    if gallery and report.best_result:
        domain = urlparse(url).netloc
        add_to_gallery(
            domain=domain,
            technique="best_result",
            extracted_text=report.best_result,
            confidence=report.confidence,
            url=url,
        )
        console.print("[green]Added to gallery[/]")

    export_report(report_dict, fmt=output_format, path=output)

    if not output:
        console.print("\n[bold]=== EXTRACTION REPORT ===[/]")
        console.print(f"Target: {url}")
        console.print(f"Confidence: {report.confidence:.2f}")
        console.print(f"Techniques: {', '.join(report.techniques_used)}")
        console.print("\n[bold]Best Result:[/]")
        console.print(report.best_result if report.best_result else "[yellow]No prompt extracted[/]")


async def _run_hunt(query: str, limit: int, output: Optional[str], output_format: str, verbose: bool):
    hunter = Hunter(limit=limit)
    results = await hunter.hunt(query)

    leaked = [r for r in results if r.status == "LEAKED"]
    partial = [r for r in results if r.status == "PARTIAL"]
    secure = [r for r in results if r.status == "SECURE"]

    console.print(f"\n[bold]Hunt Results:[/] {len(leaked)} leaked, {len(partial)} partial, {len(secure)} secure, {len(results)} total")

    for r in results:
        color = {"LEAKED": "green", "PARTIAL": "yellow", "SECURE": "dim", "ERROR": "red"}.get(r.status, "white")
        console.print(f"  [{color}]{r.status:8}[/] {r.confidence:.2f}  {r.domain}")

    if output:
        ext = os.path.splitext(output)[1].lower()
        if ext == ".json" or output_format == "json":
            hunter.export_json(results, output)
        else:
            hunter.export_html(results, query, output)
        console.print(f"[green]Report written to {output}[/]")


async def _run_batch(batch_file: str, output_dir: Optional[str], output_format: str,
                     headed: bool, proxy: Optional[str], no_cache: bool,
                     screenshot: Optional[str], timeout: int, verbose: bool):
    try:
        with open(batch_file, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(batch_file, "r", encoding="utf-16") as f:
            lines = f.readlines()

    urls = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        urls.append(stripped)

    if not urls:
        console.print("[red]No URLs found in batch file[/]")
        return

    if not output_dir:
        output_dir = "results"
    os.makedirs(output_dir, exist_ok=True)

    previous_reports = {}
    for fname in os.listdir(output_dir):
        if fname.endswith(".json") and fname != "index.html":
            fpath = os.path.join(output_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    prev = json.load(f)
                    previous_reports[prev.get("domain", "")] = prev
            except Exception:
                pass

    all_reports = []
    for target_url in urls:
        domain = urlparse(target_url).netloc
        console.print(f"\n[bold]Processing:[/] {domain}")

        config = ExtractionConfig(
            url=target_url,
            techniques=[],
            output_path=None,
            output_format="json",
            headed=headed,
            proxy=proxy,
            no_cache=no_cache,
            screenshot_path=screenshot,
            timeout=timeout,
            gallery=False,
            verbose=verbose,
        )
        engine = ExtractionEngine(config)
        try:
            report = await engine.run()
            report_dict = report.to_dict()

            safe_domain = domain.replace(".", "_")
            js_path = os.path.join(output_dir, f"{safe_domain}.json")
            export_json(report_dict, js_path)

            prev = previous_reports.get(domain)
            html_path = os.path.join(output_dir, f"{safe_domain}.html")
            export_report(report_dict, fmt="html", path=html_path, previous_report=prev)

            all_reports.append(report_dict)
            console.print(f"  [green]Done.[/] Confidence: {report.confidence:.2f}")
        except Exception as e:
            console.print(f"  [red]Failed: {e}[/]")
            all_reports.append({
                "url": target_url,
                "domain": domain,
                "confidence": 0.0,
                "best_result": "",
                "techniques_used": [],
                "results": [],
                "timestamp": "",
                "version": "",
                "status": "ERROR",
                "error": str(e),
            })

    _write_batch_index(all_reports, output_dir)
    console.print(f"\n[green]Batch complete. Results in {output_dir}/[/]")


def _write_batch_index(reports: list[dict], output_dir: str):
    from .output.formatter import classify_status
    from datetime import datetime
    from . import __version__

    rows = ""
    for rank, r in enumerate(sorted(reports, key=lambda x: x.get("confidence", 0), reverse=True), 1):
        conf = r.get("confidence", 0)
        domain = r.get("domain", "unknown")
        url = r.get("url", "")
        status = r.get("status", classify_status(conf))
        techs = r.get("techniques_used", [])
        best = r.get("best_result", "")
        safe_domain = domain.replace(".", "_")

        status_norm = status.upper() if status != "ERROR" else "ERROR"
        cls_map = {"LEAKED": "badge-leaked", "PARTIAL": "badge-partial", "SECURE": "badge-secure", "ERROR": "badge-error"}
        status_cls = cls_map.get(status_norm, "badge-secure")

        prev_path = os.path.join(output_dir, f"{safe_domain}.json")
        changed = False
        if os.path.exists(prev_path):
            try:
                with open(prev_path, "r", encoding="utf-8") as f:
                    prev_data = json.load(f)
                prev_best = prev_data.get("best_result", "")
                import difflib
                sim = difflib.SequenceMatcher(None, prev_best[:1000], best[:1000]).ratio()
                changed = sim < 0.8
            except Exception:
                pass

        changed_badge = '<span class="badge badge-changed">CHANGED</span>' if changed else ""
        detail_link = f'{safe_domain}.html'
        conf_pct = int(conf * 100)

        rows += f"""
        <tr>
            <td>{rank}</td>
            <td><a href="{detail_link}">{_escape_html(domain)}</a></td>
            <td><span class="badge {status_cls}">{status_norm}</span>{changed_badge}</td>
            <td>
                <div class="conf-bar"><div class="conf-fill" style="width:{conf_pct}%;background:{_conf_color_batch(conf)};"></div></div>
                <span class="conf-text">{conf_pct}%</span>
            </td>
            <td>{', '.join(techs[:2]) if techs else '-'}</td>
        </tr>"""

    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PromptLeak Batch Report</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: #0d1117; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.6; padding: 20px; }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    h1 {{ color: #58a6ff; font-size: 24px; margin-bottom: 8px; }}
    .subtitle {{ color: #8b949e; font-size: 14px; margin-bottom: 24px; }}
    table {{ width: 100%; border-collapse: collapse; background: #161b22; border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }}
    th {{ background: #21262d; color: #8b949e; text-transform: uppercase; font-size: 11px; padding: 12px 16px; text-align: left; border-bottom: 1px solid #30363d; }}
    td {{ padding: 12px 16px; border-bottom: 1px solid #21262d; font-size: 14px; }}
    tr:hover {{ background: #1c2128; }}
    a {{ color: #58a6ff; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .badge {{ display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-right: 4px; }}
    .badge-leaked {{ background: rgba(63,185,80,0.15); color: #3fb950; }}
    .badge-partial {{ background: rgba(210,153,34,0.15); color: #d29922; }}
    .badge-secure {{ background: rgba(248,81,73,0.15); color: #f85149; }}
    .badge-error {{ background: rgba(248,81,73,0.15); color: #f85149; }}
    .badge-changed {{ background: rgba(188,140,255,0.15); color: #bc8cff; }}
    .conf-bar {{ height: 8px; background: #21262d; border-radius: 4px; width: 100px; display: inline-block; vertical-align: middle; }}
    .conf-fill {{ height: 100%; border-radius: 4px; }}
    .conf-text {{ margin-left: 6px; font-size: 12px; vertical-align: middle; }}
    .footer {{ text-align: center; color: #8b949e; font-size: 12px; margin-top: 40px; padding: 20px; }}
    .footer a {{ color: #58a6ff; }}
</style>
</head>
<body>
<div class="container">
    <h1>PromptLeak Batch Report</h1>
    <div class="subtitle">{len(reports)} targets &mdash; {datetime.utcnow().isoformat()}</div>
    <table>
        <thead><tr><th>#</th><th>Domain</th><th>Status</th><th>Confidence</th><th>Best Technique</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>
    <div class="footer">
        Generated by <a href="https://github.com/mayankbhaskardev/prompt-leak" target="_blank">PromptLeak</a> v{__version__}
    </div>
</div>
</body>
</html>"""

    with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)


def _conf_color_batch(conf: float) -> str:
    if conf >= 0.7: return "#3fb950"
    if conf >= 0.3: return "#d29922"
    return "#f85149"


if __name__ == "__main__":
    main()
