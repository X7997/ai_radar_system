#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import ssl
import json
import re
import copy
import time
import smtplib
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr, formatdate, parsedate_to_datetime
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types
from playwright.sync_api import sync_playwright

try:
    from playwright_stealth import Stealth
    stealth_applier = Stealth().apply_stealth_sync
except Exception:
    stealth_applier = None

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ==================== CONFIGURATION ====================
BASE_DIR = "/root"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6IwBJF4HZmqZoCjZuRXc5ukksMJXCZVfSFVJ0O_yGLPwg")

MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.8-flash"
]

SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
SMTP_USER = "356719037@qq.com"
SMTP_PASS = os.getenv("SMTP_PASS", "your_qq_smtp_auth_code")  # QQ Mail Auth Code
TARGET_EMAIL = "356719037@qq.com"

GITHUB_GIST_ID = "7ad36328320740c54905a64368c2ee2f"
GITHUB_GIST_TOKEN = os.getenv("GITHUB_GIST_TOKEN", "your_github_gist_token")

HISTORY_FILE = os.path.join(BASE_DIR, "ai_radar_history.json")
LOGS_DIR = os.path.join(BASE_DIR, "ai_radar_logs")
PENDING_TASKS_FILE = os.path.join(BASE_DIR, "pending_xhs_tasks.json")
RECEIPT_FILE = os.path.join(BASE_DIR, "publish_receipt.json")
DOUYIN_STATE_FILE = os.path.join(BASE_DIR, "douyin_state.json")
CARDS_OUTPUT_DIR = os.path.join(BASE_DIR, "generated_cards")

FONT_REG_PATH = os.path.join(BASE_DIR, "msyh.ttc")
FONT_BOLD_PATH = os.path.join(BASE_DIR, "msyhbd.ttc")
# =======================================================

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

now_utc = datetime.now(timezone.utc)

STALE_TOPIC_BLACKLIST = [
    {"waymo", "50亿"},
    {"waymo", "50", "billion"},
    {"biohub", "18亿"},
    {"biohub", "18", "billion"},
    {"minimax", "估值"},
    {"minimax", "缩水"},
    {"格芯", "台积电", "20亿"},
    {"globalfoundries", "tsmc"},
    {"pacbio", "tychobio"},
    {"康涅狄格", "lamont"},
    {"tibo", "周二", "充值"},
    {"tibo", "周二", "重置"},
    {"auto-review", "全员"},
    {"outsystems", "claude"}
]

STOP_WORDS = {
    'the', 'and', 'for', 'with', 'news', 'ai', 'model', 'report', 'first', 'new',
    'says', 'official', 'tech', 'industry', 'into', 'from', 'about', 'after', 'over',
    'that', 'this', 'will', 'have', 'more', 'than', 'just', 'been', 'their', 'were',
    'today', 'daily', 'breaking', 'update', 'latest', 'release', 'launches', 'announces',
    '推出', '发布', '全新', '今日', '重磅', '正式', '全面', '宣布', '首次', '曝光', '迎来'
}

def extract_title_keywords(title):
    if not title:
        return set()
    words = re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z]{3,}', title.lower())
    return {w for w in words if w not in STOP_WORDS}

def is_stale_topic(title, snippet=""):
    combined = (title + " " + snippet).lower()
    for topic_set in STALE_TOPIC_BLACKLIST:
        if all(kw in combined for kw in topic_set):
            return True
    return False

def parse_pub_date(pub_date_str):
    if not pub_date_str:
        return None
    try:
        if 'T' in pub_date_str:
            clean_str = pub_date_str.replace('Z', '+00:00')
            return datetime.fromisoformat(clean_str)
        return parsedate_to_datetime(pub_date_str)
    except Exception:
        return None

def is_within_timeframe(pub_date_str, max_hours=36):
    if not pub_date_str:
        return True
    dt = parse_pub_date(pub_date_str)
    if not dt:
        return True
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age = now_utc - dt
    return age <= timedelta(hours=max_hours)

def load_history_blacklist(days=7):
    if not os.path.exists(HISTORY_FILE):
        return "", {}, []
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history_db = json.load(f)
    except Exception as e:
        print(f"读取历史记录异常: {e}")
        return "", {}, []

    all_recent_titles = []
    lines = []
    today = datetime.now()
    for date_str, items in sorted(history_db.items(), reverse=True):
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d')
            delta = (today - d).days
            if 0 < delta <= days:
                lines.append(f"--- 【{date_str} 历史报道记录】 ---")
                for it in items:
                    t = it.get('title', '')
                    all_recent_titles.append(t)
                    lines.append(f"- {t}")
        except Exception:
            continue

    blacklist_text = "\n".join(lines)
    print(f"已成功加载过去 {days} 天历史库，共包含 {len(all_recent_titles)} 条历史标题。")
    return blacklist_text, history_db, all_recent_titles

def is_historical_duplicate(title, history_titles):
    curr_kw = extract_title_keywords(title)
    if not curr_kw:
        return False
    for past_title in history_titles:
        past_kw = extract_title_keywords(past_title)
        if not past_kw:
            continue
        common = curr_kw & past_kw
        if len(common) >= 3 or (len(common) >= 2 and len(curr_kw) <= 4):
            return True
    return False

def fetch_codexradar():
    print("[1/6] 扫描 Codex 雷达主站: https://codexradar.com/ ...")
    req = urllib.request.Request(
        'https://codexradar.com/',
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    )
    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"抓取 codexradar 异常: {e}")
        html = ""

    sections = []
    if html:
        soup = BeautifulSoup(html, 'html.parser')
        sec1 = soup.find('section', class_=lambda c: c and 'hero-news-marquee' in c)
        if sec1:
            sections.append("【Hero 实时滚动条】\n" + sec1.get_text(separator=' ', strip=True)[:500])
            
        tibo_sec = soup.find('section', class_=lambda c: c and 'desktop-tibo-radar' in c)
        if tibo_sec:
            sections.append("【Codex 官方最新状态速览】\n" + tibo_sec.get_text(separator=' ', strip=True)[:400])

    combined = "\n\n".join(sections)
    print(f"Codex Radar 扫描完成，共提取 {len(combined)} 字符。")
    return combined

