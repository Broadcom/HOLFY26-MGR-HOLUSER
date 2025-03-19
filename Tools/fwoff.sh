#! /bin/sh
# 19-March 2025

# removing support for pfSense router
#if `nc -z 10.0.0.1 443`;then
#	echo "pfSense router detected. Please remove the dot from the Squid denylist to open firewall."
#	echo "Open https://10.0.0.1/-->Login:  admin, Password:  VMware1!-->Services-->Squid Proxy Server-->ACLs-->Denylist-->Delete the "dot"-->Save"
#	exit
#fi

ubuntu=`grep DISTRIB_RELEASE /etc/lsb-release | cut -f2 -d '='`

if [ ${ubuntu} = "20.04" ];then
   # get the password from vPod.txt
   if [ -f /tmp/vPod.txt ];then
      password=`grep password /tmp/vPod.txt | cut -f2 -d '=' | sed 's/\r$//' | xargs`
   else
      password=`grep password /hol/vPod.txt | cut -f2 -d '=' | sed 's/\r$//' | xargs`
   fi
else
   password=`cat /home/holuser/creds.txt`
fi

/usr/bin/sshpass -p $password ssh root@router /root/fwupdate.sh --off
echo "Please disable proxy settings for browser and cli (. ~/noproxy.ch)"
