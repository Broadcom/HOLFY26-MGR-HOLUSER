#! /bin/sh
# 28-February 2025

pass=`cat /home/holuser/creds.txt`

/usr/bin/sshpass -p ${pass} ssh root@router /root/fwupdate.sh --on
echo "Please re-enable proxy settings for browser and command line."
