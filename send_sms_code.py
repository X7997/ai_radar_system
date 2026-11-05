import paramiko
import sys

code = "607803"

try:
    print("Connecting to 8.129.129.246...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('8.129.129.246', username='root', password='qryyds7.9.', timeout=10)
    print("Connected successfully!")
    
    print(f"Writing SMS code {code} to /root/sms_code.txt...")
    ssh.exec_command(f"echo '{code}' > /root/sms_code.txt")
    print("Done!")
    
    # Also check the log for success
    import time
    time.sleep(5) # wait for bot to process it
    stdin, stdout, stderr = ssh.exec_command('tail -n 20 /root/xhs.log')
    print("Logs:")
    print(stdout.read().decode('utf-8'))
    
except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
