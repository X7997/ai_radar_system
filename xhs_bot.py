import asyncio
from playwright.async_api import async_playwright
import os
import time

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=[
            '--no-sandbox', 
            '--disable-setuid-sandbox',
            '--disable-blink-features=AutomationControlled'
        ])
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        if os.path.exists('state.json'):
            print("Found existing state.json. Logging in with saved state...")
            context = await browser.new_context(storage_state='state.json', viewport={'width': 1920, 'height': 1080}, user_agent=user_agent)
            page = await context.new_page()
            await page.goto('https://creator.xiaohongshu.com/creator/home')
            await page.wait_for_timeout(3000)
        else:
            print("No state.json found. Navigating to login page...")
            context = await browser.new_context(viewport={'width': 1920, 'height': 1080}, user_agent=user_agent)
            page = await context.new_page()
            
            await page.goto('https://creator.xiaohongshu.com/login')
            await page.wait_for_timeout(5000)
            
            # Fill Phone Number
            print("Filling phone number...")
            await page.get_by_placeholder("手机号").fill("19731194079")
            
            # Check the agreement box
            print("Checking agreement...")
            try:
                await page.locator('.agree-icon').click(timeout=3000)
            except:
                try:
                    await page.locator('.css-146c3p1').click(timeout=2000)
                except:
                    await page.locator('text=登录即同意').click(position={"x": -10, "y": 5}, force=True)
            
            sms_code = None
            if os.path.exists('/root/sms_code.txt'):
                with open('/root/sms_code.txt', 'r') as f:
                    sms_code = f.read().strip()
                    
            if not sms_code:
                # Click Send Code
                print("Clicking Send Code...")
                await page.get_by_text("发送验证码").click()
                
                print("WAITING_FOR_SMS_CODE")
                for _ in range(120):
                    if os.path.exists('/root/sms_code.txt'):
                        with open('/root/sms_code.txt', 'r') as f:
                            sms_code = f.read().strip()
                        if sms_code:
                            break
                    await asyncio.sleep(1)
                    
                if not sms_code:
                    print("Timeout waiting for SMS code file.")
                    await page.screenshot(path='error_timeout.png')
                    await browser.close()
                    return
            else:
                print(f"Found existing SMS code: {sms_code}. Skipping send click.")
                
            print(f"Filling SMS code: {sms_code}...")
            # Ensure it fills correctly
            await page.get_by_placeholder("验证码").fill("")
            await page.get_by_placeholder("验证码").fill(sms_code)
            
            print("Clicking Login...")
            try:
                await page.evaluate("document.querySelector('.beer-login-btn').click()")
            except Exception as e:
                print("JS click fallback failed:", e)
                await page.locator('button').last.click(force=True)
            
            print("Waiting for login success...")
            try:
                await page.wait_for_url('**/creator.xiaohongshu.com/**/home**', timeout=15000)
                print("Login successful!")
                await page.wait_for_timeout(3000)
                print("Saving session to state.json")
                await context.storage_state(path='state.json')
            except Exception as e:
                print("Login failed:", e)
                await page.screenshot(path='error_login.png', full_page=True)
                await browser.close()
                return
                
        # We are logged in
        print("Dashboard URL:", page.url)
        print("Taking dashboard screenshot to dashboard.png")
        await page.screenshot(path='dashboard.png', full_page=True)
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
