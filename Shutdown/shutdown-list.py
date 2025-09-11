########################################################################################################################################
##
## Title: VCF Single Site Shutdown Script                                                                                                                               
## Author: Christopher Lewis
## Version: 26.6.0
## Date: 23/07/2025
##
########################################################################################################################################
## Version 26.6.0
## Updated Hostlist to only add ESX hosts that are reachable.
## Added optional docker shutdown
## Added str(i).zfill(2) to HostList to cater for esx{01-10}a
########################################################################################################################################
## Version 26.5.0
## Added Docker Shutdown for Docker services.
## Renamed some functions to be shutdown_
########################################################################################################################################
## Version 26.4.0
## Added Remote Shutdown of WCP in the shutdown_Management function.
## Updated update_ShutdownList function to cycle through VMs first rather than hosts to ensure correct shutdown order.
########################################################################################################################################
## Version 26.3.0
## Added Sections to the script so that they can be disabled for troubleshooting failures (or using with VVF).
########################################################################################################################################
## Version 26.2.0
## Added Dynamic selection of VCF-A naming in vcenter so its not hardcoded.
## Updated update_ShutdownList function to cycle through VMs first rather than hosts to ensure correct shutdown order.
########################################################################################################################################

import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import time

import functions.file_functions as file
import functions.vm_functions as vmf
import functions.fleet_functions as fleet
import functions.core_functions as core

## CONSTANTS

debug = False
sslVerify = False
vSanTimeout = 2700

## FUNCTIONS

def update_ShutdownList(shutdownList, vmList, hostList):

    if len(vmList) > 0 :

        try:
            print(f"INFO: Adding {vmList} Virtual Machines to Shutdown List.")

            for vmName in vmList:

                for host in hostList:
                    if core.isReachable(host):
                        username = hostList[host]['config']['username']
                        password = hostList[host]['config']['password']
                    
                        vm = vmf.vmExists(host, username, password, vmName)
                        if vm:
                            jTemp = {
                                vm.name : {
                                    'config': {
                                        'host' : host,
                                        'username' : esxUsername,
                                        'password' : esxPassword
                                    }
                                }
                            }
                            shutdownList.update(jTemp)
                        else:
                            continue
        except Exception as e:
            print(f"ERROR: {e}")

        finally:
            return shutdownList

def shutdown_Management():
    try:
        token = fleet.getEncodedToken(lcmUsername, lcmPassword)

        if debug:
            print(token)
            print(json.dumps(fleet.getAllEnvironments(lcmFqdn, token, sslVerify), indent=4))
        print(f"TASK: Shut Cloud Management via Fleet Management.")

        envList = fleet.getAllEnvironments(lcmFqdn, token, sslVerify)

        shutdownEnv = ["vra","vrni"]

        # SYNCHRONIZE INVENTORY ALL ENVIRONMENTS IN FLEET MANAGEMENT

        for env in envList:
            productIds = envList[env]['products']
            fleet.triggerInventorySync(lcmFqdn, token, sslVerify, env, productIds)

        # SHUTDOWN VMS IN ENVIRONMENTS

        for product in shutdownEnv:
            for env, details in envList.items():
                if product in details.get("products", []):
                    fleet.triggerPowerEvent(lcmFqdn, token, sslVerify, env, product, "power-off")
                    break
    except Exception as e:
        print(f"ERROR: {e}")

def build_ShutdownList(shutdownList, hostList):

    try:
        print(f"TASK: Building a VM/Host Shutdown List")
        print("INFO: Add VMs to Shutdown List - STARTED")
        # ADD WORKLOAD VMS TO SHUTDOWN LIST
        shutdownList = update_ShutdownList(shutdownList, vcfWldList, hostList)

        # ADD WORKLOAD VCLI & K8S NODES VMS TO SHUTDOWN LIST
        if (core.isReachable(wldVcFqdn)):
            for pattern in patterns:
                wldRegexList = vmf.getVmsByRegex(wldVcFqdn, wldVcUsername, wldVcPassword, pattern)
                if wldRegexList:
                    shutdownList = update_ShutdownList(shutdownList, wldRegexList, hostList)
        else:
            print(f"ERROR: Unable to connect to {wldVcFqdn}.")
        
        # ADD MANAGEMENT VCLI & K8S NODES VMS TO SHUTDOWN LIST
        if (core.isReachable(mgmtVcFqdn)):
            for pattern in patterns:
                mgmtRegexList = vmf.getVmsByRegex(mgmtVcFqdn, mgmtVcUsername, mgmtVcPassword, pattern)
                if mgmtRegexList:
                    shutdownList = update_ShutdownList(shutdownList, mgmtRegexList, hostList)
        else:
            print(f"ERROR: Unable to connect to {mgmtVcFqdn}.")

        # ADD MGMT & NSX VMS TO SHUTDOWN LIST
        shutdownList = update_ShutdownList(shutdownList, vcfMgmtList, hostList)
        shutdownList = update_ShutdownList(shutdownList, vcfList, hostList)
        shutdownList = update_ShutdownList(shutdownList, vksList, hostList)
        shutdownList = update_ShutdownList(shutdownList, vcfNsxList, hostList)
        
        if len(shutdownList) > 0:
            print(f"TASK: Building a VM/Host Shutdown List - COMPLETED")
            file.createFile("shutdown.json", json.dumps(shutdownList, indent=4))
        else:
            raise SystemExit(f"ERROR: Shutdown List is empty.")

        if debug:
            print(json.dumps(shutdownList, indent=4))
    
    except Exception as e:
        print(f"ERROR: {e}")

    finally:
        print("INFO: Shutdown List - COMPLETE")
        return shutdownList

