#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ================= CONFIG =================
BASE_DIR = "/root"
RECEIPT_PATH = os.path.join(BASE_DIR, "publish_receipt.json")

SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
SMTP_USER = "356719037@qq.com"
SMTP_PASS = os.getenv("SMTP_PASS", "your_qq_smtp_auth_code")
TARGET_EMAIL = "356719037@qq.com"
# ==========================================

def send_alarm_email(subject, text_content):
    print(f"[{datetime.now()}] Triggering SMTP Alarm Email to {TARGET_EMAIL}: {subject}...")
    try:
        msg = MIMEText(text_content, 'plain', 'utf-8')
        msg['From'] = formataddr(("AI Radar 云端看门狗", SMTP_USER))
        msg['To'] = formataddr(("管理员", TARGET_EMAIL))
        msg['Subject'] = Header(subject, 'utf-8')

        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=15)
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [TARGET_EMAIL], msg.as_string())
        server.quit()
        print(f"[{datetime.now()}] Alarm email successfully sent.")
    except Exception as e:
        print(f"[{datetime.now()}] Failed to send alarm email: {e}")

def main():
    today_str = datetime.now().strftime('%Y-%m-%d')
    print(f"[{datetime.now()}] AI Radar 云端巡检看门狗启动，正在校验 {today_str} 发布状态...")

    if not os.path.exists(RECEIPT_PATH):
        subject = f"【AI Radar 告警】今日 ({today_str}) 发布回执缺失！"
        body = f"云端看门狗巡检提示：未在 {RECEIPT_PATH} 找到今日发布回执文件，请检查云端任务日志 /root/ai_radar.log。"
        send_alarm_email(subject, body)
        return

    try:
        with open(RECEIPT_PATH, 'r', encoding='utf-8') as f:
            receipt = json.load(f)
    except Exception as e:
        subject = f"【AI Radar 告警】今日 ({today_str}) 发布回执解析失败！"
        body = f"无法解析 {RECEIPT_PATH}：{e}"
        send_alarm_email(subject, body)
        return

    receipt_date = receipt.get("date_str")
    status = receipt.get("status")

    if receipt_date == today_str and status == "ALL_SUCCESS":
        print(f"[{datetime.now()}] 巡检通过！今日 ({today_str}) 抖音已由云端全自主成功发布，回执状态正常，保持静默。")
    else:
        subject = f"【AI Radar 告警】今日 ({today_str}) 发布状态异常：{status}"
        body = f"今日发布状态未达预期：\n日期：{receipt_date}\n状态：{status}\n平台：{receipt.get('successful_platforms')}\n时间：{receipt.get('published_at')}"
        send_alarm_email(subject, body)

if __name__ == "__main__":
    main()
