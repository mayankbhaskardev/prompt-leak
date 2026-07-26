"""Inspect Perplexity page - quick check."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://www.perplexity.ai", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(10)
        
        print(f"Final URL: {page.url}")
        print(f"Title: {await page.title()}")
        
        # Full HTML outline
        html = await page.evaluate("""() => {
            function getOutline(el, depth) {
                if (depth > 4) return '';
                let result = '';
                for (const child of el.children) {
                    const tag = child.tagName.toLowerCase();
                    const id = child.id ? '#' + child.id : '';
                    const cls = child.className && typeof child.className === 'string' ? '.' + child.className.split(' ').filter(c=>c).join('.') : '';
                    const text = (child.innerText || '').substring(0, 40).replace(/\\n/g, ' ').trim();
                    result += '  '.repeat(depth) + '<' + tag + id + cls + '> ' + text + '\\n';
                    result += getOutline(child, depth + 1);
                }
                return result;
            }
            return getOutline(document.body, 0);
        }""")
        print("Page structure:")
        print(html[:3000])
        
        await browser.close()


asyncio.run(main())
