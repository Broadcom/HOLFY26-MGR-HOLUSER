import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import base64
import functions.core_functions as core
import functions.file_functions as file
import sys

debug = False
sslVerify = False
vSanTimeout = 2700

### Fleet Management Functions

## Tokens

def getEncodedToken(username, password):
    if debug:
        print(f"getEncodedToken")
    
    credentials = f"{username}:{password}"
    bytesCredentials = credentials.encode('utf-8')
    base64BytesCredentials = base64.b64encode(bytesCredentials)
    base64Cred = base64BytesCredentials.decode('utf-8')

    return base64Cred

def getAuthToken(inFqdn, verify, username, password, authSource):
            
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

### REQUEST STATUS

def getRequestStatus(inFqdn, token, verify, requestId):
    
    if debug:
        print(f"In: getRequestStatus")

    url = f"https://{inFqdn}/lcm/request/api/v2/requests/{str(requestId)}"
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + token,
        'Accept': 'application/json'
    }

    payload = {}

    try:

        response = requests.get(url=url, data=payload, headers=headers, verify=verify )    
        jResponse = response.json()

        if not (response.status_code < 200 or response.status_code >= 300):
            response.raise_for_status 
            print(f"INFO: Request State: {jResponse["state"]}")
            if jResponse["state"] == "FAILED":
                if debug:
                    print(json.dumps(jResponse, indent=4))
            return jResponse["state"]
        else:
            print(f"INFO: Response Code: {str(response.status_code)}")
            if debug:
                print(json.dumps(jResponse, indent=4))
            response.raise_for_status  
            return "FAILED"

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

def getProductsInEnvironments(inFqdn, token, verify):
    if debug:
        print(f"In: getAllEnvironments")

    try:
        url = f"https://{inFqdn}/lcm/lcops/api/v2/environments"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + token,
            'Accept': 'application/json'
        }

        payload = {}

        response = requests.get(url=url, data=payload, headers=headers, verify=verify )       
        response.raise_for_status
        jResponse = response.json()
        

        if not (response.status_code < 200 or response.status_code >= 300):
            for environment in jResponse:
                print(f'{environment["environmentName"]}')
                products = environment['products']
                for product in products:
                    print(f'{product["id"]}')

        else:
            print(f"INFO: Response Code: {str(response.status_code)}")
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

def getAllEnvironments(inFqdn, token, verify):
    if debug:
        print(f"In: getAllEnvironments")

    try:
        url = f"https://{inFqdn}/lcm/lcops/api/v2/environments"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + token,
            'Accept': 'application/json'
        }

        payload = {}

        response = requests.get(url=url, data=payload, headers=headers, verify=verify )       
        response.raise_for_status
        jResponse = response.json()
        

        if not (response.status_code < 200 or response.status_code >= 300):
            result = {}
            for environment in jResponse:
                env = environment["environmentName"]
                product_ids = [product['id'] for product in environment['products']]
                
                result[env] = {"products": product_ids}               

            return result
        else:
            print(f"INFO: Response Code: {str(response.status_code)}")
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

def getEnvironmentVmidByName(inFqdn, token, verify, envName):
    if debug:
        print(f"In: getEnvironmentVmidByName")

    try:
        url = f"https://{inFqdn}/lcm/lcops/api/v2/environments"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + token,
            'Accept': 'application/json'
        }

        payload = {}

        response = requests.get(url=url, data=payload, headers=headers, verify=verify )       
        response.raise_for_status
        jResponse = response.json()
        
        if not (response.status_code < 200 or response.status_code >= 300):
            for environment in jResponse:
                if environment["environmentName"] == envName:
                    return environment["environmentId"]
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

def getCertificateVmidByAlias(inFqdn, token, verify, alias):
    
    if debug:
        print(f"In: getCertificateVmidByAlias")
    
    url = f"https://{inFqdn}/lcm/locker/api/certificates/list/vmids"
        
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + token,
        'Accept': 'application/json'
    }
        
    try:
        print(f"TASK: Checking for Certificate (by Alias): {alias}")
        response = requests.get(url=url, headers=headers, verify=verify )
        jResponse = response.json()
        
        if response.status_code < 200 or response.status_code >= 300:
            print(f"INFO: Response Code: {str(response.status_code)}")
            response.raise_for_status
            return response.status_code
        else:
            if debug:
                print(json.dumps(jResponse, indent=4))
            
            for cert in jResponse:
                if (cert["alias"] == alias):
                    print(f"INFO: Certificate : {alias} : {cert['vmid']} - Found")
                    return cert["vmid"]
                else:
                    continue

            print(f"INFO: Certificate: {alias} - Not Found")
            return None

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

