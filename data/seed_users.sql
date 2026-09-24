-- 用户种子（哈希含随机盐；重跑前会先删同名单）
DELETE FROM users WHERE username IN ('baba', 'mama');
INSERT INTO users (username, pw_hash, role, display_name, active, created_at) VALUES ('baba', 'pbkdf2$100000$Fw6ITDFXOjPZ5UFDKzw4PQ==$/mlkorXMBAr7VkgjzhejDSVeRk8sQBshWpJtqb8A+24=', 'parent', '爸爸', 1, '2026-09-24T00:00:00Z');
INSERT INTO users (username, pw_hash, role, display_name, active, created_at) VALUES ('mama', 'pbkdf2$100000$sSL2TBPcx6cIcnBK2tjwBg==$OkVV427ZWi2WjHFKTbENlQ4jc8/oKbog6zNFuADBXfY=', 'parent', '妈妈', 1, '2026-09-24T00:00:00Z');
