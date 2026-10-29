-- data/routine_schema_v13.sql
CREATE TABLE IF NOT EXISTS routines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL REFERENCES students(id),
  title TEXT NOT NULL,                -- '玥玥的放学流程(二年级)'
  version INTEGER NOT NULL DEFAULT 1, -- 同孩子递增(不用年级当版本号)
  effective_from TEXT NOT NULL,       -- 'YYYY-MM-DD' 本地日,含当日
  note TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_routines ON routines(student_id, effective_from);

CREATE TABLE IF NOT EXISTS routine_steps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  routine_id INTEGER NOT NULL REFERENCES routines(id),
  seq INTEGER NOT NULL,
  name TEXT NOT NULL,      -- 主动作短句
  note TEXT,               -- 说明/约束小字
  time_hint TEXT           -- '22:30' 目标时间,仅展示
);
CREATE INDEX IF NOT EXISTS idx_rsteps ON routine_steps(routine_id, seq);
