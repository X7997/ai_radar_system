import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        storage_state='douyin_state.json',
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        viewport={'width': 1280, 'height': 800}
    )
    page = context.new_page()
    page.goto('https://creator.douyin.com/creator-micro/content/upload?default-tab=3', timeout=60000, wait_until='domcontentloaded')
    time.sleep(3)
    print('Current URL:', page.url)
    
    # Check if image input is present directly
    inps = page.locator('input[type="file"]').all()
    print(f'Total file inputs: {len(inps)}')
    for i, inp in enumerate(inps):
        acc = inp.get_attribute('accept') or ''
        print(f'inp {i}: accept={acc[:40]}')
        
    browser.close()
