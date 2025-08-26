# 
# .SYNOPSIS
# Removes identified host(s) from vCenter inventory, including unhooking from vDS
# 
# .DESCRIPTION
# This is an HOL accelerator tool and is intended to be quick and dirty with some 
# error checking. It has been tested against the HOL vSphere 7.0u2 and 6.7 base vPods 
# and assumes a clean, unmodified deployment of these pods. It may work in other cases,
# but it may also run into issues. 
# 
	# Version - 14-January 2025
# 
# The script will
	# * look for VMs on the host
	# * put the host into maintenance mode
	# * remove the FreeNAS iSCSI target from the iSCSI configuration
	# * remove the host from the vDS
	# * remove the host from vCenter inventory
	# * remove the host from PuTTY sessions
	# * comment out the host in C:\hol\Resources\EsxiHosts.txt
# 
# .NOTES
# 
# Remove-HOLEsxiBase.ps1 - April 26, 2021
	# * New: Waiting for running tasks to complete.
	# * Updated: Error handling
	# * New: If fail can usually run again successfully
	# * New: Comments out the host from Resources\ESXiHosts.txt
# 
# Remove-HOLEsxiBase.ps1 - March 24, 2021
	# * New:  Modified the $adminUser preferences for Site A|B deployment prompts to use 
		# administrator@vsphere2.local as an alternative option.  Adjusted host numbers,
		# removed unnecessary 'Remove-Variable -Name 'r' line.
# 
# Remove-HolEsxiBase.ps1 - March 3, 2021
	# * New: Added vSphere 7 login credentials 'administrator@vsphere.local' which is our
		# standard at this time for new base templates as well as the vSphere 7 2020 vPod.
# 
# Remove-HolEsxiBase.ps1 - February 6, 2019 
	# * New: Added admin credential selection generation and selection for vSphere 6.7+ pods
	# * New: Find and remove the puTTY session matching the hostName
	# * New: Provision to select different admin account name, based on pod configuration
# 
# Remove-HolEsxiBase.ps1 - May 14, 2018 
	# * New: Added "Sleeps" to let the hosts settle down before ripping apart the networking and
		# the triggering the network health check/rollback function.
# 
# 
# .EXAMPLE
# Remove-HolEsxiBase.ps1
# 
# .INPUTS
# Interactive: 
	# * site [a|b]
	# * comma-separated list of host numbers
# 
# .OUTPUTS
# 

### Functions

Function waitForRunningTasks ( ) {
	$tasks = Get-Task -Status "Running"
	Write-Host $tasks
	While ( $tasks ) {
		ForEach ( $task in $tasks ) {
			Write-Host $task
			Write-Host "Waiting for $task to finish..."
			Wait-Task -Task $task
			Sleep -Seconds 1
			$tasks = Get-Task -Status "Running"
		}
		Start-Sleep -Seconds 1
	}	
	$errorTasks = Get-Task -Status Error			
	ForEach ( $errTask in $errorTasks ) {
		If ( $errTask.Id -eq $task.Id ) { Return $False }
	}
	Return $True
}

If ( $isWindows ) { 
	$labStartupRoot = 'C:\HOL'
	$puttyPath = 'HKCU:\Software\SimonTatham\PuTTY\Sessions'
	$plinkPath =  Join-Path $labStartupRoot 'Tools\plink.exe'
} ElseIf ( $isLinux ) { 
	$labStartupRoot = '/hol'
	$sshPass = "/usr/bin/sshpass"
	$sshOptions = "-o StrictHostKeyChecking=accept-new"
}

$toolsDir = Join-Path -Path $labStartupRoot -ChildPath 'Tools'

# establish the dom variable based on the current FQDN
If ( $isWindows) {
	$ans = [System.Net.Dns]::GetHostByName($env:computerName).HostName
	($junk, $sav) = $ans.split('.')
	ForEach ( $p in $sav) { $dom = "$dom.$p" }
	$dom = $dom.substring(1)
}
If ( $isLinux ) { 
	$lcmd = "hostname -A" # 2024: change to hostname -A
	$fqdn = Invoke-Expression -Command $lcmd
	$i = $fqdn.IndexOf(".")
	$hostname = $fqdn.SubString(0,$i)
	$tl = $fqdn.length -1
	$dl = $tl - $hostname.length
	$dom = $fqdn.SubString($i+1,$dl-1)
}

