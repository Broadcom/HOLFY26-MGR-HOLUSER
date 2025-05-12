# confighol.ps1 version 1.1 12-May 2025
# $args[0] server
# $args[1] user - case counts
# $args[2] password

If ( $args.Count -lt 3 ) {
	Write-Output "Usage: <server> <user> <password>"
	exit
}

Connect-VIserver -server $args[0] -user $args[1] -password $args[2]

# update local account policies
If ( -not (Get-InstalledModule -Name VMware.vSphere.SsoAdmin -ErrorAction silentlycontinue) ) {
    Install-Module -Name VMware.vSphere.SsoAdmin -Confirm:$false -Force
}
$localAccountPolicyInfo = Initialize-LocalAccountsPolicyInfo -MaxDays 9999 
Invoke-SetLocalAccountsGlobalPolicy -LocalAccountsPolicyInfo $localAccountPolicyInfo
Get-SsoPasswordPolicy | Set-SsoPasswordPolicy -ProhibitedPreviousPasswordsCount 1

ForEach ( $cluster in Get-Cluster ) {
	$quiet = Set-Cluster -Cluster $cluster -DrsAutomationLevel "PartiallyAutomated" -HAAdmissionControlEnabled $false -Confirm:$false
}

Disconnect-VIserver -Confirm:$false