@echo off
REM ============================================================================
REM check-protection-status.cmd
REM
REM Reports, per layer, whether the dev-DB protection is actually in place. It
REM only READS: it opens no development database (the trigger query connects to
REM the server's master database and reads the server-trigger catalog), changes
REM nothing, and prints whether the user-secret connection string is present
REM (yes or no) but never its value.
REM
REM Layers reported:
REM   Layer 1  server trigger present and enabled
REM   Layer 5  nightly backup task state, last result, next run
REM            newest backup name and age (down when older than 48 hours)
REM   Layer 4  user-secret ConnectionStrings:ScalpingDb present (yes or no)
REM            committed appsettings.json ScalpingDb empty (yes or no)
REM
REM Exit codes:
REM   0 - every layer is up
REM   1 - at least one layer is down (each is marked DOWN above)
REM ============================================================================
setlocal EnableExtensions EnableDelayedExpansion

set "INSTANCE=(localdb)\mssqllocaldb"
set "BACKUP_DIR=D:\Backups\ScalpingMachine"
set "TASK_NAME=ScalpingMachine-Dev-DB-Nightly-Backup"
set "REPO_ROOT=%~dp0..\..\"
set "API_PROJ=%REPO_ROOT%src\ScalpingMachine.API"
set "APPSETTINGS=%API_PROJ%\appsettings.json"
set /a FAILED=0

echo [check-protection-status] Layer 1: server trigger
set "TRIGGER_STATE="
for /f "usebackq delims=" %%t in (`sqlcmd -S "%INSTANCE%" -d master -E -b -h -1 -W -Q "SET NOCOUNT ON; SELECT CASE WHEN is_disabled = 0 THEN 'ENABLED' ELSE 'DISABLED' END FROM sys.server_triggers WHERE name = N'trg_protect_dev_databases'"`) do if not defined TRIGGER_STATE set "TRIGGER_STATE=%%t"
if /i "!TRIGGER_STATE!"=="ENABLED" (
    echo     trg_protect_dev_databases: present and ENABLED -- UP
) else (
    if not defined TRIGGER_STATE set "TRIGGER_STATE=not found or server unreachable"
    echo     trg_protect_dev_databases: !TRIGGER_STATE! -- DOWN
    set /a FAILED+=1
)

echo [check-protection-status] Layer 5: nightly backup task
schtasks /Query /TN "%TASK_NAME%" /V /FO LIST 2>nul | findstr /B /C:"Status:" /C:"Last Run Time:" /C:"Last Result:" /C:"Next Run Time:"
schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if errorlevel 1 (
    echo     task %TASK_NAME%: not installed -- DOWN
    set /a FAILED+=1
) else (
    echo     task %TASK_NAME%: installed -- UP
)

echo [check-protection-status] Layer 5: newest backup
powershell -NoProfile -Command "$f = Get-ChildItem '%BACKUP_DIR%' -Filter 'scalping-*.bak' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($null -eq $f) { Write-Output '    no backup found'; exit 1 }; $h = [int]((Get-Date) - $f.LastWriteTime).TotalHours; Write-Output ('    ' + $f.Name + ' is ' + $h + ' hours old'); if ($h -gt 48) { exit 2 }"
if errorlevel 1 (
    echo     newest backup: missing or older than 48 hours -- DOWN
    set /a FAILED+=1
) else (
    echo     newest backup: recent -- UP
)

echo [check-protection-status] Layer 4: connection string location
REM The exact key, then " = ", then at least one character: an empty value and a key that merely
REM starts with this name (ConnectionStrings:ScalpingDbOld) both read as absent. The value is discarded.
dotnet user-secrets list --project "%API_PROJ%" 2>nul | findstr /R /C:"^ConnectionStrings:ScalpingDb = ." >nul
if errorlevel 1 (
    echo     user secret ConnectionStrings:ScalpingDb present: no -- DOWN
    set /a FAILED+=1
) else (
    echo     user secret ConnectionStrings:ScalpingDb present: yes -- UP
)

REM appsettings.json carries comments, so it is matched as text rather than parsed as JSON.
findstr /R /C:"^ *\"ScalpingDb\" *: *\"\" *,* *$" "%APPSETTINGS%" >nul
if errorlevel 1 (
    echo     committed appsettings.json ScalpingDb empty: no -- DOWN
    set /a FAILED+=1
) else (
    echo     committed appsettings.json ScalpingDb empty: yes -- UP
)

if %FAILED% GTR 0 goto :some_down
echo [check-protection-status] all layers UP.
exit /b 0

:some_down
echo [check-protection-status] %FAILED% layer check^(s^) DOWN.
exit /b 1
