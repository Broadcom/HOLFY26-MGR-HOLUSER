#! /bin/sh
# 19-February 2024

# removing support for pfSense router
#if `nc -z 10.0.0.1 443`;then
#	echo "pfSense router detected. Add the dot to the Squid denylist to enble proxy."
#	exit
#fi

/usr/bin/sshpass -p VMware123! ssh root@router /root/proxyfilter.sh --on
echo "Proxy filtering is enabled. Applications must use proxy."
