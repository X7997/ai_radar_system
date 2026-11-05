import os
import sys
import json
import time
import urllib.request
import paramiko
import subprocess
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import re

SERVER_IP = os.getenv("KOREA_SERVER_IP", "47.80.9.117")
SERVER_USER = os.getenv("KOREA_SERVER_USER", "root")
SERVER_PASS = os.getenv("KOREA_SERVER_PASS", "your_korea_vps_password")
REMOTE_DIR = "/root"

GIST_ID = "7ad36328320740c54905a64368c2ee2f"

# ==========================================
# Text Processing & Layout Helpers
# ==========================================

def get_zh_title(t):
    if not t:
        return ''
    t = t.strip()
    t = re.sub(r'【#[\w\u4e00-\u9fa5\s]+】\s*', '', t).strip()
    norm = t.replace('（', '(').replace('）', ')')
    
    if norm.endswith(')'):
        depth = 0
        open_idx = -1
        for idx in range(len(norm) - 1, -1, -1):
            if norm[idx] == ')':
                depth += 1
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
    if m:
        return m.group(1).strip()
        
    matches = list(re.finditer(r'\((.*?)\)', norm))
    for m in reversed(matches):
        if re.search(r'[\u4e00-\u9fa5]', m.group(1)):
            return m.group(1).strip()

    return t

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
    elif "Shopify" in raw_title:
        return "Shopify"
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
    r'Shopify', r'Tailwind', r'React Native', r'Native', r'SpaceX',
    r'Palantir', r'NVIDIA', r'英伟达', r'Apple', r'苹果', r'iPhone Duo', r'iPhone 18 Pro',
    r'阿里', r'DeepMind', r'Google', r'Meta', r'Mercury 2\.5', r'Mercury',
    r'Quill', r'RavenDB', r'Credo', r'CRDO', r'加州新法', r'中国商务部',
    r'Pro 订阅', r'Fast 模式', r'Agents API'
]

def find_title_highlights(title_text):
    """Find at most 2 entity highlights in the title."""
    found = []
    for pat in TITLE_ENTITY_PATTERNS:
        for m in re.finditer(pat, title_text, re.IGNORECASE):
            s, e = m.span()
            overlap = False
            for fs, fe, _ in found:
                if not (e <= fs or s >= fe):
                    overlap = True
                    break
            if not overlap:
                found.append((s, e, m.group(0)))
            if len(found) >= 2:
                break
        if len(found) >= 2:
            break
    found.sort(key=lambda x: x[0])
    return [match[2] for match in found]

def find_body_highlights(desc_text):
    """Find strictly 1 to 2 key facts/conclusions/metrics in description to underline."""
    found = []
    # 1. Upstream bold markers **...** from email (author's explicit takeaways)
    m_bolds = re.findall(r'\*\*(.+?)\*\*', desc_text)
    for b in m_bolds:
        b = b.strip()
        if b and 3 <= len(b) <= 32 and b not in found:
            found.append(b)
        if len(found) >= 2:
            return found

    # 2. Priority key facts: specific reset dates/times/conclusions
    pats = [
        r'(?:预计|推断|确认)?\s*\d+月\d+日(?:\s*\d+[:：]\d+(?:[–—\-]\d+[:：]\d+)?)?(?:\s*完成)?(?:重置|触发)',
        r'重置时间[：:]\s*[^\s，。\n]+',
        r'补发一张新的预存额度重置卡|重置卡扣扣故障|生效异常|补发新配额|用量重置|额度重置|重置卡|充值卡',
        r'\b\d+(?:\.\d+)?\s*(?:K\s*Token|Token|%|倍|万卡|十万卡|亿美元|秒|小时)',
        r'暂停接受新的 ChatGPT Pro 订阅申请|暂停新 Pro 订阅|全面回归 iOS Swift 与 Android Kotlin 原生语言|首次公开拦截极高危生物科技滥用'
    ]
    for pat in pats:
        for m in re.finditer(pat, desc_text):
            val = m.group(0).strip()
            if val and val not in found and 3 <= len(val) <= 32:
                found.append(val)
            if len(found) >= 2:
                break
        if len(found) >= 2:
            break
            
    return found[:2]

