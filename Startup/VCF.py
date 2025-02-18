# VCF.py version 0.4 29-May 2024
import datetime
import os
import sys
from pyVim import connect
import logging
import lsfunctions as lsf

# read the /hol/config.ini
lsf.init(router=False)

# verify a VCF section exists
if lsf.config.has_section('VCF') == False:
    lsf.write_output('Skipping VCF startup')
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
lsf.write_vpodprogress('VCF Start', 'GOOD-3', color=color)

# connect to all VCF hosts
vcfmgmtcluster = []
if 'vcfmgmtcluster' in lsf.config['VCF'].keys():
    vcfmgmtcluster = lsf.config.get('VCF', 'vcfmgmtcluster').split('\n')
    lsf.write_vpodprogress('VCF Hosts Connect', 'GOOD-3', color=color)
    lsf.connect_vcenters(vcfmgmtcluster)
    for entry in vcfmgmtcluster:
        (hostname, mm) = entry.split(':')
        host = lsf.get_host(hostname)
        if host.runtime.inMaintenanceMode:
            lsf.write_output(f'Removing {hostname} from Maintenance Mode')
            host.ExitMaintenanceMode_Task(0)
        elif host.runtime.connectionState != 'connected':
            lsf.write_output(f'Host in Error State [{host.runtime.connectionState}]. Sleeping and trying again.')
        lsf.labstartup_sleep(lsf.sleep_seconds)

# check the vcfmgmtdatastore
vcfmgmtdatastore = []
if 'vcfmgmtdatastore' in lsf.config['VCF'].keys():
    vcfmgmtdatastore = lsf.config.get('VCF', 'vcfmgmtdatastore').split('\n')
    lsf.write_vpodprogress('VCF Datastore check', 'GOOD-3', color=color)
    for datastore in vcfmgmtdatastore:
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
vcfnsxmgr = []
if 'vcfnsxmgr' in lsf.config['VCF'].keys():
    vcfnsxmgr = lsf.config.get('VCF', 'vcfnsxmgr').split('\n')
    lsf.write_vpodprogress('VCF NSX Mgr start', 'GOOD-3', color=color)
    lsf.start_nested(vcfnsxmgr)
    # could we do a url test here for the NSX Manager instead of sleeping?
    # DEBUG - skip this sleep for dev testing
    lsf.write_output("Pausing 30 seconds for NSX Manager(s) to start...")
    lsf.labstartup_sleep(30)
else:
    lsf.write_output('Did not find any NSX Manager entry.')
    lsf.labfail('No NSX Manager')

vcfnsxedges = []
if 'vcfnsxedges' in lsf.config['VCF'].keys():
    lsf.write_output('Starting VCF NSX Edges...')
    lsf.write_vpodprogress('VCF NSX Edges start', 'GOOD-3', color=color)
    vcfnsxedges = lsf.config.get('VCF', 'vcfnsxedges').split('\n')
    lsf.start_nested(vcfnsxedges)

# is there a test we can do for the NSX Manager and Edges instead of sleeping?
# DEBUG - skip this sleep for dev testing
lsf.write_output("Pausing 5 minutes for NSX Edges to start...")
lsf.labstartup_sleep(300)

vcfvCenter = []
if 'vcfvCenter' in lsf.config['VCF'].keys():
    lsf.write_output('Starting VCF management vCenter...')
    lsf.write_vpodprogress('VCF vCenter start', 'GOOD-3', color=color)
    vcfvCenter = lsf.config.get('VCF', 'vcfvCenter').split('\n')
    lsf.start_nested(vcfvCenter)

lsf.write_output('Disconnecting VCF hosts...')
for si in lsf.sis:
    connect.Disconnect(si)

lsf.write_vpodprogress('VCF Finished', 'GOOD-3', color=color)
