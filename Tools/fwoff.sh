#! /bin/sh
# 27-May 2024

# removing support for pfSense router
#if `nc -z 10.0.0.1 443`;then
#	echo "pfSense router detected. Please remove the dot from the Squid denylist to open firewall."
#	echo "Open https://10.0.0.1/-->Login:  admin, Password:  VMware1!-->Services-->Squid Proxy Server-->ACLs-->Denylist-->Delete the "dot"-->Save"
#	exit
#fi

password=`grep password /tmp/vPod.txt | cut -f2 -d '=' | sed 's/\r$//' | xargs`

/usr/bin/sshpass -p $password ssh root@router /root/fwupdate.sh --off
echo "Please disable proxy settings for browser and cli (. ~/noproxy.ch)"
