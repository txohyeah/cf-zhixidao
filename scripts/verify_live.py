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
import string
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else 'https://zhixidao.pages.dev').rstrip('/')
# scripts/ → zhixidao/ → projects/ → workspace 根
WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SECRETS = os.path.join(WORKSPACE, '.secrets')
# Cloudflare 会 403 掉 Python-urllib 默认 UA，必须带浏览器 UA
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36'

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(method, path, body=None, op=None, text=False):
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


def check(name, ok, detail=''):
    print(('✓' if ok else '✗'), name, detail)
    return ok


pw_t = open(os.path.join(SECRETS, 'zhixidao_qwenpaw')).read().strip()
fails = 0

s, d = call('GET', '/api/health')
fails += not check('health', s == 200 and d.get('ok'))

s, d = call('POST', '/api/login', {'username': 'qwenpaw', 'password': 'definitely-wrong-xyz'})
fails += not check('错密码 401', s == 401)

s, d = call('POST', '/api/login', {'username': 'qwenpaw', 'password': pw_t})
fails += not check('登录 qwenpaw', s == 200 and d.get('ok') and d.get('role') == 'parent')

s, d = call('GET', '/api/me')
fails += not check('me', s == 200 and d.get('authed') and d.get('username') == 'qwenpaw')

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
code = None
try:
    req2 = urllib.request.Request(BASE + '/')
    req2.add_header('User-Agent', UA)
    with op2.open(req2) as r:
        code = r.status
except urllib.error.HTTPError as e:
    code = e.code
except Exception:
    pass
fails += not check('未登录 / → 302', code == 302, 'code=%s' % code)

s, d = call('GET', '/cards.html', text=True)
fails += not check('纸卡页(打印/PDF, 门禁内)', s == 200 and '字词过关卡' in d and 'window.print' in d)

code = None
try:
    req2 = urllib.request.Request(BASE + '/cards.html')
    req2.add_header('User-Agent', UA)
    with op2.open(req2) as r:
        code = r.status
except urllib.error.HTTPError as e:
    code = e.code
except Exception:
    pass
fails += not check('纸卡页未登录 302', code == 302, 'code=%s' % code)

# ---- P1.5 考卷库 ----
s, d = call('GET', '/papers.html', text=True)
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

print('\n结果: %s（失败 %d 项）' % ('全部通过' if fails == 0 else '存在失败', fails))

# 改密码测试会清理同账号其他会话（含 pw.py 部署核对的验证会话）→ 结束后自动补注
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