def deleteCertificateByAlias(inFqdn, token, verify, alias):
    
    if debug:
        print(f"In: deleteCertificateByVmid")
    
    vmid = getCertificateVmidByAlias(inFqdn, token, verify, alias)

    if vmid:
        url = f"https://{inFqdn}/lcm/locker/api/v2/certificates/{str(vmid)}"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + token,
            'Accept': 'application/json'
        }
            
        try:
            print(f"TASK: Deleting Certificate from Locker: {alias}")
            response = requests.delete(url=url, headers=headers, verify=verify )
            jResponse = response.json()
            
            if response.status_code < 200 or response.status_code >= 300:
                print(f"INFO: Response Code: {str(response.status_code)}")
                if debug:
                    print(json.dumps(jResponse, indent=4))
                response.raise_for_status
                return response.status_code
            else:
                print(json.dumps(jResponse, indent=4))
                for cert in jResponse:
                    if (cert["alias"] == alias):
                        print(f"INFO:  Certificate: {alias} : {cert['vmid']} - Deleted")
                        return cert["vmid"]
                    else:
                        continue
                
                print(f"INFO: Certificate: {alias} - Not Found")
                return None

        except requests.exceptions.HTTPError as e:
            print(f"HTTP_ERROR: {e}")
        except requests.exceptions.ConnectionError as e:
            print(f"CONNECT_ERROR: {e}")
        except requests.exceptions.Timeout:
            print(f"TIMEOUT_ERROR: {e}")
        except requests.exceptions.RequestException as e:
            print(f"REQUEST_ERROR: {e}")
    else:
        print(f"INFO: Certificate Id: {alias} - Not Found")
        return None

def importCertificateToFleetManager(inFqdn,token, verify, alias, pemFile, keyFile):

    if debug:
        print(f"In: importCertificateToFleetManager")

    url = f"https://{inFqdn}/lcm/locker/api/v2/certificates/import"
        
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + token,
        'Accept': 'application/json'
    }
 
    caChain = file.readFile(pemFile)
    key = file.readFile(keyFile)

    payload = json.dumps({
        "alias": alias,
        "certificateChain": caChain,
        "passcode": "",
        "privateKey": key
    }, indent=4) 

    if debug:
        print(payload)

    try:
        print(f"TASK: Importing Certificate {alias} into Locker")
        response = requests.post(url=url, data=payload, headers=headers, verify=verify )
        jResponse = response.json()

        if response.status_code < 200 or response.status_code >= 300:
            print(f"INFO: Response Code: {str(response.status_code)}")
            print(payload)
            print(json.dumps(jResponse, indent=4))
            response.raise_for_status()
            return response.status_code
        else:
            print(f"INFO: Certificate '{alias}' import complete.")

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

def syncInventoryByEnvironmentId(inFqdn,token, verify, environmentId):

    if debug:
        print(f"In: updateProductSupportPack")

    url = f"https://{inFqdn}/lcm/lcops/api/v2/environments/{environmentId}/inventory-sync"
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + token,
        'Accept': 'application/json'
    }

    payload = {}

    try:
        response = requests.post(url=url, data=payload, headers=headers, verify=verify )       
        response.raise_for_status
        jResponse = response.json()
        
        if not (response.status_code < 200 or response.status_code >= 300):
            return jResponse
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
   
## Inventory Sync a Product in a single environment

