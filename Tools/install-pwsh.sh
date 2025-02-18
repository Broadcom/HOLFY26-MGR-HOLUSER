# script from 
# https://learn.microsoft.com/en-us/powershell/scripting/install/install-ubuntu?view=powershell-7.4
# 12/11/2023 tested on Ubuntu 20.04.6
# 12/11/2023 removed sudo so just run as root
# 12/11/2023 removed final pwsh invocation just test manually as holuser

###################################
# Prerequisites

# Update the list of packages
apt-get update

# Install pre-requisite packages.
apt-get install -y wget apt-transport-https software-properties-common

# Get the version of Ubuntu
source /etc/os-release

# Download the Microsoft repository keys
wget -q https://packages.microsoft.com/config/ubuntu/$VERSION_ID/packages-microsoft-prod.deb

# Register the Microsoft repository keys
dpkg -i packages-microsoft-prod.deb

# Delete the the Microsoft repository keys file
rm packages-microsoft-prod.deb

# Update the list of packages after we added packages.microsoft.com
apt-get update

###################################
# Install PowerShell
apt-get install -y powershell
