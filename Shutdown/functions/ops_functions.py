import functions.file_functions as file
import functions.fleet_functions as fleet
import functions.cert_functions as cert
import functions.core_functions as core
import functions.install_functions as install
import sys
import json
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

debug = False

def getVcfOpsAuthToken(inFqdn, username, password, verify):
            
    if debug:
        print(f"In: getAuthToken")

    url = f"https://{inFqdn}/suite-api/api/auth/token/acquire"
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    payload = json.dumps({
        "username": username,
        "password": password,
        "authSource": "local"
    }) 

    try:

        response = requests.post(url=url, data=payload, headers=headers, verify=verify )    
        response.raise_for_status
        jResponse = response.json()
        
        if not (response.status_code < 200 or response.status_code >= 300):
            return jResponse['token']
        else:
            print(f"INFO: Response Code: {str(response.status_code)}")
            if debug:
                print(json.dumps(jResponse, indent=4))

            return response.status_code

    except requests.exceptions.HTTPError as e:
        print(f"ERROR (HTTP): {e}")
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR (CONNECT): {e}")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"ERROR (TIMEOUT): {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"ERROR (REQUEST): {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

def getAllVcfOpsGlobalSettings(inFqdn,token, verify):

    if debug:
        print(f"In: importCertificateToFleetManager")

    url = f"https://{inFqdn}/suite-api/api/deployment/config/globalsettings"
        
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'OpsToken ' + token,
        'Accept': 'application/json'
    }
 
    payload = {}

    if debug:
        print(payload)

    try:
        response = requests.get(url=url, data=payload, headers=headers, verify=verify )
        jResponse = response.json()

        if response.status_code < 200 or response.status_code >= 300:
            print(json.dumps(jResponse, indent=4))
            response.raise_for_status()
            return response.status_code
        else:

            return jResponse

    except requests.exceptions.HTTPError as e:
        print(f"ERROR (HTTP): {e}")
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR (CONNECT): {e}")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"ERROR (TIMEOUT): {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"ERROR (REQUEST): {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

def getVcfOpsGlobalSetting(inFqdn,token, verify, key):

    if debug:
        print(f"In: getVcfOpsSetting")

    url = f"https://{inFqdn}/suite-api/api/deployment/config/globalsettings/{key}"
        
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'OpsToken ' + token,
        'Accept': 'application/json'
    }
 
    payload = {}

    if debug:
        print(payload)

    try:
        print(f"TASK: Get Global Setting: '{key}'")
        response = requests.get(url=url, data=payload, headers=headers, verify=verify )
        jResponse = response.json()

        if response.status_code < 200 or response.status_code >= 300:
            print(f"ERROR: Response Code: {str(response.status_code)}")
            print(json.dumps(jResponse, indent=4))
            response.raise_for_status()
            return None
        else:
            print(f"INFO: Global Setting: '{key}', Value: {jResponse['values'][0]}")

    except requests.exceptions.HTTPError as e:
        print(f"ERROR (HTTP): {e}")
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR (CONNECT): {e}")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"ERROR (TIMEOUT): {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"ERROR (REQUEST): {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

def checkVcfOpsGlobalSetting(inFqdn,token, verify, key, value):

    if debug:
        print(f"In: checkVcfOpsGlobalSetting")

    try:
        print(f"TASK: Global Setting Check: '{key}' = '{value}'")
        result = getVcfOpsGlobalSetting(inFqdn, token, verify, key)

        if result:
            if result == value:
                print(f"INFO: Global Setting: '{key}' is set to {result}")
                return True
            else:
                return False

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


def setVcfOpsGlobalSetting(inFqdn,token, verify, key, value):

    if debug:
        print(f"In: setVcfOpsGlobalSetting")

    url = f"https://{inFqdn}/suite-api/api/deployment/config/globalsettings/{key}/{value}"
        
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'OpsToken ' + token,
        'Accept': 'application/json'
    }

    payload = {}
    
    if debug:
        print(payload)

    try:
        print(f"TASK: Setting the value of '{key}' to '{value}'")
        response = requests.put(url=url, data=payload, headers=headers, verify=verify )

        if response.status_code < 200 or response.status_code >= 300:
            response.raise_for_status()
            print(f"ERROR: Response Code: {str(response.status_code)}")
            return False
        else:
            return True

    except requests.exceptions.HTTPError as e:
        print(f"ERROR (HTTP): {e}")
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR (CONNECT): {e}")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"ERROR (TIMEOUT): {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"ERROR (REQUEST): {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)