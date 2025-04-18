<#
	Configuration script for HOL vCenter(s) and vESXi hosts [2017]
	Start with empty vCenter inventory
	End with Datacenter, Cluster, hosts in the Cluster, 
		iSCSI adapter added and pointed to FreeNAS
		VDS and port groups created, hosts migrated to the VDS, and vSS removed
	
	Version - 05-March 2024
	
	TODO: look at setting default gateway for vmk1 (storage) as an override to Default IP stack
	TODO: look at implementing VSAN config option (not used currently)'Syslog.global.logHost'

.NOTES
Configure-ESXi-Hosts.ps1 - December 24, 2021
	* New: Added support for Linux Main Console
	* New: Detecting the DNS Domain instead of hard coding.

Configure-ESXi-Hosts.ps1 - March 24, 2021
	* New:  Modified the $adminUser preferences for Site A|B deployment prompts to use 
		administrator@vsphere2.local as an alternative option.  Included coredump warning suppression.

Configure-ESXi-Hosts.ps1 - March 9, 2021
	* New: Updated license file usage, increased host count to 6x per site, removed $legacyAdminUser references, updated references of 'administrator@regionA.local' with 'administrator@vsphere.local' which is our
		standard at this time for new base templates as well as the vSphere 7 2021 vPod.
		
Configure-ESXi-Hosts.ps1 - May 20, 2022
	* bug fixes, error handling and verified with Linux Main Console

Configure-ESXi-Hosts.ps1 - March 4, 2024
	* bug fixes, error handling and verified with Linux Main Console

#>

#Notes

### Variables

# need this for PowerShell 5 installed on 2012 WMC since the variable is not defined.
If ( $psVersion -eq "5" -And $ENV:SystemDrive -eq "C:" ) { $isWindows = $true }


If ( $isWindows ) { $labStartupRoot = 'C:\HOL'
} ElseIf ( $isLinux ) { $labStartupRoot = '/hol'}

$toolsDir = Join-Path -Path $labStartupRoot -ChildPath 'Tools'

# establish the dom variable based on the current FQDN
If ( $isWindows) {
	$ans = [System.Net.Dns]::GetHostByName($env:computerName).HostName
	($junk, $sav) = $ans.split('.')
	ForEach ( $p in $sav) { $dom = "$dom.$p" }
	$dom = $dom.substring(1)
}

$adminUser = 'administrator@vsphere.local'
$configIni = Join-Path -Path $labStartupRoot -ChildPath "config.ini"
$p = Select-String -Path $configIni -Pattern "^password =" | Out-String
$p = $p.TrimEnd()
($junk, $rootPassword) = $p.Split('= ')
# must use IP not hostname
$ntpServer = [System.Net.Dns]::GetHostAddresses("ntp")


#If you have them, the licenses for A and B sites ("regions" in VVD-speak)
#The C:\HOL\Tools\HOL-Licenses.ps1 license file should be used to avoid modifications to this script.
$gotLicenses = $false
$assignLicenses = $false
$licenseFile = Join-Path -Path $toolsDir -ChildPath 'HOL-Licenses.ps1'

if( Test-Path $licenseFile ) {
	#load the HOL Licenses for this year
	. $licenseFile
	$gotLicenses = $true
	$assignLicenses = $true
}

# Format of "license file" to support multiple licenses, multiple sites
<#
$vCenterLicenses = @{
	'a' = 'YOUR-LICENSE-KEY-HERE' #vc.standard.instance
	'b' = 'YOUR-LICENSE-KEY-HERE'
}

$esxLicenses = @{
	'a' = 'YOUR-LICENSE-KEY-HERE' #esx.vcloudEnterprise.cpuPackage
	'b' = 'YOUR-LICENSE-KEY-HERE'
}
#>

# for "VVD-ish" naming from 2016 forward
$datacenterNamePrefix = 'Region'
$datacenterNameSuffix = '01'
$clusterNamePrefix = 'Region'
$clusterNameSuffix = '01-COMP01'

# For VMDK/drive tagging for VSAN based on size... not implemented yet
$configureVSAN = $false
$vsanSsdSize = 5
$vsanHddSize = 40

