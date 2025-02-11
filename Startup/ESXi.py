# vSphere.py version 1.8 13-February 2024
import datetime
import os
import sys
from pyVim import connect
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
# Testing that vESXi hosts are online: all hosts must respond before continuing
esx_hosts = []
if 'ESXiHosts' in lsf.config['RESOURCES'].keys():
    esx_hosts = lsf.config.get('RESOURCES', 'ESXiHosts').split('\n')

if esx_hosts:
    lsf.write_vpodprogress('Checking ESXi hosts', 'GOOD-3', color=color)
    for entry in esx_hosts:
        (host, mm) = entry.split(':')
        while True:
            if lsf.test_esx(host):
                break # go on to the next host
            else:
                lsf.write_output(f'Unable to test {host}. FAIL')
                lsf.write_vpodprogress(f'{host} TIMEOUT', 'TIMEOUT', color=color)



    

