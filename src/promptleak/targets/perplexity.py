"""Target definition for Perplexity AI (perplexity.ai)."""
import asyncio

from .base import Target


class PerplexityTarget(Target):
    name = "perplexity"

    @property
    def domain_patterns(self) -> list[str]:
        return [r"perplexity\.ai"]

    @property
    def chat_input_selector(self) -> str:
        return "div#ask-input"

    @property
    def send_button_selector(self) -> str:
        return None

    @property
    def response_selector(self) -> str:
        return "main div.prose"

    @property
    def wait_strategy(self) -> str:
        return "response_appears"

    @property
    def wait_timeout(self) -> int:
        return 15

    async def pre_navigation_hook(self, page) -> None:
        try:
            await page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass

        for _ in range(30):
            try:
                title = await page.title()
                if "Just a moment" not in title:
                    break
            except Exception:
                pass
            await asyncio.sleep(2)

        try:
            await page.wait_for_selector(self.chat_input_selector, timeout=20000)
        except Exception:
            pass

        if not await page.query_selector(self.chat_input_selector):
            try:
                await page.reload(wait_until="domcontentloaded")
                await asyncio.sleep(5)
                await page.wait_for_selector(self.chat_input_selector, timeout=30000)
            except Exception:
                pass

        try:
            btn = await page.query_selector("button:has-text('Allow all')")
            if btn:
                await btn.click()
                await asyncio.sleep(1)
        except Exception:
            pass
