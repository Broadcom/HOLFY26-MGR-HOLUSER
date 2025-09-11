import re
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import ssl
from pyVmomi import vim
from  pyVim.connect import SmartConnect, Disconnect
import sys

import functions.core_functions as core

debug = False
sslVerify = False

def connect_vCenter(fqdn, username, password, silent=True):
    context = ssl._create_unverified_context()
    try:
        if not silent:
            print(f"INFO: Connecting to {fqdn} with {username}:{password}.")
        vc = SmartConnect(host=fqdn, user=username, pwd=password, port=443, sslContext=context)
    except Exception as e:
        print(f'ERROR: {e}')
        return None
    finally:
        return vc

def connect_host(fqdn, username, password, silent=True):
    context = ssl._create_unverified_context()
    try:
        if not silent:
            print(f"INFO: Connecting to {fqdn} with {username}:{password}.")
        context = ssl._create_unverified_context()
        vc = SmartConnect(host=fqdn, user=username, pwd=password, port=443, sslContext=context)
    except vim.fault.InvalidLogin as e:
        context = ssl._create_unverified_context()
        print(f"ERROR: Invalid login for {username} on {fqdn}.")
        print(f"INFO: Connecting to {fqdn} with {username}:None.")
        vc = SmartConnect(host=fqdn, user=username, pwd=None, port=443, sslContext=context)
    finally:
        return vc

def getVMbyName(fqdn, user, password, name):
    try:
        vc = connect_host(fqdn, user, password)
        content = vc.RetrieveContent()
        listOfVms = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
        
    
        for vm in listOfVms.view:
            if vm.name == name:
                listOfVms.Destroy()
                return vm
        listOfVms.Destroy()
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

def getAllVms(fqdn, username, password):

    try:
        vc = connect_vCenter(fqdn, username, password)
        content = vc.RetrieveContent()

        listOfVms = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
           
        for vm in listOfVms.view:
            print(vm.name)
            listOfVms.Destroy()

        listOfVms.Destroy()
        return None    
    
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    
    finally:
        return None
    

def isShutdown(vm):
    if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOff:
        return True
    else:
        return False

def getVmsByRegex(fqdn, username, password, regex):

    try:
        vc = connect_vCenter(fqdn, username, password)
        content = vc.RetrieveContent()

        pattern = re.compile(regex)

        vmView = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
        listOfVms = vmView.view
        vmView.Destroy()

        regexVms = []
        for vm in listOfVms:
            if pattern.match(vm.name):
                regexVms.append(vm.name)
     
    except Exception as e:
        print(f"REGEX ERROR: {e}")
        sys.exit(1)

    finally:
        return regexVms
def new_vm(fqdn, username, password, vmName, datacenterName, clusterName, vmFolderName, datastoreName, templateName, resourcePoolName=None):
    
    def get_object(content, vimType, name):
        obj = None

        container = content.viewManager.CreateContainerView(content.rootFolder, vimType, True)
        for c in container.view:
            if c.name == name:
                obj = c
                break
        container.Destroy()
        return obj

    try:
        vc = connect_vCenter(fqdn, username, password)
        content = vc.RetrieveContent()

        datacenter = get_object(content, [vim.Datacenter], datacenterName)
        vmFolder = get_object(content, [vim.Folder], vmFolderName) or datacenter.vmFolder
        cluster = get_object(content,  [vim.ClusterComputeResource], clusterName)
        resourcePool = get_object(content, [vim.ResourcePool], resourcePoolName) or cluster.resourcePool
        datastore = get_object(content, [vim.Datastore], datastoreName)
        template = get_object(content, [vim.VirtualMachine], templateName)

        relospec = vim.vm.RelocateSpec()
        relospec.datastore = datastore
        relospec.pool = resourcePool

        # Clone the template
        cloneSpec = vim.vm.CloneSpec()
        cloneSpec.location = relospec
        cloneSpec.powerOn = False
        cloneSpec.template = False

        task = template.Clone(folder=vmFolder, name=vmName, spec=cloneSpec)
        core.countdown(5, 1)
        
        while task.info.state == vim.TaskInfo.State.running:
            print(f"INFO: Cloning VM '{vmName}' from template '{templateName}'...")
            core.countdown(5, 1)

        if task.info.state == vim.TaskInfo.State.success:
            print(f"INFO: VM '{vmName}' created successfully.")
            return getVMbyName(fqdn, username, password, vmName)
        else:
            print(f"ERROR: Failed to create VM '{vmName}': {task.info.error}")
            return None

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

