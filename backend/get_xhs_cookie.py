import json
import time
from playwright.sync_api import sync_playwright

def main():
    print("🚀 正在启动浏览器...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        print("🔗 正在打开小红书主页...")
        page.goto("https://www.xiaohongshu.com/")
        
        print("\n=======================================================")
        print("👉 请在弹出的浏览器中，手动扫码或使用手机号登录小红书。")
        print("⏳ 登录成功后，请不要关闭浏览器。本程序会等待您完成操作...")
        print("=======================================================\n")
        
        # Wait for a specific element that appears only after login
        try:
            input("✅ 登录成功后，请在此处按【回车键】继续...")
            print("正在提取 Cookie...")
            
            # Wait a few seconds for all cookies to settle
            time.sleep(1)
            
            cookies = context.cookies()
            
            # Save the cookies as a semi-colon separated string, which is what xhs library needs.
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            
            with open("xhs_cookie.txt", "w", encoding="utf-8") as f:
                f.write(cookie_str)
                
            print("\n🎉 Cookie 提取成功！已保存到当前目录下的 xhs_cookie.txt 文件中。")
            print("请将该文件中的内容复制，并配置到 GitHub Secrets 中的 XHS_COOKIE 变量里！")
            
        except Exception as e:
            print("\n❌ 未能检测到登录成功状态或登录超时。")
            print(f"错误信息: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
