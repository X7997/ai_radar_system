import os
import re
import imaplib
import email
from email.header import decode_header
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def decode_mime_words(s):
    if not s:
        return u""
    return u"".join(
        word.decode(encoding or 'utf-8') if isinstance(word, bytes) else word
        for word, encoding in decode_header(s)
    )

def fetch_summarized_events_from_gmail():
    """
    Connects to IMAP server, searches for the latest email sent TODAY containing the AI summary,
    and extracts it into a JSON structure.
    Strictly verifies that the email is fresh (sent on today's date).
    """
    imap_user = os.environ.get("IMAP_USER")
    imap_password = os.environ.get("IMAP_PASSWORD")
    imap_server = os.environ.get("IMAP_SERVER", "imap.qq.com")
    
    if not imap_user or not imap_password:
        print("Missing IMAP_USER or IMAP_PASSWORD in .env.")
        return None, None

    today_str = datetime.now().strftime('%Y-%m-%d')
    print(f"Connecting to {imap_server} as {imap_user}... Searching for today's ({today_str}) AI Radar email.")
    
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(imap_user, imap_password)
        mail.select("inbox")

        status, messages = mail.search(None, 'ALL')
        if status != "OK" or not messages[0]:
            print("No emails found in mailbox.")
            mail.logout()
            return None, None
            
        email_ids = messages[0].split()
        
        latest_email_id = None
        email_date_found = None
        
        # Traverse backwards to find an email matching TODAY's date
        for eid in reversed(email_ids):
            _, msg_data = mail.fetch(eid, '(RFC822.HEADER)')
            msg_temp = email.message_from_bytes(msg_data[0][1])
            subject = decode_mime_words(msg_temp.get("Subject", ""))
            
            if "AI Radar" in subject:
                # Extract date from subject
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', subject)
                if date_match:
                    email_date_found = date_match.group(1)
                    if email_date_found == today_str:
                        latest_email_id = eid
                        break
                    else:
                        print(f"Found older AI Radar email ID {eid.decode()} with date {email_date_found}, looking for today ({today_str})...")
                else:
                    # Fallback check X-AI-Radar-Date header
                    x_date = msg_temp.get("X-AI-Radar-Date", "")
                    if x_date == today_str:
                        latest_email_id = eid
                        email_date_found = today_str
                        break

        if not latest_email_id:
            print(f"[FRESHNESS GUARD REJECTED]: No AI Radar email matching today's date ({today_str}) found in inbox!")
            print(f"Most recent email was dated {email_date_found}. Refusing to process stale email.")
            mail.logout()
            return None, None
            
        print(f"Verified fresh email for {today_str}! Fetching email ID: {latest_email_id.decode()}...")
        status, msg_data = mail.fetch(latest_email_id, '(RFC822)')
        mail.logout()
        
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        
        subject = decode_mime_words(msg.get("Subject", ""))
        sender = decode_mime_words(msg.get("From", ""))
        print(f"Subject: {subject}")
        print(f"From: {sender}")
        
        # Extract body text
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                    except:
                        pass
        else:
            if msg.get_content_type() == "text/plain":
                try:
                    body = msg.get_payload(decode=True).decode('utf-8', errors='replace')
                except:
                    pass

        if not body:
            print("Could not extract plain text body from email.")
            return None, None
            
        # Strip forwarding headers
        body = re.sub(r'---------- Forwarded message ---------.*?To:.*?<.*?>\n*', '', body, flags=re.DOTALL | re.IGNORECASE).strip()
        
        events = []
        chunks = re.split(r'\n(?=(?:#[\w\u4e00-\u9fa5]+\s+\*)?\*?\d+\.\s+)', body)
        
        if len(chunks) > 0:
            if not re.match(r'^\s*(?:#[\w\u4e00-\u9fa5]+\s+\*)?\*?\d+\.', chunks[0]):
                chunks = chunks[1:]
                
            for chunk in chunks:
                chunk = chunk.strip()
                if not chunk: continue
                
                tag = "CodexRadar"
                tag_match = re.search(r'#([\w\u4e00-\u9fa5]+)', chunk)
                if tag_match:
                    tag = tag_match.group(1)
                    
                title_match = re.search(r'^\s*(?:#[\w\u4e00-\u9fa5]+\s+\*?)?\*?\d+\.\s*(.*?)(?=\n\s*(?:•|\ud83c[\uddfa-\uddff]|\ud83c[\udde8-\uddff]|\ud83d[\udd17]|\*?English|\*?中文))', chunk, re.DOTALL | re.IGNORECASE)
                if title_match:
                    title = title_match.group(1).replace('\r\n', ' ').replace('\n', ' ').replace('*', '').strip()
                else:
                    title = chunk.split('\n')[0].replace('*', '').strip()
                    title = re.sub(r'^\d+\.\s*', '', title)
                    
                title = re.sub(r'【?#[\w\u4e00-\u9fa5]+】?\s*', '', title).strip()
                    
                en_desc = ""
                en_match = re.search(r'(?:•\s*)?(?:\ud83c[\uddfa-\uddff]\s*)?\*?English:\*?\s*(.*?)(?=\n\s*(?:•|\ud83c[\udde8-\uddff]|\ud83d[\udd17]|\*?中文|\*?🔗))', chunk, re.DOTALL | re.IGNORECASE)
                if en_match:
                    en_desc = en_match.group(1).replace('\r\n', ' ').replace('\n', ' ').strip()
                    
                zh_desc = ""
                zh_match = re.search(r'(?:•\s*)?(?:\ud83c[\udde8-\uddff]\s*)?\*?(?:中文解读|中文):\*?\s*(.*?)(?=\n\s*(?:•|\ud83d[\udd17]|🔗|http|<|\*?出处))', chunk, re.DOTALL | re.IGNORECASE)
                if zh_match:
                    zh_desc = zh_match.group(1).replace('\r\n', ' ').replace('\n', ' ').strip()
                    zh_desc = re.sub(r'\s*-{10,}.*', '', zh_desc, flags=re.DOTALL).strip()
                    
                url = ""
                url_match = re.search(r'<(https?://[^>]+)>', chunk)
                if not url_match:
                    url_match = re.search(r'(https?://[^\s]+)', chunk[chunk.find('出处'):] if '出处' in chunk else chunk)
                if url_match:
                    url = url_match.group(1)
                    import urllib.parse
                    if 'google.com/url?q=' in url:
                        parsed = urllib.parse.urlparse(url)
                        qs = urllib.parse.parse_qs(parsed.query)
                        if 'q' in qs:
                            url = qs['q'][0]
                    
                events.append({
                    "title": title,
                    "summary": zh_desc if zh_desc else chunk.strip(),
                    "en_desc": en_desc,
                    "zh_desc": zh_desc,
                    "full_text": chunk.strip(),
                    "tag": tag,
                    "url": url,
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                
        print(f"Successfully extracted {len(events)} fresh events for {today_str}.")
        return events, today_str

    except Exception as e:
        print(f"Error fetching email: {e}")
        return None, None