def fetch_fresh_tech_pool(history_titles):
    print("[2/6] 向外深度扩散检索全球高实时性科技生态 (时间窗口严格限制 <= 36h)...")
    candidates = []
    seen_titles = set()
    filtered_duplicates = 0

    google_feeds = [
        ('(OpenAI OR Anthropic OR "Google DeepMind" OR "DeepSeek" OR "Qwen" OR "Meta AI" OR "Mistral") when:24h', 'en-US', 'US', 'US:en', 'FrontierLLM'),
        ('("Claude Code" OR "Cursor AI" OR "Devin AI" OR "MCP server" OR "vLLM" OR "Ollama" OR "coding agent") when:24h', 'en-US', 'US', 'US:en', 'DevTools&Agents'),
        ('(NVIDIA OR "TSMC" OR "ASML" OR "AMD" OR "Blackwell" OR "H100" OR "AI chip" OR "HBM") when:24h', 'en-US', 'US', 'US:en', 'Hardware&Chips'),
        ('("humanoid robot" OR "Tesla Optimus" OR "Figure AI" OR "Unitree" OR "autonomous driving" OR "Waymo") when:24h', 'en-US', 'US', 'US:en', 'Robotics&Embodied'),
        ('("AlphaFold" OR "AI drug discovery" OR "AI biology" OR "AI quantum" OR "AI science") when:24h', 'en-US', 'US', 'US:en', 'AIScience&Biotech'),
        ('(人工智能 OR 大模型 OR 具身智能 OR 开源大模型 OR 算力中心 OR 智能体) when:24h', 'zh-CN', 'CN', 'CN:zh-Hans', 'DomesticAI'),
        ('("AI startup" OR "AI regulation" OR "AI acquisition" OR "AI venture" OR "AI datacenter") when:24h', 'en-US', 'US', 'US:en', 'Industry&Policy'),
        ('(中美科技 OR "出口管制" OR "芯片制裁" OR "科技峰会" OR "科技外交" OR "商务部") when:24h', 'zh-CN', 'CN', 'CN:zh-Hans', 'TechDiplomacy&Geopolitics'),
        ('("US-China tech" OR "semiconductor export control" OR "AI sanctions" OR "AI summit") when:24h', 'en-US', 'US', 'US:en', 'TechDiplomacy&Geopolitics')
    ]

    for q, hl, gl, ceid, cat in google_feeds:
        encoded_q = urllib.parse.quote(q)
        u = f"https://news.google.com/rss/search?q={encoded_q}&hl={hl}&gl={gl}&ceid={ceid}"
        try:
            req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=8) as resp:
                xml = resp.read().decode('utf-8', errors='ignore')
                soup = BeautifulSoup(xml, 'xml')
                for it in soup.find_all('item')[:12]:
                    t = it.title.text if it.title else ""
                    pub = it.pubDate.text if it.pubDate else ""
                    link = it.link.text if it.link else ""
                    desc = BeautifulSoup(it.description.text, 'html.parser').get_text(strip=True) if it.description else ""

                    if not is_within_timeframe(pub, 36):
                        continue
                    if is_stale_topic(t, desc):
                        continue
                    if is_historical_duplicate(t, history_titles):
                        filtered_duplicates += 1
                        continue

                    clean_t = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', t.lower())
                    if clean_t and clean_t not in seen_titles:
                        seen_titles.add(clean_t)
                        candidates.append({
                            "title": t,
                            "date": pub,
                            "link": link,
                            "snippet": desc[:250],
                            "category": cat,
                            "source": "GoogleNews"
                        })
        except Exception as e:
            print(f"Google RSS {cat} error: {e}")

    direct_rss = [
        ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "Industry&Dev"),
        ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "Frontier&Culture")
    ]
    for name, url, cat in direct_rss:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=8) as resp:
                xml = resp.read().decode('utf-8', errors='ignore')
                soup = BeautifulSoup(xml, 'xml')
                for it in soup.find_all(['item', 'entry'])[:8]:
                    t = it.title.text if it.title else ""
                    pub = (it.pubDate.text if it.pubDate else (it.updated.text if it.updated else ""))
                    link = it.link.text if it.link and it.link.text else (it.link.get('href') if it.link else "")
                    desc = BeautifulSoup(it.description.text if it.description else (it.summary.text if it.summary else ""), 'html.parser').get_text(strip=True)

                    if not is_within_timeframe(pub, 36):
                        continue
                    if is_stale_topic(t, desc):
                        continue
                    if is_historical_duplicate(t, history_titles):
                        filtered_duplicates += 1
                        continue

                    clean_t = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', t.lower())
                    if clean_t and clean_t not in seen_titles:
                        seen_titles.add(clean_t)
                        candidates.append({
                            "title": t,
                            "date": pub,
                            "link": link,
                            "snippet": desc[:250],
                            "category": cat,
                            "source": name
                        })
        except Exception as e:
            print(f"Direct RSS {name} error: {e}")

    try:
        req = urllib.request.Request('https://huggingface.co/api/daily_papers', headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=8) as resp:
            papers = json.loads(resp.read().decode('utf-8'))
            for p in papers[:6]:
                paper = p.get('paper', {})
                t = paper.get('title', '')
                summary = paper.get('summary', '')
                upvotes = paper.get('upvotes', 0)
                pid = paper.get('id', '')
                link = f"https://huggingface.co/papers/{pid}" if pid else "https://huggingface.co/papers"

                if is_historical_duplicate(t, history_titles):
                    filtered_duplicates += 1
                    continue

                clean_t = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', t.lower())
                if clean_t and clean_t not in seen_titles:
                    seen_titles.add(clean_t)
                    candidates.append({
                        "title": f"{t} (HF Daily Top Paper, {upvotes} Upvotes)",
                        "date": datetime.now().strftime('%Y-%m-%d'),
                        "link": link,
                        "snippet": summary[:250],
                        "category": "AIScience&Research",
                        "source": "HuggingFace"
                    })
    except Exception as e:
        print(f"HuggingFace error: {e}")

    print(f"聚合引擎抓取完毕！过滤历史重复 {filtered_duplicates} 条，共获得 {len(candidates)} 条高实时性候选资讯！")
    return candidates

