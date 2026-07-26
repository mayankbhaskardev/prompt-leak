"""Manage pre-extracted prompt gallery for README display."""
import os
from datetime import datetime

GALLERY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "gallery")


def add_to_gallery(
    domain: str,
    technique: str,
    extracted_text: str,
    confidence: float,
    url: str = "",
) -> str:
    os.makedirs(GALLERY_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_domain = domain.replace(".", "_").replace(":", "_")
    filename = f"{safe_domain}_{technique}_{timestamp}.md"
    filepath = os.path.join(GALLERY_DIR, filename)

    content = f"""---
domain: {domain}
technique: {technique}
confidence: {confidence:.2f}
timestamp: {datetime.utcnow().isoformat()}
url: {url}
---

# Extracted Prompt from {domain}

**Technique**: {technique}  
**Confidence**: {confidence:.2f}  
**Date**: {datetime.utcnow().isoformat()}

```text
{extracted_text}
```
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


def list_gallery() -> list[dict]:
    if not os.path.isdir(GALLERY_DIR):
        return []
    entries = []
    for fname in sorted(os.listdir(GALLERY_DIR), reverse=True):
        if fname.endswith(".md") and fname != "README.md":
            filepath = os.path.join(GALLERY_DIR, fname)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            entries.append({"filename": fname, "path": filepath, "content": content})
    return entries
