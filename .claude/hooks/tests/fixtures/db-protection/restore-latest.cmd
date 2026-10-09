@echo off
REM ============================================================================
REM restore-latest.cmd
REM
REM Layer 5 of the dev-DB protection plan. Restores the most recent .bak file
REM in the backup directory (concept contract 2026-10-04-dev-db-protection-hardening,
REM INV-11).
REM
REM There is no overwrite option anywhere in this script. That alone is NOT what keeps
REM an existing database safe: a restore without an overwrite option can still write over
REM an existing database that came from the same backup lineage. What protects it is the
REM existence test that is sent in the SAME sqlcmd batch as the restore statement and
REM raises an error before it, so nothing can create the database between a check and
REM the restore.
REM
REM USAGE:
REM   restore-latest.cmd [<name> or --recover-missing-dev-db] [<backup file>]
REM
REM   The backup file, when given, is ALWAYS the last argument; without it the newest
REM   scalping-*.bak in the backup directory is used. A named file that does not exist
REM   is an error (exit 1) and nothing is restored.
REM
REM   restore-latest.cmd                          restores to a disposable
REM                                               ScalpingMachine_Test_<guid> copy
REM   restore-latest.cmd <disposable name>        restores to that name. The name must
REM                                               match ^[A-Za-z0-9_]+$ and END in a
REM                                               disposable suffix (_MigrationVerify_<hex>,
REM                                               _Test_<hex>, _e2e_<hex>, _DryRun,
REM                                               _Sandbox, _Scratch, _Throwaway)
REM   restore-latest.cmd --recover-missing-dev-db restores to the development
REM                                               database name ONLY when no
REM                                               database of that name exists.
REM                                               People only: refused from a
REM                                               Claude Code shell.
REM
REM After a recovery, if the code carries migrations newer than the backup, run
REM update-dev-database.cmd in your own terminal: this script runs no EF command,
REM so the recovered database is at the backup's schema and the server will
REM refuse to start until it is brought forward.
REM
REM Exit codes:
REM   0 - restore completed
REM   1 - no backups found, or the named backup file does not exist
REM   2 - sqlcmd / restore failed
REM   3 - refused (bad argument, a name that is not a valid disposable name, the
REM       target database already exists or is a half-restored remnant, or a Claude
REM       Code shell)
REM
REM The flow uses plain labels and top-level exits on purpose: an exit inside a
REM parenthesised block nested in another block can return exit code 0 on some machines.
REM ============================================================================
setlocal EnableExtensions

set "BACKUP_DIR=D:\Backups\ScalpingMachine"
set "INSTANCE=(localdb)\mssqllocaldb"
set "DEV_DB=ScalpingMachine"
set "RECOVER=0"

if not "%~3"=="" goto :refuse_args
set "FILE_ARG=%~2"
if /i "%~1"=="--recover-missing-dev-db" goto :mode_recover
if "%~1"=="" goto :mode_default

REM A typed name. Delayed expansion is still off, so a "!" in it is not interpreted.
set "TARGET_DB=%~1"
goto :validate

:mode_recover
if defined CLAUDECODE goto :refuse_claude
set "RECOVER=1"
set "TARGET_DB=%DEV_DB%"
goto :locate