def validate_brief_structure(brief_text):
    if not brief_text or len(brief_text) < 1200:
        return False
    # 多容错正则切分模块一和模块二
    parts = re.split(r'【.*?TOP\s*10.*?】|###\s*🎯.*?TOP\s*10|第二模块|模块二|--------------------------------------------------', brief_text, flags=re.IGNORECASE)
    if len(parts) >= 2:
        mod1_items = re.findall(r'(?:^|\n)\s*\d+\.\s+', parts[0])
        mod2_items = re.findall(r'(?:^|\n)\s*\d+\.\s+', parts[1])
        if len(mod1_items) >= 3 and len(mod2_items) >= 6:
            return True
    # 兜底：若总体编号 >= 12 且具备双语解读字段，视为结构合法
    total_items = re.findall(r'(?:^|\n)\s*\d+\.\s+', brief_text)
    if len(total_items) >= 12 and "English" in brief_text and "中文解读" in brief_text:
        return True
    return False

def generate_radar_brief(codex_data, news_items, history_blacklist_text):
    print("[3/6] 启动 Gemini 顶级大模型进行智能深度情报研判与早报生成...")
    client = genai.Client(api_key=GEMINI_API_KEY)

    today_dt = datetime.now()
    date_header = today_dt.strftime('%Y年%m月%d日')

    prompt = f"""你是一名顶级资深 AI 科技总编与全球前沿科技情报分析专家。请根据下方实时抓取的新鲜素材库，为读者编译一份极具时效性、深度洞察力与专业价值的【AI Radar 每日科技早报】（日期：{date_header}）。

【核心原则：100% 真实时效，零滞后，零重复，拒绝陈旧旧闻】：
1. 必须优先选用过去 24~36 小时内真实发生的最新突发动态、技术发布与行业深度事件。
2. 绝对严禁报道以下已知陈旧历史话题：
   - 严禁报道 Waymo 50 亿美元融资旧闻；
   - 严禁报道 Biohub 18 亿美元科学计划旧闻；
   - 严禁报道 MiniMax 估值缩水旧闻；
   - 严禁报道 格芯与台积电 20 亿美元战略合作旧闻；
   - 严禁报道 历史过期的 Tibo 周二充值预告或 9 月 27 日充值卡预告！
3. 若素材库中没有 Tibo 在过去 24 小时内真实发布的最新重磅动作，第一模块第 1 条直接选用当天最重磅的硬核开发者工具（如 Anthropic 针对开源项目的免费 AI 安全扫描、Claude Code 终端生态、最新 MCP 协议落地等）！

【版块架构要求（严格 14 条对称排版）】：
1. **第一模块：【🚀 AI Radar · 顶尖工具与高管速递 / Executive & Tool Highlights】（严格 4 条，1~4 序号排列）**：
   - 聚焦过去 24 小时内最硬核的全球 AI 开发者工具、Agent 框架、开源基础设施（如 Claude Code, Cursor, MCP Servers, vLLM, 深度数学/代码生成突破等）。

2. **第二模块：【🎯 今日核心精选（TOP 10） / Top 10 Industry Highlights】（必须严格 10 条，1~10 序号依次排列）**：
   - 必须按专业垂直领域打上标准分类标签，严禁全篇雷同，覆盖：
     - 【#前沿模型】（OpenAI、Anthropic、DeepMind、DeepSeek 等最新模型突破、财务营收数据、政策更新）
     - 【#芯片半导体】（英伟达、台积电、ASML、AMD、算力基础设施与能耗革命）
     - 【#具身智能】（人形机器人、自动驾驶、物理世界交互大模型）
     - 【#AI科学】（数学定理证明、AI 生物医药、世界模型、前沿科研 Paper）
     - 【#国内落地】（国内企业级智能体、算力中心、政企工业落地）
     - 【#宏观政策】（科技外交、国际 AI 治理、监管与出口管制新动向）

【⚠️ 🇨🇳 中文解读深度与长度铁律（极其重要！必须写满 3~4 行 / 80~150 字）】：
- **绝对严禁只写一句干巴巴的一两行概括（严禁 40 字以内的短句）！**
- 每一条新闻的“中文解读”必须充分展开为 **3~4 行深度通俗解读（字数严格保持在 80~150 字之间）**：
  1. 讲清楚事情的来龙去脉与核心事实；
  2. 用通俗大白话拆解背后的技术原理、产品细节或商业博弈逻辑；
  3. 讲透对普通用户、行业开发者或上下游产业链的实际影响与具体意义；
  4. 关键结论、核心指标或关键实体必须用 **粗体** 标注。

【⚠️ 每一条新闻（共 14 条）必须严格具备的 100% 对称三段式结构】：
每一条新闻都必须包含以下 3 个子项，缺一不可：
1. 标题：【#标签】英文标题 (中文标题)  [第一模块无需带标签]
• 🇺🇸 English: 一句话精准地道英文摘要。
• 🇨🇳 中文解读: 80~150 字的通俗深度大白话解读（3~4 行，包含背景、博弈逻辑与实际影响，关键结论加粗 **...**）。
• 🔗 一手出处 / 深度报道出处：真实 URL（优先使用素材库中提供的一手文章链接）。

【排版绝对约束】：
- 模块间必须使用正好 50 个短横线分隔（--------------------------------------------------）；
- 子项引导符必须统一使用实心圆点“•”；
- 单次紧凑输出全部内容，末尾严禁附加任何客套话。

【过去 7 天已发历史新闻黑名单（严禁重复！绝对不得再次报道以下主题）】：
{history_blacklist_text if history_blacklist_text else "暂无历史黑名单（首次运行）"}

【实时输入新鲜素材库（共 {len(news_items)} 条候选）】：
{json.dumps(news_items[:80], ensure_ascii=False, indent=1)}
"""

    for m in MODELS:
        print(f"正在调用大模型候选: {m} ...")
        for attempt in range(1, 4):
            try:
                print(f"  [{m}] 第 {attempt}/3 次尝试生成...")
                resp = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        max_output_tokens=8192
                    )
                )
                if resp and resp.text:
                    candidate_text = resp.text.strip()
                    if validate_brief_structure(candidate_text):
                        print(f"大模型 {m} (第 {attempt} 次) 成功生成包含深度解读与全对称结构的早报！")
                        return candidate_text
                    else:
                        print(f"  [{m}] 结构校验未通过(长度 {len(candidate_text)})，准备重试或备选...")
                else:
                    print(f"  [{m}] 返回空内容或被安全策略过滤...")
            except Exception as e:
                err_str = str(e)
                print(f"  [{m}] 调用异常: {err_str}")
                if any(kw in err_str for kw in ["503", "UNAVAILABLE", "high demand", "RESOURCE_EXHAUSTED", "timeout"]):
                    wait_s = attempt * 4
                    print(f"  遇到服务过载或网络拥堵，休眠 {wait_s} 秒后退避重试...")
                    time.sleep(wait_s)
                else:
                    break

    raise RuntimeError("所有模型及重试均失败，请检查 API Key 或网络环境。")

