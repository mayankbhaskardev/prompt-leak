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
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    ai_key: Optional[str] = None
    ai_base_url: Optional[str] = None
    fuzz: bool = False
    fuzz_count: int = 500
    fuzz_strategies: Optional[str] = None
    chain: bool = False
    chain_strategy: str = "auto"
    chain_max_turns: int = 5
    token_probe: bool = False
    harden: bool = False
    harden_output: Optional[str] = None
    track: bool = False
    intel_db: Optional[str] = None
    intel_report: Optional[str] = None
    intel_timeline: Optional[str] = None
    intel_leaderboard: Optional[str] = None
    vision_probe: bool = False
    monitor: bool = False
    monitor_file: Optional[str] = None
    monitor_interval: int = 300
    monitor_notify: Optional[str] = None
    grid_enabled: bool = False
    grid_role: str = "master"
    grid_redis: str = "redis://localhost:6379/0"
    grid_max_workers: int = 10
    inject: bool = False
    inject_test: Optional[str] = None
    compare: bool = False
    compare_file_a: Optional[str] = None
    compare_file_b: Optional[str] = None
    compare_label_a: str = "Prompt A"
    compare_label_b: str = "Prompt B"
    report_type: str = "standard"
    report_company: str = "PromptLeak Security"
    report_assessor: str = "Automated Assessment"
    report_logo: str = ""
    obfuscate: bool = False
    obfuscate_file: Optional[str] = None
    obfuscate_strategy: Optional[str] = None
    obfuscate_all: bool = False
    judge: Optional[str] = None
    judge_extracted_file: Optional[str] = None
    judge_response_file: Optional[str] = None
    waf_test: bool = False
    shell: bool = False
    shell_with: Optional[str] = None
