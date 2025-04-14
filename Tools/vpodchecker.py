#!/usr/bin/python3
# version 1.6 27-March 2025
import sys
sys.path.append('/hol')
import os
import errno
import datetime
import OpenSSL
import ssl
import socket
import re
from pyVim import connect
from pyVmomi import vim
from pyVim.task import WaitForTask
import lsfunctions as lsf
try:
    from prettytable import PrettyTable  # http://zetcode.com/python/prettytable/
except Exception as e:
    print('Python PrettyTable is missing. Need to install.')
    run = lsf.run_command('/home/holuser/hol/Tools/proxyfilteroff.sh')
    run = lsf.run_command('pip3 install PrettyTable')
    run = lsf.run_command('/home/holuser/hol/Tools/proxyfilteron.sh')
    from prettytable import PrettyTable


class SslHost:
    """class to record hostname and port number and SSL certificate expiration"""

    def __init__(self, name, port):
        self.name = name
        self.port = port


def get_ssl_host_from_url(u):
    """
    get the host and port substrings from a URL
    :param u: string type, the URL with the host name to extract
    :return: SslHost object with name and port
    """
    j = u.split('/')
    if j[2].find(':') == -1:  # no port number so assume 443
        name = str(j[2])
        port = 443
    else:
        p = j[2].split(':')  # in case there is a port number
        name = str(p[0])
        port = str(p[1])
    return SslHost(name, port)


def get_cert_expiration(ssl_cert):
    """
    Return SSL Certificate expiration from passed in certificate.
    :param ssl_cert: str - the SSL certificate
    :return: expiration date as datetime.date from the SSL certificate information
    """
    # x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cert)
    x509info = ssl_cert.get_notAfter()
    exp_day = x509info[6:8].decode("utf-8")
    exp_month = x509info[4:6].decode("utf-8")
    exp_year = x509info[:4].decode("utf-8")
    return datetime.date(int(exp_year), int(exp_month), int(exp_day))


def get_ntp_config(esx_host):
    """
    returns a string with the ntp configuration for the passed in ESXi host
    :param esx_host: of type vim.HostSystem
    :return ntp row data list
    """
    for service in esx_host.config.service.service:
        if service.key == 'ntpd':
            if service.running:
                ntp_running = 'True'
            else:
                ntp_running = 'False'
            ntp_data = [esx_host.name, ntp_running, service.policy, esx_host.config.dateTimeInfo.ntpConfig.server[0]]
            return ntp_data


def add_vm_config_extra_option(vm_uuid, option_key, option_value):
    """
    :param vm_uuid: vm.config.uuid
    :param option_key: the name of the option
    :param option_value: the value for the option
    :return:
    """
    for si in lsf.sis:
        vm2 = si.content.searchIndex.FindByUuid(None, vm_uuid, True)
        print(f'setting {option_key} to {option_value} for {vm2.name}')
        spec = vim.vm.ConfigSpec()
        opt = vim.option.OptionValue()
        spec.extraConfig = []
        opt.key = option_key
        opt.value = option_value
        spec.extraConfig.append(opt)
        task = vm2.ReconfigVM_Task(spec)
        WaitForTask(task)


def update_vm_resource(resource):
    """
    Updates the the specified resource if possible to HOL standards
    :param resource: 'cpu_res', 'mem_res', 'cpu_shares', 'mem_shares'
    :return: True or False
    """
    # vm2 = sic.searchIndex.FindByUuid(None, vm_uuid, True)
    # noinspection PyBroadException
    try:
        spec = vim.vm.ConfigSpec()
        res_allocation = vim.ResourceAllocationInfo()
        res_allocation.reservation = 0
        shares_info = vim.SharesInfo()
        shares_info.level = 'normal'
        res_allocation.shares = shares_info
        if resource == 'cpu_res':
            spec.cpuAllocation = []
            spec.cpuAllocation = res_allocation
        if resource == 'mem_res':
            spec.memoryAllocation = []
            spec.memoryAllocation = res_allocation
        if resource == 'cpu_shares':
            spec.cpuAllocation = []
            spec.cpuAllocation = res_allocation
        if resource == 'mem_shares':
            spec.memoryAllocation = []
            spec.memoryAllocation = res_allocation

        vm.ReconfigVM_Task(spec)
        return True
    except:
        return False

