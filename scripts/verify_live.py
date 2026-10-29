#!/usr/bin/env python3
"""智习岛线上功能自检。用法: python3 scripts/verify_live.py [https://zhixidao.pages.dev]
检查项: health / 错密码拒绝 / 登录 / me / overview(含错题副本) / 打卡写入与生效 /
改密码(旧失效·新生效·还原) / 未登录 302 / 纸卡页门禁。
全程用 qwenpaw 测试账号，不回显任何密码；测试产生的打卡行由外部脚本清理。
"""
import http.cookiejar
import json
import os
import secrets
import socket
import string
import sys
import urllib.error
import urllib.request

# 本机 IPv6 无路由：强制 getaddrinfo 只返回 IPv4，否则 urllib 连接卡死（照 mail-assistant/fetch.py 的修法）
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only(*args, **kwargs):
    return [r for r in _orig_getaddrinfo(*args, **kwargs) if r[0] == socket.AF_INET]
socket.getaddrinfo = _ipv4_only

_args = [a for a in sys.argv[1:] if not a.startswith('--')]
BASE = (_args[0] if _args else 'https://zhixidao.pages.dev').rstrip('/')
# scripts/ → zhixidao/ → projects/ → workspace 根
WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SECRETS = os.path.join(WORKSPACE, '.secrets')
# Cloudflare 会 403 掉 Python-urllib 默认 UA，必须带浏览器 UA
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36'

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(method, path, body=None, op=None, text=False):
    import socket, time
    socket.setdefaulttimeout(75)
    last_err = None
    for attempt in range(5):
        req = urllib.request.Request(BASE + path, method=method)
        req.add_header('Content-Type', 'application/json')
        req.add_header('User-Agent', UA)
        data = json.dumps(body).encode() if body is not None else None
        try:
            with (op or opener).open(req, data=data) as r:
                raw = r.read().decode()
                return r.status, (raw if text else json.loads(raw or '{}'))
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            try:
                return e.code, json.loads(raw or '{}')
            except Exception:
                return e.code, {}
        except Exception as e:          # pages.dev 抖动：超时/连接重置 → 重试
            last_err = e
            time.sleep(3 + attempt * 4)
    raise last_err


def check(name, ok, detail=''):
    print(('✓' if ok else '✗'), name, detail)
    return ok


pw_t = open(os.path.join(SECRETS, 'zhixidao_qwenpaw')).read().strip()
fails = 0
MATH_ONLY = '--math-only' in sys.argv   # 只跑登录+口算段（网络抖动时快速验证口算链路）

s, d = call('GET', '/api/health')
fails += not check('health', s == 200 and d.get('ok'))

s, d = call('POST', '/api/login', {'username': 'qwenpaw', 'password': 'definitely-wrong-xyz'})
fails += not check('错密码 401', s == 401)

s, d = call('POST', '/api/login', {'username': 'qwenpaw', 'password': pw_t})
fails += not check('登录 qwenpaw', s == 200 and d.get('ok') and d.get('role') == 'parent')

s, d = call('GET', '/api/me')
fails += not check('me', s == 200 and d.get('authed') and d.get('username') == 'qwenpaw')