def get_zh_title(t):
    if not t: return ''
    t = t.strip()
    t = re.sub(r'【#[\w\u4e00-\u9fa5\s]+】\s*', '', t).strip()
    norm = t.replace('（', '(').replace('）', ')')
    if norm.endswith(')'):
        depth, open_idx = 0, -1
        for idx in range(len(norm) - 1, -1, -1):
            if norm[idx] == ')': depth += 1
            elif norm[idx] == '(':
                depth -= 1
                if depth == 0:
                    open_idx = idx
                    break
        if open_idx != -1:
            candidate = norm[open_idx + 1:-1].strip()
            if re.search(r'[\u4e00-\u9fa5]', candidate):
                return candidate
    m = re.search(r'^([^(]+[\u4e00-\u9fa5]+[^(]*)\(', norm)
    if m: return m.group(1).strip()
    matches = list(re.finditer(r'\((.*?)\)', norm))
    for m in reversed(matches):
        if re.search(r'[\u4e00-\u9fa5]', m.group(1)):
            return m.group(1).strip()
    return t

def parse_brief_to_events(brief_text, date_str=None):
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
    events = []

    parts = re.split(r'【.*?TOP\s*10.*?】|###\s*🎯.*?TOP\s*10', brief_text, flags=re.IGNORECASE)
    mod1 = parts[0]
    mod2 = parts[1] if len(parts) > 1 else ''

    def extract_items(text_block, default_tag='CodexRadar'):
        items = []
        raw_items = re.split(r'\n(?=\s*\d+\.\s+)', text_block)
        for chunk in raw_items:
            chunk = chunk.strip()
            if not chunk or not re.match(r'^\s*\d+\.\s+', chunk):
                continue
            lines = chunk.split('\n')
            first_line = re.sub(r'^\s*\d+\.\s*', '', lines[0].strip()).strip()
            tag = default_tag
            tag_match = re.search(r'【#([\w\u4e00-\u9fa5]+)】|#([\w\u4e00-\u9fa5]+)', first_line)
            if tag_match:
                tag = tag_match.group(1) or tag_match.group(2)
                first_line = re.sub(r'【#[\w\u4e00-\u9fa5]+】|#[\w\u4e00-\u9fa5]+', '', first_line).strip()
            raw_title = first_line
            zh_title = get_zh_title(raw_title)

            # 1. 提取英文摘要 (支持全角/半角冒号、Emoji、Markdown加粗)
            en_match = re.search(
                r'[-•*]?\s*(?:🇺🇸\s*)?(?:【|\*\*)?English(?:】|\*\*)?[:：]\s*(.*?)(?=\n\s*[-•*]|\n\s*🇨🇳|\n\s*中文解读|\Z)',
                chunk, re.DOTALL | re.IGNORECASE
            )
            en_desc = en_match.group(1).replace('\r\n', ' ').replace('\n', ' ').strip() if en_match else ''

            # 2. 提取中文深度解读 (支持全角/半角冒号、Emoji、Markdown加粗)
            zh_match = re.search(
                r'[-•*]?\s*(?:🇨🇳\s*)?(?:【|\*\*)?中文解读(?:】|\*\*)?[:：]\s*(.*?)(?=\n\s*[-•*]|\n\s*🔗|\n\s*一手出处|\n\s*深度报道出处|\Z)',
                chunk, re.DOTALL | re.IGNORECASE
            )
            zh_desc = zh_match.group(1).replace('\r\n', ' ').replace('\n', ' ').strip() if zh_match else ''

            # 3. 兜底保障：若正则未命中，逐行扫描寻找包含中文字符的正文段落（跳过标题行、英文行和链接行）
            if not zh_desc or not re.search(r'[\u4e00-\u9fa5]', zh_desc):
                candidate_zh = []
                for l in lines[1:]:
                    ls = l.strip()
                    if re.search(r'English[:：]', ls, re.IGNORECASE) or re.search(r'https?://', ls):
                        continue
                    cleaned = re.sub(r'^[-•*]\s*(?:🇨🇳\s*)?(?:【|\*\*)?中文解读(?:】|\*\*)?[:：]\s*', '', ls)
                    cleaned = re.sub(r'^[-•*]\s*', '', cleaned).strip()
                    if re.search(r'[\u4e00-\u9fa5]{4,}', cleaned):
                        candidate_zh.append(cleaned)
                if candidate_zh:
                    zh_desc = ' '.join(candidate_zh).strip()

            url_match = re.search(r'[-•*]?\s*(?:🔗\s*)?(?:一手出处|深度报道出处|出处)[:：]\s*(https?://\S+)', chunk, re.IGNORECASE)
            if not url_match:
                url_match = re.search(r'(https?://[^\s>]+)', chunk)
            url = url_match.group(1).strip() if url_match else ''
            if 'google.com/url?q=' in url:
                parsed = urllib.parse.urlparse(url)
                qs = urllib.parse.parse_qs(parsed.query)
                if 'q' in qs: url = qs['q'][0]

            # 5. 核心摘要（summary 必须保持中文，严禁降级为英文！）
            summary = zh_desc if zh_desc else (zh_title if zh_title else raw_title)

            if not zh_desc or not re.search(r'[\u4e00-\u9fa5]', zh_desc):
                print(f"⚠️ [警告] 资讯条目 [{raw_title[:20]}] 未能成功提取中文解读！")

            items.append({
                'title': zh_title if zh_title else raw_title,
                'raw_title': raw_title,
                'summary': summary,
                'en_desc': en_desc,
                'zh_desc': zh_desc,
                'full_text': chunk,
                'tag': tag,
                'url': url,
                'timestamp': f'{date_str} 07:15:00'
            })
        return items

    events.extend(extract_items(mod1, default_tag='CodexRadar'))
    if mod2:
        events.extend(extract_items(mod2, default_tag='AI Industry'))
    return events

