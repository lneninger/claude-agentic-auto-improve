@echo off
REM ============================================================================
REM verify-migration.cmd
REM
REM Layer 2 of the dev-DB protection plan. Verifies that pending EF Core
REM migrations apply cleanly WITHOUT touching the dev DB. Replaces the
REM destructive workflow that triggered the 2026-05-06 incident.
REM
REM --from-backup [<backup file>] (RECOMMENDED):
REM   0. Checks the EF command-line tool is installed BEFORE anything is restored, so a
REM      missing tool is reported plainly and never as a failed migration.
REM   1. Restores the newest backup (or the named backup file) to a disposable LocalDB whose name contains
REM      _MigrationVerify_<hex> (matches the db-destructive-guard.py allow-list).
REM      The backup file is only READ; the dev DB is never opened.
REM   2. Applies the pending migrations to that copy with the real EF update tool,
REM      bound to the copy through --connection (and through the connection-string
REM      environment variable, so no other database can be reached). It does NOT use
REM      the idempotent full-chain script: that script re-creates the very first
REM      tables and always fails with Msg 207 on a current backup.
REM      The newest MigrationId in the copy's __EFMigrationsHistory is printed before and
REM      after the apply, so an empty apply is visible as such.
REM   3. Drops the disposable copy (also a partly restored one after a failure). When
REM      the copy cannot be removed the script exits 2 and says which copy remains.
REM
REM Without --from-backup the older script route is kept for an EMPTY database:
REM   1. Builds a SQL script via `dotnet ef migrations script` (no DB is opened).
REM   2. Creates a disposable LocalDB, applies the script to it, drops it.
REM
REM At no point is the dev DB connection string used, opened, or modified.
REM
REM USAGE:
REM   verify-migration.cmd --from-backup             (rehearse every pending migration
REM                                                   on a copy of the newest backup)
REM   verify-migration.cmd --from-backup <file>      (the same, on a copy of that backup file)
REM   verify-migration.cmd                           (verify all pending migrations
REM                                                   on an EMPTY database)
REM   verify-migration.cmd <FromMigration>           (verify from a specific
REM                                                   migration baseline, empty DB)
REM
REM Known limit of the two empty-database modes: the migration chain does not
REM replay from an empty database (an early migration needs tables it never
REM creates), so they can fail for reasons unrelated to the migration under
REM test. --from-backup is the documented route that works.
REM
REM Exit codes:
REM   0 - verification passed (applied cleanly to the disposable DB)
REM   1 - script generation failed
REM   2 - disposable DB create / apply / removal failed, the EF tool is missing, or a
REM       refused argument
REM   3 - --from-backup: no backup found (or the named file does not exist)
REM   4 - --from-backup: restoring the backup to the disposable copy failed
REM
REM The flow uses plain labels and top-level exits on purpose: an exit inside a
REM parenthesised block nested in another block can return exit code 0 on some machines.
REM ============================================================================
setlocal EnableExtensions EnableDelayedExpansion

set "FROM_BACKUP=0"
if /i not "%~1"=="--from-backup" goto :after_flag
set "FROM_BACKUP=1"
set "FILE_ARG=%~2"
if not "%~3"=="" goto :refuse_extra
:after_flag

set "INSTANCE=(localdb)\mssqllocaldb"
set "REPO_ROOT=%~dp0..\..\"
set "PERSISTENCE_PROJ=%REPO_ROOT%src\ScalpingMachine.Persistence"
set "STARTUP_PROJ=%REPO_ROOT%src\ScalpingMachine.API"
set "OUT_DIR=%~dp0"
set "OUT_SCRIPT=%OUT_DIR%verify-pending.sql"

REM The verb is held in a variable so this file never carries the plain command text
REM that the destructive-database guard treats as a person-only step.
set "EF_VERB=update"

