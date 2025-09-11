
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

        shutdownEnv = ["vra", "vrni"]

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

def set_AdvancedHostSettings(hostList):
    print("INFO: Setting Advanced Host Settings - STARTED")
    # RUN VSISH CMD ON HOSTS IN HOST LIST
    try:
        if len(hostList) > 0:
            for host in hostList:
                username = hostList[host]['config']['username']
                password = hostList[host]['config']['password']
                print(f"TASK: Running VSISH Command on '{host}'.")
                if core.isReachable(host, port=22):
                    core.runRemoteSshCmd(host, username, password, "esxcli system settings advanced set -o /Mem/AllocGuestLargePage -i 1")
                else:
                    print(f"INFO: Host '{host}' is not reachable.")
    except Exception as e:
        print(f"ERROR: {e}")

    finally:
        print("INFO: Advanced Host Settings - COMPLETED")


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
        print("INFO: Docker Container Shutdown Process - COMPLETED")
