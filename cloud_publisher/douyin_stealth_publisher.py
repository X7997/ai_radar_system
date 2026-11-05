#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI Radar 抖音全自主深度伪装发布器（真实家庭 PC 环境模拟）
- 模拟真实 Windows 10 x64 + NVIDIA GeForce RTX 3060 独立显卡桌面环境
- 完整恢复并保护 Cookie 与 localStorage 授权状态
- 杜绝异常时误清空凭证文件
- 采用原生 JavaScript DOM 事件穿透触发发布按钮
"""

import os
import sys
import time
import json
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

# 强制 UTF-8 标准输出
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

try:
    from playwright_stealth import Stealth
    stealth_applier = Stealth().apply_stealth_sync
except Exception:
    stealth_applier = None

BASE_DIR = '/root/ai_radar_publisher'
STATE_PATH = os.path.join(BASE_DIR, 'douyin_state.json')

# 全套真实家庭 PC 环境指纹伪装注入脚本
DISGUISE_JS = """
(() => {
    // 1. 篡改并抹除 Webdriver 与 Linux 标识，伪装为 Win32 平台
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
    
    // 2. 补齐真实 Chrome 浏览器运行时 window.chrome 对象
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
    
    // 3. WebGL 显卡驱动欺骗：抹除虚拟机 SwiftShader，伪装为 NVIDIA RTX 3060
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
    
    // 4. 物理屏幕分辨率与真彩色伪装 (1920x1080)
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
    
    print(f"[{datetime.now()}] 启动云端家庭环境深度伪装发布器...")
    print(f"早报标题: {title} | 配图数量: {len(image_paths)}")
    
    if not os.path.exists(STATE_PATH):
        print(f"错误: 登录凭证文件 {STATE_PATH} 不存在！请先扫码完成授权。")
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
            
        print("[1/5] 正在打开抖音创作者中心图文发布页面...")
        page.goto("https://creator.douyin.com/creator-micro/content/upload", timeout=60000, wait_until="domcontentloaded")
        time.sleep(5)
        
        cur_url = page.url
        body = page.evaluate("() => document.body ? document.body.innerText : ''")
        print(f"当前页面地址: {cur_url}")
        
        # 校验登录态是否仍然有效
        if "我是创作者" in body or "扫码登录" in body:
            print("错误: 当前登录态已失效，页面重定向至登录入口！请更新凭证。")
            page.screenshot(path=os.path.join(BASE_DIR, 'err_not_logged_in.png'))
            browser.close()
            return False
            
        # 智能切换至【发布图文】标签页
        print("[2/5] 正在智能切换至【发布图文】标签页...")
        img_inp = None
        for attempt in range(5):
            tab = page.locator('text=发布图文').first
            if tab.count() > 0 and tab.is_visible():
                try:
                    tab.click(timeout=3000)
                except Exception:
                    pass
            else:
                # 原生 JS 点击备用
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
                print("  -> 已找到图片上传文件控件！")
                break
            time.sleep(1)
            
        if not img_inp:
            print("错误: 未能在页面中找到图文上传控件！")
            page.screenshot(path=os.path.join(BASE_DIR, 'err_no_input.png'))
            browser.close()
            return False
            
        print(f"[3/5] 正在批量上传早报图片 ({len(image_paths)} 张)...")
        img_inp.set_input_files(image_paths)
        
        print("正在等待云端图片压缩与排版处理...")
        uploaded = False
        for sec in range(60):
            time.sleep(1)
            body_txt = page.evaluate("() => document.body.innerText")
            if f"已添加{len(image_paths)}张图片" in body_txt or "重新上传" in body_txt or "更换图片" in body_txt:
                print(f"  -> 全部 {len(image_paths)} 张图片已处理完毕 (耗时 {sec+1} 秒)！")
                uploaded = True
                break
                
        if not uploaded:
            print("  -> 图片上传检测超时，继续推进后续表单填写...")
            
        time.sleep(2)
        
        # 自动填入早报标题
        print(f"[4/5] 正在填入早报标题: '{title}'...")
        try:
            title_input = page.locator('input[placeholder*="标题"]').first
            if title_input.count() == 0:
                title_input = page.locator('input[type="text"]').first
            if title_input.count() > 0:
                title_input.click()
                title_input.fill(title)
                print("  -> 标题已成功填入。")
            else:
                print("  -> 提示: 未匹配到标题输入框控件。")
        except Exception as e:
            print(f"标题填入异常: {e}")
            
        # 自动填入早报文案与话题标签
        clean_desc = re.sub(r'https?://\\S+|www\\.\\S+', '', desc).strip() if desc else ""
        if clean_desc:
            print(f"正在填入早报文案 ({len(clean_desc)} 字)...")
            try:
                desc_zones = ['.zone-container', '.editor-kit-editor-container', '[contenteditable="true"]', 'textarea']
                for sel in desc_zones:
                    zone = page.locator(sel).first
                    if zone.count() > 0 and zone.is_visible():
                        zone.click()
                        page.keyboard.insert_text(clean_desc[:950])
                        print(f"  -> 文案已通过 {sel} 填入。")
                        break
            except Exception as e:
                print(f"文案填入异常: {e}")
                
        time.sleep(2)
        
        # 滚动到底部
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        
        # 原生 JavaScript DOM 穿透直击点击【发布】按钮
        print("[5/5] 正在通过原生 JS DOM 穿透直击【发布】按钮...")
        clicked = page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const exactBtn = btns.find(b => (b.innerText || '').trim() === '发布');
            if (exactBtn) {
                exactBtn.scrollIntoView();
                exactBtn.click();
                return 'EXACT_CLICKED';
            }
            const containBtn = btns.find(b => (b.innerText || '').includes('发布') && !b.disabled);
            if (containBtn) {
                containBtn.scrollIntoView();
                containBtn.click();
                return 'CONTAIN_CLICKED';
            }
            const primary = document.querySelector('.semi-button-primary, [class*="primary"]');
            if (primary) {
                primary.click();
                return 'PRIMARY_CLICKED';
            }
            return 'NOT_FOUND';
        }""")
        print(f"  -> 发布按钮触发状态: {clicked}")
        
        # 等待发布成功跳转
        published = False
        print("正在等待发布完成与页面跳转...")
        for s in range(30):
            time.sleep(1)
            cur_url = page.url
            body_txt = page.evaluate("() => document.body ? document.body.innerText : ''")
            if 'manage' in cur_url or '发布成功' in body_txt or 'content/post/image' in cur_url:
                print(f"成功: 今日早报已成功发布！(耗时 {s+1} 秒) 页面: {cur_url}")
                published = True
                break
                
        proof_path = os.path.join(BASE_DIR, 'final_publish_result_20261105.png')
        page.screenshot(path=proof_path)
        print(f"存证截图已保存至: {proof_path}")
        browser.close()
        return published

if __name__ == '__main__':
    target_json = sys.argv[1] if len(sys.argv) > 1 else '/root/ai_radar_publisher/temp_post_douyin.json'
    res = publish(target_json)
    if res:
        print("所有流程已圆满完成：今日早报已成功发布至抖音！")
        sys.exit(0)
    else:
        print("发布流程未完全确认！")
        sys.exit(1)
