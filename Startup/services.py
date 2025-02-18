# services.py - version v1.9 - 22-May 2024
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

# Manage Windows services on remote Windows machines
# options are "start", "restart", "stop" or "query"
winentries = []
if 'WindowsServices' in lsf.config['RESOURCES'].keys():
    winentries = lsf.config.get('RESOURCES', 'WindowsServices').split('\n')
if winentries:
    lsf.write_output('Starting Windows services.')
    action = 'start'
    lsf.write_vpodprogress('Manage Windows Services', 'GOOD-6', color=color)
    for entry in winentries:
        (host, service, p, ws) = entry.split(':')
        if not p:
            p = lsf.password
        if not ws:
            ws = 5
        while True:
            result = lsf.managewindowsservice(action, host, service, waitsec=int(ws), pw=p)
            if result == 'success':
                lsf.write_output(result)
            else:
                lsf.write_output(f'Cannot start {service} on {host}')
            lsf.labstartup_sleep(lsf.sleep_seconds)
    lsf.write_output('Finished start Windows services')

# Manage Linux services on remote machines
# options are "start", "restart", "stop" or "query"
linentries = []
if 'LinuxServices' in lsf.config['RESOURCES'].keys():
    linentries = lsf.config.get('RESOURCES', 'LinuxServices').split('\n')
if linentries:
    lsf.write_output('Starting Linux services.')
    action = 'start'
    lsf.write_vpodprogress('Manage Linux Services', 'GOOD-6', color=color)
    for entry in linentries:
        (host, service, p, ws) = entry.split(':')
        if not p:
            p = lsf.password
        if not ws:
            ws = 5
        while True:
            lsf.write_output(f'Performing {action} {service} on {host}')
            try:
                res = lsf.managelinuxservice(action, host, service, waitsec=int(ws), pw=p)
                if len(res.stdout):
                    lresult = res.stdout.lower()
                    if 'running' in lresult or 'started' in lresult:
                        lsf.write_output(f'result: {res.stdout}')
                        break
            except Exception as e:
                    lsf.write_output(f'Unable to {action} {service} on {host}. {e}')
                    lsf.labstartup_sleep(lsf.sleep_seconds)
    lsf.write_output(f'Finished {action} Linux Services.')

###
# Ensure services in the $TCPServices array are answering on specified ports
tcpentries = []
if 'TCPServices' in lsf.config['RESOURCES'].keys():
    tcpentries = lsf.config.get('RESOURCES', 'TCPServices').split('\n')
if tcpentries:
    lsf.write_output('Begin testing TCP ports...')
    lsf.write_vpodprogress('Testing TCP Ports', 'GOOD-6', color=color)
    for entry in tcpentries:
        (host, port) = entry.split(':')
        while not lsf.test_tcp_port(host, port):
            lsf.write_output(f'Testing {port} on {host}')
            lsf.labstartup_sleep(lsf.sleep_seconds)
    lsf.write_output('Finished testing TCP ports')

