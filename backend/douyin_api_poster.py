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
        print("Usage: python douyin_api_poster.py <post_json_file>")
        sys.exit(1)

    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    title = data['title']
    desc = data['desc']
    image_paths = [os.path.abspath(p) for p in data['images']]

    # Ensure title fits Douyin 20-char limit
    if len(title) > 20:
        title = title[:20]

    print(f"Starting Playwright for Douyin... Publishing: '{title}' ({len(title)} chars), {len(image_paths)} images")

    state_path = "douyin_state.json"
    if not os.path.exists(state_path):
        alt = os.path.join(os.path.dirname(__file__), "douyin_state.json")
        if os.path.exists(alt):
            state_path = alt
        elif os.path.exists("q:/xiaohonshu/ai_radar_system/douyin_state.json"):
            state_path = "q:/xiaohonshu/ai_radar_system/douyin_state.json"

    if not os.path.exists(state_path):
        print("ERROR: douyin_state.json not found! Please run douyin_login.py first.")
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
                print(f"Stealth warning: {e}")
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        page.add_init_script("Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});")

        # Navigate to Publisher
        print("Navigating to Image Publish Page...")
        page.goto("https://creator.douyin.com/creator-micro/content/upload", timeout=60000, wait_until="domcontentloaded")
        time.sleep(4)
        
        # Switch to 发布图文 Tab
        print("Switching to 发布图文 tab...")
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
                print("Image input found successfully!")
                break
            time.sleep(1)

        if not img_inp:
            print("ERROR: Could not find image input element.")
            browser.close()
            sys.exit(1)

        print(f"Uploading {len(image_paths)} images...")
        img_inp.set_input_files(image_paths)

        # Wait dynamically for upload completion
        print("Waiting for images to finish uploading and processing...")
        uploaded = False
        for sec in range(60):
            time.sleep(1)
            body_txt = page.evaluate("() => document.body.innerText")
            if f"已添加{len(image_paths)}张图片" in body_txt or "重新上传" in body_txt or "更换图片" in body_txt:
                print(f"All {len(image_paths)} images successfully uploaded and processed at {sec+1}s!")
                uploaded = True
                break
            if (sec + 1) % 5 == 0:
                print(f"Waiting for upload... {sec+1}s elapsed")

        if not uploaded:
            print("Upload detection timeout, continuing to form filling...")

        time.sleep(2)

        # Fill Title
        print(f"Filling Title: '{title}'...")
        try:
            title_input = page.locator('input[placeholder*="标题"]').first
            if title_input.count() == 0:
                title_input = page.locator('input[type="text"]').first
            if title_input.count() > 0:
                title_input.click()
                title_input.fill(title)
                print("Title filled successfully.")
            else:
                print("Warning: Title input not found.")
        except Exception as e:
            print(f"Title fill error: {e}")

        # Fill Description (Minimalist: 0 URLs, 0 descriptions, only date and tags)
        clean_desc = re.sub(r'https?://\S+|www\.\S+', '', desc).strip() if desc else ""
        if clean_desc:
            print(f"Filling Description ({len(clean_desc)} chars, stripped of any links)...")
            try:
                desc_zones = ['.zone-container', '.editor-kit-editor-container', '[contenteditable="true"]', 'textarea']
                filled_desc = False
                for sel in desc_zones:
                    zone = page.locator(sel).first
                    if zone.count() > 0 and zone.is_visible():
                        zone.click()
                        page.keyboard.insert_text(clean_desc[:950])
                        filled_desc = True
                        print(f"Description filled via {sel}.")
                        break
                if not filled_desc:
                    print("Warning: Description zone not found.")
            except Exception as e:
                print(f"Description fill error: {e}")
        else:
            print("Notice: Description is empty as requested. Skipping description input.")

        time.sleep(2)

        # Scroll to Publish Button
        print("Scrolling to bottom...")
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

        print("Clicking '发布' button...")
        pub_btn.click()

        # Verify Publish Success
        print("Waiting for publish completion / redirect...")
        published = False
        for s in range(30):
            time.sleep(1)
            cur_url = page.url
            body_txt = page.evaluate("() => document.body.innerText")
            if 'manage' in cur_url or '发布成功' in body_txt or '作品发布成功' in body_txt:
                print(f"Publish verified at {s+1}s! URL: {cur_url}")
                published = True
                break

        page.screenshot(path="final_publish_result.png")

        if published:
            try:
                context.storage_state(path=state_path)
            except Exception:
                pass
            browser.close()
            print("SUCCESS! Note published")
        else:
            browser.close()
            print("ERROR: Could not verify publish success.")
            sys.exit(1)

if __name__ == "__main__":
    main()
