# lsfunctions.py - version v2.5 - 07-April 2025
# implementing standard naming, removing unneeded legacy code and simplifying where possible

import os
import subprocess
import errno
import socket
import requests
import datetime
import time
import fileinput
import glob
import shutil
import sys
import urllib3
import logging
import json
import psutil
import re
from pathlib import Path
from ipaddress import ip_network, ip_address
from pyVim import connect
from pyVmomi import vim
from pyVim.task import WaitForTask
from xml.dom.minidom import parseString
from pypsexec.client import Client
from requests.auth import HTTPBasicAuth
from configparser import ConfigParser

# default logging level is WARNING (other levels are DEBUG, INFO, ERROR and CRITICAL)
logging.basicConfig(level=logging.WARNING)
# until the SSL cert issues are resolved...
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# static variables
sleep_seconds = 5
labcheck = False

home = '/home/holuser'
holroot = f'{home}/hol' # local to the Manager

bad_sku = 'HOL-BADSKU'
lab_sku = bad_sku
configname = 'config.ini'
configini = f'/tmp/{configname}'
creds = f'{home}/creds.txt'
router = 'router.site-a.vcf.lab'
proxy = 'proxy.site-a.vcf.lab'
XAUTHORITY = ''

if os.path.isfile(configini):
    # Read the latest config.ini file to set globals
    config = ConfigParser()
    config.read(configini)
    lab_sku = config.get('VPOD', 'vPod_SKU')
    lab_year = lab_sku[4:6]
    lab_num = lab_sku[6:8]
    vpod_repo = f'/vpodrepo/20{lab_year}-labs/{lab_year}{lab_num}'

# write to both holroot and mcholroot from the Manager
logfile = 'labstartup.log'

# LMC or WMC
LMC = False
WMC = False
lmcholroot = '/lmchol/hol' # NFS / mount from LMC
wmcholroot = '/wmchol/hol' # CIFS administrative mount from WMC
# since this loads very early in the Manager boot, wait for mount to complete
while True:
    if os.path.isdir(lmcholroot):
        LMC = True
        mc = '/lmchol'
        mcholroot = lmcholroot
        mctemp = f'{mc}/tmp'
        mcdesktop = f'{mc}/home/holuser/Desktop'
        desktop_config = '/lmchol/home/holuser/desktop-hol/VMware.config'
        logfiles = [f'{holroot}/{logfile}', f'{mcholroot}/{logfile}']
        red = '${color red}Lab Status'
        green = '${color green}Lab Status'
        break
    elif os.path.isdir(wmcholroot):
        WMC = True
        mc = '/wmchol'
        mcholroot = wmcholroot
        mcdesktop = f'{mc}/Users/Administrator/Desktop'
        mctemp = f'{mc}/Temp'
        desktop_config = '/wmchol/DesktopInfo/desktopinfo.ini'
        logfiles = [f'{holroot}/{logfile}', f'{mcholroot}/{logfile}']
        red = '3A3AFA'
        green = '55CC77'
        break

resource_file_dir = f'{holroot}/Resources'
startup_file_dir = f'{holroot}/Startup'
lab_status = f'{mcholroot}/startup_status.txt'
mcversionfile = f'{mcholroot}/version.txt'
versiontxt = ''
max_minutes_before_fail = 60
ready_time_file = f'{mcholroot}/readyTime.txt'
start_time = datetime.datetime.now()
vc_boot_minutes = datetime.timedelta(seconds=(10 * 60))
vcuser = 'administrator@vsphere.local'
linuxuser = 'root'
vsphereaccount = 'administrator@vsphere.local'
sis = []  # all vCenter session instances
# EXPERIMENTAL
sisvc = {} # dictionary to hold all vCenter/ESXi session instances indexed by host name
sshpass = '/usr/bin/sshpass'
vmtoolsd = shutil.which('vmtoolsd')
# TODO: figure out autolab
autolab = '/media/cdrom0/autolab.ps1'
cd = '/media/cdrom0'
mm = ''
vlp_tenant = ''
vlp_urn = ''
os.umask(0o0002)
odyssey = False

# default proxies entries
proxies = {
    "http": "http://proxy:3128",
    "https": "http://proxy:3128"
}

def init(**kwargs):
    """
    Add any initial operations here.
    Read the /hol/Resources/Configuration.txt file to set globals:
    lab_sku - required for AutoLabStatus
    max_minutes_before_fail - used in labstartu_sleep to fail prepop if not ready before max time
    labcheckinterval - either 1 or 2 hours must be longer than max_minutes_before_fail
    **kwargs: logfile to use
    """
    global start_time
    global labtype
    global lab_sku
    global password
    global vsphereaccount
    global proxies
    global max_minutes_before_fail
    global odyssey
    global labcheckinterval
    global versiontxt
    global XAUTHORITY
     
    lfile = kwargs.get('logfile', logfile)
    chkrouter = kwargs.get('router', True)
    start_time = datetime.datetime.now()
    password = getfilecontents(creds).strip()
    
    if lab_sku == bad_sku:
        labtype = 'HOL'
        return
    
    if os.path.isfile(mcversionfile):
        versiontxt = getfilecontents(mcversionfile)
    
    # get the config.ini variables
    if 'labtype' in config['VPOD'].keys():
        labtype = config.get('VPOD', 'labtype')
    else:
        labtype = 'HOL'
    if 'vsphereaccount' in config['VPOD'].keys():
        vsphereaccount = config.get('VPOD', 'vsphereaccount').split('\n')
    else:
        vsphereaccount = 'administrator@vsphere.local'
    if 'maxminutes' in config['VPOD'].keys():
        max_minutes_before_fail = int(config.get('VPOD', 'maxminutes'))
    else:
        max_minutes_before_fail = 60   
    if 'labcheckinterval' in config['VPOD'].keys():
        labcheckinterval = int(config.get('VPOD', 'labcheckinterval'))
    else:
        labcheckinterval = 60
    if 'odyssey' in config['VPOD'].keys():
        if config.get('VPOD', 'odyssey').casefold() == 'true'.casefold():
            odyssey = True
    
    # get the XAUTHORITY
    if LMC:
       XAUTHORITY=getfilecontents(f'{mc}/tmp/XAUTHORITY')
    
    # check the router if indicated
    if chkrouter:
        # verify proxy resolves in DNS
        while True:
            if WMC:
                write_output('Clearing DNS Server cache on Main Console.')
                runwincmd('dnscmd /clearcache', 'console', 'Administrator', password)
            res = os.system('/usr/bin/nslookup proxy')
            if res != 0:
                write_output(f'Waiting for DNS to resolve {proxy} - pause 30 seconds...')
                labstartup_sleep(30)
            else:
                write_output(f'{proxy} resolves in DNS now.')
                break
        # wait for the proxy to start
        while not test_tcp_port(proxy, 3128, logfile=lfile):
            write_output(f'Waiting for proxy on {proxy}...', logfile=lfile)
            labstartup_sleep(sleep_seconds)

        # wait for the router to be ready - remove date command not needed really
        """
        lcmd = 'date'
        while True:
            logging.debug(f'Running date commnand on holuser@{router}')
            result = ssh(lcmd, f'holuser@{router}', password)
            if "UTC" in result.stdout:
                break
            labstartup_sleep(sleep_seconds)
        write_output("Router appears responsive now.", logfile=lfile)
        """
  

