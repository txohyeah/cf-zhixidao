# 智习岛（zhixidao）— 家庭学习小站

部署：https://zhixidao.pages.dev （CF Pages + D1，架构照抄 cf-crypto-site）

## 账号
- `baba` / `mama`（role=parent）：密码在 workspace `.secrets/zhixidao_pass_baba` / `_mama`（600 权限，明文不进对话/源码/日志）
- `qwenpaw`（助教，**测试专用**）：密码在 `.secrets/zhixidao_qwenpaw`；自检脚本 verify_live.py 全部用它，不碰真实账号
- 登录后右上角「改密码」自助修改（PBKDF2 100k 迭代，改密踢其他设备）
- P2 预留：`kid` 角色账号（学生自己打卡）

## 结构
- `schema.sql` — 9 表（students/users/levels/checkin/papers/sessions/login_throttle + P1: wrong_questions/weak_points，D1=zhixidao-db）
- `worker_src/_worker.js` → `dist/_worker.js` — 全站门禁 + API（login/logout/me/me-password/overview/checkin/papers）
- `dist/` — index.html（总览：14天点阵+连胜+13关卡+**错题弱项榜**+考卷摘要最近3张+用法说明）、papers.html（**考卷库**：增删改查+分页，P1.5）、cards.html（过关卡纸卡，打印/存PDF，门禁内）、login.html、favicon
- `scripts/cf_d1.py` — D1 桥接（create-bound/exec/query/info）
- `scripts/seed_users.py` — 生成用户种子（读 .secrets，输出仅含哈希；**重跑会使所有会话失效**）
- `scripts/sync_cuoti.py` — P1 错题同步：`~/.cuoti/cuoti.db`（只读）→ D1 副本全量替换；只迁 `STUDENT_MAP` 映射表内的错题，不带姓名/学校，测试学生数据不迁
- `scripts/verify_live.py` — 线上功能自检（qwenpaw 账号；带浏览器 UA 否则 CF 403；结尾自动补注验证会话）。P1.5 起含考卷库 8 项断言（页可达/新建含科目学期/列表字段/分页/编辑/删除）
- `scripts/seed_verify_session.py` — 注入 pw.py 部署核对用的验证会话（改密码测试会杀同账号其他会话，失效就重跑本脚本）
- `data/seed_users.sql`、`data/seed_data.sql` — 种子（用户/13关/首篇考卷分析）；`data/migrate_papers_v9.sql` — P1.5 papers 加 subject/term 迁移（已执行，勿重跑）

## 运维命令
```bash
python3 scripts/cf_d1.py info                                  # 库与绑定状态
python3 scripts/cf_d1.py exec <file.sql>                       # 执行 SQL
python3 scripts/sync_cuoti.py                                  # 错题库 → D1 副本（可加 --dry-run）
python3 scripts/seed_users.py && python3 scripts/cf_d1.py exec data/seed_users.sql  # 重置密码（会踢所有会话）
python3 scripts/seed_verify_session.py                         # 修复 pw.py 核对 cookie
python3 scripts/verify_live.py                                 # 功能自检（结尾自动补注验证会话）
python3 tools/publish-web/pw.py deploy --name zhixidao --dir projects/zhixidao/dist \
  --verify-cookie-file .secrets/verify-cookie-zhixidao.txt --note "..."   # 发布（勿裸 wrangler）
```

## 数据口径
- 打卡：result=pass/fail，pass=全对；一关一天可多次尝试
- 连胜：今天有全对从今天数，否则从昨天数（不提前断签）
- 日期一律 Asia/Shanghai 本地日（worker 固定 +8 偏移计算，D1 不用 date('now')）

## 路线
- P0（已上线）：总览 + 打卡 + 考卷时间线 + 改密码
- P1（已上线）：cuoti 错题弱项——本地 `~/.cuoti/cuoti.db` 仍是错题工作库（入库/组卷/analytics），D1 只存展示副本（wrong_questions + weak_points），`sync_cuoti.py` 单向同步；顽固错题=近30天错≥3次打 🔥；cuoti skill 已迁入本方 `skills/cuoti` 并注册（CuoTiAgent 可退役）
- P1.5（已上线 2026-09-24）：考卷库 papers.html——增删改查 + 分页（20/页），papers 表加 subject/term（科目语文/数学/英语 + 学期）；总览考卷区改「最近 3 张摘要 + 全部考卷入口」；功能模块规划见 `功能模块规划.md`
- v10（已上线 2026-10-19）：**口算记录 math.html**——小虾站（u4-xuexi.xiaoxia.io）106 场（2026-09-10~10-19）全量迁入，此后 zhixidao 是口算唯一记录入口、小虾站停写。数据表 math_topics/math_sessions/math_wrong_items/math_marks（都在 schema.sql，迁移 SQL `data/math_schema_v10.sql`，导入脚本 `scripts/import_math_from_xiaoxia.py` 含对账断言：106 场/2398 题/2351 对/19673s）。页面功能：统计卡（最近一次/累计/正确率/最快纪录）+ 14 天点阵与口算连胜（有场次=亮粉，"在校完成无数据"=橙标记）+ 题型筛选联动 + 趋势三图（秒每题/正确率/题量，单次+近5+近30均值，SVG 零依赖）+ 题型对照表 + 全部记录（错题明细/备注全保留，30 条/页加载更早）+ 补录/编辑/删除（错题明细多行录入）。总览右栏新增🧮口算摘要行。API：GET /api/math/all（全量下发前端聚合）+ sessions/marks CRUD（仅家长）。verify_live 含口算 14 项断言（--math-only 可单跑口算段）。坑：D1 外键强制——删场次必须先删 math_wrong_items 子表（worker 已修）；auth 表已叫 sessions，口算场次用 math_sessions。后续记录方式：跟 agent 说一句（"玥玥今天第2场 5分30秒 21/22 错 64-46=28 应18"）或 math.html「＋补录一场」表单。
- P2：kid 账号、生字本爬取、周报推送
- P3 备忘（条件触发才做）：错题 >300 条拆独立页；跨学期/科目筛选（字段已就位）；多 kid
