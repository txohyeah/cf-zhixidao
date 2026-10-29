-- data/seed_routine_v13.sql
-- v13 种子:玥玥(学生1)放学流程 v1(七步)。幂等,可重跑。
-- 注意:D1 限制复合 SELECT 项数,故拆 7 条独立 INSERT(本地 sqlite 无此限)。

INSERT INTO routines (student_id, title, version, effective_from)
SELECT 1, '玥玥的放学流程（二年级）', 1, '2026-10-29'
WHERE NOT EXISTS (SELECT 1 FROM routines WHERE student_id=1 AND version=1);

INSERT INTO routine_steps (routine_id, seq, name, note, time_hint)
SELECT r.id, 1, '跳绳 + 立位体前屈', NULL, NULL FROM routines r
WHERE r.student_id=1 AND r.version=1
AND NOT EXISTS (SELECT 1 FROM routine_steps x WHERE x.routine_id=r.id AND x.seq=1);

INSERT INTO routine_steps (routine_id, seq, name, note, time_hint)
SELECT r.id, 2, '吃晚饭 + 休息 30 分钟', '屏幕时间最多 15 分钟', NULL FROM routines r
WHERE r.student_id=1 AND r.version=1
AND NOT EXISTS (SELECT 1 FROM routine_steps x WHERE x.routine_id=r.id AND x.seq=2);

INSERT INTO routine_steps (routine_id, seq, name, note, time_hint)
SELECT r.id, 3, '写作业', NULL, NULL FROM routines r
WHERE r.student_id=1 AND r.version=1
AND NOT EXISTS (SELECT 1 FROM routine_steps x WHERE x.routine_id=r.id AND x.seq=3);

INSERT INTO routine_steps (routine_id, seq, name, note, time_hint)
SELECT r.id, 4, '休息 + 小点心', NULL, NULL FROM routines r
WHERE r.student_id=1 AND r.version=1
AND NOT EXISTS (SELECT 1 FROM routine_steps x WHERE x.routine_id=r.id AND x.seq=4);

INSERT INTO routine_steps (routine_id, seq, name, note, time_hint)
SELECT r.id, 5, '巩固训练', '有待复习错题就练;没有就自由活动', NULL FROM routines r
WHERE r.student_id=1 AND r.version=1
AND NOT EXISTS (SELECT 1 FROM routine_steps x WHERE x.routine_id=r.id AND x.seq=5);

INSERT INTO routine_steps (routine_id, seq, name, note, time_hint)
SELECT r.id, 6, '睡前阅读', NULL, NULL FROM routines r
WHERE r.student_id=1 AND r.version=1
AND NOT EXISTS (SELECT 1 FROM routine_steps x WHERE x.routine_id=r.id AND x.seq=6);

INSERT INTO routine_steps (routine_id, seq, name, note, time_hint)
SELECT r.id, 7, '上床睡觉', NULL, '22:30' FROM routines r
WHERE r.student_id=1 AND r.version=1
AND NOT EXISTS (SELECT 1 FROM routine_steps x WHERE x.routine_id=r.id AND x.seq=7);
