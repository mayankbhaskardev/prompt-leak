"""Inspect Perplexity after Cloudflare passes."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://www.perplexity.ai", wait_until="domcontentloaded", timeout=30000)
        print("Waiting for Cloudflare and page load...")
        
        for i in range(60):
            await asyncio.sleep(2)
            title = await page.title()
            print(f"  [{i*2}s] title='{title}' url={page.url[:80]}")
            if "Just a moment" not in title:
                has_textarea = await page.evaluate("document.querySelector('textarea') !== null")
                has_input = await page.evaluate("document.querySelector('[contenteditable]') !== null")
                print(f"    textarea={has_textarea} contenteditable={has_input}")
                if has_textarea or has_input:
                    break
        
        print(f"\nFinal URL: {page.url}")
        print(f"Title: {await page.title()}")
        
        # Dump all input-like elements
        inputs = await page.evaluate("""() => {
            const all = document.querySelectorAll('textarea, [contenteditable], [role="textbox"], input[type="text"]');
            return Array.from(all).map(el => ({
                tag: el.tagName,
                id: el.id,
                cls: (el.className || '').substring(0, 100),
                placeholder: el.placeholder || '',
                aria: el.getAttribute('aria-label') || '',
                role: el.getAttribute('role') || '',
            }));
        }""")
        print(f"\nInput elements: {len(inputs)}")
        for inp in inputs:
            print(f"  {inp}")
        
        # Dump buttons with aria-labels
        buttons = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button')).map(el => ({
                aria: el.getAttribute('aria-label') || '',
                text: (el.innerText || '').substring(0, 40),
                cls: (el.className || '').substring(0, 60),
            }));
        }""")
        print(f"\nButtons: {len(buttons)}")
        for btn in buttons:
            if btn['aria'] or btn['text'].strip():
                print(f"  aria='{btn['aria']}' text='{btn['text']}'")
        
        await browser.close()


asyncio.run(main())
