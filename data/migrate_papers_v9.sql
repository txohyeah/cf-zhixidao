-- v9 P1.5 考卷管理：papers 加科目/学期列（只跑一次；重复执行会报 duplicate column，无害）
ALTER TABLE papers ADD COLUMN subject TEXT NOT NULL DEFAULT 'chinese';
ALTER TABLE papers ADD COLUMN term TEXT NOT NULL DEFAULT '2026秋';