#Tweaks to hosts - point syslogs at default HOL LogInsight host in case it is present
## 01/03/2020 - fixed syslog hostname ... $site is not defined yet!
## added coredump warning suppression and autocreation = no
$esxSettings = @{
	'UserVars.DcuiTimeOut' = 0
	'UserVars.SuppressShellWarning' = 1
	'Syslog.global.logHost' = "udp://vc-mgmt-a.${dom}:514"
	'Syslog.global.defaultRotate' = 2
	'UserVars.HostClientCEIPOptIn' = 2
	'UserVars.SuppressCoredumpWarning' = 1
	'VMkernel.Boot.autoCreateDumpFile' = 'false'
}

$vcLogSettings = @{
	'config.log.maxFileSize' = 1048576
	'config.log.maxFileNum'  = 2
}

#Determine whether we will work on site A or site B
#Site A SSO is vsphere.local, Site B is vsphere2.local
$site = ''
#$site = 'a'
while( ($site -ne 'a') -and ($site -ne 'b') -and ($site -ne 'q') ) {
	$site = Read-Host "Enter the site (a|b) or 'q' to quit"
	$site = $site.ToLower()
}
if( $site -eq 'q' ) { Return }

if( $site -eq 'b' ) {
	$adminUser = 'administrator@vsphere2.local'
	$dom = 'site-b.vcf.lab'
}
else {
	$adminUser = 'administrator@vsphere.local'
	$dom = 'site-a.vcf.lab'
}

# Remove-Variable -Name 'r'  # no idea what variable 'r' might have been but it's not here now.
Write-Host "Using $adminUser"


#Set this to the numbers of the hosts that you want to configure
#$numbers = [String]$args[0]
$numbers = Read-Host 'Host numbers as a comma-separated list (default=1,2,3,4,5,6)'
if( $numbers -ne '' ) { 
	$hostNumbers =  ($numbers.Split(',')) | %  { [int] $_ }
}
else {
	#default to hosts 1-6
	$hostNumbers = (1,2,3,4,5,6)
	$numbers = '1,2,3,4,5,6'
}

Write-Host "Performing operation on site $($site.ToUpper()) for hosts $numbers"

# Generate the host names based on standard naming and entered numbers
$hostNames = @()
foreach( $hostNumber in $hostNumbers ) { 
	$hostNames += ("esx-{0:00}{1}.${dom}" -f $hostNumber,$site)
}

Write-Host "Perform configuration for hosts:"
Foreach( $hostName in $hostNames ) {
	Write-Host "`t$hostName"
}

$answer = 'y'
while( $answer -ne 'y' ) {
	$answer = Read-Host "Confirm? [Y|n]"
	$answer = $answer.ToLower()
	if( $answer -eq '' ) { $answer = 'y' }
	if( $answer -eq 'n' ) { Return }
}


#####################################################################


$vCenterServer = "vc-mgmt-{0}.${dom}" -f $site

try {
	# DEV - remove the Write-Host
	Write-Host "Connect-VIserver -Server $vCenterServer -username $adminUser -password $rootPassword"
	Connect-VIserver -Server $vCenterServer -username $adminUser -password $rootPassword -ErrorVariable errorVar
} catch {
	#Bail if the connection to vCenter does not work. Nothing else makes sense to try.
	Write-Host -ForegroundColor Red "ERROR: Unable to connect to vCenter. $errorVar"
	Return
}

if( $assignLicenses ) {
	$vCenterLicense = $vCenterLicenses[$site]
	$esxLicense = $esxLicenses[$site]
	$LicMgr = Get-View (Get-View $DefaultViServer).Content.LicenseManager
	$LicAssignMgrView = Get-View $LicMgr.LicenseAssignmentManager
}

if( $gotLicenses ) {
	#add the licenses to the vCenter's inventory (for the correct Region)
	$LicMgr.AddLicense($vCenterLicense,$null)
	$LicMgr.AddLicense($esxLicense,$null)

	#Assign the vCenter license to vCenter
	$si = Get-View ServiceInstance
	$vcUuid = $si.Content.About.InstanceUuid
	$LicAssignMgrView.UpdateAssignedLicense($vcUuid,$vCenterLicense,$null)
}

