import functions.file_functions as file
import functions.fleet_functions as fleet
import functions.cert_functions as cert
import functions.ops_functions as ops
import functions.vm_functions as vmf
import sys
import time

certificate = True

debug = False
replaceExisting = True

pwdFile = '/home/holuser/Desktop/PASSWORD.txt'
caPwdFile = 'ca.txt'

domain = 'site-a.vcf.lab'

name = 'smtp'
shortname = f'{name}'
fqdn = f'{shortname}.{domain}'
alias = shortname

rootFolder = '/hol'
certFolder = f'{rootFolder}/ssl/host/{shortname}/'

altNames = [f'{fqdn}',f'{shortname}']
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

start = time.time()
print(f"START: {time.strftime('%H:%M:%S', time.localtime(start))}")

if certificate:
    try:

        file.createFolder(certFolder)
        cert.createCertCfgFile(cfgFile, fqdn, alias, altNames, replaceExisting)
        key = cert.createRsaKey(keyFile, keyLength, replaceExisting)
        csr = cert.createCsr(csrFile, fqdn, altNames, key, replaceExisting)
        ca = cert.readCaFile(caFile)
        caKey = cert.readCaKeyFile(caKeyFile, caPass)
        cer = cert.createCert(certFile, csr, ca, caKey, days, replaceExisting)
        cert.createCaChain(pemFile, cer, ca, replaceExisting)

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

finish = time.time()
print(f"END: {time.strftime('%H:%M:%S', time.localtime(finish))}")

elapsed = finish - start
print(f"ELAPSED: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")


