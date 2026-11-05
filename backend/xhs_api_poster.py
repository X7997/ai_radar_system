import os
import sys
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
XHS_COOKIE = os.getenv('XHS_COOKIE', '')

if not XHS_COOKIE:
    print("错误: .env 中未配置 XHS_COOKIE")
    exit(1)


def parse_cookies(cookie_str):
    cookies = []
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            k, v = item.split('=', 1)
            cookies.append({
                'name': k.strip(),
                'value': v.strip(),
                'domain': '.xiaohongshu.com',
                'path': '/'
            })
    return cookies


def main():
    if len(sys.argv) < 2:
        print("使用方法: python xhs_api_poster.py <发布JSON数据文件>")
        return

    import json
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    title = data['title']
    desc = data['desc']
    image_paths = data['images']

    print(f"正在启动 Playwright (UI 自动化模式)...")
    print(f"正在发布: '{title}' | 图片列表: {image_paths}")

    with sync_playwright() as p:
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-gpu', '--disable-dev-shm-usage', '--no-sandbox', '--start-maximized']
        )
        context = browser.new_context(user_agent=ua, viewport={"width": 1280, "height": 800})
        page = context.new_page()

        if os.path.exists('stealth.min.js'):
            page.add_init_script(path="stealth.min.js")

        context.add_cookies(parse_cookies(XHS_COOKIE))

        # 第 1 步: 加载创作者中心首页 (初始化 Vue 与鉴权状态)
        print("第 1 步: 正在加载创作者中心入口页...")
        page.goto("https://creator.xiaohongshu.com/creator/post",
                  timeout=30000, wait_until="domcontentloaded")
        time.sleep(5)

        if 'login' in page.url or 'passport' in page.url:
            print("错误: 页面被重定向至登录页，Cookie 已失效。")
            browser.close()
            return
        print(f"Page: {page.url}")

        # Step 2: Navigate directly to image publish page
        print("第 2 步: 正在直接导航至图文发布页...")
        try:
            page.goto("https://creator.xiaohongshu.com/publish/publish?from=menu&target=image",
                      timeout=30000, wait_until="domcontentloaded")
            time.sleep(5)
            print(f"After navigation, URL: {page.url}")
        except Exception as e:
            print(f"错误: 导航至图文发布页失败: {e}")
            page.screenshot(path="xhs_debug_step2.png")
            browser.close()
            return

        page.screenshot(path="xhs_debug_step3.png")
        print("已保存第 3 步截图（跳转至图文发布页后）。")

        # Enumerate all elements to find the image upload zone
        all_inputs = page.query_selector_all('input[type="file"]')
        print(f"找到文件输入框数量: {len(all_inputs)}")
        for i, inp in enumerate(all_inputs):
            print(f"  [{i}] accept={inp.get_attribute('accept')}")

        # Step 4: Try to find and use the image upload zone
        # The upload zone is usually a div that triggers a file picker on click
        # Use expect_file_chooser to catch any file picker that opens
        print("第 4 步: 定位图片上传区域并拦截文件选择器...")
        
        uploaded = False
        
        # Method A: If there's already an image-format file input, use it directly
        for inp in all_inputs:
            accept = inp.get_attribute('accept') or ''
            if any(x in accept for x in ['.jpg', '.png', '.jpeg', '.webp', 'image']):
                print("发现专属图片上传输入框，直接调用。")
                inp.set_input_files(image_paths)
                uploaded = True
                break
        
        if not uploaded:
            # Method B: Try clicking the upload area with file chooser interception
            upload_zone_selectors = [
                '[class*="upload-input"]',
                '[class*="image-upload"]', 
                '[class*="img-upload"]',
                '.upload-wrapper',
                '[class*="upload-zone"]',
                '[class*="drag-upload"]',
                '[class*="uploader"]',
                'button:has-text("涓婁紶")',
                'button:has-text("Upload")',
            ]
            
            for sel in upload_zone_selectors:
                try:
                    elem = page.query_selector(sel)
                    if elem:
                        print(f"Trying to click upload zone: {sel}")
                        try:
                            with page.expect_file_chooser(timeout=5000) as fc_info:
                                elem.click()
                            file_chooser = fc_info.value
                            file_chooser.set_files(image_paths)
                            uploaded = True
                            print(f"File selected via file chooser ({sel})!")
                            break
                        except Exception as e2:
                            print(f"  File chooser not triggered: {e2}")
                except Exception as e:
                    pass

        if not uploaded:
            # Method C: Click anywhere in the main content area with file chooser interception
            print("方案 C: 尝试点击内容区触发文件选择器...")
            content_selectors = ['main', '.main', '[class*="content"]', 'body']
            for sel in content_selectors:
                try:
                    with page.expect_file_chooser(timeout=5000) as fc_info:
                        page.click(sel)
                    file_chooser = fc_info.value
                    file_chooser.set_files(image_paths)
                    uploaded = True
                    print(f"File selected via file chooser ({sel})!")
                    break
                except:
                    pass

        if not uploaded:
            # Method D: Use all existing file inputs (including video one) as last resort
            print("方案 D: 使用备用文件输入控件...")
            if all_inputs:
                all_inputs[-1].set_input_files(image_paths)
                uploaded = True
                print("已通过备用控件传入图片文件。")

        if not uploaded:
            print("错误: 无法上传图片文件。")
            page.screenshot(path="xhs_debug_step4.png")
            browser.close()
            return

        print("正在等待图片上传解析处理 (10秒)...")
        time.sleep(10)
        page.screenshot(path="xhs_debug_step4.png")
        print("已保存第 4 步截图（上传完成后）。")

        # Print page state
        print("--- BUTTONS ---")
        for i, btn in enumerate(page.query_selector_all('button')):
            print(f"  [{i}] '{btn.inner_text().strip()[:40]}' enabled={btn.is_enabled()}")

        print("--- INPUTS ---")
        for inp in page.query_selector_all('input'):
            print(f"  type={inp.get_attribute('type')} placeholder='{inp.get_attribute('placeholder')}' maxlen={inp.get_attribute('maxlength')}")

        print("--- CONTENTEDITABLE ---")
        for i, ce in enumerate(page.query_selector_all('[contenteditable]')):
            print(f"  [{i}] '{ce.inner_text().strip()[:60]}'")

        # Step 5: Fill title
        print("第 5 步: 填写笔记标题...")
        for sel in ['input[placeholder*="\u6807\u9898"]', 'input[maxlength="20"]', 'input[maxlength]']:  # 鏍囬
            try:
                inp = page.query_selector(sel)
                if inp:
                    inp.click()
                    inp.fill(title[:20])
                    print(f"  Title filled via {sel}")
                    break
            except:
                pass

        # Step 6: Fill description
        print("第 6 步: 填写正文描述...")
        editables = page.query_selector_all('[contenteditable="true"]')
        if len(editables) >= 2:
            editables[-1].click()
            editables[-1].fill(desc[:1000])
            print("  Desc filled via last contenteditable.")
        elif editables:
            editables[0].click()
            page.keyboard.press('End')
            page.keyboard.press('Enter')
            page.keyboard.type(desc[:1000])
            print("  Desc typed via first contenteditable.")

        time.sleep(2)
        
        # Close any hashtag autocomplete popups by pressing Escape
        page.keyboard.press('Escape')
        time.sleep(1)
        
        page.screenshot(path="xhs_debug_step5.png")
        print("已保存第 5 步截图。")

        # Step 7: Click publish
        try:
            print("  正在向下滚动页面...")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Try to press Enter to accept the hashtag and close the tooltip
            page.keyboard.press('Enter')
            time.sleep(1)
            
            # Click mathematically verified center of red button (from PIL analysis: X=692, Y=755)
            print(f"  正在执行按钮物理像素精准模拟点击 (692, 755)...")
            page.mouse.click(692, 755, delay=100)
            time.sleep(8)
            click_coords = True
                
        except Exception as e:
            print(f"  Error finding or clicking publish button: {e}")
            click_coords = False

        page.screenshot(path="xhs_debug_step6.png")
        print("已保存第 6 步截图。")

        page_text = page.inner_text("body")
        if "违反社区规范" in page_text or "禁止发笔记" in page_text or "封禁" in page_text or "限制" in page_text:
            print("FAILED! Xiaohongshu account banned/restricted: 因违反社区规范禁止发笔记!")
            is_really_published = False
        elif click_coords:
            # Check if redirected or publish success indicator
            current_url = page.url
            if "publish" not in current_url or "发布成功" in page_text:
                print("发布成功！笔记已顺利发布至小红书！")
                is_really_published = True
            else:
                print("发布未成功: 仍停留在发布页面，未完成提交。")
                is_really_published = False
        else:
            print("发布未成功: 未能定位或点击发布按钮。")
            is_really_published = False

        time.sleep(3)
        browser.close()
        if is_really_published:
            print("\n执行完毕。")
        else:
            print("\n执行异常终止。")


if __name__ == "__main__":
    main()
