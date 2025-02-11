# odyssey.py - version v1.7 - 23-February 2024
import sys
import lsfunctions as lsf
import os
import shutil
import datetime
import requests
import logging
from pathlib import Path

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

if lsf.odyssey == True and lsf.labcheck == False:
    lsf.write_vpodprogress('Odyssey Install', 'GOOD-8', color=color)
else:
    exit(0)
#
# BEGIN ODYSSEY CODE
#
# Odyssey Variables
#

# LMC or WMC
if lsf.WMC:
    #mc = '/wmchol'
    desktop = '/Users/Administrator/Desktop'
    ody_shortcut = 'Play VMware Odyssey.lnk'
    odyssey_app = 'odyssey-launcher.exe'
    # legacy most likely not needed
    # odysseyEXE = 'odyssey-launcher.exe'
    odyssey_dst = 'Users/Administrator'
elif lsf.LMC:
    #mc = '/lmchol'
    desktop = '/home/holuser/Desktop'
    ody_shortcut = 'launch_odyssey.desktop'
    odyssey_app = 'odyssey-client-linux.AppImage'
    odyssey_launcher = 'odyssey-launch.sh'
    ody_icon = 'icon-256.png'
    odyssey_dst = f'home/holuser/desktop-hol'
    lmcuser = f'holuser@mainconsole.{lsf.dom}'

odyssey_launcher_src = f'https://odyssey.vmware.com/client/{odyssey_app}'
# print(odyssey_launcher_src)

if not lsf.labcheck:
    if os.path.isfile(f'{lsf.mc}/{desktop}/{ody_shortcut}'):
        lsf.write_output('Removing existing Odyssey desktop shortcut.', logfile=lsf.logfile)
        os.remove(f'{lsf.mc}/{desktop}/{ody_shortcut}')

    if os.path.isfile(f'{lsf.mc}/{odyssey_dst}/{odyssey_app}'):
        lsf.write_output(f'Removing existing Odyssey application. {lsf.mc}/{odyssey_dst}/{odyssey_app}', logfile=lsf.logfile)
        os.remove(f'{lsf.mc}/{odyssey_dst}/{odyssey_app}')

    # remove the file locally (shouldn't be here since /tmp gets deleted with each boot)
    if os.path.isfile(f'/tmp/{odyssey_app}'):
        lsf.write_output('Removing existing Odyssey application.', logfile=lsf.logfile)
        os.remove(f'/tmp/{odyssey_app}')

    # doubt this is needed but will include
    # we won't be able to do this. we can check but will need to run a command to remove (permissions)
    legacy_odyssey_client = '/wmchol/Users/Administrator/VMware_Odyssey.exe'
    if os.path.isfile(legacy_odyssey_client):
        lsf.write_output('Removing legacy Odyssey application.', logfile=lsf.logfile)
        os.remove(legacy_odyssey_client)

the_cloud = lsf.get_cloudinfo()
if the_cloud == 'NOT REPORTED':
    run_odyssey_prep = False
    if lsf.odyssey:
        lsf.write_output('Lab not deployed by VLP. Odyssey installation not running.', logfile=lsf.logfile)
else:
    lsf.write_output(the_cloud, logfile=lsf.logfile)
    run_odyssey_prep = True
    odyssey_type = 'V2'

