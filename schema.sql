-- ============================================================
-- 智习岛 (zhixidao) · schema（v11 起 = 全量初始化形态）
-- 架构：D1 = 站点真源（打卡 + 考卷 + 口算 + 错题 + 知识体系）
--       错题真源已于 v11 迁入 D1（拍照识别→agent 直写），本地 ~/.cuoti
--       转只读历史归档，sync_cuoti.py 退役；weak_points 表退役（实时聚合）
-- 设计约束：所有业务表挂 student_id（多学生将来直接复用）；
--           知识树/例题库为家庭公共资产不挂 student
-- ============================================================

-- ---------- 账号与会话（照搬 cf-crypto-site 模式） ----------
CREATE TABLE IF NOT EXISTS users (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  username     TEXT NOT NULL UNIQUE,          -- baba / mama / (P2: yueyue)
  pw_hash      TEXT NOT NULL,                 -- PBKDF2，明文只进 .secrets
  role         TEXT NOT NULL DEFAULT 'parent',-- parent | kid
  display_name TEXT,
  active       INTEGER DEFAULT 1,
  created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
  token      TEXT PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id),
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS login_throttle (
  ip           TEXT PRIMARY KEY,
  fail_count   INTEGER DEFAULT 0,
  window_start TEXT
);

-- ---------- 学生 ----------
CREATE TABLE IF NOT EXISTS students (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  code         TEXT NOT NULL UNIQUE,          -- 'yueyue'
  display_name TEXT NOT NULL,                 -- 站内只用昵称
  grade_code   TEXT,                          -- 'grade_2'
  active       INTEGER DEFAULT 1
);

-- ---------- 过关卡 ----------
-- P0 = 字词过关卡 13 关；kind 区分题型，未来 cuoti 组卷关卡直接加 kind
CREATE TABLE IF NOT EXISTS levels (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL REFERENCES students(id),
  kind       TEXT NOT NULL,   -- word_write|char_choice|liangci|zhuyin|pianpang|tingbian|duci|...
  name       TEXT NOT NULL,   -- '第1关 · 卷面错词Ⅰ'
  detail     TEXT,            -- 词表/内容摘要（展示用）
  sort       INTEGER DEFAULT 0
);

