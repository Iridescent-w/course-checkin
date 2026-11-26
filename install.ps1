$ErrorActionPreference = 'Stop'
$python = $null
foreach ($command in @('python.exe', 'python3.exe')) {
    $candidate = Get-Command $command -ErrorAction SilentlyContinue
    if ($candidate) {
        & $candidate.Source -c 'import sys, inspect, urllib.request; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { $python = $candidate.Source; break }
    }
}
if (-not $python) {
    Write-Host 'Installing Python 3.13 using Windows Package Manager...'
    & winget install --id Python.Python.3.13 --exact --source winget --scope user --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.10+ from python.org, then try again.' }
    $python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'
    & $python -c 'import inspect, urllib.request'
    if ($LASTEXITCODE -ne 0) { throw 'Python verification failed.' }
}
$appDir = Join-Path $env:LOCALAPPDATA 'CourseCheckinDemo'
$taskName = 'CourseCheckin-Daily'
$credentialPath = Join-Path $appDir 'credential.xml'
$configPath = Join-Path $appDir 'course_config.json'
$clientPath = Join-Path $appDir 'course_checkin.py'
$runnerPath = Join-Path $appDir 'run.ps1'

$serverUrl = (Read-Host 'Course test server origin, e.g. http://127.0.0.1:3033').Trim().TrimEnd('/')
$serverUri = $null
if (-not [Uri]::TryCreate($serverUrl, [UriKind]::Absolute, [ref]$serverUri) -or
    $serverUri.Scheme -notin @('http', 'https') -or $serverUri.AbsolutePath -ne '/' -or
    $serverUri.Query -or $serverUri.Fragment -or $serverUri.UserInfo) {
    throw 'Enter an origin such as http://127.0.0.1:3033, without a path.'
}

$runAtText = Read-Host 'Daily run time in 24-hour format (default 13:00)'
if ([string]::IsNullOrWhiteSpace($runAtText)) { $runAtText = '13:00' }
$runAt = [TimeSpan]::Zero
if (-not [TimeSpan]::TryParseExact($runAtText, 'hh\:mm', [Globalization.CultureInfo]::InvariantCulture, [ref]$runAt)) {
    throw 'Time must use 24-hour HH:mm format, for example 13:00.'
}
if ($runAt.TotalHours -ge 24) { throw 'Time must be between 00:00 and 23:59.' }

New-Item -ItemType Directory -Path $appDir -Force | Out-Null
$studentNo = Read-Host 'Course account student number'
$securePassword = Read-Host 'Course account password (hidden input)' -AsSecureString
if ([string]::IsNullOrWhiteSpace($studentNo) -or $securePassword.Length -eq 0) {
    throw 'Account and password must not be empty.'
}
[PSCredential]::new($studentNo, $securePassword) |
    Export-Clixml -LiteralPath $credentialPath

$config = [ordered]@{ server_url = $serverUrl; run_at = $runAtText }
$config | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'course_checkin.py') -Destination $clientPath -Force

$runner = @'
$ErrorActionPreference = 'Stop'
$appDir = Join-Path $env:LOCALAPPDATA 'CourseCheckinDemo'
$mutex = [Threading.Mutex]::new($false, 'Local\CourseCheckinDemo')
$acquired = $false
try { $acquired = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $acquired = $true }
if (-not $acquired) { $mutex.Dispose(); Write-Host 'Another instance is running.'; exit 0 }
try {
$config = Get-Content -LiteralPath (Join-Path $appDir 'course_config.json') -Raw | ConvertFrom-Json
$cred = Import-Clixml -LiteralPath (Join-Path $appDir 'credential.xml')
$env:COURSE_BASE_URL = $config.server_url
$env:COURSE_STATE_DIR = $appDir
$env:COURSE_STUDENT_NO = $cred.UserName
$env:COURSE_PASSWORD = [Net.NetworkCredential]::new('', $cred.Password).Password
try {
    & '__PYTHON__' '__CLIENT__'
    exit $LASTEXITCODE
} finally {
    Remove-Item Env:\COURSE_BASE_URL, Env:\COURSE_STATE_DIR, `
        Env:\COURSE_STUDENT_NO, Env:\COURSE_PASSWORD -ErrorAction SilentlyContinue
}
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
'@
$runner = $runner.Replace('__PYTHON__', $python.Replace("'", "''")).Replace('__CLIENT__', $clientPath.Replace("'", "''"))
Set-Content -LiteralPath $runnerPath -Value $runner -Encoding UTF8

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runnerPath`""
$at = (Get-Date).Date.Add($runAt)
$trigger = New-ScheduledTaskTrigger -Daily -At $at
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force | Out-Null

Write-Host "Installed as $taskName. Daily time: $runAtText (this computer's local time)."
Write-Host 'The task runs while this Windows account is signed in.'
Write-Host "Encrypted credentials: $credentialPath"
Write-Host "Local log: $(Join-Path $appDir 'course_checkin.log')"
Write-Host 'Use run-now.cmd to submit immediately, or wait for the next scheduled time.'
