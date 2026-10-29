# The test resource owner

This file is the full design behind the rule "One owner for every resource" in the cleanup section of the `unit-testing` skill. Read it when a project creates a database, a file, a container, a process or a queue during a test run, and no owner object exists yet.

A **test resource owner** is one object that creates, names, sets up and removes a resource that a test run needs. A test database owner is the common case. The same design fits a temporary folder, a container, a child process or a message queue.

## 1. The contract

1. **One object owns the whole lifecycle.** It chooses the name, creates the resource, runs the setup, and removes the resource.
2. **Callers never do any of those steps by hand.** A test, a base class or a script asks the owner for a resource and hands it back. No other code creates, names or removes one.
3. **Removal is guaranteed.** The owner removes the resource when the test, the class or the suite ends, whether the tests pass, fail or are aborted.
4. **The owner only touches what it made.** It tracks each resource at the moment it creates it and removes only tracked resources.

Why one object: a hand-built create-and-remove sequence in each test drifts. One copy forgets the failure path, another uses a name that matches a real resource, a third removes by pattern. A single owner has one place to get this right and one place to review.

## 2. Code standards the owner follows

Each standard comes with the reason it earns its place here.

| Standard | What it means for the owner | Why |
|---|---|---|
| Single responsibility | The owner manages the resource lifecycle and nothing else. Test data, assertions and business setup live elsewhere. | A class that also seeds data has two reasons to change, and a seeding bug can then skip the removal. |
| Setup step passed in (strategy) | The owner receives the setup as a value or a function. It does not contain the schema or the seed itself. | Each project sets up differently. Passing the step in keeps the owner reusable and lets a test supply its own. |
| Fixed order: create, set up, remove (template method) | The owner runs the steps in this order every time. Callers can change what a step does, never the order or whether removal runs. | A caller that could reorder the steps could also skip the removal. |
| Factory for disposable names | One method builds every name. It always adds the disposable marker and a unique part. | Names built by hand are the way a real resource ends up with a test-shaped name, or the other way round. |
| Dependency inversion on the managed thing | The owner depends on a small interface for the resource, such as "create", "remove" and "list leftovers". It does not depend on one concrete database client. | The same owner then serves a different engine, and a test of the owner itself can use a stand-in. |
| Open for extension, closed for modification | A new kind of resource is a new implementation of that interface. The owner's own code does not change. | Editing the owner for each new resource risks breaking the removal path that every other resource relies on. |

## 3. Rules learned the hard way

1. **The disposable-name rule.** Every name the owner builds carries a fixed disposable marker and a unique part that identifies the run. The owner refuses to remove any resource whose name lacks the marker. For a database, the marker must be one of the suffixes the destructive-database rule allows: `_DryRun`, `_MigrationVerify`, `_Sandbox`, `_Scratch`, `_Throwaway`, `_Test_<hex-guid>` or `_e2e_<hex-guid>`. Any other marker would get the owner's own removal blocked by the guard.
2. **The setup-failure policy.** If the setup step throws, the owner removes the resource first, then rethrows the setup error or records it. A resource created by a failed setup is never left behind.
3. **Always dispose the owner.** Wire the owner into the framework's teardown: `IDisposable` or `IAsyncLifetime.DisposeAsync` in xUnit, `afterEach` or `afterAll` in Vitest, `try/finally` in a script. An owner that is created and never disposed removes nothing.
4. **No step after the owner's setup in a test class's own setup.** Once the owner has made the resource, a later step in the class's setup can throw, and the framework then never reaches teardown. Put the owner's setup last, or move later steps before it.
5. **A failed removal is a named notice, never a silent skip.** When the owner cannot remove a resource, it reports the resource name and the reason. The verdict of the test that used the resource does not change. This is the same finding the skill's cleanup rule 4 asks for. The runtime leftover check in section 4 is a separate gate on the whole suite, so a resource that could not be removed still fails that check even though no single test failed.
6. **No removal by pattern.** The owner removes by the handle it tracked, never by a wildcard over names.

## 4. Two checks that keep the rule true

The owner only helps if nothing bypasses it. Two checks cover that, and each sees what the other cannot.

### The source-scan guard

A test that reads the project's source files and fails when a file outside a closed allow-list creates, names or removes a resource by hand. It looks for the calls and string shapes the owner is meant to hide, for example a database-create call or a disposable-suffix literal.

- **What it sees:** a hand-built lifecycle written in code, caught at build time and before any resource exists.
- **What it cannot see:** a name assembled at run time, a call made through a helper the scan does not list, or a resource created by a tool outside the source tree.
- **The owner is the first allow-list entry.** The owner's own file must create, name and remove the resource, so the scan would flag it. List that file with its reason, or exclude it by name.
- **Keep the allow-list closed.** Each entry names the file and a written reason. An entry added to make a failing scan pass, with no reason, defeats the guard.

### The runtime leftover check

After the whole suite, count the resources that match the disposable pattern and fail the suite if any remain. For a database engine, list databases whose names carry the disposable marker. For files, list the temp folder entries with the marker. This is a gate on the whole suite. It does not change the verdict of any single test.

Count only this run's resources. Put a run identifier inside every name the owner builds, and match on it. Without that, a second run on the same machine, for example from another worktree, has live resources that fail this run's check.

- **What it sees:** a resource of this run that survived for any reason, including a crash, an aborted run or a bypass the scan missed.
- **What it cannot see:** a resource whose name lacks the marker, a resource on another machine, a leftover from an earlier run (its run identifier differs), or anything when the run died before reaching the check.
- **Status:** this check is described here as the standard. A project builds it as code; the plugin ships no implementation of it.

Use both. The scan stops the mistake being written, and the leftover check catches the one that got through.

## 5. If the project has no owner yet

1. Check the `test.roots` slot of `.claude/project-profile.md` and search those roots for an existing owner before writing one.
2. If there is none, create one owner class in the test project's shared support area, following sections 1 to 3. Build it for the first resource the project needs, usually the database, and add other kinds later as new implementations of the resource interface.
3. Route every existing hand-built lifecycle through the owner in the same change, or list each one as an allow-list entry with a reason and a follow-up.
4. Add the source-scan guard once the first owner exists. Add the leftover check as a follow-up.

Do not copy another project's owner file into this one without reading it. A project's owner carries that project's engine and naming choices.
