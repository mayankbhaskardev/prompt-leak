"""MITM reverse proxy — capture system prompts from any AI traffic passing through."""
from __future__ import annotations

import asyncio
import json
import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from mitmproxy import http
    from mitmproxy.options import Options
    from mitmproxy.tools.dump import DumpMaster
    HAS_MITMPROXY = True
except ImportError:
    HAS_MITMPROXY = False
    # Placeholder so type hints don't fail
    http = type("http", (), {"HTTPFlow": object})()

logger = logging.getLogger("promptleak")

PROMPT_INDICATORS = [
    r"(?i)you are (a|an|the) ",
    r"(?i)your (role|task|purpose|goal|mission|job) is",
    r"(?i)(always|never|must|shall|will|do not|cannot|should not|do not)",
    r"\n\d+[\.\)]\s+[A-Z]",
    r"(?i)your response (should|must|will|needs to|ought to)",
    r"(?i)if the user (asks|says|wants|requests|provides|mentions)",
    r"(?i)(refuse|decline|avoid|forbidden|prohibited)",
    r"(?i)you (have access to|can use|are equipped with|are configured)",
    r"(?i)respond (in|with|using|by|only|as)",
    r"(?i)(first|second|third|primary|secondary) (priority|rule|guideline|directive|instruction)",
    r"(?i)do not (reveal|disclose|share|mention|output|print|repeat) (your|the|these|any)",
    r"(?i)system (prompt|message|instruction|configuration)",
    r"(?i)context window",
    r"(?i)knowledge cutoff",
    r"(?i)current date",
    r"(?i)you are an? (ai|assistant|language model|chatbot|expert)",
    r"(?i)safety guidelines?",
    r"(?i)content (policy|guidelines|restrictions|filter)",
    r"(?i)(helpful|harmless|honest|safe)",
]

PROMPT_KEY_NAMES = [
    "system_prompt", "system_prompt_updated", "system", "instructions",
    "prompt", "context", "system_message", "system_msg",
    "custom_instructions", "behavior", "persona", "character_system_prompt",
    "definition", "template", "system_template", "prompt_template",
    "configuration", "config", "system_config",
]


