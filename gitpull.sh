#! /bin/sh
# version 1.1 - 11-October 2024

# the only job of this script is to do the initial Core Team git pull
# and then call the lastest versions of VLPagent.sh and labstartup.sh

# because we're running as an at job, source the environment variables
. /home/holuser/.bashrc

# initialize the logfile
logfile='/tmp/labstartupsh.log'
> ${logfile}

cd /home/holuser/hol

hol="/home/holuser"

internalgit=10.138.147.254
externalgit=holgitlab.oc.vmware.com

status=`ssh -o ConnectTimeout=5 -T git@$internalgit`
if [ $? != 0 ];then
   vPod_SKU=`grep vPod_SKU /tmp/vPod.txt | cut -f2 -d '=' | sed 's/\r$//' | xargs`
   year=`echo ${vPod_SKU} | cut -c5-6`
   index=`echo ${vPod_SKU} | cut -c7-8`
   vpod="/vpodrepo/20${year}-labs/${year}${index}" 
   
   repos="${hol}/hol^holuser ${hol}/autocheck^holuser ${vpod}^holuser"
   for repo in $repos
   do
      repodir=`echo $repo | cut -f1 -d ^`
      cat ${repodir}/.git/config | sed s/$internalgit/$externalgit/g > ${repodir}/.git/newconfig
      mv ${repodir}/.git/config ${repodir}/.git/oldconfig
      mv ${repodir}/.git/newconfig ${repodir}/.git/config
      chmod 664 ${repodir}/.git/config
   done
fi

ctr=0
while true;do
   if [ $ctr -gt 30 ];then
      echo "FATAL could not perform git pull." >> ${logfile}
      exit  # do we exit here or just report?
   fi
   git pull origin master >> ${logfile} 2>&1
   if [ $? = 0 ];then
      > /tmp/coregitdone
      break
   else
      gitresult=`grep 'could not be found' ${logfile}`
      if [ $? = 0 ];then
         echo "The git project ${gitproject} does not exist." >> ${logfile}
         echo "FAIL - No GIT Project" > $startupstatus
         exit 1
      else
         echo "Could not complete git pull. Will try again." >> ${logfile}
      fi
  fi
  ctr=`expr $ctr + 1`
  sleep 5
done
