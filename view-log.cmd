@echo off
if exist "%LOCALAPPDATA%\CourseCheckinDemo\course_checkin.log" (
    start "" notepad.exe "%LOCALAPPDATA%\CourseCheckinDemo\course_checkin.log"
) else (
    echo No log yet. Run install.cmd and run-now.cmd first.
    pause
)
