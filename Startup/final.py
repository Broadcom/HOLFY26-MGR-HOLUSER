# final.py - version v1.6 - 05-February 2024
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
if lsf.labcheck == False:
    lsf.write_vpodprogress('Final Checks', 'GOOD-8', color=color)

# prevent update manager from showing window for updates if LMC
if lsf.LMC and lsf.labtype == 'HOL':
    try:
        lsf.write_output('Making sure updates are not showing on console...')
        lsf.ssh(f'pkill update-manager;pkill update-notifier 2>&1', 'holuser@console', lsf.password)
    except Exception as e:
        lsf.write_output(f'exception: {e}')


# add any code you want to run at the end of the startup before final "Ready"
#lsf.write_output("This is final.py output")


# fail like this
#lsf.labfail('FINAL ISSUE')
#exit(1)

lsf.write_output('Finished Final Checks')
lsf.write_vpodprogress('Finished Final Checks', 'GOOD-9', color=color)
