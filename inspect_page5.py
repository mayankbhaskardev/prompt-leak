"""Check Perplexity response structure."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://www.perplexity.ai", wait_until="domcontentloaded", timeout=30000)
        
        # Wait for page to load and Cloudflare to pass
        for i in range(30):
            await asyncio.sleep(1)
            title = await page.title()
            if "Just a moment" not in title:
                break
        
        await asyncio.sleep(3)
        
        # Find the input
        input_el = await page.query_selector("div#ask-input")
        if not input_el:
            input_el = await page.query_selector('[role="textbox"]')
        
        if input_el:
            await input_el.click()
            await input_el.fill("")
            await page.keyboard.type("Say hello in one word.", delay=50)
            await asyncio.sleep(1)
            
            # Try pressing Enter
            await page.keyboard.press("Enter")
            
            print("Sent message, waiting for response...")
            for i in range(30):
                await asyncio.sleep(2)
                # Check for new content
                responses = await page.evaluate("""() => {
                    const results = [];
                    document.querySelectorAll('[class*="message"], [class*="response"], [class*="prose"], [class*="answer"], article, [class*="result"]').forEach(el => {
                        const text = (el.innerText || '').substring(0, 80);
                        if (text.trim()) results.push({tag: el.tagName, cls: (el.className || '').substring(0, 100), text: text});
                    });
                    return results;
                }""")
                if responses:
                    print(f"  [{i*2}s] Found {len(responses)} response elements")
                    for r in responses:
                        print(f"    {r}")
                
                has_prose = await page.evaluate("!!document.querySelector('[class*=\"prose\"]')")
                if has_prose:
                    print("  Found prose element!")
                    break
        else:
            print("Could not find input element")
        
        # Take screenshot
        await page.screenshot(path="perplexity_chat.png", full_page=True)
        print("\nScreenshot saved")
        
        # Dump full response area HTML
        response_html = await page.evaluate("""() => {
            const main = document.querySelector('main');
            return main ? main.innerText.substring(0, 2000) : 'NO MAIN';
        }""")
        print(f"\nMain area text:\n{response_html}")
        
        await browser.close()


asyncio.run(main())