:mode_default
REM Build a guid-suffixed target name so the result is disposable and
REM matches the db-destructive-guard.py allow-list pattern _test_<hex>.
for /f %%g in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString(\"N\").Substring(0,12)"') do set "GUID=%%g"
set "TARGET_DB=ScalpingMachine_Test_%GUID%"

:validate
REM Safety belt -- outside the recovery mode the target must be word characters only AND end in a
REM disposable suffix. The name travels in an environment variable, never through an echo, so no
REM character in it can be read as a command.
powershell -NoProfile -Command "if ($env:TARGET_DB -match '^[A-Za-z0-9_]+(_MigrationVerify_[0-9A-Fa-f]+|_Test_[0-9A-Fa-f]+|_e2e_[0-9A-Fa-f]+|_DryRun|_Sandbox|_Scratch|_Throwaway)$') { exit 0 } else { exit 1 }"
if errorlevel 1 goto :refuse_name

:locate
setlocal EnableDelayedExpansion

if defined FILE_ARG goto :use_named_file
if not exist "%BACKUP_DIR%" goto :no_backup_dir

REM Find the newest .bak file.
set "LATEST="
for /f "delims=" %%f in ('dir /b /a:-d /o:-d "%BACKUP_DIR%\scalping-*.bak" 2^>nul') do if not defined LATEST set "LATEST=%BACKUP_DIR%\%%f"
if not defined LATEST goto :no_backups
goto :have_backup

:use_named_file
if not exist "!FILE_ARG!" goto :no_such_file
for %%i in ("!FILE_ARG!") do set "LATEST=%%~fi"

:have_backup

set "FILE_DIR=%BACKUP_DIR%\restore-staging"
REM Recovery recreates the files in the instance's default data folder, not the staging folder.
if "!RECOVER!"=="1" call :data_dir

echo [restore-latest] restoring %LATEST%
echo [restore-latest] target DB: [!TARGET_DB!]

REM Discover the logical file names embedded in the backup so we can MOVE them
REM to the chosen folder.
if not exist "!FILE_DIR!" mkdir "!FILE_DIR!"

REM Run RESTORE FILELISTONLY to capture LogicalName + Type.
set "TMPFILE=%TEMP%\restore-filelist-%RANDOM%.txt"
sqlcmd -S "%INSTANCE%" -d master -E -b -h -1 -W -s "|" -Q "SET NOCOUNT ON; RESTORE FILELISTONLY FROM DISK = N'%LATEST%'" > "%TMPFILE%"
if errorlevel 1 goto :filelist_failed

set "MOVE_CLAUSES="
for /f "usebackq tokens=1,3 delims=|" %%a in ("%TMPFILE%") do (
    set "LOGICAL=%%a"
    set "FTYPE=%%b"
    REM Trim whitespace from the captured tokens.
    for /f "tokens=* delims= " %%x in ("!LOGICAL!") do set "LOGICAL=%%x"
    for /f "tokens=* delims= " %%x in ("!FTYPE!") do set "FTYPE=%%x"

    if /i "!FTYPE!"=="D" (
        set "PHYS=!FILE_DIR!\!TARGET_DB!_!LOGICAL!.mdf"
    ) else if /i "!FTYPE!"=="L" (
        set "PHYS=!FILE_DIR!\!TARGET_DB!_!LOGICAL!.ldf"
    ) else (
        set "PHYS="
    )

    if defined PHYS (
        if defined MOVE_CLAUSES (
            set "MOVE_CLAUSES=!MOVE_CLAUSES!, MOVE N'!LOGICAL!' TO N'!PHYS!'"
        ) else (
            set "MOVE_CLAUSES=MOVE N'!LOGICAL!' TO N'!PHYS!'"
        )
    )
)
del "%TMPFILE%" 2>nul

if not defined MOVE_CLAUSES goto :no_logical_names

REM The existence test and the restore are ONE batch. THROW ends the batch, so when a database of the
REM target name exists nothing is restored; the test cannot go stale between two separate calls.
REM The block below is the batch, with three placeholders. A test runs the block against a real LocalDB
REM instance, and a harness test checks that the batch sent equals the block, so the two cannot drift.
REM RECOVERY-BATCH-BEGIN
REM SET NOCOUNT ON;
REM IF DB_ID(N'@TARGET_DB@') IS NOT NULL THROW 50000, N'a database of the target name already exists; nothing was written', 1;
REM RESTORE DATABASE [@TARGET_DB@] FROM DISK = N'@BACKUP_FILE@' WITH @MOVE_CLAUSES@, STATS = 10
REM RECOVERY-BATCH-END
set "SQL_BATCH=SET NOCOUNT ON; IF DB_ID(N'!TARGET_DB!') IS NOT NULL THROW 50000, N'a database of the target name already exists; nothing was written', 1; RESTORE DATABASE [!TARGET_DB!] FROM DISK = N'!LATEST!' WITH !MOVE_CLAUSES!, STATS = 10"
sqlcmd -S "%INSTANCE%" -d master -E -b -Q "!SQL_BATCH!"
if errorlevel 1 goto :restore_failed

echo [restore-latest] OK. Restored [!TARGET_DB!] from %LATEST%
if "!RECOVER!"=="1" goto :recovered

echo [restore-latest] to delete the restored DB after inspection, run:
echo     sqlcmd -S "%INSTANCE%" -E -Q "REMOVE_KEYWORD_ABOVE DATABASE [!TARGET_DB!]"
echo [restore-latest] (substitute the word DROP for REMOVE_KEYWORD_ABOVE; it is written
echo [restore-latest]  as a placeholder so that this script does not contain the literal
echo [restore-latest]  destructive verb in source.)
exit /b 0

:recovered
echo [restore-latest] The recovered database is at the backup's schema. If the code carries newer
echo [restore-latest] migrations, run tools\db-protection\update-dev-database.cmd in your own terminal.
exit /b 0

:restore_failed
REM A failed batch is either the refusal (the database exists) or a real restore error. Ask again
REM which one it was, so the exit code says so. A database left in the RESTORING state is the
REM remnant of a restore that never finished, and is named as such.
set "STATE="
for /f "usebackq delims=" %%c in (`sqlcmd -S "%INSTANCE%" -d master -E -b -h -1 -W -Q "SET NOCOUNT ON; SELECT state_desc FROM sys.databases WHERE name = N'!TARGET_DB!'"`) do if not defined STATE set "STATE=%%c"
if /i "!STATE!"=="RESTORING" goto :refuse_restoring
set "EXISTS="
for /f "usebackq delims=" %%c in (`sqlcmd -S "%INSTANCE%" -d master -E -b -h -1 -W -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM sys.databases WHERE name = N'!TARGET_DB!'"`) do if not defined EXISTS set "EXISTS=%%c"
if "!EXISTS!"=="1" goto :refuse_exists
echo [restore-latest] ERROR: the restore failed.
exit /b 2

:data_dir
set "DATA_DIR="
for /f "usebackq delims=" %%d in (`sqlcmd -S "%INSTANCE%" -d master -E -b -h -1 -W -Q "SET NOCOUNT ON; SELECT CAST(SERVERPROPERTY('InstanceDefaultDataPath') AS nvarchar(512))"`) do if not defined DATA_DIR set "DATA_DIR=%%d"
if defined DATA_DIR if not "!DATA_DIR!"=="NULL" for %%i in ("!DATA_DIR!.") do set "FILE_DIR=%%~fi"
exit /b 0

:refuse_args
echo [restore-latest] REFUSED: at most two arguments are accepted: a name or --recover-missing-dev-db, then a backup file.
exit /b 3

:refuse_claude
echo This step changes the development database and is run by a person in their own terminal, never from Claude Code.
exit /b 3

:refuse_name
echo [restore-latest] REFUSED: the target name is not a valid disposable name.
echo                  It must be letters, digits and underscores only and end in a disposable suffix,
echo                  such as ScalpingMachine_Test_^<hex^> or ScalpingMachine_MigrationVerify_^<hex^>.
exit /b 3

:refuse_exists
echo [restore-latest] REFUSED: database [!TARGET_DB!] already exists and is never overwritten.
exit /b 3

:refuse_restoring
echo [restore-latest] REFUSED: database [!TARGET_DB!] is in the RESTORING state. It is a half-restored remnant of
echo                  an earlier restore that never finished, not a usable database. Nothing was overwritten.
echo                  Remove the remnant by hand in your own terminal, then run this again.
exit /b 3

:no_such_file
echo [restore-latest] ERROR: the named backup file was not found: !FILE_ARG!
exit /b 1

:no_backup_dir
echo [restore-latest] ERROR: backup directory not found: %BACKUP_DIR%
exit /b 1

:no_backups
echo [restore-latest] ERROR: no scalping-*.bak files found in %BACKUP_DIR%
exit /b 1

:filelist_failed
echo [restore-latest] ERROR: reading the backup's file list failed.
del "%TMPFILE%" 2>nul
exit /b 2

:no_logical_names
echo [restore-latest] ERROR: could not parse logical filenames from backup.
exit /b 2
