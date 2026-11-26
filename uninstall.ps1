$taskName = 'CourseCheckin-Daily'
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host 'Scheduled task removed.'
} else {
    Write-Host 'No scheduled task was found.'
}
Write-Host "Local credentials and logs remain under $env:LOCALAPPDATA\CourseCheckinDemo."
Write-Host 'Remove that folder yourself if you also want to delete local settings and logs.'
