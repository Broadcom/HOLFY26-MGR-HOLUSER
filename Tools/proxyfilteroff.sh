#! /bin/sh
# 19-February 2024

# removing support for pfSense router
#if `nc -z 10.0.0.1 443`;then
#	echo "pfSense router detected. Please remove the dot from the Squid denylist to open proxy."
#	echo "Open https://10.0.0.1/-->Login:  admin, Password:  VMware1!-->Services-->Squid Proxy Server-->ACLs-->Denylist-->Delete the "dot"-->Save"
#	exit
#fi

/usr/bin/sshpass -p VMware123! ssh root@router /root/proxyfilter.sh --off
echo "Proxy is still active but will not block temporarily. Applications must use proxy."
