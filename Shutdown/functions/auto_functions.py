import functions.file_functions as file
import sys
import json
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

debug = False

############################################################
# Get Refresh Token (Username/Password) - VCF Automation 9
############################################################

def getRefreshToken(inFqdn, username, password, domain, verify):
    
    print(f"TASK: Obtain Refresh Token for '{username}'.")

    if debug:
        print(f"In: getRefreshToken")

    url = f"https://{inFqdn}/csp/gateway/am/api/login?access_token"
        
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    payload = json.dumps({
        "username": username,
        "password": password,
        "domain": domain
    })


    if debug:
        print(payload)

    try:
        response = requests.post(url=url, data=payload, headers=headers, verify=verify )
        print(f"INFO: Submitting Token Request for '{username}'.")
        if not (response.status_code < 200 or response.status_code >= 300):
            print(f"INFO: Refresh Token Request Successful.")
            jResponse = response.json()
            response.raise_for_status
            return(jResponse['refresh_token'])    
        else:
            print(f"ERROR: Refresh Token Request Failed.")

    except requests.exceptions.HTTPError as e:
        print(f"ERROR: HTTP: {e}")
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR: CONNECT: {e}")
    except requests.exceptions.Timeout:
        print(f"ERROR: TIMEOUT: {e}")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: REQUEST: {e}")


pwdFile = '/home/holuser/Desktop/PASSWORD.txt'
password = file.readFile(pwdFile)
aFqdn = 'auto-a.site-a.vcf.lab'
username = 'admin  '
password = 'password'
domain = 'domain'
sslVerify = False

print (f"{getRefreshToken(aFqdn, username, password, domain, sslVerify)}")