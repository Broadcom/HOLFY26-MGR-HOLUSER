# vSphere.py version 1.12 18-November 2024
import datetime
import os
import sys
from pyVim import connect
from pyVmomi import vim
import logging
import lsfunctions as lsf

# default logging level is WARNING (other levels are DEBUG, INFO, ERROR and CRITICAL)
logging.basicConfig(level=logging.WARNING)

# default logging level is WARNING (other levels are DEBUG, INFO, ERROR and CRITICAL)
logging.basicConfig(level=logging.DEBUG)

# read the /hol/config.ini
lsf.init(router=False)

color = 'red'
if len(sys.argv) > 1:
    lsf.start_time = datetime.datetime.now() - datetime.timedelta(seconds=int(sys.argv[1]))
    if sys.argv[2] == "True":
        lsf.labcheck = True
        color = 'green'
        lsf.write_output(f'{sys.argv[0]}: labcheck is {lsf.labcheck}')   
    else:
        lsf.labcheck = False
 
lsf.write_output(f'Running {sys.argv[0]}')

###
# connect to all vCenters
# this could be an ESXi host
vcenters = []
if 'vCenters' in lsf.config['RESOURCES'].keys():
    vcenters = lsf.config.get('RESOURCES', 'vCenters').split('\n')

if vcenters:
    lsf.write_vpodprogress('Connecting vCenters', 'GOOD-3', color=color)
    lsf.connect_vcenters(vcenters)

###
# check Datastores
if vcenters:
    lsf.write_output('Checking Datastores')
    lsf.write_vpodprogress('Checking Datastores', 'GOOD-3', color=color)
    datastores = []
    if 'Datastores' in lsf.config['RESOURCES'].keys():
        datastores = lsf.config.get('RESOURCES', 'Datastores').split('\n')
    for entry in datastores:
        while True:
            try:
                if lsf.check_datastore(entry):
                    break
            except Exception as e:
                lsf.write_output(f'Unable to check datastores. Will try again. {e}')
            lsf.labstartup_sleep(lsf.sleep_seconds)

###
# ESXi hosts must exit maintenance mode
esx_hosts = []
if 'ESXiHosts' in lsf.config['RESOURCES'].keys():
    esx_hosts = lsf.config.get('RESOURCES', 'ESXiHosts').split('\n')

for entry in esx_hosts:
    (host, mm) = entry.split(':')
    if mm == 'yes':
        lsf.mm += f'{host}:'  # do not take this host out of MM

if vcenters:
    while not lsf.check_maintenance():
        lsf.write_vpodprogress('Exit Maintenance', 'GOOD-3', color=color)
        lsf.write_output('Taking ESXi hosts out of Maintenance Mode...')
        lsf.exit_maintenance()

###
# verify the vcls VMs have started
vcls_vms = 0
if vcenters:
    vms = lsf.get_all_vms()
    for vm in vms:
        if "vCLS" in vm.name:
            vcls_vms = vcls_vms + 1
            while not vm.runtime.powerState == "poweredOn":
                lsf.write_output(f'Waiting for {vm.name} to power on...')
                lsf.labstartup_sleep(lsf.sleep_seconds)
    if vcls_vms > 0:
        lsf.write_output('All vCLS VMs have started...')

###
# wait for DRS to enable per Clusters.txt
drsclusters = ''
clusterlist = []
if 'Clusters' in lsf.config['RESOURCES'].keys():
    clusterlist = lsf.config.get('RESOURCES', 'Clusters').split('\n')
for entry in clusterlist:
    drsconfig = entry.split(':')
    if drsconfig[1] == 'on':
        drsclusters += drsconfig[0] + ':'
if vcenters:
    clusters = lsf.get_all_clusters()
    for cluster in clusters:
        if cluster.name not in drsclusters:
            continue
        while not cluster.configuration.drsConfig.enabled:
            lsf.write_output(f'Waiting for DRS to enable on {cluster.name}...')
            lsf.labstartup_sleep(lsf.sleep_seconds)
    lsf.write_output('DRS is configured on all clusters per the config.ini.')

if vcenters:
    lsf.write_vpodprogress('ESXi exit MM', 'GOOD-3', color=color)
    while not lsf.check_maintenance():
        lsf.write_output('Waiting for ESXi hosts to exit Maintenance Mode...')
        lsf.labstartup_sleep(lsf.sleep_seconds)
    lsf.write_output('All ESXi hosts are out of Maintenance Mode.')

# Suppress shell warning for all ESXi hosts
if vcenters:
    esxhosts = lsf.get_all_hosts()
    for host in esxhosts:
        try:
            option_manager = host.configManager.advancedOption
            option = vim.option.OptionValue(key="UserVars.SuppressShellWarning",
                                            value=1)
            lsf.write_output(f'Suppressing shell warning on ESXi host {host.name}')
            if option_manager.UpdateOptions(changedValue=[option]):
                lsf.write_output("Success.")
        except Exception as e:
            lsf.write_output(f'{host.name} Exception : {e}')

##############################################################################
#      Lab Startup - STEP #2 (Starting Nested VMs and vApps)
##############################################################################

###
# Use the Start-Nested function to start batches of nested VMs and/or vApps
# Create additional arrays for each batch of VMs and/or vApps
# Insert a LabStartup-Sleep as needed if a pause is desired between batches
# Or include additional tests for services after each batch and before the next batch

if vcenters:
    # wait for vCenter to be ready
    lsf.write_output('Checking vCenter readiness...')
    lsf.write_vpodprogress('Checking vCenter', 'GOOD-3', color=color)
    vc_urls = []
    for entry in vcenters:
        vc = entry.split(':', 1)[0]
        vc_urls.append(f'https://{vc}/ui/')
    for url in vc_urls:
        while not lsf.test_url(url, pattern='loading-container', timeout=2):
            lsf.write_output(f'Sleeping and will try again...')
            lsf.labstartup_sleep(lsf.sleep_seconds)
    
    lsf.write_vpodprogress('Starting vVMs', 'GOOD-4', color=color)
    lsf.write_output('Starting vVMs')
    vms = []
    if 'VMs' in lsf.config['RESOURCES'].keys():
        vms = lsf.config.get('RESOURCES', 'VMs').split('\n')
    while True:
        try:
            lsf.start_nested(vms)
            break
        except Exception as e:
            lsf.write_output('Unable to start vVMs. Will try again.')
        lsf.labstartup_sleep(lsf.sleep_seconds)

    
    vapps = []
    lsf.write_output('Starting vApps')
    if 'vApps' in lsf.config['RESOURCES'].keys():
        vapps = lsf.config.get('RESOURCES', 'vApps').split('\n')
        # vapps = lsf.read_file_into_list('vApps', wait=False)
    while True:
        try:
            lsf.start_nested(vapps)
            break
        except Exception as e:
            lsf.write_output('Unable to start vApps. Will try again.')
        lsf.labstartup_sleep(lsf.sleep_seconds)

if vcenters:
    lsf.write_output('Clearing host connection and power state alerts')
    # clear the bogus alarms
if vcenters:
    lsf.clear_host_alarms()

###
# Disconnect from vCenters
# Do not do this here if you need to perform other actions within vCenter
#  in that case, move this block later in the script. Need help? Please ask!

if vcenters:
    lsf.write_output('Disconnecting vCenters...')
    for si in lsf.sis:
        # print ("disconnect", si) # will need to build a hash at connect time to disconnect a specific si
        # inspect.getsource(si)
        connect.Disconnect(si)