def syncInventoryProductByEnvironmentId(inFqdn, token, verify, environmentId, productId):

    if debug:
        print(f"In: updateProductSupportPack")

    url = f"https://{inFqdn}/lcm/lcops/api/v2/environments/{environmentId}/products/{productId}/inventory-sync"
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + token,
        'Accept': 'application/json'
    }

    payload = {}

    try:
        response = requests.post(url=url, data=payload, headers=headers, verify=verify )       
        jResponse = response.json()

        if response.status_code < 200 or response.status_code >= 300:
            print(f"INFO: Response Code: {str(response.status_code)}")
            if debug:
                print(json.dumps(jResponse, indent=4))
            response.raise_for_status
            return response.status_code
        else:
            return jResponse["requestId"]

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
   

## Power On a Product in a single environment

def powerStateProductByEnvironmentId(inFqdn, token, verify, environmentId, productId, powerState):

    if debug:
        print(f"In: updateProductSupportPack")

    url = f"https://{inFqdn}/lcm/lcops/api/v2/environments/{environmentId}/products/{productId}/{powerState}"
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + token,
        'Accept': 'application/json'
    }

    payload = {}

    try:
        response = requests.post(url=url, data=payload, headers=headers, verify=verify )       
        jResponse = response.json()

        if response.status_code < 200 or response.status_code >= 300:
            print(f"INFO: Response Code: {str(response.status_code)}")
            if debug:
                print(json.dumps(jResponse, indent=4))
            response.raise_for_status
            return response.status_code
        else:
            return jResponse["requestId"]

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
   

def triggerPowerEvent(inFqdn, token, verify, environment, productId, powerState):
    try:

        print(f"TASK: Checking '{inFqdn}' for '{environment}' environment.")
        envId = getEnvironmentVmidByName(inFqdn, token, verify, environment)
        print(f"INFO: Environment '{environment}' has an ID of '{envId}'")
            
        if (envId):    
            requestId = powerStateProductByEnvironmentId(inFqdn, token, verify, envId, productId, powerState)
            print(f"TASK: Triggering Power Event - '{powerState}' for {productId} - (Request Id: {requestId})")
            
            requestStatus = getRequestStatus(inFqdn, token, verify, requestId)
            
            while requestStatus != "COMPLETED":
           
                core.countdown(45,1)

                requestStatus = getRequestStatus(inFqdn, token, verify, requestId)

                if requestStatus =="FAILED":
                    raise ValueError(f"Power Event '{powerState}' for {productId} failed.")
                
        else:
            print(f"ERROR: Environment '{environment}' does not exist.")

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

def triggerInventorySync(inFqdn, token, verify, environment, productIds):

    try:
        print(f"TASK: Checking for {environment}")
        envId = getEnvironmentVmidByName(inFqdn, token, verify, environment)
        print(f"INFO: Environment '{environment}' has an ID of '{envId}'")
        if (envId):
            for productId in productIds:

                requestId = syncInventoryProductByEnvironmentId(inFqdn, token, sslVerify, envId, productId )

                print(f"TASK: Trigger inventory sync for {productId} (Request Id: {requestId})")
            
                requestStatus = getRequestStatus(inFqdn, token, verify, requestId)

                while requestStatus != "COMPLETED":
                    
                    core.countdown(15, 1)

                    requestStatus = getRequestStatus(inFqdn, token, verify, requestId)
                    
                    if requestStatus == "FAILED":
                        raise ValueError(f"Inventory sync failed for {productId} in {environment}.")                   
                    
        else:
            print(f"ERROR: Environment '{environment}' does not exist.")

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
   
    finally:
        requestStatus = ""
        envId = ""

def addSoftwareToDepot(inFqdn, token, verify, productId, productVersion, productBinaryType, productName, status="NOT_DOWNLOADED"):
            
    if debug:
        print(f"In: addSoftwareToDepot")

    url = f"https://{inFqdn}/lcm/lcops/api/settings/downloadfrombroadcomdepot"

    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + token,
        'Accept': 'application/json'
    }

    payload = json.dumps([{
        "productId": productId,
        "productVersion": productVersion,
        "productBinaryType": productBinaryType,
        "productName": productName,
        "downloadStatus": status
    }]) 

    try:

        response = requests.post(url=url, data=payload, headers=headers, verify=verify )    
        jResponse = response.json()

        if debug:
            print(json.dumps(jResponse, indent=4)) 

        if not (response.status_code < 200 or response.status_code >= 300):
            response.raise_for_status 
            
            
            requestIds = jResponse["requestId"].split(",")
            count = len(requestIds)
            print(f"INFO: Adding {count} Software Component(s) to the Depot.")
            for requestId in requestIds:
                print(f"INFO: RequestId: {requestId}")

            return count, requestIds

        else:
            print(f"INFO: Response Code: {str(response.status_code)}")
            raise ValueError(f"Failed to add software to depot: {productId} - {productVersion} - {productBinaryType}")


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

