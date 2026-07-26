"""Find the correct Perplexity response selector."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://www.perplexity.ai", wait_until="domcontentloaded", timeout=30000)
        
        for _ in range(30):
            title = await page.title()
            if "Just a moment" not in title:
                break
            await asyncio.sleep(2)
        
        await asyncio.sleep(2)
        
        # Send a normal question
        input_el = await page.query_selector("div#ask-input")
        if input_el:
            await input_el.click()
            await input_el.fill("")
            await page.keyboard.type("Say hello in one word.", delay=50)
            await page.keyboard.press("Enter")
            
            await asyncio.sleep(10)
        
        # Dump the response area HTML structure
        structure = await page.evaluate("""() => {
            const results = [];
            
            // Find all elements in the main area
            const main = document.querySelector('main');
            if (!main) return 'NO MAIN FOUND';
            
            function walk(el, depth) {
                if (depth > 6) return;
                const tag = el.tagName.toLowerCase();
                const id = el.id ? '#' + el.id : '';
                let cls = '';
                if (el.className && typeof el.className === 'string') {
                    cls = '.' + el.className.split(' ').filter(c => c && !c.includes('[') && c.length < 40).join('.');
                }
                const text = (el.innerText || '').substring(0, 60).replace(/\\n/g, ' ').trim();
                if (text) {
                    results.push({tag: tag + id + cls, text: text, children: el.children.length});
                }
                for (const child of el.children) {
                    walk(child, depth + 1);
                }
            }
            walk(main, 0);
            return results;
        }""")
        
        print("Main area structure:")
        for s in structure:
            print(f"  <{s['tag']}> '{s['text']}' ({s['children']} children)")
        
        # Check specifically for answer containers
        answer_selectors = await page.evaluate("""() => {
            const candidates = [];
            
            // Try various selectors
            const selectors = [
                '[class*="answer"]',
                '[class*="response"]', 
                '[class*="result"]',
                '[class*="message"]',
                '[data-testid*="answer"]',
                'article',
                '.prose',
                '[class*="prose"]',
            ];
            
            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                if (els.length > 0) {
                    candidates.push({selector: sel, count: els.length, texts: Array.from(els).map(e => (e.innerText || '').substring(0, 80))});
                }
            }
            return candidates;
        }""")
        
        print("\nCandidate selectors:")
        for c in answer_selectors:
            print(f"  {c['selector']}: {c['count']} matches")
            for t in c['texts']:
                if t.strip():
                    print(f"    > {t}")
        
        await browser.close()


asyncio.run(main())