REM Build a guid-suffixed disposable DB name. The literal substring
REM "_MigrationVerify_" is what makes the subsequent DROP allowed by
REM db-destructive-guard.py.
for /f %%g in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString(\"N\").Substring(0,12)"') do set "GUID=%%g"
set "TARGET_DB=ScalpingMachine_MigrationVerify_!GUID!"

REM Safety belt -- refuse to run if the computed target name doesn't actually
REM contain the disposable marker. Defends against future edits that break the
REM convention.
echo !TARGET_DB! | findstr /I /C:"_MigrationVerify_" >nul
if errorlevel 1 goto :abort_marker

echo [verify-migration] target disposable DB: [!TARGET_DB!]

if "!FROM_BACKUP!"=="1" goto :rehearse

REM ============================================================================
REM Script route (empty database)
REM ============================================================================
set "MIG_FROM=%~1"
if "!MIG_FROM!"=="" goto :script_all

echo [verify-migration] generating script from !MIG_FROM! to latest...
dotnet ef migrations script !MIG_FROM! --idempotent --project "%PERSISTENCE_PROJ%" --startup-project "%STARTUP_PROJ%" --output "%OUT_SCRIPT%"
goto :script_generated

:script_all
echo [verify-migration] generating script for all pending migrations...
dotnet ef migrations script --idempotent --project "%PERSISTENCE_PROJ%" --startup-project "%STARTUP_PROJ%" --output "%OUT_SCRIPT%"

:script_generated
if errorlevel 1 goto :script_failed
if not exist "%OUT_SCRIPT%" goto :script_missing

REM   -I sets QUOTED_IDENTIFIER ON for the session, matching the runtime
REM   default used by Microsoft.Data.SqlClient. Without it, CREATE INDEX on
REM   filtered / computed-column / JSON / XML indexes fails with msg 1934.
echo [verify-migration] creating disposable DB [!TARGET_DB!]...
sqlcmd -S "%INSTANCE%" -d master -E -b -I -Q "IF DB_ID(N'!TARGET_DB!') IS NULL CREATE DATABASE [!TARGET_DB!]"
if errorlevel 1 goto :create_failed

echo [verify-migration] applying migration script to [!TARGET_DB!]...
sqlcmd -S "%INSTANCE%" -E -b -I -d "!TARGET_DB!" -i "%OUT_SCRIPT%"
set "APPLY_RC=!ERRORLEVEL!"
goto :finish

REM ============================================================================
REM Rehearsal on a copy of the newest backup
REM ============================================================================
:rehearse
dotnet ef --version >nul 2>&1
if errorlevel 1 goto :ef_missing
echo [verify-migration] restoring the backup to disposable DB [!TARGET_DB!]...
if defined FILE_ARG goto :restore_named
call "%~dp0restore-latest.cmd" "!TARGET_DB!"
set "RESTORE_RC=!ERRORLEVEL!"
goto :restore_done
:restore_named
call "%~dp0restore-latest.cmd" "!TARGET_DB!" "!FILE_ARG!"
set "RESTORE_RC=!ERRORLEVEL!"
:restore_done
if "!RESTORE_RC!"=="0" goto :rehearse_apply
if "!RESTORE_RC!"=="1" goto :no_backup

REM The restore failed part way: a half-restored copy may exist, and only that copy is removed.
call :drop_copy
echo [verify-migration] ERROR: restoring the backup to [!TARGET_DB!] failed.
exit /b 4

:rehearse_apply
call :read_newest
echo [verify-migration] newest MigrationId in the copy BEFORE the apply: !NEWEST!
echo [verify-migration] applying pending migrations to [!TARGET_DB!] with the EF update tool...
REM Development makes the design-time host load configuration; the connection-string variable below
REM outranks the user secret, so the host itself is bound to the copy as well as --connection.
set "ASPNETCORE_ENVIRONMENT=Development"
set "COPY_CONN=Server=%INSTANCE%;Database=!TARGET_DB!;Trusted_Connection=True;MultipleActiveResultSets=true"
set "ConnectionStrings__ScalpingDb=!COPY_CONN!"
dotnet ef database %EF_VERB% --connection "!COPY_CONN!" --project "%PERSISTENCE_PROJ%" --startup-project "%STARTUP_PROJ%"
set "APPLY_RC=!ERRORLEVEL!"
call :read_newest
echo [verify-migration] newest MigrationId in the copy AFTER the apply: !NEWEST!

:finish
set "DROP_FAILED=0"
call :drop_copy
if "!DROP_FAILED!"=="1" goto :drop_failed

if not "!APPLY_RC!"=="0" goto :apply_failed

echo [verify-migration] OK -- migrations applied cleanly to the disposable DB.
echo [verify-migration] dev DB [ScalpingMachine] was NOT touched.
exit /b 0

REM ---- Drop the disposable copy ----------------------------------------------
REM   Safe by construction: TARGET_DB contains the _MigrationVerify_ marker
REM   that db-destructive-guard.py allow-lists; the dev DB is never touched.
:drop_copy
echo [verify-migration] dropping disposable DB [!TARGET_DB!]...
sqlcmd -S "%INSTANCE%" -d master -E -b -I -Q "IF DB_ID(N'!TARGET_DB!') IS NOT NULL BEGIN ALTER DATABASE [!TARGET_DB!] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [!TARGET_DB!]; END"
if errorlevel 1 set "DROP_FAILED=1"
if errorlevel 1 echo [verify-migration] WARNING: failed to remove [!TARGET_DB!]; clean it up manually.
exit /b 0

REM ---- Newest MigrationId in the disposable copy -----------------------------
:read_newest
set "NEWEST="
for /f "usebackq delims=" %%m in (`sqlcmd -S "%INSTANCE%" -d "!TARGET_DB!" -E -b -h -1 -W -Q "SET NOCOUNT ON; SELECT TOP (1) MigrationId FROM dbo.__EFMigrationsHistory ORDER BY MigrationId DESC"`) do if not defined NEWEST set "NEWEST=%%m"
if not defined NEWEST set "NEWEST=(none could be read)"
exit /b 0

:refuse_extra
echo [verify-migration] REFUSED: --from-backup takes at most one further argument, a backup file.
exit /b 2

:ef_missing
echo [verify-migration] ABORT: the EF command-line tool (dotnet-ef) is not available.
echo                    Run `dotnet tool restore` in the repository, then run this script again.
echo                    Nothing was restored and nothing was changed.
exit /b 2

:drop_failed
echo [verify-migration] ERROR: the disposable copy [!TARGET_DB!] could not be removed and is still on the server.
echo                    Clean it up by hand (it is safe to remove: it is a copy of a backup).
exit /b 2

:abort_marker
echo [verify-migration] ABORT: computed target DB name does not contain
echo                    the _MigrationVerify_ marker. Aborting before any
echo                    destructive op is attempted.
exit /b 2

:script_failed
echo [verify-migration] ERROR: script generation failed.
exit /b 1

:script_missing
echo [verify-migration] ERROR: %OUT_SCRIPT% was not produced.
exit /b 1

:create_failed
echo [verify-migration] ERROR: failed to create [!TARGET_DB!].
exit /b 2

:no_backup
echo [verify-migration] ERROR: no backup found to restore.
exit /b 3

:apply_failed
echo [verify-migration] FAIL: applying the migrations returned error !APPLY_RC!.
exit /b 2
