#! /bin/sh
# 28-February 2025

pass=`cat /home/holuser/creds.txt`
/usr/bin/sshpass -p ${pass} ssh root@router /root/proxyfilter.sh --off
echo "Proxy is still active but will not block temporarily. Applications must use proxy."
