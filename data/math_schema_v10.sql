-- v10 口算表（幂等，可重复执行）
CREATE TABLE IF NOT EXISTS math_topics (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  name    TEXT NOT NULL UNIQUE,
  alias   TEXT,
  sort_no INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS math_sessions (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id         INTEGER NOT NULL REFERENCES students(id),
  date               TEXT NOT NULL,
  session_no         INTEGER NOT NULL DEFAULT 1,
  topic_id           INTEGER NOT NULL REFERENCES math_topics(id),
  duration_seconds   INTEGER,
  duration_estimated INTEGER NOT NULL DEFAULT 0,
  total_questions    INTEGER NOT NULL,
  correct_count      INTEGER NOT NULL,
  ext_key            TEXT,
  note               TEXT,
  source             TEXT NOT NULL DEFAULT 'manual',
  created_at         TEXT DEFAULT (datetime('now')),
  UNIQUE(student_id, date, session_no)
);
CREATE INDEX IF NOT EXISTS idx_math_sessions ON math_sessions(student_id, date);
CREATE TABLE IF NOT EXISTS math_wrong_items (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id     INTEGER NOT NULL REFERENCES math_sessions(id),
  expr           TEXT NOT NULL,
  answer_given   TEXT,
  answer_correct TEXT,
  note           TEXT
);
CREATE INDEX IF NOT EXISTS idx_math_wrong ON math_wrong_items(session_id);
CREATE TABLE IF NOT EXISTS math_marks (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL REFERENCES students(id),
  date       TEXT NOT NULL,
  note       TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(student_id, date)
);

-- 题型字典 seed（INSERT OR IGNORE 幂等）
INSERT OR IGNORE INTO math_topics (name, alias, sort_no) VALUES
  ('乘法口诀表的运算',                              '口诀表',   1),
  ('100以内加减法 + 乘法口诀表',                    '加减＋口诀表', 2),
  ('乘法口诀表 + 加减法两步运算',                    '口诀＋两步运算', 3),
  ('100以内加减法',                                 NULL,       4),
  ('乘法口诀表 + 两步运算 + 括号填空（求因数）',      '括号填空', 5),
  ('填入符号',                                      NULL,       6);
