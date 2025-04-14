#!/bin/sh
# version 1.0 12-April 2025

# copy this file to the vCenter appliance and run it

# enable the mob
# edit /etc/vmware-vpxd/vpxd.cfg
#<enableDebugBrowse>true</enableDebugBrowse>
# service-control --restart vmware-vpxd

# fix the browser warning issue
mkdir /tmp/vcsa
cp /usr/lib/vmware-sso/vmware-sts/web/lib/libvmidentity-sts-server.jar /tmp/vcsa
cd /tmp/vcsa
/usr/bin/unzip libvmidentity-sts-server.jar
# edit resources/js/websso.js isBrowserSupportedVC() return true
# this the only match in the file with 6 leading spaces (line 182)
cat /tmp/vcsa/resources/js/websso.js | sed s/'^      return false\;'/'      return true\;'/ > /tmp/websso.js
cp -f /tmp/websso.js /tmp/vcsa/resources/js/websso.js
# zip shows warnings about CRC for class files
/usr/bin/zip -r /tmp/vcsa/libvmidentity-sts-server.jar *
cp /tmp/vcsa/libvmidentity-sts-server.jar /usr/lib/vmware-sso/vmware-sts/web/lib/libvmidentity-sts-server.jar

# reboot the vcsa
# even after reboot using VAMI, the websso.js still returns false.
