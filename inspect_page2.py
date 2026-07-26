"""Inspect Perplexity page - take screenshot and check URL."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://www.perplexity.ai", wait_until="networkidle", timeout=60000)
        await asyncio.sleep(3)
        
        print(f"Final URL: {page.url}")
        print(f"Title: {await page.title()}")
        
        body_text = await page.evaluate("document.body.innerText.substring(0, 2000)")
        print(f"Body text (first 2000 chars):")
        print(body_text)
        
        # Check all text-like elements
        all_inputs = await page.evaluate("""() => {
            const all = document.querySelectorAll('input, textarea, [contenteditable], [role="textbox"]');
            return Array.from(all).map(el => ({
                tag: el.tagName,
                type: el.type,
                id: el.id,
                cls: el.className,
                placeholder: el.placeholder,
                visible: el.offsetParent !== null
            }));
        }""")
        print(f"\nAll input-like elements: {len(all_inputs)}")
        for inp in all_inputs:
            print(f"  {inp}")

        await page.screenshot(path="perplexity_home.png", full_page=True)
        print("\nScreenshot saved to perplexity_home.png")
        
        await browser.close()


asyncio.run(main())
