#! /bin/bash
# version 1.5 - 2025-11-13

# the only job of this script is to do the initial Core Team git pull

# because we're running as an at job, source the environment variables
. /home/holuser/.bashrc

# initialize the logfile
logfile='/tmp/labstartupsh.log'
statusdir='/lmchol/hol'
startupstatus="${statusdir}/startup_status.txt"
gitproject='HOLUSER'
echo "Initializing log file" > ${logfile}

cd /home/holuser/hol || exit

proxyready=$(nmap -p 3128 proxy | grep open)
while [ $? != 0 ];do
   echo "Waiting for proxy to be ready..." >> ${logfile}
   proxyready=$(nmap -p 3128 proxy | grep open)
   sleep 1
done

ctr=0
while true;do
   if [ "$ctr" -gt 30 ];then
      echo "FATAL could not perform git pull." >> ${logfile}
      exit  # do we exit here or just report?
   fi
   git pull origin main >> ${logfile} 2>&1
   if [ $? = 0 ];then
      echo "" > /tmp/coregitdone
      break
   else
      gitresult=$(grep 'could not be found' ${logfile})
      if [ $? = 0 ];then
         echo "The git project ${gitproject} does not exist." >> ${logfile}
         if [ ! -f $startupstatus ];then
            mkdir -p $statusdir
         fi
         echo "FAIL - No GIT Project" > $startupstatus
         exit 1
      else
         echo "Could not complete git pull. Will try again." >> ${logfile}
      fi
  fi
  ctr=$(("$ctr" + 1))
  sleep 5
done