def tokenize_with_markers(text, highlights):
    """Tokenize text while tagging which tokens are part of a highlight (first occurrence only, max 2)."""
    if not highlights:
        tokens = re.findall(r'[a-zA-Z0-9_\-\.\/\@\:\%\+]+|[\u4e00-\u9fff]|[\u3000-\u303f\uff00-\uffef]|[^\w\s]|\s+', text)
        return [(tok, False) for tok in tokens]

    spans = []
    for hl in highlights[:2]:
        idx = text.find(hl)
        if idx != -1:
            spans.append((idx, idx + len(hl), hl))

    spans.sort(key=lambda x: x[0])
    merged_spans = []
    for s, e, hl in spans:
        if not merged_spans:
            merged_spans.append((s, e, hl))
        else:
            ls, le, lhl = merged_spans[-1]
            if s >= le:
                merged_spans.append((s, e, hl))

    parts = []
    last_idx = 0
    for s, e, hl in merged_spans:
        if s > last_idx:
            for tok in re.findall(r'[a-zA-Z0-9_\-\.\/\@\:\%\+]+|[\u4e00-\u9fff]|[\u3000-\u303f\uff00-\uffef]|[^\w\s]|\s+', text[last_idx:s]):
                parts.append((tok, False))
        parts.append((hl, True))
        last_idx = e

    if last_idx < len(text):
        for tok in re.findall(r'[a-zA-Z0-9_\-\.\/\@\:\%\+]+|[\u4e00-\u9fff]|[\u3000-\u303f\uff00-\uffef]|[^\w\s]|\s+', text[last_idx:]):
            parts.append((tok, False))

    return parts

def wrap_tokens(token_stream, font, max_w):
    """Natural wrapping across full width."""
    lines = []
    curr_line = []
    curr_w = 0

    for tok, is_hl in token_stream:
        w = font.getlength(tok)
        if curr_w + w <= max_w:
            curr_line.append((tok, is_hl, w))
            curr_w += w
        else:
            if curr_line:
                lines.append(curr_line)
            curr_line = [(tok, is_hl, w)]
            curr_w = w

    if curr_line:
        lines.append(curr_line)
    return lines

# ==========================================
# Editorial Newspaper Rendering Engine
# ==========================================

def get_editorial_fonts():
    """Load bold and regular fonts with environment fallbacks."""
    font_bold_path = '/home/niumao/ai_radar_system/backend/msyhbd.ttc' if os.path.exists('/home/niumao/ai_radar_system/backend/msyhbd.ttc') else 'C:/Windows/Fonts/msyhbd.ttc'
    font_reg_path = '/home/niumao/ai_radar_system/backend/msyh.ttc' if os.path.exists('/home/niumao/ai_radar_system/backend/msyh.ttc') else 'C:/Windows/Fonts/msyh.ttc'
    if not os.path.exists(font_bold_path):
        font_bold_path = font_reg_path

    return {
        "f_header_brand": ImageFont.truetype(font_bold_path, 46),
        "f_header_title": ImageFont.truetype(font_bold_path, 40),
        "f_header_page": ImageFont.truetype(font_reg_path, 22),
        "f_num": ImageFont.truetype(font_reg_path, 28),
        "f_source": ImageFont.truetype(font_bold_path, 21),
        "f_title_bold": ImageFont.truetype(font_bold_path, 33),
        "f_desc_reg": ImageFont.truetype(font_reg_path, 23),
        "f_footer_right": ImageFont.truetype(font_bold_path, 19)
    }

