########################################################################################################################################
##
## Title: VCF Operations Certificate & Settings Configuration Script
## Version: 2026.07.07.1
## Date: 2026-07-07
##
########################################################################################################################################
## Version 2026.07.07.1
## Fixed: The VRSLCM locker API does not support PATCH, so updateCertificateByVmid always failed silently when
## replaceExisting was True and the main alias already existed.  The locker also rejects DELETE for certs associated
## with a deployed environment.  The replacement flow is now:
##   1. Import the new cert under a versioned alias (<fqdn>-<year>) in the VRSLCM locker.
##   2. Use the VCF Ops internal cert management API
##      (PUT /suite-api/internal/certificatemanagement/certificates/{certKey}/replace)
##      to push the new cert live, referencing the locker vmid.
##   3. Poll the cert management task until SUCCESSFUL.
## The PEM chain file now always includes the private key so VRSLCM can import it correctly.
########################################################################################################################################
import functions.file_functions as file
import functions.fleet_functions as fleet
import functions.cert_functions as cert
import functions.ops_functions as ops
import sys
import time
import datetime

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
versionedAlias = f"{fqdn}-{datetime.datetime.now().year}"
cName = f'{name}collector-01a'
cFqdn = f'{cName}.{domain}'

rootFolder = '/lmchol/hol'
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
            cert.createCaChain(pemFile, cer, ca, replaceExisting, key)

            try:
                if certVmid:
                    # VRSLCM locker PATCH is not supported and DELETE is rejected for
                    # certs associated with a deployed environment.  Instead, import
                    # the new cert under a versioned alias and invoke the VCF Ops
                    # internal cert management replace API to push it live.
                    fleet.deleteCertificateByAlias(lcmFqdn, token, sslVerify, versionedAlias)
                    fleet.importCertificateToFleetManager(lcmFqdn, token, sslVerify, versionedAlias, pemFile, keyFile)
                    newVmid = fleet.getCertificateVmidByAlias(lcmFqdn, token, sslVerify, versionedAlias)
                    if newVmid:
                        opsToken = ops.getVcfOpsAuthToken(opsFqdn, opsUsername, opsPassword, sslVerify)
                        opsSession = ops.createOpsCertSession(opsFqdn, opsToken, sslVerify)
                        certKey = ops.getOpsCertResourceKey(opsFqdn, opsToken, sslVerify, opsFqdn, session=opsSession)
                        if certKey:
                            taskId = ops.replaceOpsCertificate(opsFqdn, opsToken, sslVerify, certKey, newVmid, session=opsSession)
                            if taskId:
                                ops.pollOpsCertTask(opsFqdn, opsToken, sslVerify, taskId, session=opsSession)
                        else:
                            print(f"ERROR: Could not find cert resource key for '{opsFqdn}' in VCF Ops")
                    else:
                        print(f"ERROR: Failed to retrieve vmid for versioned alias '{versionedAlias}'")
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


