"""Auto-detect which Target class to use based on URL."""
from .base import Target
from .custom_gpt import CustomGPTTarget
from .chatgpt import ChatGPTTarget
from .claude import ClaudeTarget
from .gemini import GeminiTarget
from .perplexity import PerplexityTarget
from .generic import GenericTarget

_registered_targets: list[type[Target]] = [
    CustomGPTTarget,
    ChatGPTTarget,
    ClaudeTarget,
    GeminiTarget,
    PerplexityTarget,
    GenericTarget,
]


def register_target(target_cls: type[Target]) -> None:
    _registered_targets.insert(0, target_cls)


def detect_target(url: str) -> Target:
    for cls in _registered_targets:
        instance = cls()
        if instance.matches(url):
            return instance
    return GenericTarget()
