# VCFfinal.py version 1.4 28-April 2026
import datetime
import os
import sys
import time
import requests
from pyVim import connect
from pyVmomi import vim
import logging
import lsfunctions as lsf

def verify_nic_connected (vm_obj, simple):
    """
    Loop through the NICs and verify connection
    :param vm: the VM to check
    :param simple: true just connect do not disconnect then reconnect
    """
    nics = lsf.get_network_adapter(vm_obj)
    for nic in nics:
        if simple:
            lsf.write_output(f'Connecting {nic.deviceInfo.label} on {vm.name} .')
            lsf.set_network_adapter_connection(vm, nic, True)
            lsf.labstartup_sleep(lsf.sleep_seconds)
        elif nic.connectable.connected == True:
            lsf.write_output(f'{vm.name} {nic.deviceInfo.label} is connected.')
        else:
            lsf.write_output(f'{vm.name} {nic.deviceInfo.label} is NOT connected.')
            lsf.set_network_adapter_connection(vm, nic, False)
            lsf.labstartup_sleep(lsf.sleep_seconds)
            lsf.write_output(f'Connecting {nic.deviceInfo.label} on {vm.name} .')
            lsf.set_network_adapter_connection(vm, nic, True)


def _vcenter_delete_session(sess, vc_host, token):
    try:
        sess.delete(
            f'https://{vc_host}/api/session',
            headers={'vmware-api-session-id': token},
            verify=False, timeout=15, proxies=None)
    except Exception:
        pass


def check_supervisor_status_api(lsf, vc_host, vc_user):
    """
    Query vCenter REST API for WCP/Supervisor clusters.
    Returns a list of dicts: cluster_name, config_status, kubernetes_status, api_servers.
    """
    sess = requests.Session()
    sess.trust_env = False
    token = None
    try:
        session_resp = sess.post(
            f'https://{vc_host}/api/session',
            auth=(vc_user, lsf.password),
            verify=False, timeout=30, proxies=None)
        if session_resp.status_code not in (200, 201):
            lsf.write_output(
                f'  {vc_host}: session POST returned HTTP {session_resp.status_code}')
            return []
        token = session_resp.text.strip().strip('"')
        headers = {'vmware-api-session-id': token}
        clusters_resp = sess.get(
            f'https://{vc_host}/api/vcenter/namespace-management/clusters',
            headers=headers, verify=False, timeout=60, proxies=None)
        if clusters_resp.status_code != 200:
            lsf.write_output(
                f'  {vc_host}: namespace-management/clusters HTTP {clusters_resp.status_code}')
            return []
        rows = clusters_resp.json()
        if not isinstance(rows, list):
            return []
        out = []
        for item in rows:
            name = item.get('cluster_name') or item.get('name') or str(
                item.get('cluster', 'unknown'))
            cfg = item.get('config_status', '') or ''
            k8s = item.get('kubernetes_status', '') or ''
            api_srv = []
            eps = item.get('api_server_endpoints') or item.get('api_servers')
            if isinstance(eps, list):
                api_srv = [str(x) for x in eps if x]
            elif isinstance(eps, str) and eps:
                api_srv = [eps]
            out.append({
                'cluster_name': name,
                'config_status': cfg,
                'kubernetes_status': k8s,
                'api_servers': api_srv,
            })
        return out
    except Exception as ex:
        lsf.write_output(f'  {vc_host}: Supervisor API error: {ex}')
        return []
    finally:
        if token:
            _vcenter_delete_session(sess, vc_host, token)


# read the /hol/config.ini
lsf.init(router=False)

# verify a VCFfinal section exists
if lsf.config.has_section('VCFFINAL') == False:
    lsf.write_output('Skipping VCF final startup')
    exit(0)

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
lsf.write_vpodprogress('Tanzu Start', 'GOOD-8', color=color)

### Start SupervisorControlPlaneVMs
vcfmgmtcluster = []
if lsf.config.has_section('VCF') and 'vcfmgmtcluster' in lsf.config['VCF'].keys():
    vcfmgmtcluster = lsf.config.get('VCF', 'vcfmgmtcluster').split('\n')
    lsf.write_vpodprogress('VCF Hosts Connect', 'GOOD-3', color=color)
    lsf.connect_vcenters(vcfmgmtcluster)

lsf.write_vpodprogress('Tanzu Control Plane', 'GOOD-8', color=color)
supvms = lsf.get_vm_match('Supervisor*')
for vm in supvms:
   lsf.write_output(f'{vm.name} is {vm.runtime.powerState}')
   try:
        if vm.runtime.powerState != "poweredOn":
            lsf.start_nested([f'{vm.name}:{vm.runtime.host.name}'])
   except Exception as e:
        lsf.write_output(f'exception: {e}')

### Reconnect SupervisorControlPlaneVM NICs
for vm in supvms:
    verify_nic_connected (vm, False) # if not connected, disconnet then reconnect

## Restart Supervisor Webhooks to make sure certificate is valid/renewed
# if supvms list is not empty, then restart the webhooks
if supvms:
    lsf.write_output(f'Restarting Supervisor Webhooks')
    lsf.run_command("/home/holuser/hol/Tools/restart_k8s_webhooks.sh")

