#! /bin/sh
# version 1.6 27-March 2025

git_pull() {
   cd $1
   ctr=0
   # stash uncommitted changes if not running in HOL-Dev
   if [ $branch = "master" ];then
       echo "git stash local changes for prod." >> ${logfile}
       git stash >> ${logfile}
   else
       echo "Not doing git stash due to HOL-Dev." >> ${logfile}
   fi
   while true;do
      if [ $ctr -gt 30 ];then
         echo "Could not perform git pull. Will attempt LabStartup with existing code." >> ${logfile}
         break  # just break so labstartup such as it is will run
      fi
      git checkout $branch
      git pull origin $branch >> ${logfile} 2>&1
      if [ $? = 0 ];then
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
}

git_clone() {
  cd $1
  git init >> ${logfile}
  git remote add origin $gitproject >> ${logfile}
  echo "Performing git clone for repo ${vpodgit}" >> ${logfile}
  # git clone git@holgitlab.oc.vmware.com:hol-labs/2087-labs/8701.git
  git clone  -b $branch $gitproject $vpodgitdir >> ${logfile} 2>&1
}

runlabstartup() {
   # start the Python labstartup.py script with optional "labcheck" argument
   # we only want one labstartup.py running
   lsprocs=`ps -ef | grep labstartup.py | grep -v grep`
   if [ "$lsprocs" = "" ];then
      echo "Starting ${holroot}/labstartup.py $1" >> ${logfile}
      # -u unbuffered output
      /usr/bin/python3 -u ${holroot}/labstartup.py $1 >> ${logfile} 2>&1 &
   fi
}

get_vpod_repo() {
   # get the vPod_SKU from $configini removing Windows carriage return if present
   vPod_SKU=`grep vPod_SKU ${configini} | grep -v \# | cut -f2 -d= | sed 's/\r$//' | xargs`
   # calculate the git repo based on the vPod_SKU
   year=`echo ${vPod_SKU} | cut -c5-6`
   index=`echo ${vPod_SKU} | cut -c7-8`
   yearrepo="${gitdrive}/20${year}-labs"
   vpodgitdir="${yearrepo}/${year}${index}"
}

holroot=/home/holuser/hol
gitdrive=/vpodrepo
lmcholroot=/lmchol/hol
wmcholroot=/wmchol/hol
configini=/tmp/config.ini
logfile=/tmp/labstartupsh.log
sshoptions='StrictHostKeyChecking=accept-new'
LMC=false
WMC=false
[ -d /home/holuser/hol/vpodrouter ] && router='vpodrouter'
[ -d /home/holuser/hol/holorouter ] && router='holorouter'

# because we're running as an at or cron job, source the environment variables
. /home/holuser/.bashrc

# if no command line argument
if [ -z "$1" ];then
   # delete the old config.ini (not really needed but good for dev)
   rm ${configini} > /dev/null 2>&1
fi

# remove all the at jobs before starting
for i in `atq | awk '{print $1}'`;do atrm $i;done

# pause until mount is present
while true;do
   if [ -d ${lmcholroot} ];then
      echo "LMC detected." >> ${logfile}
      mcholroot=${lmcholroot}
      desktopfile=/lmchol/home/holuser/desktop-hol/VMware.config
      [ "$1" != "labcheck" ] && cp /home/holuser/hol/Tools/VMware.config $desktopfile
      LMC=true
      break
   elif [ -d ${wmcholroot} ];then    
      echo "WMC detected." >> ${logfile}
      mcholroot=${wmcholroot}
      desktopfile=/wmchol/DesktopInfo/desktopinfo.ini
      [ "$1" != "labcheck" ] && cp /home/holuser/hol/Tools/desktopinfo.ini $desktopfile
      WMC=true
      break
   fi
   echo "Waiting for Main Console mount to complete..." >> ${logfile}
   sleep 5
done

# start the VLP Agent in prod if not already running
startagent=`ps -ef | grep VLPagent.sh | grep -v grep`
if [ "${startagent}" = "" ];then
   cloud=`/usr/bin/vmtoolsd --cmd "info-get guestinfo.ovfenv" 2>&1 | grep vlp_org_name | cut -f3 -d: | cut -f2 -d\\`
   if [ "${cloud}" = "" ];then
      echo "Dev environment. Not starting VLP Agent." >> ${logfile}
      echo "NOT REPORTED" > /tmp/cloudinfo.txt
   else
      echo "Prod environment. Starting VLP Agent." >> ${logfile}
      echo $cloud > /tmp/cloudinfo.txt
      /home/holuser/hol/Tools/VLPagent.sh &
   fi
