"""Inspect Perplexity page structure."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://www.perplexity.ai", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)

        inputs = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('textarea').forEach(el => {
                results.push({tag: 'textarea', id: el.id, cls: el.className, placeholder: el.placeholder, aria: el.getAttribute('aria-label'), role: el.getAttribute('role')});
            });
            document.querySelectorAll('div[contenteditable]').forEach(el => {
                results.push({tag: 'div[contenteditable]', id: el.id, cls: el.className, aria: el.getAttribute('aria-label'), role: el.getAttribute('role')});
            });
            document.querySelectorAll('[role="textbox"]').forEach(el => {
                results.push({tag: el.tagName, id: el.id, cls: el.className, aria: el.getAttribute('aria-label')});
            });
            document.querySelectorAll('input[type="text"]').forEach(el => {
                results.push({tag: 'input[type=text]', id: el.id, cls: el.className, placeholder: el.placeholder});
            });
            return results;
        }""")
        print("Input elements:")
        for inp in inputs:
            print(f"  {inp}")

        buttons = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('button').forEach(el => {
                const aria = el.getAttribute('aria-label');
                if (aria && (aria.toLowerCase().includes('send') || aria.toLowerCase().includes('submit') || aria.toLowerCase().includes('ask')))
                    results.push({tag: 'button', id: el.id, cls: el.className, aria: aria, text: el.innerText.substring(0, 50)});
            });
            return results;
        }""")
        print("Send buttons:")
        for btn in buttons:
            print(f"  {btn}")

        responses = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('[class*="message"], [class*="response"], [class*="assistant"], [class*="prose"], [class*="answer"]').forEach(el => {
                results.push({tag: el.tagName, cls: el.className, id: el.id});
            });
            return results;
        }""")
        print(f"Response elements ({len(responses)}):")
        for r in responses[:10]:
            print(f"  {r}")

        await browser.close()


asyncio.run(main())
