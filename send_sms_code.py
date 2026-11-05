import os
import paramiko
import sys

code = "607803"

try:
    print("正在连接服务器 8.129.129.246...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('8.129.129.246', username='root', password=os.getenv("SERVER_PASS", "your_server_password"), timeout=10)
    print("服务器连接成功！")
    
    print(f"正在将短信验证码 {code} 写入 /root/sms_code.txt...")
    ssh.exec_command(f"echo '{code}' > /root/sms_code.txt")
    print("完成！")
    
    # Also check the log for success
    import time
    time.sleep(5) # wait for bot to process it
    stdin, stdout, stderr = ssh.exec_command('tail -n 20 /root/xhs.log')
    print("日志内容:")
    print(stdout.read().decode('utf-8'))
    
except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
