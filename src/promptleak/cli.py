"""Click-based CLI interface for PromptLeak v3.0.0."""
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


@click.group(invoke_without_command=True)
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
@click.option("--web", is_flag=True, help="Start the PromptLeak web UI server")
@click.option("--plugins-dir", default=None, type=click.Path(), help="Custom plugins directory (default: ~/.promptleak/plugins/)")
@click.option("--list-plugins", is_flag=True, help="List all loaded plugins and exit")
@click.option("--schedule", is_flag=True, help="Run scheduled scans in foreground")
@click.option("--schedule-file", default=None, type=click.Path(exists=True), help="JSON file with scheduled job definitions")
@click.option("--interval", default=24, type=int, help="Scan interval in hours (for --schedule)")
@click.option("--notify", default=None, help="Notification config as JSON or type:url (for --schedule)")
@click.option("--ai-provider", default=None, help="LLM provider for AI payload generation (openai, anthropic, ollama)")
@click.option("--ai-model", default=None, help="Model for AI payload generation (default: gpt-4o-mini)")
@click.option("--ai-key", default=None, help="API key for AI payload generation provider")
@click.option("--ai-base-url", default=None, help="Base URL for AI provider (e.g. Ollama: http://localhost:11434)")
@click.option("--fuzz", is_flag=True, help="Enable prompt fuzzing (500+ mutations of base payloads)")
@click.option("--fuzz-count", default=500, type=int, help="Max payloads for fuzzer (default: 500)")
@click.option("--fuzz-strategies", default=None, help="Comma-separated fuzz strategies: case,punctuation,spacing,language,formatting,framing,injection,encoding")
@click.option("--fingerprint", is_flag=True, help="Fingerprint the model behind the target")
@click.option("--test-prompt", is_flag=True, help="Test a system prompt for vulnerabilities")
@click.option("--prompt-file", default=None, type=click.Path(exists=True), help="File containing system prompt to test (for --test-prompt)")
@click.option("--share", is_flag=True, help="Generate a shareable report link")
@click.option("--share-method", default="file", type=click.Choice(["file", "dpaste", "transfer", "0x0"]), help="Share method (default: file)")
@click.option("--proxy-mode", is_flag=True, help="Start MITM proxy to capture prompts from any traffic")
@click.option("--proxy-port", default=8080, type=int, help="Port for MITM proxy (default: 8080)")
@click.option("--proxy-output", default="./captures", type=click.Path(), help="Output directory for proxy captures")
@click.option("--chain", is_flag=True, help="Enable multi-turn conversation chain extraction")
@click.option("--chain-strategy", default="auto", type=click.Choice(["auto", "trust_escalation", "authority_cascade", "fragment_assembly", "philosophical_trap", "emotional_manipulation"]), help="Conversation chain strategy")
@click.option("--max-turns", default=5, type=int, help="Max turns for conversation chain")
@click.option("--token-probe", is_flag=True, help="Run token-level probe analysis")
@click.option("--harden", is_flag=True, help="Harden a leaked prompt against future extraction")
@click.option("--harden-output", default=None, type=click.Path(), help="Output file for hardened prompt")
@click.option("--track", is_flag=True, help="Track prompt changes with IntelTracker")
@click.option("--intel-db", default=None, type=click.Path(), help="Intel database path (default: ~/.promptleak/intel.db)")
@click.option("--intel-report", default=None, type=click.Path(), help="Export intel report to file")
@click.option("--intel-timeline", default=None, type=click.Path(), help="Export intel timeline to file")
@click.option("--intel-leaderboard", default=None, type=click.Path(), help="Export intel leaderboard to file")
@click.option("--vision-probe", is_flag=True, help="Scan page for image-based prompt leakage")
@click.option("--monitor", is_flag=True, help="Start real-time monitor mode")
@click.option("--monitor-file", default=None, type=click.Path(exists=True), help="File with targets for monitor mode")
@click.option("--monitor-interval", default=300, type=int, help="Monitor scan interval in seconds")
@click.option("--monitor-notify", default=None, help="Notification config for monitor (type:url)")
@click.option("--grid", is_flag=True, help="Enable distributed grid mode")
@click.option("--grid-role", default="master", type=click.Choice(["master", "worker"]), help="Grid node role")
@click.option("--grid-redis", default="redis://localhost:6379/0", help="Redis URL for grid coordination")
@click.option("--grid-max-workers", default=10, type=int, help="Max workers for grid master")
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging")
@click.pass_context
def main(
    ctx: click.Context,
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
    web: bool,
    plugins_dir: Optional[str],
    list_plugins: bool,
    schedule: bool,
    schedule_file: Optional[str],
    interval: int,
    notify: Optional[str],
    ai_provider: Optional[str],
    ai_model: Optional[str],
    ai_key: Optional[str],
    ai_base_url: Optional[str],
    fuzz: bool,
    fuzz_count: int,
    fuzz_strategies: Optional[str],
    fingerprint: bool,
    test_prompt: bool,
    prompt_file: Optional[str],
    share: bool,
    share_method: str,
    proxy_mode: bool,
    proxy_port: int,
    proxy_output: str,
    chain: bool,
    chain_strategy: str,
    max_turns: int,
    token_probe: bool,
    harden: bool,
    harden_output: Optional[str],
    track: bool,
    intel_db: Optional[str],
    intel_report: Optional[str],
    intel_timeline: Optional[str],
    intel_leaderboard: Optional[str],
    vision_probe: bool,
    monitor: bool,
    monitor_file: Optional[str],
    monitor_interval: int,
    monitor_notify: Optional[str],
    grid: bool,
    grid_role: str,
    grid_redis: str,
    grid_max_workers: int,
    verbose: bool,
):
    """Extract system prompts from AI chat applications.

    URL is the target AI chat application URL (e.g. https://chat.openai.com).

    For subcommands, use: pleak serve, pleak plugins, etc.
    """
    if ctx.invoked_subcommand is not None:
        return

    setup_logger(verbose)

    if list_plugins:
        _list_plugins(plugins_dir)
        return

    if proxy_mode:
        _start_proxy(proxy_port, proxy_output, verbose)
        return

    if test_prompt:
        asyncio.run(_run_test_prompt(ai_provider, ai_model, ai_key, ai_base_url, prompt_file, output, output_format, verbose))
        return

    if web:
        _start_web(verbose)
        return

    if show_gallery:
        entries = list_gallery_entries()
        if not entries:
            console.print("[yellow]No gallery entries found[/]")
        else:
            console.print(f"[bold cyan]PromptLeak Gallery ({len(entries)} entries)[/]")
            for e in entries:
                console.print(f"  {e['filename']}")
        return

    if schedule or schedule_file:
        _run_scheduler(schedule_file, interval, notify, plugins_dir, verbose)
        return

    if monitor:
        asyncio.run(_run_monitor(monitor_file, monitor_interval, monitor_notify, verbose))
        return

    if grid:
        asyncio.run(_run_grid(grid_role, grid_redis, grid_max_workers, verbose))
        return

    mode_count = sum(1 for x in [url, hunt, batch] if x)
    if mode_count == 0:
        console.print("[red]Error: Provide a URL, --hunt QUERY, --batch FILE, --web, --proxy-mode, --test-prompt, --schedule, --monitor, or --grid[/]")
        sys.exit(1)
    if mode_count > 1:
        console.print("[red]Error: URL, --hunt, and --batch are mutually exclusive[/]")
        sys.exit(1)

    if hunt:
        console.print(f"[bold cyan]PromptLeak[/] hunting for [bold]{hunt}[/] (limit: {limit})")
        asyncio.run(_run_hunt(hunt, limit, output, output_format, fingerprint, verbose))
        return

    if batch:
        console.print(f"[bold cyan]PromptLeak[/] batch mode: [bold]{batch}[/]")
        asyncio.run(_run_batch(batch, output, output_format, headed, proxy, no_cache, screenshot, timeout,
                               fingerprint, verbose))
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
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_key=ai_key,
        ai_base_url=ai_base_url,
        fuzz=fuzz,
        fuzz_count=fuzz_count,
        fuzz_strategies=fuzz_strategies,
        chain=chain,
        chain_strategy=chain_strategy,
        chain_max_turns=max_turns,
        token_probe=token_probe,
        harden=harden,
        harden_output=harden_output,
        track=track,
        intel_db=intel_db,
        intel_report=intel_report,
        intel_timeline=intel_timeline,
        intel_leaderboard=intel_leaderboard,
        vision_probe=vision_probe,
        monitor=monitor,
        monitor_file=monitor_file,
        monitor_interval=monitor_interval,
        monitor_notify=monitor_notify,
        grid_enabled=grid,
        grid_role=grid_role,
        grid_redis=grid_redis,
        grid_max_workers=grid_max_workers,
    )

    engine = ExtractionEngine(config)

    console.print(f"[bold cyan]PromptLeak[/] targeting [bold]{url}[/]")
    console.print(f"[dim]Techniques: {', '.join(config.techniques) if config.techniques else 'all'}[/]")
    if fuzz:
        console.print(f"[dim]Fuzzing enabled: up to {fuzz_count} mutations[/]")
    if fingerprint:
        console.print(f"[dim]Model fingerprinting enabled[/]")

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

    # Run model fingerprinting if requested
    if fingerprint and report.best_result:
        try:
            from .core.fingerprinter import ModelFingerprinter
            from .core.browser import BrowserManager as FBBrowser
            async def do_fingerprint():
                async with FBBrowser(headed=headed, proxy=proxy) as bm:
                    page = await bm.new_page()
                    try:
                        await page.goto(url, wait_until="load", timeout=120000)
                    except Exception:
                        pass
                    await asyncio.sleep(2)
                    target = __import__("promptleak.targets.registry", fromlist=["detect_target"]).detect_target(url)
                    if hasattr(target, "pre_navigation_hook"):
                        await target.pre_navigation_hook(page)
                    fp = ModelFingerprinter()
                    result = await fp.fingerprint(page, target)
                    await bm.close_page(page)
                    return result
            fp_result = asyncio.run(do_fingerprint())
            report_dict["fingerprint"] = fp_result
            console.print(fp.format_result(fp_result))
        except Exception as e:
            if verbose:
                console.print(f"[yellow]Fingerprinting skipped: {e}[/]")

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

    # Share if requested
    if share:
        asyncio.run(_do_share(report_dict, share_method))

    # Post-extraction: Token Probe analysis
    if token_probe and report.best_result:
        try:
            from .core.token_probe import TokenProbe
            tp = TokenProbe()
            tp_report = tp.analyze(report.best_result)
            report_dict["token_probe"] = tp_report
            console.print(tp.format_report(tp_report))
        except Exception as e:
            if verbose:
                console.print(f"[yellow]Token probe skipped: {e}[/]")

    # Post-extraction: Prompt Hardener
    if harden and report.best_result:
        try:
            from .core.hardener import PromptHardener
            ph = PromptHardener()
            hardened = ph.harden(report.best_result)
            report_dict["hardened_prompt"] = hardened
            if harden_output:
                with open(harden_output, "w", encoding="utf-8") as f:
                    f.write(ph.format_harden_report(hardened))
                console.print(f"[green]Hardened prompt written to {harden_output}[/]")
            else:
                console.print(ph.format_harden_report(hardened))
        except Exception as e:
            if verbose:
                console.print(f"[yellow]Hardener skipped: {e}[/]")

    # Post-extraction: Intel Tracker
    if track and report.best_result:
        try:
            from .core.intel_tracker import IntelTracker
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            it = IntelTracker(db_path=intel_db)
            it.record_scan(domain, url, report.best_result, report.confidence, ",".join(report.techniques_used))
            console.print(f"[green]Intel tracked: {domain}[/]")
            if intel_report:
                try:
                    it.export_intel_report(intel_report)
                    console.print(f"[green]Intel report written to {intel_report}[/]")
                except Exception as e:
                    if verbose:
                        console.print(f"[yellow]Intel report export: {e}[/]")
            if intel_timeline:
                try:
                    tl = it.get_timeline(domain)
                    with open(intel_timeline, "w", encoding="utf-8") as f:
                        json.dump(tl, f, indent=2)
                    console.print(f"[green]Intel timeline written to {intel_timeline}[/]")
                except Exception as e:
                    if verbose:
                        console.print(f"[yellow]Intel timeline export: {e}[/]")
            if intel_leaderboard:
                try:
                    lb = it.get_leaderboard("most_changes")
                    with open(intel_leaderboard, "w", encoding="utf-8") as f:
                        json.dump(lb, f, indent=2)
                    console.print(f"[green]Intel leaderboard written to {intel_leaderboard}[/]")
                except Exception as e:
                    if verbose:
                        console.print(f"[yellow]Intel leaderboard export: {e}[/]")
        except Exception as e:
            if verbose:
                console.print(f"[yellow]Intel tracker skipped: {e}[/]")

    if not output:
        console.print("\n[bold]=== EXTRACTION REPORT ===[/]")
        console.print(f"Target: {url}")
        console.print(f"Confidence: {report.confidence:.2f}")
        console.print(f"Techniques: {', '.join(report.techniques_used)}")
        console.print("\n[bold]Best Result:[/]")
        console.print(report.best_result if report.best_result else "[yellow]No prompt extracted[/]")


