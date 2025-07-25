#!/usr/bin/sh
# version 1.5.1 10-June 2025

if [ ! -f ~holuser/rtrcreds.txt ]; then
   echo "Enter the password for the holorouter:"
   read rtrpass
   echo $rtrpass > ~holuser/rtrcreds.txt
fi

pwd=$(pwd)
cd $HOME

# remove the current folder in order to clone the correct repo
autocheckdir=~holuser/autocheck
[ -d $autocheckdir ] && rm -rf $autocheckdir

echo "Cloning AutoCheck from public GitHub..."

autorepo="https://github.com/broadcom/HOLFY26-MGR-AUTOCHECK.git"
# uncomment the next line when AUTOCHECK2 repo is available
#autorepo="https://github.com/broadcom/HOLFY26-MGR-AUTOCHECK2.git"

git clone -b main ${autorepo} $autocheckdir > /dev/null 2>&1

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
cd $autocheckdir
pwsh -File autocheck.ps1 | tee ~holuser/hol/AutoCheck.log

cd $pwd

