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
    s, d = call('GET', '/api/overview')
    lv = d.get('levels', [])
    wq = d.get('wrong_questions', [])
    wps = d.get('weak_points', [])
    fails += not check('overview(13关+1考卷+错题副本)',
                       s == 200 and len(lv) == 13 and len(d.get('papers', [])) == 1 and len(wq) >= 30 and len(wps) >= 3,
                       'levels=%d papers=%d wq=%d weak=%d streak=%s'
                       % (len(lv), len(d.get('papers', [])), len(wq), len(wps), d.get('streak')))

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

# ---- v10 口算记录 ----
MATH_TEST_DATE = '2099-01-01'   # 固定测试日期：重入前先清，物理隔离不碰真数据

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

d0 = math_clean()
fails += not check('口算-真数据(106场/6题型/1标记/2398题/2351对)',
                   len(d0.get('sessions', [])) == 106 and len(d0.get('topics', [])) == 6
                   and len(d0.get('marks', [])) == 1
                   and sum(x['total_questions'] for x in d0['sessions']) == 2398
                   and sum(x['correct_count'] for x in d0['sessions']) == 2351,
                   's=%d t=%d mk=%d' % (len(d0.get('sessions', [])), len(d0.get('topics', [])), len(d0.get('marks', []))))

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
                   and len(d0['sessions']) == 106 and len(d0['marks']) == 1)

s, d = call('GET', '/api/overview')
fails += not check('口算-总览摘要', s == 200 and d.get('math_last') and d.get('math_total') == 106,
                   'streak=%s total=%s' % (d.get('math_streak'), d.get('math_total')))

s, d = fetch_text_retry('/math.html')
fails += not check('口算页(门禁内)', s == 200 and '补录一场' in d and '题型对照' in d)
code = status_no_redirect('/math.html')
fails += not check('口算页未登录 302', code == 302, 'code=%s' % code)

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
