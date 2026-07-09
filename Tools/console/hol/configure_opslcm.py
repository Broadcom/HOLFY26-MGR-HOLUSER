########################################################################################################################################
##
## Title: VCF Operations Lifecycle Manager Certificate Configuration Script
## Version: 2026.07.07
## Date: 2026-07-07
##
########################################################################################################################################
## Version 2026.07.07
## Initial creation based on configure_ops.py.
## Manages the TLS certificate for opslcm-a.site-a.vcf.lab (VCF Operations Lifecycle Manager / VRSLCM).
##
## Key differences from configure_ops.py:
##   - Single-node appliance: shortname == vip == 'opslcm-a' (no separate -01a node FQDN or DNS entry).
##   - No collector appliance, so altNames contains only the FQDN and short hostname.
##   - The cert management API is still on ops-a.site-a.vcf.lab; opslcm-a is searched as the target component.
##   - certKey for opslcm-a TLS cert: f358e7e7-77fc-346f-b069-189aae3f6627 (expires 2027-05-10 if not replaced).
##
## Replacement flow (same as configure_ops.py v2026.07.07.1+):
##   1. Import new cert under versioned alias (<fqdn>-<year>) in VRSLCM locker — safe to DELETE because
##      it is NOT the main deployment alias and is not associated with an environment.
##   2. Use the VCF Ops internal cert management API
##      (PUT /suite-api/internal/certificatemanagement/certificates/{certKey}/replace)
##      to push the new cert live, referencing the locker vmid.
##   3. Poll the cert management task until SUCCESSFUL.
## The PEM chain file always includes the private key so VRSLCM can import it with hasPrivateKey=true.
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

# VCF Ops Fleet Management API host (cert management API lives on ops-a, not opslcm-a)
opsFqdn = 'ops-a.site-a.vcf.lab'
opsUsername = 'admin'
opsPassword = file.readFile(pwdFile)

# Certificate Variables
# opslcm-a is a single-node appliance: there is no separate -01a node FQDN in DNS.
# shortname, vip, and their FQDNs all resolve to the same appliance.
name = 'opslcm'
shortname = f'{name}-a'
fqdn = f'{shortname}.{domain}'
vip = f'{name}-a'
vipFqdn = f'{vip}.{domain}'
alias = f'{fqdn}'
versionedAlias = f"{fqdn}-{datetime.datetime.now().year}"

rootFolder = '/lmchol/hol'
certFolder = f'{rootFolder}/ssl/host/{shortname}/'

# opslcm-a has no collector appliance — SANs cover only the FQDN and short hostname
altNames = [fqdn, shortname]
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
                # Always import under a versioned alias and invoke the VCF Ops
                # internal cert management replace API to push the new cert live.
                # This works whether or not a cert already exists under the main alias
                # because VCF Ops tracks cert resource keys independently of the locker.
                fleet.deleteCertificateByAlias(lcmFqdn, token, sslVerify, versionedAlias)
                fleet.importCertificateToFleetManager(lcmFqdn, token, sslVerify, versionedAlias, pemFile, keyFile)
                newVmid = fleet.getCertificateVmidByAlias(lcmFqdn, token, sslVerify, versionedAlias)
                if newVmid:
                    opsToken = ops.getVcfOpsAuthToken(opsFqdn, opsUsername, opsPassword, sslVerify)
                    opsSession = ops.createOpsCertSession(opsFqdn, opsToken, sslVerify)
                    # Search by fqdn (opslcm-a.site-a.vcf.lab) — the cert CN in VCF Ops,
                    # different from the API host (ops-a.site-a.vcf.lab)
                    certKey = ops.getOpsCertResourceKey(opsFqdn, opsToken, sslVerify, fqdn, session=opsSession)
                    if certKey:
                        taskId = ops.replaceOpsCertificate(opsFqdn, opsToken, sslVerify, certKey, newVmid, session=opsSession)
                        if taskId:
                            ops.pollOpsCertTask(opsFqdn, opsToken, sslVerify, taskId, session=opsSession)
                    else:
                        print(f"ERROR: Could not find cert resource key for '{fqdn}' in VCF Ops")
                else:
                    print(f"ERROR: Failed to retrieve vmid for versioned alias '{versionedAlias}'")
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


finish = time.time()
print(f"END: {time.strftime('%H:%M:%S', time.localtime(finish))}")

elapsed = finish - start
print(f"ELAPSED: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")
