# ClickHouse Schema (Langfuse v3+)

Langfuse v3 stores trace events in ClickHouse. Metadata/config remains in PostgreSQL.

## `traces` table

```sql
CREATE TABLE traces (
    id String,
    timestamp DateTime64(3),
    name String,
    user_id Nullable(String),
    session_id Nullable(String),
    project_id String,
    metadata Nullable(String),        -- JSON string
    tags Array(String),
    environment Nullable(String),
    input Nullable(String),           -- JSON string (Langfuse structured format)
    output Nullable(String),          -- JSON string
    created_at DateTime64(3),
    updated_at DateTime64(3),
    -- ...
) ENGINE = ReplacingMergeTree()
ORDER BY (project_id, timestamp, id);
```

**Key columns for analysis:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | String | Trace UUID |
| `name` | String | Trace name (e.g. LLM chain name) |
| `user_id` | String | End user identifier (may be null if not configured) |
| `session_id` | String | Groups multiple traces in a session |
| `timestamp` | DateTime64(3) | When trace started |
| `input` | String | JSON: user messages |
| `output` | String | JSON: final output |
| `metadata` | String | JSON: custom metadata |

## `observations` table

```sql
CREATE TABLE observations (
    id String,
    trace_id String,
    name String,
    type String,                      -- GENERATION, SPAN, EVENT
    level Nullable(String),           -- DEBUG, DEFAULT, WARNING, ERROR
    start_time DateTime64(3),
    end_time Nullable(DateTime64(3)),
    parent_observation_id Nullable(String),
    metadata Nullable(String),
    model Nullable(String),           -- Model name if type=GENERATION
    input Nullable(String),
    output Nullable(String),
    -- ...
) ENGINE = ReplacingMergeTree()
ORDER BY (trace_id, start_time);
```

**Key columns for analysis:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | String | Observation UUID |
| `trace_id` | String | Parent trace UUID |
| `name` | String | Observation name |
| `type` | String | GENERATION, SPAN, or EVENT |
| `level` | String | ERROR indicates failures |
| `model` | String | LLM model name (for GENERATION type) |

## Typical queries

### Count traces by error level
```sql
SELECT level, count()
FROM observations
WHERE project_id = '...'
  AND start_time >= '2026-05-06'
  AND start_time < '2026-05-07'
  AND level != ''
GROUP BY level
```

### Find traces with most observations
```sql
SELECT trace_id, count() as obs_count
FROM observations
WHERE trace_id IN (SELECT id FROM traces WHERE project_id = '...')
GROUP BY trace_id
HAVING obs_count > 15
ORDER BY obs_count DESC
```

### Model usage distribution
```sql
SELECT model, count() as calls
FROM observations
WHERE type = 'GENERATION'
  AND model != ''
GROUP BY model
ORDER BY calls DESC
```
