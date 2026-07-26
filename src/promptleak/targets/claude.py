"""Target definition for Claude (claude.ai)."""
from .base import Target


class ClaudeTarget(Target):
    name = "claude"

    @property
    def domain_patterns(self) -> list[str]:
        return [r"claude\.ai"]

    @property
    def chat_input_selector(self) -> str:
        return 'div[contenteditable="true"].ProseMirror'

    @property
    def send_button_selector(self) -> str:
        return 'button[aria-label="Send Message"]'

    @property
    def response_selector(self) -> str:
        return 'div[data-testid^="conversation-turn-"]'

    @property
    def wait_strategy(self) -> str:
        return "typing_stops"

    @property
    def wait_timeout(self) -> int:
        return 40
