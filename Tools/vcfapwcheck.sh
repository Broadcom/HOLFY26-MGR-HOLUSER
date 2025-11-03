#!/bin/bash

# Author: Burke Azbill
# Version: 1.0
# Date: October, 2025
# Purpose: Check VCF Automation appliance to see if the password has expired. If so, use expect script to reset the password

# First task - see if password is expired and reset it if necessary:
HOST="vmware-system-user@10.1.1.71" # Replace with your SSH username and host

# Attempt to connect via SSH in batch mode (no interactive prompts for password)
# and capture the output.
# The 'StrictHostKeyChecking=no' and 'UserKnownHostsFile=/dev/null' options
# are used to avoid host key confirmation prompts, which can interfere with detection.
SSH_OUTPUT=$(sshpass -f /home/holuser/creds.txt ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o PreferredAuthentications=password -o PubkeyAuthentication=no "$HOST" 2>&1)
# TODO: Add handler for ssh Exit 1 -- this requires a reboot of the auto-a host
# Check if the output contains keywords indicating a password reset prompt.
# Common phrases include "old password:", "new password:", "You are required to change your password", etc.
if echo "$SSH_OUTPUT" | grep -qE "old password:|new password:|You are required to change your password|Permission denied"; then
  echo "Password reset prompt detected on $HOST."
  /home/holuser/hol/Tools/vcfapass.sh $(cat /home/holuser/creds.txt) $(/home/holuser/hol/Tools/holpwgen.sh)
else
  echo "No password reset prompt detected on $HOST (or SSH connection failed for other reasons)."
fi