def test_firewall(url, pattern, timeout):
    """
    open firewall test just in case
    :param url: the url to test that should be blocked
    :param pattern: the pattern for test_url to check
    :param timeout: seconds to try before connection timeout
    """
    write_output('Testing firewall...')
    ctr = 0
    while ctr < 5:
        if test_url(url, pattern, no_proxy=True, timeout=timeout):
            write_output('Waiting for firewall to close...')
            labstartup_sleep(sleep_seconds)
        else:
            write_output("Firewall is good.")
            return True
        ctr = ctr + 1
    write_output('FAIL: Firewall is open.')
    labfail('OPEN FIREWALL')

def parse_labsku(sku):
    """
    sets the lab_sku which is used to report vPod status
    writes the /hol/labname.txt for desktop display
    if bad SKU, updates vpodprogress which fails the lab. Captain needs to define
    :param sku: the sku to check
    """
    global lab_sku
    lab_sku = sku
    line: str
    flag = False
    lmcmatch = 'notset'
    wmcmatch = 'notset'
    if LMC:
        base = '${font weight:bold}${color0}${alignc}'
        lmcmatch = 'labname DO NOT CHANGE THIS LINE'
    elif WMC:
        base = 'COMMENT=active:1,interval:60,color:FFFFFF,style:b,text:'
        wmcmatch = base
    
    display_line = f'{base}{lab_sku}\n'

    if sku == bad_sku:
        write_output(f'BAD SKU: {sku}')        
        write_output(f'LabStartup script on the Manager VM has not been implemented yet.')
        write_output(f'Please ask for assistance if you need it.')
        write_vpodprogress('Implement LabStartup', 'FAIL-1')
        return
    else:
        write_vpodprogress('Not Ready', 'STARTING')
    
    tempfile = open(desktop_config, 'r+')
    for line in fileinput.input(desktop_config):
        if flag:
            tempfile.write(display_line)
            flag = False
        elif lmcmatch in line:  # update the next line
            flag = True
            tempfile.write(line)
        elif wmcmatch in line:  # update this line
            tempfile.write(display_line)
        else:
            tempfile.write(line)
    tempfile.close()
    if LMC:
        ssh(f'export XAUTHORITY={XAUTHORITY};pkill conky;/home/holuser/.conky/conky-startup.sh', 'holuser@console', password)


def postmanfix():
    """
    prevent Postman upgrades
    """
    if WMC:
        hostpath = '/wmchol/Windows/System32/drivers/etc/hosts'
        el = '\r\n'
    elif LMC:
        hostpath = '/lmchol/etc/hosts'
        el = '\n'

    sp = '         '
    hostlines = [f'0.0.0.0{sp}dl.pstmn.io{el}',
                 f'0.0.0.0{sp}sync-v3.getpostman.com{el}',
                 f'0.0.0.0{sp}getpostman.com{el}',
                 f'0.0.0.0{sp}go.pstmn.io{el}']

    hostscontents = getfilecontents(hostpath)

    if '0.0.0.0' not in hostscontents:
        write_output('Updating hosts file to prevent Postman upgrade.')
        if LMC:
            localhosts = '/tmp/hosts'
            run_command(f'cp {hostpath} {localhosts}')
            hostpath = localhosts
        
        hfile = open(hostpath, 'a')
        hfile.writelines(hostlines)
        hfile.close()
    
        if LMC:
            scp(localhosts, 'root@console:/etc/hosts', password)


def run_command(cmd):
    """
    convenience function to run a shell command and return the output.
    :param: run: the command to run locally
    """
    #print(cmd)
    run = subprocess.CompletedProcess
    run.stdout = ''
    rcmdlist = cmd.split()
    try:
        run = subprocess.run(rcmdlist, capture_output=True, text=True, check=True)
    except Exception as e:
        if hasattr(run, 'stderr'):
            write_output(f'{run.stdout} {run.stderr} {e}')
        else:
            write_output(f'Exception {e}')
        return e
    return run


def test_ping(host):
    """
    convenience function to ping host 3 times until lab timeout
    :param: host: string - the host name or IP to ping
    return pass fail
    """
    res = subprocess.Popen(['ping', '-c', '3', host], stdout=subprocess.DEVNULL).wait()
    while not res == 0:
        write_output(f'Unable to ping {host}')
        labstartup_sleep(sleep_seconds)
        res = subprocess.Popen(['ping', '-c', '3', host], stdout=subprocess.DEVNULL).wait()
    write_output('Sucessfully pinged ' + host)
    return True


def test_labcheck():
    """
    if sys.argv[1] to labstartup.py is "labcheck", then this is a subsequent run
    if idle time is less than the labcheck interval, delete the  at job and exit
    """
    global labcheck
    mouseaction = f'{mcholroot}/mouseaction'

    # clear out the holuser labcheck job so it won't run during active labstartup
    clear_atq()
    
    if len(sys.argv) == 1:
        labcheck = False
        return False
    if sys.argv[1] == 'labcheck':
        write_output("LabCheck is active.")
        labcheck = True  
    if os.path.exists(mouseaction) and labcheck:
        write_output('input detected - labcheck will not run again')
        # clear out the holuser labcheck job
        clear_atq()
        exit(0)


def start_autolab():
    if labcheck:
        write_output('Labcheck is active. Skipping start_autolab')
        return False
    if os.path.exists(autolab):
        write_output('Executing ' + autolab)
        write_vpodprogress('Ready: Executing ' + autolab, 'AUTOLAB')
        # start a shell executing autolab
        os.system('/usr/bin/pwsh ' + autolab)
        write_vpodprogress('Finished with ' + autolab, 'AUTOLAB')
        return True
    return False


def set_status_color(color):
    """
    change the Conky desktop status color
    """
    tempfile = open(desktop_config, 'r+')
    line: str
    for line in fileinput.input(desktop_config):
        if 'Lab Status' in line and color not in line:
            if color == 'red':
               updline = line.replace(green, red)
            elif color == 'green':
                updline = line.replace(red, green)
            tempfile.write(updline)
        else:
            tempfile.write(line)
    tempfile.close()
    if LMC:
        ssh(f'export XAUTHORITY={XAUTHORITY};pkill conky;/home/holuser/.conky/conky-startup.sh', 'holuser@console', password)


def write_vpodprogress(display, code, **kwargs):
    """
    :param display: the message to display on the desktop
    :param code: the lab status code
    """
    global labcheck
    color = kwargs.get('color', 'red')
    # print(color)
    if code == 'STARTING' and labcheck:
        code = 'LABCHECK'
    if labcheck:
        if code != 'LABCHECK' and code != 'READY':
            write_output(f'LABCHECK: bumping {code} to LC-{code}')
            code = f'LC-{code}'
    if code == 'READY':
        # let the router know.
        os.system('echo "" > /tmp/ready')
        scp('/tmp/ready', f'holuser@{router}:/tmp/holorouter', password)
    now = datetime.datetime.now()
    if 'FAIL' in code or 'TIMEOUT' in code:
        if 'fail' not in display.lower():
            display = f'FAIL {display}'
    message = display + ' ' + now.strftime("%m/%d %H:%M")
    if not labcheck:
        with open(lab_status, "w") as f:
            f.write(message)
            f.close()
        
        set_status_color(color)

    if 'FAIL' in code or 'TIMEOUT' in code:
        write_output('FAILING vPod. Exit...')
        # clear out the holuser labcheck job
        clear_atq()
        exit(1)


