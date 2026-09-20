$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root "scripts\RUN_SERVER.bat"
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$script`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
try {
  Register-ScheduledTask -TaskName "RC Rock Crawling Timing Server" -Action $action -Trigger $trigger -Settings $settings -Description "Offline RC timing server" -Force | Out-Null
  Write-Host "Autostart task installed."
} catch {
  Write-Error "Could not install Task Scheduler entry. Run PowerShell as Administrator and try again."
}
