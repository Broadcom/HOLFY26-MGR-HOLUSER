#!/bin/sh
# version 1.7 - 03-December 2024

get_vpod_repo() {
   # labstartup.sh creates the vPod_SKU.txt file
   vPod_SKU=`cat /tmp/vPod_SKU.txt`
   # calculate the git repo based on the vPod_SKU
   year=`echo ${vPod_SKU} | cut -c5-6`
   index=`echo ${vPod_SKU} | cut -c7-8`
   yearrepo="${gitdrive}/20${year}-labs"
   vpodgitdir="${yearrepo}/${year}${index}"
}

. /home/holuser/.bashrc
# firewall is open to the Manager so no proxy needed
. /home/holuser/noproxy.sh

logfile='/tmp/VLPagentsh.log'
# delete this one if present
egwagent='/home/holuser/hol/Tools/egw-agent-1.0.0.jar'
# install this version
vlpagentversion='1.0.6'

gitdrive=/vpodrepo
prepopstart=/tmp/prepop.txt
prepopstartscript=prepopstart.sh
labstart=/tmp/labstart.txt
labstartscript=labstart.sh
vlpagentdir=/home/holuser/hol/vlp-agent

# cleanup some leftover dev files
[ -f /home/holuser/egwagent/labactive.sh ] && rm /home/holuser/egwagent/labactive.sh
[ -f /home/holuser/egwagent/empty.sh ] && rm /home/holuser/egwagent/empty.sh
[ -f /home/holuser/egwagent/test_create_file.sh ] && rm /home/holuser/egwagent/test_create_file.sh

[ -f ${egwagent} ] && rm ${egwagent}

# clean up old vlp-agent jar files if present
jars=`ls ${vlpagentdir}/vlp-agent-*.jar`
for file in $jars;do
   [ $file != ${vlpagentdir}/vlp-agent-${vlpagentversion}.jar ] && rm $file
done

# install the VLP Agent (also installs the required JRE version)
echo "Sleeping 15 seconds before installing VLP Agent..." >> ${logfile}
sleep 15
cd /home/holuser/hol
Tools/vlp-vm-agent-cli.sh install --platform linux-x64 --version ${vlpagentversion} >> ${logfile} 2>&1
pkill -f -9 "java -jar vlp-agent-${vlpagentversion}.jar" >> ${logfile} 2>&1

# start the VLP Agent if not running
lsprocs=`ps -ef | grep jar | grep -v grep`
if [ "$lsprocs" = "" ];then
   echo "Sleeping 15 seconds before starting VLP Agent..." >> ${logfile}
   sleep 15
   echo "Starting VLP Agent:  ${vlpagentversion}" >> ${logfile}
   Tools/vlp-vm-agent-cli.sh start # attempts to capture the output generate "[Fatal Error]"
   [ $? = 0 ] && echo "VLP Agent started." >> ${logfile}
fi


# find the git repository for this vPod
get_vpod_repo
# start the watcher loop waiting for the vlpagent.txt when lab starts
while true;do
   if [ -f  ${prepopstart} ];then
      # note that this will run at prepop start
      echo "Received prepop start notification. Running ${vpodgitdir}/${prepopstartscript}" >> ${logfile}
      # verify that the script files exists and is executable
      if [ -f ${vpodgitdir}/${prepopstartscript} ] && [ -x ${vpodgitdir}/${prepopstartscript} ];then
         /bin/sh ${vpodgitdir}/${prepopstartscript}
      fi
   elif [ -f ${labstart} ];then
      # if labcheck is running - kill it.
	  pid=`ps -ef | grep labstartup.py | grep -v grep | awk '{print $2}'`
      if [ ! -z "${pid}" ];then
	     echo "Stopping current LabStartup processes..." >> ${logfile}
         pkill -P ${pid}
         kill ${pid}
      fi
      # active lab so delete the scheduled labcheck
      for i in `atq | awk '{print $1}'`;do atrm $i;done
      
      # note that this will run everytime the console opens
      echo "Received lab start notification. Running ${vpodgitdir}/${labstartscript}" >> ${logfile}
      # verify that the script files exists and is executable
      if [ -f ${vpodgitdir}/${labstartscript} ] && [ -x ${vpodgitdir}/${labstartscript} ];then
         /bin/sh ${vpodgitdir}/${labstartscript}
      fi
   fi
   sleep 2
done

