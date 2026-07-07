########################################################################################################################################
##
## Title: VCF Operations Certificate & Settings Configuration Script
## Version: 2026.07.07
## Date: 2026-07-07
##
########################################################################################################################################
## Version 2026.07.07
## Fixed: replaceExisting was ignored once a certificate alias already existed in the Fleet Manager locker, so a force
## replace never regenerated or reinstalled the certificate. The locker rejects deleting a certificate that is still
## associated with a deployed environment (LCM_CERTIFICATE_API_ERROR0000), so a force replace now regenerates the
## cert/key locally and updates the existing locker entry in place (fleet.updateCertificateByVmid) instead of
## deleting and re-importing it.
########################################################################################################################################
import functions.file_functions as file
import functions.fleet_functions as fleet
import functions.cert_functions as cert
import functions.ops_functions as ops
import sys
import time

certificate = True
settings = False

debug = False
sslVerify = False
replaceExisting = True

pwdFile = '/home/holuser/Desktop/PASSWORD.txt'
caPwdFile = 'ca.txt'

domain = 'site-a.vcf.lab'
lcmFqdn = 'opslcm-a.site-a.vcf.lab'
lcmUsername = 'admin@local'
lcmPassword = file.readFile(pwdFile)

opsFqdn = 'ops-a.site-a.vcf.lab'
opsUsername = 'admin'
opsPassword = file.readFile(pwdFile)

# Certificate Variables
name = 'ops'
shortname = f'{name}-01a'
fqdn = f'{shortname}.{domain}'
vip = f'{name}-a'
vipFqdn = f'{vip}.{domain}'
alias = f'{fqdn}'
cName = f'{name}collector-01a'
cFqdn = f'{cName}.{domain}'

rootFolder = '/hol'
certFolder = f'{rootFolder}/ssl/host/{shortname}/'

altNames = [f'{fqdn}',f'{shortname}',f'{vip}', f'{vipFqdn}', f'{cFqdn}', f'{cName}']
keyLength = 2048
csrFile = f"{certFolder}{shortname}.csr"
cfgFile = f"{certFolder}{shortname}.cfg"
keyFile = f"{certFolder}{shortname}.key"
certFile = f"{certFolder}{shortname}.cer"
pemFile = f"{certFolder}{shortname}.pem"
caFile = f'/home/holuser/hol/ca/ca.crt'
caKeyFile = f'/home/holuser/hol/ca/ca.key'
caPass = file.readFile(caPwdFile)
days = 730

lockerCertId = None

tenant = 'default'

globalSettings = [
    {
        "key": "ALLOW_CONCURRENT_LOGIN_SESSIONS",
        "value": "false"
    }
]

token = fleet.getEncodedToken(lcmUsername, lcmPassword)

start = time.time()
print(f"START: {time.strftime('%H:%M:%S', time.localtime(start))}")

if certificate:
    try:
        certVmid = fleet.getCertificateVmidByAlias(lcmFqdn, token, sslVerify, alias)

        if not certVmid or replaceExisting:
            if certVmid:
                print(f'INFO: Certificate already configured. Forcing replacement of existing Locker certificate.')

            file.createFolder(certFolder)
            cert.createCertCfgFile(cfgFile, fqdn, alias, altNames, replaceExisting)
            key = cert.createRsaKey(keyFile, keyLength, replaceExisting)
            csr = cert.createCsr(csrFile, fqdn, altNames, key, replaceExisting)
            ca = cert.readCaFile(caFile)
            caKey = cert.readCaKeyFile(caKeyFile, caPass)
            cer = cert.createCert(certFile, csr, ca, caKey, days, replaceExisting)
            cert.createCaChain(pemFile, cer, ca, replaceExisting)

            try:
                if certVmid:
                    fleet.updateCertificateByVmid(lcmFqdn, token, sslVerify, certVmid, alias, pemFile, keyFile)
                else:
                    fleet.importCertificateToFleetManager(lcmFqdn, token, sslVerify, alias, pemFile, keyFile)
            except Exception as e:
                print(f"ERROR: {e}")
        else:
            print(f'INFO: Certificate already configured.')

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    finally:
        certVmid = fleet.getCertificateVmidByAlias(lcmFqdn, token, sslVerify, alias)
        if certVmid:
            lockerCertId = fleet.buildLockerIdFromVmid(fleet.getCertificateVmidByAlias(lcmFqdn, token, sslVerify, fqdn), alias, 'certificate')
            print(f'INFO: Locker Cert ID: {lockerCertId}')

if settings:
    try:
        token = ops.getVcfOpsAuthToken(opsFqdn, opsUsername, opsPassword, sslVerify)

        for globalSetting in globalSettings:
            key = globalSetting['key']
            value = globalSetting['value']
            if not (ops.checkVcfOpsGlobalSetting(opsFqdn, token, sslVerify, key, value)):
                ops.setVcfOpsGlobalSetting(opsFqdn, token, sslVerify, key, value)
    
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


finish = time.time()
print(f"END: {time.strftime('%H:%M:%S', time.localtime(finish))}")

elapsed = finish - start
print(f"ELAPSED: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")


