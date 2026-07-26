# Security Policy

## Reporting a Vulnerability in prompt-leak

If you find a security vulnerability in **prompt-leak itself** (not in a target AI platform), please report it responsibly.

**Do NOT open a public issue.**

Email: security@example.com

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Scope

This security policy covers the **prompt-leak tool itself**. It does NOT cover:

- Vulnerabilities in AI platforms that prompt-leak can extract prompts from (that's the point)
- Prompt injection vulnerabilities in target AI applications (report those to the respective platform)
- Issues with third-party dependencies (report to the respective project)

### What IS in scope

- Arbitrary code execution via crafted input
- Path traversal in file handling
- Command injection in proxy/target handling
- Authentication bypass in the web UI
- SSRF in the hunter/proxy modules
- SQL injection in the cache/intel database
- Denial of service via malicious inputs

## Disclosure Policy

- Acknowledge receipt within 48 hours
- Initial assessment within 7 days
- Fix timeline communicated within 14 days
- Credit in release notes (unless anonymous)
- No legal threats for good-faith reports

## Supported Versions

Only the latest release is supported. Older versions will not receive security patches.
