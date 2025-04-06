#! /bin/sh
#  06-April 2025

# updated password retrieval logic
# removing support for pfSense router
#if `nc -z 10.0.0.1 443`;then
#	echo "pfSense router detected. Please remove the dot from the Squid denylist to open proxy."
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

if [ ${ubuntu} = "20.04" ];then
   /usr/bin/sshpass -p ${password} ssh root@router /root/proxyfilter.sh --off
else
   /usr/bin/sshpass -p ${password} ssh holuser@router sudo /root/proxyfilter.sh --off
fi
echo "Proxy is still active but will not block temporarily. Applications must use proxy."
