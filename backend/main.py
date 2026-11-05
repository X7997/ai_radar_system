import os
import json
import time
import requests
import subprocess
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image, ImageDraw
from mail_fetcher import fetch_summarized_events_from_gmail

load_dotenv()

# Configurations
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK_URL")
GITHUB_GIST_TOKEN = os.environ.get("GITHUB_GIST_TOKEN")
GIST_ID = os.environ.get("GIST_ID") # Optional, if updating an existing Gist

def post_to_feishu(summarized_events):
    if not FEISHU_WEBHOOK_URL:
        print("未配置飞书 Webhook，跳过飞书推送。")
        return
        
    print("正在推送至飞书群机器人...")
    
    card_elements = []
    for event in summarized_events:
        content_text = event.get('full_text', event.get('summary', ''))
        # Limit text length in Feishu to avoid huge cards, or just pass it all
        if len(content_text) > 2000:
            content_text = content_text[:2000] + "...(阅读更多)"
            
        url_text = f"\n\n[🔗 点击直达原文]({event.get('url')})" if event.get('url') else ""
        card_elements.append({
            "tag": "markdown",
            "content": f"**[{event.get('tag', 'CodexRadar')}] {event.get('title', '')}**\n\n{content_text}{url_text}"
        })
        card_elements.append({
            "tag": "hr"
        })
        
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "🚀 AI 雷达邮箱专报"
                },
                "template": "blue"
            },
            "elements": card_elements
        }
    }
    
    try:
        resp = requests.post(FEISHU_WEBHOOK_URL, json=payload)
        resp.raise_for_status()
        print("飞书卡片推送成功。")
    except Exception as e:
        print(f"飞书卡片推送失败: {e}")

def update_github_gist(summarized_events):
    if not GITHUB_GIST_TOKEN:
        print("未配置 GITHUB_GIST_TOKEN，跳过 Gist 同步。")
        return None
        
    print("正在更新 GitHub Gist 数据...")
    headers = {
        "Authorization": f"token {GITHUB_GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    content = json.dumps({"events": summarized_events}, ensure_ascii=False, indent=2)
    
    data = {
        "description": "AI Radar 安卓桌面小组件资讯流",
        "public": True,
        "files": {
            "ai_radar_events.json": {
                "content": content
            }
        }
    }
    
    try:
        if GIST_ID:
            url = f"https://api.github.com/gists/{GIST_ID}"
            resp = requests.patch(url, headers=headers, json=data)
        else:
            url = "https://api.github.com/gists"
            resp = requests.post(url, headers=headers, json=data)
            
        resp.raise_for_status()
        gist_info = resp.json()
        import re
        raw_url = gist_info['files']['ai_radar_events.json']['raw_url']
        raw_url = re.sub(r'/raw/[a-f0-9]+/', '/raw/', raw_url)
        print(f"GitHub Gist 同步成功！直链 URL: {raw_url}")
        
        if not GIST_ID:
            print(f"NEW GIST ID: {gist_info['id']} -> Please save this as GIST_ID secret for future updates.")
            
        return raw_url
    except Exception as e:
        print(f"GitHub Gist 同步失败: {e}")
        return None

def publish_to_xhs(events):
    print("小红书发布流程已启动...")
    title = f"🚀 AI科技雷达早报 ({datetime.now().strftime('%m月%d日')})"
    desc = "每天早上为您精选最重磅的AI与科技圈大事件！\n\n"
    for idx, e in enumerate(events, 1):
        desc += f"{idx}. {e['title']}\n"
        if len(desc) > 800:
            desc += "...详细内容请看主页哦！"
            break
    
    desc += "\n#AI #科技 #早报 #人工智能 #科技资讯"
    
def publish_to_xhs(event, image_path):
    print("正在将待发布任务保存至 pending_xhs_tasks.json...")
    
    title = f"AI Radar 科技早报 {datetime.now().strftime('%Y-%m-%d')}"
    desc = f"今日 AI 科技速览：\n\n{event['summary']}\n\n#AI #科技 #人工智能"
    
    task_data = {
        "title": title,
        "desc": desc,
        "image_file": os.path.basename(image_path),
        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "date_str": datetime.now().strftime('%Y-%m-%d')
    }
    
    task_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pending_xhs_tasks.json")
    try:
        with open(task_file, "w", encoding="utf-8") as f:
            json.dump(task_data, f, ensure_ascii=False, indent=2)
        print(f"任务已持久化写入 {task_file}")
        return True
    except Exception as e:
        print(f"保存任务文件失败: {e}")
        return False

def main():
    print("启动 AI Radar 处理流水线 (Gmail IMAP 抓取模式)...")
    
    events = fetch_summarized_events_from_gmail()
    
    if not events:
        print("未检索到符合条件的邮件或缺少凭证，检查备用流程。")
        return
        
    post_to_feishu(events)
    
    raw_url = update_github_gist(events)
    if raw_url:
        print(f"安卓桌面小组件数据源 URL: {raw_url}")
    if events:
        print("正在生成纯色背景排版图片...")
        img_path = "xhs_bg.jpg"
        try:
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (1080, 1440), color=(173, 216, 230))
            d = ImageDraw.Draw(img)
            d.text((100, 700), "AI Radar Daily News", fill=(0, 0, 0))
            img.save(img_path)
        except Exception as e:
            print(f"生成图片失败: {e}")
            return
            
        publish_to_xhs(events[0], img_path)
    
    print("AI Radar 任务流水线执行圆满完成！")

if __name__ == "__main__":
    main()
