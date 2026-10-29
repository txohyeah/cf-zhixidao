# 智习岛（zhixidao）— 家庭学习小站

部署：https://zhixidao.pages.dev （CF Pages + D1，架构照抄 cf-crypto-site）

## 账号
- `baba` / `mama`（role=parent）：密码在 workspace `.secrets/zhixidao_pass_baba` / `_mama`（600 权限，明文不进对话/源码/日志）
- `qwenpaw`（助教，**测试专用**）：密码在 `.secrets/zhixidao_qwenpaw`；自检脚本 verify_live.py 全部用它，不碰真实账号
- 登录后右上角「改密码」自助修改（PBKDF2 100k 迭代，改密踢其他设备）
- P2 预留：`kid` 角色账号（学生自己打卡）

## 结构
- `schema.sql` — 全量初始化形态（v11 起： students/users/levels/checkin/papers/sessions/login_throttle + wrong_questions/weak_points(P1) + math 四表(v10) + knowledge_nodes/questions/paper_items(v11)，D1=zhixidao-db）
- `worker_src/_worker.js` → `dist/_worker.js` — 全站门禁 + API（login/logout/me/me-password/overview/checkin/papers + v10 math 全套 + **v11 kb：/api/kb/nodes、/api/kb/questions、/api/papers/:id/items、/api/assess**）
- `dist/` — index.html（总览：14天点阵+连胜+13关卡+**错题弱项榜**+考卷摘要最近3张+口算摘要+用法说明）、papers.html（**考卷库**：增删改查+分页，P1.5）、cards.html（过关卡纸卡，打印/存PDF，门禁内）、cards-math.html（**口算口诀卡 v10.1**：十几减几36式+凑十加法26式+家长页；源文件在 workspace `media/`，`scripts/build_cards.py` 参数化多卡构建）、math.html（**口算记录 v10**）、login.html、favicon
- `scripts/cf_d1.py` — D1 桥接（create-bound/exec/query/info）
- `scripts/seed_users.py` — 生成用户种子（读 .secrets，输出仅含哈希；**重跑会使所有会话失效**）
- `scripts/sync_cuoti.py` — **已于 v11 退役（文件保留备查）**：错题真源已迁 D1（agent 拍照识别直写），本地 `~/.cuoti/cuoti.db` 转只读历史归档；weak_points 表同步退役（总览弱项榜改 worker 实时聚合 kp_names）
- `scripts/verify_live.py` — 线上功能自检（qwenpaw 账号；带浏览器 UA 否则 CF 403；结尾自动补注验证会话）。P1.5 起含考卷库 8 项断言（页可达/新建含科目学期/列表字段/分页/编辑/删除）
- `scripts/seed_verify_session.py` — 注入 pw.py 部署核对用的验证会话（改密码测试会杀同账号其他会话，失效就重跑本脚本）
- `data/seed_users.sql`、`data/seed_data.sql` — 种子（用户/13关/首篇考卷分析）；`data/migrate_papers_v9.sql` — P1.5 papers 加 subject/term 迁移（已执行，勿重跑）