$adminUser = 'administrator@vsphere.local'
$configIni = Join-Path -Path "/tmp" -ChildPath "config.ini"
$p = Select-String -Path $configIni -Pattern "^password =" | Out-String
$p = $p.TrimEnd()
($junk, $rootPassword) = $p.Split('= ')

### Variables
$svsName = 'vSwitchTemp'
$mgmtPgName = 'Management Network'

<#
#If not present, Load PowerCLI - legacy Windows stuff not needed
If( !( Test-Path 'C:\Program Files\WindowsPowerShell\Modules\VMware.VimAutomation.Core') ) {
	#Checks for VMware.VimAutomation.Core module - PowerCLI 6.5.1+
	Write-Host "No PowerCLI found, unable to continue."
	Write-VpodProgress "FAIL - No PowerCLI" 'FAIL-1'
	Return
} 
#>

# Disconnect from all vCenters to eliminate confusion
If( ($global:DefaultVIServers).Count -gt 0 ) {
	Disconnect-VIserver * -Confirm:$false | Out-Null
}

#Determine whether we will work on site A or site B
#Site A SSO is vsphere.local, Site B is vsphere2.local
$site = ''
While( ($site -ne 'a') -and ($site -ne 'b') -and ($site -ne 'q') ) {
	$site = Read-Host "Enter the site (a|b) or 'q' to quit"
	$site = $site.ToLower()
}
If( $site -eq 'q' ) { Return }

If( $site -eq 'b' ) {
	$adminUser = 'administrator@vsphere2.local'
}
Else {
	$adminUser = 'administrator@vsphere.local'
}

Write-Host "Using $adminUser"

#Set this to the numbers of the hosts that you want to configure
$numbers = Read-Host 'Host numbers as a comma-separated list (default=4,5,6)'
If( $numbers -ne '' ) { 
	$hostNumbers =  ($numbers.Split(',')) | %  { [int] $_ }
}
Else {
	#default to hosts 4-6
	$hostNumbers = (4,5,6)
	$numbers = '4,5,6'
}

# Generate the host names based on standard naming and entered numbers
$hostNames = @()
ForEach( $hostNumber in $hostNumbers ) { 
	$hostNames += ("esx-{0:00}{1}.${dom}" -f $hostNumber,$site)
}

Write-Host "Ready to work on site $($site.ToUpper())"
ForEach( $hostName in $hostNames ) {
	Write-Host "`t$hostName"
}
While( $answer -ne 'y' ) {
	$answer = Read-Host "Confirm? [Y|n]"
	$answer = $answer.ToLower()
	If( $answer -eq '' ) { $answer = 'y' }
	If( $answer -eq 'n' ) { Return }
}

$vCenterServer = "vcsa-01{0}.${dom}" -f $site
Try {
	Write-Host -ForegroundColor Yellow "`tConnecting to $vCenterServer..."
	# DEV
	Write-Host "Connect-VIserver $vCenterServer -username $adminUser -password $rootPassword"
	Connect-VIserver $vCenterServer -username $adminUser -password $rootPassword -ErrorAction Stop -ErrorVariable errorVar
} Catch {
	#Bail if the connection to vCenter does not work. Nothing else makes sense to try.
	Write-Host -ForegroundColor Red "ERROR: Unable to connect to vCenter $vCenterServer $errorVar"
	Return
}

#####################################################################

$dc = Get-Datacenter

#Get the VDS -- there should only be one in the base pod
$vdsName = "Region"+$site.ToUpper()+"01-vDS-COMP"
$vds = Get-VDSwitch -Name $vdsName