def vmExists(fqdn, username, password, vmName):
    
    try:
        vc = connect_vCenter(fqdn, username, password)
        content = vc.RetrieveContent()
        listOfVms = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)

        for vm in listOfVms.view:
            if (vm.name == vmName):
                listOfVms.Destroy()
                return vm
        
        listOfVms.Destroy()
    
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

def shutdownVm(fqdn, username, password, vm_name):
    try:
        vm = getVMbyName(fqdn, username, password, vm_name)

        if vm is not None:
            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
                print(f"INFO: VMware Tools Status: \'{vm.guest.toolsRunningStatus}\' on {vm.name}.")
                print(f"INFO: Running Guest Shutdown on {vm.name}")
                try:
                    vm.ShutdownGuest()
                    while getVmToolsStatus(vm) != 'guestToolsNotRunning':
                        print(f"INFO: Waiting for Guest Shutdown on {vm.name}")
                        while vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOff:
                            core.countdown(5,1)
                        else:
                            print(f"INFO: {vm.name} is powered off.")   
                except vim.fault.ToolsUnavailable as e:
                    print(f"INFO: Guest Shutdown on {vm.name} Failed. Powering Off")
                    powerOffVm(vm)
            else:
                print(f"INFO: {vm.name} is already powered off.")
        else:
            print(f"INFO: {vm.name} does not exist.")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

def powerOffVm(vm):
    if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
        try:
            task = vm.PowerOffVM_Task()
            while task.info.state == vim.TaskInfo.State.running:
                print(f"INFO: {vm.name} Power Off Task Progress: {task.info.progress if task.info.progress is not None else 'N/A'}%")
                core.countdown(5,1)
            if task.info.state == vim.TaskInfo.State.success:
                print(f"INFO: {vm.name} powered off successfully.")
            else:
                print(f"INFO: {vm.name} : Task failed {task.info.error}")
        except Exception as e:
            print(f"ERROR: {e}")
    else:
        print(f"INFO: VM {vm.name} already powered off.")

def monitorVmToolsStatus(vm, toolStatus):
    while getVmToolsStatus(vm) != toolStatus:
        core.countdown(5,1)
    print(f"INFO: VMware Tools Status: \'{vm.guest.toolsRunningStatus}\' on {vm.name}.")

def getVmToolsStatus(vm):
    print(f"INFO: VMware Tools Status: \'{vm.guest.toolsRunningStatus}\' on {vm.name}.")
    return vm.guest.toolsRunningStatus

def shutdownHost(fqdn, username, password):
    print(f"INFO: Shutting down {fqdn}...")

    try:
        if (core.isReachable(fqdn)):
            esx = connect_host(fqdn, username, password)
            content = esx.RetrieveContent()
            host = content.rootFolder.childEntity[0].hostFolder.childEntity[0].host[0]
        
            task = host.ShutdownHost_Task(force=True)
            while task.info.state == vim.TaskInfo.State.running:
                print(f"INFO: {host.name} Power Off Task Progress: {task.info.progress if task.info.progress is not None else 'N/A'}%")
                core.countdown(5,1)
            if task.info.state == vim.TaskInfo.State.success:
                print(f"INFO: {host.name} powered off successfully.")
            else:
                print(f"INFO: {host.name} : Task failed {task.info.error}")
        else:
            print(f"INFO: {fqdn} is not reachable.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

def shutdownWcp(fqdn, username, password):
    print(f"INFO: Stopping WCP on {fqdn}...")

    try:
        if (core.isReachable(fqdn)):
            core.runRemoteSshCmd(fqdn, username, password, 'vmon-cli -k wcp', hostCheck='no')
        else:
            print(f"INFO: {fqdn} is not reachable.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)