@main.command()
def serve():
    """Start the PromptLeak web UI server."""
    _start_web(verbose=True)


@main.command()
@click.option("--plugins-dir", default=None, type=click.Path(), help="Plugins directory")
def plugins(plugins_dir: Optional[str]):
    """List all loaded plugins."""
    _list_plugins(plugins_dir)


@main.command()
@click.option("--file", "schedule_file", type=click.Path(exists=True), help="JSON file with job definitions")
@click.option("--interval", default=24, type=int, help="Scan interval in hours")
@click.option("--notify", default=None, help="Notification config JSON or type:url")
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging")
def schedule(file: Optional[str], interval: int, notify: Optional[str], verbose: bool):
    """Run scheduled scans."""
    _run_scheduler(file, interval, notify, None, verbose)


@main.command()
@click.option("--port", default=8080, type=int, help="Proxy port (default: 8080)")
@click.option("--output", default="./captures", type=click.Path(), help="Output directory")
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging")
def proxy(port: int, output: str, verbose: bool):
    """Start MITM proxy mode."""
    _start_proxy(port, output, verbose)


@main.command()
@click.option("--provider", default="openai", help="LLM provider")
@click.option("--model", default="gpt-4o-mini", help="Model name")
@click.option("--key", default=None, help="API key")
@click.option("--base-url", default=None, help="Base URL for provider")
@click.option("--prompt-file", default=None, type=click.Path(exists=True), help="System prompt file")
@click.option("-o", "--output", default=None, type=click.Path(), help="Output file")
@click.option("-f", "--format", "output_format", default="json", type=click.Choice(["json", "markdown", "html"]), help="Output format")
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging")
def test_prompt(provider: str, model: str, key: Optional[str], base_url: Optional[str],
                prompt_file: Optional[str], output: Optional[str], output_format: str, verbose: bool):
    """Test a system prompt for extraction vulnerabilities."""
    setup_logger(verbose)
    asyncio.run(_run_test_prompt(provider, model, key, base_url, prompt_file, output, output_format, verbose))