class PromptCaptureAddon:
    """mitmproxy addon that captures system prompts from AI traffic."""

    def __init__(self, output_dir: str = "./captures", verbose: bool = False):
        self.output_dir = output_dir
        self.verbose = verbose
        self.captures: list[dict] = []
        self._capture_count = 0
        self._ai_domains_seen = set()

    def request(self, flow: http.HTTPFlow):
        """Capture requests to common AI API endpoints."""
        url = flow.request.pretty_url
        if self._is_ai_endpoint(url):
            self._ai_domains_seen.add(flow.request.host)
            if self.verbose:
                logger.info(f"[proxy] AI request: {flow.request.method} {url[:120]}")

            body = flow.request.get_text(strict=False)
            if body:
                prompt = self._extract_from_request(body)
                if prompt:
                    self._capture_prompt(flow, prompt, source="request")

    def response(self, flow: http.HTTPFlow):
        """Capture system prompts from AI API responses."""
        url = flow.request.pretty_url
        if not self._is_ai_endpoint(url):
            return

        try:
            body = flow.response.get_text(strict=False)
            if not body or len(body) < 50:
                return

            prompt = self._extract_from_response(body)
            if prompt:
                self._capture_prompt(flow, prompt, source="response")
            elif self._contains_system_prompt(body):
                extracted = self._extract_prompt_from_body(body)
                if extracted:
                    self._capture_prompt(flow, extracted, source="response_heuristic")
        except Exception as e:
            if self.verbose:
                logger.debug(f"[proxy] Error processing response: {e}")

    def _is_ai_endpoint(self, url: str) -> bool:
        """Check if URL looks like an AI API endpoint."""
        ai_patterns = [
            r"\.openai\.com/v\d+/chat/completions",
            r"\.openai\.com/v\d+/completions",
            r"api\.anthropic\.com/v\d+/messages",
            r"api\.anthropic\.com/v\d+/complete",
            r"generativelanguage\.googleapis\.com",
            r"api\.google\.com/gemini",
            r"api\.deepseek\.com",
            r"api\.mistral\.ai",
            r"api\.together\.xyz",
            r"api\.cohere\.ai",
            r"api\.groq\.com",
            r"api\.perplexity\.ai",
            r"chat\.ai\.com/api",
            r"/v1/chat/completions",
            r"/v1/completions",
            r"/api/chat",
            r"/api/generate",
            r"/api/conversation",
            r"/graphql.*chat",
            r"/v1/messages",
        ]
        return any(re.search(p, url, re.IGNORECASE) for p in ai_patterns)

    def _extract_from_request(self, body: str) -> Optional[str]:
        """Extract system prompt from request body."""
        try:
            data = json.loads(body)
            if isinstance(data, dict):
                msgs = data.get("messages", data.get("contents", []))
                if isinstance(msgs, list):
                    for msg in msgs:
                        role = ""
                        content = ""
                        if isinstance(msg, dict):
                            role = msg.get("role", "")
                            content = msg.get("content", "")
                            if isinstance(content, list):
                                content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
                        if role in ("system", "developer", "context") and isinstance(content, str) and len(content) > 50:
                            return content
                if data.get("system"):
                    return str(data["system"])
        except (json.JSONDecodeError, AttributeError):
            pass
        return None

    def _extract_from_response(self, body: str) -> Optional[str]:
        """Extract system prompt from response body."""
        try:
            data = json.loads(body)
            if isinstance(data, dict):
                choices = data.get("choices", [])
                if isinstance(choices, list) and choices:
                    choice = choices[0]
                    msg = choice.get("message", choice.get("delta", {}))
                    if isinstance(msg, dict):
                        content = msg.get("content", msg.get("text", ""))
                        system_fingerprint = data.get("system_fingerprint", "")
                        if isinstance(content, str) and len(content) > 100:
                            if self._contains_system_prompt(content):
                                return content
                if "system_prompt" in data:
                    return str(data["system_prompt"])
        except (json.JSONDecodeError, AttributeError):
            pass
        return None

    def _contains_system_prompt(self, text: str) -> bool:
        """Check if text contains what looks like a system prompt."""
        matches = sum(1 for p in PROMPT_INDICATORS if re.search(p, text[:2000]))
        return matches >= 3 and len(text) > 200

    def _extract_prompt_from_body(self, body: str) -> Optional[str]:
        """Try to isolate the system prompt from response body."""
        try:
            data = json.loads(body)
            return self._find_prompt_in_dict(data)
        except json.JSONDecodeError:
            match = re.search(r'(?:system_prompt|instructions|prompt)\s*[:=]\s*"([^"]+)"', body[:5000])
            if match:
                return match.group(1)
            return None

    def _find_prompt_in_dict(self, obj, depth: int = 0) -> Optional[str]:
        """Recursively search for system prompt keys in nested dict."""
        if depth > 5:
            return None
        if isinstance(obj, dict):
            for k, v in obj.items():
                if any(pk in k.lower() for pk in PROMPT_KEY_NAMES) and isinstance(v, str) and len(v) > 50:
                    return v
                result = self._find_prompt_in_dict(v, depth + 1)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self._find_prompt_in_dict(item, depth + 1)
                if result:
                    return result
        return None

    def _capture_prompt(self, flow: http.HTTPFlow, prompt: str, source: str = "response"):
        """Save a captured prompt."""
        self._capture_count += 1
        capture = {
            "id": self._capture_count,
            "url": flow.request.pretty_url,
            "method": flow.request.method,
            "host": flow.request.host,
            "path": flow.request.path,
            "timestamp": datetime.utcnow().isoformat(),
            "source": source,
            "system_prompt": prompt,
            "prompt_length": len(prompt),
            "response_size": len(flow.response.get_text(strict=False)) if flow.response else 0,
            "status_code": flow.response.status_code if flow.response else 0,
            "request_headers": dict(flow.request.headers),
            "response_headers": dict(flow.response.headers) if flow.response else {},
        }
        self.captures.append(capture)
        self._save_capture(capture)
        self._print_alert(capture)

    def _print_alert(self, capture: dict):
        """Print a real-time alert when a prompt is captured."""
        print(f"{'=' * 60}")
        print(f"🔒 PROMPT CAPTURED VIA PROXY")
        print(f"   ID: {capture['id']}")
        print(f"   URL: {capture['url'][:120]}")
        print(f"   Source: {capture['source']}")
        print(f"   Length: {capture['prompt_length']} chars")
        print(f"   Preview: {capture['system_prompt'][:120]}...")
        print(f"{'=' * 60}")

    def _save_capture(self, capture: dict):
        """Save capture to file."""
        Path(self.output_dir).mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        domain = capture["host"].replace(".", "_")
        filename = f"{timestamp}_{domain}_capture_{capture['id']}.json"
        filepath = Path(self.output_dir) / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(capture, f, indent=2, default=str)

    def generate_summary(self) -> str:
        """Generate a summary HTML report of all captures."""
        if not self.captures:
            return "<html><body><h1>No prompts captured</h1></body></html>"

        rows = ""
        for cap in self.captures:
            preview = cap["system_prompt"][:200]
            rows += f"""
            <tr>
                <td>{cap['id']}</td>
                <td>{cap['timestamp']}</td>
                <td>{cap['host']}</td>
                <td>{cap['source']}</td>
                <td>{cap['prompt_length']}</td>
                <td><pre style="max-height:100px;overflow:auto;font-size:11px;">{preview}</pre></td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>PromptLeak Proxy Captures</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: #0d1117; color: #c9d1d9; font-family: -apple-system, sans-serif; padding: 20px; }}
    h1 {{ color: #58a6ff; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
    th {{ background: #21262d; color: #8b949e; text-align: left; padding: 10px; border-bottom: 2px solid #30363d; }}
    td {{ padding: 10px; border-bottom: 1px solid #21262d; }}
    tr:hover {{ background: #1c2128; }}
</style>
</head>
<body>
    <h1>PromptLeak Proxy — Captures ({len(self.captures)})</h1>
    <table>
        <tr><th>#</th><th>Timestamp</th><th>Host</th><th>Source</th><th>Length</th><th>Preview</th></tr>
        {rows}
    </table>
</body>
</html>"""
        return html


