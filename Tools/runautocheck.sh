#!/usr/bin/sh
# version 1.1 25-April 2024

pwd=`pwd`
cd ~holuser/autocheck
echo -n "git pull: "
git pull

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
