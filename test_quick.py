"""Quick verification that all imports and basic structures work."""
import sys

print("[1] Testing imports...")

from promptleak.core.config import ExtractionConfig
print("    config.py OK")

from promptleak.core.cache import get_cached, set_cached, get_all_gallery_entries
print("    cache.py OK")

from promptleak.core.engine import ExtractionEngine, ExtractionReport, TECHNIQUE_MAP
print("    engine.py OK")

from promptleak.core.browser import BrowserManager
print("    browser.py OK")

from promptleak.targets.registry import detect_target, register_target
print("    registry.py OK")

from promptleak.targets.base import Target
from promptleak.targets.chatgpt import ChatGPTTarget
from promptleak.targets.claude import ClaudeTarget
from promptleak.targets.gemini import GeminiTarget
from promptleak.targets.perplexity import PerplexityTarget
from promptleak.targets.generic import GenericTarget
print("    targets OK")

from promptleak.techniques.base import ExtractionTechnique, TechniqueResult
from promptleak.techniques.direct_ask import DirectAskTechnique
from promptleak.techniques.role_confusion import RoleConfusionTechnique
from promptleak.techniques.translation_leak import TranslationLeakTechnique
from promptleak.techniques.continuation_leak import ContinuationLeakTechnique
from promptleak.techniques.encoding_trick import EncodingTrickTechnique
from promptleak.techniques.token_analysis import TokenAnalysisTechnique
print("    techniques OK")

from promptleak.output.formatter import clean_extraction, score_confidence, deduplicate, consensus_boost, strip_markdown
from promptleak.output.export import export_json, export_markdown, export_html, export_report
from promptleak.output.gallery import add_to_gallery, list_gallery
print("    output OK")

from promptleak.utils.stealth import random_delay, random_viewport, get_random_user_agent, inject_stealth_scripts
from promptleak.utils.logger import setup_logger, console
print("    utils OK")

print()
print("[2] Instantiating ExtractionConfig...")
config = ExtractionConfig(url="https://chat.openai.com")
assert config.url == "https://chat.openai.com"
assert config.timeout == 120
assert config.output_format == "json"
print("    OK")

print()
print("[3] Testing target detection...")
for test_url, expected in [
    ("https://chat.openai.com", "chatgpt"),
    ("https://chatgpt.com", "chatgpt"),
    ("https://claude.ai", "claude"),
    ("https://gemini.google.com", "gemini"),
    ("https://www.perplexity.ai", "perplexity"),
    ("https://some-random-chat.site", "generic"),
]:
    target = detect_target(test_url)
    status = "OK" if target.name == expected else f"FAIL (got {target.name})"
    print(f"    {test_url} -> {target.name} {status}")
    assert target.name == expected, f"Expected {expected}, got {target.name}"

print()
print("[4] Listing registered techniques...")
for name, cls in TECHNIQUE_MAP.items():
    instance = cls()
    print(f"    {name}: {instance.__class__.__name__}")
    assert instance.name == name

print()
print("[5] Testing formatter functions...")
text = "You are an AI assistant. You must be helpful."
score = score_confidence(text)
assert score > 0.0, f"Expected positive score, got {score}"
cleaned = clean_extraction("prompt? I was told: be helpful.", "prompt?")
assert "prompt?" not in cleaned
deduped = deduplicate([("hello world", "a", 0.5), ("hello world!", "b", 0.5)])
assert len(deduped) == 1
print("    OK")

print()
print("ALL IMPORTS OK")
