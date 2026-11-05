import paramiko
import sys
import time

def run_command(ssh, cmd):
    print(f"\n--- Running: {cmd} ---")
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    
    # Read output in real-time
    while not stdout.channel.exit_status_ready():
        if stdout.channel.recv_ready():
            sys.stdout.write(stdout.channel.recv(4096).decode('utf-8', errors='replace'))
            sys.stdout.flush()
        if stderr.channel.recv_stderr_ready():
            sys.stderr.write(stderr.channel.recv_stderr(4096).decode('utf-8', errors='replace'))
            sys.stderr.flush()
        time.sleep(0.5)
        
    # Read any remaining output
    if stdout.channel.recv_ready():
        sys.stdout.write(stdout.channel.recv(4096).decode('utf-8', errors='replace'))
        sys.stdout.flush()
    if stderr.channel.recv_stderr_ready():
        sys.stderr.write(stderr.channel.recv_stderr(4096).decode('utf-8', errors='replace'))
        sys.stderr.flush()
        
    status = stdout.channel.recv_exit_status()
    print(f"\n--- Exit status: {status} ---\n")
    return status

try:
    print("Connecting to 8.129.129.246...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('8.129.129.246', username='root', password='qryyds7.9.', timeout=10)
    print("Connected successfully!")
    
    run_command(ssh, 'export PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/ && playwright install chromium')
    
except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
