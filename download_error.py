import paramiko
import os

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('8.129.129.246', username='root', password=os.getenv("SERVER_PASS", "your_server_password"), timeout=10)
    sftp = ssh.open_sftp()
    
    # 下载控制台截图
    sftp.get('/root/dashboard.png', 'C:/Users/Q/.gemini/antigravity/brain/434fd9c3-64d5-4500-a919-364f6cb6b8f6/dashboard.png')
    sftp.close()
    ssh.close()
    print("成功下载控制台截图 dashboard.png！")
except Exception as e:
    print(f"Error: {e}")
