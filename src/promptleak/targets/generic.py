"""Generic fallback target using heuristic selectors."""
from .base import Target


class GenericTarget(Target):
    name = "generic"

    @property
    def domain_patterns(self) -> list[str]:
        return [r".*"]

    @property
    def chat_input_selector(self) -> str:
        return "textarea, input[type='text'], div[contenteditable], [role='textbox']"

    @property
    def send_button_selector(self) -> str:
        return "button[type='submit'], button[aria-label*='send' i], button[aria-label*='Submit' i]"

    @property
    def response_selector(self) -> str:
        return "[class*='message'], [class*='response'], [class*='assistant'], [data-role='assistant']"

    @property
    def wait_strategy(self) -> str:
        return "response_appears"

    @property
    def wait_timeout(self) -> int:
        return 30
