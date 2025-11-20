#!/bin/bash

# Author: Burke Azbill
# Purpose: Check VCF Automation appliance to see if the password has expired. If so, use expect script to reset the password
# Version: 1.0 Date: October, 2025
# Version: 1.1 Date: November, 2025 - re-wrote to account for failed connections, incorrect password, and successful connection.

# Configuration
# Replace these with your actual values or pass them as arguments
HOST="10.1.1.71"
USER="vmware-system-user"
# This file was written to be called by the lsfunctions.py function run_command() which outputs logs to labstartup.log
# If running standalone, you can uncomment the following line and set the LOGFILE to the path of the log file.
# When doing so, be sure to add >> $LOGFILE to the end of the echo statements.
# LOGFILE="/home/holuser/hol/labstartup.log"

# Loop for 7 total attempts (1 Initial + 6 Retries)
for i in {0..10}; do
    # Attempt SSH connection using sshpass
    # -o StrictHostKeyChecking=no: Auto-accept host keys
    # -o UserKnownHostsFile=/dev/null: Don't save host keys (prevents known_hosts pollution)
    # -o ConnectTimeout=10: Fail fast if host is unreachable
    # -o PreferredAuthentications=password: Force password auth
    # -o PubkeyAuthentication=no: Disable public key auth
    # "exit": Command to run if connection succeeds (immediately closes session)
    # 2>&1: Capture both stdout and stderr to catch the expiration message
    OUTPUT=$(sshpass -f /home/holuser/creds.txt ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o PreferredAuthentications=password -o PubkeyAuthentication=no "$USER@$HOST" "exit" 2>&1)
    RET=$?

    # Check specifically for the password expiration message
    # grep -F uses fixed string matching (safer/faster than regex)
    # 1. Check for password expiration
    if echo "$OUTPUT" | grep -F -q "You are required to change your password immediately"; then
        echo "Password has expired"
        /home/holuser/hol/Tools/vcfapass.sh $(cat /home/holuser/creds.txt) $(/home/holuser/hol/Tools/holpwgen.sh)
        exit 0
    fi

    # 2. Check for incorrect password
    #    Note: "Permission denied, please try again." is standard, but sometimes it's just "Permission denied".
    #    Using -F for fixed string matching on the specific message provided.
    if echo "$OUTPUT" | grep -F -q "Permission denied, please try again."; then
        echo "Incorrect password"
        exit 1
    fi
    
    # Fallback check for standard "Permission denied" (publickey,password,keyboard-interactive) 
    # which might occur if password auth fails entirely or after max attempts.
    if echo "$OUTPUT" | grep -F -q "Permission denied ("; then
        echo "Authentication failed (Incorrect password or method)"
        exit 1
    fi

    # 3. Check for successful connection (Exit Code 0)
    if [ $RET -eq 0 ]; then
        exit 0
    fi

    # If failed and retries remain, wait 30 seconds
    if [ $i -lt 10 ]; then
        sleep 30
    fi
done
