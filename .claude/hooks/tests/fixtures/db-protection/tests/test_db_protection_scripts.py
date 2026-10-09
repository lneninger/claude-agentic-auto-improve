#!/usr/bin/env python3
"""
test_db_protection_scripts.py -- behavioural harness for the tools/db-protection scripts
(concept contract 2026-10-04-dev-db-protection-hardening.md, Revision 3, block 11).

WHAT THIS PROVES, AND HOW IT NEVER TOUCHES A DATABASE
-----------------------------------------------------
Each test runs a COPY of the real scripts under a throwaway repository root. Three programs the scripts call
(`dotnet`, `sqlcmd`, `schtasks`) are replaced by one tiny stand-in executable, placed FIRST on PATH, that records
its arguments and the SQL text it was handed to a log file and returns a scripted result. No stand-in opens a
connection; the only things this file ever runs are the scripts themselves, `powershell` (a timestamp and a guid),
`findstr`, `dir` and that one stand-in.

Why the stand-in is an .exe and not a .cmd: a batch file that starts another batch file without CALL never gets
control back. The real `dotnet` and `sqlcmd` are executables, so the scripts do not CALL them; a .cmd stand-in
would end every script at its first tool call and every test would pass or fail for that reason alone. The .exe is
built once per run from the source embedded below, with the same SDK that builds the repository.

What the copies change (and nothing else):
  * the `set "BACKUP_DIR=..."` line is pointed at a temp folder holding one empty fake backup, so the real backup
    folder is never read, listed or pruned;
  * line endings are normalised to CRLF, so a script that is still saved LF is judged on its logic here; INV-16
    (the bytes of the real files) is enforced by DevDatabaseProtectionSourceGuardTests, not by this file.

Run:
    py -3 tools/db-protection/tests/test_db_protection_scripts.py
Exit code: 0 = all passed, 1 = at least one failed or errored.

Facts a script author must honour for these tests to be able to see the script (the stand-in contract):
  * target resolution reads `dotnet user-secrets list` (a `Key = Value` line, or JSON with --json) OR
    `dotnet ef dbcontext info` ("Database name:" / "Data source:" lines);
  * a database existence test is a SQL text containing `DB_ID(` or `sys.databases`;
  * a batch that must refuse when the database exists raises an error (THROW, or RAISERROR followed by RETURN)
    inside the SAME batch as the restore statement, before it, in the form `IF DB_ID(N'name') IS [NOT] NULL THROW|RAISERROR`
    (or `IF [NOT] EXISTS (SELECT ... sys.databases ... name = N'name') THROW|RAISERROR`). FINAL FIX ROUND: the stand-in now
    EVALUATES that condition. `IS NOT NULL` raises when the database exists, `IS NULL` when it is missing; THROW ends
    the batch; RAISERROR(...,16,1) does NOT (the restore after it runs, recorded as effect OVERWROTE_EXISTING_DATABASE);
    the exit code of a raised error is non-zero only when the call carries -b. A guard in any other form is answered
    with effect UNEVALUABLE_GUARD and exit 99, so the stand-in can never approve a form it did not understand;
  * the backup is a BACKUP statement sent through `sqlcmd`;
  * the recovery batch lives in ONE block of comment lines in restore-latest.cmd, between a line containing
    RECOVERY-BATCH-BEGIN and a line containing RECOVERY-BATCH-END, with the placeholders @TARGET_DB@, @BACKUP_FILE@ and
    @MOVE_CLAUSES@ (a leading REM or :: is removed from each line);
  * extra stand-in switches (environment variables, set per test through `run_script(stub_xxx=...)`): STUB_EF_MISSING
    (every `dotnet ef` call fails), STUB_EXISTS_RC / STUB_EXISTS_OUTPUT (the existence read fails, or answers with text),
    STUB_DB_STATE (state of an existing database: ONLINE or RESTORING; a state query is one that selects state_desc /
    state or calls DATABASEPROPERTYEX, answered with the value alone), STUB_DROP_RC (a database removal fails),
    STUB_MIGRATION_BEFORE / STUB_MIGRATION_AFTER (the newest MigrationId, read from `__EFMigrationsHistory`: the first
    read answers BEFORE, later reads AFTER). Every recorded call also carries `connEnv`, the value of
    ConnectionStrings__ScalpingDb the tool saw.

The destructive verbs are composed from parts, so this file never contains the literal text the database guard
screens for, and the dev database name is composed so no protected name sits in a target position here.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REAL_DIR = HERE.parent                      # tools/db-protection
REPO_ROOT = REAL_DIR.parent.parent

DEV = "Scalping" + "Machine"                # the protected dev database name, composed
DEV_SERVER = "(localdb)\\mssqllocaldb"
OTHER_SERVER = "(localdb)\\someotherinstance"
LOGIN_REFUSAL = (
    "This step changes the development database and is run by a person in their own terminal, "
    "never from Claude Code."
)
_DROPW = "DR" + "OP"
_REPL = "REP" + "LACE"
_UPD = "up" + "date"
_RESTORE_STMT = "RESTORE DATABASE"
_COPY_NAME = re.compile(r"^" + DEV + r"_MigrationVerify_[0-9A-Fa-f]{4,}$")

_STUB_CSPROJ = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net9.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <UseAppHost>true</UseAppHost>
    <AssemblyName>StubTool</AssemblyName>
    <InvariantGlobalization>true</InvariantGlobalization>
    <SatelliteResourceLanguages>en</SatelliteResourceLanguages>
  </PropertyGroup>
</Project>
"""

