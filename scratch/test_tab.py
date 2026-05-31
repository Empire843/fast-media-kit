import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("http://127.0.0.1:8000/")
        
        print("Initial active tab:", await page.eval_on_selector(".tab-btn.active", "el => el.dataset.tab"))
        print("Initial active workspace:", await page.eval_on_selector(".workspace.active", "el => el.dataset.workspace"))
        
        # Click Translate XLSX tab
        print("\nClicking Translate XLSX tab...")
        await page.click(".tab-btn[data-tab='translate']")
        
        # Wait a bit
        await asyncio.sleep(0.5)
        
        print("Active tab after click:", await page.eval_on_selector(".tab-btn.active", "el => el.dataset.tab"))
        print("Active workspace after click:", await page.eval_on_selector(".workspace.active", "el => el.dataset.workspace"))
        
        # Check if there are any console errors
        print("\nConsole errors (if any):")
        
        await browser.close()

asyncio.run(main())
