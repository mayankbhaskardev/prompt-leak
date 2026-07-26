# 🔓 PromptLeak

Extract hidden system prompts from any AI chat application

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/mayankbhaskardev/prompt-leak?style=social)](https://github.com/mayankbhaskardev/prompt-leak)

**Found 200+ AI apps leaking their system prompts. Open source, free, no API key needed.**

<!-- DEMO GIF HERE -->

## What It Does

- **System prompts are the new API keys.** Every AI chat app embeds a hidden prompt that controls tone, behavior, and content policies. Most don't protect them.
- **PromptLeak automates extraction.** It uses 7 adversarial techniques — direct asking, role confusion, translation leakage, and more — to recover those prompts in seconds.
- **No API keys, no accounts, no subscriptions.** Just a URL and a browser. Point it at any AI chat app and get back the extracted prompt with a confidence score.
- **Built for security researchers.** Hunt mode discovers vulnerable targets automatically via search dorks. Batch mode processes hundreds of URLs. Diff tracking shows when prompts change.

## Installation

```bash
pip install prompt-leak
playwright install chromium
```

## Quick Start

**Single target — extract from one app:**

```bash
pleak https://free.ai --headed -f markdown -o report.md
```

**Hunt mode — discover and extract from multiple targets:**

```bash
pleak --hunt "free AI chatbot" --limit 10 -f html -o hunt_results.html
```

**Batch mode — process a file of URLs:**

```bash
echo "https://free.ai" > targets.txt
echo "https://you.com" >> targets.txt
pleak --batch targets.txt -f html -o results/
```

## Techniques

| Technique | How It Works | Success Rate |
|-----------|-------------|--------------|
| `api_probe` | Intercepts XHR/fetch network traffic to discover API endpoints and replay extraction prompts | Medium — works on apps with exposed internal APIs |
| `direct_ask` | Simply asks the AI to reveal its system prompt directly | High — many models comply before refusal kicks in |
| `role_confusion` | Tricks the AI by impersonating a system administrator or developer requesting configuration | High — exploits role-based trust |
| `translation_leak` | Asks the AI to translate its initial instructions into another language | Medium — some models output the prompt as translation context |
| `continuation_leak` | Provides partial text and asks the AI to continue, targeting the prompt prefix | High — exploits autoregressive completion behavior |
| `encoding_trick` | Obfuscates the request in base64/hex and asks the AI to decode and repeat | Medium — bypasses simple keyword filters |
| `token_analysis` | Analyzes token-by-token output to identify prompt boundaries and estimate size | Low — indirect, useful when other techniques are blocked |

## Features

- 🔍 **Auto-Discovery** — Hunt mode finds vulnerable targets via DuckDuckGo search with built-in dork templates
- 🎯 **Custom GPT Support** — Extracts from ChatGPT custom GPTs by clicking through the info panel
- 📡 **API Probe** — Discovers and replays against undocumented internal API endpoints
- 📊 **Confidence Scoring** — Weighted indicator system that classifies results as LEAKED / PARTIAL / SECURE
- 📄 **Dark HTML Reports** — Full dark-theme reports with technique comparison tables, copy buttons, and confidence bars
- 📦 **Batch Mode** — Process hundreds of URLs with per-target JSON/HTML output and aggregate leaderboard
- 🔄 **Diff Tracking** — Detects when extracted prompts have changed between runs using SequenceMatcher

## Gallery

Real extracted prompts from live AI applications: [View Gallery](gallery/)

## Why This Matters

System prompt leakage is a documented vulnerability class in the OWASP LLM Top 10 (Sensitive Information Disclosure). Every AI chat app that embeds instructions in its system prompt — without enforcing output-side protections — is leaking intellectual property, behavioral constraints, and sometimes API credentials. PromptLeak exists to demonstrate the scope of the problem and push the industry toward runtime prompt sandboxing.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT
