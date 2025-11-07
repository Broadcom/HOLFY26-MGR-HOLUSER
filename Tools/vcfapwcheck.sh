#!/bin/bash

# Author: Burke Azbill
# Version: 2.0
# Date: November, 2025
# Purpose: Check VCF Automation appliance to see if the password has expired. If so, use expect script to reset the password

function retry {
    # Function source: https://serverfault.com/questions/80862/bash-script-repeat-command-if-it-returns-an-error
    command="$*"
    retval=1
    attempt=1
    until [[ $retval -eq 0 ]] || [[ $attempt -gt 6 ]]; do
        # Execute inside of a subshell in case parent script is running with "set -e"
        (
            set +e
            $command
        )
        retval=$?
        (( attempt ++ ))
        if [[ $retval -ne 0 ]]; then
            # If there was an error wait 20 seconds
            echo "Error when attempting to check for expired pw. Waiting 20s and then trying again..."
            sleep 20
        fi
    done
    if [[ $retval -ne 0 ]] && [[ $attempt -gt 6 ]]; then
        # Something is fubar, go ahead and exit
        echo "Error when attempting to check for expired pw. Tried for 3m, something is very wrong, failing..."
        exit $retval
    fi
}

# By the time this script is called, Automation should be accessible via SSH
retry /home/holuser/hol/Tools/vcfapass-v2.sh $(cat /home/holuser/creds.txt) $(/home/holuser/hol/Tools/holpwgen.sh)
