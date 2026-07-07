import functions.file_functions as file
import functions.fleet_functions as fleet
import functions.cert_functions as cert
import functions.core_functions as core
import functions.install_functions as install
import sys
import json
import time
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


def createOpsCertSession(inFqdn, token, verify):
    """
    Creates a requests.Session initialized for the VCF Ops internal cert management API.

    Two requirements apply to all /suite-api/internal/certificatemanagement/* calls:
      1. The X-vRealizeOps-API-use-unsupported header must be present.
      2. A one-time init POST to /vcf-operations/rest/ops/internal/... must be made
         first so the server establishes the internal session context.

    Returns the initialized Session.  Pass this to getOpsCertResourceKey,
    replaceOpsCertificate, and pollOpsCertTask to share session state.
    """
    session = requests.Session()
    session.verify = verify
    session.headers.update({
        'Authorization': 'OpsToken ' + token,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-vRealizeOps-API-use-unsupported': 'true'
    })
    try:
        session.post(
            f"https://{inFqdn}/vcf-operations/rest/ops/internal/certificatemanagement/certificates/query",
            json={"vcfComponent": "VCF_MANAGEMENT", "vcfComponentType": "ARIA"},
            timeout=15
        )
    except Exception as e:
        print(f"WARN: Cert session init call failed: {e}")
    return session


def getOpsCertResourceKey(inFqdn, token, verify, targetFqdn, session=None):
    """
    Returns the certificateResourceKey for the TLS cert belonging to targetFqdn
    by querying POST /suite-api/internal/certificatemanagement/certificates/query.

    Response contains vcfCertificateModels[], each with applianceFqdn and
    certificateResourceKey fields.  Match is attempted on both applianceFqdn
    and issuedToCommonName so either the VIP or node FQDN can be supplied.

    Pass a session created with createOpsCertSession() to reuse the initialized
    session context; one will be created automatically if not provided.
    """
    if session is None:
        session = createOpsCertSession(inFqdn, token, verify)

    url = f"https://{inFqdn}/suite-api/internal/certificatemanagement/certificates/query"
    body = {"vcfComponent": "VCF_MANAGEMENT", "vcfComponentType": "ARIA"}

    try:
        print(f"TASK: Finding cert resource key for '{targetFqdn}' in VCF Ops")
        response = session.post(url, json=body, timeout=30)
        jResponse = response.json()

        if response.status_code < 200 or response.status_code >= 300:
            print(f"ERROR: Response Code: {str(response.status_code)}")
            print(json.dumps(jResponse, indent=4))
            return None

        for c in jResponse.get('vcfCertificateModels', []):
            appliance = c.get('applianceFqdn') or c.get('applianceIp', '')
            issued_to = c.get('issuedToCommonName', '')
            cert_key = c.get('certificateResourceKey')
            if targetFqdn.lower() in str(appliance).lower() or targetFqdn.lower() in str(issued_to).lower():
                print(f"INFO: Found cert resource key '{cert_key}' for appliance '{appliance}'")
                return cert_key

        print(f"INFO: No cert resource key found for '{targetFqdn}'")
        return None

    except Exception as e:
        print(f"ERROR: {e}")
        return None


def replaceOpsCertificate(inFqdn, token, verify, certKey, lockerVmid, caType="EXTERNAL_CA", session=None):
    """
    Triggers certificate replacement via PUT /suite-api/internal/certificatemanagement/
    certificates/{certKey}/replace.

    lockerVmid is the vmid of the new certificate in the VRSLCM locker.
    Returns the task ID string on success, or None on failure.

    Pass a session created with createOpsCertSession() to reuse the initialized
    session context; one will be created automatically if not provided.
    """
    if session is None:
        session = createOpsCertSession(inFqdn, token, verify)

    url = f"https://{inFqdn}/suite-api/internal/certificatemanagement/certificates/{certKey}/replace"
    body = {"certificateId": lockerVmid, "caType": caType}

    try:
        print(f"TASK: Triggering cert replacement for certKey='{certKey}' with lockerVmid='{lockerVmid}'")
        response = session.put(url, json=body, timeout=60)
        jResponse = response.json()

        if response.status_code not in (200, 201, 202):
            print(f"ERROR: Response Code: {str(response.status_code)}")
            print(json.dumps(jResponse, indent=4))
            return None

        taskId = jResponse.get('id')
        print(f"INFO: Cert replacement task started (taskId={taskId})")
        return taskId

    except Exception as e:
        print(f"ERROR: {e}")
        return None


def pollOpsCertTask(inFqdn, token, verify, taskId, maxWaitSec=600, intervalSec=15, session=None):
    """
    Polls GET /suite-api/internal/certificatemanagement/tasks/{taskId} until the
    task reaches SUCCESSFUL or FAILED status, or maxWaitSec is exceeded.

    Returns True if SUCCESSFUL, False otherwise.

    Pass a session created with createOpsCertSession() to reuse the initialized
    session context; one will be created automatically if not provided.
    """
    if session is None:
        session = createOpsCertSession(inFqdn, token, verify)

    url = f"https://{inFqdn}/suite-api/internal/certificatemanagement/tasks/{taskId}"

    elapsed = 0
    while elapsed < maxWaitSec:
        try:
            response = session.get(url, timeout=30)
            jResponse = response.json()
            status = jResponse.get('status', 'UNKNOWN')
            orch = jResponse.get('orchestratorTask') or {}
            orchStatus = orch.get('status') if orch else None
            errors = jResponse.get('errors', [])
            print(f"INFO: [{elapsed}s] Status={status}  OrchestratorTask={orchStatus}  errors={errors}")

            if status == 'SUCCESSFUL':
                return True
            if status == 'FAILED':
                print(f"ERROR: Cert replacement task FAILED")
                return False

        except Exception as e:
            print(f"WARN: Poll error: {e}")

        time.sleep(intervalSec)
        elapsed += intervalSec

    print(f"ERROR: Cert replacement task timed out after {maxWaitSec}s")
    return False