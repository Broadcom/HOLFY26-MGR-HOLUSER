#! /bin/sh
# 28-February 2025

pass=`cat /home/holuser/creds.txt`
/usr/bin/sshpass -p ${pass} ssh root@router /root/proxyfilter.sh --on
echo "Proxy filtering is enabled. Applications must use proxy."
