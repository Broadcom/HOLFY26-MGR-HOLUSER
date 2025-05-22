# confighol.py version 1.13 22-May 2025
import os
import glob
from pyVim import connect
from pyVmomi import vim
import logging
import xml.etree.ElementTree as et
import lsfunctions as lsf

# this must be run manually. The VC shell part can only be run once.
# must have an accurate /tmp/config.ini

def process_nsx_node(nsxmachine):
    nsxusers = ["admin", "root", "audit"]
    print(f'enabling ssh auth for manager and LMC on {nsxmachine}')
    lsf.scp(local_auth_file, f'root@{nsxmachine}:{auth_file}', lsf.password)
    lsf.ssh(f'chmod 600 {auth_file}', f'root@{nsxmachine}', lsf.password)
        
    # Remove password expiry for admin, root and audit on all NSX Managers
    
    for nsxuser in nsxusers:
        print(f'Removing password expiration for {nsxuser} on {nsxmachine}...')
        lsf.ssh(f'clear user {nsxuser} password-expiration', f'admin@{nsxmachine}', lsf.password)


# read the /tmp/config.ini
lsf.init(router=False)

if not os.path.exists('/usr/bin/expect'):
    print("Please install 'expect' on the Manager.")
    exit(1)
else:
    print("The 'expect' utility is present. Continuing...")

# deal with the Firefox SSL certificates
filepath = glob.glob('/lmchol/home/holuser/snap/firefox/common/.mozilla/firefox/*/SiteSecurityServiceState.bin')
if len(filepath) == 1:
    print(f'Renaming {filepath[0]} to {filepath[0]}.bak')
    os.rename(filepath[0], f'{filepath[0]}.bak')

# remove known_hosts LMC and Manager to prevent ssh/scp key issues
known_hosts = '/home/holuser/.ssh/known_hosts'
if os.path.exists(known_hosts):
    os.remove(known_hosts)
if os.path.exists(f'/lmchol/{known_hosts}'):
    os.remove(f'/lmchol/{known_hosts}')

# create .ssh/config to accept new ssh keys on LMC and Manager
sshconfig = "Host *\n\tStrictHostKeyChecking=no\n"
with open('/home/holuser/.ssh/config', 'w') as c:
    c.write(sshconfig)
c.close()
os.system('cp /home/holuser/.ssh/config /lmchol/home/holuser/.ssh/config')

# create the authorized_keys file locally
manager_key = lsf.getfilecontents('/home/holuser/.ssh/id_rsa.pub')
lmc_key = lsf.getfilecontents('/lmchol/home/holuser/.ssh/id_rsa.pub')
global local_auth_file
local_auth_file = '/tmp/authorized_keys'
with open(local_auth_file, 'w') as lf:
    lf.write(manager_key)
    lf.write(lmc_key)
    lf.close()

esx_auth_file = '/etc/ssh/keys-root/authorized_keys'
global auth_file
auth_file = '/root/.ssh/authorized_keys'
vpxd = '/etc/vmware-vpx/vpxd.cfg'
lvpxd = '/tmp/vpxd.cfg'

vcenters = []
if 'vCenters' in lsf.config['RESOURCES'].keys():
    vcenters = lsf.config.get('RESOURCES', 'vCenters').split('\n')

# need to connect to vCenters in order to enable ssh on ESXi hosts
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
                lsf.connect_vc(host, 'root', lsf.password)
                lsf.enable_ssh_on_esx(host)
                lsf.scp(local_auth_file, f'root@{host}:{esx_auth_file}', lsf.password)
                lsf.ssh(f'chmod 600 {esx_auth_file}', f'root@{host}', lsf.password)
                lsf.update_session_timeout(host, 0)
                print(f'Setting non-expiring password for root on {host}')
                lsf.ssh('chage -M 9999 root', f'root@{host}', lsf.password)
                break # go on to the next host

