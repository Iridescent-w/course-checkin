@echo off
if not exist "%LOCALAPPDATA%\CourseCheckinDemo\run.ps1" (
    echo Run install.cmd first.
    pause
    exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%LOCALAPPDATA%\CourseCheckinDemo\run.ps1"
if errorlevel 1 echo Submission failed. See the message above or open view-log.cmd.
pause
