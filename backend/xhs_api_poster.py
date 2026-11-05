import os
import sys
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
XHS_COOKIE = os.getenv('XHS_COOKIE', '')

if not XHS_COOKIE:
    print("Error: XHS_COOKIE is not set in .env")
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
        print("Usage: python xhs_api_poster.py <post_json_file>")
        return

    import json
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    title = data['title']
    desc = data['desc']
    image_paths = data['images']

    print(f"Starting Playwright (UI automation mode)...")
    print(f"Publishing: '{title}' | images: {image_paths}")

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

        # Step 1: Load entry page (initializes Vue app + auth)
        print("Step 1: Loading creator entry page...")
        page.goto("https://creator.xiaohongshu.com/creator/post",
                  timeout=30000, wait_until="domcontentloaded")
        time.sleep(5)

        if 'login' in page.url or 'passport' in page.url:
            print("ERROR: Redirected to login. Cookie expired.")
            browser.close()
            return
        print(f"Page: {page.url}")

        # Step 2: Navigate directly to image publish page
        print("Step 2: Navigating to image publish page...")
        try:
            page.goto("https://creator.xiaohongshu.com/publish/publish?from=menu&target=image",
                      timeout=30000, wait_until="domcontentloaded")
            time.sleep(5)
            print(f"After navigation, URL: {page.url}")
        except Exception as e:
            print(f"ERROR navigating to image page: {e}")
            page.screenshot(path="xhs_debug_step2.png")
            browser.close()
            return

        page.screenshot(path="xhs_debug_step3.png")
        print("Screenshot 3 saved (after navigation to image publish page).")

        # Enumerate all elements to find the image upload zone
        all_inputs = page.query_selector_all('input[type="file"]')
        print(f"File inputs found: {len(all_inputs)}")
        for i, inp in enumerate(all_inputs):
            print(f"  [{i}] accept={inp.get_attribute('accept')}")

        # Step 4: Try to find and use the image upload zone
        # The upload zone is usually a div that triggers a file picker on click
        # Use expect_file_chooser to catch any file picker that opens
        print("Step 4: Looking for image upload zone and intercepting file chooser...")
        
        uploaded = False
        
        # Method A: If there's already an image-format file input, use it directly
        for inp in all_inputs:
            accept = inp.get_attribute('accept') or ''
            if any(x in accept for x in ['.jpg', '.png', '.jpeg', '.webp', 'image']):
                print("Found image-specific file input, using directly.")
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
            print("Method C: Trying to click content area to trigger file chooser...")
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
            print("Method D: Using existing file input (fallback)...")
            if all_inputs:
                all_inputs[-1].set_input_files(image_paths)
                uploaded = True
                print("File set via fallback input.")

        if not uploaded:
            print("ERROR: Could not upload file.")
            page.screenshot(path="xhs_debug_step4.png")
            browser.close()
            return

        print("Waiting for upload to process (10s)...")
        time.sleep(10)
        page.screenshot(path="xhs_debug_step4.png")
        print("Screenshot 4 saved (after upload).")

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
        print("Step 5: Filling title...")
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
        print("Step 6: Filling description...")
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
        print("Screenshot 5 saved.")

        # Step 7: Click publish
        try:
            print("  Scrolling to bottom...")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Try to press Enter to accept the hashtag and close the tooltip
            page.keyboard.press('Enter')
            time.sleep(1)
            
            # Click mathematically verified center of red button (from PIL analysis: X=692, Y=755)
            print(f"  Executing physical blind click at (692, 755)...")
            page.mouse.click(692, 755, delay=100)
            time.sleep(8)
            click_coords = True
                
        except Exception as e:
            print(f"  Error finding or clicking publish button: {e}")
            click_coords = False

        page.screenshot(path="xhs_debug_step6.png")
        print("Screenshot 6 saved.")

        page_text = page.inner_text("body")
        if "违反社区规范" in page_text or "禁止发笔记" in page_text or "封禁" in page_text or "限制" in page_text:
            print("FAILED! Xiaohongshu account banned/restricted: 因违反社区规范禁止发笔记!")
            is_really_published = False
        elif click_coords:
            # Check if redirected or publish success indicator
            current_url = page.url
            if "publish" not in current_url or "发布成功" in page_text:
                print("SUCCESS! Note published to Xiaohongshu!")
                is_really_published = True
            else:
                print("FAILED! Xiaohongshu publish failed: Still stuck on publish page, not published.")
                is_really_published = False
        else:
            print("FAILED! Could not find or click publish button.")
            is_really_published = False

        time.sleep(3)
        browser.close()
        if is_really_published:
            print("\nFinished execution.")
        else:
            print("\nFinished execution with failure.")


if __name__ == "__main__":
    main()
