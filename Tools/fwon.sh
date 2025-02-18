#! /bin/sh
# # 27-May 2024

# removing support for pfSense router
#if `nc -z 10.0.0.1 443`;then
#	echo "pfSense router detected. Add the dot to the Squid denylist to enably proxy."
#	exit
#fi

password=`grep password /tmp/vPod.txt | cut -f2 -d '=' | sed 's/\r$//' | xargs`

/usr/bin/sshpass -p $password ssh root@router /root/fwupdate.sh --on
echo "Please re-enable proxy settings for browser and command line."