def deleteSoftwareFromDepot(inFqdn, token, verify, productId, productVersion, productBinaryType, productName):
            
    if debug:
        print(f"In: deleteSoftwareFromDepot")

    url = f"https://{inFqdn}/lcm/lcops/api/settings/productbinarydelete"

    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + token,
        'Accept': 'application/json'
    }

    payload = json.dumps({
        "productId": productId,
        "productVersion": productVersion,
        "productBinaryType": productBinaryType,
        "productName": productName,
    }) 

    try:
        print(f"TASK: Deleting Binary from Depot: {productId} - {productVersion} - {productBinaryType}")
        response = requests.post(url=url, data=payload, headers=headers, verify=verify )    
        jResponse = response.json()

        if debug:
            print(json.dumps(jResponse, indent=4)) 

        if not (response.status_code < 200 or response.status_code >= 300):
            response.raise_for_status 
            print(json.dumps(jResponse, indent=4)) 
            print(f"INFO: RequestId: {jResponse["requestId"]}")
            return jResponse["requestId"]

        else:
            print(f"INFO: Response Code: {str(response.status_code)}")

            response.raise_for_status        
            return "FAILED"

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

def createPassword(inFqdn, token, verify, username, alias, password, tenant ):

    url = f"https://{inFqdn}/lcm/locker/api/v3/passwords"

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + token,
        'Accept': 'application/json'
    }

    description = f'{alias} created programmatically'

    payload = json.dumps({
        "alias": alias,
        "password": password,
        "passwordDescription": description,
        "referenced": None,
#        "tenant": tenant,
        "userName": username
    }, indent=4) 

    try:

        response = requests.post(url=url, data=payload, headers=headers, verify=verify )    
        jResponse = response.json()

        if not (response.status_code < 200 or response.status_code >= 300):
            response.raise_for_status 
            print(f"INFO: Password {alias} created with {jResponse["vmid"]}.")
            return jResponse["vmid"]
        else:
            print(f"INFO: Response Code: {str(response.status_code)}")
            if debug:
                print(json.dumps(jResponse, indent=4))
            response.raise_for_status        
            return "FAILED"

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

def getUsernameFromPasswordAlias(inFqdn, token, verify, alias, tenant):

    url = f"https://{inFqdn}/lcm/locker/api/passwords"

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + token,
        'Accept': 'application/json'
    }

    payload = {}

    try:
        print(f"TASK: Get Username associated with '{alias}'")
        response = requests.get(url=url, data=payload, headers=headers, verify=verify )    
        jResponse = response.json()

        if not (response.status_code < 200 or response.status_code >= 300):
            response.raise_for_status 
            for password in jResponse:
                if (password['alias'] == alias):
                    print(f"INFO: Password '{alias}' - Found")
                    print(f"INFO: Username: {password['userName']}")
                    return password['userName']
            
            print(f"INFO: Password {alias} not found")
            return None
        else:
            print(f"INFO: Response Code: {str(response.status_code)}")
            if debug:
                print(json.dumps(jResponse, indent=4))
            raise ValueError(f"Failed to get username for password alias: {alias}")

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