lsf.init(router=False)

#DEBUG
#lsf.lab_year = '25'

min_exp_date = datetime.date(int(lsf.lab_year) + 2000, 12, 30)
min_date = str(min_exp_date.month) + '/' + str(min_exp_date.day) + '/' + str(min_exp_date.year)
print('HOL licenses must NOT expire before:', min_date)

max_exp_date = datetime.date(int(lsf.lab_year) + 2001, 1, 31)
max_date = str(max_exp_date.month) + '/' + str(max_exp_date.day) + '/' + str(max_exp_date.year)
print('HOL licenses MUST expire before:', max_date)
print('HOL SSL Certificates MUST not expire before:', min_date)

# begin SSL cert testing
if 'URLs' in lsf.config['RESOURCES'].keys():
    urls = lsf.config.get('RESOURCES', 'URLs').split('\n')
urls_to_test = []
for entry in urls:
    url = entry.split(',')
    if url[0].startswith('https'):
        # if live hostname dictionary with port number value
        urls_to_test.append(str(url[0]))

hosts = {}  # dictionary to track hosts checked and skip dupes
ssl_report_table = PrettyTable()
# column labels for report output
# ssl_report_table.field_names = ['HostName', 'PortNum', 'CertName', 'ExpiryDate', 'DaysToExpire', 'Issuer']
ssl_report_table.field_names = ['HostName', 'PortNum', 'CertName', 'ExpiryDate', 'DaysToExpire']

for url in urls_to_test:
    if lsf.check_proxy(url):  # no need to check external SSL certificates
        continue
    host = get_ssl_host_from_url(url)
    if host.name in hosts:  # have we tested this domain already?
        continue
    if lsf.test_tcp_port(host.name, host.port):
        cert: str = ssl.get_server_certificate((host.name, host.port))
        # noinspection PyTypeChecker
        x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cert)
        subject = x509.get_subject()
        host.certname = subject.CN  # the Common Name field
        issuer = x509.get_issuer()
        if issuer.OU is None or issuer.O is None:
            host.issuer = "Self-Assigned"
        else:
            host.issuer = 'OU=' + issuer.OU + 'O=' + issuer.O
        host.ssl_exp_date = get_cert_expiration(x509)
        host.days_to_expire = str((host.ssl_exp_date - min_exp_date).days)
        if int(host.days_to_expire) < 1:
            host.days_to_expire = host.days_to_expire + ' - *** EXPIRES EARLY!!!'
        exp_date = str(host.ssl_exp_date.month) + '/' + str(host.ssl_exp_date.day) + '/' + str(host.ssl_exp_date.year)
        # ssl_report_table.add_row([host.name, host.port, host.certname, exp_date, host.days_to_expire, host.issuer])
        ssl_report_table.add_row([host.name, host.port, host.certname, exp_date, host.days_to_expire])
        hosts[host.name] = 1
    else:
        ssl_report_table.add_row([host.name, host.port, 'could not test', '', ''])

# report on SSL Certificates
print(f'==== SSL CERTIFICATES with days to expire after lab expiration {min_exp_date} ====')
print(ssl_report_table)
print('==========================')

# begin vSphere ESXi NTP and license checking
if 'vCenters' in lsf.config['RESOURCES'].keys():
    vcenters = lsf.config.get('RESOURCES', 'vCenters').split('\n')
    lsf.connect_vcenters(vcenters)

# ESXi host ntp configuration
ntp_report_table = PrettyTable()
ntp_report_table.field_names = ['HostName', 'NTPD Running', 'NTPD Policy', 'NTP Server']
hosts = lsf.get_all_hosts()
for host in hosts:
    row = get_ntp_config(host)
    ntp_report_table.add_row(row)

