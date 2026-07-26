"""Target definition for ChatGPT (chat.openai.com / chatgpt.com)."""
from .base import Target


class ChatGPTTarget(Target):
    name = "chatgpt"

    @property
    def domain_patterns(self) -> list[str]:
        return [r"chat\.openai\.com", r"chatgpt\.com"]

    @property
    def chat_input_selector(self) -> str:
        return "textarea#prompt-textarea"

    @property
    def send_button_selector(self) -> str:
        return 'button[data-testid="send-button"]'

    @property
    def response_selector(self) -> str:
        return 'div[data-message-author-role="assistant"]'

    @property
    def wait_strategy(self) -> str:
        return "response_appears"

    @property
    def wait_timeout(self) -> int:
        return 30

    async def pre_navigation_hook(self, page) -> None:
        try:
            banner = await page.query_selector("button:has-text('Accept')")
            if banner:
                await banner.click()
        except Exception:
            pass
