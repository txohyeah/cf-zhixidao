-- 智习岛 P0 种子：学生 + 13 关字词过关卡 + 第一篇考卷时间线
-- 注意：本文件按 ';'+换行 切分语句，字符串内不得出现 ASCII 分号+换行

DELETE FROM students WHERE code = 'yueyue';

INSERT INTO students (code, display_name, grade_code, active)
VALUES ('yueyue', 'yueyue', 'grade_2', 1);

DELETE FROM levels WHERE student_id = (SELECT id FROM students WHERE code = 'yueyue');

INSERT INTO levels (student_id, kind, name, detail, sort) VALUES ((SELECT id FROM students WHERE code='yueyue'), 'word_write', '第1关 · 卷面错词Ⅰ', '松柏/杨树/辛苦/初升/红领巾', 1);
INSERT INTO levels (student_id, kind, name, detail, sort) VALUES ((SELECT id FROM students WHERE code='yueyue'), 'word_write', '第2关 · 卷面错词Ⅱ', '丛林/稻谷/归来/夏季/农事', 2);
INSERT INTO levels (student_id, kind, name, detail, sort) VALUES ((SELECT id FROM students WHERE code='yueyue'), 'word_write', '第3关 · yuán/huà 同音家族', '花园/队员/元旦/变化/说话', 3);
INSERT INTO levels (student_id, kind, name, detail, sort) VALUES ((SELECT id FROM students WHERE code='yueyue'), 'word_write', '第4关 · 树名关（树之歌）', '枫树/水杉/桦树/银杏/金桂', 4);
INSERT INTO levels (student_id, kind, name, detail, sort) VALUES ((SELECT id FROM students WHERE code='yueyue'), 'word_write', '第5关 · 鸟儿关（拍手歌）', '麻雀/老鹰/锦鸡/天鹅/大雁', 5);
INSERT INTO levels (student_id, kind, name, detail, sort) VALUES ((SELECT id FROM students WHERE code='yueyue'), 'char_choice', '选字关A · 园员元圆', '公（园）/队（员）/（元）宵/（圆）形', 6);
INSERT INTO levels (student_id, kind, name, detail, sort) VALUES ((SELECT id FROM students WHERE code='yueyue'), 'char_choice', '选字关B · 化画话', '变（化）/（画）图/说（话）/童（话）', 7);
INSERT INTO levels (student_id, kind, name, detail, sort) VALUES ((SELECT id FROM students WHERE code='yueyue'), 'char_choice', '选字关C · 辛和幸', '（辛）苦/（幸）福/（幸）好', 8);
INSERT INTO levels (student_id, kind, name, detail, sort) VALUES ((SELECT id FROM students WHERE code='yueyue'), 'liangci', '第6关 · 量词关', '座/块/方/丛/棵/条/个（重点：块和方）', 9);
INSERT INTO levels (student_id, kind, name, detail, sort) VALUES ((SELECT id FROM students WHERE code='yueyue'), 'zhuyin', '注音关', '港/翠/枫/杉/锦/灵/桦/杏', 10);
INSERT INTO levels (student_id, kind, name, detail, sort) VALUES ((SELECT id FROM students WHERE code='yueyue'), 'pianpang', '偏旁关 · 隹和鸟', '雀雁（隹）/鹰鸡鹅鹂（鸟）', 11);
INSERT INTO levels (student_id, kind, name, detail, sort) VALUES ((SELECT id FROM students WHERE code='yueyue'), 'tingbian', '听辨关 · 前后鼻音', '金/星/心/明/林/灵/民/京（口头）', 12);
INSERT INTO levels (student_id, kind, name, detail, sort) VALUES ((SELECT id FROM students WHERE code='yueyue'), 'duci', '读词关 · 秋天词语', '一叶知秋/丹桂飘香/层林尽染/红叶似火 等12词', 13);

DELETE FROM papers WHERE student_id = (SELECT id FROM students WHERE code='yueyue') AND title = '语文二上第二单元巩固练（过关训练）';

INSERT INTO papers (student_id, date, title, analysis_md, source)
VALUES (
  (SELECT id FROM students WHERE code='yueyue'),
  '2026-09-24',
  '语文二上第二单元巩固练（过关训练）',
  '**现象**：老师批注"有点慢，3道大题未做完"——查字典（字典没带）+ 2 道多步骤大题来不及。
**归因**：不是态度问题。同音形近字、前后鼻音、偏旁精细度提取不熟练 → 犹豫、涂改多 → 时间被吃光。慢和错是同一个根：熟练度不足。
**对策**：
- 每日字词过关（本站 13 关，全对才算过，家卫式得分过关）
- 每天查字典 1 字（部首→除去部首几画→页码→读音，1 分钟内）
- 每周 1 次 40 分钟限时小卷，练"先易后难 + 卡住 30 秒跳过做记号"
- 话术：不说"怎么又没做完"，改说"这是还没练壮的肌肉，每天 5 分钟就够"',
  'manual'
);
