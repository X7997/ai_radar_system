import os
import paramiko
import sys
import time

def run_command(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    out = stdout.read().decode('utf-8')
    err = stderr.read().decode('utf-8')
    return out

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('8.129.129.246', username='root', password=os.getenv("SERVER_PASS", "your_server_password"), timeout=10)
    
    print("正在检查服务器上的 xhs.log 日志...")
    out = run_command(ssh, 'tail -n 20 /root/xhs.log')
    print(out)
    
except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
