"""Target definition for Google Gemini (gemini.google.com)."""
from .base import Target


class GeminiTarget(Target):
    name = "gemini"

    @property
    def domain_patterns(self) -> list[str]:
        return [r"gemini\.google\.com"]

    @property
    def chat_input_selector(self) -> str:
        return 'div.ql-editor[contenteditable="true"]'

    @property
    def send_button_selector(self) -> str:
        return 'button[aria-label*="Send"]'

    @property
    def response_selector(self) -> str:
        return "model-response"

    @property
    def wait_strategy(self) -> str:
        return "response_appears"

    @property
    def wait_timeout(self) -> int:
        return 30

    async def pre_navigation_hook(self, page) -> None:
        try:
            btn = await page.query_selector("button:has-text('Accept all')")
            if btn:
                await btn.click()
        except Exception:
            pass