def _start_web(verbose: bool = False):
    try:
        import uvicorn
        console.print("[bold cyan]Starting PromptLeak Web UI[/] on [bold]http://localhost:8420[/]")
        uvicorn.run("promptleak.web.app:app", host="0.0.0.0", port=8420, log_level="info")
    except ImportError:
        console.print("[red]uvicorn is not installed. Run: pip install uvicorn[/]")
        sys.exit(1)


def _list_plugins(plugins_dir: Optional[str] = None):
    from .plugins.loader import load_plugins, get_loaded_plugins
    loaded = load_plugins(plugins_dir)
    info = get_loaded_plugins()
    console.print("[bold cyan]PromptLeak Plugins[/]")
    console.print(f"  Techniques: {len(info['techniques'])}")
    for t in info["techniques"]:
        console.print(f"    - {t.name} ({t.__doc__ or 'No description'})")
    console.print(f"  Targets: {len(info['targets'])}")
    for t in info["targets"]:
        console.print(f"    - {t.name} ({t.__doc__ or 'No description'})")
    if not info["techniques"] and not info["targets"]:
        console.print("  [yellow]No plugins found[/]")


def _start_proxy(port: int, output_dir: str, verbose: bool):
    try:
        from .proxy.server import start_proxy
        asyncio.run(start_proxy(output_dir=output_dir, port=port, verbose=verbose))
    except ImportError as e:
        if "mitmproxy" in str(e):
            console.print("[red]mitmproxy is required. Install: pip install mitmproxy[/]")
        else:
            console.print(f"[red]Failed to start proxy: {e}[/]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Proxy error: {e}[/]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)


async def _run_test_prompt(provider: str, model: str, api_key: Optional[str], base_url: Optional[str],
                           prompt_file: Optional[str], output: Optional[str], output_format: str, verbose: bool):
    from .core.prompt_tester import PromptTester, format_security_report

    if prompt_file:
        with open(prompt_file, "r", encoding="utf-8") as f:
            system_prompt = f.read().strip()
    elif not sys.stdin.isatty():
        system_prompt = sys.stdin.read().strip()
    else:
        console.print("[yellow]Enter/paste your system prompt (Ctrl+D/Ctrl+Z to finish):[/]")
        system_prompt = sys.stdin.read().strip()

    if not system_prompt:
        console.print("[red]No system prompt provided[/]")
        sys.exit(1)

    console.print(f"[bold cyan]Testing system prompt[/] ({len(system_prompt)} chars)")
    console.print(f"[dim]Provider: {provider}, Model: {model}[/]")

    tester = PromptTester(provider=provider, model=model, api_key=api_key, base_url=base_url)
    report = await tester.test_prompt(system_prompt)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        console.print(f"[green]Report written to {output}[/]")

    console.print(format_security_report(report))


def _run_scheduler(schedule_file: Optional[str], interval: int, notify: Optional[str],
                   plugins_dir: Optional[str], verbose: bool):
    from .core.scheduler import ScanScheduler

    notify_config = None
    if notify:
        try:
            notify_config = json.loads(notify)
        except (json.JSONDecodeError, TypeError):
            if ":" in notify:
                ntype, url = notify.split(":", 1)
                notify_config = {"type": ntype, "url": url}
            else:
                notify_config = {"type": "discord", "url": notify}

    scheduler = ScanScheduler(plugins_dir=plugins_dir)

    if schedule_file:
        count = scheduler.load_from_file(schedule_file)
        console.print(f"[green]Loaded {count} jobs from {schedule_file}[/]")
    else:
        console.print("[yellow]No schedule file provided. Use --schedule-file jobs.json[/]")
        return

    if not scheduler.jobs:
        console.print("[red]No jobs loaded[/]")
        return

    console.print(f"[bold cyan]PromptLeak Scheduler[/] running {len(scheduler.jobs)} jobs")
    for job in scheduler.jobs:
        console.print(f"  [{job.id}] {job.url} every {job.interval_hours}h")
        if job.notify_config:
            console.print(f"    Notify: {job.notify_config.get('type', 'webhook')}")

    asyncio.run(scheduler.run())


async def _do_share(report_dict: dict, method: str):
    from .output.share import ReportSharer
    sharer = ReportSharer(method=method)
    try:
        url = await sharer.share(report_dict, method=method)
        if url:
            console.print(f"[green]Report shared:[/] [bold blue]{url}[/]")
        else:
            console.print("[yellow]Report saved locally (upload failed)[/]")
    except Exception as e:
        console.print(f"[yellow]Share failed: {e}[/]")


async def _run_hunt(query: str, limit: int, output: Optional[str], output_format: str,
                    do_fingerprint: bool, verbose: bool):
    hunter = Hunter(limit=limit, timeout=120)
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
                     screenshot: Optional[str], timeout: int,
                     do_fingerprint: bool, verbose: bool):
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

            if do_fingerprint and report.best_result:
                try:
                    from .core.fingerprinter import ModelFingerprinter
                    from .core.browser import BrowserManager as FBBrowser
                    async with FBBrowser(headed=headed, proxy=proxy) as bm:
                        fpage = await bm.new_page()
                        try:
                            await fpage.goto(target_url, wait_until="load", timeout=120000)
                        except Exception:
                            pass
                        await asyncio.sleep(2)
                        target = __import__("promptleak.targets.registry", fromlist=["detect_target"]).detect_target(target_url)
                        if hasattr(target, "pre_navigation_hook"):
                            await target.pre_navigation_hook(fpage)
                        fp = ModelFingerprinter()
                        fpr = await fp.fingerprint(fpage, target)
                        report_dict["fingerprint"] = fpr
                        await bm.close_page(fpage)
                except Exception:
                    pass

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