# ----------------------------------------------------------------------
# VVF901-MicroPod: verify Supervisor control plane on all vCenters (REST)
# Polls until all clusters RUNNING+READY or labfail on ERROR / timeout.
# ----------------------------------------------------------------------
if lsf.lab_sku == 'VVF901-MicroPod':
    WCP_POLL_INTERVAL = 30
    WCP_MAX_POLL_TIME = 3600

    vcenters_list = []
    if lsf.config.has_section('RESOURCES') and 'vCenters' in lsf.config['RESOURCES'].keys():
        for vc_line in lsf.config.get('RESOURCES', 'vCenters').split('\n'):
            line = vc_line.strip()
            if not line or line.startswith('#'):
                continue
            vcenters_list.append(line)

    if not vcenters_list:
        lsf.labfail('VVF901-MicroPod: no vCenters in [RESOURCES] to verify Supervisor')

    lsf.write_output('=' * 60)
    lsf.write_output('Verifying Supervisor Control Plane Status (Multi-vCenter)')
    lsf.write_output('=' * 60)
    lsf.write_vpodprogress('Tanzu Control Plane', 'GOOD-3', color=color)

    vcenter_targets = []
    for vc_line in vcenters_list:
        vc_parts = vc_line.split(':')
        vc_host = vc_parts[0].strip()
        vc_sso_domain = 'vsphere.local'
        vc_user = 'administrator@vsphere.local'
        if len(vc_parts) >= 3:
            user_part = vc_parts[2].strip()
            vc_user = user_part
            if '@' in user_part:
                vc_sso_domain = user_part.split('@', 1)[1]
        vcenter_targets.append({
            'host': vc_host,
            'sso_domain': vc_sso_domain,
            'user': vc_user,
        })

    lsf.write_output(f'Will check {len(vcenter_targets)} vCenter(s) for supervisors:')
    for target in vcenter_targets:
        lsf.write_output(
            f'  - {target["host"]} (SSO: {target["sso_domain"]})')

    supervisor_start_time = time.time()
    last_overall_status = 'No supervisors found'
    tanzu_verify_ok = False

    try:
        while (time.time() - supervisor_start_time) < WCP_MAX_POLL_TIME:
            elapsed = int(time.time() - supervisor_start_time)

            all_supervisor_clusters = {}
            total_clusters = 0
            ready_clusters = 0
            error_clusters = 0

            for target in vcenter_targets:
                vc_host = target['host']
                vc_user = target['user']

                sup_clusters = check_supervisor_status_api(lsf, vc_host, vc_user)

                if sup_clusters:
                    all_supervisor_clusters[vc_host] = sup_clusters
                    total_clusters += len(sup_clusters)

                    for cluster in sup_clusters:
                        config_status = cluster.get('config_status', '')
                        k8s_status = cluster.get('kubernetes_status', '')

                        if config_status == 'RUNNING' and k8s_status == 'READY':
                            ready_clusters += 1
                        elif config_status == 'ERROR':
                            error_clusters += 1

            if total_clusters == 0:
                lsf.write_output(
                    f'  No supervisor clusters found on any vCenter - waiting... '
                    f'({elapsed}s / {WCP_MAX_POLL_TIME}s)')
                last_overall_status = 'No supervisor clusters found'
            else:
                lsf.write_output(
                    f'  Found {total_clusters} supervisor cluster(s): '
                    f'{ready_clusters} ready, {error_clusters} error, '
                    f'{total_clusters - ready_clusters - error_clusters} pending '
                    f'({elapsed}s / {WCP_MAX_POLL_TIME}s)')

                for vc_host, clusters in all_supervisor_clusters.items():
                    for cluster in clusters:
                        config_status = cluster.get('config_status', '')
                        k8s_status = cluster.get('kubernetes_status', '')
                        cluster_name = cluster.get('cluster_name', 'unknown')
                        api_servers = cluster.get('api_servers', [])

                        status_str = f'config={config_status}, k8s={k8s_status}'
                        lsf.write_output(
                            f'    {vc_host}: "{cluster_name}" -> {status_str}')

                        if api_servers and config_status == 'RUNNING' and k8s_status == 'READY':
                            lsf.write_output(
                                f'      API servers: {", ".join(api_servers)}')

                last_overall_status = (
                    f'{ready_clusters}/{total_clusters} ready, {error_clusters} error')

                if error_clusters > 0:
                    lsf.labfail(
                        f'VVF901-MicroPod: {error_clusters} supervisor cluster(s) in ERROR '
                        f'({last_overall_status})')

                if ready_clusters == total_clusters and total_clusters > 0:
                    lsf.write_output(
                        f'All {total_clusters} supervisor cluster(s) are RUNNING and READY!')
                    tanzu_verify_ok = True
                    break

            time.sleep(WCP_POLL_INTERVAL)

        if not tanzu_verify_ok:
            lsf.labfail(
                f'VVF901-MicroPod: Supervisors did not reach RUNNING/READY within '
                f'{WCP_MAX_POLL_TIME // 60} minutes. Final status: {last_overall_status}')

    except SystemExit:
        raise
    except Exception as e:
        lsf.write_output(f'Error verifying Supervisor status: {e}')
        lsf.labfail(f'VVF901-MicroPod: Supervisor verification failed: {e}')

    lsf.write_output('Supervisor Control Plane: All clusters RUNNING and READY')

