# confighol.py version 1.3 16-April 2025
import os
import glob
from pyVim import connect
from pyVmomi import vim
import logging
import xml.etree.ElementTree as et
import lsfunctions as lsf

# this must be run manually. The VC shell part can only be run once.
# must have an accurate /tmp/config.ini

# read the /tmp/config.ini
lsf.init(router=False)

if not os.path.exists('/usr/bin/expect'):
    print("Please install 'expect' on the Manager.")
    exit(1)
else:
    print("The 'expect' utility is present. Continuing...")

# deal with the Firefox SSL certificates
filepath = glob.glob('/lmchol/home/holuser/snap/firefox/common/.mozilla/firefox/*/SiteSecurityServiceState.bin')
if os.path.isfile(filepath[0]):
    print(f'Renaming {filepath[0]} to {filepath[0]}.bak')
    os.rename(filepath[0], f'{filepath[0]}.bak')

# remove known_hosts LMC and Manager to prevent ssh/scp key issues
known_hosts = '/home/holuser/.ssh/known_hosts'
if os.path.exists(known_hosts):
    os.remove(known_hosts)
if os.path.exists(f'/lmchol/{known_hosts}'):
    os.remove(f'/lmchol/{known_hosts}')

# create .ssh/config to accept new ssh keys on LMC and Manager
sshconfig = "Host *\n\tStrictHostKeyChecking=no=\n"
with open('/home/holuser/.ssh/config', 'w') as c:
    c.write(sshconfig)
c.close()
os.system('cp /home/holuser/.ssh/config /lmchol/home/holuser/.ssh/config')

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
vpxd = '/etc/vmware-vpx/vpxd.cfg'
lvpxd = '/tmp/vpxd.cfg'

vcenters = []
if 'vCenters' in lsf.config['RESOURCES'].keys():
    vcenters = lsf.config.get('RESOURCES', 'vCenters').split('\n')

for entry in vcenters:
    vc_host = entry.split(':')
    vcshell = False
    answer = input(f'Enter "y" if you need to enable shell on {vc_host[0]} (n):')
    if "y" in answer:
        print(f'enabling shell on {vc_host[0]}...')
        lsf.run_command(f'/usr/bin/expect vcshell.exp {vc_host[0]} {lsf.password}')

    print(f'enabling ssh auth for manager and LMC on {vc_host[0]}')
    lsf.scp(local_auth_file, f'root@{vc_host[0]}:{vc_auth_file}', lsf.password)
    lsf.ssh(f'chmod 600 {vc_auth_file}', f'root@{vc_host[0]}', lsf.password)
    print(f'fixing browser support and enabling MOB on {vc_host[0]}')
    lsf.run_command(f'/home/holuser/hol/Tools/vcbrowser.sh {vc_host[0]}')
    # enable the MOB
    # edit /etc/vmware-vpxd/vpxd.cfg
    #<enableDebugBrowse>true</enableDebugBrowse>
    # service-control --restart vmware-vpxd
    lsf.scp(f'root@{vc_host[0]}:{vpxd}', lvpxd, lsf.password)
    tree = et.parse(lvpxd)
    root = tree.getroot()
    parent = root.find('vpxd')
    mob = et.Element('enableDebugBrowse')
    mob.text = 'true'
    parent.append(mob)
    tree.write(lvpxd)
    lsf.scp(lvpxd, f'root@{vc_host[0]}:{vpxd}',  lsf.password)
    lsf.ssh('service-control --restart vmware-vpxd', f'root@{vc_host[0]}', lsf.password)

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
