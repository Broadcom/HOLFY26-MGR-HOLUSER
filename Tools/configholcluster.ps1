# confighol.ps1 version 1.0 07-May 2025
# $args[0] server
# $args[1] user - case counts
# $args[2] password
# $args[3] cluster

If ( $args.Count -lt 3 ) {
	Write-Output "Usage: <server> <user> <password>"
	exit
}

Connect-VIserver -server $args[0] -user $args[1] -password $args[2]
#$clusters = Get-Cluster
ForEach ( $cluster in Get-Cluster ) {
	$quiet = Set-Cluster -Cluster $cluster -DrsAutomationLevel "PartiallyAutomated" -HAAdmissionControlEnabled $false -Confirm:$false
}
Disconnect-VIserver -Confirm:$false