async def start_proxy(output_dir: str = "./captures", port: int = 8080,
                      verbose: bool = False, web_mode: bool = False):
    """Start the MITM proxy server."""
    if not HAS_MITMPROXY:
        raise ImportError(
            "mitmproxy is required for proxy mode. Install with: pip install mitmproxy"
        )

    os.makedirs(output_dir, exist_ok=True)

    addon = PromptCaptureAddon(output_dir=output_dir, verbose=verbose)

    opts = Options(
        listen_host="0.0.0.0",
        listen_port=port,
    )

    master = DumpMaster(opts)
    master.addons.add(addon)

    print(f"\n{'=' * 60}")
    print(f"🔒 PromptLeak Proxy Mode")
    print(f"   Listening on: http://0.0.0.0:{port}")
    print(f"   Output dir:   {output_dir}")
    print(f"   Configure your browser/device to use this proxy.")
    print(f"   Press Ctrl+C to stop and generate summary.")
    print(f"{'=' * 60}\n")

    try:
        await master.run()
    except KeyboardInterrupt:
        print("\n\nGenerating summary report...")
        summary_html = addon.generate_summary()
        summary_path = os.path.join(output_dir, "summary.html")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary_html)
        print(f"Summary saved to: {summary_path}")
        print(f"Total captures: {len(addon.captures)}")
        print(f"AI domains seen: {len(addon._ai_domains_seen)}")
    finally:
        master.shutdown()
