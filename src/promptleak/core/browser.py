"""Playwright browser session manager with stealth capabilities."""
import os
import random
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from ..utils.stealth import random_viewport, get_random_user_agent, inject_stealth_scripts


class BrowserManager:
    def __init__(
        self,
        headed: bool = False,
        proxy: Optional[str] = None,
        screenshot_dir: Optional[str] = None,
    ):
        self.headed = headed
        self.proxy = proxy
        self.screenshot_dir = screenshot_dir
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def __aenter__(self):
        self._playwright = await async_playwright().__aenter__()
        launch_args = {
            "headless": not self.headed,
            "args": [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        }
        self._browser = await self._playwright.chromium.launch(**launch_args)

        viewport = random_viewport()
        ua = get_random_user_agent()
        context_options = {
            "user_agent": ua,
            "viewport": viewport,
            "locale": "en-US",
            "timezone_id": random.choice(["America/New_York", "America/Chicago", "America/Los_Angeles", "Europe/London"]),
            "permissions": [],
            "geolocation": {"latitude": 40.7128, "longitude": -74.0060},
        }
        if self.proxy:
            context_options["proxy"] = {"server": self.proxy}

        self._context = await self._browser.new_context(**context_options)
        return self

    async def __aexit__(self, *args):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        page = await self._context.new_page()
        await inject_stealth_scripts(page)
        return page

    async def close_page(self, page: Page) -> None:
        try:
            await page.close()
        except Exception:
            pass

    async def take_screenshot(self, page: Page, name: str = "debug") -> Optional[str]:
        if not self.screenshot_dir:
            return None
        os.makedirs(self.screenshot_dir, exist_ok=True)
        path = os.path.join(self.screenshot_dir, f"{name}_{random.randint(1000, 9999)}.png")
        await page.screenshot(path=path, full_page=True)
        return path