print('==== HOST CONFIGURATION - NTP ====')
print(ntp_report_table)
print('==========================')

# L2 VM checks
print('==== L2 VM CONFIGURATION ====')
l2_vm_table = PrettyTable()
l2_vm_table.field_names = ['VM Name', 'OS Type', 'uuid.action', 'TypeDelay', 'AutoLock']


vms = lsf.get_all_vms()
for vm in vms:
    if 'vCLS-' in vm.name:
        continue
    uuid = ''
    type_delay = ''
    autolock = ''
    for optionValue in vm.config.extraConfig:
        if optionValue.key == 'uuid.action':
            uuid = optionValue.value
        if optionValue.key == 'keyboard.typematicMinDelay':
            type_delay = optionValue.value          
        if optionValue.key == 'tools.guest.desktop.autolock':
            autolock = optionValue.value
    #print(f'vm: {vm.name} autolock: {autolock}')
    if uuid != 'keep':
        try:
            add_vm_config_extra_option(vm.config.uuid, 'uuid.action', 'keep')
            if not uuid:
                uuid = 'was BLANK'
            else:
                uuid = f'was {uuid}'
        except Exception as e:
            print(f'Exception: Attribute error {e}')
            uuid = 'FIXMANUAL'
        
    if any(re.findall(r'windows', vm.config.guestId, re.IGNORECASE)):
        if autolock != 'FALSE':
            try:
                add_vm_config_extra_option(vm.config.uuid, 'tools.guest.desktop.autolock', 'FALSE')
                if not autolock:
                   autolock = 'was BLANK'
                else:
                   autolock = f'was {autolock}'
            except Exception as e:
                print(f'Exception: Attribute error {e}')
                autolock = 'FIXMANUAL'
    else:
        autolock = 'NA'
        
    if any(re.findall(r'linux|ubuntu|debian|centos|sles|suse|asianux|novell|redhat|photon|rhel|other',
                          vm.config.guestId, re.IGNORECASE)):
        if type_delay != '2000000':
            try:
                add_vm_config_extra_option(vm.config.uuid, 'keyboard.typematicMinDelay', '2000000')
                if not type_delay:
                    type_delay = 'was BLANK'
                else:
                    type_delay = f'was {type_delay}'
            except Exception as e:
                print(f'{vm.name} Exception: Attribute error {e}')
                print(f'If {vm.name} is not a managed VM, please run vPodchecker.py again to set keyboard.typmaticMinDelay.')
                type_delay = 'FIXMANUAL'
    else:
        type_delay = 'NA'

    l2_vm_table.add_row([vm.name, vm.config.guestId, uuid, type_delay, autolock])

print(l2_vm_table)
print('==========================')

print('==== L2 RESOURCE CONFIGURATION ====')
l2_vm_res_table = PrettyTable()
l2_vm_res_table.field_names = ['VM Name', 'CPU Reservation', 'Mem Reservation', 'CPU Shares Level', 'Mem Shares Level']


vms = lsf.get_all_vms()
for vm in vms:
    cpu_reservation_mhz = vm.resourceConfig.cpuAllocation.reservation
    if cpu_reservation_mhz:
        print('Setting ', vm.name, 'CPU reservation to 0 per HOL standards...')
        if update_vm_resource('cpu_res'):
            cpu_reservation_mhz = 'was ' + str(cpu_reservation_mhz)
        else:
            print('Failed to remove CPU reservation on', vm.name)

    mem_reservation_GB = vm.resourceConfig.memoryAllocation.reservation
    if mem_reservation_GB:
        print('Setting ', vm.name, 'Memory reservation to 0 per HOL standards...')
        if update_vm_resource('mem_res'):
            mem_reservation_GB = 'was ' + str(mem_reservation_GB)
        else:
            print('Failed to remove memory reservation on', vm.name)

    cpu_shares_level = vm.resourceConfig.cpuAllocation.shares.level
    if cpu_shares_level != 'normal':
        print('Setting ', vm.name, 'CPU shares to normal per HOL standards...')
        if update_vm_resource('cpu_shares'):
            cpu_shares_level = 'was ' + str(cpu_shares_level)
        else:
            print('Failed to change CPU shares on', vm.name)

    mem_shares_level = vm.resourceConfig.memoryAllocation.shares.level
    if mem_shares_level != 'normal':
        print('Setting ', vm.name, 'Memory shares to normal per HOL standards...')
        if update_vm_resource('mem_shares'):
            mem_shares_level = 'was ' + str(mem_shares_level)
        else:
            print('Failed to change memory shares on', vm.name)

        l2_vm_res_table.add_row([vm.name, cpu_reservation_mhz, mem_reservation_GB, cpu_shares_level, mem_shares_level])

