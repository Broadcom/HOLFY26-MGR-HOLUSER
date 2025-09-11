import os
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.x509 import DNSName, SubjectAlternativeName
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import functions.file_functions as file
import functions.core_functions as core
import datetime
import ipaddress
from datetime import timedelta

debug = False

def createCertCfgFile(cfgFile, fqdn, shortname, altNames, replace):

    cfg = file.checkFile(cfgFile)

    if not (cfg) or replace:

        file.createFile(f'{cfgFile}', ' ')
    
        with open(f'{cfgFile}', 'a') as f:
            f.write(f'[ req ]\n')
            f.write(f'default_md = sha512\n')
            f.write(f'default_bits = 2048\n')
            f.write(f'default_keyfile = rui.key\n')
            f.write(f'distinguished_name = req_distinguished_name\n')
            f.write(f'encrypt_key = no\n')
            f.write(f'prompt = no\n')
            f.write(f'string_mask = nombstr\n')
            f.write(f'req_extensions = v3_req\n')
            f.write('\n')
            f.write(f'[ v3_req ]\n')
            f.write(f'basicConstraints = CA:false\n')
            f.write(f'keyUsage = digitalSignature, keyEncipherment, dataEncipherment\n')
            f.write(f'extendedKeyUsage = serverAuth, clientAuth\n')
            f.write(f'subjectAltName = @alt_names\n')
            f.write('\n')
            f.write('[ alt_names ]\n')
            for i in range(len(altNames)):
                try:
                    if ipaddress.ip_address(altNames[i]):
                        f.write(f'IP.{i} = {altNames[i]}\n')
                except ValueError:
                    f.write(f'DNS.{i} = {altNames[i]}\n')  
            f.write('\n')      
            f.write(f'[ req_distinguished_name ]\n')
            f.write(f'countryName = US\n')
            f.write(f'stateOrProvinceName = California\n')
            f.write(f'localityName = Palo Alto\n')
            f.write(f'0.organizationName = VMware\n')
            f.write(f'organizationalUnitName = Hands-on Labs\n')
            f.write(f'commonName = {fqdn}\n')
            f.write(f'emailAddress = administrator@vcf.lab\n')
        
        f.close()

    else:
        raise Exception(f'SSL Certificate : SSL Config File Exists : {cfgFile}')

def createRsaKey(aFile, keySize, replace):
    key = rsa.generate_private_key(public_exponent=65537, key_size=keySize)

    if not (file.checkFile(aFile)) or replace:
        file.createByteFile(aFile, key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    
    return key

def createCsr(aFile, fqdn, altNames, key, replace):
   
    def createSan(altNames):
        """
        Create a list of Subject Alternative Names (SAN) from the provided list.
        """
        san = []
        for entry in altNames:
            try:
                if ipaddress.ip_address(entry):
                    san.append(x509.IPAddress(ipaddress.ip_address(entry)))
            except ValueError:
                san.append(x509.DNSName(entry))
        return x509.SubjectAlternativeName(san)

    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"California"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"Palo Alto"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"VMware"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, u"Hands-on Labs"),
        x509.NameAttribute(NameOID.COMMON_NAME, fqdn)
    ])

    san = createSan(altNames)

    csr = x509.CertificateSigningRequestBuilder().subject_name(subject).add_extension(san, critical=False).sign(key, hashes.SHA256())

    if not (file.checkFile(aFile)) or replace:
        file.createByteFile(aFile, csr.public_bytes(serialization.Encoding.PEM))

    return csr

def createCert(aFile, csr, ca, caKey, days, replace):

    cer = (
        x509.CertificateBuilder()
        .subject_name(csr.subject)
        .issuer_name(ca.subject)
        .public_key(csr.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + timedelta(days=days))
        .add_extension(
            x509.SubjectAlternativeName(csr.extensions.get_extension_for_class(x509.SubjectAlternativeName).value),
            critical=False
        )
        .sign(caKey, hashes.SHA256())
    )

    if not (file.checkFile(aFile)) or replace:
        file.createByteFile(aFile, cer.public_bytes(serialization.Encoding.PEM))
    
    return cer

def createCaChain(aFile, cer, ca, replace):

    pem = file.checkFile(aFile)

    print(f'TASK: SSL Certificate : Creating PEM : {os.path.splitext(os.path.basename(aFile))[0]}')

    if not (pem) or replace:
    
        file.deleteFile(aFile)

        print(f'INFO: Creating PEM file: {aFile}.')

        with open(aFile, 'wb') as p:
            p.write(cer.public_bytes(serialization.Encoding.PEM))
            p.write(ca.public_bytes(serialization.Encoding.PEM))

        file.checkFile(aFile)

def readCaFile(aFile):
    print(f'TASK: Reading CA Cert: {aFile}')
    with open(aFile, 'rb') as f:
        return x509.load_pem_x509_certificate(f.read(), default_backend())
    
def readCaKeyFile(aFile, caPassword):
    print(f'TASK: Reading CA Key: {aFile}')
    with open(aFile, 'rb') as f:
        return serialization.load_pem_private_key(f.read(), password=caPassword.encode())