def write_output(content, **kwargs):
    """
    convenience function to add the current date time formatted per US convention
    :param content: the message to be printed
    **kwargs: logfile to use
    :return: no return
    """
    lfile = kwargs.get('logfile', logfile)
    now = datetime.datetime.now()
    nowfmt = now.strftime("%m/%d/%Y %H:%M:%S")
    out = f'{nowfmt} {content}'
    # if lfile not in logfiles:
    #    with open(lfile, "a") as lf:
    #        lf.write(f'{out}\n')
    #        lf.close()
    for log in logfiles:
        # print(f'writing to {log}')
        with open(log, "a") as lf:
            lf.write(f'{out}\n')
            lf.close()


def choose_file(folder, name, ext):
    """
    Return HOL file based on original vPod or git update.
    :param folder: str - the vPod folder of the original file
    :param name: str - the name of the HOL file to check
    :param name: ext - the extension (typically txt or py)
    :return: the file path to use
    """    
    filename = f'{name}.{ext}'
    filepath = f'{holroot}/{folder}/{filename}'

    gitfilepath = os.path.join(vpod_repo, filename)
    gitfilepath2 = os.path.join(f'{vpod_repo}/Startup', filename)
    origfilepath = os.path.join(folder, filename)
    if os.path.exists(gitfilepath):
        filepath = gitfilepath
    elif os.path.exists(gitfilepath2):
        filepath = gitfilepath2
    elif os.path.exists(origfilepath):
        filepath = origfilepath
    return filepath


def read_file_into_dict(resource_name, **kwargs):
    """
    Return HOL resources read from file based on resource name.
    Excludes commented and blank lines
    :param resource_name: str - the name of the HOL resource file to read
    :return: res_dict - the dictionary
    """
    res_list = {}
    wait = kwargs.get('wait', False)
    if wait:
        filepath = choose_file(resource_file_dir, resource_name, "txt")
    else:
        filepath = f'{resource_file_dir}/{resource_name}.txt'
    
    try:
        res_dict = {}
        with open(filepath) as f:
            for line in f:
                if not (line.startswith('#') or line.startswith('\n')):
                    # print(line.rstrip())
                    (key, val) = line.split(':')
                    val = val.strip()
                    res_dict[key] = val
        f.close()
        return res_dict
    except OSError as e:
        write_output(f'Cannot read {filepath}: {e}')


def read_file_into_list(resource_name, **kwargs):
    """
    Return HOL resources read from file based on resource name.
    Excludes commented and blank lines
    :param resource_name: str - the name of the HOL resource file to read
    :return: res_list - the lines of the HOL resources in resource_name file
    """
    res_list = []
    wait = kwargs.get('wait', True)
    if wait:
        filepath = choose_file(resource_file_dir, resource_name, "txt")
    else:
        filepath = f'{resource_file_dir}/{resource_name}.txt'
    
    try:
        res_list = []
        with open(filepath) as f:
            for line in f:
                if not (line.startswith('#') or line.startswith('\n')):
                    # print(line.rstrip())
                    res_list.append(line.rstrip())
        f.close()
        return res_list
    except OSError as e:
        write_output(f'Cannot read {filepath}: {e}')


def test_tcp_port(server, port, **kwargs):
    """
    attempt a socket connection to the host on the port
    :param server:
    :param port:
    **kwargs: logfile to use
    :return: boolean, true it connection is sucessful
    """
    lfile = kwargs.get('logfile', logfile)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect((server, int(port)))
        s.shutdown(2)
        write_output(f'Successfully connected to {server} on port ' + str(port), logfile=lfile)
        return True
    except IOError:
        return False


def connect_vcenters(entries):
    """
    param entries: list of vCenter entries from config.ini
    """
    for entry in entries:
        vc = entry.split(':')
        write_output('Connecting to ' + vc[0] + '...')
        vc_type = vc[1]
        if len(vc) == 3:
            login_user = vc[2]
        else:
            login_user = vcuser
        test_ping(vc[0])
        if vc_type == 'esx':
            login_user = 'root'

        while not connect_vc(vc[0], login_user, password):
            labstartup_sleep(sleep_seconds)

        if type == 'linux':
            write_output('Starting vsphere-ui')
            run_command(f'ssh root@{vc[0]} service-control --start vsphere-ui')


def connect_vc(server, user, userpass):
    """
    connect to the specified vCenter with the specified credentials
    :param: server: the vCenter server for the connection attempt
    :parmam: user: the user for the connection
    :param: userpass: the password to use for the connection
    """
    global sis
    global sisvc
    # print(f'server:{server} user:{user} userpass:{userpass}')
    try:
        # connect without verifying the SSL certificate. Easier for Core Team and Captains
        try:
            # pyVmomi 7.0
            vc_si = connect.SmartConnectNoSSL(host=server, port=443, user=user, pwd=userpass)
        except:
            # pyVmomi 8.0
            vc_si = connect.SmartConnect(host=server, port=443, user=user, pwd=userpass, disableSslCertValidation=True)
        sis.append(vc_si)
        sisvc[server] = vc_si
        write_output('Connected to ' + server)
        return True
    except Exception as e:
        write_output('Exception: ' + str(e))
        return False


def get_all_objs(si_content: object, vimtype: object) -> object:
    """
    Method that populates objects of type vimtype such as
    vim.VirtualMachine, vim.HostSystem, vim.Datacenter, vim.Datastore, vim.ClusterComputeResource
    :param si_content serviceinstance.content
    :param vimtype VIM object type name
    """
    obj = {}
    container = si_content.viewManager.CreateContainerView(si_content.rootFolder, vimtype, True)
    for managed_object_ref in container.view:
        obj.update({managed_object_ref: managed_object_ref.name})
    return obj


def get_all_option_managers():
    """
    Convenience function to return all OptionManager objects
    return list of vim.option.OptionManager
    """
    all_oms = []
    for si in sis:
        om = si.content.setting
        # noinspection PyTypeChecker
        all_oms.append(om)
    return all_oms


def get_all_vms():
    """
    Convenience function to return all VMs
    return list of vim.VirtualMachine
    """
    all_vms = []
    for si in sis:
        vms = get_all_objs(si.content, [vim.VirtualMachine])
        # noinspection PyTypeChecker
        for vm in vms:
            all_vms.append(vm)
    return all_vms


def get_all_clusters():
    """
    Convenience function to return all VMs
    return list of vim.ClusterComputeResource
    """
    all_clusters = []
    for si in sis:
        clusters = get_all_objs(si.content, [vim.ClusterComputeResource])
        # noinspection PyTypeChecker
        for cluster in clusters:
            all_clusters.append(cluster)
    return all_clusters


def get_cluster(cs_name):
    """
    convenience function to retrieve a cluster by name
    :param: cs_name string - the name of the cluster to return
    :return vim.ClusterComputeResource
    """
    clusters = get_all_clusters()
    for cluster in clusters:
        if cluster.name == cs_name:
            return cluster