#Reconfigure vCenter logging
$vcLogSettings.Keys | % { Get-AdvancedSetting -Entity $defaultviserver -name $_ | Set-AdvancedSetting -Value $($vcLogSettings[$_]) -Confirm:$false | Out-Null }

#Set SSL Certificate "organizationalUnit" to "Hands-on Labs"
Get-AdvancedSetting -Entity $defaultviserver -name 'vpxd.certmgmt.certs.cn.organizationalUnitName' | Set-AdvancedSetting -Value 'Hands-on Labs' -Confirm:$false | Out-Null

#Disable vCenter Alarms
#This keeps tripping on the 6.5 hosts, but we don't have 3rd party filters.. disable it ??
Get-AlarmDefinition -Name "Registration/unregistration of third-party IO filter storage providers fails on a host" | Set-AlarmDefinition -Enabled $false
Get-AlarmDefinition -Name "vSAN health alarm 'vSAN release catalog up-to-date'" -ErrorAction SilentlyContinue | Set-AlarmDefinition -Enabled $false
#...any others?

#Build the Datacenter if it is not already there
$dcName = $datacenterNamePrefix + $site.ToUpper() + $datacenterNameSuffix

Try {
	$dc = Get-Datacenter -Name $dcName -ErrorAction 1
} Catch {
	$f = Get-Folder
	$dc = New-Datacenter -Name $dcName -Location $f
}

#Build the default COMP01 Cluster if it is not already there
$clusterName = $clusterNamePrefix + $site.ToUpper() + $clusterNameSuffix

Try {
	$cluster = Get-Cluster -Name $clusterName -Location $dc -ErrorAction 1
} Catch {
	#Create a cluster with VSAN, HA, DRS disabled -- set DRS to 'PartiallyAutomated' before disabling
	$cluster = New-Cluster -Location $dc -Name $clusterName -HAEnabled:$false -DrsEnabled:$true -VsanEnabled:$false -DrsAutomationLevel PartiallyAutomated
	$cluster | Set-Cluster -DrsEnabled:$false -Confirm:$false
}

#Add the hosts if they're not already in the DC... put them into the default cluster
Foreach ($hostName in $hostNames) {
	Try {
		Get-VMHost -Location $dc -Name $hostName -ErrorAction 1
	} Catch {
		Add-VMHost -Location $cluster -Name $hostName -username "root" -password $rootPassword -Confirm:$false -Force
	}
}

#####################################################################

