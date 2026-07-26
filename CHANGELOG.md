# Changelog

All notable changes to prompt-leak will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [5.0.0] - 2025-01-XX

### Added
- **Injection Sandbox**: 14 prompt injection tests with severity scoring (LOW/MEDIUM/HIGH/CRITICAL)
- **WAF Tester**: Detect and evaluate prompt injection Web Application Firewalls
- **Interactive Shell**: Reverse shell for prompt injection — persistent injected context
- **Obfuscation Engine**: 10 bypass strategies (unicode confusables, zero-width, encoding chains, etc.)
- **Prompt Comparison Engine**: 7-dimension deep comparison (semantic, structural, topic, tone, template)
- **LLM-as-Judge**: Nuanced evaluation via LLM (extraction quality, hardening effectiveness, injection severity, prompt quality)
- **Professional Reports**: Consultancy-grade HTML with cover page, risk matrix, remediation roadmap, A4 print-ready
- **Conversation Chain Engine**: Multi-turn state machine with 5 pre-built strategies (trust escalation, authority cascade, fragment assembly, philosophical trap, emotional manipulation)
- **Token-Level Probe**: Context window mapping, prompt position/length estimation, partial content extraction
- **Prompt Hardener**: Auto-patch vulnerabilities with targeted rules, re-test to verify improvement
- **Prompt Tester**: Test your own prompts against extraction locally via LLM API
- **GitHub Action**: CI/CD integration — fail builds on vulnerable prompts
- **Competitor Intelligence Tracker**: SQLite database for tracking prompt changes, model migrations, timelines
- **Distributed Grid**: Master/worker architecture via Redis
- **Vision Probe**: Image-based system prompt detection, hidden text/element scanning
- **Real-Time Monitor**: Continuous monitoring with instant change alerts (Discord, Telegram, Slack)
- **Model Fingerprinting**: Identify underlying LLM (GPT-4, Claude, Gemini, Llama, etc.) by response patterns
- **AI Payload Generator**: LLM meta-generates novel extraction payloads
- **Prompt Fuzzer**: 500+ mutations across 8 strategies
- **MITM Proxy Mode**: Capture prompts from any traffic
- **Shareable Reports**: Upload to dpaste/transfer.sh/0x0
- **Web UI**: FastAPI dashboard with WebSocket real-time progress
- **Plugin System**: Drop .py files for custom techniques/targets
- **22+ Target Definitions**: ChatGPT, Claude, Gemini, DeepSeek, Perplexity, Poe, HuggingChat, You.com, Phind, Copilot, Groq, Mistral, Cohere, Together, Anthropic Console, Generic
- **Adaptive Rate Limiting**: Auto-backoff with circuit breaker pattern
- **Scheduled Scans**: Recurring scans with change detection and webhook notifications

### Changed
- Complete CLI rewrite with 30+ options across 10+ modes
- Confidence scoring overhaul with 20+ weighted indicators
- HTML reports redesigned with dark theme

## [4.0.0] - 2025-01-XX

### Added
- Conversation chain engine with 5 strategies
- Token-level context window probing
- Automated prompt hardening engine
- Competitor intelligence tracker
- Distributed scanning grid (Redis)
- Multi-modal vision probe
- Real-time monitoring mode

## [3.0.0] - 2025-01-XX

### Added
- AI-powered payload generator
- Prompt fuzzer (500+ mutations)
- Model fingerprinting
- Defensive prompt testing
- GitHub Action for CI/CD
- MITM reverse proxy mode
- Shareable report links

## [2.0.0] - 2025-01-XX

### Added
- Web UI (FastAPI + vanilla JS)
- Plugin system
- 15 new target definitions
- Adaptive rate limiting with circuit breaker
- Scheduled scans with notifications
- Batch mode with diff tracking
- API probe technique

## [1.0.0] - 2025-01-XX

### Added
- Initial release
- 6 extraction techniques (direct ask, role confusion, translation leak, continuation leak, encoding trick, token analysis)
- Auto-discovery hunt mode via DuckDuckGo
- Batch scanning
- HTML/JSON/Markdown export
- Confidence scoring
- Stealth browser with anti-detection
- SQLite cache
- 7 initial targets (ChatGPT, Claude, Gemini, Perplexity, Custom GPT, and generic fallback)
