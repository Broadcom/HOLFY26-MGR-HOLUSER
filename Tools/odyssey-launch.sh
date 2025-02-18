#!/bin/bash
# version 1.1 16-January 2024

odyssey_client=/home/holuser/desktop-hol/odyssey-client-linux.AppImage
chmod 774 $odyssey_client

echo "#!/usr/bin/bash
nohup ${odyssey_client} > /dev/null 2>&1 &
exit" > /tmp/runit.sh
chmod 775 /tmp/runit.sh
nohup /tmp/runit.sh
exit
    