### Work with the hosts
Foreach ($hostName in $hostNames) {
	$h = Get-VMHost -Location $dc -Name $hostName 
	$matches = Select-String -InputObject $hostName -Pattern "esx-(\d+)(a|b).${dom}"
	$hostNum = [int]$matches.Matches[0].Groups[1].value
	$hostSite = $matches.Matches[0].Groups[2].value

	Write-Host -Fore Green "Working on host $hostname"

	if( $gotLicenses ) {
		Write-Host -Fore Green "Assigning License"
		$hostMoRef = ($h | Get-View).MoRef
		#it looks like the 3rd parameter here is the "Asset" name
		$LicAssignMgrView.UpdateAssignedLicense($hostMoRef.Value,$esxLicense,$hostName)	
	}

	Write-Host -Fore Green "Configuring NTP"
	Add-VMhostNtpserver -vmhost $h -ntpserver $ntpServer -ErrorAction SilentlyContinue
	# this next line errors "Cannot enable/disable this ruleset, it is owned by system service"
	#Get-VMHostFirewallException  -vmh $h | where {$_.name -like "*NTP Client*" } | Set-VMHostFirewallException -Enabled:$true
	Get-VMHostService -vmhost $h | Where {$_.key -eq "ntpd"} | Start-VMHostService
	Get-VMHostService -vmhost $h | Where {$_.key -eq "ntpd"} | Set-VMHostService -policy 'on'

	Write-Host -Fore Green "Configuring vSS Networking"	
	$vs = get-virtualswitch -name vSwitch0 -vmhost $h
	
	#Add vmnic1 to the vSwitch0 so it has two uplinks 
	$pNic1 = $h | Get-VMHostNetworkAdapter -Physical -Name vmnic1
	$vswitch = Get-VirtualSwitch -VMHost $h -Standard -Name "vSwitch0"
	$vswitch | Add-VirtualSwitchPhysicalNetworkAdapter -VMHostPhysicalNic $pNic1 -Confirm:$false

	#Configure the vmkernel interface IP addresses and names
	$hostID = 50 + $hostNum
	$storageIP = '10.00.20.' + $hostID
	$vmotionIP = '10.00.30.' + $hostID
	$vmotionGW = '10.00.30.1'
	$storageHostIP = '10.00.20.60'
	
	$storage_portgroup = $hostname + "_storage"
	$vmotion_portgroup = $hostname + "_vmotion"

	if( $hostSite -eq 'a' ) {
		$storageIP = $storageIP.Replace('00','10')
		$vmotionIP = $vmotionIP.Replace('00','10')
		$vmotionGW = $vmotionGW.Replace('00','10')
		$storageHostIP = $storageHostIP.Replace('00','10')
	} else {
		$storageIP = $storageIP.Replace('00','20')
		$vmotionIP = $vmotionIP.Replace('00','20')
		$vmotionGW = $vmotionGW.Replace('00','20')
		$storageHostIP = $storageHostIP.Replace('00','20')
	}
	
	#vmk1 is IP storage ... don't flag for VSAN at this point
	Write-Host -Fore Green "`tIP storage: $storageIP @ vmk1 on DEFAULT"
	
	New-VmHostNetworkAdapter -vmhost $h -portgroup $storage_portgroup -IP $storageIP -subnetmask 255.255.255.0 -virtualswitch $vs -vsantrafficenabled $false -confirm:$false

	#vmk2 is vmotion - create the interface on the 'vmotion' IP stack
	Write-Host -Fore Green "`tvMotion: $vmotionIP @ vmk2 on VMOTION"

	Try {	
		$vmotion_pg = New-VirtualPortGroup -Name $vmotion_portgroup -VirtualSwitch $vswitch
		$nic = New-Object VMware.Vim.HostVirtualNicSpec
		$nic.Portgroup = $vmotion_pg
		$nic.netStackInstanceKey = 'vmotion'

		$ip = New-Object VMware.Vim.HostIpConfig
		$ip.dhcp = $false
		$ip.ipAddress = $vmotionIP
		$ip.subnetMask = '255.255.255.0'
		$nic.Ip = $ip

		$networkSystem = $h.ExtensionData.configManager.NetworkSystem
		$theHostNetworkSystem = Get-view -Id ($networkSystem.Type + "-" + $networkSystem.Value)

		$theHostNetworkSystem.AddVirtualNic($vmotion_pg.name, $nic)
	} Catch {
		Write-Host "Could not create vmk2 for vMotion."
	}

	#Set the default route for the vmotion stack
	$esxcli = Get-EsxCli -VMHost $h
	$esxcli.network.ip.route.ipv4.add($vmotionGW,'vmotion','default')

	#IP Storage - iSCSI: add SW iSCSI adapter and rescan
	Write-Host -Fore Green "Configuring iSCSI adapter and target"	
	Get-VMHostStorage -VMHost $h | Set-VMHostStorage -SoftwareIScsiEnabled $true
	Write-Host -Fore Green "`tSleeping for 20 seconds"	
	Start-Sleep -Seconds 20
	$h | Get-VMHostHba -Type iScsi | New-IScsiHbaTarget -Address $storageHostIP -ErrorAction SilentlyContinue | Out-Null
	Get-VMHostStorage -VMHost $h -RescanAllHba
	Get-VMHostStorage -VMHost $h -RescanVmfs

	#Tweak advanced settings on the host
	Write-Host -Fore Green "Adjusting advanced settings"	
	#can I get away with just setting the 'global' value instead of resetting each one?
	Get-AdvancedSetting -Entity $h -Name 'Syslog.loggers.*.rotate' | Set-AdvancedSetting -Value 2 -Confirm:$false | Out-Null
	Foreach ($setting in $esxSettings.Keys) { 
		Get-AdvancedSetting -Entity $h -name $setting | Set-AdvancedSetting -Value $($esxSettings[$setting]) -Confirm:$false | Out-Null
	}
} # END Foreach Host


#####################################################################

#Create the vDS
Write-Host -Fore Green "Configuring default vDS Networking"	