for entry in vcenters:
    (vc_host, vc_type, user) = entry.split(':')
    vcshell = False
    answer = input(f'Enter "y" if you need to enable shell and browser support warning on {vc_host} (n):')
    if "y" in answer:
        print(f'enabling shell on {vc_host}...')
        lsf.run_command(f'/usr/bin/expect ~/hol/Tools/vcshell.exp {vc_host} {lsf.password}')

        print(f'enabling ssh auth for manager and LMC on {vc_host}')
        lsf.scp(local_auth_file, f'root@{vc_host}:{auth_file}', lsf.password)
        lsf.ssh(f'chmod 600 {auth_file}', f'root@{vc_host}', lsf.password)

        print(f'fixing browser support and enabling MOB on {vc_host}')
        lsf.run_command(f'/home/holuser/hol/Tools/vcbrowser.sh {vc_host}')

        # enable the MOB
        # edit /etc/vmware-vpxd/vpxd.cfg
        #<enableDebugBrowse>true</enableDebugBrowse>
        # service-control --restart vmware-vpxd
        lsf.scp(f'root@{vc_host}:{vpxd}', lvpxd, lsf.password)
        tree = et.parse(lvpxd)
        root = tree.getroot()
        parent = root.find('vpxd')
        mob = et.Element('enableDebugBrowse')
        mob.text = 'true'
        parent.append(mob)
        tree.write(lvpxd)
        lsf.scp(lvpxd, f'root@{vc_host}:{vpxd}',  lsf.password)
        lsf.ssh('service-control --restart vmware-vpxd', f'root@{vc_host}', lsf.password)

    print(f'Setting non-expiring password for root on {vc_host}')
    lsf.ssh('chage -M -1 root', f'root@{vc_host}', lsf.password)
    print(f'Disabling HA Admission Control and configuring DRS to be partially automated on {vc_host}...')
    print(f'Configuring local accounts and password policies on {vc_host}...')
    lsf.run_command(f'pwsh -File configvsphere.ps1 {vc_host} {user} {lsf.password}')
    print(f'Clearing arp cache for {vc_host}...')
    lsf.ssh('ip -s -s neigh flush all', f'root@{vc_host}', lsf.password)

# NSX stuff
if 'VCF' in lsf.config:
    vcfnsxmgr = []
    if 'vcfnsxmgr' in lsf.config['VCF'].keys():
        vcfnsxmgrs = lsf.config.get('VCF', 'vcfnsxmgr').split('\n')
        for entry in vcfnsxmgrs:
            (nsxmgr, esxhost) = entry.split(':')
            answer = input(f'Enter "y" if ssh is enabled on {nsxmgr} (n):')
            if "y" in answer:
                process_nsx_node(nsxmgr)

    vcfnsxedges = []
    if 'vcfnsxedges' in lsf.config['VCF'].keys():
        vcfnsxedges = lsf.config.get('VCF', 'vcfnsxedges').split('\n')
        for entry in vcfnsxedges:
            (nsxedge, esxhost) = entry.split(':')
            answer = input(f'Enter "y" if ssh is enabled on {nsxedge} (n):')
            if "y" in answer:
                process_nsx_node(nsxedge)

# Remove password expiry for vcf, backup and root on sddcmanager-a
sddcmgr = 'sddcmanager-a.site-a.vcf.lab'
# only setup ssh auth to the sddcmanager-a from the console (manager rsa_id.pub not working)
lsf.scp('/lmchol/homes/holuser/.ssh/id_rsa.pub', f'vcf@{sddcmgr}:{auth_file}', lsf.password)
lsf.ssh('chmod 600 ~/.ssh/authorized_keys', f'vcf@{sddcmgr}', lsf.password)
# run the expect script to su -, send the password. then update password expiry
print(f'configuring non-expiring passwords on {sddcmgr} for vcf, backup and root accounts...')
lsf.run_command(f'/usr/bin/expect ~/hol/Tools/sddcmgr.exp {sddcmgr} {lsf.password}')

# OPs stuff
opsvms = []
if 'VMs' in lsf.config['RESOURCES'].keys():
    vms = lsf.config.get('RESOURCES', 'VMs').split('\n')
    for vm in vms:
        if "ops" in vm:
            (ops, vc) = vm.split(':')
            opsvms.append(ops)

for opsvm in opsvms:
    print(f'Setting non-expiring password for root on {opsvm}')
    lsf.ssh('chage -M -1 root', f'root@{opsvm}', lsf.password)
    print(f'enabling ssh auth for manager and LMC on {opsvm}')
    lsf.scp(local_auth_file, f'root@{opsvm}:{auth_file}', lsf.password)
    lsf.ssh(f'chmod 600 {auth_file}', f'root@{opsvm}', lsf.password)

# arp cache stuff in console and router (Cannot do Manager except as root)
for machine in ["console", "router"]:
    lsf.ssh('ip -s -s neigh flush all', f'root@{machine}', lsf.password)

# final step is to call vpodchecker.py to update L2 VMs (uuid and typematicdelay)
print("Starting vpodchecker.py...")
os.system('python3 /home/holuser/hol/Tools/vpodchecker.py')
