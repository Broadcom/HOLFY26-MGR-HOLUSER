#! /bin/sh
# 28-February 2025

pass=`cat /home/holuser/creds.txt`

/usr/bin/sshpass -p ${pass} ssh root@router /root/fwupdate.sh --off
echo "Please disable proxy settings for browser and cli (. ~/noproxy.ch)"
