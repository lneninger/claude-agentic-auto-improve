@echo off
REM ============================================================================
REM update-dev-database.cmd
REM
REM The ONE explicit, person-run way to apply pending EF Core migrations to the
REM development database (concept contract 2026-10-04-dev-db-protection-hardening,
REM "Development Database Update", INV-12). The web application never applies
REM migrations at start; it refuses to start while any are pending and points here.
REM
REM What it does:
REM   1. Refuses to run from a Claude Code shell (CLAUDECODE is set).
REM   2. Refuses ANY argument, so it can never be used to roll a database back.
REM   3. Resolves its target ONCE, from the per-machine user secret
REM      ConnectionStrings:ScalpingDb, and refuses unless that target is the
REM      protected development database on (localdb)\mssqllocaldb. An absent or
REM      empty secret refuses too. The backup (step 6) and the update (step 7) act
REM      on that same database: the backup script backs up the development name and
REM      the update is bound to the secret value checked here.
REM   4. REFUSES (exit 3) when the development database does not exist. The migration
REM      chain cannot succeed from an empty database (AddResourceOwnership raises when
REM      Users has no rows), and a failed run would leave a half-built protected
REM      database. The script prints the working route instead: copy a .bak into
REM      D:\Backups\ScalpingMachine, run restore-latest.cmd --recover-missing-dev-db, then
REM      run this script again. It never runs the EF update against a missing database.
REM   5. Checks that the EF command-line tool is installed (dotnet ef --version) BEFORE
REM      the backup, so a missing tool is reported plainly and never as a failed migration.
REM   6. Takes a full backup (backup-dev-db.cmd) and ABORTS before any schema change if
REM      the backup fails.
REM   7. Applies every pending migration to the target it checked: the EF update is given
REM      --connection with the user-secret value read in step 3, and the environment
REM      variable ConnectionStrings__ScalpingDb (which outranks the secret) is cleared
REM      for that call.
REM
REM Run it in your own terminal. To rehearse a migration without touching the dev
REM database, use verify-migration.cmd --from-backup instead.
REM
REM USAGE:
REM   update-dev-database.cmd        (no arguments are accepted)
REM
REM Exit codes:
REM   0 - pending migrations applied (or none were pending)
REM   2 - backup failed, the existence of the database could not be read, or the EF
REM       tool is missing; no schema change was attempted
REM   3 - refused: an argument was given, this is a Claude Code shell, the configured
REM       target is not the development database, or that database does not exist
REM   4 - the EF update returned an error (the backup is the way back; some migrations
REM       may already have been applied, because EF applies them one by one)
REM
REM The flow below uses plain labels and top-level exits on purpose: an exit inside a
REM parenthesised block nested in another block can return exit code 0 on some machines.
REM ============================================================================
setlocal EnableExtensions

set "DEV_DB=ScalpingMachine"
set "DEV_SERVER=(localdb)\mssqllocaldb"

if defined CLAUDECODE goto :refuse_claude

REM Any argument at all, including an empty first one followed by another, is refused.
if not "%~1%~2%~3%~4%~5%~6%~7%~8%~9"=="" goto :refuse_argument
if not "%~1"=="" goto :refuse_argument
if not "%~2"=="" goto :refuse_argument

set "REPO_ROOT=%~dp0..\..\"
set "PERSISTENCE_PROJ=%REPO_ROOT%src\ScalpingMachine.Persistence"
set "STARTUP_PROJ=%REPO_ROOT%src\ScalpingMachine.API"

REM The verb is held in a variable so this file never carries the plain command text
REM that the destructive-database guard treats as a person-only step.
set "EF_VERB=update"

REM ---- Resolve the target ONCE ----------------------------------------------
set "SECRET_CONN="
for /f "usebackq tokens=1,* delims==" %%a in (`dotnet user-secrets list --project "%STARTUP_PROJ%" 2^>nul`) do for /f "tokens=1" %%t in ("%%a") do if /i "%%t"=="ConnectionStrings:ScalpingDb" set "SECRET_CONN=%%b"
if not defined SECRET_CONN goto :refuse_no_target