-- ---------- 打卡 ----------
-- source: agent(跟agent说一句代写) | web_parent | web_kid(P2)
CREATE TABLE IF NOT EXISTS checkin (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL REFERENCES students(id),
  level_id   INTEGER NOT NULL REFERENCES levels(id),
  date       TEXT NOT NULL,                   -- YYYY-MM-DD
  result     TEXT NOT NULL,                   -- pass | fail
  stars      INTEGER DEFAULT 0,               -- 全对☆数
  note       TEXT,
  source     TEXT DEFAULT 'agent',
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_checkin ON checkin(student_id, level_id, date);

-- ---------- 考卷时间线 ----------
-- source: manual | cuoti（P1 迁移后，cuoti 的考卷/分析从这里进）
CREATE TABLE IF NOT EXISTS papers (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id  INTEGER NOT NULL REFERENCES students(id),
  date        TEXT NOT NULL,
  title       TEXT NOT NULL,                  -- '二上第二单元巩固练'
  analysis_md TEXT,                           -- 归因 + 方案摘要（markdown）
  subject     TEXT NOT NULL DEFAULT 'chinese', -- 科目：chinese / math（english 预留）
  term        TEXT NOT NULL DEFAULT '2026秋',  -- 学期：2026秋 / 2027春 …
  source      TEXT DEFAULT 'manual',
  created_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_papers ON papers(student_id, date);

-- ============================================================
-- P1：错题展示副本（cuoti 本地库单向同步，只展示不回写）
-- 源头：~/.cuoti/cuoti.db（错题工作库），scripts/sync_cuoti.py 全量替换
-- 隐私红线：不含学生姓名/学校/班级；学生以 code 标识（见 data/seed_data.sql 实例配置）
-- ============================================================

CREATE TABLE IF NOT EXISTS wrong_questions (
  id            TEXT PRIMARY KEY,           -- 沿用 cuoti question id（UUID）
  student_code  TEXT NOT NULL,              -- 'yueyue'
  subject_code  TEXT NOT NULL,              -- math | chinese
  title         TEXT,
  stem          TEXT,
  answer        TEXT,
  analysis      TEXT,
  question_type TEXT,                       -- fill | choice | unknown
  difficulty    INTEGER DEFAULT 1,
  status        TEXT,                       -- new | learning | mastered（cuoti 状态机）
  is_archived   INTEGER DEFAULT 0,
  wrong_count   INTEGER DEFAULT 0,          -- 复习答错次数（practice_records.result=incorrect）
  correct_count INTEGER DEFAULT 0,          -- 复习答对次数
  last_wrong_at TEXT,
  last_practice_at TEXT,
  created_at    TEXT,                       -- cuoti 题目录入时间
  kp_codes      TEXT,                       -- JSON 数组
  kp_names      TEXT,                       -- JSON 数组（展示用）
  stubborn      INTEGER DEFAULT 0,          -- 顽固错题：近 30 天错 ≥3 次
  sync_at       TEXT,                       -- v11 起停用（真源迁入，无同步链）
  node_id       INTEGER REFERENCES knowledge_nodes(id)  -- v11：挂知识树（真源迁移时加列）
);
CREATE INDEX IF NOT EXISTS idx_wq ON wrong_questions(student_code, is_archived, subject_code);

CREATE TABLE IF NOT EXISTS weak_points (
  student_code   TEXT NOT NULL,
  kp_code        TEXT NOT NULL,
  kp_name        TEXT,
  subject_code   TEXT,
  question_count INTEGER DEFAULT 0,         -- 关联错题数
  wrong_count    INTEGER DEFAULT 0,         -- 复习答错合计
  last_wrong_at  TEXT,
  stubborn_count INTEGER DEFAULT 0,         -- 顽固错题数
  sync_at        TEXT,
  PRIMARY KEY (student_code, kp_code)
);

-- ============================================================
-- v10：口算练习（math.html）
-- 真源：D1（小虾站 2026-09-10~10-19 全量迁移 106 场后，zhixidao 唯一记录入口；
--       小虾站停写）。所有表挂 student_id（二宝复用）。
-- ============================================================

-- 题型字典（name=正式名；alias=历史别名/页签简称）
CREATE TABLE IF NOT EXISTS math_topics (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  name    TEXT NOT NULL UNIQUE,
  alias   TEXT,
  sort_no INTEGER NOT NULL DEFAULT 0
);

-- 练习场次（auth 表已叫 sessions，口算场次用 math_sessions）
CREATE TABLE IF NOT EXISTS math_sessions (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id         INTEGER NOT NULL REFERENCES students(id),
  date               TEXT NOT NULL,            -- YYYY-MM-DD
  session_no         INTEGER NOT NULL DEFAULT 1, -- 当日第几场
  topic_id           INTEGER NOT NULL REFERENCES math_topics(id),
  duration_seconds   INTEGER,                  -- 秒；估算时存估算值
  duration_estimated INTEGER NOT NULL DEFAULT 0, -- 1=用时估算（原站未实测，note 有说明）
  total_questions    INTEGER NOT NULL,
  correct_count      INTEGER NOT NULL,
  ext_key            TEXT,                     -- 迁移溯源键（date-sessionno）
  note               TEXT,
  source             TEXT NOT NULL DEFAULT 'manual', -- manual | agent | import_xiaoxia
  created_at         TEXT DEFAULT (datetime('now')),
  UNIQUE(student_id, date, session_no)
);
CREATE INDEX IF NOT EXISTS idx_math_sessions ON math_sessions(student_id, date);

-- 错题明细（expr 支持任意算式：54+27 / ( )-15=62 / 2 ( ) 4 = 8）
CREATE TABLE IF NOT EXISTS math_wrong_items (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id     INTEGER NOT NULL REFERENCES math_sessions(id),
  expr           TEXT NOT NULL,
  answer_given   TEXT,
  answer_correct TEXT,
  note           TEXT
);
CREATE INDEX IF NOT EXISTS idx_math_wrong ON math_wrong_items(session_id);

-- 日历标记：有打卡意义但无场次数据的日子（如「在校完成，无具体数据」）
CREATE TABLE IF NOT EXISTS math_marks (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL REFERENCES students(id),
  date       TEXT NOT NULL,
  note       TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(student_id, date)
);

-- ============================================================
-- v11：知识体系（知识树 + 例题库 + 考卷逐题）
-- 详见 知识体系扩展方案-v11.md；节点永不物理删除（status=retired）
-- ============================================================

CREATE TABLE IF NOT EXISTS knowledge_nodes (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  parent_id   INTEGER REFERENCES knowledge_nodes(id),
  level       INTEGER NOT NULL,               -- 1=学科 2=册 3=章 4=节 5+=知识点
  name        TEXT NOT NULL,
  subject     TEXT,                           -- 冗余（写入侧传播）
  grade       TEXT,                           -- 冗余（'二上'…'九下'/'大一…'）
  is_zhongkao INTEGER NOT NULL DEFAULT 0,     -- 中考考点，只标实际考点粒度
  tags        TEXT NOT NULL DEFAULT '[]',     -- JSON 数组：教材版本等低频属性
  sort        INTEGER NOT NULL DEFAULT 0,
  status      TEXT NOT NULL DEFAULT 'active', -- active | retired（软删除）
  note        TEXT,
  created_at  TEXT DEFAULT (datetime('now')),
  updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_kn_parent ON knowledge_nodes(parent_id, sort);
CREATE INDEX IF NOT EXISTS idx_kn_filter ON knowledge_nodes(subject, grade);

CREATE TABLE IF NOT EXISTS questions (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id     INTEGER NOT NULL REFERENCES knowledge_nodes(id),
  qtype       TEXT,                           -- choice|fill|apply|proof|solution
  difficulty  INTEGER,                        -- 1-5
  stem        TEXT NOT NULL,
  answer      TEXT,
  analysis    TEXT,
  image_ref   TEXT,                           -- 题图（隐私红线未拍板，留列不启用）
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
  qno        TEXT NOT NULL,                  -- 题号文本，含 '17(2)'
  node_id    INTEGER REFERENCES knowledge_nodes(id),
  correct    INTEGER,                        -- 1|0|NULL(未判)
  score      REAL, full_score REAL,
  note       TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(paper_id, qno)
);
CREATE INDEX IF NOT EXISTS idx_pi_node ON paper_items(node_id);