print(l2_vm_res_table)
print('==========================')


license_table = PrettyTable()
license_table.field_names = ['LicenseName', 'LicenseKey', 'Expiration', 'Status']
license_keys = {}
overall_lic_status = 'PASS'
for si in lsf.sis:
    lic_mgr = si.content.licenseManager
    lic_assignment_mgr = lic_mgr.licenseAssignmentManager
    assets = lic_assignment_mgr.QueryAssignedLicenses()
    for asset in assets:
        license_key = asset.assignedLicense.licenseKey
        license_name = asset.assignedLicense.name
        entity_name = asset.entityDisplayName
        if license_key == '00000-00000-00000-00000-00000':
            license_keys[license_key] = "FAIL: evaluation"
            overall_lic_status = 'FAIL'
            license_name = entity_name + ' EVALUATION!'
            print(license_name, license_key, license_keys[license_key], entity_name)
        else:
            if license_key in license_keys:
                continue
            license_keys[license_key] = license_name
        props = asset.assignedLicense.properties
        exp_date = ''
        for item in props:
            if exp_date:  # avoid the repetition
                break
            if item.key == 'expirationDate':
                exp_date = item.value
                break
        # we have what we need at this point a licensed asset
        #  exp_date = '' #  simulated testing
        if exp_date:
            expiration_date = str(exp_date.month) + '/' + str(exp_date.day) + '/' + str(exp_date.year)
            if exp_date.date() < min_exp_date:
                license_keys[license_key] = "FAIL: expires too soon"
                overall_lic_status = 'FAIL'
                print(license_name, license_key, license_keys[license_key], expiration_date)
            elif exp_date.date() > max_exp_date:
                license_keys[license_key] = 'FAIL: expires too late'
                overall_lic_status = 'FAIL'
                print(license_name, license_key, license_keys[license_key], expiration_date)
            else:
                license_keys[license_key] = 'PASS license exipres'
        else:
            expiration_date = 'non-expiring'
            #  license_name = 'NSX for vShield Endpoint'  # simulated testing
            if 'NSX for vShield Endpoint' in license_name:
                license_keys[license_key] = 'EXCEPTION'
                print(license_name, license_key, 'NEVER expires, but it usually does not.')
            else:
                license_keys[license_key] = 'FAIL'
                overall_lic_status = 'FAIL'
                print(license_name, license_key, 'NEVER expires!!')
        license_table.add_row([license_name, license_key, expiration_date, license_keys[license_key]])

print('==== VCENTER LICENSES ====')

try:
    # noinspection PyUnboundLocalVariable
    for lic in lic_mgr.licenses:
        if not lic.used and lic.licenseKey != '00000-00000-00000-00000-00000':
            print(lic.name, lic.licenseKey, 'is UNASSIGNED and should be removed.')
            license_table.add_row([lic.name, lic.licenseKey, '', 'UNASSIGNED'])
            overall_lic_status = 'FAIL'
except Exception as e:
   license_table.add_row(['NO', 'LICENSES', 'TO', 'CHECK'])

print(license_table)
if overall_lic_status == 'PASS':
    print('Final result of license check is PASS')
else:
    print('Final result of license check is FAIL')
print('==========================')
for si in lsf.sis:
    # print ("disconnect", si) # how do I find the members of ServiceInstance?
    # inspect.getsource(si)
    connect.Disconnect(si)
# input('Press enter to finish.')