def shutdown_Vms(shutdownList):
    print("TASK: Shutdown VMs")
    print("INFO: VM Shutdown Process - STARTED")
    
    # SHUTDOWN VMS IN SHUTDOWN LIST
    try:
        if len(shutdownList) > 0 :
            for vm in shutdownList:
                user = shutdownList[vm]['config']['username']
                password = shutdownList[vm]['config']['password']
                host = shutdownList[vm]['config']['host']

                print(f"TASK: Shutting Down {vm} on {host}.")
                
                vmf.shutdownVm(host, user, password, vm)
                core.countdown(5,1)

    except Exception as e:
        print(f"ERROR: {e}")

    print("INFO: VM Shutdown Process - COMPLETED")

def shutdown_Vsan(hostList):
    print("INFO: vSAN Shutdown Process - STARTED")
    # RUN VSISH CMD ON HOSTS IN HOST LIST
    try:
        if len(hostList) > 0:
            for host in hostList:
                username = hostList[host]['config']['username']
                password = hostList[host]['config']['password']
                print(f"TASK: Running VSISH Command on '{host}'.")
                core.runRemoteSshCmd(host, username, password, "yes | vsish -e set /config/LSOM/intOpts/plogRunElevator 1")

            print(f"INFO: Waiting for {vSanTimeout/60} mins for VSAN I/O to stop...")
            core.countdown(vSanTimeout, 60)
            
            for host in hostList:
                username = hostList[host]['config']['username']
                password = hostList[host]['config']['password']
                print(f"TASK: Running VSISH Command on '{host}'.")
                core.runRemoteSshCmd(host, username, password, "yes | vsish -e set /config/LSOM/intOpts/plogRunElevator 0")

    except Exception as e:
        print(f"ERROR: {e}")

    finally:
        print("INFO: vSAN Shutdown Process - COMPLETED")


def shutdown_Hosts(hostList):
    print("INFO: Host Shutdown Process - STARTED")
    # SHUTDOWN HOSTS IN HOST LIST

    try:
        if len(hostList) > 0:
            print("TASK: HOST Shutdown Process - STARTED")
            for host in hostList:
                username = hostList[host]['config']['username']
                password = hostList[host]['config']['password']
                vmf.shutdownHost(host, username, password)
        else:
            print("INFO: No Hosts in Host List.")
    
    except Exception as e:
        print(f"ERROR: {e}")

    finally:
        print("INFO: Host Shutdown Process - COMPLETED")

def shutdown_Docker(dockerHost, username, password, dockerContainerList):
    print("INFO: Docker Container Shutdown Process - STARTED")

    try:
        if core.isReachable(dockerHost, port=22):
            if len(dockerContainerList) > 0:
                for container in dockerContainerList:
                    print(f"TASK: Running 'Docker Stop {container}'.")
                    core.runRemoteSshCmd(dockerHost, username, password, f"docker stop {container}")
            else:
                print(f"INFO: No containers in the list")
        else:
            print(f"INFO: Docker Host '{dockerHost} is not available")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        print("INFO: Docker Container Shutdown Process - STARTED")

## VARIABLES

pwdFile = '/home/holuser/Desktop/PASSWORD.txt'

mgmtVcFqdn = 'vc-mgmt-a.site-a.vcf.lab'
mgmtVcUsername = 'administrator@vsphere.local'
mgmtVcPassword = file.readFile(pwdFile)

wldVcFqdn = 'vc-wld01-a.site-a.vcf.lab'
wldVcUsername = 'administrator@wld.sso'
wldVcPassword = file.readFile(pwdFile)

wld2VcFqdn = 'vc-wld02-a.site-a.vcf.lab'
wld2VcUsername = 'administrator@wld02.sso'
wld2VcPassword = file.readFile(pwdFile)

dockerHost = "docker.site-a.vcf.lab"
dockerUsername = "holuser"
dockerPassword = file.readFile(pwdFile)

esxUsername = 'root'
esxPassword = file.readFile(pwdFile)