def push_to_github_gist(events):
    print("[4/6] 正在同步更新 GitHub Gist (严格按照纯中文小组件契约推送)...")
    gist_events = []
    for ev in events:
        e = copy.deepcopy(ev)
        zh_title = e.get("title", "")
        clean_zh_title = get_zh_title(zh_title)

        tag = e.get("tag") or ""
        if "Codex" in tag or "Codex" in zh_title or "Tibo" in zh_title:
            e["tag"] = "· Codex 独家雷达"
        elif "外交" in tag or "出口管制" in tag or "中美" in zh_title or "政策" in zh_title:
            e["tag"] = "· 宏观与科技政策"
        elif "芯片" in tag or "半导体" in tag or "NVIDIA" in zh_title or "Blackwell" in zh_title or "算力" in zh_title:
            e["tag"] = "· 芯片与算力前沿"
        elif "具身智能" in tag or "机器人" in tag or "灵巧手" in zh_title:
            e["tag"] = "· 具身智能与机器人"
        elif "Agent" in tag or "模型" in tag or "Claude" in zh_title or "Cursor" in zh_title or "OpenAI" in zh_title or "Kimi" in zh_title:
            e["tag"] = "· 前沿模型与 Agent"
        elif "开源" in tag or "GitHub" in tag or "MCP" in zh_title:
            e["tag"] = "· 开源与极客生态"
        else:
            e["tag"] = "· 全球 AI 产业精选"

        e["title"] = clean_zh_title if clean_zh_title else zh_title
        
        # 安卓桌面小组件契约：
        # Android 端 RemoteViews 在 item_en_desc 渲染主内容（支持 **加粗** 高亮）；
        # 因此 e["en_desc"] 必须严格承载 80~150 字的完整中文深度解读！
        main_content = e.get("zh_desc") or e.get("summary") or ""
        if not re.search(r'[\u4e00-\u9fa5]', main_content):
            print(f"⚠️ [警告] 小组件推流检测到非中文文本: {main_content[:30]}")
        e["en_desc"] = main_content
        e["zh_desc"] = ""  # Hide secondary text box
        gist_events.append(e)

    url = f"https://api.github.com/gists/{GITHUB_GIST_ID}"
    headers = {
        "Authorization": f"token {GITHUB_GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AIRadarBot"
    }

    payload = {
        "description": "Daily AI Radar Events for Android Widget",
        "public": True,
        "files": {
            "ai_radar_events.json": {
                "content": json.dumps({"events": gist_events}, ensure_ascii=False, indent=2)
            }
        }
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='PATCH')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 201):
                print(f"GitHub Gist 纯中文小组件契约同步成功！(HTTP {resp.status})")
                return True
            else:
                print(f"GitHub Gist 同步返回状态码: {resp.status}")
                return False
    except Exception as e:
        print(f"GitHub Gist 同步失败: {e}")
        return False

# ==========================================
# Card Rendering Engine (Server-Side)
# ==========================================

def get_source_label(ev):
    tag = ev.get("tag") or ""
    raw_title = ev.get("title") or ""
    if "Codex" in tag or "Codex" in raw_title or "Tibo" in raw_title:
        return "Codex Radar"
    elif "OpenAI" in raw_title:
        return "OpenAI"
    elif "Anthropic" in raw_title:
        return "Anthropic"
    elif "DeepMind" in raw_title or "Google" in raw_title:
        return "Google DeepMind"
    elif "NVIDIA" in raw_title or "英伟达" in raw_title:
        return "NVIDIA"
    elif "SpaceX" in raw_title:
        return "SpaceX"
    elif "Cognition" in raw_title or "Devin" in raw_title:
        return "Cognition"
    elif "Apple" in raw_title or "苹果" in raw_title:
        return "Apple"
    elif tag:
        return tag.replace('·', '').strip()
    return "AI Radar"