## 运维命令
```bash
python3 scripts/cf_d1.py info                                  # 库与绑定状态
python3 scripts/cf_d1.py exec <file.sql>                       # 执行 SQL
# sync_cuoti.py 已退役（v11 错题真源迁 D1），勿再跑
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
- P1（已上线 → v11 演进）：cuoti 错题弱项——**v11 起错题真源=D1**（写入=agent 拍照识别直写），本地 `~/.cuoti/cuoti.db` 只读归档，`sync_cuoti.py` 退役；顽固错题=近30天错≥3次打 🔥；weak_points 表退役（弱项榜=worker 实时聚合 kp_names）
- P1.5（已上线 2026-09-24）：考卷库 papers.html——增删改查 + 分页（20/页），papers 表加 subject/term（科目语文/数学/英语 + 学期）；总览考卷区改「最近 3 张摘要 + 全部考卷入口」；功能模块规划见 `功能模块规划.md`
- v10（已上线 2026-10-19）：**口算记录 math.html**——小虾站（u4-xuexi.xiaoxia.io）106 场（2026-09-10~10-19）全量迁入，此后 zhixidao 是口算唯一记录入口、小虾站停写。数据表 math_topics/math_sessions/math_wrong_items/math_marks（都在 schema.sql，迁移 SQL `data/math_schema_v10.sql`，导入脚本 `scripts/import_math_from_xiaoxia.py` 含对账断言：106 场/2398 题/2351 对/19673s）。页面功能：统计卡（最近一次/累计/正确率/最快纪录）+ 14 天点阵与口算连胜（有场次=亮粉，"在校完成无数据"=橙标记）+ 题型筛选联动 + 趋势三图（秒每题/正确率/题量，单次+近5+近30均值，SVG 零依赖）+ 题型对照表 + 全部记录（错题明细/备注全保留，30 条/页加载更早）+ 补录/编辑/删除（错题明细多行录入）。总览右栏新增🧮口算摘要行。API：GET /api/math/all（全量下发前端聚合）+ sessions/marks CRUD（仅家长）。verify_live 含口算 14 项断言（--math-only 可单跑口算段）。坑：D1 外键强制——删场次必须先删 math_wrong_items 子表（worker 已修）；auth 表已叫 sessions，口算场次用 math_sessions。后续记录方式：跟 agent 说一句（"玥玥今天第2场 5分30秒 21/22 错 64-46=28 应18"）或 math.html「＋补录一场」表单。
- v11（2026-10-27 上线 API，一期推进中）：**知识体系**——方案 `知识体系扩展方案-v11.md`（轻站点 agent 中枢 / 单树多视图 / 真源收敛 / 打卡去按钮 / 口算零伤 五决策）。D1 新表 knowledge_nodes（学科→册→章→知识点，grade/is_zhongkao 冗余列+tags 软删除）/ questions（例题主挂 node_id+tags 次挂）/ paper_items（考卷逐题 UNIQUE 幂等）；wrong_questions 加 node_id+tags。API：/api/kb/nodes（GET/POST/PUT 软删除无 DELETE）、/api/kb/questions（同）、/api/papers/:id/items（批量 UPSERT）、/api/assess（三色灯：红=累计错≥3且近30天仍错/黄=有错/绿=近期无错/灰=没练，递归 CTE 祖先聚合）。总览弱项榜切实时聚合。开发=codex 执笔+审核 fixes 2 处（questions tags 字段、apiPaperDelete 外键联动）；本地 sqlite3 冒烟 5 项+线上真测 24 项（首轮 22/24+复测 10/10）全过。待办：建树（数学/语文二上起步）、存量错题 31 题补挂、verify_live 扩展、前端重构（学习手账风+kb.html）
- v11.1（2026-10-27）：**打印中心**——print.html（build_cards.py CARDS 数据驱动生成，加新打印物=media 写源+注册一行）；乘法口诀表卡 cards-koujue99.html（全表 45 句/挖空自填/默写 3 页）；**口算练习纸生成器**（print.html 内嵌：题型多选 20以内/100以内进退位/乘法乘数/除法+题数 20/30/50+答案页，纯前端枚举题池，做完拍照→助教批改代录闭环）；index 两处散装打印链接收敛为一个入口。verify_live +3 断言
- v11.2（2026-10-28）：打印中心三件（codex 执笔+韩立审核）——**田字格练习纸卡** cards-tianzige.html（页1 纯田字格 12×10、页2 拼音田字格：四线格+田字格逐行对应）；**查字典练习卡** cards-zidian.html（音序 6 字+部首 6 字+答案页，页码留空以手头字典为准）；**时钟练习纸生成器**（print.html 内嵌：读钟面/画指针/时间推算 × 整点半点/5分钟刻度 × 6/8/12 题，SVG 钟面，与口算生成器共用 worksheet 容器互清）。verify_live +8 断言
- v12（2026-10-29 上线，codex 执笔+韩立审核，规格 `每日流程与多孩子扩展方案-v12.md`）：**每日放学流程打印表 + 多孩子 URL 切换 + 总览改名首页**。拍板：流程不做完成状态（无 logs 表），纸面方格手打勾；多孩子走右上角切换器+URL `?student=code`（session 不存当前孩子，无效参数 403 绝不静默回退，无参=第一个 active 学生；单学生显示纯徽章）；纸面「巩固训练」印条件句不接实时（在线另显待复习数仅供参考）。新增 routines/routine_steps 两表（版本化：effective_from 生效日，改流程=建新版，取当天前最新版；线上 D1 限制复合 SELECT 项数，种子拆 7 条独立 INSERT）；API：/api/students + /api/routine GET/POST/PUT（仅家长写，已生效流程不可改）；worker resolveStudent() 统一学生上下文（kid 预留=账号名绑 code），错题 4 处 yueyue 字面量清零、assess 旁路对齐、overview 打卡 JOIN 加 student_id 归属；前端 student-context.js（fetch 拦截注入 student+站内链接改写）、routine.html（A4 竖版一页、大编号+方格、页脚版本生效日期、@media print 隐藏导航/按钮/在线参考）、导航分组「学习｜知识库」+总览改名首页（全站 grep 清零）；index 顶部加流程摘要区。verify_live +7 断言（学生列表/无效拒绝/七步默认版/2099 未来版不干扰+先子后母清理/首页导航/打印页），本地双学生隔离冒烟 scripts/test_v12_local.py（kid 强制/流程考卷错题关卡口算隔离/缓存头）。坑：D1 复合 SELECT 项数限制（本地 sqlite 不限）；emoji 在无头浏览器渲染成豆腐块为字体缺失非 bug
- P2：kid 账号（关联方式需定：v12 预留按账号名=code）、生字本爬取、周报推送
- P3 备忘（条件触发才做）：错题 >300 条拆独立页；跨学期/科目筛选（字段已就位）；多 kid

## 状态快照（迁移自 PROFILE.md 项目矩阵 @2026-10-29）

- 原矩阵行（无损保留）：| **zhixidao** (智习岛) | v1 v10 | 🟢 已上线 | 照抄 crypto-site 架构（用户名+密码版）；`projects/zhixidao/`，代码 `git@github.com:txohyeah/cf-zhixidao.git`（v10 口算模块 a36c53c 已 push）；部署 https://zhixidao.pages.dev ；家长账号 baba/mama（密码在 `.secrets/zhixidao_pass_*`，不落对话）+ **qwenpaw 测试账号**（`.secrets/zhixidao_qwenpaw`，verify_live 专用，不碰真实账号）；D1 zhixidao-db；功能：玥玥字词 13 关过关卡+打卡（v9.3 起二次确认）+14天点阵/连胜+**P1 错题弱项榜**（~/.cuoti 单向同步 D1 副本，sync_cuoti.py，顽固题🔥）+**P1.5 考卷库**（papers.html 增删改查+分页+subject/term 列，总览留最近3张摘要；规划见 `projects/zhixidao/功能模块规划.md`）+登录后自助改密码+过关卡纸卡上站可打印/存PDF（cards.html）+**v10 口算记录 math.html（2026-10-19：小虾站 106 场 2026-09-10~10-19 全量迁入+对账断言（106场/2398题/2351对/19673s），此后 zhixidao 为口算唯一真源、小虾站停写；math_topics/sessions/wrong_items/marks 四表；统计卡+独立点阵连胜（橙=在校完成标记）+题型筛选联动+趋势三图 SVG+题型对照+错题明细/备注全保留+补录编辑删除；总览🧮摘要行；踩坑=D1 外键强制删场次先删子表、verify_live 加 IPv4-only 补丁治 urllib 走 IPv6 卡死）+口诀卡纸卡 cards-math.html（2026-10-21 十几减几36式+凑十加法26式，build_cards.py 参数化多卡构建）；日常记口算=拍照发韩立批改代录（source=manual，note 格式：错题+正解+错因+秒/题+当日第N场）；**verify_live 口算真数据断言已改 D1 动态对账（math_truth() 口径同 worker getStudentId=yueyue 排除 2099 测试日期，6569c78），代录新场次无需改脚本**；自检 37 项全绿（口算 14 项断言，--math-only 可单跑；真数据基线 119 场/2728 题/2670 对 @10-26），自检打卡带标记与真实数据隔离 |

## 归并记录

- 2026-10-29 晓道友确认：cuoti 错题本项目已并入本站（P1 错题弱项榜模块，~/.cuoti 单向同步 D1 副本）；projects/cuoti/ 独立入口撤除，错题相关仍可用 cuoti skill（数据在 ~/.cuoti/）。

- **cuoti skill 状态（2026-10-29 迁移补记）**: 错题管理能力现由工作区 `skills/cuoti/` 承载（家庭错题管理+智能组卷+学能分析；Python CLI + SQLite + ReportLab；数据 `~/.cuoti/cuoti.db`，知识点 1073 条，v1.0 完成）。旧仓库 tx-cuoti-review / tx-cuoti-review-skill 已于 2026-10-25 归档（本地 .trash/cleanup-20261025/，gitee 远端保留终态 a58ee8a）；原 CuoTiAgent 已于 2026-10-10 删除。修改原则：SKILL.md 不随意改，操作规则放 AGENTS.md。错题数据经 sync_cuoti.py 单向同步本站错题弱项榜（见上快照）