def render_editorial_cards(events_or_task, date_str=None, output_dir="."):
    os.makedirs(output_dir, exist_ok=True)
    if isinstance(events_or_task, dict):
        events = events_or_task.get("events", [])
        if not date_str:
            date_str = events_or_task.get("date_str")
    else:
        events = events_or_task

    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')

    fonts = get_editorial_fonts()
    f_header_brand = fonts["f_header_brand"]
    f_header_title = fonts["f_header_title"]
    f_header_page = fonts["f_header_page"]
    f_num = fonts["f_num"]
    f_source = fonts["f_source"]
    f_title_bold = fonts["f_title_bold"]
    f_desc_reg = fonts["f_desc_reg"]
    f_footer_right = fonts["f_footer_right"]

    W, H = 1080, 1440
    margin_x = 72
    w_num_col = 52
    gap_num_to_text = 16
    x_content = margin_x + w_num_col + gap_num_to_text
    max_w_title = W - x_content - margin_x
    max_w_desc = W - x_content - margin_x

    # Modern Editorial Palette
    bg_color = (255, 255, 255)
    color_brand = (24, 62, 138)
    color_title = (18, 22, 28)
    color_desc = (44, 49, 58)
    color_num = (168, 175, 185)
    color_source = (110, 118, 130)
    color_divider = (235, 238, 242)
    color_footer = (175, 182, 192)
    color_underline = (49, 135, 232)
    color_highlighter = (226, 238, 255)

    # 1. Measure and parse all news items
    parsed_items = []
    for idx, ev in enumerate(events, 1):
        num_str = f"{idx:02d}"
        source_label = get_source_label(ev)
        source_w = f_source.getlength(source_label)

        raw_title = ev.get("title", "")
        zh_title = get_zh_title(raw_title)
        title_text = zh_title if zh_title else raw_title

        desc_raw = ev.get("zh_desc") or ev.get("summary") or ""
        if not re.search(r'[\u4e00-\u9fa5]', desc_raw) and ev.get("full_text"):
            m = re.search(
                r'[-•*]?\s*(?:🇨🇳\s*)?(?:【|\*\*)?中文解读(?:】|\*\*)?[:：]\s*(.*?)(?=\n\s*[-•*]|\n\s*🔗|\n\s*一手出处|\n\s*深度报道出处|\Z)',
                ev.get("full_text", ""), re.DOTALL | re.IGNORECASE
            )
            if m:
                desc_raw = m.group(1).strip()

        clean_desc = re.sub(r'•\s*(?:🇨🇳\s*)?中文解读[:：]\s*', '', desc_raw).strip()
        clean_desc = re.sub(r'•\s*一手出处.*', '', clean_desc).strip()
        clean_desc = re.sub(r'https?://\S+', '', clean_desc).strip()

        # Highlights
        title_hls = find_title_highlights(title_text)
        desc_hls = find_body_highlights(clean_desc)
        clean_desc_no_stars = clean_desc.replace('**', '')

        # Token wrapping
        title_tokens = tokenize_with_markers(title_text, title_hls)
        title_lines = wrap_tokens(title_tokens, f_title_bold, max_w_title)

        desc_tokens = tokenize_with_markers(clean_desc_no_stars, desc_hls)
        desc_lines = wrap_tokens(desc_tokens, f_desc_reg, max_w_desc)

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

    # 2. Dynamic Greedy Layout into Pages (Max content height budget: 1118px)
    max_content_h = 1118
    base_gap = 44

    pages = []
    current_page = []
    current_page_h = 0

    for it in parsed_items:
        needed_h = it["height"] + (base_gap if current_page else 0)
        if current_page and (current_page_h + needed_h > max_content_h):
            pages.append(current_page)
            current_page = [it]
            current_page_h = it["height"]
        else:
            current_page.append(it)
            current_page_h += needed_h

    if current_page:
        pages.append(current_page)

    total_pages = len(pages)
    print(f"Dynamic Greedy Layout: {len(events)} events packed into {total_pages} cohesive pages.")

    # 3. Render all pages
    image_paths = []
    month_day = f"{date_str[5:7]}月{date_str[8:10]}日"

    for page_idx, batch in enumerate(pages, 1):
        img = Image.new("RGB", (W, H), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Header: AI Radar (deep blue) + 每日科技快报 · MM月DD日 (black)
        header_y = 82
        brand_text = "AI Radar"
        title_suffix = f" 每日科技快报 · {month_day}"
        
        w_brand = f_header_brand.getlength(brand_text)
        w_suffix = f_header_title.getlength(title_suffix)
        title_gap = 18
        total_header_w = w_brand + title_gap + w_suffix
        header_start_x = (W - total_header_w) / 2

        # Draw AI Radar brand (centered)
        draw.text((header_start_x, header_y), brand_text, font=f_header_brand, fill=color_brand)
        
        # AI Radar rough highlighter underline (7px thick, #3187E8, rounded ends)
        ul_y = header_y + 54
        draw.rounded_rectangle((header_start_x - 3, ul_y, header_start_x + w_brand + 3, ul_y + 7), radius=3, fill=color_underline)
        
        # Header title suffix
        draw.text((header_start_x + w_brand + title_gap, header_y + 4), title_suffix, font=f_header_title, fill=color_title)
        
        # Header Page indicator (top right)
        page_text = f"{page_idx:02d} / {total_pages:02d}"
        w_page = f_header_page.getlength(page_text)
        draw.text((W - margin_x - w_page, header_y + 18), page_text, font=f_header_page, fill=color_num)

        # Header Divider Line
        top_div_y = 176
        draw.line((margin_x, top_div_y, W - margin_x, top_div_y), fill=color_divider, width=2)

        # Dynamic balanced gap for natural vertical rhythm
        fy = 1354
        content_top = top_div_y + 36
        content_bottom_budget = fy - 20
        total_item_h = sum(it["height"] for it in batch)
        remaining_space = content_bottom_budget - content_top - total_item_h
        if len(batch) > 1:
            item_gap = max(44, min(68, remaining_space // (len(batch) - 1)))
        else:
            item_gap = 44

        # Content Flow
        cur_y = content_top
        for b_idx, it in enumerate(batch):
            # Row 1: Source Tag placed at Top-Right of the news block
            source_y = cur_y
            draw.text((W - margin_x - it["source_w"], source_y), it["source_label"], font=f_source, fill=color_source)

            # Row 2: Number 01 on the left + Title across FULL width
            title_y = source_y + it["source_row_h"] + it["source_to_title_gap"]
            draw.text((margin_x, title_y + 3), it["num_str"], font=f_num, fill=color_num)

            line_h_title = 44
            cur_title_y = title_y
            for l_idx, line in enumerate(it["title_lines"]):
                line_x = x_content
                for tok_str, is_hl, tok_w in line:
                    if is_hl:
                        hl_pad_x = 4
                        draw.rounded_rectangle(
                            (line_x - hl_pad_x, cur_title_y + 4, line_x + tok_w + hl_pad_x, cur_title_y + 36),
                            radius=6,
                            fill=color_highlighter
                        )
                        draw.text((line_x, cur_title_y), tok_str, font=f_title_bold, fill=color_title)
                        line_x += tok_w
                    else:
                        draw.text((line_x, cur_title_y), tok_str, font=f_title_bold, fill=color_title)
                        line_x += tok_w
                cur_title_y += line_h_title

            # Row 3: Description Lines
            cur_desc_y = cur_title_y + 12
            line_h_desc = 35
            for line in it["desc_lines"]:
                line_x = x_content
                for tok_str, is_hl, tok_w in line:
                    draw.text((line_x, cur_desc_y), tok_str, font=f_desc_reg, fill=color_desc)
                    if is_hl:
                        underline_y = cur_desc_y + 28
                        draw.line((line_x, underline_y, line_x + tok_w, underline_y), fill=color_underline, width=3)
                    line_x += tok_w
                cur_desc_y += line_h_desc

            cur_y += it["height"] + item_gap

        # Footer (Strictly at y=1354)
        draw.line((margin_x, fy, W - margin_x, fy), fill=color_divider, width=2)
        f_tag_text = "AI RADAR · 每日核心情报精选"
        draw.text((margin_x, fy + 14), f_tag_text, font=f_footer_right, fill=color_footer)

        card_path = os.path.join(output_dir, f"xhs_img_{page_idx}.jpg")
        img.save(card_path, quality=95)
        image_paths.append(card_path)

    print(f"Generated {len(image_paths)} dynamic packed editorial cards successfully!")
    return image_paths

# ==========================================
# Task Acquisition & Receipt Handling
# ==========================================

def fetch_task_from_server():
    """Tier 1: Fetch pending task from Korea VPS via SFTP."""
    print(f"Connecting to Korea VPS ({SERVER_IP})...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASS, timeout=10)
    sftp = ssh.open_sftp()
    
    remote_task_path = f"{REMOTE_DIR}/pending_xhs_tasks.json"
    local_task_path = "downloaded_tasks.json"
    sftp.get(remote_task_path, local_task_path)
    sftp.close()
    ssh.close()
    
    with open(local_task_path, 'r', encoding='utf-8') as f:
        task = json.load(f)
    return task

def fetch_task_from_gist():
    """Tier 2: Fallback to fetch events directly from GitHub Gist."""
    print("Falling back to GitHub Gist API...")
    url = f"https://api.github.com/gists/{GIST_ID}"
    req = urllib.request.Request(url, headers={'User-Agent': 'AIRadarLocalPublisher'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        gist_data = json.loads(resp.read().decode('utf-8'))
        raw_content = gist_data['files']['ai_radar_events.json']['content']
        obj = json.loads(raw_content)
        events = obj.get("events", [])
        today_str = datetime.now().strftime('%Y-%m-%d')
        return {
            "date_str": today_str,
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "events": events
        }

def fetch_today_task(today_str):
    # Tier 1: Korea VPS
    try:
        task = fetch_task_from_server()
        if task and task.get("date_str") == today_str:
            print("Successfully loaded task from Korea VPS!")
            return task
    except Exception as e:
        print(f"Tier 1 (Korea VPS SFTP) failed: {e}")

    # Tier 2: GitHub Gist
    try:
        task = fetch_task_from_gist()
        if task and task.get("events"):
            print("Successfully loaded task from GitHub Gist!")
            return task
    except Exception as e:
        print(f"Tier 2 (GitHub Gist) failed: {e}")

    # Tier 3: QQ Mail IMAP
    try:
        from mail_fetcher import fetch_summarized_events_from_gmail
        events, date_str = fetch_summarized_events_from_gmail()
        if events and date_str == today_str:
            print("Successfully loaded task from QQ Mail IMAP!")
            return {
                "date_str": date_str,
                "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "events": events
            }
    except Exception as e:
        print(f"Tier 3 (QQ Mail IMAP) failed: {e}")

    return None

def upload_publish_receipt(date_str, target_platforms, success_platforms, failed_platforms, error_msg=None):
    receipt = {
        "date_str": date_str,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "target_platforms": target_platforms,
        "success_platforms": success_platforms,
        "failed_platforms": failed_platforms,
        "status": "ALL_SUCCESS" if (success_platforms and not failed_platforms) else ("PARTIAL_SUCCESS" if success_platforms else "FAILED"),
        "error_msg": error_msg or ""
    }
    receipt_local = f"publish_receipt_{date_str}.json"
    try:
        with open(receipt_local, "w", encoding="utf-8") as f:
            json.dump(receipt, f, ensure_ascii=False, indent=2)
        with open("publish_receipt.json", "w", encoding="utf-8") as f:
            json.dump(receipt, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Notice writing local receipt: {e}")

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASS, timeout=10)
        sftp = ssh.open_sftp()
        remote_receipt_date = f"{REMOTE_DIR}/publish_receipt_{date_str}.json"
        remote_receipt_latest = f"{REMOTE_DIR}/publish_receipt.json"
        sftp.put(receipt_local, remote_receipt_date)
        sftp.put(receipt_local, remote_receipt_latest)
        sftp.close()
        ssh.close()
        print(f"Successfully uploaded publish receipt to Korea VPS ({remote_receipt_latest}).")
    except Exception as e:
        print(f"Warning: Failed to upload publish receipt to Korea VPS: {e}")

# ==========================================
# Main Execution Pipeline
# ==========================================

def main():
    today_str = datetime.now().strftime('%Y-%m-%d')
    print(f"[{datetime.now()}] Starting Local Publisher (AI Radar 编辑批注式科技日报). Checking fresh task ({today_str})...")
    
    last_post_file = "last_post_date.txt"
    last_post_date = ""
    if os.path.exists(last_post_file):
        with open(last_post_file, "r", encoding="utf-8") as f:
            last_post_date = f.read().strip()
            
    task = fetch_today_task(today_str)
    if not task:
        print(f"ERROR: No valid task found for today ({today_str}).")
        return
        
    date_str = task.get("date_str")
    if not date_str or date_str != today_str:
        print(f"[PUBLISHER GUARD REJECT]: Task date '{date_str}' is NOT today '{today_str}'! Skipping.")
        return

    # GUARD 2: Avoid duplicate publishing on the same day
    if date_str == last_post_date:
        print(f"Task for {date_str} has already been posted today. Waiting for next day.")
        return

    events = task.get("events", [])
    if not events:
        print("No events in task.")
        return

    # GUARD 3: Content Freshness / Deduplication against previous post
    new_titles = [e.get('title', '').strip() for e in events if e.get('title')]
    last_titles_file = "last_published_titles.json"
    if os.path.exists(last_titles_file):
        try:
            with open(last_titles_file, "r", encoding="utf-8") as f:
                last_titles = json.load(f)
            overlap = set(new_titles) & set(last_titles)
            if len(overlap) >= len(new_titles) * 0.7:
                print(f"[PUBLISHER GUARD REJECT]: Refusing to publish! {len(overlap)}/{len(new_titles)} titles overlap with previous post.")
                return
        except Exception as e:
            print(f"Notice checking title history: {e}")

    print(f"Verified fresh task for {date_str} with {len(events)} events!")
    
    # Render Editorial Newspaper Cards
    image_paths = render_editorial_cards(events, date_str, output_dir=".")

    # Clean title & caption (Douyin minimalist format: strictly 0 URLs, 0 descriptions)
    post_title = f"AI Radar 每日情报 {date_str[5:7]}月{date_str[8:10]}日"
    post_desc = f"📅 {date_str} · AI Radar 每日科技快报\n#AI #科技 #AI早报 #人工智能"
    
    # Single-Track: Douyin ONLY
    target_platforms = ["douyin"]
    print(f"Publishing Strategy for date '{date_str}': Target Platforms = {target_platforms} (Douyin Only)")
    
    success_platforms = []
    failed_platforms = []

    for platform in target_platforms:
        poster_script = "douyin_api_poster.py"
        platform_name = "Douyin"

        print(f"\n==========================================")
        print(f"Executing {poster_script} for {platform_name} with fresh content...")
        print(f"==========================================")

        post_data = {
            "title": post_title,
            "desc": post_desc,
            "images": image_paths
        }
        temp_post_file = f"temp_post_{platform}.json"
        with open(temp_post_file, "w", encoding="utf-8") as f:
            json.dump(post_data, f, ensure_ascii=False)
            
        py_bin = sys.executable if sys.platform == 'win32' else "/home/niumao/ai_radar_system/venv/bin/python"
        cmd = [
            py_bin,
            "-X", "utf8",
            poster_script,
            temp_post_file
        ]
        run_cmd = cmd if sys.platform == 'win32' else ['xvfb-run', '-a', '-s', '-screen 0 1280x800x24'] + cmd
        
        try:
            result = subprocess.run(run_cmd, capture_output=True)
            stdout_text = result.stdout.decode('utf-8', errors='replace') if result.stdout else ""
            stderr_text = result.stderr.decode('utf-8', errors='replace') if result.stderr else ""
            
            print(f"--- {platform_name} Publish Output ---")
            print(stdout_text)
            if stderr_text:
                print(f"--- {platform_name} Errors ---")
                print(stderr_text)
                
            is_success = False
            if "SUCCESS! Note published" in stdout_text or "Publish successful" in stdout_text or "已发布" in stdout_text:
                is_success = True

            if is_success:
                print(f"[{platform_name}] Successfully published from local machine!")
                success_platforms.append(platform_name)
            else:
                print(f"[{platform_name}] Failed to publish. See detailed output above.")
                failed_platforms.append(platform_name)
        except Exception as e:
            print(f"[{platform_name}] Exception running poster: {e}")
            failed_platforms.append(platform_name)

    print("\n==========================================")
    print(f"Publishing Summary for {date_str}:")
    print(f"Successful: {success_platforms}")
    print(f"Failed:     {failed_platforms}")
    print("==========================================")

    if success_platforms:
        with open(last_post_file, "w", encoding="utf-8") as f:
            f.write(date_str)
        with open(last_titles_file, "w", encoding="utf-8") as f:
            json.dump(new_titles, f, ensure_ascii=False)
        print(f"Updated {last_post_file} and history for {date_str}.")
    else:
        print(f"ERROR: Target platform failed to publish for {date_str}. last_post_date not updated.")

    # Always upload publish receipt to Korea VPS for watchdog verification
    upload_publish_receipt(date_str, target_platforms, success_platforms, failed_platforms)
        
if __name__ == "__main__":
    main()