$ctr = 0
ForEach ($hostName in $hostNames) {
	
	If ( $ctr ) {
		Write-Host -ForegroundColor Yellow "Pausing 30 seconds for the environment to stabilize...`n`n"
		Start-Sleep -Seconds 30
	}
	
	Try {
		$vmhost = Get-VMHost -Location $dc -Name $hostName -ErrorAction SilentlyContinue
		Write-Host -ForegroundColor Green "Working on $hostName"
	} Catch {
			Write-Host -ForegroundColor Yellow "`t$hostName is not present. Moving on..."
			Continue
	}

	# Look for VMs registered on host, stop if found
	Write-Host "`tLooking for VMs..."
	$virtmachines = ($vmhost | Get-VM)
	
	Write-Host("`tProceeding...")
	
	If( $virtmachines.Count -gt 1 ) {
		Write-Host -ForegroundColor Red "VMs exist on host $hostName. Cannot continue."
		Continue
	}

	# Put the target into Maintenance Mode
	If ( $vmhost.ConnectionState -ne "Maintenance" ) {
		Try {
			Write-Host "`tEntering Maintenance Mode"
			$vmhost = Get-VMHost -Name $hostName -ErrorAction SilentlyContinue -ErrorVariable errorVar
			If ( $vmhost -eq $Null ) {				
				Write-Host -ForegroundColor Red "`t`t$hostName is not found. Please try again."
				Continue
			}
			$quiet = Set-VMHost -VMHost $vmhost -State Maintenance -ErrorVariable errorVar
			
			If ( -Not (waitForRunningTasks) ) {
				Write-Host -ForegroundColor Red "`t`t$hostName s unable to enter maintenance mode. Please try again."
				Continue
			}
			$vmhost = Get-VMHost -Name $hostName
			While ( $vmhost.ConnectionState -ne "Maintenance" ) {
				$state = $vmhost.ConnectionState
				Write-Host "`t`t$hostName state: $state"
				Start-Sleep -Seconds 1
				$vmhost = Get-VMHost -Name $hostName
			}
		} Catch {
			Write-Host -ForegroundColor Red "`t`t$hostName is unable to enter maintenance mode. Please try again. Error: $errorVar"
			Continue
		}
	}
	
	Write-Host "`tUnconfiguring iSCSI"
	#Disconnect iSCSI datastore from this host
	
	Write-Host "`t`tRemoving iSCSI HBA target(s)..."
	$vmhost = Get-VMHost -Name $hostName
	$iScsiHba = Get-VMHostHba -VMHost $vmhost -Type iScsi
	$iTarget = Get-IScsiHbaTarget -IScsiHba $iScsiHba
	If ( $iTarget -ne "" ) {
		$build = [int]$vmhost.build
		If ( $build  -ge 17630552 ) {
			# run esxcli iscsi session remove -A $hbaName
			$hbaName = ($vmhost | Get-VMHostHba -Type iScsi).Device
			Write-Host "`t`tRemoving iSCSI session from $hbaName (~5 sec)"
			$lcmd = "esxcli iscsi session remove -A $hbaName"
			If ( $isWindows ) { 
				$cmd = "Echo Y | $plinkPath -ssh $hostName -l root $lcmd  2>&1" 
			} Elseif ( $isLinux ) {
				$cmd = "$sshPass -p $rootPassword ssh $sshOptions root@$hostName $lcmd 2>&1"
			}
			Write-Host "`t`tEnding iSCSI sessions on $hbaName... (~10 sec)"
			Invoke-Expression -Command $cmd -ErrorVariable errorVar
			Write-Host $errorVar
			Start-Sleep -Seconds 5
		}
		Try {
			Remove-IScsiHbaTarget -Target $iTarget -Confirm:$false -ErrorAction SilentlyContinue -ErrorVariable errorVar
			If ( -Not (waitForRunningTasks) ) {
				Write-Host -ForegroundColor Red "`t`tUnable to remove iSCSI target(s) from $hostName. Please try again."
				Continue
			}
			# need to rescan/refresh to remove iSCSI datastore
			Write-Host "`t`tRescanning storage on $hostName... (~30 sec)"
			$vmhost | Get-VMhostStorage -RescanAllHba -RescanVmfs | Out-Null
			If ( -Not (waitForRunningTasks) ) {
				Write-Host -ForegroundColor Red "`t`tUnable to rescan storage on $hostName. Please try again."
				Continue
			}
			Write-Host "`tPausing 30 seconds for $hostName to quiesce..."
			Start-Sleep -Seconds 30
		} Catch {
			Write-Host -ForegroundColor Yellow "`t`tRemove iSCSI targets not needed for $hostName. $errorVar"
		}
	}

	#Unhook from vDS
	#Remove vmnic1 from VDS -- sleep is necessary to allow NIC to finish reassignment
	Write-Host ("`tDisconnecting $hostName from $vdsName." )
	Try {
		$pNic1 = Get-VMHostNetworkAdapter -VMHost $vmhost -Physical -Name "vmnic1" -VirtualSwitch $vds -ErrorAction SilentlyContinue
		If ( $pNic1 -eq $Null ) {
			Write-Host -ForegroundColor Yellow "`t`tvmnic1 already removed from $vdsName."
		} Else {
			Write-Host "`t`tRemoving $hostName vmnic1 from $vdsName (~10 sec)"
			Remove-VDSwitchPhysicalNetworkAdapter -VMHostNetworkAdapter $pNic1 -Confirm:$false -ErrorAction SilentlyContinue -ErrorVariable errorVar
			If ( -Not (waitForRunningTasks) ) {
					Write-Host -ForegroundColor Red "`t`tUnable to remove vmnic1 from $vdsName for $hostName. Please try again."
					Continue
				}
			$pNic1 = Get-VMHostNetworkAdapter -VMHost $vmhost -Physical -Name "vmnic1" -VirtualSwitch $vds -ErrorAction SilentlyContinue
			If ( $pNic1 -ne $Null ) {				
				Write-Host -ForegroundColor Red "`t`tUnable to remove vmnic1 from $vdsName. Please try again. $errorVar"
				Continue
			}
			Write-Host "`t`tPausing 10 seconds for $hostName to quiesce after removing vmmnic1..."
			Start-Sleep -Seconds 10
		}
	} Catch {
		If ( $errorVar -Like "*disconnected*" ) {
			Write-Host -ForegroundColor Red "`t`tUnable to remove vmnic1 from $vdsName. Please try again. $errorVar"
			Continue
		} Else {
			Write-Host -ForegroundColor Yellow "`t`tvmnic1 already removed from $vdsName."
		}
	} # Nothing to do since vmnic1 has already been removed

	#Look for standard vSwitch. If none, create a new one called "vSwitchTemp"
	Try { 
		Write-Host "`t`tChecking $hostName for existing vSwitch"
		$svs = Get-VirtualSwitch -Standard -VMHost $vmhost -Name $svsName -ErrorAction SilentlyContinue
		If ( $svs -eq $Null ) {
			Try {Write-Host "`t`tCreating new vSwitch $svsName on $hostName (~10 sec)"
				$pNic1 = Get-VMHostNetworkAdapter -VMHost $vmhost -Physical -Name "vmnic1" -ErrorAction SilentlyContinue
				$svs = New-VirtualSwitch -VMHost $vmhost -Name $svsName -Nic $pNic1 -ErrorVariable errorVar -ErrorAction SilentlyContinue
				If ( -Not (waitForRunningTasks) ) {
					Write-Host -ForegroundColor Red "`t`tUnable to create new vSwitch on $hostName. Please try again."
					Continue
				}
				$svs = Get-VirtualSwitch -Standard -VMHost $vmhost -Name $svsName -ErrorAction SilentlyContinue
				If ( $svs -eq $Null ) {
					Write-Host -ForegroundColor Red "`t`tCould not create $svsName on $hostName. $errorVar"
					Continue
				}
			} Catch {
				If ( $errorVar -Like "*busy*" ) {
					Write-Host -ForegroundColor Red "`t`t$hostName is too busy. Please try again later. Error: $errorVar"
					Continue
				}
			}	
		}		
	}
	Catch {
		Try {
			Write-Host "`t`tCreating new vSwitch on $hostName (~10 sec)"
			$svs = New-VirtualSwitch -VMHost $vmhost -Name $svsName -Nic $pNic1 -ErrorVariable errorVar -ErrorAction SilentlyContinue
			If ( -Not (waitForRunningTasks) ) {
				Write-Host -ForegroundColor Red "`t`tUnable to create new vSwitch on $hostName. Please try again."
				Continue
			}
		} Catch {
			If ( $errorVar -Like "*busy*" ) {
				Write-Host -ForegroundColor Red "`t`t$hostName is too busy. Please try again later. Error: $errorVar"
				Continue
			}
		}	
	}

	#Create the "Management Network" portgroup if it is not there already
	Try { 
		Write-Host "`t`tChecking $svsName for existing Management port group"
		$mgmtPg = Get-VirtualPortGroup -VirtualSwitch $svs -Name $mgmtPgName -ErrorAction SilentlyContinue
		If ( $mgmtPg -eq $Null ) {
			Try {
				Write-Host "`t`tCreating new port group on $hostName (~10 sec)"
				$mgmtPg = New-VirtualPortGroup -VirtualSwitch $svs -Name $mgmtPgName
				If ( -Not (waitForRunningTasks) ) {
					Write-Host -ForegroundColor Red "`t`tUnable to create new port group on $hostName. Please try again."
					Continue
				}
			} Catch {
				If ( $errorVar -Like "*busy*" ) {
					Write-Host -ForegroundColor Red "`t`t$hostName is too busy. Please try again later. Error: $errorVar"
					Continue
				}
			}
		}
	} Catch {
		Try {
			Write-Host "`t`tCreating new port group on $hostName (~10 sec)"
			$mgmtPg = New-VirtualPortGroup -VirtualSwitch $svs -Name $mgmtPgName
			If ( -Not (waitForRunningTasks) ) {
				Write-Host -ForegroundColor Red "`t`tUnable to create new port group on $hostName. Please try again."
				Continue
			}
		} Catch {
			If ( $errorVar -Like "*busy*" ) {
				Write-Host -ForegroundColor Red "`t`t$hostName is too busy. Please try again later. Error: $errorVar"
				Continue
			}
		}
	}
	
	#Remove vmk1, vmk2
	Write-Host "`t`tRemoving vmk1 and vmk2 (~20 sec)"
	$vmks = @("vmk1", "vmk2")
	ForEach ( $vmkName in $vmks ) {
		Try {
			$vmk = Get-VMHostNetworkAdapter -VMHost $vmhost -VMKernel -Name $vmkName -ErrorAction SilentlyContinue
			If ( $vmk ) {
				Remove-VMHostNetworkAdapter -Nic $vmk -Confirm:$false
				If ( -Not (waitForRunningTasks) ) {
					Write-Host -ForegroundColor Red "`t`tUnable to remove $vmkName on $hostName. Please try again."
					$abort = $True
					Continue
				}
				# for some reason need to pause here
				Write-Host "`t`tPausing 10 seconds for $hostName to quiesce after removing $vmkName..."
				Start-Sleep -Seconds 10
			}
		} Catch {
			Write-Host -ForegroundColor Yellow "`t`t$vmkName already removed."
		}
	}
	If ( $abort ) { Continue } # one or more vm kernel ports could not be removed. Go to the next host.
	
	Try {
		$vmk0 = $vmhost | Get-VMHostNetworkAdapter -VMKernel -Name 'vmk0' -VirtualSwitch $vds -ErrorAction SilentlyContinue
		If ( $vmk0 -eq $Null ) {
			Write-Host -ForegroundColor Yellow "`t`t$hostName vmk0 already migrated off of $vdsName."
		} Else {
			Write-Host "`t`tMigrating $hostName vmk0 to $svsName (~30 sec)"
			$svs = Get-VirtualSwitch -Standard -VMHost $vmhost -Name $svsName -ErrorAction SilentlyContinue
			$pNic1 = Get-VMHostNetworkAdapter -VMHost $vmhost -Physical -Name "vmnic1" -VirtualSwitch $svs
			Add-VirtualSwitchPhysicalNetworkAdapter -VirtualSwitch $svs -VMHostPhysicalNic $pNic1 -VMHostVirtualNic $vmk0 -VirtualNicPortgroup $mgmtPgName -Confirm:$false	-ErrorAction SilentlyContinue -ErrorVariable erroVar
			If ( -Not (waitForRunningTasks) ) {
				Write-Host -ForegroundColor Red "`t`tUnable to migrate $hostName vmk0 to $svsName. Please try again."
				Continue
			}
			$vmk0 = $vmhost | Get-VMHostNetworkAdapter -VMKernel -Name 'vmk0' -VirtualSwitch $vds -ErrorAction SilentlyContinue
			If ( $vmk0 -ne $Null ) {
				Write-Host -ForegroundColor Red "`t`tUnable to migrate $hostName vmk0 off of $vdsName. Please try again. Error: $errorVar"
				Continue
			}
			Start-Sleep -Seconds 30
		}
	} Catch {
			Write-Host -ForegroundColor Red "`t`tUnable to migrate $hostName vmk0 off of $vdsName. Please try again. Error: $errorVar"
			Continue
	}
	
	#Remove vmnic0 from vDS
	Write-Host "`t`tRemoving $hostName vmnic0 from $vdsName"
	$pNic0 = $vmhost | Get-VMHostNetworkAdapter -Physical -Name 'vmnic0'
	Try {
		Remove-VDSwitchPhysicalNetworkAdapter -VMHostNetworkAdapter $pNic0 -Confirm:$false -ErrorVariable errorVar
		If ( -Not (waitForRunningTasks) ) {
			Write-Host -ForegroundColor Red "`t`tUnable to remove vmnic0 from $vdsName. Please try again."
			Continue
		}
	} Catch {
		Write-Host -ForegroundColor Red "`t`tUnable to remove vmnic0 from $vdsName. Please try again. Error: $errorVar"
		Continue
	}

	#Remove host from vDS
	Write-Host "`tRemoving $hostName from $vdsName"
	Try {
		$vds | Remove-VDSwitchVMHost -VMHost $vmhost -Confirm:$false -ErrorVariable errorVar
		If ( -Not (waitForRunningTasks) ) {
			Write-Host -ForegroundColor Red "`t`tUnable to remove $hostName from $vdsName. Please try again."
			Continue
		}
	} Catch {
		Write-Host -ForegroundColor Red "`t`tUnable to remove $hostName from $vdsName. Please try again. Error: $errorVar"
		Continue
	}
 
	#Remove host from vCenter
	Write-Host "`tRemoving $hostName from vCenter"
	$vmhost | Remove-VMHost -Confirm:$false
	
	If ( $isWindows ) {
		#Remove puTTY session for this host
		$sessions = Get-ChildItem $puttyPath
		Write-Host "`tRemoving $hostName from puTTY"
		ForEach( $session in $sessions ) {
			if( $($session.name) -match $vmhost.Name ) {
				$delPath = $session.Name -replace 'HKEY_CURRENT_USER','HKCU:'
				Remove-Item -LiteralPath $delPath -Confirm:$false -ErrorAction Continue
			}
		}
	}
	
	# TODO: maybe. Remove or comment out the host from the config.ini for this vPod_SKU
	# on the Manager VM /vpodrepo
	# first get the /tmp/vPod_SKU.txt from the Manager.
	# then get the config.ini from the /vpodrepo on the Manager
	# then find and update the file.
	# put the updated config.ini back in the /vpodrepo on the Manager
	# then do a git push to update the remote repo.
	<#
	$resources = Join-Path -Path $labStartupRoot -ChildPath "Resources"
	$esxHostsFile = Join-Path -Path $resources -ChildPath "ESXiHosts.txt" 
	Write-Host "`tCommenting out $hostName in $esxHostsFile"
	$content = Get-Content -Path $esxHostsFile
	ForEach ( $line in $content ) {
		If ( $line -eq $hostName ) { $line = "#$line"  }
		$newcontent += "$line`n"
	}
	$newcontent.TrimEnd("`n") | Set-Content -Path $esxHostsFile -NoNewline
	$newcontent = ""
	#>
	
	Write-Host -ForegroundColor Green "Removed $hostName `n`n"
	$ctr++
}

#####################################################################

Disconnect-VIserver * -Confirm:$false

Write-Host -Fore Green "*** Finished ***"

### END ###