def enable_drs(cs):
    """
    convenience function to enable DRS on a cluster
    :param: cs vim.ClusterComputeResource
    :return: True/Fail
    """
    cluster_spec = vim.cluster.ConfigSpecEx()
    drs_info = vim.cluster.DrsConfigInfo()
    drs_info.enabled = True
    cluster_spec.drsConfig = drs_info
    try:
        task = cs.ReconfigureComputeResource_Task(cluster_spec, True)
        WaitForTask(task)
        return True
    except Exception as e:
        write_output(f'Exception: {e} {cs.name}' + str(e))
        return False


def get_datastore(ds_name):
    """
    convenience function to retrieve a datastore by name
    :param: ds_name string - the name of the datastore to return
    :return vim.Datastore
    """
    for si in sis:
        datastores = get_all_objs(si.content, [vim.Datastore])
        # noinspection PyTypeChecker
        for datastore in datastores:
            if datastore.name == ds_name:
                return datastore


def get_all_hosts():
    """
    convenience function to retrieve all ESX host systems
    return: list of vim.HostSystem
    """
    all_hosts = []
    for si in sis:
        hosts = get_all_objs(si.content, [vim.HostSystem])
        # noinspection PyTypeChecker
        for host in hosts:
            if 'VMware Mobility Agent' not in host.summary.hardware.model:
                all_hosts.append(host)
            labstartup_sleep(1)
    return all_hosts


def get_host(name):
    """
    convenience function to retrieve the VM named from all session content
    :param: name: string the name of the VM to retrieve
    """
    for si in sis:
        hosts = get_all_objs(si.content, [vim.HostSystem])
        for host in hosts:
            if host.name == name:
                return host


# EXPERIMENTAL
def get_vm(name, **kwargs):
    """
    convenience function to retrieve the VM named from a specific session
    :param: name: string the name of the VM to retrieve
    :param: vc: the session to use
    """
    vc = kwargs.get('vc', '')
    vmlist = []
    if vc:
        vms = get_all_objs(sisvc[vc].content, [vim.VirtualMachine])
    else:
        for si in sis:
            vms = get_all_objs(si.content, [vim.VirtualMachine])
    for vm in vms:
        if vm.name == name:
            vmlist.append(vm)
    return vmlist


def get_vm_match(name):
    """
    convenience function to retrieve the VM named from all session content
    :param: name: string the name of the VMs to retrieve (including wildcard)
    """
    pattern = re.compile(name, re.IGNORECASE)
    vmsreturn = []
    for si in sis:
        vms = get_all_objs(si.content, [vim.VirtualMachine])
        for vm in vms:
            match = pattern.match(vm.name)
            if match:
                vmsreturn.append(vm)
    return vmsreturn


def get_vapp(name, **kwargs):
    """
    convenience function to retrieve the vApp named from all session content
    :param: name: string the name of the vApp to retrieve
    """
    vc = kwargs.get('vc', '')
    valist = []
    if vc:
        vapps = get_all_objs(sisvc[vc].content, [vim.VirtualApp])
    else:
        for si in sis:
            vapps = get_all_objs(si.content, [vim.VirtualApp])
    for vapp in vapps:
            if vapp.name == name:
                valist.append(vapp)
    return valist

def reboot_hosts():
    """
    To deal with NFS mount timing issues reboot all ESXi hosts.
    """
    hosts = get_all_hosts()
    for host in hosts:
        write_output(f'Rebooting host {host.name} ...')
        task = host.RebootHost_Task(True)
        labstartup_sleep(1)
        
    # test for tcp port 22 failure
    write_output(f'Waiting for hosts to stop responding...')
    for host in hosts:
        while test_tcp_port(host.name, 22):
            labstartup_sleep(sleep_seconds)
        
    # now test for port 22 connection
    write_output(f'Waiting for hosts to begin responding...')
    for host in hosts:
        while not test_esx(host.name):
            write_output(f'Unable to test {host.name}. Will try again...')
            labstartup_sleep(sleep_seconds)

 
def check_datastore(entry):
    """
    for the /hol/Resources/Datastores.txt entry, checks accessible and counts the files
    if VMFS (typical) has all ESX host systems rescan their HBAs
    if NFS verify accessible and if not reboot ESXi hosts to work around timing issues
    :entry: string colon-delimited entry from Datastores in config.ini
    :return: True or False
    """
    (server, datastore_name) = entry.split(':')
    write_output(f'Checking {datastore_name}...')
    while True:
        try:
            ds = get_datastore(datastore_name)
            if ds.summary.type == 'VMFS' or 'NFS' in ds.summary.type or ds.summary.type == 'vsan':
                break
        except Exception as e:
            write_output(f'Exception checking datastores on {server}')
            write_output(f'Exception: {e}', logfile='/tmp/lsterrors.log')
        print(ds.summary.type)
        labstartup_sleep(sleep_seconds)

    if ds.summary.type == 'VMFS':
        try:
            hosts = get_all_hosts()
        except Exception as e:
            print(f'exception: {e}')
        for host in hosts:
            write_output(f'Checking datastores on {host.name}...')
            while True:
                try:
                    host_ss = host.configManager.storageSystem
                    host_ss.RescanAllHba()
                    break
                except Exception as e:
                    if 'Licenses' in e.args[0]:
                        write_output(f'Waiting for License Service to start before datastore check on {host.name}')
                    else:
                        write_output(f'Exception checking datastores on {host.name}')
                        write_output(f'Exception: {e}', logfile='/tmp/lsterrors.log')
                labstartup_sleep(sleep_seconds)
    elif 'NFS' in ds.summary.type:
        # get all VMs and reboot ESXi hosts if any are inaccessible
        # this typically happens because the ESXi hosts boot faster than the NFS storage appliance
        # re-mounting the NAS datastore does not work because there is no way to unmount first
        # reboot the ESXi hosts then wait for the NFS datastore to be accessible
        
        vms = get_all_vms()
        for vm in vms:
            check = False
            for dsuse in vm.storage.perDatastoreUsage:
                if dsuse.datastore.name == ds.name:
                    check = True
                    break         
            if vm.runtime.connectionState == 'inaccessible' and check:
                write_output(f'{vm.name} is inaccessible.')
                reboot_hosts()
                break
        
        # wait for the NFS datastore to mount
        while not ds.summary.accessible:
            write_output('Waiting for NFS datastore to mount...')
            labstartup_sleep(sleep_seconds)
   
    if ds.summary.accessible:
        ds_browser = ds.browser
        spec = vim.host.DatastoreBrowser.SearchSpec(query=[vim.host.DatastoreBrowser.FolderQuery()])
        task = ds_browser.SearchDatastore_Task("[%s]" % ds.name, spec)
        WaitForTask(task)
        if len(task.info.result.file):
            write_output(f'Datastore {datastore_name} on {server} looks ok.')
            return True
        else:
            write_output(f'Datastore {datastore_name} on {server} has no files but is accessible.')
            return True
    else:
        write_output(f'Datastore {datastore_name} on {server} is unavailable.')
        return False


