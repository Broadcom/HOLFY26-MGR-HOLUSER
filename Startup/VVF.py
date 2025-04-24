# VVF.py version 1.0 24-April 2025
import datetime
import os
import sys
from pyVim import connect
import logging
import lsfunctions as lsf

# read the /hol/config.ini
lsf.init(router=False)

# verify a VVF section exists
if lsf.config.has_section('VVF') == False:
    lsf.write_output('Skipping VVF startup')
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
lsf.write_vpodprogress('VVF Start', 'GOOD-3', color=color)

# connect to all VVF hosts
vvfmgmtcluster = []
if 'vvfmgmtcluster' in lsf.config['VVF'].keys():
    vvfmgmtcluster = lsf.config.get('VVF', 'vvfmgmtcluster').split('\n')
    lsf.write_vpodprogress('VVF Hosts Connect', 'GOOD-3', color=color)
    lsf.connect_vcenters(vvfmgmtcluster)
    for entry in vvfmgmtcluster:
        (hostname, mm) = entry.split(':')
        host = lsf.get_host(hostname)
        if host.runtime.inMaintenanceMode:
            lsf.write_output(f'Removing {hostname} from Maintenance Mode')
            host.ExitMaintenanceMode_Task(0)
        elif host.runtime.connectionState != 'connected':
            lsf.write_output(f'Host in Error State [{host.runtime.connectionState}]. Sleeping and trying again.')
        lsf.labstartup_sleep(lsf.sleep_seconds)

# check the vvfmgmtdatastore
vvfmgmtdatastore = []
if 'vvfmgmtdatastore' in lsf.config['VVF'].keys():
    vvfmgmtdatastore = lsf.config.get('VVF', 'vvfmgmtdatastore').split('\n')
    lsf.write_vpodprogress('VVF Datastore check', 'GOOD-3', color=color)
    for datastore in vvfmgmtdatastore:
        while True:
            try:
                lsf.write_output(f'Attempting to check datastore {datastore}')
                ds = lsf.get_datastore(datastore)
                if ds is None:
                    lsf.write_output(f'Did not find {datastore}. Skipping.')
                    break
                if ds.summary.accessible:
                    vmstocheck = ds.vm
                    if len(vmstocheck) == 0: # if no VMs then something is wrong
                        raise Exception(f'No connected VMs on {datastore}')
                    for vmtocheck in vmstocheck:
                        lsf.write_output(f'Getting VM: {vmtocheck.config.name}')
                        if vmtocheck.runtime.connectionState != 'connected':
                            lsf.write_output(f'Datastore {datastore} may not be online yet...')
                            lsf.write_output("Pausing 30 seconds for vSAN to stabilze...")
                            lsf.labstartup_sleep(30)
                        else:
                            lsf.write_output(f'{vmtocheck.config.name} is {vmtocheck.runtime.connectionState}')
                            lsf.write_output(f'Datastore {datastore} appears to be available now...')
                            break
                    break
                else:
                    lsf.write_output(f'ds.summary.accessible: {ds.summary.accessible}')
            except Exception as e:
                lsf.write_output(f'Unable to check datastore {datastore}. Will try again in 30 seconds. {e}')
                lsf.labstartup_sleep(30)

# Start the NSX Manager due to Tanzu
vvfnsxmgr = []
if 'vvfnsxmgr' in lsf.config['VVF'].keys():
    vvfnsxmgr = lsf.config.get('VVF', 'vvfnsxmgr').split('\n')
    lsf.write_vpodprogress('VVF NSX Mgr start', 'GOOD-3', color=color)
    lsf.start_nested(vvfnsxmgr)
    # could we do a url test here for the NSX Manager instead of sleeping?
    # DEBUG - skip this sleep for dev testing
    lsf.write_output("Pausing 30 seconds for NSX Manager(s) to start...")
    lsf.labstartup_sleep(30)

vvfnsxedges = []
if 'vvfnsxedges' in lsf.config['VVF'].keys():
    lsf.write_output('Starting VVF NSX Edges...')
    lsf.write_vpodprogress('VVF NSX Edges start', 'GOOD-3', color=color)
    vvfnsxedges = lsf.config.get('VVF', 'vvfnsxedges').split('\n')
    lsf.start_nested(vvfnsxedges)
    lsf.write_output("Pausing 5 minutes for NSX Edges to start...")
    lsf.labstartup_sleep(300)

vvfvCenter = []
if 'vvfvCenter' in lsf.config['VVF'].keys():
    lsf.write_output('Starting VVF management vCenter...')
    lsf.write_vpodprogress('VVF vCenter start', 'GOOD-3', color=color)
    vvfvCenter = lsf.config.get('VVF', 'vvfvCenter').split('\n')
    lsf.start_nested(vvfvCenter)

lsf.write_output('Disconnecting VVF hosts...')
for si in lsf.sis:
    connect.Disconnect(si)

lsf.write_vpodprogress('VVF Finished', 'GOOD-3', color=color)