if not MATH_ONLY:
    # v13：临时流程只用独立随机标题，清理时先子表后主表。
    s, d = call('GET', '/api/students')
    students = d.get('students', [])
    target_student = next((x for x in students if x.get('code') == 'yueyue'), None)
    fails += not check('v13-学生列表', s == 200 and target_student is not None)
    s, d = call('GET', '/api/overview?student=invalid')
    fails += not check('v13-无效学生拒绝', s in (400, 403) and bool(d.get('error')))
    s, d = call('GET', '/api/routine')
    default_routine = d.get('routine') or {}
    fails += not check('v13-默认流程七步', s == 200 and default_routine.get('student_id') == (target_student or {}).get('id')
                       and default_routine.get('version') == 1 and len(d.get('steps', [])) == 7
                       and isinstance(d.get('pending_wrong'), int))
    title = 'verify-routine-' + secrets.token_hex(12)
    try:
        if target_student:
            s, d = call('POST', '/api/routine?student=yueyue', {'student_id': target_student['id'], 'title': title,
                         'effective_from': '2099-01-01', 'steps': [{'name': 'verify'}]})
            fails += not check('v13-创建未来版本', s == 200 and d.get('ok'))
            s, d = call('GET', '/api/routine?student=yueyue')
            fails += not check('v13-未来版本不改变当前版', s == 200 and (d.get('routine') or {}).get('version') == 1)
        else:
            fails += 2
    finally:
        if target_student:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from cf_d1 import find_db, execute_sql
            db = find_db()
            assert db, 'D1 不可达，无法清理测试流程'
            where = "student_id=%d AND title='%s' AND effective_from='2099-01-01'" % (target_student['id'], title)
            for sql in ('DELETE FROM routine_steps WHERE routine_id IN (SELECT id FROM routines WHERE ' + where + ')',
                        'DELETE FROM routines WHERE ' + where):
                result = execute_sql(db, sql)
                if not result[0]: raise RuntimeError('测试流程清理失败')
    s, page = fetch_text_retry('/') if 'fetch_text_retry' in globals() else call('GET', '/', text=True)
    fails += not check('v13-首页导航', s == 200 and '首页' in page and '知识库' in page and '总览' not in page)
    s, page = call('GET', '/routine.html?student=yueyue', text=True)
    fails += not check('v13-流程打印页', s == 200 and 'student-context.js' in page and 'window.print' in page)

    # papers 真数据计数动态对账（overview 考卷摘要=LIMIT 3；基线曾写死 1，用户录新卷即过期——2026-10-27 改动态）
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cf_d1 import find_db, execute_sql as _esql
    _db = find_db()
    papers_n = _esql(_db, "SELECT COUNT(*) n FROM papers WHERE student_id="
                          "(SELECT id FROM students WHERE code='yueyue' AND active=1)")[1][0]['n']
    s, d = call('GET', '/api/overview')
    lv = d.get('levels', [])
    wq = d.get('wrong_questions', [])
    wps = d.get('weak_points', [])
    fails += not check('overview(13关+%d考卷摘要+错题副本)' % min(papers_n, 3),
                       s == 200 and len(lv) == 13 and len(d.get('papers', [])) == min(papers_n, 3)
                       and len(wq) >= 30 and len(wps) >= 3,
                       'levels=%d papers=%d(真值%s) wq=%d weak=%d streak=%s'
                       % (len(lv), len(d.get('papers', [])), papers_n, len(wq), len(wps), d.get('streak')))

    if lv:
        target = sorted(lv, key=lambda x: x['sort'])[0]
        before = target['passes'] or 0
        # 自检打卡带 verify 标记：worker 端统计会排除该行（不污染真实学习数据）
        s, d = call('POST', '/api/checkin', {'level_id': target['id'], 'result': 'pass',
                                             'note': 'verify-selfcheck'})
        fails += not check('打卡写入', s == 200 and d.get('ok'))
        s, d = call('GET', '/api/overview')
        lv2 = {x['id']: x for x in d.get('levels', [])}
        # 隔离断言：带标记的行不应计入 attempts/passes（passes 保持打卡前的值）
        fails += not check('打卡隔离(自检行不计入统计)',
                           lv2[target['id']]['passes'] == before,
                           'passes %s→%s' % (before, lv2[target['id']]['passes']))

    tmp = 'tmp-' + ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
    s, d = call('POST', '/api/me/password', {'current': pw_t, 'next': tmp})
    fails += not check('改密码', s == 200 and d.get('ok'))
    s, d = call('POST', '/api/login', {'username': 'qwenpaw', 'password': pw_t})
    fails += not check('旧密码已失效', s == 401)
    s, d = call('POST', '/api/login', {'username': 'qwenpaw', 'password': tmp})
    fails += not check('新密码可登录', s == 200 and d.get('ok'))
    s, d = call('POST', '/api/me/password', {'current': tmp, 'next': pw_t})
    fails += not check('密码还原', s == 200 and d.get('ok'))
    s, d = call('POST', '/api/login', {'username': 'qwenpaw', 'password': pw_t})
    fails += not check('还原后可登录', s == 200 and d.get('ok'))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