TITLE_ENTITY_PATTERNS = [
    r'ChatGPT Work', r'GPT-6 Astra', r'GPT-Astra', r'Astra Medium', r'GPT-6', r'Astra',
    r'Claude Code', r'Claude', r'Anthropic', r'OpenAI', r'Codex Radar', r'Codex',
    r'Tibo', r'SWE-2', r'SWE-bench', r'Devin', r'Cognition', r'Navier-Stokes', r'Lean 4',
    r'Palantir', r'NVIDIA', r'英伟达', r'Apple', r'苹果', r'MCP', r'Cinema 4D',
    r'阿里', r'DeepMind', r'Google', r'Meta', r'Kimi', r'月之暗面', r'GitGuardian',
    r'LinkerBot', r'Jabil', r'捷普', r'Firmus'
]

def find_title_highlights(title_text):
    found = []
    for pat in TITLE_ENTITY_PATTERNS:
        for m in re.finditer(pat, title_text, re.IGNORECASE):
            s, e = m.span()
            overlap = any(not (e <= fs or s >= fe) for fs, fe, _ in found)
            if not overlap:
                found.append((s, e, m.group(0)))
            if len(found) >= 2: break
        if len(found) >= 2: break
    found.sort(key=lambda x: x[0])
    return [match[2] for match in found]

def find_body_highlights(desc_text):
    found = []
    m_bolds = re.findall(r'\*\*(.+?)\*\*', desc_text)
    for b in m_bolds:
        b = b.strip()
        if b and 3 <= len(b) <= 32 and b not in found:
            found.append(b)
        if len(found) >= 2: return found

    pats = [
        r'\b\d+(?:\.\d+)?\s*(?:K\s*Token|Token|%|倍|万卡|十万卡|亿美元|秒|小时)',
        r'开源项目|安全审计|AI Hooks|协议漏洞|年化营收|用户协议|数学证明|算力底座|主权 AI|仿生灵巧手|敏捷研发'
    ]
    for pat in pats:
        for m in re.finditer(pat, desc_text):
            val = m.group(0).strip()
            if val and val not in found and 3 <= len(val) <= 32:
                found.append(val)
            if len(found) >= 2: break
        if len(found) >= 2: break
    return found[:2]

def tokenize_with_markers(text, highlights):
    if not highlights:
        tokens = re.findall(r'[a-zA-Z0-9_\-\.\/\@\:\%\+]+|[\u4e00-\u9fff]|[\u3000-\u303f\uff00-\uffef]|[^\w\s]|\s+', text)
        return [(tok, False) for tok in tokens]

    token_pattern = re.compile(r'[a-zA-Z0-9_\-\.\/\@\:\%\+]+|[\u4e00-\u9fff]|[\u3000-\u303f\uff00-\uffef]|[^\w\s]|\s+')
    all_tokens = token_pattern.findall(text)
    token_spans = []
    curr = 0
    for tok in all_tokens:
        idx = text.find(tok, curr)
        token_spans.append((tok, idx, idx + len(tok)))
        curr = idx + len(tok)

    hl_spans = []
    for hl in highlights:
        m = re.search(re.escape(hl), text, re.IGNORECASE)
        if m:
            s, e = m.span()
            if not any(not (e <= hs or s >= he) for hs, he in hl_spans):
                hl_spans.append((s, e))

    result = []
    for tok, ts, te in token_spans:
        is_hl = any(hs <= ts and te <= he for hs, he in hl_spans)
        result.append((tok, is_hl))
    return result

def wrap_tokens(tokens, font, max_width):
    lines = []
    cur_line = []
    cur_w = 0
    for tok_str, is_hl in tokens:
        if tok_str == '\n':
            if cur_line: lines.append(cur_line)
            cur_line, cur_w = [], 0
            continue
        tw = font.getlength(tok_str)
        if cur_w + tw <= max_width:
            cur_line.append((tok_str, is_hl, tw))
            cur_w += tw
        else:
            if cur_line: lines.append(cur_line)
            cur_line = [(tok_str, is_hl, tw)]
            cur_w = tw
    if cur_line: lines.append(cur_line)
    return lines