# If needed, Import-Module Vmware.VimAutomation.Vds
$vdsName = $dcName + "-vDS-COMP" 

try {
	$vds = Get-VDSwitch -Name $vdsName -Location (Get-Datacenter -Name $dcName) -ErrorAction 1
} catch {
	$vds = New-VDSwitch -Name $vdsName -Location (Get-Datacenter -Name $dcName) -ErrorAction 1
}

# Create VDPortgroups
Write-Host "`tCreating new Management VDPortgroup"
$vds_mgmt_portgroup = "ESXi-$vdsName"
#Write-Host "vds_mgmt_portgroup $vds_mgmt_portgroup"

New-VDPortgroup -Name $vds_mgmt_portgroup -Vds $vds -ErrorAction SilentlyContinue | Out-Null

$vds_storage_portgroup = "Storage-$vdsName"
Write-Host "`tCreating new Storage VDPortgroup"
#Write-Host "vds_storage_portgroup $vds_storage_portgroup"

New-VDPortgroup -Name $vds_storage_portgroup -Vds $vds -ErrorAction SilentlyContinue | Out-Null

$vds_vmotion_portgroup = "vMotion-$vdsName"
Write-Host "`tCreating new vMotion VDPortgroup"
New-VDPortgroup -Name $vds_vmotion_portgroup -Vds $vds -ErrorAction SilentlyContinue | Out-Null

$vds_vm_portgroup = "VM-$vdsName"
Write-Host "`tCreating new VM VDPortgroup`n"
#Write-Host "vds_vm_portgroup $vds_vm_portgroup"

New-VDPortgroup -Name $vds_vm_portgroup -Vds $vds -ErrorAction SilentlyContinue | Out-Null

#rename uplink group on vds
$vds_uplink_portgroup = "Uplink-$vdsName"
#Write-Host "vds_uplink_portgroup $vds_uplink_portgroup"

$uplinks_pg = Get-VDPortgroup -Name *uplink* -Vds $vds
$uplinks_pg.ExtensionData.Rename($vds_uplink_portgroup)

