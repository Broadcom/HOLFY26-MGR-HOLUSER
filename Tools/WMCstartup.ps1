# WMCStartup.ps1 - version 1.1 - 26-May 2024
$sleep_seconds = 5

# Empty recycle bin
Write-Output "Emptying the Recylce Bin..."
Clear-RecycleBin -Force -Confirm:$false

# empty the C:\Temp folder
Write-Output "Clearing C:\Temp folder..."
Remove-Item "C:\Temp\*" -Confirm:$false -Recurse

#Address vSphere 8 Windows console locking issue
Write-Output "Preventing Windows console locking..."
$psProcs = Get-Process -Name "vmtoolsd" | Select-Object Id
ForEach ( $proc in $psProcs ) {
	Stop-Process -Id $proc.Id -Force
	Sleep $sleep_seconds
}
While ( $true ) {
	Try {
		Write-Output "Restarting VMware Tools..."
		Start-Service -Name "VMTools"
		Break
	} Catch {
		Write-Output "Could not start VMware Tools. Will try again..."
	}
	Sleep $sleep_seconds
}

<#
# I am unable to to get this to work correctly when run from the Manager VM
# delete all destkoptinfo64.exe processes then start a single instance
$deskProc = Get-Process -ProcessName 'DesktopInfo64' -ErrorAction SilentlyContinue
ForEach ( $proc in $deskProc ) {
	Stop-Process -Id $proc.Id -Force
}
While ( $true ) {
	Try {
		Start-Process -Verb runAs -FilePath 'C:\desktopinfo\DesktopInfo64.exe'
		Write-Output "Restarting DesktopInfo..."
		Break
	} Catch {
		Write-Output "Could not start DesktopInfo. Will try again..."
	}
	Sleep $sleep_seconds
}
#>
 