op2 = urllib.request.build_opener(NoRedirect())

def status_no_redirect(path, tries=4):
    """未登录状态取状态码（带重试；网络抖动重试期间可能偶然带不上 cookie 状态也无妨，仅判 302）。"""
    import time
    code, last = None, None
    for _ in range(tries):
        code = None
        try:
            req2 = urllib.request.Request(BASE + path)
            req2.add_header('User-Agent', UA)
            with op2.open(req2) as r:
                code = r.status
        except urllib.error.HTTPError as e:
            code = e.code
        except Exception as e:
            last = e
        if code is not None:
            return code
        time.sleep(3)
    raise last or RuntimeError('no status')

if not MATH_ONLY:
    code = status_no_redirect('/')
    fails += not check('未登录 / → 302', code == 302, 'code=%s' % code)

def fetch_text_retry(path, tries=4):
    import time
    last = None
    for _ in range(tries):
        try:
            s, d = call('GET', path, text=True)
            return s, d
        except Exception as e:
            last = e
            time.sleep(3)
    raise last

if not MATH_ONLY:
    s, d = fetch_text_retry('/cards.html')
    fails += not check('纸卡页(打印/PDF, 门禁内)', s == 200 and '字词过关卡' in d and 'window.print' in d)

    code = status_no_redirect('/cards.html')
    fails += not check('纸卡页未登录 302', code == 302, 'code=%s' % code)

    s, d = fetch_text_retry('/cards-math.html')
    fails += not check('口算口诀卡页(打印/PDF, 门禁内)', s == 200 and '十几减几' in d and 'window.print' in d)

    code = status_no_redirect('/cards-math.html')
    fails += not check('口算口诀卡页未登录 302', code == 302, 'code=%s' % code)

    # ---- P1.5 考卷库 ----
    s, d = fetch_text_retry('/papers.html')
    fails += not check('考卷库页(门禁内)', s == 200 and '考卷库' in d and 'api/papers' in d)

    ptitle = 'verify临时卷-' + ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(6))
    s, d = call('POST', '/api/papers', {'title': ptitle, 'date': '2026-09-01',
                                        'subject': 'math', 'term': '2026秋', 'analysis_md': 'verify 测试卷 **可删**'})
    fails += not check('考卷-新建(含科目/学期)', s == 200 and d.get('ok'))

    s, d = call('GET', '/api/papers?limit=20&offset=0')
    created = next((p for p in d.get('papers', []) if p['title'] == ptitle), None)
    fails += not check('考卷-列表含新卷+字段', s == 200 and created is not None
                       and created.get('subject') == 'math' and created.get('term') == '2026秋',
                       'total=%s has_more=%s' % (d.get('total'), d.get('has_more')))

    s, d = call('GET', '/api/papers?limit=1&offset=0')
    fails += not check('考卷-分页(limit=1)', s == 200 and len(d.get('papers', [])) == 1
                       and d.get('has_more') == (d.get('total', 0) > 1),
                       'total=%s has_more=%s' % (d.get('total'), d.get('has_more')))

    if created:
        pid = created['id']
        s, d = call('PUT', '/api/papers/%d' % pid, {'title': ptitle + '-改', 'date': '2026-09-02',
                                                    'subject': 'chinese', 'term': '2027春', 'analysis_md': None})
        fails += not check('考卷-编辑', s == 200 and d.get('ok'))
        s, d = call('GET', '/api/papers?limit=20&offset=0')
        edited = next((p for p in d.get('papers', []) if p['id'] == pid), None)
        fails += not check('考卷-编辑生效', edited is not None and edited['title'] == ptitle + '-改'
                           and edited['subject'] == 'chinese' and edited['term'] == '2027春')
        s, d = call('DELETE', '/api/papers/%d' % pid)
        fails += not check('考卷-删除', s == 200 and d.get('ok'))
        s, d = call('GET', '/api/papers?limit=20&offset=0')
        fails += not check('考卷-删除生效(列表已无)', not any(p['id'] == pid for p in d.get('papers', [])))
    else:
        fails += 3  # 编辑/删除/确认三项无法执行

    # ---- v13 错题页（wrong.html，2026-10-29 首页入口化；防的是只测总览漏了新页）----
    s, d = fetch_text_retry('/wrong.html')
    fails += not check('错题页(门禁内, 筛选/清除在页)', s == 200 and '错题' in d and 'api/overview' in d and '清除筛选' in d)

    code = status_no_redirect('/wrong.html')
    fails += not check('错题页未登录 302', code == 302, 'code=%s' % code)

    s, d = fetch_text_retry('/')
    fails += not check('总览-导航错题+摘要卡+代录直达(手风琴已拆)', s == 200 and '/wrong.html' in d
                       and 'wrongSummary' in d and '/math.html#record' in d and 'renderWq' not in d)

    def wrong_truth():
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from cf_d1 import find_db, execute_sql
        db = find_db()
        assert db, 'D1 zhixidao-db 不可达（错题总数对账基线取不到）'
        return execute_sql(db, "SELECT COUNT(*) n FROM wrong_questions WHERE is_archived=0 AND student_code='yueyue'")[1][0]['n']
    s, d = call('GET', '/api/overview')
    n_db = wrong_truth()
    fails += not check('错题-总数动态对账(overview vs D1)', s == 200 and d.get('wq_total') == n_db,
                       'api=%s d1=%s' % (d.get('wq_total'), n_db))

