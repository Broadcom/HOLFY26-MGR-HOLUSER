#!/bin/bash
REBOOTS=0
POSTGRES="."
CCSK3SAPP="."

# First task - see if password is expired and reset it if necessary:
HOST="vmware-system-user@10.1.1.71" # Replace with your SSH username and host

# Attempt to connect via SSH in batch mode (no interactive prompts for password)
# and capture the output.
# The 'StrictHostKeyChecking=no' and 'UserKnownHostsFile=/dev/null' options
# are used to avoid host key confirmation prompts, which can interfere with detection.
SSH_OUTPUT=$(sshpass -f /home/holuser/creds.txt ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o PubkeyAuthentication=no "$HOST" 2>&1)

# Check if the output contains keywords indicating a password reset prompt.
# Common phrases include "old password:", "new password:", "You are required to change your password", etc.
if echo "$SSH_OUTPUT" | grep -qE "old password:|new password:|You are required to change your password|Permission denied"; then
  echo "Password reset prompt detected on $HOST."
  /home/holuser/hol/Tools/vcfapass.sh $(cat /home/holuser/creds.txt) $(/home/holuser/hol/Tools/holpwgen.sh)
else
  echo "No password reset prompt detected on $HOST (or SSH connection failed for other reasons)."
fi
# Now try to remediate Automation
echo "$(date) -------------WATCHVCFA RUN START-------------" 
echo "$(date +%T)-> VCFA Watcher started" 

while [[ $REBOOTS -lt 3 || "$POSTGRES" != "2/2" ]]; do
   while ! $(sshpass -f /home/holuser/creds.txt ssh -q -o ConnectTimeout=5 "vmware-system-user@10.1.1.71" exit); do
        sleep 30
	echo "$(date +%T)-> Waiting for VCFA to come Online"  
   done
   echo "$(date +%T)-> VCFA online, reboot# $REBOOTS" 
   sleep 60
   CNT=0
   while [[ "$POSTGRES" != "2/2" ]]; do 
        sleep 60;
	POSTGRES=$(sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl get pods -n prelude -s https://10.1.1.71:6443'" | grep vcfapostgres-0 | awk '{ print $2 }')
	((CNT++))
        echo "$(date +%T)-> PG Result: $POSTGRES - Attempt: $CNT" 
	if [ $CNT -eq 30 ]; then
	  echo "$(date +%T)-> Rebooting after 15 minutes with Postgres only $POSTGRES"
	  sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c reboot"
	  sleep 30
	  break
	fi
    done
   CNT=0
   while [[ "$CCSK3SAPP" != "2/2" ]]; do 
        sleep 300;
	CCSK3SAPP=$(sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl get pods -n prelude -s https://10.1.1.71:6443'" | grep ccs-k3s-app | awk '{ print $2 }')
	((CNT++))
        echo "$(date +%T)-> CCS Result: $CCSK3SAPP - Attempt: $CNT" 
	if [ $CNT -eq 12 ]; then
	  echo "$(date +%T)-> Rebooting after 60 minutes with CCS-K3SAPP only $POSTGRES"
	  sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c reboot"
	  sleep 30
	  break
	fi
    done
    if [ "$CCSK3SAPP" == "2/2" ]; then
      CCSK3SAPPNAME=$(sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl get pods -n prelude -s https://10.1.1.71:6443'" | grep ccs-k3s-app | awk '{ print $1 }')
      sshpass -f /home/holuser/creds.txt ssh vmware-system-user@10.1.1.71 "sudo -i bash -c 'kubectl delete pod '\"$CCSK3SAPPNAME\"' -n prelude -s https://10.1.1.71:6443'"
      echo "$(date +%T)-> Deleted CCS-K3S-APP for CPU usage bug" 
      break
    fi
    if [ "$POSTGRES" == "2/2" ]; then
      echo "$(date +%T)-> Postgres is up, waiting for CCS-K3S-APP" 
      break
    fi
    ((REBOOTS++))
done