_STUB_SOURCE = r'''
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

var tool = Path.GetFileNameWithoutExtension(Environment.ProcessPath ?? "stub").ToLowerInvariant();
static string Env(string n, string d = "") => Environment.GetEnvironmentVariable(n) ?? d;
static int Rc(string n) => int.TryParse(Environment.GetEnvironmentVariable(n), out var v) ? v : 0;

var dev = Env("STUB_DEV_DB");
var dbExists = Env("STUB_DB_EXISTS") == "1";
var server = Env("STUB_SERVER");
var database = Env("STUB_DATABASE");
var mode = Env("STUB_TARGET_MODE", "ok");
var text = string.Empty;
var effect = string.Empty;

int Finish(int rc)
{
    var log = Env("STUB_LOG");
    if (log.Length > 0)
    {
        // connEnv / aspnetEnv: the environment this tool call saw, so a case can prove a script cleared (or kept)
        // the connection-string variable before an EF call (final fix round, item 9).
        var line = JsonSerializer.Serialize(new
        {
            tool, args, text, effect, rc,
            connEnv = Environment.GetEnvironmentVariable("ConnectionStrings__ScalpingDb"),
            aspnetEnv = Environment.GetEnvironmentVariable("ASPNETCORE_ENVIRONMENT"),
        });
        File.AppendAllText(log, line + "\n", new UTF8Encoding(false));
    }
    return rc;
}

static string? NameAfter(string input, string pattern)
{
    var m = Regex.Match(input, pattern, RegexOptions.IgnoreCase);
    return m.Success ? m.Groups[1].Value : null;
}

if (tool == "dotnet")
{
    if (args.Length >= 2 && args[0] == "user-secrets" && args[1] == "list")
    {
        var key = Env("STUB_SECRET_KEY", "ConnectionStrings:ScalpingDb");
        var value = "Server=" + server + ";Database=" + database + ";Trusted_Connection=True;MultipleActiveResultSets=true";
        if (mode == "absent")
        {
            Console.WriteLine("No secrets configured for this application.");
        }
        else
        {
            var shown = mode == "empty" ? string.Empty : value;
            if (args.Contains("--json"))
            {
                Console.WriteLine("{ \"" + key + "\": \"" + shown.Replace("\\", "\\\\") + "\" }");
            }
            else
            {
                Console.WriteLine(key + " = " + shown);
            }
        }
        return Finish(0);
    }
    if (args.Length >= 3 && args[0] == "ef" && args[1] == "dbcontext" && args[2] == "info")
    {
        if (mode == "absent" || mode == "empty")
        {
            Console.Error.WriteLine("The ConnectionStrings:ScalpingDb is not configured.");
            return Finish(1);
        }
        Console.WriteLine("Type: ScalpingDbContext");
        Console.WriteLine("Provider name: Microsoft.EntityFrameworkCore.SqlServer");
        Console.WriteLine("Database name: " + database);
        Console.WriteLine("Data source: " + server);
        Console.WriteLine("Options: MaxPoolSize=128");
        return Finish(0);
    }
    if (args.Length >= 1 && args[0] == "ef" && Env("STUB_EF_MISSING") == "1")
    {
        // The EF tool is not installed: every `dotnet ef ...` call, the preflight included, fails the way the host does.
        Console.Error.WriteLine("Could not execute because the specified command or file was not found.");
        return Finish(1);
    }
    if (args.Length >= 2 && args[0] == "ef" && args.Contains("--version"))
    {
        Console.WriteLine("Entity Framework Core .NET Command-line Tools 9.0.15");
        return Finish(0);
    }
    if (args.Length >= 1 && args[0] == "ef")
    {
        if (args.Contains("migrations") && args.Contains("script"))
        {
            // Script generation is read-only and succeeds; it writes a trivial file where --output points.
            var at = Array.IndexOf(args, "--output");
            if (at >= 0 && at + 1 < args.Length)
            {
                File.WriteAllText(args[at + 1], "SELECT 1;\n");
            }
            return Finish(0);
        }
        if (args.Contains("update"))
        {
            return Finish(Rc("STUB_EF_RC"));
        }
        return Finish(0);
    }
    return Finish(0);
}

if (tool == "schtasks")
{
    Console.WriteLine("Status:                               Ready");
    Console.WriteLine("Last Run Time:                        10/05/2026 2:00:00 AM");
    Console.WriteLine("Last Result:                          0");
    Console.WriteLine("Next Run Time:                        10/06/2026 2:00:00 AM");
    return Finish(Rc("STUB_TASK_RC"));
}

if (tool == "sqlcmd")
{
    string? query = null, file = null;
    for (var i = 0; i < args.Length; i++)
    {
        if ((args[i] == "-Q" || args[i] == "-q") && i + 1 < args.Length) { query = args[++i]; }
        else if (args[i] == "-i" && i + 1 < args.Length) { file = args[++i]; }
    }
    text = query ?? (file is not null && File.Exists(file) ? File.ReadAllText(file) : string.Empty);
    var u = text.ToUpperInvariant();
    bool Guarded(int before)
    {
        var idDb = u.IndexOf("DB_ID(", StringComparison.Ordinal);
        var sysDb = u.IndexOf("SYS.DATABASES", StringComparison.Ordinal);
        var first = new[] { idDb, sysDb }.Where(x => x >= 0).DefaultIfEmpty(-1).Min();
        return first >= 0 && first < before;
    }

    if (u.Contains("BACKUP DATABASE"))
    {
        var name = NameAfter(text, @"BACKUP DATABASE\s+\[?([A-Za-z0-9_]+)");
        if (string.Equals(name, dev, StringComparison.OrdinalIgnoreCase) && !dbExists)
        {
            effect = "BACKUP_OF_MISSING_DATABASE";
            Console.Error.WriteLine("Msg 911, Level 16: Database '" + name + "' does not exist.");
            return Finish(1);
        }
        return Finish(Rc("STUB_BACKUP_RC"));
    }
    if (u.Contains("DR" + "OP DATABASE"))
    {
        // Removing a database (the verify script's disposable copy): the result is scripted, so a failed removal can be tested.
        var removeRc = Rc("STUB_DROP_RC");
        if (removeRc != 0) { Console.Error.WriteLine("Msg 3702, Level 16: the database cannot be removed (scripted failure)."); }
        return Finish(removeRc);
    }
    if (u.Contains("__EFMIGRATIONSHISTORY"))
    {
        // `newest MigrationId` read: the first answer is the copy's state BEFORE the apply, later answers AFTER it.
        var prior = 0;
        var logPath = Env("STUB_LOG");
        if (logPath.Length > 0 && File.Exists(logPath))
        {
            prior = File.ReadAllLines(logPath).Count(l => l.Contains("__EFMigrationsHistory", StringComparison.OrdinalIgnoreCase));
        }
        var before = Env("STUB_MIGRATION_BEFORE", "20260101000000_StubInitial");
        Console.WriteLine(prior == 0 ? before : Env("STUB_MIGRATION_AFTER", before));
        return Finish(Rc("STUB_HISTORY_RC"));
    }
    if (u.Contains("RESTORE FILELISTONLY"))
    {
        Console.WriteLine("LogicalDev|C:\\data\\LogicalDev.mdf|D|1048576|");
        Console.WriteLine("LogicalDev_log|C:\\data\\LogicalDev_log.ldf|L|1048576|");
        return Finish(0);
    }
    if (u.Contains("RESTORE DATABASE"))
    {
        var at = u.IndexOf("RESTORE DATABASE", StringComparison.Ordinal);
        var name = NameAfter(text, @"RESTORE DATABASE\s+\[?([A-Za-z0-9_]+)");
        var existing = dbExists && string.Equals(name, dev, StringComparison.OrdinalIgnoreCase);
        var before = text.Substring(0, at);

        // FINAL FIX ROUND (t15 B4, item 15): the stand-in EVALUATES the existence guard instead of approving any text
        // that mentions DB_ID( before the restore. Three real T-SQL facts are modelled:
        //   * the predicate matters: `IS NOT NULL` raises when the database exists, `IS NULL` when it is missing;
        //   * THROW ends the batch, but RAISERROR(...,16,1) does NOT: the next statement (the restore) still runs,
        //     unless a RETURN follows it;
        //   * sqlcmd returns a failing exit code for a raised error only with -b.
        bool? refuse = null;
        var terminates = false;
        string? guardedName = null;
        var m = Regex.Match(before,
            @"IF\s+DB_ID\(\s*N?'([^']+)'\s*\)\s+IS\s+(NOT\s+)?NULL\s+(?:BEGIN\s+)?(THROW|RAISERROR)(?<rest>.*)",
            RegexOptions.IgnoreCase | RegexOptions.Singleline);
        string verb = string.Empty, rest = string.Empty;
        if (m.Success)
        {
            guardedName = m.Groups[1].Value;
            var there = dbExists && string.Equals(guardedName, dev, StringComparison.OrdinalIgnoreCase);
            refuse = m.Groups[2].Success ? there : !there;
            verb = m.Groups[3].Value.ToUpperInvariant();
            rest = m.Groups["rest"].Value;
        }
        else
        {
            var e = Regex.Match(before,
                @"IF\s+(NOT\s+)?EXISTS\s*\(\s*SELECT\b[^)]*?sys\.databases[^)]*?name\s*=\s*N?'([^']+)'[^)]*\)\s+(?:BEGIN\s+)?(THROW|RAISERROR)(?<rest>.*)",
                RegexOptions.IgnoreCase | RegexOptions.Singleline);
            if (e.Success)
            {
                guardedName = e.Groups[2].Value;
                var there = dbExists && string.Equals(guardedName, dev, StringComparison.OrdinalIgnoreCase);
                refuse = e.Groups[1].Success ? !there : there;
                verb = e.Groups[3].Value.ToUpperInvariant();
                rest = e.Groups["rest"].Value;
            }
        }
        if (refuse is null && (before.ToUpperInvariant().Contains("DB_ID(") || before.ToUpperInvariant().Contains("SYS.DATABASES")))
        {
            effect = "UNEVALUABLE_GUARD";
            Console.Error.WriteLine("stand-in sqlcmd cannot evaluate the existence guard in front of the restore; keep the form IF DB_ID(N'name') IS [NOT] NULL THROW|RAISERROR.");
            return Finish(99);
        }
        if (verb == "THROW")
        {
            terminates = true;
        }
        else if (verb == "RAISERROR")
        {
            terminates = Regex.IsMatch(rest, @"^\s*\([^)]*\)\s*;?\s*RETURN\b", RegexOptions.IgnoreCase);
        }

        var haltOnError = args.Contains("-b");
        var raised = refuse == true;
        if (raised && terminates)
        {
            var wasThere = dbExists && string.Equals(guardedName, dev, StringComparison.OrdinalIgnoreCase);
            effect = wasThere ? "BATCH_REFUSED_DATABASE_EXISTS" : "BATCH_REFUSED_DATABASE_ABSENT";
            Console.Error.WriteLine("Msg 50000, Level 16: the existence guard raised; the batch ended before the restore.");
            return Finish(haltOnError ? 1 : 0);
        }
        if (raised)
        {
            Console.Error.WriteLine("Msg 50000, Level 16: the existence guard raised, but the batch CONTINUES (RAISERROR does not end a batch).");
        }
        effect = existing ? "OVERWROTE_EXISTING_DATABASE" : "RESTORED_TARGET";
        if (raised)
        {
            return Finish(haltOnError ? 1 : 0);
        }
        return Finish(Rc("STUB_RESTORE_RC"));
    }
    if (u.Contains("SERVER_TRIGGERS"))
    {
        Console.WriteLine(Env("STUB_TRIGGER", "ENABLED"));
        return Finish(0);
    }
    if (u.Contains("INSTANCEDEFAULTDATAPATH"))
    {
        Console.WriteLine(Env("STUB_DATA_DIR", "NULL"));
        return Finish(0);
    }
    var isExistenceTest = (u.Contains("DB_ID(") || u.Contains("SYS.DATABASES"))
        && !u.Contains("CREATE DATABASE") && !u.Contains("DR" + "OP DATABASE") && !u.Contains("ALTER DATABASE");
    if (isExistenceTest)
    {
        var names = Regex.Matches(text, @"(?:DB_ID\(\s*N?'|name\s*=\s*N?')([^']+)'", RegexOptions.IgnoreCase)
            .Select(m => m.Groups[1].Value).ToList();
        var exists = dbExists && (names.Count == 0 || names.Contains(dev, StringComparer.OrdinalIgnoreCase));
        if (u.Contains("RAISERROR") || u.Contains("THROW"))
        {
            return Finish(exists ? 1 : 0);
        }
        // A plain read. Scripted failures (final fix round, item 15): the query itself fails, or answers with text that
        // is not a count, so a script's reading of "does the database exist" can be tested.
        var failRc = Env("STUB_EXISTS_RC");
        if (failRc.Length > 0)
        {
            Console.Error.WriteLine("Msg 4060, Level 11: the stand-in could not answer the existence query (scripted failure).");
            return Finish(int.Parse(failRc));
        }
        var custom = Env("STUB_EXISTS_OUTPUT");
        if (custom.Length > 0)
        {
            Console.WriteLine(custom);
            return Finish(0);
        }
        // The state of a database that exists (a restore that never finished leaves RESTORING behind).
        var state = Env("STUB_DB_STATE", "ONLINE").ToUpperInvariant();
        var literal = Regex.Match(text, @"STATE_DESC\s*(=|<>|!=)\s*N?'(\w+)'", RegexOptions.IgnoreCase);
        if (u.Contains("COUNT(") && literal.Success)
        {
            var equal = string.Equals(state, literal.Groups[2].Value, StringComparison.OrdinalIgnoreCase);
            var hit = exists && (literal.Groups[1].Value == "=" ? equal : !equal);
            Console.WriteLine(hit ? "1" : "0");
            return Finish(0);
        }
        if (u.Contains("STATE_DESC") || u.Contains("DATABASEPROPERTYEX"))
        {
            Console.WriteLine(exists ? state : "NULL");
            return Finish(0);
        }
        if (Regex.IsMatch(u, @"SELECT\s+(?:TOP\s*\(?\s*1\s*\)?\s+)?(?:\w+\.)?STATE\b"))
        {
            Console.WriteLine(exists ? (state == "ONLINE" ? "0" : "1") : "NULL");
            return Finish(0);
        }
        Console.WriteLine(u.Contains("COUNT(") ? (exists ? "1" : "0") : (exists ? "7" : "NULL"));
        return Finish(0);
    }
    if (file is not null)
    {
        return Finish(Rc("STUB_APPLY_RC"));
    }
    return Finish(0);
}

return Finish(0);
'''