fi

startupstatus=${mcholroot}/startup_status.txt

# if run with the labcheck argument, only pass on to labstartup.py and exit
if [ "$1" = "labcheck" ];then
   runlabstartup labcheck
   exit 0
else  # normal first run with no labcheck argument
   echo "Main Console mount is present. Clearing labstartup logs." >> ${logfile}
   > ${holroot}/labstartup.log
   > ${mcholroot}/labstartup.log
   if [ -f ${holroot}/${router}/gitdone ];then
      rm ${holroot}/${router}/gitdone
   fi
fi

# copy the vPod.txt from the mainconsole to /tmp
if [ -f ${mcholroot}/vPod.txt ];then
   echo "Copying ${mcholroot}/vPod.txt to /tmp/vPod.txt..." >> ${logfile}
   cp ${mcholroot}/vPod.txt /tmp/vPod.txt
   labtype=`grep labtype /tmp/vPod.txt | cut -f2 -d '=' | sed 's/\r$//' | xargs`
   if [ "$labtype" != "HOL" ];then
      cp ${holroot}/holodeck/defaultconfig.ini ${configini}
   fi
else
   echo "No vPod.txt on Main Console. Abort." >> ${logfile}
   echo "FAIL - No vPod_SKU" > $startupstatus
   exit 1
fi

# did /root/mount.sh complete the volume preparation?
while [ ! -d ${gitdrive}/lost+found ];do
   echo "Waiting for ${gitdrive}..."
   sleep 5
   gitmount=`mount | grep ${gitdrive}`
   if [ "${gitmount}" = "" ];then
      echo "" >> ${logfile}
      echo "External ${gitmount} not found. Abort." >> ${logfile}
      echo "FAIL - No GIT Drive" > $startupstatus
      exit 1
   fi
done

ubuntu=`grep DISTRIB_RELEASE /etc/lsb-release | cut -f2 -d '='`

# the Core Team git pull is done using gitpull.sh at boot up
# still need to do the vPod git pull
if [ -f ${configini} ];then
   echo "Getting vPod_SKU from ${configini}" >> ${logfile}
   # get the vPod_SKU from $configini removing Windows carriage return if present
   vPod_SKU=`grep vPod_SKU ${configini} | grep -v \# | cut -f2 -d= | sed 's/\r$//' | xargs`
   password=`cat /home/holuser/creds.txt`
   # get the lab type
   labtype=`grep 'labtype =' ${configini} | grep -v \# | cut -f2 -d= | sed 's/\r$//' | xargs`
   [ "${labtype}" = "" ] && labtype="HOL"
   echo "labtype: $labtype" >> ${logfile}
elif [ -f /tmp/vPod.txt ];then
   echo "Getting vPod_SKU from /tmp/vPod.txt" >> ${logfile}
   vPod_SKU=`grep vPod_SKU /tmp/vPod.txt | cut -f2 -d '=' | sed 's/\r$//' | xargs`
   echo "vPod_SKU is ${vPod_SKU}" >> ${logfile}
   if [ ${ubuntu} = "20.04" ];then
      # get the password from $config
      password=`grep password /tmp/vPod.txt | cut -f2 -d '=' | sed 's/\r$//' | xargs`
   else
      password=`cat /home/holuser/creds.txt`
      [ -d ${lmcholroot} ] && cp /home/holuser/creds.txt /lmchol/home/holuser/creds.txt
      [ -d ${lmcholroot} ] && cp /home/holuser/creds.txt /lmchol/home/holuser/Desktop/PASSWORD.txt
   fi
fi

# if labstartup has not been implemented, apply the default router rules
# then run labstartup.py which will update the desktop and exit
if [ "$vPod_SKU" = "HOL-BADSKU" ];then
   echo "LabStartup not implemented." >> ${logfile}
   # alert the router that the git pull is complete (at least the Core Team git pull)
   > /home/holuser/hol/${router}/gitdone
   # create /tmp/${router} with contents on the router
   if [ "${labtype}" = "HOL" ];then
      /usr/bin/sshpass -p ${password} scp -o ${sshoptions} -r ${holroot}/${router} holuser@router:/tmp
   fi
   runlabstartup
   exit 0
fi

# calculate the git repos based on the vPod_SKU
year=`echo ${vPod_SKU} | cut -c5-6`
index=`echo ${vPod_SKU} | cut -c7-8`