# only run if the pod is deployed by VLP and in an identified cloud org
# DEBUG ONLY
# run_odyssey_prep = True  
if run_odyssey_prep and lsf.odyssey and not lsf.labcheck:  # VLP deployments and Configuration.txt enabled

    lsf.write_output('Begin Odyssey Install...', logfile=lsf.logfile)
    lsf.write_vpodprogress('Odyssey Install', 'GOOD-8', color=color)

    # Get the Odyssey app
    while not os.path.isfile(f'/tmp/{odyssey_app}'):
        response = requests.get(odyssey_launcher_src, stream=True, proxies=lsf.proxies, timeout=5)
        if response.status_code == 200:
            lsf.write_output(f'Latest {odyssey_app} downloaded', logfile=lsf.logfile)
            with open(f'/tmp/{odyssey_app}', 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file) # need to use os            
            lsf.write_output(f'Copying /tmp/{odyssey_app} to {lsf.mc}/{odyssey_dst}/{odyssey_app}', logfile=lsf.logfile)
            os.system(f'cp /tmp/{odyssey_app} {lsf.mc}/{odyssey_dst}/{odyssey_app}')  # shutil.copy gets permission error
        else:
            lsf.write_output(f'Waiting for {odyssey_app} download...', logfile=lsf.logfile)
            lsf.labstartup_sleep(lsf.sleep_seconds)
    if lsf.WMC:
        # execute the Odyssey prep script on the WMC to complete the prep phase
        os.system(f'cp {lsf.holroot}/Tools/WMC-Odyssey-prep.ps1 {lsf.mc}/{odyssey_dst}/')
        # C:\Program Files\PowerShell\7\pwsh.exe
        command = 'pwsh C:\\Users\\Administrator\\WMC-Odyssey-prep.ps1 > C:\\Users\\Administrator\\odyssey-prep.log'
        lsf.write_output('Running WMC-Odyssey-prep.ps1 on mainconsole. Please stand by...', logfile=lsf.logfile)
        result = lsf.runwincmd(command, 'mainconsole', 'Administrator', lsf.password, logfile=lsf.logfile)
        with open(f'{lsf.mc}/{odyssey_dst}/odyssey-prep.log', 'r') as ologfile:
            olog = ologfile.readlines()
        ologfile.close()
        for line in olog:
            lsf.write_output(line.strip(), logfile=lsf.logfile)
        os.system(f'rm {lsf.mc}/{odyssey_dst}/WMC-Odyssey-prep.ps1')
        os.system(f'mv {lsf.mc}/{odyssey_dst}/odyssey-prep.log /tmp')
    elif lsf.LMC:
        # copy the launcher
        os.system(f'cp {lsf.holroot}/Tools/{odyssey_launcher} {lsf.mc}/{odyssey_dst}/{odyssey_launcher}')
        # copy the icon
        os.system(f'cp {lsf.holroot}/Tools/{ody_icon} {lsf.mc}/{odyssey_dst}/images/{ody_icon}')
        # copy the desktop file
        os.system(f'cp {lsf.holroot}/Tools/{ody_shortcut} {lsf.mc}/{desktop}/{ody_shortcut}')
        lcmd = f'/usr/bin/gio set /home/holuser/Desktop/{ody_shortcut} metadata::trusted true'
        result = lsf.ssh(lcmd, lmcuser, lsf.password, logfile=lsf.logfile)
        lcmd = f'/usr/bin/chmod a+x /home/holuser/Desktop/{ody_shortcut} '
        result = lsf.ssh(lcmd, lmcuser, lsf.password, logfile=lsf.logfile)
    
    if os.path.isfile(f'{lsf.mc}/{desktop}/{ody_shortcut}'):
        lsf.write_output('Finished Odyssey install.', logfile=lsf.logfile) 
        lsf.write_vpodprogress('READY', 'ODYSSEY-READY', color='green')
    else:        
        lsf.write_output(f'Odyssey ERROR. {lsf.mc}/{desktop}/{ody_shortcut} not created.', logfile=lsf.logfile) 
        lsf.write_vpodprogress('ODYSSEY FAIL', 'ODYSSEY-FAIL', color='red')

    lsf.write_output(f'Hosting cloud is {the_cloud} ... created Odyssey launcher.', logfile=lsf.logfile)
elif lsf.odyssey:
    lsf.write_output(f'Hosting cloud is {the_cloud} ... did not run Odyssey prep, but thought about it.', logfile=lsf.logfile)

