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
    #
    # vCenter 9.x uses the VAMI appliance shell as root's login shell and a
    # PAM module (pam_mgmt_cli.so) that intercepts SSH auth with its own
    # password prompt.  Both prevent sshpass-based remote commands.
    #
    # Fix via pyVmomi Guest Operations (VMware Tools) on ESXi hosts:
    #   1. Set root login shell to /bin/bash   (usermod)
    #   2. Remove pam_mgmt_cli.so from /etc/pam.d/sshd
    #   3. Reset pam_faillock counters
    # Then enable SSH + shell access via the vCenter REST API.
    #==========================================================================
    import time as _time_ssh
    import subprocess as _subprocess_ssh
    import requests
    import ssl as _ssl_ssh
    import urllib.request as _urlreq

    lsf.write_output('Ensuring SSH and bash shell are enabled on vCenters...')

    _PAM_SSHD_CLEAN = (
        '# Begin /etc/pam.d/sshd\n'
        '\n'
        'auth            include         system-auth\n'
        'account         include         system-account\n'
        'password        include         system-password\n'
        'session         include         system-session\n'
        '\n'
        '# End /etc/pam.d/sshd\n'
    )

    def _find_vc_vm_on_esxi(vc_name, esxi_hosts, esxi_password):
        """Search ESXi hosts for a vCenter VM and return (si, vm, esxi_host)."""
        for esxi_entry in esxi_hosts:
            esxi_host = esxi_entry.split(':')[0].strip()
            if not esxi_host or esxi_host.startswith('#'):
                continue
            try:
                si = connect.SmartConnect(
                    host=esxi_host, user='root', pwd=esxi_password,
                    disableSslCertValidation=True
                )
                content = si.RetrieveContent()
                container = content.viewManager.CreateContainerView(
                    content.rootFolder, [vim.VirtualMachine], True
                )
                for vm in container.view:
                    if vc_name in vm.name and vm.runtime.powerState == 'poweredOn':
                        tools_ok = vm.guest.toolsRunningStatus == 'guestToolsRunning'
                        if tools_ok:
                            container.Destroy()
                            return si, vm, esxi_host
                container.Destroy()
                connect.Disconnect(si)
            except Exception:
                pass
        return None, None, None

    def _guest_run(pm, vm, auth, prog, args, wait=2):
        """Run a program inside a VM via Guest Operations and return exit code."""
        spec = vim.vm.guest.ProcessManager.ProgramSpec(
            programPath=prog, arguments=args
        )
        pid = pm.StartProgramInGuest(vm, auth, spec)
        _time_ssh.sleep(wait)
        procs = pm.ListProcessesInGuest(vm, auth, pids=[pid])
        return procs[0].exitCode if procs else -1

    def _guest_read(fm, vm, auth, path, esxi_host):
        """Read a file from inside a VM via Guest Operations."""
        ctx = _ssl_ssh.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl_ssh.CERT_NONE
        fti = fm.InitiateFileTransferFromGuest(vm, auth, path)
        url = fti.url.replace('*', esxi_host)
        resp = _urlreq.urlopen(url, context=ctx)
        return resp.read().decode()

    def _get_vc_root_passwords():
        """Query SDDC Manager for actual vCenter root passwords."""
        pw_map = {}
        try:
            tok_resp = requests.post(
                'https://sddcmanager-a.site-a.vcf.lab/v1/tokens',
                json={'username': 'admin@local', 'password': lsf.password},
                verify=False, timeout=15
            )
            if tok_resp.status_code in (200, 201):
                token = tok_resp.json().get('accessToken', '')
                cred_resp = requests.get(
                    'https://sddcmanager-a.site-a.vcf.lab/v1/credentials?resourceType=VCENTER',
                    headers={'Authorization': f'Bearer {token}'},
                    verify=False, timeout=15
                )
                if cred_resp.status_code == 200:
                    for elem in cred_resp.json().get('elements', []):
                        if elem.get('username') == 'root':
                            rn = elem.get('resource', {}).get('resourceName', '')
                            pw_map[rn] = elem.get('password', lsf.password)
        except Exception:
            pass
        return pw_map

    vc_root_passwords = _get_vc_root_passwords()

    for entry in vcenters:
        if not entry or entry.strip().startswith('#'):
            continue

        parts = entry.split(':')
        vc_hostname = parts[0].strip()
        vc_user = parts[2].strip() if len(parts) > 2 else 'administrator@vsphere.local'
        vc_short = vc_hostname.split('.')[0]

        # --- Phase 1: Fix login shell and PAM via Guest Operations ---
        lsf.write_output(f'  {vc_hostname}: Configuring bash shell via Guest Operations...')
        si_esx, vc_vm, esxi_host = _find_vc_vm_on_esxi(vc_short, esx_hosts, lsf.password)

        if vc_vm:
            gom = si_esx.RetrieveContent().guestOperationsManager
            pm = gom.processManager
            fm = gom.fileManager

            root_pw = vc_root_passwords.get(vc_hostname, lsf.password)
            guest_auth = None
            for pw_candidate in [root_pw, lsf.password]:
                try:
                    test_auth = vim.vm.guest.NamePasswordAuthentication(
                        username='root', password=pw_candidate
                    )
                    pm.ListProcessesInGuest(vc_vm, test_auth, pids=[])
                    guest_auth = test_auth
                    break
                except Exception:
                    continue

            if guest_auth:
                rc = _guest_run(pm, vc_vm, guest_auth,
                                '/usr/sbin/usermod', '-s /bin/bash root')
                lsf.write_output(f'  {vc_hostname}: usermod -s /bin/bash root → rc={rc}')

                _guest_run(pm, vc_vm, guest_auth, '/bin/bash',
                           '-c "cp /etc/pam.d/sshd /etc/pam.d/sshd.bak 2>/dev/null; true"')

                write_pam_args = (
                    "-c \"cat > /etc/pam.d/sshd << 'PAMEOF'\n"
                    + _PAM_SSHD_CLEAN
                    + "PAMEOF\n\""
                )
                rc2 = _guest_run(pm, vc_vm, guest_auth, '/bin/bash', write_pam_args)
                lsf.write_output(f'  {vc_hostname}: PAM sshd fix → rc={rc2}')

                _guest_run(pm, vc_vm, guest_auth, '/bin/bash',
                           '-c "faillock --user root --reset 2>/dev/null; true"')

                _guest_run(pm, vc_vm, guest_auth, '/bin/bash',
                           '-c "chage -I -1 -m 0 -M 99999 -E -1 root 2>/dev/null; true"')

                if root_pw != lsf.password:
                    rc_pw = _guest_run(pm, vc_vm, guest_auth, '/bin/bash',
                                       f'-c "echo root:{lsf.password} | chpasswd"')
                    if rc_pw == 0:
                        lsf.write_output(f'  {vc_hostname}: Root password reset to lab default')

                _guest_run(pm, vc_vm, guest_auth, '/bin/bash',
                           '-c "systemctl restart sshd 2>/dev/null; true"')
            else:
                lsf.write_output(f'  {vc_hostname}: WARNING - Could not authenticate to VM via Guest Operations')

            connect.Disconnect(si_esx)
        else:
            lsf.write_output(f'  {vc_hostname}: WARNING - VM not found on ESXi hosts, skipping Guest Operations')

        # --- Phase 2: Enable SSH and shell via REST API (with retries) ---
        try:
            session = requests.Session()
            session.trust_env = False

            api_token = None
            for attempt in range(6):
                try:
                    session_resp = session.post(
                        f'https://{vc_hostname}/api/session',
                        auth=(vc_user, lsf.password),
                        verify=False, timeout=15, proxies=None
                    )
                    if session_resp.status_code in (200, 201):
                        api_token = session_resp.text.strip().strip('"')
                        break
                except Exception:
                    pass
                lsf.write_output(f'  {vc_hostname}: Waiting for REST API...')
                _time_ssh.sleep(10)

            if not api_token:
                lsf.write_output(f'  {vc_hostname}: REST API unavailable, skipping SSH/shell API enablement')
                continue

            api_headers = {'vmware-api-session-id': api_token}

            ssh_resp = session.get(
                f'https://{vc_hostname}/api/appliance/access/ssh',
                headers=api_headers, verify=False, timeout=15, proxies=None
            )
            ssh_enabled = ssh_resp.status_code == 200 and ssh_resp.json() is True

            if not ssh_enabled:
                lsf.write_output(f'  {vc_hostname}: Enabling SSH via REST API...')
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
                    shell_enabled = shell_data is True

            if not shell_enabled:
                lsf.write_output(f'  {vc_hostname}: Enabling bash shell via REST API...')
                shell_enable_resp = session.put(
                    f'https://{vc_hostname}/api/appliance/access/shell',
                    headers=api_headers,
                    json={'enabled': True, 'timeout': 86400},
                    verify=False, timeout=15, proxies=None
                )
                if shell_enable_resp.status_code in [200, 204]:
                    lsf.write_output(f'  {vc_hostname}: Bash shell enabled successfully')
                else:
                    lsf.write_output(f'  {vc_hostname}: WARNING - Failed to enable bash shell (HTTP {shell_enable_resp.status_code})')
            else:
                lsf.write_output(f'  {vc_hostname}: Bash shell already enabled')

            session.delete(f'https://{vc_hostname}/api/session',
                           headers=api_headers, verify=False, timeout=10, proxies=None)

        except Exception as e:
            lsf.write_output(f'  {vc_hostname}: WARNING - REST API enablement failed: {e}')

        # --- Phase 3: Verify SSH connectivity ---
        _time_ssh.sleep(2)
        ssh_test = _subprocess_ssh.run(
            f'{lsf.sshpass} -p {lsf.password} ssh -o StrictHostKeyChecking=accept-new '
            f'-o ConnectTimeout=10 root@{vc_hostname} "echo SSH_OK"',
            shell=True, capture_output=True, text=True, timeout=30
        )
        if 'SSH_OK' in (ssh_test.stdout or ''):
            lsf.write_output(f'  {vc_hostname}: SSH connectivity verified')
        else:
            lsf.write_output(f'  {vc_hostname}: WARNING - SSH test failed (rc={ssh_test.returncode})')

