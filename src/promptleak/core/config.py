from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExtractionConfig:
    url: str
    techniques: list[str] = field(default_factory=lambda: [])
    output_path: Optional[str] = None
    output_format: str = "json"
    headed: bool = False
    proxy: Optional[str] = None
    no_cache: bool = False
    screenshot_path: Optional[str] = None
    timeout: int = 600
    gallery: bool = False
    verbose: bool = False
