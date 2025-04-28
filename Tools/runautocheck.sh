#!/usr/bin/sh
# version 1.2 28-April 2025

if [ ! -f ~holuser/rtrcreds.txt ]; then
   echo "Enter the password for the holorouter:"
   read rtrpass
   echo $rtrpass > ~holuser/rtrcreds.txt
fi

pwd=`pwd`

# remove the current folder in order to clone the correct repo
autocheckdir=~holuser/autocheck

grep 'git@holgitlab.oc.vmware.com:hol-labs/autocheck.git' ${autocheckdir}/.git/config > /dev/null
fixautocheck=$?
if [ $fixautocheck = 0 ]; then
   echo "Pulling AutoCheck from public GitHub..."
   rm -rf $autocheckdir
   git clone https://github.com/broadcom/HOLFY26-MGR-AUTOCHECK.git $autocheckdir
else
   cd ~holuser/autocheck
   echo -n "git pull: "
   git pull
fi

# need to turn off proxyfiltering to install PSSQLite
~holuser/hol/Tools/proxyfilteroff.sh

echo "Installing PSSQLite module for PowerShell..."
pwsh -Command Install-Module PSSQLite -Confirm:\$false -Force

echo "PowerCLI: Disabling CEIP..."
pwsh -Command 'Set-PowerCLIConfiguration -Scope User -ParticipateInCEIP $false -Confirm:$false' > /dev/null

echo "PowerCLI: Ignore invalid certificates..."
pwsh -Command 'Set-PowerCLIConfiguration -InvalidCertificateAction Ignore -Confirm:$false' > /dev/null

echo "PowerCLI: DefaultVIServerMode multiple..."
pwsh -Command 'Set-PowerCLIConfiguration -DefaultVIServerMode multiple -Confirm:$false' > /dev/null
#DefaultServerMode parameter of Set-PowerCLIConfiguration

echo "Starting autocheck..."
pwsh -File autocheck.ps1 | tee ~holuser/hol/AutoCheck.log

cd $pwd