def render_editorial_cards(events, date_str, output_dir):
    print("[5/6] 正在服务器本地极速渲染 5 张 1080x1440 高清早报排版卡片...")
    os.makedirs(output_dir, exist_ok=True)
    
    font_bold = ImageFont.truetype(FONT_BOLD_PATH if os.path.exists(FONT_BOLD_PATH) else FONT_REG_PATH, 28)
    font_reg = ImageFont.truetype(FONT_REG_PATH, 23)
    font_header_brand = ImageFont.truetype(FONT_BOLD_PATH if os.path.exists(FONT_BOLD_PATH) else FONT_REG_PATH, 34)
    font_header_title = ImageFont.truetype(FONT_REG_PATH, 22)
    font_header_page = ImageFont.truetype(FONT_BOLD_PATH if os.path.exists(FONT_BOLD_PATH) else FONT_REG_PATH, 24)
    font_num = ImageFont.truetype(FONT_BOLD_PATH if os.path.exists(FONT_BOLD_PATH) else FONT_REG_PATH, 26)
    font_source = ImageFont.truetype(FONT_BOLD_PATH if os.path.exists(FONT_BOLD_PATH) else FONT_REG_PATH, 20)
    font_footer = ImageFont.truetype(FONT_BOLD_PATH if os.path.exists(FONT_BOLD_PATH) else FONT_REG_PATH, 19)

    W, H = 1080, 1440
    margin_x = 72
    w_num_col = 52
    gap_num_to_text = 16
    x_content = margin_x + w_num_col + gap_num_to_text
    max_w_title = W - x_content - margin_x
    max_w_desc = W - x_content - margin_x

    parsed_items = []
    for idx, ev in enumerate(events):
        num_str = f"{idx + 1:02d}"
        source_label = get_source_label(ev)
        source_w = font_source.getlength(source_label)

        title_text = get_zh_title(ev.get("title", ""))
        clean_desc = ev.get("zh_desc") or ev.get("summary") or ""

        title_hls = find_title_highlights(title_text)
        desc_hls = find_body_highlights(clean_desc)
        clean_desc_no_stars = clean_desc.replace('**', '')

        title_tokens = tokenize_with_markers(title_text, title_hls)
        title_lines = wrap_tokens(title_tokens, font_bold, max_w_title)

        desc_tokens = tokenize_with_markers(clean_desc_no_stars, desc_hls)
        desc_lines = wrap_tokens(desc_tokens, font_reg, max_w_desc)

        source_row_h = 24
        source_to_title_gap = 14
        item_h = source_row_h + source_to_title_gap + len(title_lines) * 44 + 12 + len(desc_lines) * 35

        parsed_items.append({
            "num_str": num_str,
            "source_label": source_label,
            "source_w": source_w,
            "title_lines": title_lines,
            "desc_lines": desc_lines,
            "height": item_h,
            "source_row_h": source_row_h,
            "source_to_title_gap": source_to_title_gap
        })

    max_content_h = 1118
    item_gap = 28
    pages = []
    cur_page = []
    cur_h = 0

    for it in parsed_items:
        needed_h = it["height"] if not cur_page else (item_gap + it["height"])
        if cur_h + needed_h <= max_content_h:
            cur_page.append(it)
            cur_h += needed_h
        else:
            if cur_page: pages.append(cur_page)
            cur_page = [it]
            cur_h = it["height"]
    if cur_page: pages.append(cur_page)

    total_pages = len(pages)
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    date_header_str = dt.strftime('%Y.%m.%d')
    image_paths = []

    for page_idx, batch in enumerate(pages, start=1):
        img = Image.new("RGB", (W, H), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Header
        draw.text((margin_x, 82), "AI RADAR", font=font_header_brand, fill=(24, 62, 138))
        draw.text((margin_x + 195, 93), f"全球科技情报日刊 · {date_header_str}", font=font_header_title, fill=(74, 85, 104))
        page_str = f"{page_idx:02d} / {total_pages:02d}"
        draw.text((W - margin_x - font_header_page.getlength(page_str), 90), page_str, font=font_header_page, fill=(160, 174, 192))
        draw.line([(margin_x, 148), (W - margin_x, 148)], fill=(226, 232, 240), width=2)

        # Content Flow
        cur_y = 176
        for b_idx, it in enumerate(batch):
            source_y = cur_y
            draw.text((W - margin_x - it["source_w"], source_y), it["source_label"], font=font_source, fill=(110, 118, 130))

            title_y = source_y + it["source_row_h"] + it["source_to_title_gap"]
            draw.text((margin_x, title_y + 3), it["num_str"], font=font_num, fill=(168, 175, 185))

            cur_title_y = title_y
            for line in it["title_lines"]:
                line_x = x_content
                for tok_str, is_hl, tok_w in line:
                    if is_hl:
                        draw.rounded_rectangle((line_x - 4, cur_title_y + 4, line_x + tok_w + 4, cur_title_y + 36), radius=6, fill=(237, 242, 247))
                    draw.text((line_x, cur_title_y), tok_str, font=font_bold, fill=(18, 22, 28))
                    line_x += tok_w
                cur_title_y += 44

            cur_desc_y = cur_title_y + 12
            for line in it["desc_lines"]:
                line_x = x_content
                for tok_str, is_hl, tok_w in line:
                    draw.text((line_x, cur_desc_y), tok_str, font=font_reg, fill=(44, 49, 58))
                    if is_hl:
                        underline_y = cur_desc_y + 28
                        draw.line([(line_x, underline_y), (line_x + tok_w, underline_y)], fill=(190, 200, 215), width=3)
                    line_x += tok_w
                cur_desc_y += 35

            cur_y += it["height"] + item_gap

        # Footer
        draw.line([(margin_x, 1354), (W - margin_x, 1354)], fill=(226, 232, 240), width=2)
        draw.text((margin_x, 1368), "AI RADAR · 每日核心情报精选", font=font_footer, fill=(160, 174, 192))

        card_path = os.path.join(output_dir, f"xhs_img_{page_idx}.jpg")
        img.save(card_path, quality=95)
        image_paths.append(card_path)

    print(f"成功生成 {len(image_paths)} 张 1080x1440 高清早报排版卡片！")
    return image_paths

# ==========================================
# Douyin Cloud Automated Publisher (Playwright)
# ==========================================

def publish_to_douyin(title, desc, image_paths):
    print("[6/6] 启动云端 Playwright 无头浏览器发布抖音...")
    if not os.path.exists(DOUYIN_STATE_FILE):
        print(f"ERROR: {DOUYIN_STATE_FILE} not found! Cannot publish.")
        return False

    if len(title) > 20:
        title = title[:20]

    with sync_playwright() as p:
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        launch_args = {
            'headless': True,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-gpu',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--start-maximized'
            ]
        }

        browser = p.chromium.launch(**launch_args)
        context = browser.new_context(
            user_agent=ua,
            viewport={"width": 1280, "height": 800},
            storage_state=DOUYIN_STATE_FILE
        )
        page = context.new_page()
        if stealth_applier:
            try: stealth_applier(page)
            except Exception as e: print(f"Stealth warning: {e}")

        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        page.add_init_script("Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});")

        print("Navigating to Image Publish Page...")
        page.goto("https://creator.douyin.com/creator-micro/content/upload", timeout=60000, wait_until="domcontentloaded")
        time.sleep(4)

        print("Switching to 发布图文 tab...")
        img_inp = None
        for attempt in range(5):
            tab = page.locator('text=发布图文').first
            if tab.count() > 0:
                try: tab.click(timeout=3000)
                except Exception: pass
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
            return False

        print(f"Uploading {len(image_paths)} images...")
        img_inp.set_input_files(image_paths)

        print("Waiting for images to finish uploading and processing...")
        uploaded = False
        for sec in range(60):
            time.sleep(1)
            body_txt = page.evaluate("() => document.body.innerText")
            if f"已添加{len(image_paths)}张图片" in body_txt or "重新上传" in body_txt or "更换图片" in body_txt:
                print(f"All {len(image_paths)} images successfully uploaded and processed at {sec+1}s!")
                uploaded = True
                break

        if not uploaded:
            print("Warning: Image upload status text not detected within 60s, proceeding...")

        # Title
        print(f"Filling Title: '{title}'...")
        title_inputs = [
            page.locator('input[placeholder*="填写作品标题"]'),
            page.locator('input[placeholder*="标题"]'),
            page.locator('.semi-input[type="text"]')
        ]
        title_filled = False
        for inp in title_inputs:
            if inp.count() > 0 and inp.first.is_visible():
                try:
                    inp.first.click()
                    inp.first.fill(title)
                    title_filled = True
                    print("Title filled successfully.")
                    break
                except Exception: pass

        # Description
        clean_desc = re.sub(r'https?://\S+', '', desc)
        print(f"Filling Description ({len(clean_desc)} chars, stripped of links)...")
        desc_containers = [
            page.locator('.zone-container'),
            page.locator('.notranslate.public-DraftEditor-content'),
            page.locator('div[contenteditable="true"]')
        ]
        desc_filled = False
        for container in desc_containers:
            if container.count() > 0 and container.first.is_visible():
                try:
                    container.first.click()
                    container.first.fill(clean_desc)
                    desc_filled = True
                    print("Description filled successfully.")
                    break
                except Exception: pass

        # Publish Button
        print("Scrolling to bottom...")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)

        publish_buttons = [
            page.locator('button:has-text("发布")'),
            page.locator('.button-primary:has-text("发布")'),
            page.locator('button[type="primary"]:has-text("发布")')
        ]

        btn_clicked = False
        for btn in publish_buttons:
            if btn.count() > 0 and btn.first.is_visible():
                print(f"Clicking '{btn.first.inner_text().strip()}' button...")
                btn.first.click()
                btn_clicked = True
                break

        if not btn_clicked:
            print("ERROR: Could not find publish button!")
            browser.close()
            return False

        print("Waiting for publish completion / redirect...")
        success = False
        for s in range(25):
            time.sleep(1)
            cur_url = page.url
            body_txt = page.evaluate("() => document.body.innerText")
            if "manage" in cur_url or "发布成功" in body_txt or "作品发布成功" in body_txt:
                print(f"Publish verified at {s+1}s! URL: {cur_url}")
                success = True
                break

        browser.close()
        return success