def start_nested(records):
    """
    Start all the nested vApps or VMs in the records list passed in
    :param: records: list of vApps or VMs to start. Format is documented in /hol/Resources/vApps.txt or VMs.txt
    """
    if not len(records):
        write_output('no records')
        return

    for record in records:
        p = record.split(':')
        e_name = p[0]
        vc_name = p[1]
        if 'pause' in e_name.lower():
            if labcheck:
                continue
            write_output(f'pausing {p[1]} seconds...')
            labstartup_sleep(int(p[1]))
            continue

        va = get_vapp(e_name, vc=vc_name)
        vms = get_vm(e_name, vc=vc_name)
        if not vms:
            vms = get_vm_match(e_name)
        if not vms:
            write_output(f'Unable to find entity {e_name}')
            continue
        for vm in vms:
            if va:
                good_power = 'started'
                if va.summary.vAppState == good_power:
                    write_output(f'{va.name} already powered on.')
                    continue
                e_type = 'vApp'
                entity = va
            elif vm:
                good_power = 'poweredOn'
                if vm.runtime.powerState == good_power:
                    write_output(f'{vm.name} already powered on.')
                    continue
                e_type = 'vm'
                entity = vm
            else:
                write_output(f'Unable to find entity {e_name}')
                continue
            write_output(f'Attempting to power on {e_type} {entity.name}...')
            while True:
                if e_type == 'vm':
                    check = False
                    for dsuse in entity.storage.perDatastoreUsage:
                        if 'NFS' in dsuse.datastore.summary.type:
                            check = True
                            break
                    if entity.runtime.connectionState == 'inaccessible' and check:
                        write_output(f'{vm.name} is inaccessible. Rebooting hosts...')
                        reboot_hosts()
                    while entity.runtime.connectionState != "connected":
                        write_output(f'Unable to power on. Connection state for {entity.name}'
                                     f' is {entity.runtime.connectionState}. ')
                        labstartup_sleep(sleep_seconds)
                    try:
                        task = entity.PowerOnVM_Task()
                    except Exception as e:
                        write_output(f'Unable to power on {entity.name} - skipping.')
                        break
                else:
                    task = entity.PowerOnVApp_Task()
                write_output(f'task state is {task.info.state}')
                if e_type == 'vm':
                    while task.info.progress is not None:
                        write_output(f'Waiting for task to complete {task.info.progress}%...')
                        labstartup_sleep(sleep_seconds)
                        vm = get_vm(e_name)
                        write_output(f'{vm.name} power state is {vm.runtime.powerState}.')
                        if vm.runtime.powerState == good_power:
                            write_output(f'{vm.name} is powered on.')
                            break
                if e_type == 'vApp':
                    while True:
                        va = get_vapp(e_name)
                        if va.summary.vAppState == good_power:
                            write_output(f'{va.name} is powered on.')
                            break
                        else:
                            write_output(f'Waiting for {va.name} to power on. ...')
                            if task.info.error:
                                write_output(task.info.error.msg)
                            labstartup_sleep(sleep_seconds)
                break


def clear_host_alarms():
    filter_spec = vim.alarm.AlarmFilterSpec(status=[], typeEntity='entityTypeAll', typeTrigger='triggerTypeAll')
    for si in sis:
        alarm_mgr = si.content.alarmManager
        alarm_mgr.ClearTriggeredAlarms(filter_spec)


def get_network_adapter(vm_obj):
   """
   Return a list of networks adapters for the VM
   :param vm_obj: the VM to use
   """
   net_adapters= []
   for dev in vm_obj.config.hardware.device:
        if isinstance(dev, vim.vm.device.VirtualEthernetCard):
            net_adapters.append(dev)
   return net_adapters


def set_network_adapter_connection(vm_obj, adapter, connect):
   """
   Function to connect or disconnect a VM network adapter
   :param adapter: the VM virtual network adapter
   :param connect: True or False the desired connection state
   """
   adapter_spec = vim.vm.device.VirtualDeviceSpec()
   adapter_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
   adapter_spec.device = adapter
   adapter_spec.device.key = adapter.key
   adapter_spec.device.macAddress = adapter.macAddress
   adapter_spec.device.backing = adapter.backing
   adapter_spec.device.wakeOnLanEnabled = adapter.wakeOnLanEnabled
   connectable = vim.vm.device.VirtualDevice.ConnectInfo()
   connectable.connected = connect
   connectable.startConnected = connect
   adapter_spec.device.connectable = connectable
   dev_changes = [adapter_spec]
   spec = vim.vm.ConfigSpec()
   spec.deviceChange = dev_changes
   task = vm_obj.ReconfigVM_Task(spec=spec)


def check_proxy(u):
    """
    returns True if url is outside the vPod and False otherwise
    :param: u: the url to check for proxy use
    """
    status = 'good'
    ip_tst = ''
    proxy = True
    nets = ['192.168.0.0/16', '172.16.0.0/12', '10.0.0.0/8', '127.0.0.0/8']
    j = u.split('/')
    if j[2].find(':') == -1:  # no port number so assume 443
        name = str(j[2])
    else:
        p = j[2].split(':')  # in case there is a port number
        name = str(p[0])
    ctr = 0
    while ctr < 10:
        try:
            ip_tst = ip_address(socket.gethostbyname(name))
            status = 'good'
            break
        except Exception as e:
            write_output('Exception: ' + str(e) + ': ' + name)
            status = str(e)
        ctr += 1
        labstartup_sleep(sleep_seconds)
    if 'not known' in status:
        write_output('Cannot reach external DNS. Failing the lab.')
        write_vpodprogress('DNS Failure', 'FAIL-1')
        return False

    for net in nets:
        range_tst = ip_network(net)
        if ip_tst in range_tst:
            proxy = False
    return proxy

def test_esx(esxhname):
    write_output(f'Testing port 22 on {esxhname}')
    ctr = 0
    maxctr = 30
    while not test_tcp_port(esxhname, 22):
        if ctr > maxctr:
            write_output(f'Cannot connect to {esxhname} on port 22 after {maxctr} attempts. FAIL')
            return False
        ctr += 1
        write_output(f'Cannot connect to {esxhname} on port 22. Will try again.')
        labstartup_sleep(sleep_seconds)
    return True


def test_url(url, **kwargs):
    """
    check that the pattern is present in the page returned from a get to url
    :param url: the site from which to get content
    **kwargs: pattern: the pattern to find in the page as text
              not_ready: optional pattern if present means not ready
              verbose: display the html
              no_proxy: for testing open firewall, do not use a proxy
              timeout: seconds before timeout exception
    :return:
    """
    pattern = kwargs.get('pattern', '')
    not_ready = kwargs.get('not_ready', None)
    no_proxy = kwargs.get('no_proxy', None)
    timeout = kwargs.get('timeout', 5)
    verbose = kwargs.get('verbose', None)
    # get errors on some sites 'dh key too small'
    # 12/11/2024 with Python 3.12 DEFAULT_CIPHERS is not available. commenting out.
    #requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += 'HIGH:!DH:!aNULL'
    try:
        if verbose:
            print('testing', url)
            write_output(f'testing {url}')
        if check_proxy(url):
            if no_proxy:
                # need to explicitly specify NO proxy
                session = requests.Session()
                session.trust_env = False
                try:
                    r = session.get(url, verify=False, timeout=timeout)
                except Exception as e:
                    write_output(f'Testing firewall. No access is good. {e}')
                    return False
            else:
                r = requests.get(url, proxies=proxies, timeout=timeout)
        else:
            # need to explicitly specify NO proxy
            session = requests.Session()
            session.trust_env = False
            r = session.get(url, verify=False)
    except Exception as e:
        write_output(f'Exception: {e}')
        return False

    if verbose:
        print(r.text)
        write_output(r.text)
    if pattern == '':
        if r.status_code == 200:
            write_output(f'Received HTTP response code {r.status_code} for {url}')
            return True
        else:
            write_output(f'Received HTTP response code {r.status_code} for {url}')
            return False
    if not_ready and r.text.find(not_ready) > -1:
        write_output(f'Connected to: {url} but found not ready pattern: {not_ready}')
        return False
    if r.text.find(pattern) == -1:
        write_output(f'Connected to: {url} but did NOT find pattern {pattern}')
        return False
    else:
        write_output(f'Success: Found pattern {pattern} in {url}')
        return True


