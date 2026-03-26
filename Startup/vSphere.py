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
            lsf.write_output('Still powering on vVMs. Will try again.')
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

if lsf.labtype != 'HOL':
    #==========================================================================
    # TASK: Ensure SSH and bash shell are enabled on vCenters
    # The autostart services check (TASK 7) requires SSH access to each
    # vCenter. On fresh lab environments that haven't had confighol run,
    # SSH may be disabled and the root shell may be the VAMI appliance
    # shell instead of bash. Use the vCenter REST API to enable SSH and
    # set the shell, then verify SSH connectivity.
    #==========================================================================
    import time as _time_ssh
    import requests
    
    lsf.write_output('Ensuring SSH and bash shell are enabled on vCenters...')
    
    for entry in vcenters:
        if not entry or entry.strip().startswith('#'):
            continue
        
        parts = entry.split(':')
        vc_hostname = parts[0].strip()
        vc_user = parts[2].strip() if len(parts) > 2 else 'administrator@vsphere.local'
        
        try:
            session = requests.Session()
            session.trust_env = False
            
            # Get API session token
            session_resp = session.post(
                f'https://{vc_hostname}/api/session',
                auth=(vc_user, lsf.password),
                verify=False, timeout=15, proxies=None
            )
            if session_resp.status_code not in (200, 201):
                lsf.write_output(f'  {vc_hostname}: Could not get API session (HTTP {session_resp.status_code}), skipping SSH/shell check')
                continue
            
            api_token = session_resp.text.strip().strip('"')
            api_headers = {'vmware-api-session-id': api_token}
            
            # Check and enable SSH
            ssh_resp = session.get(
                f'https://{vc_hostname}/api/appliance/access/ssh',
                headers=api_headers, verify=False, timeout=15, proxies=None
            )
            ssh_enabled = False
            if ssh_resp.status_code == 200:
                ssh_enabled = ssh_resp.json() is True or ssh_resp.json() == True
            
            if not ssh_enabled:
                lsf.write_output(f'  {vc_hostname}: SSH not enabled - enabling via REST API...')
                enable_resp = session.put(
                    f'https://{vc_hostname}/api/appliance/access/ssh',
                    headers=api_headers, json=True,
                    verify=False, timeout=15, proxies=None
                )
                if enable_resp.status_code in [200, 204]:
                    lsf.write_output(f'  {vc_hostname}: SSH enabled successfully')
                else:
                    lsf.write_output(f'  {vc_hostname}: WARNING - Failed to enable SSH (HTTP {enable_resp.status_code})')
            else:
                lsf.write_output(f'  {vc_hostname}: SSH already enabled')
            
            # Check and enable bash shell
            shell_resp = session.get(
                f'https://{vc_hostname}/api/appliance/access/shell',
                headers=api_headers, verify=False, timeout=15, proxies=None
            )
            shell_enabled = False
            if shell_resp.status_code == 200:
                shell_data = shell_resp.json()
                if isinstance(shell_data, dict):
                    shell_enabled = shell_data.get('enabled', False)
                else:
                    shell_enabled = shell_data is True or shell_data == True
            
            if not shell_enabled:
                lsf.write_output(f'  {vc_hostname}: Bash shell not enabled - enabling via REST API...')
                shell_enable_resp = session.put(
                    f'https://{vc_hostname}/api/appliance/access/shell',
                    headers=api_headers,
                    json={'enabled': True, 'timeout': 0},
                    verify=False, timeout=15, proxies=None
                )
                if shell_enable_resp.status_code in [200, 204]:
                    lsf.write_output(f'  {vc_hostname}: Bash shell enabled successfully')
                else:
                    lsf.write_output(f'  {vc_hostname}: WARNING - Failed to enable bash shell (HTTP {shell_enable_resp.status_code})')
            else:
                lsf.write_output(f'  {vc_hostname}: Bash shell already enabled')
            
            # Also ensure root user has /bin/bash as shell via SSH
            # (the REST API enables shell access but may not change the login shell)
            if lsf.test_tcp_port(vc_hostname, 22, timeout=5):
                chsh_result = lsf.ssh('chsh -s /bin/bash root 2>/dev/null; echo OK',f'root@{vc_hostname}',lsf.password)
                if hasattr(chsh_result, 'stdout') and 'OK' in chsh_result.stdout:
                    lsf.write_output(f'  {vc_hostname}: Root shell set to /bin/bash')
                else:
                    lsf.write_output(f'  {vc_hostname}: Note - chsh not available (shell may already be bash)')
            
            # Delete the API session
            session.delete(f'https://{vc_hostname}/api/session',
                           headers=api_headers, verify=False, timeout=10, proxies=None)
            
        except Exception as e:
            lsf.write_output(f'  {vc_hostname}: WARNING - SSH/shell enablement check failed: {e}')

