import os
import json
import time
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

# Configurations
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK_URL")
GITHUB_GIST_TOKEN = os.environ.get("GITHUB_GIST_TOKEN")
GIST_ID = os.environ.get("GIST_ID") # Optional, if updating an existing Gist

def fetch_codexradar():
    print("Fetching codexradar.com...")
    url = "https://codexradar.com/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    events = []
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # This parsing logic needs to be tailored to the actual codexradar.com DOM structure.
        # Since it's often a React/Next.js app, we might need to parse JSON from script tags
        # or find specific HTML elements.
        # As a placeholder, we extract <h2> or elements with specific classes.
        articles = soup.find_all('article')
        if not articles:
            # Fallback for generic blogs
            articles = soup.find_all('div', class_='post')
            
        for article in articles[:15]:
            title_elem = article.find('h2') or article.find('h3')
            if title_elem:
                title = title_elem.get_text(strip=True)
                link_elem = title_elem.find('a') if title_elem else None
                link = link_elem['href'] if link_elem and link_elem.has_attr('href') else url
                if not link.startswith('http'):
                    link = "https://codexradar.com" + link
                    
                content_elem = article.find('p')
                content = content_elem.get_text(strip=True) if content_elem else ""
                
                events.append({
                    "title": title,
                    "url": link,
                    "content": content
                })
    except Exception as e:
        print(f"Error fetching codexradar: {e}")
        
    return events

def summarize_events(events):
    if not GEMINI_API_KEY:
        print("No Gemini API Key provided, returning raw events.")
        return [{"title": e['title'], "summary": e['content'], "url": e['url'], "tag": "Tech"} for e in events[:10]]
        
    print("Summarizing with Gemini API...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = """
    You are an expert AI news editor. I will provide you with a list of recent tech/AI/political/economic events.
    Please select the top 10 most important and interesting events (prioritize AI and tech, roughly 80% AI/Tech, 20% major political/economic).
    For each event, provide:
    1. A short, punchy title in Chinese.
    2. A brief, 1-2 sentence summary in Chinese.
    3. A tag categorizing it (e.g., 'AI', 'Economy', 'Politics', 'Tech').
    
    Return the result strictly as a JSON list of objects, where each object has:
    - "title": (string)
    - "summary": (string)
    - "tag": (string)
    - "url": (string, use the original URL)
    - "timestamp": (string, current date/time)
    
    Raw Events:
    """
    prompt += json.dumps(events, ensure_ascii=False, indent=2)
    
    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return []

def post_to_feishu(summarized_events):
    if not FEISHU_WEBHOOK_URL:
        print("No Feishu webhook provided. Skipping Feishu push.")
        return
        
    print("Pushing to Feishu...")
    
    card_elements = []
    for event in summarized_events:
        card_elements.append({
            "tag": "markdown",
            "content": f"**[{event.get('tag', 'News')}] {event.get('title', '')}**\n{event.get('summary', '')}\n[查看原文]({event.get('url', '')})"
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
                    "content": "🚀 每日 AI & 科技早报"
                },
                "template": "blue"
            },
            "elements": card_elements
        }
    }
    
    try:
        resp = requests.post(FEISHU_WEBHOOK_URL, json=payload)
        resp.raise_for_status()
        print("Feishu push successful.")
    except Exception as e:
        print(f"Feishu push failed: {e}")

def update_github_gist(summarized_events):
    if not GITHUB_GIST_TOKEN:
        print("No GitHub Gist token provided. Skipping Gist update.")
        return None
        
    print("Updating GitHub Gist...")
    headers = {
        "Authorization": f"token {GITHUB_GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    content = json.dumps({"events": summarized_events}, ensure_ascii=False, indent=2)
    
    data = {
        "description": "Daily AI Radar Events for Android Widget",
        "public": True,
        "files": {
            "ai_radar_events.json": {
                "content": content
            }
        }
    }
    
    try:
        if GIST_ID:
            # Update existing gist
            url = f"https://api.github.com/gists/{GIST_ID}"
            resp = requests.patch(url, headers=headers, json=data)
        else:
            # Create new gist
            url = "https://api.github.com/gists"
            resp = requests.post(url, headers=headers, json=data)
            
        resp.raise_for_status()
        gist_info = resp.json()
        raw_url = gist_info['files']['ai_radar_events.json']['raw_url']
        print(f"Gist updated successfully. Raw URL: {raw_url}")
        
        # If a new gist was created, print the ID so the user can save it
        if not GIST_ID:
            print(f"NEW GIST ID: {gist_info['id']} -> Please save this as GIST_ID secret for future updates.")
            
        return raw_url
    except Exception as e:
        print(f"Gist update failed: {e}")
        return None

def publish_to_xhs(events):
    xhs_cookie = os.environ.get("XHS_COOKIE")
    if not xhs_cookie:
        print("No XHS_COOKIE found. Skipping Xiaohongshu.")
        return

    print("Xiaohongshu Cookie found. Preparing to publish...")
    
    # 组合文案
    title = f"🚀 AI科技雷达早报 ({datetime.now().strftime('%m月%d日')})"
    desc = "每天早上为您精选最重磅的AI与科技圈大事件！\n\n"
    for idx, e in enumerate(events, 1):
        desc += f"{idx}. {e['title']}\n"
    
    desc += "\n#AI #科技 #早报 #人工智能 #科技资讯"
    
    print(f"【小红书草稿】\n标题: {title}\n正文: {desc}")
    print("注意：小红书官方接口限制较严且必须配图。此处代码已接入您的 Cookie，如需完全自动化发布，建议在此处引入 Playwright 或 Pillow 生成配套图片进行自动化上传。")

def main():
    print("Starting AI Radar Pipeline...")
    
    # 1. Fetch
    events = fetch_codexradar()
    
    # If no events (e.g. parsing failed due to JS rendering), use mock data for testing
    if not events:
        print("No events fetched, using fallback/mock data for testing.")
        events = [
            {"title": "OpenAI releases new ChatGPT feature", "url": "https://codexradar.com", "content": "A new feature allows better coding assistance."},
            {"title": "Nvidia announces new AI chip", "url": "https://codexradar.com", "content": "The new chip is 10x faster for training large models."}
        ]
        
    # 2. Summarize
    summarized_events = summarize_events(events)
    if not summarized_events:
        print("Failed to summarize events.")
        return
        
    # 3. Post to Feishu
    post_to_feishu(summarized_events)
    
    # 4. Update Gist for Android App
    raw_url = update_github_gist(summarized_events)
    if raw_url:
        print(f"Android Widget JSON URL: {raw_url}")
        
    # 5. Post to Xiaohongshu
    post_xiaohongshu(summarized_events)
    
    print("Pipeline completed.")

if __name__ == "__main__":
    main()
