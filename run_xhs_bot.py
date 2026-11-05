import paramiko
import sys

def run_command(ssh, cmd):
    print(f"Running: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    
    while not stdout.channel.exit_status_ready():
        if stdout.channel.recv_ready():
            sys.stdout.write(stdout.channel.recv(4096).decode('utf-8', errors='replace'))
            sys.stdout.flush()
        import time
        time.sleep(0.1)
        
    if stdout.channel.recv_ready():
        sys.stdout.write(stdout.channel.recv(4096).decode('utf-8', errors='replace'))
        sys.stdout.flush()

try:
    print("Connecting to 8.129.129.246...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('8.129.129.246', username='root', password='qryyds7.9.', timeout=10)
    print("Connected successfully!")
    
    print("Uploading xhs_bot.py...")
    sftp = ssh.open_sftp()
    sftp.put('xhs_bot.py', '/root/xhs_bot.py')
    sftp.close()
    
    ssh.exec_command('rm -f /root/sms_code.txt /root/error_timeout.png /root/error_login.png /root/dashboard.png')
    
    run_command(ssh, 'python3 /root/xhs_bot.py')
    
except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
