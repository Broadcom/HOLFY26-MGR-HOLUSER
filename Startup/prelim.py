# prelim.py version 1.15 06-April 2025
import sys
import os
import glob
import logging
import datetime
import lsfunctions as lsf
from pathlib import Path

# default logging level is WARNING (other levels are DEBUG, INFO, ERROR and CRITICAL)
logging.basicConfig(level=logging.DEBUG)

# Record whether this is a first run or a LabCheck execution
lsf.test_labcheck()

color = 'red'
if len(sys.argv) > 1:
    lsf.start_time = datetime.datetime.now() - datetime.timedelta(seconds=int(sys.argv[1]))
    if sys.argv[2] == "True":
        lsf.labcheck = True
        color = 'green'
        lsf.write_output(f'{sys.argv[0]}: labcheck is {lsf.labcheck}', logfile=lsf.logfile)   
    else:
        lsf.labcheck = False

# read the /hol/config.ini
lsf.init(router=False)

lsf.write_output(f'Running {sys.argv[0]}', logfile=lsf.logfile)
lsf.write_vpodprogress('PRELIM', 'GOOD-2', color=color)

#
# Copy this file to the /vpodrepo/202?-Labs/2??? folder for your vPod_SKU
# Make your changes after the Core Team code section
# 

#
## Begin Core Team code (please do not edit)
#
if lsf.labtype == "HOL":
    # copy the README.txt from the vpodrepo to the MC if byte count is different and newer
    repo_readme = f'{lsf.vpod_repo}/README.txt'
    mc_readme = f'{lsf.mcdesktop}/README.txt'
    try:
        if os.stat(repo_readme).st_size != os.stat(mc_readme).st_size:
            readme_tdiff = os.path.getmtime(repo_readme) - os.path.getmtime(mc_readme)
            if readme_tdiff > 0:
                lsf.write_output('vPodrepo README is different and newer. Copying to Main Console...')
                os.system(f'cp -p {repo_readme} {mc_readme}')
            elif readme_tdiff < 0:
                lsf.write_output('Changes detected on MC README. Please add to vPodrepo and check in.')
        else:
            lsf.write_output('vPodrepo README and MC have no differences. All good.')
    except Exception as e:
        lsf.write_output(f'Error updating README.txt: {e}')

# prevent the annoying Firefox banner if WMC
if lsf.WMC and lsf.labtype == 'HOL':
    appdata = f'{lsf.mc}/Users/Administrator/AppData'
    ffroamprofiles = f'{appdata}/Roaming/Mozilla/Firefox/Profiles/*.default-release'
    fflocalprofiles = f'{appdata}/Local/Mozilla/Firefox/Profiles/*.default-release'
    os.system(f'rm {ffroamprofiles}/parent.lock > /dev/null 2>&1')
    os.system(f'rm -rf {ffroamprofiles}/storage > /dev/null 2>&1')
    os.system(f'rm -rf {fflocalprofiles}/cache2 > /dev/null 2>&1')
    # and apparently all this is not enough. must also create user.js with disableResetPrompt option
    releasedir = glob.glob(ffroamprofiles)
    resetprompt = 'user_pref("browser.disableResetPrompt", true);'
    userpref = f'{releasedir[0]}/user.js'
    prefneeded = True
    if not os.path.isfile(userpref):
        Path(userpref).touch()
    with open(userpref, 'r') as fp:
        prefs = fp.read()
        for pref in prefs:
            if pref.find('disableResetPrompt'):
                prefneeded = False
                break
    fp.close()
    if prefneeded:
        lsf.write_output(f'need to add {resetprompt} in {userpref}')
        with open(userpref, 'a') as fp:
            fp.write(f'{resetprompt}\n')
        fp.close()

# test an external url to be certain the connection is blocked. The last argument is the timeout.
if lsf.labtype != 'HOL':
    lsf.write_output(f'NOT checking firewall for labtype {lsf.labtype}')
