# T-SQL Patterns Reference

Reusable patterns for SQL Server schema design and query authoring. Referenced by the `/sql-server-patterns` skill and `.claude/agents/dotnet-backend-architect.md` -- the routing named in `CLAUDE.md`'s Agent Selection Guide. When either needs a pattern, it consults this file rather than inlining examples. (An earlier revision cited a sql-server-architect agent; no such agent has ever existed.)

---

## Table partitioning

```sql
-- Partition function: define boundaries
CREATE PARTITION FUNCTION pf_Monthly (datetime2)
AS RANGE RIGHT FOR VALUES (
    '2026-01-01', '2026-02-01', '2026-03-01' -- ...
);

-- Partition scheme: map partitions to filegroups
CREATE PARTITION SCHEME ps_Monthly
AS PARTITION pf_Monthly ALL TO ([PRIMARY]);

-- Table on the partition scheme
CREATE TABLE HistoricalBars (
    Id uniqueidentifier NOT NULL,
    Symbol nvarchar(32) NOT NULL,
    Timestamp datetime2 NOT NULL,
    -- ...
    CONSTRAINT PK_HistoricalBars PRIMARY KEY CLUSTERED (Id, Timestamp)
) ON ps_Monthly(Timestamp);
```

**Critical rules:**
- Partition key MUST be in the clustered index key.
- Unique indexes must include the partition key.

**Partition when:** table > 10M rows AND growing, clear time/category partition key, queries naturally filter on it (partition elimination), need to switch partitions out for archival.

**Don't partition when:** table < 1M rows (overhead exceeds benefit), queries don't filter on partition key (full scan across all partitions), OLTP point lookups by non-partition key (no benefit, possible regression).

---

## Hierarchical data — 4 options

**Option 1 — `HierarchyId` (native, best for deep trees with path queries):**

```sql
CREATE TABLE Categories (
    Id int IDENTITY PRIMARY KEY,
    Node hierarchyid NOT NULL,
    Level AS Node.GetLevel() PERSISTED,
    Name nvarchar(256) NOT NULL,
    INDEX IX_Categories_Node UNIQUE (Node),
    INDEX IX_Categories_BreadthFirst (Level, Node)
);

-- Get all descendants of a node:
SELECT * FROM Categories WHERE Node.IsDescendantOf(@parentNode) = 1;
```

**Option 2 — Adjacency list (simplest, EF Core friendly, best for shallow trees):**

```sql
CREATE TABLE Categories (
    Id int IDENTITY PRIMARY KEY,
    ParentId int NULL FOREIGN KEY REFERENCES Categories(Id),
    Name nvarchar(256) NOT NULL,
    INDEX IX_Categories_ParentId (ParentId)
);
-- Recursive CTE for tree traversal.
```

**Option 3 — Closure table (best for many-to-many ancestor queries, fast reads):**

```sql
CREATE TABLE CategoryClosure (
    AncestorId int NOT NULL FOREIGN KEY REFERENCES Categories(Id),
    DescendantId int NOT NULL FOREIGN KEY REFERENCES Categories(Id),
    Depth int NOT NULL,
    PRIMARY KEY (AncestorId, DescendantId),
    INDEX IX_Closure_Descendant (DescendantId, AncestorId)
);
```

**Option 4 — Materialized path (string path, good for breadcrumbs):**

```sql
CREATE TABLE Categories (
    Id int IDENTITY PRIMARY KEY,
    Path nvarchar(900) NOT NULL,  -- e.g., '/1/5/12/'
    Name nvarchar(256) NOT NULL,
    INDEX IX_Categories_Path (Path)
);
-- WHERE Path LIKE '/1/5/%' uses index seek (left-anchored).
```

---

## SARGable vs non-SARGable predicates

```sql
-- SARGable — CAN use index seek
WHERE CreatedAt >= '2026-01-01' AND CreatedAt < '2026-02-01'
WHERE Symbol = 'AAPL'
WHERE MarketCap BETWEEN 1000000000 AND 10000000000

-- Non-SARGable — CANNOT use index, forces scan
WHERE YEAR(CreatedAt) = 2026          -- function on column
WHERE Symbol LIKE '%PL'               -- leading wildcard
WHERE ISNULL(Sector, '') = 'Tech'     -- function wrapping column
WHERE Price * Quantity > 10000        -- expression on columns

-- Fix non-SARGable patterns
WHERE CreatedAt >= '2026-01-01' AND CreatedAt < '2027-01-01'  -- instead of YEAR()
WHERE Symbol LIKE 'AA%'              -- trailing wildcard only
WHERE Sector = 'Tech'                -- handle NULL separately with IS NULL
-- Use persisted computed column for expressions, then index it.
```

---

## Data compression

```sql
-- ROW: ~15-40% space savings, minimal CPU, good default for OLTP
ALTER TABLE ProviderCallLogs REBUILD WITH (DATA_COMPRESSION = ROW);

-- PAGE: ~40-60% savings, more CPU, best for read-heavy/archive
ALTER TABLE HistoricalBars REBUILD WITH (DATA_COMPRESSION = PAGE);

-- Per-partition tiering (hot vs cold)
ALTER TABLE HistoricalBars REBUILD PARTITION = 1 WITH (DATA_COMPRESSION = PAGE);
ALTER TABLE HistoricalBars REBUILD PARTITION = 12 WITH (DATA_COMPRESSION = ROW);
```

---

## Temporal tables (system-versioned)

```sql
CREATE TABLE Strategies (
    Id uniqueidentifier NOT NULL PRIMARY KEY,
    Name nvarchar(256) NOT NULL,
    -- ...
    ValidFrom datetime2 GENERATED ALWAYS AS ROW START NOT NULL,
    ValidTo datetime2 GENERATED ALWAYS AS ROW END NOT NULL,
    PERIOD FOR SYSTEM_TIME (ValidFrom, ValidTo)
) WITH (SYSTEM_VERSIONING = ON (HISTORY_TABLE = dbo.StrategiesHistory));

-- Point-in-time query
SELECT * FROM Strategies FOR SYSTEM_TIME AS OF '2026-03-15T12:00:00';
```