def clear_atq():
    """
    clear out all at jobs (we only want a single at job for holuser)
    """
    result = run_command("atq")
    joblist = result.stdout.split('\n')
    for atjobline in joblist:
        atjob = atjobline.split()
        try:
            run_command(f'at -r {atjob[0]}')
        except:
           pass


def create_labcheck_task():
    """
    Uses labcheckinterval - default is 60
    Creates an "at" scheduled job to run once
    """
    clear_atq()
    # run next labcheck in labcheckinterval minutes from now
    if get_cloudinfo() != 'NOT REPORTED':
        now = datetime.datetime.now()
        labcheckdelta = datetime.timedelta(minutes=labcheckinterval)
        nextjob = now + labcheckdelta
        nextjobtime = nextjob.strftime("%H:%M")
        atcmd = f'echo {holroot}/labstartup.sh labcheck | at {nextjobtime}'
        os.system(atcmd)
    return


def labstartup_sleep(seconds):
    """
    sleep for the spefied number of seconds
    also fails the lab if runtime exceeds the maximum allowed runtime
    :param seconds: the number of seconds to sleep
    """
    global start_time
    time.sleep(seconds)
    now = datetime.datetime.now()
    delta = now - start_time
    if delta.seconds >= (max_minutes_before_fail * 60):
        message = f'Maximum {max_minutes_before_fail} minutes.'
        labfail(f'FAIL: {message}')


def labfail(message):
    """
    called when a catastrophic failure is encountered
    :param message: the message to convey for the failure
    """
    write_output(message)
    write_output(f'FAILURE: {message} and has been terminated.')
    # we use TIMEOUT here because that is what is caught by the prepop reaper
    write_vpodprogress(f'{message}', 'TIMEOUT')
    kill_labstartup()
    exit(1)


def get_cloudinfo():
    # lcmd = '/usr/bin/vmtoolsd --cmd "info-get guestinfo.ovfenv" 2>&1 |
    # grep vlp_org_name | cut -f3 -d: | cut -f2 -d\\"'
    result = get_ovf_property('vlp_org_name')
    if result:
        return result
    else:
        return 'NOT REPORTED'