lcmFqdn = 'opslcm-a.site-a.vcf.lab'
lcmUsername = 'admin@local'
lcmPassword = file.readFile(pwdFile)

patterns = [
    "^([{]?dev-project-{1}[}]?)([{]?[0-9a-zA-Z]{5}-[0-9a-zA-Z]{5}[}]?$)",
    "^([{]?dev-project-worker-{1}[}]?)([{]?[0-9a-zA-Z]{5}-[0-9a-zA-Z]{8,}-[0-9a-zA-Z]{5}[}]?$)",
    "^([{]?cci-service-{1}[}]?)([{]?[0-9a-z]{10}-[0-9a-z]{5}[}]?$)",
    "^([{]?cci-service-{1}[}]?)([{]?[0-9a-z]{10}-[0-9a-z]{5}[}]?$)",
    "^([{]?vCLS-{1}[}]?)([{]?[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}[}]?$)"
]

vksPatterns = [
    "^([{]?kubernetes-cluster-{1}[}]?)([{]?[0-9a-z]{1}-[0-9a-z]{10}(-[0-9a-z]{5}){2}[}]?$)",
    "^([{]?kubernetes-cluster-{1}[}]?)([{]?[0-9a-z]{1}-[0-9a-z]{10}-([{]?kubernetes-cluster-{1}[}]?)([0-9a-z]{4}-[0-9a-z]{7})[}]?$)"
]

if (core.isReachable(mgmtVcFqdn)):
    autoVms = vmf.getVmsByRegex(mgmtVcFqdn, mgmtVcUsername, mgmtVcPassword, "^([{]?auto-{1}[}]?)([{]?[0-9a-zA-Z]-{1}|[0-9a-zA-Z]-{3}[}]?)([{]?[0-9a-zA-Z]{5}[}]?$)")
    vcfMgmtList = ['o11n-02a','o11n-01a','opslogs-01a','ops-01a','ops-a','opscollector-01a','opsproxy-01a','opslcm-01a', 'opsnet-a', 'opsnet-01a', 'opsnetcollector-01a', 'opslcm-a']
    vcfMgmtList = [*autoVms, *vcfMgmtList]

vcfList = ['sddcmanager-a']
vcList = ['vc-wld02-a','vc-wld01-a','vc-mgmt-a']
vcfList = [*vcfList, *vcList]

vksList = ['SupervisorControlPlaneVM (1)']
vcfNsxList = ['edge-wld01-01a','edge-wld01-02a','edge-wld02-01a','edge-wld02-02a','nsx-mgmt-01a', 'nsx-wld02-01a', 'nsx-wld01-01a']
vcfWlds = ['core-a','core-b','hol-ubuntu-001','hol-snapshot-001','linux-dev-0010','linux-dev-0011']
vcfWldList = []

containerList=['gitlab','ldap','poste.io','flask']

if (core.isReachable(wldVcFqdn)):
    for pattern in vksPatterns:
        tmpList = vmf.getVmsByRegex(wldVcFqdn, wldVcUsername, wldVcPassword, pattern)
        vcfWldList = [*vcfWldList,*tmpList]

if (core.isReachable(wld2VcFqdn)):
    for pattern in vksPatterns:
        tmpList = vmf.getVmsByRegex(wld2VcFqdn, wld2VcUsername, wld2VcPassword, pattern)
        vcfWldList = [*vcfWldList,*tmpList]


vcfWldList = [*vcfWldList, *vcfWlds]

hostList = {
    f'esx-{str(i).zfill(2)}a.site-a.vcf.lab': 
    {
        'config': {
            'username': esxUsername,
            'password': esxPassword
        }
    }
    for i in range(1, 11)
    if core.isReachable(f'esx-{str(i).zfill(2)}a.site-a.vcf.lab')
}

print(f'INFO: There are {len(hostList)} in the Host List')

## MAIN

try:
    shutdownList = {}
    start = time.time()
    print(f"START: {time.strftime('%H:%M:%S', time.localtime(start))}")
    
    #shutdown_Docker(dockerHost, dockerUsername, dockerPassword, containerList)
    # shutdown_Management()
    shutdownList = build_ShutdownList(shutdownList, hostList)
    # vmf.shutdownWcp(mgmtVcFqdn, "root", mgmtVcPassword)
    # vmf.shutdownWcp(wldVcFqdn, "root", wldVcPassword)
    # vmf.shutdownWcp(wld2VcFqdn, "root", wld2VcPassword)
    # shutdown_Vms(shutdownList)
    # shutdown_Vsan(hostList)
    # shutdown_Hosts(hostList)

except Exception as e:
    print(f"ERROR: {e}")

finally:
    finish = time.time()
    print(f"END: {time.strftime('%H:%M:%S', time.localtime(finish))}")

    elapsed = finish - start
    print(f"ELAPSED: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")