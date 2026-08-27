import os
import requests
import json

GITHUB_GIST_TOKEN = os.environ.get("GITHUB_GIST_TOKEN")
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK_URL")

dummy_events = [
    {
        "title": "测试新闻标题：AI雷达小组件连接成功！",
        "summary": "这是来自后台自动发送的一条测试消息，说明飞书和GitHub Gist通路均已打通。",
        "tag": "系统通知",
        "url": "https://codexradar.com"
    }
]

# Test Feishu
payload = {
    "msg_type": "interactive",
    "card": {
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "🚀 AI 雷达测试"
            },
            "template": "blue"
        },
        "elements": [
            {
                "tag": "markdown",
                "content": f"**[{dummy_events[0]['tag']}] {dummy_events[0]['title']}**\n{dummy_events[0]['summary']}\n[查看原文]({dummy_events[0]['url']})"
            }
        ]
    }
}
resp = requests.post(FEISHU_WEBHOOK_URL, json=payload)
print(f"Feishu test: {resp.status_code}")

# Test Gist
headers = {
    "Authorization": f"token {GITHUB_GIST_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}
data = {
    "description": "Daily AI Radar Events for Android Widget",
    "public": True,
    "files": {
        "ai_radar_events.json": {
            "content": json.dumps({"events": dummy_events}, ensure_ascii=False, indent=2)
        }
    }
}
resp2 = requests.post("https://api.github.com/gists", headers=headers, json=data)
print(f"GitHub Gist test: {resp2.status_code}")
if resp2.status_code == 201:
    print(f"Gist ID: {resp2.json().get('id')}")