#Migrate hosts to new VDS
Write-Host -Fore Green "Migrating hosts to VDS"
Foreach ($hostName in $hostNames) {
	$vmhost = Get-VMHost -Location $dc -Name $hostName 

	#generate port group names for this host
	$mgmt_portgroup = "Management Network" 
	$vm_portgroup = "VM Network"
	$storage_portgroup = $hostname + "_storage"
	$vmotion_portgroup = $hostname + "_vmotion"

	Write-Host ("Adding {0} to {1}" -f $hostname,$vdsName)
	$vds | Add-VDSwitchVMHost -VMHost $vmhost | Out-Null

	# Migrate host's second pNIC to VDS (vmnic1)
	Write-Host ("Adding vmnic1 to {0}" -f $vdsName)
	$vmhostNetworkAdapter = $vmhost | Get-VMHostNetworkAdapter -Physical -Name 'vmnic1'
	$vds | Add-VDSwitchPhysicalNetworkAdapter -VMHostNetworkAdapter $vmhostNetworkAdapter -Confirm:$false

	#sleep for a bit to give the switch a chance to stabilize?
	#TODO: test sleeping here

	# Migrate Management VMkernel interface to VDS
	# current name = $mgmt_portgroup
	# new name = $vds_mgmt_portgroup
	
	# Management #
	Write-Host ("Migrating {0} to {1}" -f $mgmt_portgroup, $vds_mgmt_portgroup)
	$dvportgroup = Get-VDPortgroup -name $vds_mgmt_portgroup -VDSwitch $vds
	$vmk = Get-VMHostNetworkAdapter -Name 'vmk0' -VMHost $vmhost
	Set-VMHostNetworkAdapter -PortGroup $dvportgroup -VirtualNic $vmk -Confirm:$false | Out-Null

	# Storage #
	Write-Host ("Migrating {0} to {1}" -f $storage_portgroup, $vdsName)
	$dvportgroup = Get-VDPortgroup -name $vds_storage_portgroup -VDSwitch $vds
	$vmk = Get-VMHostNetworkAdapter -Name 'vmk1' -VMHost $vmhost
	Set-VMHostNetworkAdapter -PortGroup $dvportgroup -VirtualNic $vmk -Confirm:$false | Out-Null

	# vMotion #
	Write-Host ("Migrating {0} to {1}" -f $vmotion_portgroup, $vdsName)
	$dvportgroup = Get-VDPortgroup -name $vds_vmotion_portgroup -VDSwitch $vds
	$vmk = Get-VMHostNetworkAdapter -Name 'vmk2' -VMHost $vmhost
	Set-VMHostNetworkAdapter -PortGroup $dvportgroup -VirtualNic $vmk -Confirm:$false | Out-Null

	Start-Sleep -Seconds 45

	# Migrate host's first pNIC to VDS (vmnic0)
	Write-Host ("Adding vmnic0 to {0}" -f $vdsName)
	$vmhostNetworkAdapter = $vmhost | Get-VMHostNetworkAdapter -Physical -Name 'vmnic0'
	$vds | Add-VDSwitchPhysicalNetworkAdapter -VMHostNetworkAdapter $vmhostNetworkAdapter -Confirm:$false


	# Remove old vSwitch portgroups from vSwitch0
	$vswitch = Get-VirtualSwitch -VMHost $vmhost -Name "vSwitch0"
	 
	Write-Host "Removing vSwitch portgroup" $mgmt_portgroup
	$mgmt_pg = Get-VirtualPortGroup -Name $mgmt_portgroup -VirtualSwitch $vswitch
	Remove-VirtualPortGroup -VirtualPortGroup $mgmt_pg -confirm:$false

	$vmotion_portgroup = $hostname + "_vmotion" 
	Write-Host "Removing vSwitch portgroup" $vmotion_portgroup
	$vmotion_pg = Get-VirtualPortGroup -Name $vmotion_portgroup -VirtualSwitch $vswitch
	Remove-VirtualPortGroup -VirtualPortGroup $vmotion_pg -confirm:$false

	$storage_portgroup = $hostname + "_storage"
	Write-Host "Removing vSwitch portgroup" $storage_portgroup
	$storage_pg = Get-VirtualPortGroup -Name $storage_portgroup -VirtualSwitch $vswitch
	Remove-VirtualPortGroup -VirtualPortGroup $storage_pg -confirm:$false
	
	Write-Host "Removing vSwitch portgroup" $vm_portgroup
	$vm_pg = Get-VirtualPortGroup -Name $vm_portgroup -VirtualSwitch $vswitch
	Remove-VirtualPortGroup -VirtualPortGroup $vm_pg -confirm:$false

	#Remove the vSwitch0
	Write-Host -Fore Green "Removing vSwitch0 from $hostName"
	Remove-VirtualSwitch -VirtualSwitch $vswitch -Confirm:$false
	Write-Host "`n"

} #Foreach host - vSwitch migration to VDS

if( $configureVSAN ) {
	#Import the module we use for flagging SSD/HDD devices
	try {
		Import-Module 'C:\HOL\Tools\HOL-SCSI.psm1' -ErrorAction 1
	} catch {
		Write-Host "No HOL-SCSI module. Not flagging devices"
	}
	
	## Configure the LUNs for VSAN (assume all 'SSD' devices are the same size

<#  This is built for a per-host connection. Needs to be tested to see if it works with a VC connection

	if( Get-Module HOL-SCSI ) {
		Write-Host -Fore Green "Working on Storage"
		Get-SCSILun | where {$_.CapacityGB -eq $vsanSsdSize} | Set-ScsiLunFlags | Out-Null
		Get-SCSILun | where {$_.CapacityGB -eq $vsanHddSize} | Set-ScsiLunFlags -ExplicitHDD | Out-Null
		
		Get-SCSILun | Get-ScsiLunFlags
	} else {
		Write-Host -Fore Yellow "No PS module HOL-SCSI loaded, not flagging devices"
	}
#>
}

# Put everybody in Maintenance Mode
Foreach ($hostName in $hostNames) {
	$h = Get-VMHost -Location $dc -Name $hostName 
	Write-Host -Fore Green "Enter Maintenance Mode"
	$h | Set-VMhost -State Maintenance
}

Disconnect-VIserver * -Confirm:$false

Write-Host -Fore Green "*** Finished ***"

### END ###
