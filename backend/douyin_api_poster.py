import os
import sys
import time
import json
import re
from playwright.sync_api import sync_playwright

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

try:
    from playwright_stealth import Stealth
    stealth_applier = Stealth().apply_stealth_sync
except Exception:
    stealth_applier = None

def main():
    if len(sys.argv) < 2:
        print("使用方法: python douyin_api_poster.py <待发布任务JSON文件>")
        sys.exit(1)

    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    title = data['title']
    desc = data['desc']
    image_paths = [os.path.abspath(p) for p in data['images']]

    # Ensure title fits Douyin 20-char limit
    if len(title) > 20:
        title = title[:20]

    print(f"启动 Playwright 抖音发布引擎... 正在发布: '{title}' ({len(title)} 字符), {len(image_paths)} 张图片")

    state_path = "douyin_state.json"
    if not os.path.exists(state_path):
        alt = os.path.join(os.path.dirname(__file__), "douyin_state.json")
        if os.path.exists(alt):
            state_path = alt
        elif os.path.exists("q:/xiaohonshu/ai_radar_system/douyin_state.json"):
            state_path = "q:/xiaohonshu/ai_radar_system/douyin_state.json"

    if not os.path.exists(state_path):
        print("错误: 未找到 douyin_state.json 登录凭证！请先执行 douyin_login.py 登录。")
        sys.exit(1)

    with sync_playwright() as p:
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        launch_args = {
            'headless': True if sys.platform != 'win32' else False,
            'args': ['--disable-blink-features=AutomationControlled', '--disable-gpu', '--no-sandbox', '--start-maximized']
        }

        browser = p.chromium.launch(**launch_args)
        context = browser.new_context(
            user_agent=ua, 
            viewport={"width": 1280, "height": 800},
            storage_state=state_path
        )
        page = context.new_page()
        if stealth_applier:
            try:
                stealth_applier(page)
            except Exception as e:
                print(f"防检测伪装提示: {e}")
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        page.add_init_script("Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});")

        # Navigate to Publisher
        print("正在导航至抖音创作者中心图文发布页面...")
        page.goto("https://creator.douyin.com/creator-micro/content/upload", timeout=60000, wait_until="domcontentloaded")
        time.sleep(4)
        
        # Switch to 发布图文 Tab
        print("正在切换至【发布图文】标签页...")
        img_inp = None
        for attempt in range(5):
            tab = page.locator('text=发布图文').first
            if tab.count() > 0:
                try:
                    tab.click(timeout=3000)
                except Exception:
                    pass
            else:
                page.mouse.click(380, 112)
                
            time.sleep(2)
            inps = page.locator('input[type="file"]').all()
            for inp in inps:
                acc = inp.get_attribute('accept') or ''
                if 'image' in acc:
                    img_inp = inp
                    break
            if img_inp:
                print("成功定位到图片上传文件控件！")
                break
            time.sleep(1)

        if not img_inp:
            print("错误: 未能找到图片上传文件控件。")
            browser.close()
            sys.exit(1)

        print(f"正在上传 {len(image_paths)} 张高清排版卡片...")
        img_inp.set_input_files(image_paths)

        # Wait dynamically for upload completion
        print("正在等待图片上传及云端渲染处理...")
        uploaded = False
        for sec in range(60):
            time.sleep(1)
            body_txt = page.evaluate("() => document.body.innerText")
            if f"已添加{len(image_paths)}张图片" in body_txt or "重新上传" in body_txt or "更换图片" in body_txt:
                print(f"全部 {len(image_paths)} 张图片已在第 {sec+1} 秒成功上传并处理完成！")
                uploaded = True
                break
            if (sec + 1) % 5 == 0:
                print(f"等待上传处理中... 已耗时 {sec+1} 秒")

        if not uploaded:
            print("等待上传检测超时，继续执行表单填写...")

        time.sleep(2)

        # Fill Title
        print(f"正在填写作品标题: '{title}'...")
        try:
            title_input = page.locator('input[placeholder*="标题"]').first
            if title_input.count() == 0:
                title_input = page.locator('input[type="text"]').first
            if title_input.count() > 0:
                title_input.click()
                title_input.fill(title)
                print("作品标题填写成功。")
            else:
                print("警告: 未能找到标题输入框。")
        except Exception as e:
            print(f"填写标题异常: {e}")

        # Fill Description (Minimalist: 0 URLs, 0 descriptions, only date and tags)
        clean_desc = re.sub(r'https?://\S+|www\.\S+', '', desc).strip() if desc else ""
        if clean_desc:
            print(f"正在填写作品正文描述 ({len(clean_desc)} 字，已过滤外链)...")
            try:
                desc_zones = ['.zone-container', '.editor-kit-editor-container', '[contenteditable="true"]', 'textarea']
                filled_desc = False
                for sel in desc_zones:
                    zone = page.locator(sel).first
                    if zone.count() > 0 and zone.is_visible():
                        zone.click()
                        page.keyboard.insert_text(clean_desc[:950])
                        filled_desc = True
                        print(f"通过选择器 {sel} 成功填写描述。")
                        break
                if not filled_desc:
                    print("警告: 未能找到描述输入区域。")
            except Exception as e:
                print(f"填写描述异常: {e}")
        else:
            print("提示: 描述为空，跳过描述填写。")

        time.sleep(2)

        # Scroll to Publish Button
        print("正在滑动页面至底部...")
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)

        # Locate Publish Button
        pub_btn = None
        for b in page.locator('button').all():
            btxt = (b.inner_text() or '').strip()
            if btxt == '发布' and b.is_visible():
                pub_btn = b
                break

        if not pub_btn:
            pub_btn = page.locator('button:text-is("发布")').last

        print("正在点击【发布】按钮...")
        pub_btn.click()

        # Verify Publish Success
        print("正在等待发布提交完成及页面跳转...")
        published = False
        for s in range(30):
            time.sleep(1)
            cur_url = page.url
            body_txt = page.evaluate("() => document.body.innerText")
            if 'manage' in cur_url or '发布成功' in body_txt or '作品发布成功' in body_txt:
                print(f"在第 {s+1} 秒成功验证作品已发布！当前页面 URL: {cur_url}")
                published = True
                break

        page.screenshot(path="final_publish_result.png")

        if published:
            try:
                context.storage_state(path=state_path)
            except Exception:
                pass
            browser.close()
            print("发布成功！作品已成功发布至抖音。")
        else:
            browser.close()
            print("错误: 无法验证作品发布状态。")
            sys.exit(1)

if __name__ == "__main__":
    main()
