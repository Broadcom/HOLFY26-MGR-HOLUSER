#!/bin/bash
#REBOOTS=0
SEAWEEDPOD="."
CONATAINERDREADY="."
#POSTGRES="."
#CCSK3SAPP="."
LOGFILE="/home/holuser/hol/labstartup.log"

# Now try to remediate Automation
echo "$(date +%T) -------------WATCHVCFA RUN START-------------" >> "${LOGFILE}"
echo "$(date +%T)-> VCFA Watcher started"  >> "${LOGFILE}"

# while [[ $REBOOTS -lt 3 || "$POSTGRES" != "2/2" ]]; do
  CNT=0
  while ! $(sshpass -f /home/holuser/creds.txt ssh -q -o ConnectTimeout=5 "vmware-system-user@10.1.1.71" exit); do
    sleep 30
	  echo "$(date +%T)-> Waiting for VCFA to come Online" >> "${LOGFILE}"
    ((CNT++))
    if [ $CNT -eq 10 ]; then
      echo "$(date +%T)-> VCFA Online check check tried 10 times (5m), continuing..." >> "${LOGFILE}"
      break
    fi
  done
  # echo "$(date +%T)-> VCFA online, reboot# $REBOOTS" >> "${LOGFILE}" 

  ###### Containerd check/fix ######
  echo "$(date +%T)-> Checking containerd on VCFA for Ready,SchedulingDisabled..." >> "${LOGFILE}"
  CNT=0
  while [[ "$CONATAINERDREADY" != "" ]]; do
    ((CNT++))
    CONATAINERDREADY=$(sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl -s https://10.1.1.71:6443 get nodes '" | grep "Ready,SchedulingDisabled" | awk '{print $2}')
   
    if [ "$CONATAINERDREADY" == "Ready,SchedulingDisabled" ]; then
      echo "$(date +%T)-> Stale containerd found, restarting..." >> "${LOGFILE}"
      sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'systemctl restart containerd'" >> "${LOGFILE}"
      sleep 5
      sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl -s https://10.1.1.71:6443 get nodes'" >> "${LOGFILE}"
    fi
    sleep 5
    if [ $CNT -eq 2 ]; then
      NODENAME=$(sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl -s https://10.1.1.71:6443 get nodes '" | grep "Ready,SchedulingDisabled" | awk '{print $1}')
      sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl -s https://10.1.1.71:6443 uncordon ${NODENAME}'"
    fi
    if [ $CNT -eq 3 ]; then
      echo "$(date +%T)-> containerd check tried 3 times, continuing..." >> "${LOGFILE}"
      break
    fi
  done

###### kube-scheduler check/fix ######
  echo "$(date +%T)-> Checking kube-scheduler on VCFA for 0/1 Running..." >> "${LOGFILE}"
  CNT=0
  while [[ "$KUBESCHEDULER" != "" ]]; do
    ((CNT++))
    sleep 30
    KUBESCHEDULER=$(sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl -n kube-system -s https://10.1.1.71:6443 get pods '" | grep "kube-scheduler" | grep "0/1" | awk '{print $2}')
   
    if [ "$KUBESCHEDULER" == "0/1" ]; then
      echo "$(date +%T)-> Stale kube-scheduler found, restarting..." >> "${LOGFILE}"
      sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'systemctl restart containerd'" >> "${LOGFILE}"
      sleep 120
      sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl -n kube-system -s https://10.1.1.71:6443 get pods'" | grep "kube-scheduler" >> "${LOGFILE}"
    fi
    if [ $CNT -eq 3 ]; then
      echo "$(date +%T)-> kube-scheduler check tried 3 times, continuing..." >> "${LOGFILE}"
      break
    fi
  done

  # seaweedfs-master-0 is stale in the captured vAppTemplate. When Automation starts, sometimes this pod is NOT
  #   cleaned up properly, resulting in the prevention of many other pods failint go start.
  #  Check this pod and delete it if it is old:
  # Delete the seaweedfs-master-0 pod if age over 1 hour
  echo "$(date +%T)-> Checking seaweedfs-master-0 pod from VCFA if older than 1 hour..." >> "${LOGFILE}"
  CNT=0
  while [[ "$SEAWEEDPOD" != "" ]]; do
    ((CNT++))
    SEAWEEDPOD=$(sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl -n vmsp-platform -s https://10.1.1.71:6443 get pods seaweedfs-master-0 -o json'" | \
    jq -r '. | select(.metadata.creationTimestamp | fromdateiso8601 < (now - 3600)) | .metadata.name ')
    
    if [ "$SEAWEEDPOD" == "seaweedfs-master-0" ]; then
      echo "$(date +%T)-> Stale seaweedfs-master-0 pod found, deleting..." >> "${LOGFILE}"
      sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl -n vmsp-platform -s https://10.1.1.71:6443 delete pod seaweedfs-master-0'" >> "${LOGFILE}"
      sleep 5
      sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl -n vmsp-platform -s https://10.1.1.71:6443 get pods | grep seaweedfs'" >> "${LOGFILE}"
    fi
    sleep 5
    if [ $CNT -eq 3 ]; then
      echo "$(date +%T)-> seaweedfs-master-0 check tried 3 times, continuing..." >> "${LOGFILE}"
      break
    fi
  done
  

  # CNT=0
  # while [[ "$POSTGRES" != "2/2" ]]; do 
  #   sleep 60;
	#   POSTGRES=$(sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl get pods -n prelude -s https://10.1.1.71:6443'" | grep vcfapostgres-0 | awk '{ print $2 }')
	#   ((CNT++))
  #   echo "$(date +%T)-> PG Running pods Result: $POSTGRES - Attempt: $CNT" >> "${LOGFILE}" 
  #   if [ $CNT -eq 5 ]; then
  #     echo "$(date +%T)-> Rebooting after 5 minutes with Postgres only $POSTGRES" >> "${LOGFILE}"
  #     #sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c reboot"
  #     # Instead of a full reboot try deleting the vcfapostgres-0 pods, this forces the ReplicaSet to re-create them:
  #     sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl -n prelude delete pods vcfapostgres-0'"
  #     sleep 30
  #     break
  #   fi
  # done

  # CNT=0
  # while [[ "$CCSK3SAPP" != "2/2" ]]; do 
  #   sleep 300;
	#   CCSK3SAPP=$(sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl get pods -n prelude -s https://10.1.1.71:6443'" | grep ccs-k3s-app | awk '{ print $2 }')
	#   ((CNT++))
  #   echo "$(date +%T)-> CCS Running pods Result: $CCSK3SAPP - Attempt: $CNT" >> "${LOGFILE}" 
  #   if [ $CNT -eq 12 ]; then
  #     echo "$(date +%T)-> Rebooting after 60 minutes with CCS-K3SAPP only $POSTGRES" >> "${LOGFILE}"
  #     sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c reboot"
  #     sleep 30
  #     break
  #   fi
  # done
  
  # if [ "$CCSK3SAPP" == "2/2" ]; then
  #   CCSK3SAPPNAME=$(sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl get pods -n prelude -s https://10.1.1.71:6443'" | grep ccs-k3s-app | awk '{ print $1 }')
  #   sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl delete pod '\"$CCSK3SAPPNAME\"' -n prelude -s https://10.1.1.71:6443'"
  #   echo "$(date +%T)-> Deleted CCS-K3S-APP for CPU usage bug" >> "${LOGFILE}" 
  #   break
  # fi
  # if [ "$POSTGRES" == "2/2" ]; then
  #   echo "$(date +%T)-> Postgres is up, waiting for CCS-K3S-APP" >> "${LOGFILE}" 
  #   break
  # fi
#   ((REBOOTS++))
# done
