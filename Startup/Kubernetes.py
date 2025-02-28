# Kubernetes.py - version v1.8 - 28-February 2025
import datetime
import os
import sys
import io
import logging
import subprocess
import lsfunctions as lsf

# default logging level is WARNING (other levels are DEBUG, INFO, ERROR and CRITICAL)
logging.basicConfig(level=logging.DEBUG)


def checkKubernetes_certs(entry):
    """
    Function to evaluate Kubernetes SSL certificates and renew if needed
    :param entry: from Resources/Kubernetes.txt, e.g. primary host:privileged account:renewal command
    """
    renew = False
    now = datetime.datetime.now()
    timedifftolerance = 5  # certificate renews if expires in 5 days or less
    timetolerance = datetime.timedelta(days=timedifftolerance)
    
    (remotehost, account, renewcommand) = entry.split(':')
    # print(f'{remotehost} {account} {renewcommand}')
    lsf.write_output(f'Checking Kubernetes SSL Certificate expirations on {remotehost}...')
    scriptname = 'checkcerts.sh'
    checkscriptfile = f'/tmp/{scriptname}'
    checkcmd = 'for i in $(ls /etc/kubernetes/pki/*.crt);do openssl x509 -text -noout -in $i | grep "Not After";done'
    # the modern way needed on Windows probably not on LMC
    with io.open(checkscriptfile, "w", newline='\n') as lf: 
        lf.write(f'{checkcmd}\n')
    lf.close()
    lsf.scp(checkscriptfile, f'{account}@{remotehost}:{scriptname}', lsf.password)
    output = lsf.ssh(f'/bin/bash ./{scriptname} 2>&1', f'{account}@{remotehost}', lsf.password)
    # parse the results which cert expires first?
    ctr = 0
    for i in output:
        # hopefully openssl always outputs the expiration date in the same format
        (junk, mdh, mn, secyz) = i.split(':')
        (m, d, h) = mdh.split()
        (sec, y, z) = secyz.split()
        # strptime format is tricky - %b month abbreviation %Y 4 digit year %Z time zone name
        expiration = datetime.datetime.strptime(f'{m}/{d}/{y} {h}:{mn}:{sec} {z}', '%b/%d/%Y %H:%M:%S %Z')
        timediff = expiration - now
        if ctr == 0:
            firsttimediff = timediff
            ctr += 1
        if timediff < firsttimediff:
            firsttimediff = timediff
        # print(f'{firsttimediff} {timetolerance}')
        if firsttimediff < timetolerance:
            lsf.write_output('Expiring certificate. Need to renew!')
            renew = True
            break
        lsf.write_output(f'{expiration} expires in {timediff}')
    
    if renew:
        lsf.write_output(f'Renewing Kubernetes certificates for {remotehost} using {renewcommand}')
        try:
          # this command messes up the terminal for some reason. type "reset" to fix
          output = lsf.ssh(renewcommand, f'{account}@{remotehost}', lsf.password)
        except Exception as e:
          lsf.write_output(f'Could not renew Kubernetes SSL certificates on {remotehost}. {e}')
    else:
        days = firsttimediff.days
        lsf.write_output(f'Kubernetes SSL certificates are good for {days} days on {remotehost}')


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
lsf.write_vpodprogress('Checking Kubernetes', 'GOOD-6', color=color)
kubernetes = []
if 'Kubernetes' in lsf.config['RESOURCES'].keys():
    kubernetes = lsf.config.get('RESOURCES', 'Kubernetes').split('\n')
for line in kubernetes:
    checkKubernetes_certs(line)

