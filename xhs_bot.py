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
            print("发现已存在的 state.json，使用已保存的会话状态登录...")
            context = await browser.new_context(storage_state='state.json', viewport={'width': 1920, 'height': 1080}, user_agent=user_agent)
            page = await context.new_page()
            await page.goto('https://creator.xiaohongshu.com/creator/home')
            await page.wait_for_timeout(3000)
        else:
            print("未检测到 state.json，正在跳转至登录页面...")
            context = await browser.new_context(viewport={'width': 1920, 'height': 1080}, user_agent=user_agent)
            page = await context.new_page()
            
            await page.goto('https://creator.xiaohongshu.com/login')
            await page.wait_for_timeout(5000)
            
            # 填写手机号码
            print("正在填写手机号码...")
            await page.get_by_placeholder("手机号").fill("19731194079")
            
            # 勾选用户服务协议
            print("正在勾选服务协议...")
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
                # 点击发送验证码
                print("正在点击发送验证码...")
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
                    print("等待短信验证码文件超时。")
                    await page.screenshot(path='error_timeout.png')
                    await browser.close()
                    return
            else:
                print(f"发现已存在的验证码: {sms_code}，跳过点击发送。")
                
            print(f"正在填写短信验证码: {sms_code}...")
            # 确保验证码填写准确
            await page.get_by_placeholder("验证码").fill("")
            await page.get_by_placeholder("验证码").fill(sms_code)
            
            print("正在点击登录按钮...")
            try:
                await page.evaluate("document.querySelector('.beer-login-btn').click()")
            except Exception as e:
                print("JS 注入模拟点击备用方案失败:", e)
                await page.locator('button').last.click(force=True)
            
            print("正在等待登录成功跳转...")
            try:
                await page.wait_for_url('**/creator.xiaohongshu.com/**/home**', timeout=15000)
                print("登录成功！")
                await page.wait_for_timeout(3000)
                print("正在将会话状态持久化保存至 state.json...")
                await context.storage_state(path='state.json')
            except Exception as e:
                print("登录失败:", e)
                await page.screenshot(path='error_login.png', full_page=True)
                await browser.close()
                return
                
        # 已成功处于登录状态
        print("当前工作台 URL:", page.url)
        print("正在截取工作台屏幕保存至 dashboard.png...")
        await page.screenshot(path='dashboard.png', full_page=True)
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
