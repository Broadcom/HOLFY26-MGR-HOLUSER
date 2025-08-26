Function Enable-InternetProxy {
	[CmdletBinding()]
	PARAM(
		[Parameter(Mandatory=$True,ValueFromPipeline=$true,ValueFromPipelineByPropertyName=$true)]
		[String[]]$Proxy,
		
		[Parameter(Mandatory=$False,ValueFromPipeline=$true,ValueFromPipelineByPropertyName=$true)]
		[AllowEmptyString()]
		[String[]]$Override

	)
	
	BEGIN {
		$regKey="HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
	}
	
	PROCESS {
		Set-ItemProperty -path $regKey ProxyEnable -value 1 -ErrorAction Stop
		Set-ItemProperty -path $regKey ProxyServer -value $Proxy -ErrorAction Stop
		Set-ItemProperty -path $regKey ProxyOverride -value $Override -ErrorAction Stop
		Set-ItemProperty -path $regKey AutoConfigURL -Value "" -ErrorAction Stop
		
		#must run IE in order to have the proxy reconfiguration take effect -- thanks Microsoft!
		Write-Output 'Launching IE and hitting a URL to make the proxy configuration "stick"'
		$url = 'https://www.vmware.com'
		$ie = New-Object -com internetexplorer.application
		$ie.visible = $false
		$ie.navigate($url)
		Start-Sleep -Seconds 5
		Write-Output 'Stop iexplorer'
		Kill -ProcessName iexplore -ErrorAction SilentlyContinue
		Write-Output 'Finished.'
	}
	
	END {
		Write-Output "Proxy is now Enabled"
		Write-Output "Proxy Server : $Proxy"
		Write-Output "Proxy Override : $Override"
	}
} #END Enable-InternetProxy

$sleep_seconds = 5

#So the Odyssey client can reach the required API endpoints - function is in current LabStartupFunctions
Enable-InternetProxy -Proxy proxy:3128 -Override "192.168.*;10.*;172.*;*.$dom;<local>"

#SET REG FOR SILENT JSON
reg add "HKEY_CLASSES_ROOT\MIME\Database\Content Type\application/json" /t REG_SZ /d "{25336920-03F9-11cf-8FD0-00AA00686F13}" /f
reg add "HKEY_CLASSES_ROOT\MIME\Database\Content Type\application/json" /v Encoding /t REG_DWORD /d 0x08000000 /f
reg add "HKEY_CLASSES_ROOT\MIME\Database\Content Type\application/json" /v CLSID /t REG_SZ /d "{25336920-03F9-11cf-8FD0-00AA00686F13}" /f


Start-Sleep -Seconds $sleep_seconds
$test_url = "https://q1uk5yfspf.execute-api.us-east-2.amazonaws.com/api/v2/public/game?join_code="
$ie = New-Object -com internetexplorer.application
$ie.visible = $false
$ie.navigate($test_url)
Start-Sleep -Seconds $sleep_seconds
Write-Output 'Stop Internet Explorer'
Kill -ProcessName 'iexplore' -erroraction 'silentlycontinue'
Write-Output "Finished proxy config.`n`n"
Start-Sleep -Seconds $sleep_seconds
	
$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut('C:\Users\Administrator\Desktop\Play VMware Odyssey.lnk')
#$Shortcut.WindowStyle = 7 #minimized
$Shortcut.WindowStyle = 1 #activated, original size, position
$Shortcut.TargetPath = "C:\Users\Administrator\odyssey-launcher.exe"
$Shortcut.Save()