def send_email(subject, text_content):
    print(f"正在发送早报邮件至 {TARGET_EMAIL} ...")
    msg = MIMEText(text_content, 'plain', 'utf-8')
    msg['From'] = formataddr(("AI Radar 科技雷达", SMTP_USER))
    msg['To'] = formataddr(("订阅者", TARGET_EMAIL))
    msg['Subject'] = Header(subject, 'utf-8')
    msg['Date'] = formatdate(localtime=True)

    try:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=15)
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [TARGET_EMAIL], msg.as_string())
        server.quit()
        print("邮件已成功直投！")
        return True
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False

def write_publish_receipt(date_str, success):
    receipt = {
        "date_str": date_str,
        "published_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "successful_platforms": ["douyin"] if success else [],
        "status": "ALL_SUCCESS" if success else "FAILED"
    }
    with open(RECEIPT_FILE, 'w', encoding='utf-8') as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)
    print(f"今日发布回执已更新落盘: {RECEIPT_FILE}")

def main():
    today_dt = datetime.now()
    today_str = today_dt.strftime('%Y-%m-%d')
    print(f"==================================================")
    print(f"🚀 AI Radar 云端全自主自闭环引擎启动: {today_str}")
    print(f"==================================================")

    blacklist_text, history_db, history_titles = load_history_blacklist(days=7)
    codex_data = fetch_codexradar()
    news_items = fetch_fresh_tech_pool(history_titles)

    if len(news_items) < 5:
        print("警告: 抓取到的新鲜资讯数量不足，跳过本次生成。")
        return

    brief_text = generate_radar_brief(codex_data, news_items, blacklist_text)
    
    # 持久化备份早报文稿
    os.makedirs(LOGS_DIR, exist_ok=True)
    brief_log_path = os.path.join(LOGS_DIR, f"brief_{today_dt.strftime('%Y%m%d')}.txt")
    with open(brief_log_path, 'w', encoding='utf-8') as f:
        f.write(brief_text)
    print(f"早报原始文稿已持久化备份至: {brief_log_path}")

    events = parse_brief_to_events(brief_text, today_str)
    print(f"成功解析出 {len(events)} 条结构化前沿情报！")

    # 1. Update Gist for Mobile Widget
    push_to_github_gist(events)

    # 2. Send email
    subject = f"AI Radar 科技早报 | {today_dt.strftime('%Y年%m月%d日')}（全球科技前沿·中英双语·一手直达版）"
    send_email(subject, brief_text)

    # 3. Save pending tasks
    task_data = {
        "date_str": today_str,
        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "events": events
    }
    with open(PENDING_TASKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(task_data, f, ensure_ascii=False, indent=2)

    # 4. Render Cards
    image_paths = render_editorial_cards(events, today_str, CARDS_OUTPUT_DIR)

    # 5. Publish to Douyin
    douyin_title = f"AI Radar 每日早报 {today_dt.strftime('%m月%d日')}"
    douyin_desc = f"📡 AI Radar 科技早报 | 全球科技前沿与开发者独家情报\n#人工智能 #科技前沿 #大模型 #算力 #具身智能"
    publish_success = publish_to_douyin(douyin_title, douyin_desc, image_paths)

    # 6. Write receipt & history
    write_publish_receipt(today_str, publish_success)
    history_db[today_str] = events
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history_db, f, ensure_ascii=False, indent=2)

    print("AI Radar 云端全链路（抓取+生成+渲染+抖音发布+小组件+邮件）圆满完成！")

if __name__ == "__main__":
    main()
