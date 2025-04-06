#! /bin/sh
# 06-April 2025


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
   /usr/bin/sshpass -p $password ssh root@router /root/fwupdate.sh --on
else
   /usr/bin/sshpass -p $password ssh holuser@router sudo /root/fwupdate.sh --on
fi   

echo "Please disable proxy settings for browser and cli (. ~/noproxy.ch)"