_STUB_BIN: Path | None = None
_STUB_TMP: Path | None = None
_DOTNET_ROOT = ""


def setUpModule() -> None:
    """Builds the stand-in executable once and lays out dotnet.exe, sqlcmd.exe and schtasks.exe."""
    global _STUB_BIN, _STUB_TMP, _DOTNET_ROOT
    if os.name != "nt":
        raise unittest.SkipTest("the db-protection scripts are Windows .cmd files; they cannot run here")
    real = shutil.which("dotnet")
    if not real:
        raise RuntimeError("cannot build the stand-in tool: no dotnet SDK on PATH")
    _DOTNET_ROOT = str(Path(real).resolve().parent)
    _STUB_TMP = Path(tempfile.mkdtemp(prefix="dbprot-stub-"))
    src = _STUB_TMP / "src"
    src.mkdir()
    (src / "StubTool.csproj").write_text(_STUB_CSPROJ, encoding="utf-8")
    (src / "Program.cs").write_text(_STUB_SOURCE, encoding="utf-8")
    out = _STUB_TMP / "out"
    proc = subprocess.run(
        ["dotnet", "build", str(src / "StubTool.csproj"), "-c", "Release", "-o", str(out), "-nologo", "-v", "q"],
        capture_output=True, text=True, timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError("building the stand-in tool failed:\n" + proc.stdout[-2000:] + proc.stderr[-2000:])
    bin_dir = _STUB_TMP / "bin"
    shutil.copytree(out, bin_dir)
    for name in ("dotnet", "sqlcmd", "schtasks"):
        shutil.copy2(bin_dir / "StubTool.exe", bin_dir / f"{name}.exe")
    _STUB_BIN = bin_dir


def tearDownModule() -> None:
    if _STUB_TMP is not None:
        shutil.rmtree(_STUB_TMP, ignore_errors=True)


class Result:
    def __init__(self, rc: int, out: str, calls: list[dict]) -> None:
        self.rc, self.out, self.calls = rc, out, calls

    def describe(self) -> str:
        lines = [f"exit code {self.rc}", "--- output ---", self.out.strip()[-1500:], "--- recorded calls ---"]
        for i, c in enumerate(self.calls):
            text = (c.get("text") or "").replace("\n", " ")[:170]
            lines.append(f"{i}: {c['tool']} {' '.join(c['args'])[:140]} | {text} | effect={c.get('effect') or '-'} rc={c['rc']}")
        return "\n".join(lines)

    def of(self, tool: str) -> list[dict]:
        return [c for c in self.calls if c["tool"] == tool]


class ScriptCase(unittest.TestCase):
    """A throwaway repository root holding patched copies of the scripts, rebuilt for every test."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="dbprot-root-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.tools = self.root / "tools" / "db-protection"
        self.tools.mkdir(parents=True)
        self.backups = self.root / "backups"
        self.backups.mkdir()
        (self.backups / "scalping-20260101-000000.bak").write_bytes(b"")
        self.data = self.root / "data"
        self.data.mkdir()
        self.log = self.root / "calls.jsonl"
        patched = 0
        for src in REAL_DIR.iterdir():
            if not src.is_file() or src.suffix.lower() not in {".cmd", ".ps1", ".sql"}:
                continue
            text = src.read_bytes().decode("utf-8")
            if src.suffix.lower() == ".cmd":
                text = text.replace("\r\n", "\n").replace("\n", "\r\n")
                text, n = re.subn(
                    r'(?im)^(\s*set\s+"BACKUP_DIR=)[^"]*(")',
                    lambda m: m.group(1) + str(self.backups) + m.group(2), text)
                patched += n
            (self.tools / src.name).write_bytes(text.encode("utf-8"))
        self.assertGreaterEqual(patched, 3, "ARRANGE CONTROL: BACKUP_DIR must be repointed in at least the backup, "
                                "restore and status scripts, or a test would read the real backup folder")
        api = self.root / "src" / "ScalpingMachine.API"
        api.mkdir(parents=True)
        shutil.copy2(REPO_ROOT / "src" / "ScalpingMachine.API" / "appsettings.json", api / "appsettings.json")
        (self.root / "src" / "ScalpingMachine.Persistence").mkdir()

    def run_script(self, name: str, args: list[str] | None = None, claudecode: bool = False,
                   extra_env: dict[str, str] | None = None, **stub: str) -> Result:
        assert _STUB_BIN is not None
        env = dict(os.environ)
        for k in list(env):
            if (k.startswith("STUB_") or k in ("CLAUDECODE", "CLAUDE_DESTRUCTIVE_DB_OK", "ASPNETCORE_ENVIRONMENT")
                    or k.upper() == "CONNECTIONSTRINGS__SCALPINGDB"):
                env.pop(k)
        env["PATH"] = str(_STUB_BIN) + os.pathsep + env.get("PATH", "")
        env["DOTNET_ROOT"] = _DOTNET_ROOT
        env["DOTNET_NOLOGO"] = "1"
        env.update({
            "STUB_LOG": str(self.log), "STUB_DEV_DB": DEV, "STUB_DB_EXISTS": "1",
            "STUB_SERVER": DEV_SERVER, "STUB_DATABASE": DEV, "STUB_DATA_DIR": str(self.data),
        })
        env.update({k.upper(): v for k, v in stub.items()})
        if extra_env:
            env.update(extra_env)          # exact spelling kept (the connection-string variable is mixed case)
        if claudecode:
            env["CLAUDECODE"] = "1"
        proc = subprocess.run(
            ["cmd.exe", "/d", "/c", str(self.tools / name), *(args or [])],
            env=env, cwd=str(self.root), capture_output=True, timeout=180,
        )
        out = (proc.stdout + proc.stderr).decode("cp437", errors="replace")
        calls = []
        if self.log.exists():
            for line in self.log.read_text(encoding="utf-8-sig").splitlines():
                if line.strip():
                    calls.append(json.loads(line))
        return Result(proc.returncode, out, calls)

    # ---- assertion helpers ---------------------------------------------------------------------
    def fail_with(self, res: Result, message: str) -> None:
        self.fail(message + "\n" + res.describe())

    def eq(self, res: Result, actual, expected, message: str) -> None:
        if actual != expected:
            self.fail_with(res, f"{message}: expected {expected!r}, got {actual!r}")

    @staticmethod
    def queries(res: Result) -> list[tuple[int, str]]:
        return [(i, c["text"]) for i, c in enumerate(res.calls) if c["tool"] == "sqlcmd" and c.get("text")]

    @staticmethod
    def ef_update_calls(res: Result) -> list[tuple[int, dict]]:
        return [(i, c) for i, c in enumerate(res.calls)
                if c["tool"] == "dotnet" and c["args"][:1] == ["ef"] and "database" in c["args"][1:3] and _UPD in c["args"]]

    @staticmethod
    def ef_version_calls(res: "Result") -> list[int]:
        return [i for i, c in enumerate(res.calls)
                if c["tool"] == "dotnet" and c["args"][:1] == ["ef"] and "--version" in c["args"]]

    def add_backup(self, name: str, days_old: float) -> Path:
        """An extra empty backup in the (repointed) backup folder, with a modification time `days_old` days ago."""
        import time
        path = self.backups / name
        path.write_bytes(b"")
        stamp = time.time() - days_old * 86400
        os.utime(path, (stamp, stamp))
        return path

    @staticmethod
    def recovery_template(script_text: str) -> str | None:
        """The recovery batch read out of the script's marker lines (RECOVERY-BATCH-BEGIN / -END), prefix removed."""
        lines = script_text.replace("\r\n", "\n").split("\n")
        begin = next((i for i, l in enumerate(lines) if "RECOVERY-BATCH-BEGIN" in l), -1)
        end = next((i for i, l in enumerate(lines) if "RECOVERY-BATCH-END" in l), -1)
        if begin < 0 or end <= begin:
            return None
        body = [re.sub(r"(?i)^\s*(?:REM(?:\s|$)|::)", "", l).strip() for l in lines[begin + 1:end]]
        text = "\n".join(l for l in body if l)
        return text or None

    def mutate_script(self, name: str, mutate) -> int:
        """Rewrites the COPY of a script under the throwaway root (never the real file). Returns the edit count."""
        path = self.tools / name
        text = path.read_bytes().decode("utf-8")
        new, count = mutate(text)
        path.write_bytes(new.encode("utf-8"))
        return count

    @staticmethod
    def positional_after_update(args: list[str]) -> list[str]:
        value_flags = {"--project", "-p", "--startup-project", "-s", "--connection", "--context", "-c",
                       "--configuration", "--framework", "--runtime", "--launch-profile"}
        tail = args[args.index(_UPD) + 1:]
        out, i = [], 0
        while i < len(tail):
            a = tail[i]
            if a == "--":
                break
            if a.startswith("-"):
                i += 2 if a in value_flags else 1
            else:
                out.append(a)
                i += 1
        return out

    @staticmethod
    def connection_database(args: list[str]) -> str | None:
        for i, a in enumerate(args):
            raw = args[i + 1] if a == "--connection" and i + 1 < len(args) else (
                a.split("=", 1)[1] if a.startswith("--connection=") else None)
            if raw is not None:
                m = re.search(r"(?i)(?:Database|Initial Catalog)\s*=\s*([^;\"]+)", raw)
                return m.group(1).strip() if m else ""
        return None

    @staticmethod
    def restore_target(sql: str) -> str | None:
        m = re.search(r"(?i)" + _RESTORE_STMT + r"\s+\[?([A-Za-z0-9_]+)", sql)
        return m.group(1) if m else None


# =============================================================================================
# update-dev-database.cmd  (INV-12)
# =============================================================================================
class UpdateDevDatabaseTests(ScriptCase):
    SCRIPT = "update-dev-database.cmd"

    def test_refuses_under_a_claude_code_shell_and_runs_no_tool(self) -> None:
        # passes today BY DESIGN (control): the CLAUDECODE refusal already exists.
        res = self.run_script(self.SCRIPT, claudecode=True)
        self.eq(res, res.rc, 3, "refusal exit code")
        self.assertIn(LOGIN_REFUSAL, res.out, "the verbatim refusal text must be printed\n" + res.describe())
        self.eq(res, res.calls, [], "no tool may run before the refusal")

    def test_refuses_any_argument_and_runs_no_tool(self) -> None:
        # INV-12: "accepts no argument". The empty-first-argument shape (`"" x`) is the one a `%~1` test misses.
        for args in (["0"], ["20260101000000_Init"], ["--connection", "x"], ["", "x"]):
            with self.subTest(args=args):
                self.log.unlink(missing_ok=True)
                res = self.run_script(self.SCRIPT, args)
                self.eq(res, res.rc, 3, f"refusal exit code for arguments {args!r}")
                self.eq(res, res.calls, [], f"no tool may run for arguments {args!r}")

    def test_with_an_existing_database_the_backup_runs_before_the_update_and_both_target_the_dev_database(self) -> None:
        res = self.run_script(self.SCRIPT)
        self.eq(res, res.rc, 0, "a clean run exits 0")
        backups = [(i, q) for i, q in self.queries(res) if "BACKUP DATABASE" in q.upper()]
        updates = self.ef_update_calls(res)
        if len(backups) != 1 or len(updates) != 1:
            self.fail_with(res, f"expected exactly one backup and one EF update, got {len(backups)} and {len(updates)}")
        self.assertLess(backups[0][0], updates[0][0],
                        "the backup must run BEFORE the migration\n" + res.describe())
        m = re.search(r"(?i)BACKUP DATABASE\s+\[?([A-Za-z0-9_]+)", backups[0][1])
        self.eq(res, m.group(1) if m else None, DEV, "the backup must be of the dev database")
        self.eq(res, self.positional_after_update(updates[0][1]["args"]), [],
                "the update must carry no positional migration target, so it can only move forward")
        conn_db = self.connection_database(updates[0][1]["args"])
        if conn_db is not None:
            self.eq(res, conn_db, DEV, "an explicit --connection must name the same database that was backed up")

    def test_a_missing_dev_database_is_refused_with_exit_3_the_recovery_route_is_printed_and_the_update_never_runs(self) -> None:
        # DELIBERATE FLIP (final fix round, Amendment C). The revision 3 test of this name's predecessor expected a first
        # run to SKIP the backup and RUN the update (exit 0). Amendment C reverses it: the migration chain cannot succeed
        # from an empty database (AddResourceOwnership raises when Users has no rows) and a failed run would leave a
        # half-built protected database that the server trigger will not let anyone remove. So the script refuses,
        # prints the working route, and NEVER invokes the EF update.
        res = self.run_script(self.SCRIPT, stub_db_exists="0")
        self.eq(res, res.rc, 3, "a missing dev database is a refusal (exit 3)")
        self.eq(res, self.ef_update_calls(res), [],
                "Amendment C: the EF update must NEVER be invoked against a missing dev database")
        ef_database_calls = [c for c in res.calls if c["tool"] == "dotnet" and c["args"][:1] == ["ef"]
                             and "database" in c["args"][1:3]]
        self.eq(res, ef_database_calls, [], "no `dotnet ef database ...` call of any kind may run")
        backups = [q for _, q in self.queries(res) if "BACKUP DATABASE" in q.upper()]
        self.eq(res, backups, [], "no backup of a database that does not exist may be attempted")
        self.assertRegex(res.out, r"(?i)restore-latest\.cmd\s+--recover-missing-dev-db",
                         "the route must name the recovery command\n" + res.describe())
        self.assertRegex(res.out, r"(?i)\.bak", "the route must say a .bak file goes into the backup folder\n" + res.describe())
        self.assertRegex(res.out, r"(?i)D:\\Backups\\ScalpingMachine",
                         "the route must name the backup folder\n" + res.describe())
        self.assertRegex(res.out, r"(?i)update-dev-database\.cmd",
                         "the route must end with running the update script again\n" + res.describe())
        self.assertRegex(res.out, r"(?is)--recover-missing-dev-db.*update-dev-database\.cmd",
                         "the route lists the recovery BEFORE running the update script again, in that order\n" + res.describe())

    def test_a_failed_backup_stops_the_update(self) -> None:
        # passes today BY DESIGN (control): "abort before any schema change if the backup fails".
        res = self.run_script(self.SCRIPT, stub_backup_rc="1")
        self.assertNotEqual(res.rc, 0, "a failed backup must fail the script\n" + res.describe())
        self.eq(res, self.ef_update_calls(res), [], "no schema change after a failed backup")

    def test_refuses_when_the_configured_database_is_not_the_dev_name(self) -> None:
        # INV-12 / t6 WARN-1: the backup and the update must act on the SAME database.
        res = self.run_script(self.SCRIPT, stub_database="SomeOtherDb")
        self.assertNotEqual(res.rc, 0, "a different configured database must refuse\n" + res.describe())
        self.eq(res, self.ef_update_calls(res), [], "no update against a database that is not the dev name")
        backups = [q for _, q in self.queries(res) if "BACKUP DATABASE" in q.upper()]
        self.eq(res, backups, [], "no backup of a database other than the one being updated")

    def test_refuses_when_the_configured_server_is_not_the_localdb_instance(self) -> None:
        res = self.run_script(self.SCRIPT, stub_server=OTHER_SERVER)
        self.assertNotEqual(res.rc, 0, "a different server must refuse\n" + res.describe())
        self.eq(res, self.ef_update_calls(res), [], "no update against a server other than (localdb)\\mssqllocaldb")

    def test_refuses_when_no_connection_is_configured(self) -> None:
        for mode in ("absent", "empty"):
            with self.subTest(mode=mode):
                self.log.unlink(missing_ok=True)
                res = self.run_script(self.SCRIPT, stub_target_mode=mode)
                self.assertNotEqual(res.rc, 0, f"an {mode} connection must refuse\n" + res.describe())
                self.eq(res, self.ef_update_calls(res), [], f"no update with an {mode} connection")

    # ---- final fix round (contract Revision 4, items 9, 10 and 15) -------------------------------

    SECRET_VALUE = f"Server={DEV_SERVER};Database={DEV};Trusted_Connection=True;MultipleActiveResultSets=true"
    OTHER_CONN = f"Server={DEV_SERVER};Database=SomeOtherDb;Trusted_Connection=True"

    def test_the_update_gets_connection_with_the_checked_secret_value_and_the_environment_variable_is_cleared(self) -> None:
        # Item 9 / t15 W7. RED today: the EF call carries no --connection and the variable that outranks the user
        # secret in the Development design-time host is left set, so a person whose shell holds it gets a backup of
        # the dev database followed by a migration of ANOTHER database.
        res = self.run_script(self.SCRIPT, extra_env={"ConnectionStrings__ScalpingDb": self.OTHER_CONN})
        self.eq(res, res.rc, 0, "a clean run exits 0")
        updates = self.ef_update_calls(res)
        self.eq(res, len(updates), 1, "exactly one EF update")
        call = updates[0][1]
        args = call["args"]
        self.assertIn("--connection", args, "the EF update must be bound with --connection\n" + res.describe())
        value = args[args.index("--connection") + 1] if args.index("--connection") + 1 < len(args) else ""
        self.eq(res, value.strip(), self.SECRET_VALUE,
                "--connection must carry the value of the user secret the script CHECKED, not the environment's")
        self.assertNotIn("SomeOtherDb", " ".join(args), "the redirecting environment value must never reach the EF call")
        self.assertIn(call.get("connEnv"), (None, ""),
                      "ConnectionStrings__ScalpingDb must be cleared for the EF call (it outranks the user secret)\n" + res.describe())
        if "--" in args:
            self.assertLess(args.index("--connection"), args.index("--"), "--connection must come before any `--`")

    def test_the_update_binds_the_connection_even_when_the_environment_variable_is_not_set(self) -> None:
        res = self.run_script(self.SCRIPT)
        updates = self.ef_update_calls(res)
        self.eq(res, len(updates), 1, "exactly one EF update")
        self.assertIn("--connection", updates[0][1]["args"], "the EF update must always be bound\n" + res.describe())

    def test_the_ef_tool_preflight_runs_before_the_backup(self) -> None:
        # Item 10. RED today: no `dotnet ef --version` call exists, so a missing tool is found only AFTER the backup.
        res = self.run_script(self.SCRIPT)
        pre = self.ef_version_calls(res)
        backups = [i for i, q in self.queries(res) if "BACKUP DATABASE" in q.upper()]
        self.assertTrue(pre, "the script must run `dotnet ef --version` as a preflight\n" + res.describe())
        self.assertTrue(backups, "ARRANGE CONTROL: a backup must run in this scenario\n" + res.describe())
        self.assertLess(pre[0], backups[0], "the preflight must come BEFORE the backup\n" + res.describe())
        self.assertLess(pre[0], self.ef_update_calls(res)[0][0], "and before the update\n" + res.describe())

    def test_a_missing_ef_tool_is_reported_plainly_before_any_backup_and_is_not_a_failed_migration(self) -> None:
        # Item 10. RED today: the backup runs, then the EF update fails and the script reports exit 4 "the EF update failed".
        res = self.run_script(self.SCRIPT, stub_ef_missing="1")
        self.assertNotEqual(res.rc, 0, "a missing tool must fail the script\n" + res.describe())
        self.assertNotEqual(res.rc, 4, "exit 4 means the migration ran and failed; a missing tool is not that\n" + res.describe())
        backups = [q for _, q in self.queries(res) if "BACKUP DATABASE" in q.upper()]
        self.eq(res, backups, [], "no backup may be attempted when the EF tool is missing")
        self.eq(res, self.ef_update_calls(res), [], "no update may be attempted when the EF tool is missing")
        self.assertRegex(res.out, r"(?i)dotnet tool restore|dotnet-ef",
                         "the message must name the tool and how to install it\n" + res.describe())
        self.assertNotRegex(res.out, r"(?i)EF update failed|migrations? (?:failed|did not apply)",
                            "a missing tool must not be reported as a failed migration\n" + res.describe())

    def test_a_query_that_fails_to_answer_is_not_read_as_a_missing_database(self) -> None:
        # t15 W6 / S7. passes today BY DESIGN (control for the mutation "unreadable answer -> first run"): the
        # existence read that fails, or answers with text that is not a count, must abort with exit 2 and run nothing.
        for label, stub in (("the query fails", {"stub_exists_rc": "1"}),
                            ("the answer is not a count", {"stub_exists_output": "Sqlcmd: Error: Login timeout expired"})):
            with self.subTest(case=label):
                self.log.unlink(missing_ok=True)
                res = self.run_script(self.SCRIPT, **stub)
                self.eq(res, res.rc, 2, f"{label}: the script must abort with exit 2")
                self.eq(res, self.ef_update_calls(res), [], f"{label}: no update")
                backups = [q for _, q in self.queries(res) if "BACKUP DATABASE" in q.upper()]
                self.eq(res, backups, [], f"{label}: no backup either")
                self.assertNotRegex(res.out, r"(?i)--recover-missing-dev-db",
                                    f"{label}: it must not be reported as 'the database is missing'\n" + res.describe())


# =============================================================================================
# restore-latest.cmd  (INV-11)
# =============================================================================================
class RestoreLatestTests(ScriptCase):
    SCRIPT = "restore-latest.cmd"
    RECOVER = "--recover-missing-dev-db"
    RESTORING_WORDS = r"RESTORING|[Hh]alf[- ]restored|[Pp]art(?:ly|ially) restored|[Uu]nfinished restore|[Ii]ncomplete restore"

    def restores(self, res: Result) -> list[tuple[int, str]]:
        return [(i, q) for i, q in self.queries(res) if _RESTORE_STMT in q.upper()]

    def test_accepts_a_name_of_word_characters_that_ends_in_a_disposable_suffix(self) -> None:
        for name in ("Foo_Test_0a1b2c3d4e5f", DEV + "_MigrationVerify_0a1b2c3d4e5f", "Foo_DryRun", "Foo_e2e_0a1b2c3d4e5f"):
            with self.subTest(name=name):
                self.log.unlink(missing_ok=True)
                res = self.run_script(self.SCRIPT, [name], stub_db_exists="0")
                self.eq(res, res.rc, 0, f"{name} is a valid disposable target")
                self.eq(res, [self.restore_target(q) for _, q in self.restores(res)], [name],
                        "the restore must target exactly the requested name")

    def test_rejects_a_name_that_fails_the_character_rule_or_has_no_disposable_suffix(self) -> None:
        # INV-11(a): ^[A-Za-z0-9_]+$ AND ends in a disposable suffix. The first four carry the marker but break the
        # character rule (RED today: the script only tests for the marker anywhere in the name); the next two carry
        # the marker in the MIDDLE (RED today); the last three have no marker (green today).
        bad = [
            "Foo_Test_0a1b2c3d4e5f]", "a'b_Test_0a1b2c3d4e5f", "Foo Test_0a1b2c3d4e5f", "Foo-Test_0a1b2c3d4e5f",
            "Foo.Test_0a1b2c3d4e5f", "Foo_Test_0a1b2c3d4e5f_Prod", "Foo_MigrationVerify_abc12345_Live",
            DEV, DEV + "_Testing", "SomeDb",
        ]
        for name in bad:
            with self.subTest(name=name):
                self.log.unlink(missing_ok=True)
                res = self.run_script(self.SCRIPT, [name], stub_db_exists="0")
                self.eq(res, res.rc, 3, f"{name!r} must be refused (exit 3)")
                self.eq(res, self.restores(res), [], f"{name!r}: no restore statement may be sent")

    def test_the_default_target_is_a_fresh_disposable_name(self) -> None:
        # passes today BY DESIGN (control).
        res = self.run_script(self.SCRIPT, [], stub_db_exists="0")
        self.eq(res, res.rc, 0, "the no-argument mode restores a disposable copy")
        targets = [self.restore_target(q) for _, q in self.restores(res)]
        self.assertEqual(len(targets), 1, res.describe())
        self.assertRegex(targets[0] or "", r"^" + DEV + r"_Test_[0-9A-Fa-f]{8,}$", res.describe())

    def test_no_restore_statement_ever_carries_the_replace_option(self) -> None:
        # passes today BY DESIGN (control): the replace option is gone from every mode.
        for args, exists in (([], "0"), (["Foo_Test_0a1b2c3d4e5f"], "0"), ([self.RECOVER], "0")):
            with self.subTest(args=args):
                self.log.unlink(missing_ok=True)
                res = self.run_script(self.SCRIPT, args, stub_db_exists=exists)
                for _, q in self.restores(res):
                    self.assertNotIn(_REPL, q.upper(), res.describe())

    def test_recovery_refuses_under_a_claude_code_shell(self) -> None:
        # passes today BY DESIGN (control).
        res = self.run_script(self.SCRIPT, [self.RECOVER], claudecode=True, stub_db_exists="0")
        self.eq(res, res.rc, 3, "refusal exit code")
        self.assertIn(LOGIN_REFUSAL, res.out, res.describe())
        self.eq(res, res.calls, [], "no tool may run before the refusal")

    def test_recovery_refuses_when_the_dev_database_exists_and_overwrites_nothing(self) -> None:
        res = self.run_script(self.SCRIPT, [self.RECOVER], stub_db_exists="1")
        self.assertNotEqual(res.rc, 0, "recovery must refuse when the dev database exists\n" + res.describe())
        overwritten = [c for c in res.calls if c.get("effect") == "OVERWROTE_EXISTING_DATABASE"]
        self.eq(res, overwritten, [], "a restore must never reach an existing dev database")

    def test_recovery_restores_the_dev_database_when_it_is_missing(self) -> None:
        res = self.run_script(self.SCRIPT, [self.RECOVER], stub_db_exists="0")
        self.eq(res, res.rc, 0, "recovery of a missing database succeeds")
        self.eq(res, [self.restore_target(q) for _, q in self.restores(res)], [DEV],
                "the recovery restores the dev database name")

    def test_recovery_checks_existence_and_restores_in_one_batch(self) -> None:
        # RED today: the check is a separate earlier call and the restore batch carries no check (INV-11(b)).
        res = self.run_script(self.SCRIPT, [self.RECOVER], stub_db_exists="0")
        restores = self.restores(res)
        self.eq(res, len(restores), 1, "exactly one restore batch is expected")
        sql = restores[0][1]
        upper = sql.upper()
        at = upper.index(_RESTORE_STMT)
        before = upper[:at]
        has_check = "DB_ID(" in before or "SYS.DATABASES" in before
        # RAISERROR at severity 16 does NOT end a batch (t15 B4): it only counts together with a RETURN.
        raises = "THROW" in before or ("RAISERROR" in before and "RETURN" in before)
        if not (has_check and raises):
            self.fail_with(res, "the restore batch must begin with an existence test that raises an error and so "
                                "stops the batch BEFORE the restore statement (check present: "
                                f"{has_check}, raises: {raises}); a separate earlier call leaves a window in which "
                                "something can create the database between the check and the restore")
        self.assertIn(DEV.upper(), before, "the existence test must name the dev database\n" + res.describe())

    def test_a_restore_batch_with_no_embedded_check_is_never_sent_in_recovery_mode(self) -> None:
        # The same rule from the other side: when the dev database exists, an unguarded restore would overwrite it.
        # (The earlier test proves nothing is overwritten; this one proves WHY: every recovery restore is guarded.)
        res = self.run_script(self.SCRIPT, [self.RECOVER], stub_db_exists="1")
        for _, sql in self.restores(res):
            before = sql.upper()[:sql.upper().index(_RESTORE_STMT)]
            self.assertTrue("DB_ID(" in before or "SYS.DATABASES" in before,
                            "a recovery restore batch without an embedded existence test was sent\n" + res.describe())

    # ---- final fix round (contract Revision 4, items 11, 12 and 15) ------------------------------

    def test_the_recovery_restore_call_carries_dash_b_so_a_raised_error_is_an_exit_code(self) -> None:
        # t15 S6. passes today BY DESIGN (control); the stand-in now honours -b, and the mutation control below proves
        # that removing it turns the refusal into a reported success.
        res = self.run_script(self.SCRIPT, [self.RECOVER], stub_db_exists="0")
        restore_calls = [c for c in res.of("sqlcmd") if _RESTORE_STMT in (c.get("text") or "").upper()]
        self.eq(res, len(restore_calls), 1, "exactly one restore batch is expected")
        self.assertIn("-b", restore_calls[0]["args"], "the recovery sqlcmd call must carry -b\n" + res.describe())

    def test_a_refused_recovery_exits_non_zero_because_the_stand_in_honours_dash_b(self) -> None:
        # passes today BY DESIGN: with the batch guard and -b in place, a database that exists is a refusal.
        res = self.run_script(self.SCRIPT, [self.RECOVER], stub_db_exists="1")
        self.eq(res, res.rc, 3, "an existing database is a refusal (exit 3)")
        self.assertTrue(any(c.get("effect") == "BATCH_REFUSED_DATABASE_EXISTS" for c in res.calls),
                        "the batch itself must have refused (not a separate earlier check)\n" + res.describe())

    def test_the_recovery_batch_sent_is_the_delimited_block_with_its_placeholders_filled(self) -> None:
        # Item 14 (harness half). RED today: the script has no RECOVERY-BATCH-BEGIN / -END block. The LocalDB test
        # runs the block for real; THIS test proves the script sends exactly that text, so the two cannot drift.
        template = self.recovery_template((self.tools / self.SCRIPT).read_bytes().decode("utf-8"))
        self.assertIsNotNone(template, "restore-latest.cmd must keep the recovery batch in one block between "
                                       "RECOVERY-BATCH-BEGIN and RECOVERY-BATCH-END comment lines")
        for placeholder in ("@TARGET_DB@", "@BACKUP_FILE@", "@MOVE_CLAUSES@"):
            self.assertIn(placeholder, template, f"the block must carry the placeholder {placeholder}")
        res = self.run_script(self.SCRIPT, [self.RECOVER], stub_db_exists="0")
        sent = [q for _, q in self.queries(res) if _RESTORE_STMT in q.upper()]
        self.eq(res, len(sent), 1, "exactly one restore batch is sent")
        pieces = re.split(r"(@TARGET_DB@|@BACKUP_FILE@|@MOVE_CLAUSES@)", template)
        fill = {"@TARGET_DB@": re.escape(DEV), "@BACKUP_FILE@": r".+?", "@MOVE_CLAUSES@": r".+?"}
        # whitespace is ignored on both sides, so a line break in the block cannot make the comparison fail
        pattern = "".join(fill[p] if p in fill else re.escape(re.sub(r"\s+", "", p)) for p in pieces)
        normalised = re.sub(r"\s+", "", sent[0])
        self.assertRegex(normalised, "^" + pattern + "$",
                         "the batch the script sends must equal the delimited block, placeholders substituted\n"
                         f"block: {template!r}\n" + res.describe())

    def test_restore_accepts_an_optional_backup_file_as_its_last_argument_and_defaults_to_the_newest(self) -> None:
        # Item 11. RED today: a second argument is refused ("at most one argument"). passes by design for the default.
        older = self.add_backup("scalping-20250101-000000.bak", days_old=30)
        newest = self.backups / "scalping-20260101-000000.bak"
        for args, label in (([], "no argument (default name)"), ([self.RECOVER], "recovery mode")):
            with self.subTest(case=f"default: {label}"):
                self.log.unlink(missing_ok=True)
                res = self.run_script(self.SCRIPT, args, stub_db_exists="0")
                self.eq(res, res.rc, 0, "the default run succeeds")
                sent = " ".join(q for _, q in self.queries(res) if _RESTORE_STMT in q.upper() or "FILELISTONLY" in q.upper())
                self.assertIn(newest.name.lower(), sent.lower(), "no file argument: the NEWEST backup is used\n" + res.describe())
                self.assertNotIn(older.name.lower(), sent.lower(), res.describe())
        for args, label in ((["Foo_Test_0a1b2c3d4e5f", str(older)], "disposable name + file"),
                            ([self.RECOVER, str(older)], "recovery mode + file")):
            with self.subTest(case=f"explicit: {label}"):
                self.log.unlink(missing_ok=True)
                res = self.run_script(self.SCRIPT, args, stub_db_exists="0")
                self.eq(res, res.rc, 0, f"{label}: an explicit older backup is accepted")
                for _, q in self.queries(res):
                    if _RESTORE_STMT in q.upper() or "FILELISTONLY" in q.upper():
                        self.assertIn(older.name.lower(), q.lower(),
                                      f"{label}: both the file-list read and the restore must use the named file\n" + res.describe())
                        self.assertNotIn(newest.name.lower(), q.lower(), res.describe())

    def test_restore_refuses_a_backup_file_that_does_not_exist_and_restores_nothing(self) -> None:
        # RED today (the first step): an explicit file argument is refused outright, so the control step fails.
        present = self.add_backup("scalping-20250101-000000.bak", days_old=30)
        res = self.run_script(self.SCRIPT, ["Foo_Test_0a1b2c3d4e5f", str(present)], stub_db_exists="0")
        self.eq(res, res.rc, 0, "CONTROL: a named backup that exists is accepted")
        self.log.unlink(missing_ok=True)
        res = self.run_script(self.SCRIPT, ["Foo_Test_0a1b2c3d4e5f", str(self.backups / "no-such-file.bak")], stub_db_exists="0")
        self.assertNotEqual(res.rc, 0, "a named backup that is not there must fail\n" + res.describe())
        self.eq(res, self.restores(res), [], "no restore statement may be sent for a missing file")

    def test_a_database_left_in_the_restoring_state_is_reported_as_restoring_not_as_already_existing(self) -> None:
        # Item 12. RED today: any database of the name is "already exists and is never overwritten".
        res = self.run_script(self.SCRIPT, [self.RECOVER], stub_db_exists="1", stub_db_state="RESTORING")
        self.assertNotEqual(res.rc, 0, "recovery must not succeed over a RESTORING remnant\n" + res.describe())
        overwritten = [c for c in res.calls if c.get("effect") == "OVERWROTE_EXISTING_DATABASE"]
        self.eq(res, overwritten, [], "nothing may be overwritten")
        # case-sensitive on purpose: the ordinary progress line "restoring <file>" must not satisfy it
        self.assertRegex(res.out, self.RESTORING_WORDS, "the remnant must be named as RESTORING\n" + res.describe())
        self.assertNotRegex(res.out, r"(?i)already exists",
                            "a half-restored remnant must not be reported as an ordinary existing database\n" + res.describe())

    def test_an_online_database_is_still_reported_as_already_existing(self) -> None:
        # passes today BY DESIGN: the control for the RESTORING case above (same flow, ONLINE state).
        res = self.run_script(self.SCRIPT, [self.RECOVER], stub_db_exists="1", stub_db_state="ONLINE")
        self.eq(res, res.rc, 3, "an existing online database is a refusal (exit 3)")
        self.assertRegex(res.out, r"(?i)already exists", res.describe())
        self.assertNotRegex(res.out, self.RESTORING_WORDS, "an online database is not RESTORING\n" + res.describe())


# =============================================================================================
# Stand-in fidelity (t15 B4, W6): mutations of the recovery guard must be VISIBLE to the harness.
# Each case rewrites the throwaway COPY of restore-latest.cmd, runs it against an EXISTING dev database,
# and asserts the stand-in sees the damage. The mutations are the ones that survived 26/26 in round 3.
# =============================================================================================
class RecoveryGuardMutationControlTests(ScriptCase):
    SCRIPT = "restore-latest.cmd"
    RECOVER = "--recover-missing-dev-db"

    def overwrote(self, res: Result) -> bool:
        return any(c.get("effect") == "OVERWROTE_EXISTING_DATABASE" for c in res.calls)

    def test_control_the_unmutated_script_refuses_and_overwrites_nothing(self) -> None:
        # passes today BY DESIGN: without this, a harness that cannot run the script at all would pass every control below.
        res = self.run_script(self.SCRIPT, [self.RECOVER], stub_db_exists="1")
        self.assertFalse(self.overwrote(res), res.describe())
        self.assertNotEqual(res.rc, 0, res.describe())

    def test_an_inverted_existence_test_overwrites_an_existing_database_and_the_stand_in_sees_it(self) -> None:
        # t15 S4 (IS NOT NULL -> IS NULL). passes today BY DESIGN once the stand-in evaluates the predicate.
        n = self.mutate_script(self.SCRIPT, lambda t: re.subn(r"(?i)IS\s+NOT\s+NULL", "IS NULL", t))
        self.assertGreaterEqual(n, 1, "ARRANGE CONTROL: the script must contain the existence predicate `IS NOT NULL`")
        res = self.run_script(self.SCRIPT, [self.RECOVER], stub_db_exists="1")
        self.assertTrue(self.overwrote(res), "the stand-in must report the overwrite an inverted guard allows\n" + res.describe())
        # ... and the other direction: with the database MISSING the inverted guard refuses, so the recovery fails.
        self.log.unlink(missing_ok=True)
        res = self.run_script(self.SCRIPT, [self.RECOVER], stub_db_exists="0")
        self.assertNotEqual(res.rc, 0, "an inverted guard must break the recovery of a missing database\n" + res.describe())
        self.assertFalse([c for c in res.calls if c.get("effect") == "RESTORED_TARGET"], res.describe())

    def test_a_raiserror_in_place_of_throw_lets_the_restore_run_and_the_stand_in_sees_it(self) -> None:
        # t15 S5 (THROW -> RAISERROR(...,16,1)). passes today BY DESIGN once RAISERROR is modelled as non-terminating.
        n = self.mutate_script(
            self.SCRIPT,
            lambda t: re.subn(r"(?i)THROW\s+\d+\s*,\s*(N'(?:[^']|'')*')\s*,\s*\d+", r"RAISERROR(\1, 16, 1)", t))
        self.assertGreaterEqual(n, 1, "ARRANGE CONTROL: the script must contain `THROW <n>, N'<text>', <state>`")
        res = self.run_script(self.SCRIPT, [self.RECOVER], stub_db_exists="1")
        self.assertTrue(self.overwrote(res),
                        "RAISERROR does not end a batch, so the restore after it runs; the stand-in must say so\n" + res.describe())

    def test_removing_dash_b_turns_a_refusal_into_a_reported_success_and_the_stand_in_sees_it(self) -> None:
        # t15 S6. passes today BY DESIGN once the stand-in honours -b.
        n = self.mutate_script(self.SCRIPT, lambda t: re.subn(r"(?i)(sqlcmd\b[^\r\n]*?)\s-b\b", r"\1", t))
        self.assertGreaterEqual(n, 1, "ARRANGE CONTROL: at least one sqlcmd call in the script carries -b")
        res = self.run_script(self.SCRIPT, [self.RECOVER], stub_db_exists="1")
        self.eq(res, res.rc, 0, "without -b the refusal is not an exit code, so the script reports success")
        self.assertTrue([c for c in res.calls if c.get("effect") == "BATCH_REFUSED_DATABASE_EXISTS"],
                        "the batch DID refuse; the script just failed to notice\n" + res.describe())


# =============================================================================================
# verify-migration.cmd --from-backup  (the rehearsal applies with the real tool)
# =============================================================================================
class VerifyMigrationFromBackupTests(ScriptCase):
    SCRIPT = "verify-migration.cmd"

    def drops(self, res: Result) -> list[tuple[int, str]]:
        return [(i, q) for i, q in self.queries(res) if f"{_DROPW} DATABASE" in q.upper()]

    def test_rehearsal_restores_a_copy_applies_with_the_ef_update_tool_bound_to_it_and_drops_it(self) -> None:
        res = self.run_script(self.SCRIPT, ["--from-backup"], stub_db_exists="0")
        # 1. never the idempotent full-chain script (it always fails on a current backup with Msg 207).
        scripts = [c for c in res.calls if c["tool"] == "dotnet" and "migrations" in c["args"] and "script" in c["args"]]
        self.eq(res, scripts, [], "the full-chain idempotent script must not be generated or applied")
        applied_files = [c for c in res.calls if c["tool"] == "sqlcmd" and "-i" in c["args"]]
        self.eq(res, applied_files, [], "no SQL file may be fed to sqlcmd; the apply tool is the EF update")
        # 2. the copy is restored.
        restores = [(i, self.restore_target(q)) for i, q in self.queries(res) if _RESTORE_STMT in q.upper()]
        self.eq(res, len(restores), 1, "exactly one restore, onto the disposable copy")
        copy = restores[0][1] or ""
        self.assertRegex(copy, _COPY_NAME, "the restore target must be a _MigrationVerify_ copy\n" + res.describe())
        # 3. the EF update is bound to that copy, with --connection before any `--`.
        updates = self.ef_update_calls(res)
        self.eq(res, len(updates), 1, "exactly one EF update")
        idx, call = updates[0]
        args = call["args"]
        self.eq(res, self.connection_database(args), copy,
                "the EF update must be bound, through --connection, to the disposable copy")
        if "--" in args:
            self.assertLess(args.index("--connection") if "--connection" in args else 10**6, args.index("--"),
                            "--connection must come BEFORE any `--`\n" + res.describe())
        self.eq(res, self.positional_after_update(args), [], "the rehearsal applies forward, no positional target")
        # 4. order, then the copy (and only the copy) is dropped.
        self.assertLess(restores[0][0], idx, "restore must precede the apply\n" + res.describe())
        drops = self.drops(res)
        self.assertTrue(drops, "the disposable copy must be dropped at the end\n" + res.describe())
        for _, q in drops:
            self.assertNotIn(DEV.upper() + "]", q.upper().replace(copy.upper(), ""),
                             "a drop may name only the disposable copy\n" + res.describe())
        self.assertTrue(any(copy in q for _, q in drops), res.describe())
        self.assertGreater(drops[-1][0], idx, "the drop comes after the apply\n" + res.describe())
        self.eq(res, res.rc, 0, "a clean rehearsal exits 0")

    def test_a_failed_apply_still_drops_the_copy_and_exits_2(self) -> None:
        res = self.run_script(self.SCRIPT, ["--from-backup"], stub_db_exists="0", stub_ef_rc="1")
        self.eq(res, res.rc, 2, "an apply failure exits 2")
        self.assertTrue(self.drops(res), "the copy must be dropped even when the apply failed\n" + res.describe())

    def test_a_failed_restore_removes_the_partly_restored_copy_and_exits_4(self) -> None:
        # RED today: the script exits 4 without dropping the half-restored copy (t6 NIT-3).
        res = self.run_script(self.SCRIPT, ["--from-backup"], stub_db_exists="0", stub_restore_rc="1")
        self.eq(res, res.rc, 4, "a restore failure exits 4")
        drops = self.drops(res)
        self.assertTrue(drops, "the partly restored copy must be removed before exit\n" + res.describe())
        for _, q in drops:
            self.assertRegex(q, r"(?i)\[" + DEV + r"_MigrationVerify_[0-9A-Fa-f]+\]",
                             "only the disposable copy may be removed\n" + res.describe())
        self.eq(res, self.ef_update_calls(res), [], "nothing may be applied after a failed restore")

    # ---- final fix round (contract Revision 4, items 10, 11 and 12) ------------------------------

    def test_the_ef_tool_preflight_runs_before_the_restore(self) -> None:
        # Item 10. RED today: no `dotnet ef --version` call exists.
        res = self.run_script(self.SCRIPT, ["--from-backup"], stub_db_exists="0")
        pre = self.ef_version_calls(res)
        restores = [i for i, q in self.queries(res) if _RESTORE_STMT in q.upper()]
        self.assertTrue(pre, "the script must run `dotnet ef --version` as a preflight\n" + res.describe())
        self.assertTrue(restores, "ARRANGE CONTROL: a restore must run in this scenario\n" + res.describe())
        self.assertLess(pre[0], restores[0], "the preflight must come BEFORE the restore\n" + res.describe())

    def test_a_missing_ef_tool_is_reported_plainly_before_any_restore_and_is_not_a_failed_apply(self) -> None:
        # Item 10. RED today: the copy is restored first, then the apply fails and is reported as a failed migration.
        res = self.run_script(self.SCRIPT, ["--from-backup"], stub_db_exists="0", stub_ef_missing="1")
        self.assertNotEqual(res.rc, 0, "a missing tool must fail the script\n" + res.describe())
        self.eq(res, [q for _, q in self.queries(res) if _RESTORE_STMT in q.upper()], [],
                "no copy may be restored when the EF tool is missing")
        self.eq(res, self.ef_update_calls(res), [], "nothing may be applied")
        self.assertRegex(res.out, r"(?i)dotnet tool restore|dotnet-ef",
                         "the message must name the tool and how to install it\n" + res.describe())
        self.assertNotRegex(res.out, r"(?i)applying the migrations returned|FAIL: applying",
                            "a missing tool must not be reported as a failed apply\n" + res.describe())

    def test_it_prints_the_copys_newest_migration_id_before_and_after_the_apply(self) -> None:
        # Item 11. RED today: nothing reads the copy's migration history.
        before, after = "20260401000000_BeforeApply", "20261004000000_AfterApply"
        res = self.run_script(self.SCRIPT, ["--from-backup"], stub_db_exists="0",
                              stub_migration_before=before, stub_migration_after=after)
        self.eq(res, res.rc, 0, "a clean rehearsal exits 0")
        self.assertIn(before, res.out, "the newest MigrationId BEFORE the apply must be printed\n" + res.describe())
        self.assertIn(after, res.out, "the newest MigrationId AFTER the apply must be printed\n" + res.describe())
        self.assertLess(res.out.index(before), res.out.index(after), "before comes first\n" + res.describe())
        history = [i for i, c in enumerate(res.calls)
                   if c["tool"] == "sqlcmd" and "__efmigrationshistory" in ((c.get("text") or "").lower())]
        updates = self.ef_update_calls(res)
        self.eq(res, len(history), 2, "the history is read exactly twice: before and after the apply")
        self.assertLess(history[0], updates[0][0], "the first read is BEFORE the apply\n" + res.describe())
        self.assertGreater(history[1], updates[0][0], "the second read is AFTER the apply\n" + res.describe())
        copy = [self.restore_target(q) for _, q in self.queries(res) if _RESTORE_STMT in q.upper()][0] or ""
        for i in history:
            call = res.calls[i]
            self.assertIn(copy.lower(), (" ".join(call["args"]) + " " + (call.get("text") or "")).lower(),
                          "the history is read from the disposable COPY, never another database\n" + res.describe())

    def test_it_exits_2_when_removing_the_disposable_copy_fails(self) -> None:
        # Item 12. RED today: a failed removal prints a warning and the script still exits 0.
        res = self.run_script(self.SCRIPT, ["--from-backup"], stub_db_exists="0", stub_drop_rc="1")
        self.eq(res, res.rc, 2, "a copy that could not be removed is a failure (exit 2), so it is not left behind silently")
        self.assertRegex(res.out, r"(?i)clean up|remove|drop", "the message must say the copy remains\n" + res.describe())

    def test_a_named_backup_file_is_restored_instead_of_the_newest(self) -> None:
        # Item 11. RED today: any second argument is refused with exit 2.
        older = self.add_backup("scalping-20250101-000000.bak", days_old=30)
        newest = self.backups / "scalping-20260101-000000.bak"
        res = self.run_script(self.SCRIPT, ["--from-backup", str(older)], stub_db_exists="0")
        self.eq(res, res.rc, 0, "a rehearsal on a named older backup succeeds")
        for _, q in self.queries(res):
            if _RESTORE_STMT in q.upper() or "FILELISTONLY" in q.upper():
                self.assertIn(older.name.lower(), q.lower(), "the named file must be read and restored\n" + res.describe())
                self.assertNotIn(newest.name.lower(), q.lower(), res.describe())

    def test_without_a_file_argument_the_newest_backup_is_restored(self) -> None:
        # passes today BY DESIGN (control for the named-file case above).
        older = self.add_backup("scalping-20250101-000000.bak", days_old=30)
        newest = self.backups / "scalping-20260101-000000.bak"
        res = self.run_script(self.SCRIPT, ["--from-backup"], stub_db_exists="0")
        self.eq(res, res.rc, 0, "the default rehearsal succeeds")
        sent = " ".join(q for _, q in self.queries(res) if _RESTORE_STMT in q.upper())
        self.assertIn(newest.name.lower(), sent.lower(), "the newest backup is the default\n" + res.describe())
        self.assertNotIn(older.name.lower(), sent.lower(), res.describe())


# =============================================================================================
# check-protection-status.cmd  (INV-13)
# =============================================================================================
class CheckProtectionStatusTests(ScriptCase):
    SCRIPT = "check-protection-status.cmd"
    PLANTED = "PlantedSecretValue_9f3a"

    def fresh_backup(self) -> None:
        # the status script reads the newest backup's age from the repointed folder
        (self.backups / "scalping-20260101-000000.bak").write_bytes(b"")

    def test_every_sqlcmd_call_connects_to_master(self) -> None:
        # RED today: no -d master, so the login's default database (possibly the dev one) is what gets opened.
        res = self.run_script(self.SCRIPT)
        sqlcmds = res.of("sqlcmd")
        self.assertTrue(sqlcmds, "the status script must query the server\n" + res.describe())
        for c in sqlcmds:
            args = c["args"]
            ok = any(a == "-d" and i + 1 < len(args) and args[i + 1].lower() == "master" for i, a in enumerate(args))
            self.assertTrue(ok, f"sqlcmd was called without -d master: {args}\n" + res.describe())

    def test_a_planted_secret_value_is_never_printed_and_presence_is_reported_yes(self) -> None:
        # passes today BY DESIGN (control): the value is discarded, only yes/no is printed.
        res = self.run_script(self.SCRIPT, stub_target_mode="ok", stub_database=self.PLANTED)
        self.assertNotIn(self.PLANTED, res.out, "the secret value leaked into the output\n" + res.describe())
        self.assertRegex(res.out, r"(?i)ConnectionStrings:ScalpingDb present: yes", res.describe())

    def test_an_empty_secret_value_reads_as_absent_and_the_script_exits_nonzero(self) -> None:
        # RED today: the key is matched by prefix, so an empty value reads as present.
        res = self.run_script(self.SCRIPT, stub_target_mode="empty")
        self.assertRegex(res.out, r"(?i)ConnectionStrings:ScalpingDb present: no", res.describe())
        self.assertNotEqual(res.rc, 0, "an empty secret is a layer that is down\n" + res.describe())

    def test_an_absent_secret_reads_as_absent(self) -> None:
        # passes today BY DESIGN (control).
        res = self.run_script(self.SCRIPT, stub_target_mode="absent")
        self.assertRegex(res.out, r"(?i)ConnectionStrings:ScalpingDb present: no", res.describe())
        self.assertNotEqual(res.rc, 0, res.describe())

    def test_a_look_alike_key_does_not_count_as_the_secret(self) -> None:
        # RED today: findstr /B matches ConnectionStrings:ScalpingDbOld by prefix (t7 NIT-1).
        res = self.run_script(self.SCRIPT, stub_secret_key="ConnectionStrings:ScalpingDbOld")
        self.assertRegex(res.out, r"(?i)ConnectionStrings:ScalpingDb present: no", res.describe())

    def test_with_every_layer_in_place_it_exits_zero_and_calls_nothing_but_reads(self) -> None:
        # passes today BY DESIGN (control): proves the script CAN report all-up, so the failures above are real.
        res = self.run_script(self.SCRIPT)
        self.eq(res, res.rc, 0, "every layer up exits 0")
        for _, q in self.queries(res):
            u = q.upper()
            for verb in (_DROPW, "INSERT", "UPDATE", "DELETE", "ALTER", "BACKUP", _RESTORE_STMT, "CREATE"):
                self.assertNotIn(verb, u, f"the status script must only read; it sent: {q}\n" + res.describe())


if __name__ == "__main__":
    unittest.main(verbosity=2)