# ---- v10 口算记录 ----
MATH_TEST_DATE = '2099-01-01'   # 固定测试日期：重入前先清，物理隔离不碰真数据

def math_truth():
    """D1 直查真数据基线（口径同 worker getStudentId=yueyue，排除测试日期）。
    线上 API 与之对账——代录新场次后无需再改本脚本。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cf_d1 import find_db, execute_sql
    db = find_db()
    assert db, 'D1 zhixidao-db 不可达（对账基线取不到）'
    q = lambda s: execute_sql(db, s)[1]
    sess = q("SELECT COUNT(*) n, SUM(total_questions) t, SUM(correct_count) c FROM math_sessions "
             "WHERE student_id=(SELECT id FROM students WHERE code='yueyue' AND active=1) "
             "AND date != '%s'" % MATH_TEST_DATE)[0]
    marks = q("SELECT COUNT(*) n FROM math_marks "
              "WHERE student_id=(SELECT id FROM students WHERE code='yueyue' AND active=1) "
              "AND date != '%s'" % MATH_TEST_DATE)[0]
    topics = q('SELECT COUNT(*) n FROM math_topics')[0]
    return sess['n'], topics['n'], marks['n'], sess['t'], sess['c']

def math_clean():
    for _ in range(6):
        s, d = call('GET', '/api/math/all')
        ls = [x for x in d.get('sessions', []) if x['date'] == MATH_TEST_DATE]
        lm = [x for x in d.get('marks', []) if x['date'] == MATH_TEST_DATE]
        if not ls and not lm:
            return d
        for x in ls: call('DELETE', '/api/math/sessions/%d' % x['id'])
        for x in lm: call('DELETE', '/api/math/marks/%d' % x['id'])
    raise SystemExit('口算测试数据 4 轮未清零')

TRUTH = math_truth()   # (场次, 题型, 标记, 总题, 总对) —— 动态基线，录新数据自动跟上
d0 = math_clean()
fails += not check('口算-真数据(对账D1: %d场/%d题型/%d标记/%d题/%d对)' % TRUTH,
                   len(d0.get('sessions', [])) == TRUTH[0] and len(d0.get('topics', [])) == TRUTH[1]
                   and len(d0.get('marks', [])) == TRUTH[2]
                   and sum(x['total_questions'] for x in d0['sessions']) == TRUTH[3]
                   and sum(x['correct_count'] for x in d0['sessions']) == TRUTH[4],
                   'api(s=%d t=%d mk=%d) vs d1(s=%d t=%d mk=%d)' % (
                       len(d0.get('sessions', [])), len(d0.get('topics', [])), len(d0.get('marks', [])),
                       TRUTH[0], TRUTH[1], TRUTH[2]))

s, d = call('POST', '/api/math/sessions', {
    'date': MATH_TEST_DATE, 'topic_id': 1, 'duration_seconds': 100, 'total_questions': 22,
    'correct_count': 21, 'note': 'verify-selfcheck',
    'wrong_items': [{'expr': '9+9', 'answer_given': '19', 'answer_correct': '18', 'note': 'verify'}]})
fails += not check('口算-新建(含错题明细)', s == 200 and d.get('ok'))
msid = d.get('id')
s, d = call('GET', '/api/math/all')
mt = [x for x in d.get('sessions', []) if x['date'] == MATH_TEST_DATE]
fails += not check('口算-新场可见+明细随行', len(mt) == 1 and len(mt[0].get('wrong_items', [])) == 1)
s, d = call('PUT', '/api/math/sessions/%s' % msid, {
    'date': MATH_TEST_DATE, 'session_no': 1, 'topic_id': 2, 'duration_seconds': 90,
    'duration_estimated': 1, 'total_questions': 22, 'correct_count': 22,
    'note': 'verify-selfcheck-改', 'wrong_items': []})
fails += not check('口算-编辑', s == 200 and d.get('ok'))
s, d = call('GET', '/api/math/all')
mt = [x for x in d.get('sessions', []) if x['date'] == MATH_TEST_DATE]
fails += not check('口算-编辑生效', mt and mt[0]['topic_id'] == 2
                   and mt[0]['duration_estimated'] == 1 and mt[0]['correct_count'] == 22
                   and len(mt[0].get('wrong_items', [])) == 0)
s, d = call('POST', '/api/math/marks', {'date': MATH_TEST_DATE, 'note': 'verify-selfcheck'})
# 重试副作用容错：POST 成功但响应丢失时重试会撞 UNIQUE 400 —— 以最终可见性为准
fails += not check('口算-标记新增', s == 200 or (s == 400 and '已有标记' in d.get('error', '')),
                   's=%s %s' % (s, d.get('error', '')))
s, d = call('GET', '/api/math/all')
mm = [x for x in d.get('marks', []) if x['date'] == MATH_TEST_DATE]
fails += not check('口算-标记可见', len(mm) == 1)
if msid:
    s, d = call('DELETE', '/api/math/sessions/%s' % msid)
    fails += not check('口算-删除场次', s == 200 and d.get('ok'))
if mm:
    s, d = call('DELETE', '/api/math/marks/%d' % mm[0]['id'])
    fails += not check('口算-删除标记', s == 200 and d.get('ok'))
d0 = math_clean()
fails += not check('口算-清理干净+真数据无损',
                   not [x for x in d0['sessions'] if x['date'] == MATH_TEST_DATE]
                   and len(d0['sessions']) == TRUTH[0] and len(d0['marks']) == TRUTH[2])

s, d = call('GET', '/api/overview')
fails += not check('口算-总览摘要', s == 200 and d.get('math_last') and d.get('math_total') == TRUTH[0],
                   'streak=%s total=%s (d1场次=%s)' % (d.get('math_streak'), d.get('math_total'), TRUTH[0]))

s, d = fetch_text_retry('/math.html')
fails += not check('口算页(门禁内)', s == 200 and '补录一场' in d and '题型对照' in d)
code = status_no_redirect('/math.html')
fails += not check('口算页未登录 302', code == 302, 'code=%s' % code)

if not MATH_ONLY:
    # ---- v11 知识体系（kb）----
    def kb_truth():
        """D1 直查知识树/错题挂载基线（动态对账——建树/补挂/录错题后无需改本脚本）。"""
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from cf_d1 import find_db, execute_sql
        db = find_db()
        assert db, 'D1 zhixidao-db 不可达（kb 对账基线取不到）'
        q = lambda s: execute_sql(db, s)[1]
        m = q("SELECT COUNT(*) n FROM knowledge_nodes WHERE status='active' AND subject='math'")[0]['n']
        c = q("SELECT COUNT(*) n FROM knowledge_nodes WHERE status='active' AND subject='chinese'")[0]['n']
        hang = q("SELECT COUNT(*) n FROM wrong_questions w JOIN knowledge_nodes n ON n.id=w.node_id "
                 "WHERE w.is_archived=0 AND w.student_code='yueyue' AND n.status='active'")[0]['n']
        total = q("SELECT COUNT(*) n FROM wrong_questions WHERE is_archived=0 AND student_code='yueyue'")[0]['n']
        recite = q("SELECT COUNT(*) n FROM wrong_questions w JOIN knowledge_nodes n ON n.id=w.node_id "
                   "WHERE w.is_archived=0 AND w.student_code='yueyue' AND n.name='背诵积累'")[0]['n']
        return m, c, hang, total, recite

    KB = kb_truth()   # (数学节点, 语文节点, 挂载错题, 错题总数, 背诵积累挂载数)

    s, d = call('GET', '/api/kb/nodes?subject=math&limit=500')
    fails += not check('kb-树真数据-数学(%d节点,对账D1)' % KB[0],
                       s == 200 and len(d.get('nodes', [])) == KB[0], 'api=%s' % len(d.get('nodes', [])))
    s, d = call('GET', '/api/kb/nodes?subject=chinese&limit=500')
    fails += not check('kb-树真数据-语文(%d节点,对账D1)' % KB[1],
                       s == 200 and len(d.get('nodes', [])) == KB[1], 'api=%s' % len(d.get('nodes', [])))

    s, d = call('GET', '/api/overview')
    wq = d.get('wrong_questions', [])
    # 2026-10-29 起新契约：无对应知识点的错题有意挂 NULL（如"分类与整理"，树里暂无该节点），
    # kp_names 仍进弱项榜——不再要求 100% 挂载；未挂题必须带有效 kp_names（不上树但不失踪）
    hang_api = sum(1 for w in wq if w.get('node_id'))
    unhang = [w for w in wq if not w.get('node_id')]
    unhang_kp_ok = all((w.get('kp_names') or '') not in ('', '[]') for w in unhang)
    fails += not check('kb-错题挂载(overview对账D1 %d/%d;未挂须有kp_names)' % (hang_api, KB[3]),
                       s == 200 and hang_api == KB[2] and hang_api + len(unhang) == KB[3] and unhang_kp_ok,
                       'api挂载=%s D1挂载=%s 未挂=%d' % (hang_api, KB[2], len(unhang)))
    fails += not check('kb-弱项榜(实时聚合有数据)',
                       isinstance(d.get('weak_points'), list) and len(d['weak_points']) >= 1,
                       'n=%s' % len(d.get('weak_points', [])))

    s, d = call('GET', '/api/assess?limit=500')
    rows = d.get('nodes', [])
    lamps_ok = all(r.get('lamp') in (-1, 0, 1, 2) for r in rows)
    recite = next((r for r in rows if r['name'] == '背诵积累'), None)
    cond_recite = (recite is not None and recite['lamp'] != -1) if KB[4] > 0 else True
    fails += not check('kb-assess(灯值域+覆盖, %d节点)' % len(rows),
                       s == 200 and len(rows) >= KB[0] + KB[1] and lamps_ok and cond_recite,
                       '背诵积累lamp=%s' % (recite or {}).get('lamp'))

    # 测试节点全链（用后 retire 清理，无物理删除）
    s, d = call('POST', '/api/kb/nodes', {'name': 'TEST-verify-kb', 'level': 1, 'subject': 'math', 'sort': 9999})
    tn = (d.get('ids') or [None])[0]
    fails += not check('kb-建测试节点', s == 200 and tn, 'st=%s' % s)
    s, d = call('GET', '/api/kb/nodes?parent_id=null&subject=math&limit=500')
    fails += not check('kb-测试节点懒加载可见', s == 200 and any(n['id'] == tn for n in d.get('nodes', [])))
    s, d = call('POST', '/api/kb/questions', {'node_id': tn, 'stem': 'verify', 'tags': 'bad'})
    fails += not check('kb-questions tags非数组400(审核fix1回归)', s == 400, 'st=%s' % s)
    s, d = call('DELETE', '/api/kb/nodes/%d' % tn)
    fails += not check('kb-无DELETE端点(软删除契约)', s == 404, 'st=%s' % s)

    # 考卷逐题外键联动删除回归（审核fix2）：带逐题的考卷必须能删掉
    s, d = call('POST', '/api/papers', {'title': 'TEST-verify-kb卷', 'subject': 'math', 'term': 'verify'})
    s, d = call('GET', '/api/papers?limit=50')
    pid = next((p['id'] for p in d.get('papers', []) if p['title'] == 'TEST-verify-kb卷'), None)
    s1, _ = call('POST', '/api/papers/%s/items' % pid, [{'qno': '1', 'correct': 1}])
    s2, _ = call('DELETE', '/api/papers/%s' % pid)
    fails += not check('kb-考卷删除外键联动(审核fix2回归)', s1 == 200 and s2 == 200, 'items=%s del=%s' % (s1, s2))

    s, d = call('PUT', '/api/kb/nodes/%d' % tn, {'status': 'retired'})
    s, d = call('GET', '/api/kb/nodes?subject=math&limit=500')
    fails += not check('kb-retire后active不可见+测试清理', s == 200 and not any(n['id'] == tn for n in d.get('nodes', [])))

    # ---- v11.1 打印中心 ----
    s, d = fetch_text_retry('/print.html')
    fails += not check('打印中心页(清单+生成器)',
                       s == 200 and '打印素材' in d and '乘法口诀表' in d and '口算练习纸生成器' in d)
    s, d = fetch_text_retry('/cards-koujue99.html')
    fails += not check('乘法口诀表卡(门禁内+打印按钮)',
                       s == 200 and '乘法口诀表' in d and 'window.print' in d)
    code = status_no_redirect('/cards-koujue99.html')
    fails += not check('口诀表卡未登录 302', code == 302, 'code=%s' % code)

    # ---- v11.2 打印中心三件（田字格/查字典/时钟生成器） ----
    s, d = fetch_text_retry('/print.html')
    fails += not check('v11.2 打印中心清单含两新卡+时钟生成器',
                       s == 200 and '田字格练习纸' in d and '查字典练习卡' in d and '时钟练习纸生成器' in d)
    s, d = fetch_text_retry('/cards-tianzige.html')
    fails += not check('田字格练习纸卡(门禁内+打印按钮)',
                       s == 200 and '田字格练习纸' in d and 'window.print' in d)
    code = status_no_redirect('/cards-tianzige.html')
    fails += not check('田字格卡未登录 302', code == 302, 'code=%s' % code)
    s, d = fetch_text_retry('/cards-zidian.html')
    fails += not check('查字典练习卡(门禁内+两查法+打印按钮)',
                       s == 200 and '查字典练习卡' in d and '音序查字法' in d and '部首查字法' in d and '再查几画' in d and 'window.print' in d)
    fails += not check('查字典卡页码留空+字典为准注记',
                       '<td>C</td>' in d and ('页码以你手头的字典为准' in d or '以所用字典为准' in d))
    code = status_no_redirect('/cards-zidian.html')
    fails += not check('查字典卡未登录 302', code == 302, 'code=%s' % code)



print('\n结果: %s（失败 %d 项）' % ('全部通过' if fails == 0 else '存在失败', fails))

# 改密码测试会清理同账号其他会话（含 pw.py 部署核对的验证会话）→ 结束后自动补注
# （--math-only 模式没跑改密码链，无需补注）
if not MATH_ONLY:
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'seed_verify_session.py')],
            capture_output=True, text=True, timeout=90)
        if r.returncode == 0:
            print('验证会话已补注:', (r.stdout.strip().splitlines() or [''])[-1])
        else:
            print('⚠️ 验证会话补注失败 rc=%d %s' % (r.returncode, (r.stderr or '').strip()[:200]))
            fails += 1
    except Exception as e:
        print('⚠️ 验证会话补注异常:', e)
        fails += 1

sys.exit(1 if fails else 0)
