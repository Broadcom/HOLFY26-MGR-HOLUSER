# confighol.py version 1.0 14-April 2025
from pyVim import connect
from pyVmomi import vim
import logging
import lsfunctions as lsf

# this must be run manually. The VC shell part can only be run once.
# must have an accurate /tmp/config.ini

# read the /tmp/config.ini
lsf.init(router=False)

# create the authorized_keys file locally
manager_key = lsf.getfilecontents('/home/holuser/.ssh/id_rsa.pub')
lmc_key = lsf.getfilecontents('/lmchol/home/holuser/.ssh/id_rsa.pub')
local_auth_file = '/tmp/authorized_keys'
with open(local_auth_file, 'w') as lf:
    lf.write(manager_key)
    lf.write(lmc_key)
    lf.close()

esx_auth_file = '/etc/ssh/keys-root/authorized_keys'
vc_auth_file = '/root/.ssh/authorized_keys'

vcenters = []
if 'vCenters' in lsf.config['RESOURCES'].keys():
    vcenters = lsf.config.get('RESOURCES', 'vCenters').split('\n')

for entry in vcenters:
    vc_host = entry.split(':')
    vcshell = False
    answer = input(f'Enter "y" if you need to enable shell on {vc_host[0]} (n):')
    if "y" in answer:
        print(f'enabling shell on vc_host[0]...')
        lsf.run_command(f'/usr/bin/expect vcshell.exp {vc_host[0]}')

    print(f'enabling ssh auth for manager and LMC on {vc_host[0]}')
    lsf.scp(local_auth_file, f'root@{vc_host[0]}:{vc_auth_file}', lsf.password)
    lsf.ssh(f'chmod 600 {vc_auth_file}', f'root@{vc_host[0]}', lsf.password)
    print(f'fixing browser support and enabling MOB on {vc_host[0]}')
#   vcbrowser.sh - this is not working. investigate creating new jar file with Java jar
    lsf.scp('home/holuser/hol/Tools/vcbrowser.sh', f'root@{vc_host[0]}:/tmp/vcbrowser.sh', lsf.password)
    lsf.ssh(f'/usr/bin/bash /tmp/vcbrowser.sh', f'root@{vc_host[0]}', lsf.password)


if vcenters:
    lsf.connect_vcenters(vcenters)

esx_hosts = []
if 'ESXiHosts' in lsf.config['RESOURCES'].keys():
    esx_hosts = lsf.config.get('RESOURCES', 'ESXiHosts').split('\n')

if esx_hosts:
    for entry in esx_hosts:
        (host, mm) = entry.split(':')
        while True:
            if lsf.test_ping(host):
                lsf.enable_ssh_on_esx(host)
                # lsf.test_esx()
                lsf.scp(local_auth_file, f'root@{host}:{esx_auth_file}', lsf.password)
                lsf.ssh(f'chmod 600 {esx_auth_file}', f'root@{host}', lsf.password)
                lsf.update_session_timeout(host, 0)
                break # go on to the next host