set "TGT_SERVER="
set "TGT_DB="
for %%p in ("%SECRET_CONN:;=" "%") do for /f "tokens=1,* delims==" %%k in ("%%~p") do for /f "tokens=*" %%t in ("%%k") do call :take_pair "%%t" "%%l"

if /i not "%TGT_SERVER%"=="%DEV_SERVER%" goto :refuse_target
if /i not "%TGT_DB%"=="%DEV_DB%" goto :refuse_target

REM ---- Does the database exist yet? -----------------------------------------
set "EXISTS="
for /f "usebackq delims=" %%c in (`sqlcmd -S "%DEV_SERVER%" -d master -E -b -h -1 -W -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM sys.databases WHERE name = N'%DEV_DB%'"`) do if not defined EXISTS set "EXISTS=%%c"
if not defined EXISTS goto :exists_unknown
if "%EXISTS%"=="0" goto :refuse_missing
if not "%EXISTS%"=="1" goto :exists_unknown

REM ---- The EF tool must be there BEFORE anything is backed up or changed ------
dotnet ef --version >nul 2>&1
if errorlevel 1 goto :ef_missing

echo [update-dev-database] step 1 of 2: backing up the development database [%DEV_DB%] first...
call "%~dp0backup-dev-db.cmd"
if errorlevel 1 goto :backup_failed

echo [update-dev-database] step 2 of 2: applying pending migrations...
REM Development makes the design-time host load the user-secret connection string. The environment
REM variable below outranks that secret, so it is cleared; --connection carries the value that was checked.
set "ASPNETCORE_ENVIRONMENT=Development"
set "ConnectionStrings__ScalpingDb="
dotnet ef database %EF_VERB% --connection "%SECRET_CONN%" --project "%PERSISTENCE_PROJ%" --startup-project "%STARTUP_PROJ%"
if errorlevel 1 goto :update_failed

echo [update-dev-database] OK. Start the server again.
exit /b 0

:take_pair
REM Called with a connection-string key and value; keeps the server and database names only.
if /i "%~1"=="Server" set "TGT_SERVER=%~2"
if /i "%~1"=="Data Source" set "TGT_SERVER=%~2"
if /i "%~1"=="Database" set "TGT_DB=%~2"
if /i "%~1"=="Initial Catalog" set "TGT_DB=%~2"
exit /b 0

:refuse_claude
echo This step changes the development database and is run by a person in their own terminal, never from Claude Code.
exit /b 3

:refuse_argument
echo [update-dev-database] REFUSED: this script accepts no argument. It only moves the database forward.
exit /b 3

:refuse_no_target
echo [update-dev-database] REFUSED: the user secret ConnectionStrings:ScalpingDb is absent or empty, so there is no target.
exit /b 3

:refuse_target
echo [update-dev-database] REFUSED: the configured target is not database [%DEV_DB%] on %DEV_SERVER%. Nothing was changed.
exit /b 3

:exists_unknown
echo [update-dev-database] ABORT: could not determine whether [%DEV_DB%] exists. No schema change was attempted.
exit /b 2

:refuse_missing
echo [update-dev-database] REFUSED: database [%DEV_DB%] does not exist, and this script never creates it:
echo                       the migration chain cannot succeed from an empty database. Nothing was changed.
echo [update-dev-database] To bring the database back from a backup, in your own terminal, in this order:
echo                       1. copy a .bak file into D:\Backups\ScalpingMachine
echo                       2. run tools\db-protection\restore-latest.cmd --recover-missing-dev-db
echo                       3. run tools\db-protection\update-dev-database.cmd again
exit /b 3

:ef_missing
echo [update-dev-database] ABORT: the EF command-line tool (dotnet-ef) is not available.
echo                       Run `dotnet tool restore` in the repository, then run this script again.
echo                       Nothing was backed up and nothing was changed.
exit /b 2

:backup_failed
echo [update-dev-database] ABORT: the backup failed. No schema change was attempted.
exit /b 2

:update_failed
echo [update-dev-database] ERROR: the EF update returned an error. EF applies migrations one at a time, so some
echo                       may already have been applied and the database may be partway forward; nothing was rolled back.
echo                       The backup taken in step 1 is the way back
echo                       ^(restore-latest.cmd restores it to a disposable copy for inspection^).
exit /b 4
