import os
import paramiko
import sys
import time

def run_command(ssh, cmd):
    print(f"\n--- 正在执行命令: {cmd} ---")
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    
    # 实时读取标准输出
    while not stdout.channel.exit_status_ready():
        if stdout.channel.recv_ready():
            sys.stdout.write(stdout.channel.recv(4096).decode('utf-8', errors='replace'))
            sys.stdout.flush()
        if stderr.channel.recv_stderr_ready():
            sys.stderr.write(stderr.channel.recv_stderr(4096).decode('utf-8', errors='replace'))
            sys.stderr.flush()
        time.sleep(0.5)
        
    # 读取剩余输出内容
    if stdout.channel.recv_ready():
        sys.stdout.write(stdout.channel.recv(4096).decode('utf-8', errors='replace'))
        sys.stdout.flush()
    if stderr.channel.recv_stderr_ready():
        sys.stderr.write(stderr.channel.recv_stderr(4096).decode('utf-8', errors='replace'))
        sys.stderr.flush()
        
    status = stdout.channel.recv_exit_status()
    print(f"\n--- 执行退出状态码: {status} ---\n")
    return status

try:
    print("正在连接服务器 8.129.129.246...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('8.129.129.246', username='root', password=os.getenv("SERVER_PASS", "your_server_password"), timeout=10)
    print("服务器连接成功！")
    
    run_command(ssh, 'export PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/ && playwright install chromium')
    
except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
