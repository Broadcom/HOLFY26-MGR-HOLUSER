#!/bin/bash
REBOOTS=0
POSTGRES="."
CCSK3SAPP="."
echo "$(date) -------------RUN START-------------" >> watchvcfa.log
echo "$(date +%T)-> VCFA Watcher started" >> watchvcfa.log

while [[ $REBOOTS -lt 3 || "$POSTGRES" != "2/2" ]]; do
   while ! $(sshpass -f /home/holuser/Desktop/PASSWORD.txt ssh -q -o ConnectTimeout=5 "vmware-system-user@10.1.1.71" exit); do
        sleep 30
	echo "$(date +%T)-> Waiting for VCFA to come Online" >> watchvcfa.log 
   done
   echo "$(date +%T)-> VCFA online, reboot# $REBOOTS" >> watchvcfa.log
   sleep 60
   CNT=0
   while [[ "$POSTGRES" != "2/2" ]]; do 
        sleep 60;
	POSTGRES=$(sshpass -f /home/holuser/Desktop/PASSWORD.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl get pods -n prelude -s https://10.1.1.71:6443'" | grep vcfapostgres-0 | awk '{ print $2 }')
	((CNT++))
        echo "$(date +%T)-> PG Result: $POSTGRES - Attempt: $CNT" >> watchvcfa.log
	if [ $CNT -eq 30 ]; then
	  echo "$(date +%T)-> Rebooting after 15 minutes with Postgres only $POSTGRES"
	  sshpass -f /home/holuser/Desktop/PASSWORD.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c reboot"
	  sleep 30
	  break
	fi
    done
   CNT=0
   while [[ "$CCSK3SAPP" != "2/2" ]]; do 
        sleep 300;
	CCSK3SAPP=$(sshpass -f /home/holuser/Desktop/PASSWORD.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl get pods -n prelude -s https://10.1.1.71:6443'" | grep ccs-k3s-app | awk '{ print $2 }')
	((CNT++))
        echo "$(date +%T)-> CCS Result: $CCSK3SAPP - Attempt: $CNT" >> watchvcfa.log
	if [ $CNT -eq 12 ]; then
	  echo "$(date +%T)-> Rebooting after 60 minutes with CCS-K3SAPP only $POSTGRES"
	  sshpass -f /home/holuser/Desktop/PASSWORD.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c reboot"
	  sleep 30
	  break
	fi
    done
    if [ "$CCSK3SAPP" == "2/2" ]; then
      CCSK3SAPPNAME=$(sshpass -f /home/holuser/Desktop/PASSWORD.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl get pods -n prelude -s https://10.1.1.71:6443'" | grep ccs-k3s-app | awk '{ print $1 }')
      sshpass -f /home/holuser/Desktop/PASSWORD.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl delete pod '\"$CCSK3SAPPNAME\"' -n prelude -s https://10.1.1.71:6443'"
      echo "$(date +%T)-> Deleted CCS-K3S-APP for CPU usage bug" >> watchvcfa.log
      break
    fi
    if [ "$POSTGRES" == "2/2" ]; then
      echo "$(date +%T)-> Postgres is up, waiting for CCS-K3S-APP" >> watchvcfa.log
      break
    fi
    ((REBOOTS++))
done
