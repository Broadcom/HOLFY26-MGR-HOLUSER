# pings.py - version v1.25 - 26-January 2024
import sys
import logging
import datetime
import lsfunctions as lsf

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

# Wait here for all hosts in the pings list to respond before continuing
pings = []
if 'Pings' in lsf.config['RESOURCES'].keys():
    pings = lsf.config.get('RESOURCES', 'Pings').split('\n')

if pings:
    lsf.write_vpodprogress('Waiting for pings', 'GOOD-5', color=color)
    for ping in pings:
        lsf.test_ping(ping)

