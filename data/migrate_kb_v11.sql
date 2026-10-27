-- ============================================================
-- zhixidao v11：知识体系扩展（知识树 + 例题库 + 考卷逐题）
-- 依据：projects/zhixidao/知识体系扩展方案-v11.md（2026-10-27 定稿）
-- 铁律：先库后码——本文件先于 worker v11 部署执行
-- 注意：wrong_questions.node_id 的 ALTER 不在本文件（不幂等，单独执行）
-- ============================================================

CREATE TABLE IF NOT EXISTS knowledge_nodes (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  parent_id   INTEGER REFERENCES knowledge_nodes(id),
  level       INTEGER NOT NULL,
  name        TEXT NOT NULL,
  subject     TEXT,
  grade       TEXT,
  is_zhongkao INTEGER NOT NULL DEFAULT 0,
  tags        TEXT NOT NULL DEFAULT '[]',
  sort        INTEGER NOT NULL DEFAULT 0,
  status      TEXT NOT NULL DEFAULT 'active',
  note        TEXT,
  created_at  TEXT DEFAULT (datetime('now')),
  updated_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_kn_parent ON knowledge_nodes(parent_id, sort);

CREATE INDEX IF NOT EXISTS idx_kn_filter ON knowledge_nodes(subject, grade);

CREATE TABLE IF NOT EXISTS questions (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id     INTEGER NOT NULL REFERENCES knowledge_nodes(id),
  qtype       TEXT,
  difficulty  INTEGER,
  stem        TEXT NOT NULL,
  answer      TEXT,
  analysis    TEXT,
  image_ref   TEXT,
  source      TEXT DEFAULT 'agent',
  status      TEXT NOT NULL DEFAULT 'active',
  note        TEXT,
  created_at  TEXT DEFAULT (datetime('now')),
  updated_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_q_node ON questions(node_id);

CREATE TABLE IF NOT EXISTS paper_items (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  paper_id   INTEGER NOT NULL REFERENCES papers(id),
  qno        TEXT NOT NULL,
  node_id    INTEGER REFERENCES knowledge_nodes(id),
  correct    INTEGER,
  score      REAL,
  full_score REAL,
  note       TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(paper_id, qno)
);

CREATE INDEX IF NOT EXISTS idx_pi_node ON paper_items(node_id);