cloud=`/usr/bin/vmtoolsd --cmd 'info-get guestinfo.ovfEnv' 2>&1`
holdev=`echo ${cloud} | grep -i hol-dev`
if [ "${cloud}" = "No value found" ] || [ !-z "${holdev}" ];then 
   branch="dev"
else
   branch="master"
fi

gitproject="https://github.com/Broadcom/HOL-${year}${index}.git"

# this is the 2nd git pull for lab-specific captain updates
echo "Ready to pull updates for ${vPod_SKU} from HOL gitlab ${gitproject}." >> ${logfile}

prod=false
holdev=`vmtoolsd --cmd 'info-get guestinfo.ovfEnv' 2>&1 | grep -i HOL-Dev`
[ $? = 1 ] && prod=true

yearrepo="${gitdrive}/20${year}-labs"
yeargit="${yearrepo}/.git"
vpodgitdir="${yearrepo}/${year}${index}"
vpodgit="${vpodgitdir}/.git"

if [ $labtype = "HOL" ] || [ $vPod_SKU = "HOL-2554" ] || [ $vPod_SKU = "HOL-2557" ];then

   # use git clone if local git repo is new else git pull for existing local repo
   if [ ! -e ${yearrepo} ] || [ ! -e ${vpodgitdir} ];then
      echo "Creating new git repo for ${vPod_SKU}..." >> ${logfile}
      mkdir $yearrepo > /dev/null 2>&1   
      # if $vpodgitdir not exist git complains about fatal error
      # but the remote add but still completes so hide the error
      git_clone $yearrepo > /dev/null 2>&1
      if [ $? != 0 ];then
         echo "The git project ${vpodgit} does not exist." >> ${logfile}
         echo "FAIL - No GIT Project" > $startupstatus
         exit 1
      fi
   elif [ ! -e ${yeargit} ];then
     # yearrepo exists but no .git
      echo "Creating new git repo for ${vPod_SKU}..." >> ${logfile}
      git_clone $yearrepo
   else
      echo "Performing git pull for repo ${vpodgit}" >> ${logfile}
      git_pull $vpodgitdir
   fi
   if [ $? = 0 ];then
      echo "${vPod_SKU} git operations were successful." >> ${logfile}
   else
      echo "Could not complete ${vPod_SKU} git clone." >> ${logfile}
   fi 
fi

if [ -f ${vpodgitdir}/config.ini ];then
   cp ${vpodgitdir}/config.ini ${configini}
fi

# push the default router files for proxy filtering and iptables
if [ "${labtype}" = "HOL" ];then
   # the router applies when the files arrive
   echo "Pushing default router files..." >> ${logfile}
   /usr/bin/sshpass -p ${password} scp -o $sshoptions -r ${holroot}/${router} holuser@router:/tmp
else
   echo "Pushing $labtype router files..." >> ${logfile}
   /usr/bin/sshpass -p ${password} ssh -o $sshoptions holuser@router mkdir /tmp/holorouter
   /usr/bin/sshpass -p ${password} scp -o $sshoptions ${holroot}/${router}/nofirewall.sh holuser@router:/tmp/holorouter/iptablescfg.sh
   /usr/bin/sshpass -p ${password} scp -o $sshoptions ${holroot}/${router}/allowall holuser@router:/tmp/holorouter/allowlist
fi

# get the vPod_SKU router files to the hol folder which overwrites the Core Team default files (except allowlist)
skurouterfiles="${yearrepo}/${year}${index}/${router}"
if [ -d ${skurouterfiles} ] && [ "${labtype}" = "HOL" ];then
   if [ "${labtype}" = "HOL" ];then
      echo "Updating router files from ${vPod_SKU}."  >> ${logfile}
      # concatenate the allowlist files
      cp -r ${skurouterfiles} /tmp
      cat ${holroot}/${router}/allowlist ${skurouterfiles}/allowlist | sort | uniq > /tmp/${router}/allowlist
      /usr/bin/sshpass -p ${password} scp -o ${sshoptions} -r /tmp/${router} holuser@router:/tmp
   fi
elif [ "${labtype}" = "HOL" ];then
   echo "Using default Core Team router files only."  >> ${logfile}
fi
# alert the router that the git pull is complete so files are applied
/usr/bin/sshpass -p ${password} ssh -o ${sshoptions} holuser@router "> /tmp/${router}/gitdone"

# note that the gitlab pull is complete
> /tmp/gitdone

if [ -f ${configini} ];then
   runlabstartup
   echo "$0 finished." >> ${logfile}
else
   echo "No config.ini on Main Console or vpodrepo. Abort." >> ${logfile}
   echo "FAIL - No Config" > $startupstatus
   exit 1
fi 
