-- Review Memory Store - MVP Schema
--
-- Just findings + dismissals. No embeddings, no complex schemas.

CREATE TABLE IF NOT EXISTS findings (
    -- Identity: file + function + category (NOT line number!)
    semantic_key TEXT PRIMARY KEY,  -- "file.go:FuncName:category"

    -- PR context
    pr_number INTEGER NOT NULL,

    -- Location
    file_path TEXT NOT NULL,
    function_name TEXT NOT NULL,    -- Stable across edits
    line_number INTEGER,            -- For display only, NOT identity

    -- Content
    category TEXT NOT NULL,         -- auth-bypass, nil-deref, etc.
    severity TEXT NOT NULL,         -- critical, high, medium, low
    description TEXT NOT NULL,

    -- Deduplication
    code_hash TEXT,                 -- Simple exact match

    -- Lifecycle
    status TEXT NOT NULL,           -- new, still-present, resolved
    first_seen_sha TEXT NOT NULL,   -- When first detected
    last_seen_sha TEXT NOT NULL,    -- Most recent occurrence

    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pr ON findings(pr_number);
CREATE INDEX IF NOT EXISTS idx_status ON findings(status);
CREATE INDEX IF NOT EXISTS idx_file_func ON findings(file_path, function_name);


-- NEW: Track WHY findings were dismissed
--
-- Example: "race-condition in coldStart access"
-- Reason: "Single-goroutine invariant - only runCollection calls this"
--
-- This gives future reviews context, not just a boolean "skip this"
CREATE TABLE IF NOT EXISTS intentional_exceptions (
    semantic_key TEXT PRIMARY KEY,
    dismissal_reason TEXT NOT NULL,  -- Human's reasoning
    approved_by TEXT,                -- Who made the call
    created_at TEXT NOT NULL,
    FOREIGN KEY (semantic_key) REFERENCES findings(semantic_key)
);


-- Example data:
--
-- findings:
-- ┌─────────────────────────────────────────────────┬───────┬──────────┬────────────┬────────────┬──────────────┬──────────┬─────────────┐
-- │ semantic_key                                    │ pr    │ file     │ function   │ line       │ category     │ severity │ status      │
-- ├─────────────────────────────────────────────────┼───────┼──────────┼────────────┼────────────┼──────────────┼──────────┼─────────────┤
-- │ exporter.go:runCollection:race-condition        │ 123   │ exp...   │ runColl... │ 221        │ race-cond... │ medium   │ still-pre...│
-- │ auth.go:CheckPermission:auth-bypass             │ 123   │ auth.go  │ CheckPer...│ 42         │ auth-bypass  │ high     │ resolved    │
-- └─────────────────────────────────────────────────┴───────┴──────────┴────────────┴────────────┴──────────────┴──────────┴─────────────┘
--
-- intentional_exceptions:
-- ┌─────────────────────────────────────────────────┬──────────────────────────────────────────────────┬─────────────────┐
-- │ semantic_key                                    │ dismissal_reason                                 │ approved_by     │
-- ├─────────────────────────────────────────────────┼──────────────────────────────────────────────────┼─────────────────┤
-- │ exporter.go:runCollection:race-condition        │ Single-goroutine invariant - only runCollect...  │ senior-engineer │
-- └─────────────────────────────────────────────────┴──────────────────────────────────────────────────┴─────────────────┘
