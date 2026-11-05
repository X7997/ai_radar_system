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
    ssh.connect('8.129.129.246', username='root', password='qryyds7.9.', timeout=10)
    
    print("Checking xhs.log on server...")
    out = run_command(ssh, 'tail -n 20 /root/xhs.log')
    print(out)
    
except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
