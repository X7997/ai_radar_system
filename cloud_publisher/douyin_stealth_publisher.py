#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Radar Douyin Stealth Publisher (Residential Disguise)
- Emulates Windows 10 x64 + NVIDIA RTX 3060 desktop environment
- Preserves cookies and localStorage
- Never destroys state file on error
- Native JS DOM button click
"""

import os
import sys
import time
import json
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

try:
    from playwright_stealth import Stealth
    stealth_applier = Stealth().apply_stealth_sync
except Exception:
    stealth_applier = None

BASE_DIR = '/root/ai_radar_publisher'
STATE_PATH = os.path.join(BASE_DIR, 'douyin_state.json')

DISGUISE_JS = """
(() => {
    // 1. Overwrite navigator properties
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
    
    // 2. Overwrite window.chrome
    if (!window.chrome) {
        window.chrome = {};
    }
    window.chrome.runtime = window.chrome.runtime || {};
    window.chrome.app = {
        isInstalled: false,
        InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
        RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }
    };
    window.chrome.csi = function() {};
    window.chrome.loadTimes = function() {};
    
    // 3. Overwrite WebGL vendor & renderer to NVIDIA RTX 3060
    const getParameterProxyHandler = {
        apply: function(target, thisArg, argumentsList) {
            const param = argumentsList[0];
            if (param === 37445) return 'Google Inc. (NVIDIA)';
            if (param === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)';
            return Reflect.apply(target, thisArg, argumentsList);
        }
    };
    
    const getContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, ...args) {
        const ctx = getContext.apply(this, [type, ...args]);
        if (ctx && (type === 'webgl' || type === 'experimental-webgl' || type === 'webgl2')) {
            const getParam = ctx.getParameter;
            ctx.getParameter = new Proxy(getParam, getParameterProxyHandler);
        }
        return ctx;
    };
    
    // 4. Overwrite Screen
    Object.defineProperty(screen, 'width', { get: () => 1920 });
    Object.defineProperty(screen, 'height', { get: () => 1080 });
    Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
    Object.defineProperty(screen, 'availHeight', { get: () => 1040 });
    Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
    Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });
})();
"""

def publish(post_json_path):
    with open(post_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    title = data['title'][:20]
    desc = data.get('desc', '')
    image_paths = [os.path.abspath(p) for p in data['images']]
    
    print(f"[{datetime.now()}] Stealth Publishing Starting...")
    print(f"Title: {title} | Images: {len(image_paths)}")
    
    if not os.path.exists(STATE_PATH):
        print(f"ERROR: State path {STATE_PATH} does not exist!")
        return False
        
    with sync_playwright() as p:
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--start-maximized',
                '--lang=zh-CN,zh'
            ]
        )
        context = browser.new_context(
            storage_state=STATE_PATH,
            user_agent=ua,
            viewport={"width": 1920, "height": 960},
            locale="zh-CN",
            timezone_id="Asia/Shanghai"
        )
        context.add_init_script(DISGUISE_JS)
        
        page = context.new_page()
        if stealth_applier:
            stealth_applier(page)
            
        print("[1/5] Navigating to Douyin Creator upload page...")
        page.goto("https://creator.douyin.com/creator-micro/content/upload", timeout=60000, wait_until="domcontentloaded")
        time.sleep(5)
        
        cur_url = page.url
        body = page.evaluate("() => document.body ? document.body.innerText : ''")
        print(f"Current URL: {cur_url}")
        
        # Check login status
        if "我是创作者" in body or "扫码登录" in body:
            print("ERROR: Not logged in! Session cookies need update.")
            page.screenshot(path=os.path.join(BASE_DIR, 'err_not_logged_in.png'))
            browser.close()
            return False
            
        # Switch to 图文 Tab
        print("[2/5] Switching to 图文 tab...")
        img_inp = None
        for attempt in range(5):
            tab = page.locator('text=发布图文').first
            if tab.count() > 0 and tab.is_visible():
                try:
                    tab.click(timeout=3000)
                except Exception:
                    pass
            else:
                # Try JS click on tab
                page.evaluate("""() => {
                    const tabs = Array.from(document.querySelectorAll('div, span, button'));
                    const tuwen = tabs.find(t => (t.innerText || '').trim() === '发布图文' || (t.innerText || '').trim() === '图文');
                    if (tuwen) tuwen.click();
                }""")
                
            time.sleep(2)
            inps = page.locator('input[type="file"]').all()
            for inp in inps:
                acc = inp.get_attribute('accept') or ''
                if 'image' in acc:
                    img_inp = inp
                    break
            if img_inp:
                print("  -> Found image file input element!")
                break
            time.sleep(1)
            
        if not img_inp:
            print("ERROR: Image input not found!")
            page.screenshot(path=os.path.join(BASE_DIR, 'err_no_input.png'))
            browser.close()
            return False
            
        print(f"[3/5] Setting files: {image_paths}...")
        img_inp.set_input_files(image_paths)
        
        print("Waiting for image processing...")
        uploaded = False
        for sec in range(60):
            time.sleep(1)
            body_txt = page.evaluate("() => document.body.innerText")
            if f"已添加{len(image_paths)}张图片" in body_txt or "重新上传" in body_txt or "更换图片" in body_txt:
                print(f"  -> All {len(image_paths)} images processed ({sec+1}s)!")
                uploaded = True
                break
                
        if not uploaded:
            print("  -> Upload detection timeout, continuing to form fill...")
            
        time.sleep(2)
        
        # Fill Title
        print(f"[4/5] Filling Title: '{title}'...")
        try:
            title_input = page.locator('input[placeholder*="标题"]').first
            if title_input.count() == 0:
                title_input = page.locator('input[type="text"]').first
            if title_input.count() > 0:
                title_input.click()
                title_input.fill(title)
                print("  -> Title filled successfully.")
            else:
                print("  -> Warning: Title input element not matched.")
        except Exception as e:
            print(f"Title fill error: {e}")
            
        # Fill Description
        clean_desc = re.sub(r'https?://\S+|www\.\S+', '', desc).strip() if desc else ""
        if clean_desc:
            print(f"Filling Description ({len(clean_desc)} chars)...")
            try:
                desc_zones = ['.zone-container', '.editor-kit-editor-container', '[contenteditable="true"]', 'textarea']
                for sel in desc_zones:
                    zone = page.locator(sel).first
                    if zone.count() > 0 and zone.is_visible():
                        zone.click()
                        page.keyboard.insert_text(clean_desc[:950])
                        print(f"  -> Description filled via {sel}.")
                        break
            except Exception as e:
                print(f"Description fill error: {e}")
                
        time.sleep(2)
        
        # Scroll to bottom
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        
        # Click 发布 button via native DOM evaluation
        print("[5/5] Clicking '发布' button via JS DOM evaluation...")
        clicked = page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            // Look for button with exact text '发布'
            const exactBtn = btns.find(b => (b.innerText || '').trim() === '发布');
            if (exactBtn) {
                exactBtn.scrollIntoView();
                exactBtn.click();
                return 'EXACT_CLICKED';
            }
            // Look for button containing '发布'
            const containBtn = btns.find(b => (b.innerText || '').includes('发布') && !b.disabled);
            if (containBtn) {
                containBtn.scrollIntoView();
                containBtn.click();
                return 'CONTAIN_CLICKED';
            }
            // Look for primary button
            const primary = document.querySelector('.semi-button-primary, [class*="primary"]');
            if (primary) {
                primary.click();
                return 'PRIMARY_CLICKED';
            }
            return 'NOT_FOUND';
        }""")
        print(f"  -> Publish button click result: {clicked}")
        
        # Wait for publish confirmation
        published = False
        print("Waiting for publish completion / redirection...")
        for s in range(30):
            time.sleep(1)
            cur_url = page.url
            body_txt = page.evaluate("() => document.body ? document.body.innerText : ''")
            if 'manage' in cur_url or '发布成功' in body_txt or 'content/post/image' in cur_url:
                print(f"SUCCESS: Note published at {s+1}s! URL: {cur_url}")
                published = True
                break
                
        proof_path = os.path.join(BASE_DIR, 'final_publish_result_20261105.png')
        page.screenshot(path=proof_path)
        print(f"Saved proof screenshot to {proof_path}")
        browser.close()
        return published

if __name__ == '__main__':
    target_json = sys.argv[1] if len(sys.argv) > 1 else '/root/ai_radar_publisher/temp_post_douyin.json'
    res = publish(target_json)
    if res:
        print("ALL DONE: PUBLISHED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("PUBLISH FAILED!")
        sys.exit(1)