# Wizardry to deploy Tanzu

tanzucreate = []
if 'tanzucreate' in lsf.config['VCFFINAL'].keys():
    lsf.write_vpodprogress('Deploy Tanzu (25 Minutes)', 'GOOD-8', color=color)
    lsf.write_output('Deploy Tanzu (25 Minutes)')
    tanzucreate = lsf.config.get('VCFFINAL', 'tanzucreate').split('\n')
    lsf.write_vpodprogress('Waiting for Tanzu img to populate', 'GOOD-8', color=color)
    lsf.write_output('Waiting for Tanzu Images (10 minutes)...')
    # DEBUG skip this for dev testing - is there a test we can do?
    lsf.labstartup_sleep(600)

    # centos machine is 10.0.0.3 /root/TanzuCreate script. recommend DNS entry
    (tchost, tcaccount, tcscript) = tanzucreate[0].split(':')
    lsf.write_output(f'Running {tcscript} as {tcaccount}@{tchost} with password lsf.password')
    # DEBUG comment out
    result = lsf.ssh(tcscript, f'{tcaccount}@{tchost}', lsf.password, logfile=lsf.logfile)
    lsf.write_output(result.stdout)

######Start Aria Automation VMs
# Could we start this during the 10 minutes we're waiting for Tanzu?
vravms = []
if 'vravms' in lsf.config['VCFFINAL'].keys():
    vcenters = []
    if 'vCenters' in lsf.config['RESOURCES'].keys():
        vcenters = lsf.config.get('RESOURCES', 'vCenters').split('\n')

    if vcenters:
        lsf.write_vpodprogress('Connecting vCenters', 'GOOD-3', color=color)
        lsf.connect_vcenters(vcenters)
    vravms = lsf.config.get('VCFFINAL', 'vravms').split('\n')
    lsf.write_output('Starting Workspace Access...')
    lsf.write_vpodprogress('Starting Workspace Access', 'GOOD-8', color=color)
    # before starting verify NICs are set to start connected
    for vravm in vravms:
        (vmname, server) = vravm.split(':')
        try:
            vms = lsf.get_vm_match(vmname)
            for vm in vms:
                verify_nic_connected (vm, True) # just make sure connected at start
        except Exception as e:
            lsf.write_output(f'{e}')
    lsf.start_nested(vravms)
    # verify that the wsa L2 VM is actually starting
    # after starting verify NIC is actually connected
    for vravm in vravms:
        (vmname, server) = vravm.split(':')
        vms = lsf.get_vm_match(vmname)
        for vm in vms:
            while vm.runtime.powerState != 'poweredOn':
                vm.PowerOnVM_Task()
                lsf.labstartup_sleep(lsf.sleep_seconds)
            while vm.summary.guest.toolsRunningStatus != 'guestToolsRunning':
                lsf.write_output(f'Waiting for Tools in {vmname}...')
                lsf.labstartup_sleep(lsf.sleep_seconds)
                verify_nic_connected (vm, False) # if not connected, disconnect and reconnect
    
##### Final URL Checking
vraurls = []
if 'vraurls' in lsf.config['VCFFINAL'].keys():
    vraurls = lsf.config.get('VCFFINAL', 'vraurls').split('\n')
    lsf.write_vpodprogress('Aria Automation URL Checks', 'GOOD-8', color=color)
    lsf.write_output('Aria Automation URL Checks...')
    # Check VCF Automation ssh for password expiration and fix if expired
    lsf.write_output('Fixing expired automation pw if necessary...')
    lsf.run_command("/home/holuser/hol/Tools/vcfapwcheck.sh")
    # Run the watchvcfa script to make sure the seaweedfs-master-0 pod is not stale
    lsf.run_command("/home/holuser/hol/Tools/watchvcfa.sh")

    for entry in vraurls:
        url = entry.split(',')
        lsf.write_output(f'Testing {url[0]} for pattern {url[1]}')
        #  not_ready: optional pattern if present means not ready verbose: display the html
        #  lsf.test_url(url[0], pattern=url[1], not_ready='not yet', verbose=True)
        ctr = 0
        while not lsf.test_url(url[0], pattern=url[1], timeout=2, verbose=False):
            ctr += 1
            # If the URL is still unreachable after 30m, even with remediation attempt, then fail the pod
            if ctr == 30:
                lsf.labfail('fail: Automation URLS not accessible after 30m, should be reached in under 8m')
                exit(1)
                # Try to prevent excessive logging while waiting for VLP to stop vApp
                lsf.labstartup_sleep(120)
            # Wait for 1m before retrying
            lsf.write_output(f'Sleeping and will try again... {ctr} / 30')
            lsf.labstartup_sleep(60)             

for si in lsf.sis:
    connect.Disconnect(si)

lsf.write_output(f'{sys.argv[0]} finished.')
 