def deletePasswordByAlias(inFqdn, token, verify, alias, tenant):
    
    if debug:
        print(f"In: deletePasswordByAlias")
    
    vmid = getPasswordVmid(inFqdn, token, verify, alias, tenant)
    
    if vmid:
        url = f"https://{inFqdn}/lcm/locker/api/v2/passwords/{vmid}"

        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + token,
            'Accept': 'application/json'
        }
        
        payload = {}

        try:
            print(f"TASK: Deleting Password from Locker: {alias}")
            response = requests.delete(url=url, headers=headers, data=payload, verify=verify )
            jResponse = response.json()

            if debug:
                print(json.dumps(jResponse, indent=4))
            
            if response.status_code < 200 or response.status_code >= 300:
                print(f"INFO: Password {alias} deleted.")
                response.raise_for_status
            else:
                print(f"INFO: Response Code: {str(response.status_code)}")


        except requests.exceptions.HTTPError as e:
            print(f"HTTP_ERROR: {e}")
        except requests.exceptions.ConnectionError as e:
            print(f"CONNECT_ERROR: {e}")
        except requests.exceptions.Timeout:
            print(f"TIMEOUT_ERROR: {e}")
        except requests.exceptions.RequestException as e:
            print(f"REQUEST_ERROR: {e}")
    else:
        print(f"INFO: Certificate Id: {alias} - Not Found")
        return None

def getAllPasswords(inFqdn, token, verify, tenant):

    url = f"https://{inFqdn}/lcm/locker/api/passwords"

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + token,
        'Accept': 'application/json'
    }

    payload = {}

    try:
        print(f"TASK: Get All Password in Fleet Management - Locker")
        
        response = requests.get(url=url, data=payload, headers=headers, verify=verify )    
        jResponse = response.json()
        
        if debug:
            print(json.dumps(jResponse, indent=4))

        if not (response.status_code < 200 or response.status_code >= 300):
            response.raise_for_status
            for password in jResponse:
                print(f"INFO: Password: {password['alias']} - {password['vmid']}") 
            return jResponse       
        else:
            if debug:
                print(f"INFO: Response Code: {str(response.status_code)}")

            response.raise_for_status
            print(f"INFO: Password: Not Found")
            return None

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


def getPasswordVmid(inFqdn, token, verify, alias, tenant):

    url = f"https://{inFqdn}/lcm/locker/api/passwords"

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + token,
        'Accept': 'application/json'
    }

    payload = {}

    try:
        print(f"TASK: Locating Password Id for {alias}")
        
        response = requests.get(url=url, data=payload, headers=headers, verify=verify )    
        jResponse = response.json()
        
        if debug:
            print(json.dumps(jResponse, indent=4))

        if not (response.status_code < 200 or response.status_code >= 300):
            response.raise_for_status
            for password in jResponse:
                if (password['alias'] == alias):
                    print(f"INFO: Password {alias}:{password['vmid']} - Already Exists")
                    return password['vmid']
                else: 
                    continue

            print(f"INFO: Password: {alias} - Not Found")
            return None
        
        else:
            if debug:
                print(f"INFO: Response Code: {str(response.status_code)}")

            response.raise_for_status
            raise ValueError(f"Password: {alias} - Not Found")

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

def buildLockerIdFromVmid(vmid, alias, contentType):

    match contentType:
        case "certificate":
            return f'locker:certificate:{vmid}:{alias}'
        case "password":
            return f'locker:password:{vmid}:{alias}'
        case "license":
            return f'locker:license:{vmid}:{alias}'
        case _:
            print(f"ERROR: Unknown content type: {contentType}")
            return None
    

def isProductBinaryAvailable(inFqdn, token, verify, productId, productVersion, productBinaryType):
    if debug:
        print(f"In: isProductBinaryAvailable")

    try:
        url = f"https://{inFqdn}/lcm/lcops/api/v2/settings/product-binaries"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + token,
            'Accept': 'application/json'
        }

        payload = {}

        response = requests.get(url=url, data=payload, headers=headers, verify=verify )       
        response.raise_for_status
        jResponse = response.json()
        
        if debug:
            print(json.dumps(jResponse, indent=4))
        
        if not (response.status_code < 200 or response.status_code >= 300):
            for download in jResponse:
                if (download["productId"] == productId) and (download["productVersion"] == productVersion) and (download["productBinaryType"] == str.lower(productBinaryType)):
                    print(f"INFO: Product '{productBinaryType}' Binary: {productId} - {productVersion} - Available")
                    return True

            print(f"INFO: Product '{productBinaryType}' Binary: {productId} - {productVersion} - Not Found")            
            return False
        else:
            print(f"INFO: Product '{productBinaryType}' Binary: {productId} - {productVersion} - Not Available")
            print(f"INFO: Response Code: {str(response.status_code)}")
            return False
    
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