else:
    # check the firewall from the Main Console
    fwok = False
    ctr = 0
    maxctr = 20
    lsf.write_output("Sleeping 60 seconds for holorouter firewall to come up...")
    lsf.labstartup_sleep(60)
    os.system(f'cp {lsf.holroot}/Tools/checkfw.py {lsf.mctemp}')
    output = []
    if lsf.LMC:
        try:
            fwout = lsf.ssh('/usr/bin/python3 /tmp/checkfw.py', 'holuser@console', lsf.password)
            output = fwout.stdout
        except Exception as e:
            lsf.write_output(f'Error ruuning checkfw.py: {e}')
    elif lsf.WMC:
        try:
            output = lsf.runwincmd('python C:\\Temp\\checkfw.py', 'console', 'Administrator', lsf.password, logfile=lsf.logfile)
        except Exception as e:
            lsf.write_output(f'Error ruuning checkfw.py: {e}')
    while 'Good' not in output and ctr < maxctr:
        if lsf.LMC:
            fwout = lsf.ssh('/usr/bin/python3 /tmp/checkfw.py', 'holuser@console', lsf.password)
            output = fwout.stdout
        elif lsf.WMC:
            output = lsf.runwincmd('python C:\\Temp\\checkfw.py', 'console', 'Administrator', lsf.password, logfile=lsf.logfile)        
        for line in output:
            if 'Good' in line:
                fwok = True
                break
        ctr += 1
        if ctr == maxctr:
            lsf.write_output('Firewall is OFF for the Main Console. Failing lab.')
            lsf.labfail('OPEN FIREWALL')        
        lsf.write_output(f'Checking firewall on Main Console. Attempt: {ctr}')
        lsf.write_output(f'firewall output: {output} {ctr}')
        lsf.labstartup_sleep(lsf.sleep_seconds)
    
    if fwok:
        lsf.write_output('Firewall is on for the Main Console.', logfile=lsf.logfile)
    #lsf.test_firewall('https://vmware.com', '<title>', 2)
    lsf.run_command(f'rm {lsf.mctemp}/checkfw.py')

if lsf.WMC and lsf.labcheck == False:   
    # execute the WMCstart script on the WMC to address startup issues
    # Windows console locking and DesktopInfo startup issue on Windows 2019
    admindir = 'Users/Administrator'
    os.system(f'cp {lsf.holroot}/Tools/WMCstartup.ps1 {lsf.mc}/{admindir}/')
    # C:\Program Files\PowerShell\7\pwsh.exe
    command = 'pwsh C:\\Users\\Administrator\\WMCstartup.ps1 > C:\\Users\\Administrator\\WMCstartup.log'
    lsf.write_output('Running WMCstartup.ps1 on console. Please stand by...', logfile=lsf.logfile)
    lsf.runwincmd(command, 'console', 'Administrator', lsf.password, logfile=lsf.logfile)
    with open(f'{lsf.mc}/{admindir}/WMCstartup.log', 'r') as ologfile:
        olog = ologfile.readlines()
    ologfile.close()
    for line in olog:
        lsf.write_output(line.strip(), logfile=lsf.logfile)
    os.system(f'rm {lsf.mc}/{admindir}/WMCstartup.ps1')
    os.system(f'mv {lsf.mc}/{admindir}/WMCstartup.log /tmp')

# BEGIN ODYSSEY RESET CODE
#
# Odyssey Variables
#

# LMC or WMC
if lsf.WMC:
    desktop = '/Users/Administrator/Desktop'
    ody_shortcut = 'Play VMware Odyssey.lnk'
    odyssey_app = 'odyssey-launcher.exe'
    # legacy most likely not needed
    # odysseyEXE = 'odyssey-launcher.exe'
    odyssey_dst = '/Users/Administrator'
elif lsf.LMC:
    desktop = '/home/holuser/Desktop'
    ody_shortcut = 'launch_odyssey.desktop'
    odyssey_app = 'odyssey-client-linux.AppImage'
    odyssey_launcher = 'odyssey-launch.sh'
    odyssey_dst = f'desktop-hol'
    lmcuser = 'holuser@console'

# on initial boot remove the Odyssey files if present
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

#
## End Core Team code
#

#        
# Insert your code here using the file in your vPod_repo
#

# fail like this
#now = datetime.datetime.now()
#delta = now - lsf.start_time
#lsf.labfail('PRELIM ISSUE', delta)
#exit(1)

lsf.write_output(f'{sys.argv[0]} finished.', logfile=lsf.logfile) 
exit(0)

