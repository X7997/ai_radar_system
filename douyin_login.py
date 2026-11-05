import asyncio
from playwright.async_api import async_playwright

async def main():
    print("启动浏览器...")
    async with async_playwright() as p:
        # 使用本地可见模式启动浏览器
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        print("正在打开抖音创作者中心登录页...")
        await page.goto("https://creator.douyin.com/")

        print("\n" + "="*50)
        print("请在弹出的浏览器中，使用手机抖音 APP 扫码，或者使用验证码登录。")
        print("登录成功后，确保页面完全加载进入了【创作者中心主页】。")
        print("="*50 + "\n")
        
        # 轮询检查是否已经成功跳转到主页 (登录成功后URL通常会变)
        # 抖音创作者中心登录后的 URL 类似于 https://creator.douyin.com/creator-micro/home
        logged_in = False
        for i in range(120): # 最多等待 120 * 2 = 240 秒
            url = page.url
            # 如果 URL 中不再包含 login，且包含了 creator-micro，说明大概率进去了
            if "login" not in url and "creator.douyin.com" in url and "home" in url:
                logged_in = True
                break
            await asyncio.sleep(2)
            
        if not logged_in:
            print("自动检测登录超时。如果您其实已经登录成功，请在控制台按回车继续...")
            input("按回车继续保存 Cookie: ")

        # 留一点缓冲时间让页面加载出完整的 Cookie
        print("检测到登录成功，正在等待 5 秒使数据完全加载...")
        await asyncio.sleep(5)

        print("正在保存登录状态 (douyin_state.json)...")
        await context.storage_state(path="douyin_state.json")
        print("保存成功！您现在可以关闭浏览器了。")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
