#!/bin/sh
# version 1.1 15-April 2025

# must have the vCenter FQDN
[ -z "$1" ] && echo "Usage $0 vCenterFQDN" && exit 1

# TODO: enable the mob
# edit /etc/vmware-vpxd/vpxd.cfg
#<enableDebugBrowse>true</enableDebugBrowse>
# service-control --restart vmware-vpxd

# fix the browser warning issue
pw=`cat /home/holuser/creds.txt`
libjar=/usr/lib/vmware-sso/vmware-sts/web/lib/libvmidentity-sts-server.jar
vc=$1
jar=/home/holuser/hol/vlp-agent/jre/bin/jar
[ -d /tmp/vcsa ] && rm -rf /tmp/vcsa

mkdir /tmp/vcsa
/usr/bin/sshpass -p $pw scp root@${vc}:${libjar} /tmp/vcsa
cd /tmp/vcsa
/usr/bin/unzip libvmidentity-sts-server.jar
# edit resources/js/websso.js and websso.js.tmpl isBrowserSupportedVC() return true
# this is the only match in the file with 6 leading spaces (line 182)
cd /tmp/vcsa/resources/js/
for websso in "websso.js" "websso.js.tmpl"
do
   cat $websso | sed s/'^      return false\;'/'      return true\;'/ > /tmp/${websso}
   cp -f /tmp/${websso} /tmp/vcsa/resources/js/${websso}
done

# recreate the jar file
cd /tmp/vcsa
mv libvmidentity-sts-server.jar /tmp
$jar cf libvmidentity-sts-server.jar *

/usr/bin/sshpass -p $pw scp /tmp/vcsa/libvmidentity-sts-server.jar root@${vc}:${libjar}

# reboot the vcsa?