def getAllDownloadedProductBinariesJson(inFqdn, token, verify, productId, productVersion):
    if debug:
        print(f"In: getAllDownloadedProductBinariesJson")

    try:
        url = f"https://{inFqdn}/lcm/lcops/api/v2/settings/product-binaries"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + token,
            'Accept': 'application/json'
        }

        payload = {}

        response = requests.get(url=url, data=payload, headers=headers, verify=verify )       
        response.raise_for_status
        jResponse = response.json()
        
        if not (response.status_code < 200 or response.status_code >= 300):
            return jResponse
        else:
            print(f"INFO: Response Code: {str(response.status_code)}")
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

def createSoftwareDepot(inFqdn, token, verify, depotUsername, depotPassword, depotType, depotPathOrUrl=None, enabled=True, trustCert=True):
    if debug:
        print(f"In: createSoftwareDepot")


    try:
        print(f"TASK: Creating Offline Depot")
        
        url = f"https://{inFqdn}/lcm/lcops/api/depot-configuration/{depotType}"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + token,
            'Accept': 'application/json'
        }

        match depotType:
            case 'local':
                payload = json.dumps(
                    {
                        "depotType": depotPathOrUrl,
                        "isEnabled": enabled,
                    }, indent=4)
                
            case 'online':
                payload = json.dumps(
                {
                    "password": depotPassword,
                    "userName": depotUsername
                }, indent=4)

            case 'offline':
                payload = json.dumps(
                    {
                        "offlineDepotUrl": depotPathOrUrl,
                        "userName": depotUsername,
                        "password": depotPassword,
                        "isEnabled": enabled,
                        "trustCertificate": trustCert
                    }, indent=4)
            case _:
                print(f"ERROR: Unknown depot type: {depotType}")
                return False

        response = requests.post(url=url, data=payload, headers=headers, verify=verify )       
        response.raise_for_status
        jResponse = response.json()
        
        if debug:
            print(json.dumps(jResponse, indent=4))

        if not (response.status_code < 200 or response.status_code >= 300):
            print(f"INFO: '{depotType}' Depot created at {depotPathOrUrl}")
            return True
        else:
            print(f"INFO: Response Code: {str(response.status_code)}")
            return False
    
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

def checkDepotExists(inFqdn, token, verify, depotType, enabled):
    if debug:
        print(f"In: depotExists")

    print(f"TASK: Checking for {depotType} Depot")
    try:
        url = f"https://{inFqdn}/lcm/lcops/api/depot-configuration?depotType={depotType}&isEnabled={enabled}"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + token,
            'Accept': 'application/json'
        }

        payload = {}

        response = requests.get(url=url, data=payload, headers=headers, verify=verify )       
        response.raise_for_status
        jResponse = response.json()
        
        if debug:
            print(json.dumps(jResponse, indent=4))

        if not (response.status_code < 200 or response.status_code >= 300):
            if len(jResponse) == 0:
                print(f"INFO: '{depotType}' Depot Missing")
                return False
            else:
                print(f"INFO: '{depotType}' Depot found")
                return True
        else:   
            print(f"INFO: Response Code: {str(response.status_code)}")
            return False
    
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