async def _run_monitor(monitor_file: Optional[str], interval: int, notify: Optional[str], verbose: bool):
    from .core.monitor import RealtimeMonitor
    from .core.notifications import NotificationManager

    notifier = NotificationManager() if notify else None
    monitor = RealtimeMonitor(notifier=notifier)

    if monitor_file:
        monitor.load_from_file(monitor_file)
    else:
        console.print("[red]Error: --monitor requires --monitor-file with target URLs[/]")
        sys.exit(1)

    if not monitor.targets:
        console.print("[red]No targets loaded from monitor file[/]")
        sys.exit(1)

    console.print(f"[bold cyan]PromptLeak Monitor[/] watching {len(monitor.targets)} targets")
    console.print(f"[dim]Interval: {interval}s per target[/]")
    if notify:
        console.print(f"[dim]Notifications: {notify}[/]")

    await monitor.start()


async def _run_grid(role: str, redis_url: str, max_workers: int, verbose: bool):
    if role == "master":
        from .grid.master import GridMaster
        master = GridMaster(redis_url=redis_url, max_workers=max_workers)
        console.print(f"[bold cyan]PromptLeak Grid Master[/] (max workers: {max_workers})")
        console.print(f"[dim]Redis: {redis_url}[/]")
        await master.start()
    elif role == "worker":
        from .grid.worker import GridWorker
        worker = GridWorker(master_url=redis_url)
        console.print(f"[bold cyan]PromptLeak Grid Worker[/] ({worker.worker_id})")
        console.print(f"[dim]Redis: {redis_url}[/]")
        await worker.start()


def _conf_color(conf: float) -> str:
    if conf >= 0.7: return "#3fb950"
    if conf >= 0.3: return "#d29922"
    return "#f85149"


if __name__ == "__main__":
    main()