if lsf.labtype != 'HOL':
    #==========================================================================
    # TASK: Verify all Autostart vCenter services are Started
    # Some services configured for AUTOMATIC startup fail to start during
    # vCenter boot (e.g. vapi-endpoint, trustmanagement). Check each vCenter
    # and start any AUTOMATIC services that are not in STARTED state.
    #==========================================================================
    import time as _time

    autostart_total = 0
    autostart_started = 0
    autostart_fixed = 0
    autostart_failed = 0

    lsf.write_output('Verifying vCenter autostart services...')

    AUTOSTART_START_TIMEOUT = 60
    AUTOSTART_CHECK_INTERVAL = 10

    for entry in vcenters:
        if not entry or entry.strip().startswith('#'):
            continue

        vc_hostname = entry.split(':')[0].strip()
        lsf.write_output(f'Checking autostart services on {vc_hostname}...')

        ssh_opts = '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
        check_cmd = (
            f"{lsf.sshpass} -p {lsf.password} ssh {ssh_opts} root@{vc_hostname} "
            "'for svc in $(vmon-cli --list 2>/dev/null); do "
            'info=$(vmon-cli -s $svc 2>/dev/null); '
            'starttype=$(echo "$info" | grep "Starttype:" | head -1 | sed "s/.*Starttype: //"); '
            'if [ "$starttype" = "AUTOMATIC" ]; then '
            'state=$(echo "$info" | grep "RunState:" | head -1 | sed "s/.*RunState: //"); '
            'echo "$svc:$state"; '
            "fi; done'"
        )

        result = lsf.run_command(check_cmd)

        if not hasattr(result, 'stdout') or not result.stdout:
            lsf.write_output(f'  WARNING: Could not query services on {vc_hostname}')
            autostart_failed += 1
            continue

        not_started = []
        vc_service_count = 0

        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if ':' not in line:
                continue

            svc_name, svc_state = line.split(':', 1)
            svc_name = svc_name.strip()
            svc_state = svc_state.strip()
            vc_service_count += 1

            if svc_state == 'STARTED':
                autostart_started += 1
            else:
                not_started.append((svc_name, svc_state))

        autostart_total += vc_service_count

        if not not_started:
            lsf.write_output(f'  All {vc_service_count} autostart services on {vc_hostname} are running')
            continue

        lsf.write_output(f'  Found {len(not_started)} autostart service(s) not started on {vc_hostname}:')
        for svc_name, svc_state in not_started:
            lsf.write_output(f'    {svc_name}: {svc_state} - starting...')

            start_result = lsf.ssh(f'vmon-cli --start {svc_name} 2>&1', f'root@{vc_hostname}', lsf.password)

            started = False
            wait_start = _time.time()
            while (_time.time() - wait_start) < AUTOSTART_START_TIMEOUT:
                verify_result = lsf.ssh(
                    f"vmon-cli -s {svc_name} 2>/dev/null | grep 'RunState:' | head -1 | sed 's/.*RunState: //'",
                    f'root@{vc_hostname}', lsf.password
                )
                if hasattr(verify_result, 'stdout') and verify_result.stdout.strip() == 'STARTED':
                    started = True
                    break
                _time.sleep(AUTOSTART_CHECK_INTERVAL)

            if started:
                lsf.write_output(f'    {svc_name}: Started successfully')
                autostart_started += 1
                autostart_fixed += 1
            else:
                lsf.write_output(f'    WARNING: {svc_name} did not start within {AUTOSTART_START_TIMEOUT}s')
                autostart_failed += 1

    if autostart_fixed > 0:
        lsf.write_output(f'Autostart services check complete: {autostart_fixed} service(s) were started')
    elif autostart_failed > 0:
        lsf.write_output(f'Autostart services check complete: {autostart_failed} service(s) failed to start')
    else:
        lsf.write_output('All autostart services are running on all vCenters')