def deleteSoftwareDepot(inFqdn, token, verify, depotUsername, depotPassword, depotType, depotPathOrUrl=None, enabled=True, trustCert=True):
    if debug:
        print(f"In: configSoftwareDepot")
    try:
        print(f"TASK: Delete '{depotType}' Depot Settings")
        
        match depotType:
            case "local":
                print(f"INFO: Deleting '{depotType}' Depot")
                url = f"https://{inFqdn}/lcm/lcops/api/settings/depotlocalsetting/delete"
                payload = json.dumps(
                    {
                        "depotType": depotPathOrUrl,
                        "isEnabled": enabled,
                    }, indent=4)
            case "online":
                print(f"INFO: Deleting '{depotType}' Depot")
                url = f"https://{inFqdn}/lcm/lcops/api/settings/depotonlinesetting/delete"
                payload = json.dumps(
                    {
                        "password": depotPassword,
                        "userName": depotUsername
                    }, indent=4)

            case 'offline':
                print(f"INFO: Deleting '{depotType}' Depot")
                url = f"https://{inFqdn}/lcm/lcops/api/settings/depotofflinesetting/delete"
                payload = json.dumps(
                    {
                        "directoryPath": None,
                        "depotType": depotType,
                        "offlineDepotUrl": depotPathOrUrl,
                        "userName": depotUsername,
                        "password": depotPassword,
                        "isEnabled": enabled,
                        "trustCertificate": trustCert
                    }, indent=4)
            case _:
                print(f"ERROR: Unknown depot type: '{depotType}'")
                return False            

        url = f"https://{inFqdn}/lcm/lcops/api/settings/depotofflinesetting/delete"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + token,
            'Accept': 'application/json'
        }

        payload = json.dumps(
            {
                "depotType": "offline",
                "offlineDepotUrl": depotPathOrUrl,
                "userName": depotUsername,
                "password": depotPassword,
                "isEnabled": enabled,
                "trustCertificate": trustCert
            }, indent=4)

        response = requests.delete(url=url, data=payload, headers=headers, verify=verify )       
        response.raise_for_status
       

        if not (response.status_code < 200 or response.status_code >= 300):
            print(f"INFO: '{depotType}' Depot Settings - Deleted")
            return True
        else:
            print(f"INFO: Response Code: {str(response.status_code)}")
            return False
    
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


def getDatacenterVmid(inFqdn, token, verify, dcName):
    if debug:
        print(f"In: getDatacenterVmid")

    try:
        print(f"TASK: Checking for Datacenter: {dcName}")
        url = f"https://{inFqdn}/lcm/lcops/api/v2/datacenters"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + token,
            'Accept': 'application/json'
        }

        payload = {}

        response = requests.get(url=url, data=payload, headers=headers, verify=verify )       
        response.raise_for_status
        jResponse = response.json()
        

        if not (response.status_code < 200 or response.status_code >= 300):
            for datacenter in jResponse:
                print(f'INFO: Located: {datacenter["dataCenterName"]}, Vmid: {datacenter["dataCenterVmid"]}')
                if datacenter["dataCenterName"] == dcName:
                    return datacenter["dataCenterVmid"]
                else:
                    continue
            return None
        else:
            print(f"INFO: Response Code: {str(response.status_code)}")
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

def triggerVcDataCollection(inFqdn, token, verify, dcName, vcName):
    if debug:
        print(f"In: triggerVcDataCollection")

    try:
        print(f"TASK: Triggering vCenter Data Collection for Datacenter: {dcName}")

        dcVmid = getDatacenterVmid(inFqdn, token, verify, dcName)

        url = f"https://{inFqdn}/lcm/lcops/api/v2/datacenters/{dcVmid}/vcenters/{vcName}/data-collection"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + token,
            'Accept': 'application/json'
        }

        payload = {}

        response = requests.post(url=url, data=payload, headers=headers, verify=verify )       
        response.raise_for_status
        jResponse = response.json()
        
        if response.status_code < 200 or response.status_code >= 300:
            print(f"INFO: Response Code: {str(response.status_code)}")
            if debug:
                print(json.dumps(jResponse, indent=4))
            response.raise_for_status
            return response.status_code
        else:
            return jResponse["requestId"]
    
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

def getAllCertificates(inFqdn, token, verify=False):
    
    if debug:
        print(f"In: getAllCertificate")
    
    url = f"https://{inFqdn}/lcm/locker/api/certificates/list/vmids"
        
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + token,
        'Accept': 'application/json'
    }
        
    try:
        print(f"TASK: Listing ALL Certificates")
        response = requests.get(url=url, headers=headers, verify=verify )
        jResponse = response.json()
        
        if response.status_code < 200 or response.status_code >= 300:
            print(f"INFO: Response Code: {str(response.status_code)}")
            response.raise_for_status
            return response.status_code
        else:
            if debug:
                print(json.dumps(jResponse, indent=4))
            
            if len(jResponse) > 0:
                for cert in jResponse:
                    print(f"INFO: Certificate : {cert}")
                          
                return jResponse
            else:
                print(f"INFO: No Certificates Found")
                return None

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