if lsf.labtype != 'HOL':
    #==========================================================================
    # TASK: Verify all Autostart vCenter services are Started
    # Some services configured for AUTOMATIC startup fail to start during
    # vCenter boot (e.g. vapi-endpoint, trustmanagement). Check each vCenter
    # and start any AUTOMATIC services that are not in STARTED state.
    #==========================================================================
    import time as _time
    import subprocess as _subprocess

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

        try:
            result = _subprocess.run(
                check_cmd, shell=True, capture_output=True, text=True, timeout=120
            )
        except Exception as e:
            lsf.write_output(f'  WARNING: Could not query services on {vc_hostname}: {e}')
            autostart_failed += 1
            continue

        if result.returncode != 0 or not result.stdout:
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

            start_cmd = (
                f"{lsf.sshpass} -p {lsf.password} ssh {ssh_opts} "
                f"root@{vc_hostname} 'vmon-cli --start {svc_name} 2>&1'"
            )
            _subprocess.run(start_cmd, shell=True, capture_output=True,
                            text=True, timeout=120)

            started = False
            wait_start = _time.time()
            while (_time.time() - wait_start) < AUTOSTART_START_TIMEOUT:
                verify_cmd = (
                    f"{lsf.sshpass} -p {lsf.password} ssh {ssh_opts} "
                    f"root@{vc_hostname} "
                    f"\"vmon-cli -s {svc_name} 2>/dev/null | grep 'RunState:' | head -1 | sed 's/.*RunState: //'\""
                )
                verify_result = _subprocess.run(
                    verify_cmd, shell=True, capture_output=True,
                    text=True, timeout=30
                )
                if verify_result.stdout.strip() == 'STARTED':
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
