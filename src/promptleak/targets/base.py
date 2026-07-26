"""Abstract base class for target definitions."""
import re
from abc import ABC, abstractmethod
from typing import Optional


class Target(ABC):
    name: str = "generic"

    @property
    @abstractmethod
    def domain_patterns(self) -> list[str]:
        ...

    @property
    def chat_input_selector(self) -> Optional[str]:
        return None

    @property
    def send_button_selector(self) -> Optional[str]:
        return None

    @property
    def response_selector(self) -> Optional[str]:
        return None

    @property
    def wait_strategy(self) -> str:
        return "response_appears"

    @property
    def wait_timeout(self) -> int:
        return 30

    async def pre_navigation_hook(self, page) -> None:
        pass

    async def post_send_hook(self, page) -> None:
        pass

    async def is_logged_in(self, page) -> bool:
        return True

    def matches(self, url: str) -> bool:
        for pattern in self.domain_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False
