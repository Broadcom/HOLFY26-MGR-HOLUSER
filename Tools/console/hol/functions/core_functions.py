import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import time
import socket
import subprocess
import sys
import ipaddress

debug = False

def runRemoteSshCmd(hostname, username, password, command, hostCheck="no"):
    
    sshCmd = [
        'sshpass', '-p', f'{password}',
        'ssh', '-o', f'StrictHostKeyChecking={hostCheck}',
        f'{username}@{hostname}',
        command
    ]

    try:

        print(f'TASK: Running command: {sshCmd}')
        result = subprocess.run(sshCmd, stdout=-subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode == 0:
            print(f'INFO: Command executed successfully.')
        else:
            print(f'ERROR:\n: {result.stderr}')
                
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


def isReachable(hostname, port=443, timeout=5):
    try:
        with socket.create_connection((hostname, port), timeout):
            return True
    except (socket.timeout, socket.error):
        return False

def countdown(seconds, increment):
    while seconds != 0:
        mins, secs = divmod(seconds, 60)
        timer = f'{mins:02d}:{secs:02d}'
        print(f"INFO: Time Remaining: {timer}\r", end='\r')
        time.sleep(increment)
        seconds -= increment
    print(f"\nINFO: Countdown complete.")

def downloadFile(url, local_path):
    try:
        response = requests.get(url, verify=False)
        if response.status_code == 200:
            with open(local_path, 'wb') as file:
                file.write(response.content)
            print(f"INFO: File downloaded successfully to {local_path}")
        else:
            print(f"ERROR: Failed to download file. Status code: {response.status_code}")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

def isValidIpAddress(value):
    if debug:
        print(f'TASK: Checking if {value} is a valid IP address.')

    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False