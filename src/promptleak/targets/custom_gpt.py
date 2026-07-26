"""Target definition for Custom GPTs on chatgpt.com/g/ URLs."""
import asyncio
import logging

from .base import Target

logger = logging.getLogger("promptleak")


class CustomGPTTarget(Target):
    name = "custom_gpt"

    @property
    def domain_patterns(self) -> list[str]:
        return [r"chatgpt\.com/g/"]

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
            await page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        await asyncio.sleep(2)

        try:
            btn = await page.query_selector("button:has-text('Accept')")
            if btn:
                await btn.click()
                await asyncio.sleep(1)
        except Exception:
            pass

        try:
            about_btn = await page.query_selector('button[aria-label*="Shared GPT"], button[aria-label*="GPT details"]')
            if about_btn:
                await about_btn.click()
                await asyncio.sleep(2)
                for sel in ["div:has-text('Instructions')", "div:has-text('Description')", '[class*="instructions"]', '[class*="description"]']:
                    try:
                        el = await page.query_selector(sel)
                        if el:
                            text = await el.inner_text()
                            if text and len(text) > 20:
                                logger.info(f"Captured GPT info panel text ({len(text)} chars)")
                                self._captured_about_text = text
                                return
                    except Exception:
                        pass
        except Exception:
            pass

        self._captured_about_text = None

    async def post_send_hook(self, page) -> None:
        pass

    async def is_logged_in(self, page) -> bool:
        return False

    def get_captured_about_text(self) -> str:
        return getattr(self, "_captured_about_text", None) or ""
