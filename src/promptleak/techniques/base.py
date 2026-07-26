"""Abstract base class for extraction techniques."""
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import random

from ..utils.stealth import random_delay


class TechniqueAborted(Exception):
    pass


@dataclass
class TechniqueResult:
    technique_name: str
    success: bool
    raw_output: str
    cleaned_output: str
    confidence: float = 0.0
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


SIGNUP_WALL_PHRASES = [
    "sign up",
    "sign in",
    "create an account",
    "log in",
    "repeat your request",
    "please log in",
    "please sign in",
]


def _is_signup_wall(text: str) -> bool:
    lower = text.lower()
    for phrase in SIGNUP_WALL_PHRASES:
        if phrase in lower:
            return True
    return False


class ExtractionTechnique(ABC):
    name: str = "base"
    last_prompt: str = ""
    _consecutive_failures: int = 0
    _max_consecutive_failures: int = 3

    @abstractmethod
    async def execute(self, page, target) -> TechniqueResult:
        ...

    async def _count_responses(self, page, target) -> int:
        try:
            elements = await page.query_selector_all(target.response_selector)
            return len(elements)
        except Exception:
            return 0

    async def _wait_for_response(self, page, target) -> None:
        current_count = await self._count_responses(page, target)
        timeout = target.wait_timeout

        for _ in range(timeout):
            await asyncio.sleep(1)
            try:
                new_count = await self._count_responses(page, target)
                if new_count > current_count:
                    return
            except Exception:
                pass

            body_text = await page.evaluate("document.body.innerText")
            if len(body_text) > 500:
                if current_count > 0:
                    return

    async def _get_latest_response(self, page, target) -> str:
        try:
            elements = await page.query_selector_all(target.response_selector)
            if elements:
                el = elements[-1]
                text = await el.inner_text()
                if text.strip():
                    return text.strip()
        except Exception:
            pass
        try:
            text = await page.evaluate("document.body.innerText")
            return text
        except Exception:
            return ""

    async def _check_input_exists(self, page, target) -> bool:
        try:
            el = await page.wait_for_selector(
                target.chat_input_selector, timeout=5000
            )
            return el is not None
        except Exception:
            return False

    async def _send_prompt(self, page, target, prompt: str, delay_range: tuple = (20, 60)) -> str:
        self.last_prompt = prompt
        exists = await self._check_input_exists(page, target)
        if not exists:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._max_consecutive_failures:
                raise TechniqueAborted(f"Input '{target.chat_input_selector}' not found after {self._consecutive_failures} attempts")
            return ""
        self._consecutive_failures = 0

        input_el = await page.query_selector(target.chat_input_selector)
        if not input_el:
            return ""
        try:
            await input_el.click()
            await input_el.fill("")
        except Exception:
            pass
        await page.keyboard.type(prompt, delay=random.randint(*delay_range))

        if target.send_button_selector:
            btn = await page.query_selector(target.send_button_selector)
            if btn:
                await btn.click()
        else:
            await page.keyboard.press("Enter")

        await self._wait_for_response(page, target)
        response = await self._get_latest_response(page, target)

        return response
