# urls.py - version v1.8 - 05-July 2024
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

urls = []
if 'URLs' in lsf.config['RESOURCES'].keys():
    urls = lsf.config.get('RESOURCES', 'URLs').split('\n')
if urls:
    lsf.write_output('Testing URLS')
    lsf.write_vpodprogress('Checking URLs', 'GOOD-7', color=color)
    pattern = ''
    for entry in urls:
        pattern = ''
        url = entry.split(',')
        if len(url) == 2:
            pattern = url[1]
            if pattern != '':
                pattern = url[1]
                lsf.write_output(f'Testing {url[0]} for pattern {url[1]}')
        if pattern == '':
            lsf.write_output(f'Testing {url[0]} for HTTP response since there is no pattern.')
                
        
        #  not_ready: optional pattern if present means not ready verbose: display the html
        #  lsf.test_url(url[0], url[1], not_ready='not yet', verbose=True)
        no_proxy = False
        if lsf.labtype != 'HOL':
            no_proxy = True
        while not lsf.test_url(url[0], pattern=pattern, timeout=2, verbose=False, no_proxy=no_proxy):
            lsf.write_output(f'Sleeping and will try again...')
            lsf.labstartup_sleep(lsf.sleep_seconds)

    lsf.write_output('Finished testing URLs')