def get_ovf_property(pname):
    """
        Return a dict of the requested OVF property in the ovfenv
        param pname: the name of the OVF property value to return
    """
    properties = {}
    ovfenv_cmd = f"{vmtoolsd} --cmd 'info-get guestinfo.ovfEnv'"
    proc = subprocess.Popen(ovfenv_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    xml_parts = proc.stdout.read()
    xml_err = proc.stderr.read()
    if xml_err:
        return ""
    raw_data = parseString(xml_parts)
    for prop in raw_data.getElementsByTagName('Property'):
        key, value = [prop.attributes['oe:key'].value,
                      prop.attributes['oe:value'].value]
        properties[key] = value
        if key == pname:
            return properties[key]


def getfilecontents(filepath):
    """
    Utility function to read file contents and return as text
    param filepath: the path to the file to read
    """
    with open(filepath, 'r') as infile:
        contents = infile.readlines()
    infile.close()
    try:
        contents = ''.join(contents)
    except Exception as e:
        print(e)
    return contents


def ssh(cmd, rh, pw, **kwargs):
    """
    param cmd: the command to run
    param rh: the remote host specified as user@remotehost
    param pw: the password or password from creds.txt if blank
    """
    lfile = kwargs.get('logfile', logfile)
    run = subprocess.CompletedProcess
    run.stdout = ''
    run.returncode = 1 # assume error since 
    if '@' not in rh:
        run.stderr = f'remote host must use account@host format. Got: {rh}'
        return run
    if pw == '':
        pw = password

    sshoptions = '-o StrictHostKeyChecking=accept-new'
    rcmd = f'/usr/bin/sshpass -p {pw} ssh {sshoptions} {rh} {cmd}'  # 2>&1
    rcmdlist = rcmd.split()
    logging.debug(f'rcmdlist: {rcmdlist}')
    try:
        run = subprocess.run(rcmdlist, capture_output=True, text=True, check=True)
        # for property, value in vars(run).items():
            # print(f'{property} : {value}')
    except Exception as e:
        write_output(f'{e}', logfile=lfile)
        run.stdout = str(e)
        # if e.returncode != 255:  # weird vCenter appliance FIPS error
        #    write_output(f'Exception: {e}')
    return run


def scp(src, dst, pw, **kwargs):
    """
    param src: the full path to the source file in scp format, e.g. user@host:filepath or just path if local
    param dst: the full path to the destination file in scp format or just path if local
    param pw: the password or '' if no password is needed?
    """
    lfile = kwargs.get('logfile', logfile)
    run = subprocess.CompletedProcess
    run.returncode = 1
    if pw == '':
        pw = password
    if '@' not in src and '@' not in dst:
        write_output('Local copy not allowed. Need user@host for source or destination.', logfile=lfile)
        return
    sshoptions = '-o StrictHostKeyChecking=accept-new'
    rcmd = f'/usr/bin/sshpass -p {pw} scp {sshoptions} {src} {dst}'  # 2>&1
    rcmdlist = rcmd.split()
    logging.debug(f'rcmd: {rcmd}')
    try:
        write_output(f'Copying {src} to {dst}...', logfile=lfile)
        run = subprocess.run(rcmdlist, capture_output=True, text=True, check=True)
        # for property, value in vars(run).items():
            # print(f'{property} : {value}')
    except Exception as e:
        if 'no' in e.stderr:
            run.stdout = str(e.stderr)
            return run
    return run


def addroute(nw, nm, gw):
    """
    :param nw: the network to add
    :param nm: the subnet mask to use
    :param gw: the default gateway for the network
    """
    lf = '/tmp/addroute.sh'
    rh = f'root@{router}'
    pw = password
    rf = '/root/addroute.sh'
    rootinf = '/root/interfaces'
    etcinf = '/etc/network/interfaces'
    greprte = f'/sbin/route | grep {nw}'
    res = ssh(greprte, rh, pw)
    if res.out.find(nw) != -1:
        write_output(f"Route {nw} already present. Nothing to do.")
        return
    rtecmd = 'sed -e \'s/^allow-hotplug eth2/post-up route add -net ' + nw + ' netmask ' + nm + ' gw ' + gw
    rtecmd += '\\npre-down route del -net ' + nw + ' netmask ' + nm + ' gw ' + gw
    rtecmd += '\\n\\nallow-hotplug eth2/g\''
    rtecmd += ' ' + etcinf
    rtecmd += '\n/sbin/route add -net ' + nw + ' netmask ' + nm + ' gw ' + gw + '\n'
    with open(lf, "w") as f:
        f.write(rtecmd)
        f.close()
    scp(lf, f'root@{router}:{rf}', pw)
    write_output(f'Adding route {nw} {nm} {gw}')
    cmd = f'''/bin/sh {rf} > {rootinf}'''
    ssh(cmd, rh, pw)
    cmd = f'''cp {etcinf} {etcinf}.bak'''
    ssh(cmd, rh, pw)
    cmd = f'''mv {rootinf} {etcinf}'''
    ssh(cmd, rh, pw)


def managevcsaservice(action, server, service, pw):
    """
    This function manages (start/stop/restart/status) the specified service on the specified VCSA server (6.0 or 6.5)
    param action: start/stop/restart/status
    param server: the server
    param service: the service
    param pw: the password
    """
    action = action.lower()
    if pw == '':
        pw = password
    cred = f'{linuxuser}@{server}'
    validactions = ['restart', 'start', 'status', 'stop']
    # get over the weird FIPS error with vSphere 8 RTM on vcsa
    lcmdstatus = f'service-control --status {service}'
    ssh(lcmdstatus, cred, pw)
    if action in validactions:
        try:
            # execute a stop or restart action (which is a stop, then start)
            if action == 'stop' or action == 'restart':
                lcmdstop = f'service-control --stop {service}'
                write_output(f'Stopping {service} on {server}')
                ret = ssh(lcmdstop, cred, pw)
                write_output(f'Stopped {service} on {server}: {ret.stdout}')

            if action == 'start' or action == 'restart':
                lcmdstart = f'ssh {cred} service-control --start {service}'
                write_output(f'Starting {service} on {server}')
                ret = ssh(lcmdstart, cred, pw)
                labstartup_sleep(sleep_seconds)
                if 'start' in ret.stdout:
                    write_output(f'Started {service} on {server}: {ret.stdout}')
                else:
                    write_output(f'Did not start {service} on {server}')
            # get the state of the service
            lcmdstatus = f'service-control --status {service}'
            write_output(f'Querying status of {service} on {server}')
            ret = ssh(lcmdstatus, cred, pw)
            write_output(f'Status of {service} on {server} is {ret.stdout}')
            return ret
        except Exception as e:
            write_output(f'Failed to {action} {service} on {server}')
            return e


def managelinuxservice(action, server, service, waitsec, pw):
    """
    This function manages (start/stop/restart/query) the specified service on the specified server
    The service must respond within $waitsec seconds or the function reports 'fail'
    :param action: start/stop/restart/query
    :param server: the target ssh server optional account@hostname
    :param service: the name of the Linux service
    :param waitsec: the number of seconds to sleep (optional 30 default)
    :param pw: the password - default is the password from creds.txt
    """
    lcmd1 = f'service {service} {action}'
    lcmd2 = f'service {service} status'
    ret = subprocess.CompletedProcess

    if server.find('@') == -1:
        cred = f'{linuxuser}@{server}'
    else:
        cred = server
    if waitsec == '':
        waitsec = 30
    if pw == '':
        pw = password

    try:
        ret = ssh('uname -v', cred, pw)
        logging.debug(f'{ret.stdout} {ret.stderr}')
        if ret.stdout.find('photon') != -1:
            write_output('Operating System is Photon')
            if action == 'query':
                ret = managevcsaservice('status', server, service, pw)
            else:
                ret = managevcsaservice(action, server, service, pw)
            return ret
    except Exception as e:
        write_output(f'Failed to run uname -v on {server} -- {e}')

    # non-photon Linux machine
    try:
        if action != 'query':
            ret = ssh(lcmd1, cred, pw)  # start or stop
            write_output(f'Pausing for {waitsec} seconds for service to start...\n {ret.stdout}')
            labstartup_sleep(waitsec)
        ret = ssh(lcmd2, cred, pw)
        return ret
    except Exception as e:
        write_output(f'Failed to {action} {service} on {server} -- {e}')
        return ret

def runwincmd(cmd, server, user='Administrator', pw='XXX', **kwargs):
    """
    This function runs a command on a remote Windows machine
    :param cmd: the command to run
    :param server: the remote Windows machine hostname
    :param user: default Administrator
    :param pw: to use default XXX
    """
    stdout = ''
    lfile = kwargs.get('logfile', logfile)
    display = kwargs.get('display', False)
    arg = f'/c {cmd}'  # the "/c" is CRITICAL - it will hang if not included
    c = Client(server, username=user, password=pw, encrypt=False)
    write_output(f'Running {cmd} on {server}...', logfile=lfile)
    try:
        if not test_ping(server):
            return 'fail'
        c.connect()
        c.create_service()
        stdout, stderr, rc = c.run_executable('cmd.exe', arguments=arg)
    except Exception as e:
        write_output(f'Failed to run {cmd} on {server} -- {e}')
        #psexec_cleanup(server, user, pw)
        return 'fail'
    finally:  # must always do this
        try:
            if hasattr(stdout, 'decode'):
                print("decode")
                out = stdout.decode('ascii').split('\n')
            else:
                out = stdout
        except Exception as e:
            return f'fail: {e}'
        
        out = f'{cmd}: {" ".join(out)}'
        outfmt = out.replace('\r', '')
        write_output(outfmt, logfile=lfile)
        if display:
            print(outfmt)
        try:
            c.remove_service()
        except Exception as e:
            # get error SERVICE IS MARKED FOR DELETION
            write_output(e)
        c.disconnect()
        return out


def managewindowsservice(action, server, service, user='holuser', pw='', waitsec=30):
    r"""
    This function performs an action (start/stop/restart/query) on the specified
    Windows service on the specified server. The service must report within $waitsec
    seconds or the function reports 'fail'

    Based on information at https://pypi.org/project/pypsexec/
    In an elevated PowerShell prompt, disable UAC to fix "access denied" error:
    $reg_path = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
    $reg_prop_name = "EnableLUA"
    $reg_key = Get-Item -Path $reg_path
    $reg_prop = $reg_key.GetValue($reg_prop_name)
    if ($null -ne $reg_prop) {
       Remove-ItemProperty -Path $reg_path -Name $reg_prop_name
    }
    New-ItemProperty -Path $reg_path -Name $reg_prop_name -Value 0 -PropertyType DWord
    Reboot the machine
    :param action: start/restart/stop/query
    :param server: the Windows machine hostname
    :param service: the name of the Windows service
    :param user: default holuser
    :param pw: password to use default password as defined in creds.txt
    :param waitsec: default 30 seconds
    """
    arg2 = ''
    stdout = ''
    if pw == '':
        pw = password
    if action == 'start' or action == 'stop' or action == 'query':
        arg = f'/c sc {action} {service}'  # the "/c" is CRITICAL - it will hang if not included
    elif action == 'restart':
        arg = f'/c sc stop {service}'
        arg2 = f'/c sc start {service}'
    else:
        write_output(f'Invalid action: {action}')
        return
    query = f'/c sc query {service}'
    c = Client(server, username=user, password=pw, encrypt=False)
    write_output(f'{action}ing Windows service {service} on {server}...')
    try:
        if not test_ping(server):
            return 'fail'
        c.connect()
        c.create_service()
        if action == 'start' or action == 'stop' or action == 'restart':
            stdout, stderr, rc = c.run_executable('cmd.exe', arguments=arg)
        if action == 'restart':
            stdout, stderr, rc = c.run_executable('cmd.exe', arguments=arg2)  # start the service
        if action == 'query':  # query option
            stdout, stderr, rc = c.run_executable('cmd.exe', arguments=query)
        if action == 'start' or action == 'restart':
            write_output(f'Pausing {waitsec} seconds for service to {action}...')
            labstartup_sleep(waitsec)  # pause for the service to start then check status
        if action != 'query':
            stdout, stderr, rc = c.run_executable('cmd.exe', arguments=query)
    except Exception as e:
        write_output(f'Failed to {action} {service} on {server} -- {e}')
        #psexec_cleanup(server, user, pw)
        return 'fail'
    finally:  # must always do this
        try:
            out = stdout.decode('ascii').split('\n')
        except Exception as e:
            return f'fail: {e}'
        state = out[3].split(':')
        sline = state[1]
        (status) = sline.split(' ')
        write_output(f'The {service} service on {server} is {status[3]}')
        c.remove_service()
        c.disconnect()
        return 'success'


def psexec_cleanup(server, user='holuser', pw=''):
    """
    This function removes any leftover PAExec services on the server
    :param server: the server to clean
    :param user: optional default is holuser
    :param pw: optonal default is password as defined in creds.txt
    """
    if pw == '':
        pw = password
    c = Client(server, username=user, password=pw, encrypt=False)
    c.connect()
    c.cleanup()
    c.disconnect()
    return


# LEGACY - no longer used. On LMC, please see /home/holuser/desktop-hol/lmcstart.sh
# which calls /home/holuser/desktop-hol/cleanfirefox.py
# lmcstart.sh is called by Gnome startup applications
def cleanfirefoxannoyfile():
    """
    Remove the Firefox lock files that asks to refresh Firefox and the cache folder
    """
    filelist1 = glob.glob(f'{home}/.mozilla/firefox/*/.parentlock')
    filelist2 = glob.glob(f'{home}/.mozilla/firefox/*/lock')
    filelist = filelist1 + filelist2

    for filepath in filelist:
        try:
            write_output(f'Removing {filepath}')
            if os.path.isfile(filepath):
                os.remove(filepath)
        except Exception as e:
            write_output(f'Cannot remove {filepath} Exception: {e}')
    mozcache = f'{home}/.cache/mozilla'
    if os.path.exists(mozcache):
        write_output(f'Removing {mozcache}.')
        shutil.rmtree(mozcache)

    # and apparently all this is not enough. must also create user.js with disableResetPrompt option
    releasedir = glob.glob(f'{home}/.mozilla/firefox/*default-release')
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
        write_output(f'need to add {resetprompt} in {userpref}')
        with open(userpref, 'a') as fp:
            fp.write(f'{resetprompt}\n')
        fp.close()


def prepare_idisk():
    """
    Partition and format the independent disk attached at /dev/sda
    """
    cmd = f'/bin/sudo {cd}/prep-idisk.sh'
    runit = '/tmp/runit.sh'
    outfile = open(f'{runit}', 'w')
    outfile.write(cmd + '\n')
    outfile.close()
    os.system(f'chmod a+x {runit}')
    result = subprocess.run([f'{cd}/expectpass.sh', "holuser:", {password}, runit],
                            capture_output=True, text=True)
    if result.returncode == 0:
        return True
    else:
        return False


def start_autocheck():
    """
    Check for script and iDisk then run AutoCheck.
    """
    if labcheck:
        write_output('Labcheck is active. Skipping start_autoCheck"')
        return False
    thescript = f'{cd}/autocheck.ps1'
    if os.path.exists(thescript):
        write_output('######## HOL Development Validation Support #######')
        write_output('Preparing the iDisk')
        if prepare_idisk():
            write_output(f'Looking for {thescript}')
            write_output(f'Executing {thescript}')
            write_vpodprogress('Ready: Executing AUTOCHECK', 'AUTOCHECK')
            # Call the script, waiting for it to complete
            aclog = open('/hol/AutoCheck.log', 'w')
            acerr = open('/hol/AutoCheck.err', 'w')
            subprocess.run(["/bin/pwsh", thescript], stderr=acerr, stdout=aclog)
            write_output(f'Finished with {thescript}')
            # unmount the iDisk
            write_output('Unmounting iDisk...')
            ssh('/usr/bin/umount /mnt/idisk', 'root@console', password)
            write_output('iDisk unmounted.')
            # eject the CD
            write_output('Ejecting the CD...')
            ssh('/usr/bin/eject', 'root@console', password)
            write_output('AutoCheck CD ejected.')
            aclog.close()
            acerr.close()
            write_vpodprogress('Finished with AUTOCHECK', 'AUTOCHECK-DONE')
            return True
        else:
            write_output('prepare_idisk failed.')
            return False
    return False


def exit_maintenance():
    """
    Take all ESXi hosts out of Maintenance Mode
    """
    hosts = get_all_hosts()
    for host in hosts:
        if host.runtime.inMaintenanceMode:
            host.ExitMaintenanceMode_Task(0)


def check_maintenance():
    """
    Verify that all ESXi hosts are not in Maintenance Mode
    """
    maint = 0
    hosts = get_all_hosts()
    for host in hosts:
        if host.name in mm:  # leave this one in MM
            continue
        elif host.runtime.inMaintenanceMode:
            write_output(f'{host.name} is still in Maintenance Mode.')
    
    hosts = get_all_hosts()
    for host in hosts:
        if host.name in mm:  # leave this one in MM
            continue
        elif host.runtime.inMaintenanceMode:
            maint += 1
    
    if maint == 0:     
        return True
    else:
        return False


def router_finished():
    """
    Return true if finished is found in getrules.log
    """
    # wait to go ready until getrules.sh is finished on the router
    rcmd = "grep finished /root/getrules.log"
    ret = ssh(rcmd, f'holuser@{router}', password)
    if 'finished' in ret.stdout:
        return True
    else:
        return False


def killcmd(cmdln):
    """
    
    """
    for p in psutil.process_iter(attrs=["cmdline"]):
       for cmd in p.info['cmdline']:
          if cmdln in cmd:
             print(f'killing {cmd}')
             p.terminate()


def kill_labstartup():
    """
    """
    # build the list of Startup scripts
    labscripts = os.listdir('/hol/Startup')
    # add labstartup
    labscripts.append('labstartup.py')
    for script in labscripts:
       killcmd(script)


def startup(fname):
    """
    :param fname: the name of the Python script to run
    """
    global run_seconds
    global labcheck
    
    filepath = choose_file(startup_file_dir, fname, "py")   
    now = datetime.datetime.now()
    delta = now - start_time
    run_seconds = delta.seconds
    cmd = f'/usr/bin/python3 {filepath} {run_seconds} {labcheck}'
    run = run_command(cmd)
    ctr = 0
    maxtries = 10
    while run.returncode != 0:
        if ctr > maxtries:
            break        
        write_output(f'{fname} returned non-zero exit status. {run.stderr} Will try again in 30 seconds...')
        labstartup_sleep(30)
        run = run_command(cmd)
        ctr = ctr + 1
    
    # check lab_status - if FAIL then exit
    f = open(lab_status, 'r')
    status = f.readlines()
    f.close()
    if 'FAIL' in status[0].upper():
        write_output(f'{fname}output: {run.stdout} {fname.stderr}')
        kill_labstartup()
        exit(1)
    if run.returncode != 0:
        write_output(f'{fname} returned non-zero exit status. Failing lab. {run.stdout}')
        labfail(f'Unknown error from {fname}')
        exit(1)

