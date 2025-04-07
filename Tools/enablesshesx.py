from pyVim import connect
from pyVmomi import vim
import logging
import lsfunctions as lsf

# read the /hol/config.ini
lsf.init(router=False)

vcenters = []
if 'vCenters' in lsf.config['RESOURCES'].keys():
    vcenters = lsf.config.get('RESOURCES', 'vCenters').split('\n')

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
                break # go on to the next host
