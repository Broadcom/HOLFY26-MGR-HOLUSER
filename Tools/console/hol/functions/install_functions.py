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


def deployOpsLogs(inFqdn, token, verify, envName, dcVmid, vcFqdn, vcUsername, vcLockerPasswordId, lockerCertId, vcDatacenter, vcCluster, vcNetwork, vcStorage, ipv4Gateway, ipv4Address, ipv4SubnetMask, vipIpv4Address, fqdn, vipFqdn, productId, productVersion, lockerPasswordId):

    hostname = fqdn.split(".",1)[0]
    dnsDomain = fqdn.split(".",1)[1]

    print(f"TASK: Deploy {productId} - {productVersion} to {envName}")

    try:
        url = f"https://{inFqdn}/lcm/lcops/api/v2/environments"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + token,
            'Accept': 'application/json'
        }

        payload = json.dumps(
        {
            "environmentId": "",
            "environmentName": envName,
            "environmentDescription": None,
            "environmentHealth": None,
            "logHistory": None,
            "environmentStatus": None,
            "infrastructure": {
                "properties": {
                "dataCenterVmid": dcVmid,
                "regionName": "",
                "zoneName": "",
                "vCenterName": vcFqdn,
                "vCenterHost": vcFqdn,
                "vcUsername": vcUsername,
                "vcPassword": vcLockerPasswordId,
                "acceptEULA": "false",
                "enableTelemetry": "true",
                "defaultPassword": "",
                "certificate": lockerCertId,
                "cluster": f"{vcDatacenter}#{vcCluster}",
                "storage": vcStorage,
                "folderName": "",
                "resourcePool": "",
                "diskMode": "thin",
                "network": vcNetwork,
                "masterVidmEnabled": "false",
                "vmwareSSOEnabled": "false",
                "dns": ipv4Gateway,
                "domain": dnsDomain,
                "gateway": ipv4Gateway,
                "netmask": ipv4SubnetMask,
                "searchpath": dnsDomain,
                "timeSyncMode": "ntp",
                "ntp": ipv4Gateway,
                "isDhcp": "false",
                "vcfProperties": "{\"vcfEnabled\":true,\"sddcManagerDetails\":[]}",
                "_selectedProducts": "[{\"id\":\"vrli\",\"type\":\"new\",\"selected\":true,\"sizes\":{\"9.0.0.0\":[\"standard\",\"cluster\"]},\"selectedVersion\":\"9.0.0.0\",\"selectedDeploymentType\":\"standard\",\"selectedAuthenticationType\":\"\",\"tenantId\":\"Standalone vRASSC\",\"description\":\"Operations-logs delivers heterogeneous and highly scalable log management with intuitive, actionable dashboards, sophisticated analytics and broad third-party extensibility, providing deep operational visibility and faster troubleshooting.\",\"detailsHref\":\"https://docs.vmware.com/en/VMware-Aria-Operations-for-Logs/index.html\",\"errorMessage\":null,\"productVersions\":[{\"version\":\"9.0.0.0\",\"deploymentType\":[\"standard\",\"cluster\"],\"productDeploymentMetaData\":{\"sizingURL\":null,\"productInfo\":\"Operations-logs - 9.0.0.0\",\"deploymentType\":[\"Standalone\",\"Cluster\"],\"deploymentItems\":{\"Virtual Machines\":[\"10,000\",\"30,000\"],\"Node Count\":[\"1\",\"3\"],\"Log Ingest Rate Per Day In Gbs\":[\"30\",\"75\"],\"Events Per Second\":[\"2,000\",\"5,000\"]},\"additionalInfo\":[\"*Standalone - Master node provisioned by default\",\"*Cluster - Master and two worker nodes provisioned by default\",\"#Refer to Operations-logs Installation Guide\"],\"disasterRecovery\":null}}],\"disasterRecoveryEnabled\":\"false\"}]",
                "_isRedeploy": "false",
                "_isResume": "false",
                "_leverageProximity": "false",
                "__isInstallerRequest": "false",
                "ipv6Gateway": "",
                "ipv6Netmask": "",
                "useIpv4": "",
                "useIpv6": "",
                "useIpv4AndIpv6": ""
                }
            },
            "products": [
                {
                "vmid": None,
                "tenant": "default",
                "version": productVersion,
                "id": productId,
                "productUuid": None,
                "fleetEnabled": True,
                "nodes": [
                    {
                    "type": "vrli-master",
                    "properties": {
                        "vmName": hostname,
                        "hostName": fqdn,
                        "ip": ipv4Address,
                        "ipPool": "",
                        "additionalVips": ""
                    }
                    }
                ],
                "properties": {
                    "authenticationType": "",
                    "ntp": ipv4Gateway,
                    "certificate": lockerCertId,
                    "contentLibraryItemId": "",
                    "productPassword": lockerPasswordId,
                    "adminEmail": f"admin@{dnsDomain}",
                    "fipsMode": "true",
                    "licenseRef": "",
                    "nodeSize": "small",
                    "configureClusterVIP": "true",
                    "affinityRule": False,
                    "isUpgradeVmCompatibility": False,
                    "vrliAlwaysUseEnglish": False,
                    "masterVidmEnabled": "false",
                    "configureAffinitySeparateAll": "true",
                    "timeSyncMode": "ntp",
                    "monitorWithvROps": "false",
                    "vmwareSSOEnabled": "false"
                },
                "references": [],
                "clusterVIP": {
                    "clusterVips": [
                    {
                        "type": "vrli-cluster-1",
                        "properties": {
                        "hostName": vipFqdn,
                        "ip": vipIpv4Address
                        }
                    }
                    ]
                }
                }
            ],
            "metaData": {},
            "requestId": None,
            "fleet": True
        }, indent=4)
    
        file.createFile(f'{productId}.json', payload)

        response = requests.post(url=url, data=payload, headers=headers, verify=verify )       
        response.raise_for_status
        jResponse = response.json()
        
        if debug:
            print(json.dumps(jResponse, indent=4))

        if not (response.status_code < 200 or response.status_code >= 300):
            print(f"INFO: RequestId: {jResponse['requestId']}")
            return jResponse["requestId"]
        else:   
            print(f"INFO: Response Code: {str(response.status_code)}")
            print(json.dumps(jResponse, indent=4))
            return response.status_code
        
    except requests.exceptions.HTTPError as e:
        print(f"ERROR(HTTP): {e}")
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR(CONNECT): {e}")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"ERROR(TIMEOUT): {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"ERROR(REQUEST): {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    

def deployNetOps(inFqdn, token, verify, envName, dcVmid, vcFqdn, vcUsername, vcLockerPasswordId, lockerCertId, vcDatacenter, vcCluster, vcNetwork, vcStorage, ipv4Gateway, ipv4Address, ipv4SubnetMask, fqdn, cFqdn, cIpv4Address, productId, productVersion, lockerPasswordId):

    hostname = fqdn.split(".",1)[0]
    dnsDomain = fqdn.split(".",1)[1]
    cHostname = cFqdn.split(".",1)[0]

    print(f"TASK: Deploy {productId} - {productVersion} to {envName}")

    try:
        url = f"https://{inFqdn}/lcm/lcops/api/v2/environments"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + token,
            'Accept': 'application/json'
        }

        payload = json.dumps(
        {
            "environmentId": "",
            "environmentName": envName,
            "environmentDescription": None,
            "environmentHealth": None,
            "logHistory": None,
            "environmentStatus": None,
            "infrastructure": {
                "properties": {
                "dataCenterVmid": dcVmid,
                "regionName": "",
                "zoneName": "",
                "vCenterName": vcFqdn,
                "vCenterHost": vcFqdn,
                "vcUsername": vcUsername,
                "vcPassword": vcLockerPasswordId,
                "acceptEULA": "false",
                "enableTelemetry": "true",
                "defaultPassword": "",
                "certificate": lockerCertId,
                "cluster": f"{vcDatacenter}#{vcCluster}",
                "storage": vcStorage,
                "folderName": "",
                "resourcePool": "",
                "diskMode": "thin",
                "network": vcNetwork,
                "masterVidmEnabled": "false",
                "vmwareSSOEnabled": "false",
                "dns": ipv4Gateway,
                "domain": dnsDomain,
                "gateway": ipv4Gateway,
                "netmask": ipv4SubnetMask,
                "searchpath": dnsDomain,
                "timeSyncMode": "ntp",
                "ntp": ipv4Gateway,
                "isDhcp": "false",
                "vcfProperties": "{\"vcfEnabled\":true,\"sddcManagerDetails\":[]}",
                "_selectedProducts": "[{\"id\":\"vrli\",\"type\":\"new\",\"selected\":true,\"sizes\":{\"9.0.0.0\":[\"standard\",\"cluster\"]},\"selectedVersion\":\"9.0.0.0\",\"selectedDeploymentType\":\"standard\",\"selectedAuthenticationType\":\"\",\"tenantId\":\"Standalone vRASSC\",\"description\":\"Operations-logs delivers heterogeneous and highly scalable log management with intuitive, actionable dashboards, sophisticated analytics and broad third-party extensibility, providing deep operational visibility and faster troubleshooting.\",\"detailsHref\":\"https://docs.vmware.com/en/VMware-Aria-Operations-for-Logs/index.html\",\"errorMessage\":null,\"productVersions\":[{\"version\":\"9.0.0.0\",\"deploymentType\":[\"standard\",\"cluster\"],\"productDeploymentMetaData\":{\"sizingURL\":null,\"productInfo\":\"Operations-logs - 9.0.0.0\",\"deploymentType\":[\"Standalone\",\"Cluster\"],\"deploymentItems\":{\"Virtual Machines\":[\"10,000\",\"30,000\"],\"Node Count\":[\"1\",\"3\"],\"Log Ingest Rate Per Day In Gbs\":[\"30\",\"75\"],\"Events Per Second\":[\"2,000\",\"5,000\"]},\"additionalInfo\":[\"*Standalone - Master node provisioned by default\",\"*Cluster - Master and two worker nodes provisioned by default\",\"#Refer to Operations-logs Installation Guide\"],\"disasterRecovery\":null}}],\"disasterRecoveryEnabled\":\"false\"}]",
                "_isRedeploy": "false",
                "_isResume": "false",
                "_leverageProximity": "false",
                "__isInstallerRequest": "false",
                "ipv6Gateway": "",
                "ipv6Netmask": "",
                "useIpv4": "",
                "useIpv6": "",
                "useIpv4AndIpv6": ""
                }
            },
            "products": [
                {
                "vmid": None,
                "tenant": "default",
                "version": productVersion,
                "id": productId,
                "productUuid": None,
                "fleetEnabled": True,
                "nodes": [
                    {
                    "type": "vrni-platform",
                    "properties": {
                        "vmName": hostname,
                        "vrniNodeSize": "small",
                        "ip": ipv4Address,
                        "ipPool": "",
                        "additionalVips": ""
                    }
                    },
                   {
                    "type": "vrni-collector",
                    "properties": {
                        "vmName": cHostname,
                        "vrniNodeSize": "small",
                        "ip": cIpv4Address,
                        "ipPool": "",
                        "additionalVips": ""
                    }
                    }
                ],
                "properties": {
                    "authenticationType": "",
                    "certificate": lockerCertId,
                    "contentLibraryItemId:platform": "",
                    "contentLibraryItemId:proxy": "",
                    "productPassword": lockerPasswordId,
                    "licenseRef": "",
                    "ntp": ipv4Gateway,
                    "affinityRule": False,
                    "configureAffinitySeparateAll": "true",
                    "masterVidmEnabled": False,
                    "fipsMode": "true",
                    "monitorWithvROps": "false",
                },
                "references": [],
                "clusterVIP": {
                    "clusterVips": []
                }
                }
            ],
            "metaData": {},
            "requestId": None,
            "fleet": True
        }, indent=4)
    
        file.createFile(f'{productId}.json', payload)

        response = requests.post(url=url, data=payload, headers=headers, verify=verify )       
        response.raise_for_status
        jResponse = response.json()
        
        if debug:
            print(json.dumps(jResponse, indent=4))

        if not (response.status_code < 200 or response.status_code >= 300):
            print(f"INFO: RequestId: {jResponse['requestId']}")
            return jResponse["requestId"]
        else:   
            print(f"INFO: Response Code: {str(response.status_code)}")
            print(json.dumps(jResponse, indent=4))
            raise Exception(f"{jResponse['errorMessage']}")
        
    except requests.exceptions.HTTPError as e:
        print(f"ERROR(HTTP): {e}")
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR(CONNECT): {e}")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"ERROR(TIMEOUT): {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"ERROR(REQUEST): {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    