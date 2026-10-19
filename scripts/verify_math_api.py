#!/usr/bin/env python3
"""口算 API 写链路冒烟（线上）：POST 测试场 → GET 验证 → PUT → DELETE 清理 → 确认清零。
凭证：qwenpaw 测试账号（不碰 baba/mama）。幂等：测试日期用 2099-01-01，删除收尾。
"""
import json, ssl, time, urllib.request

try:
    _CTX = ssl.create_default_context(cafile=ssl.get_default_verify_paths().cafile)
except Exception:
    _CTX = None
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
BASE = 'https://zhixidao.pages.dev'
TEST_DATE = '2099-01-01'

def req(method, path, body=None, cookie=None, retries=3):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header('User-Agent', UA)
    r.add_header('Content-Type', 'application/json')
    if cookie: r.add_header('Cookie', cookie)
    last = None
    for i in range(retries + 2):
        try:
            with urllib.request.urlopen(r, context=_CTX, timeout=30) as resp:
                return resp.status, json.loads(resp.read().decode()), resp.headers
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode()), e.headers
            except Exception:
                return e.code, {'error': 'non-json response'}, e.headers
        except Exception as e:
            last = e; time.sleep(3 + i * 3)
    raise last

# 1) 登录 qwenpaw
pw = open('/root/.qwenpaw/workspaces/default/.secrets/zhixidao_qwenpaw').read().strip()
st, login, hh = req('POST', '/api/login', {'username': 'qwenpaw', 'password': pw})
assert st == 200 and login.get('ok'), (st, login)
sc = hh.get('Set-Cookie') or ''
ck = sc.split(';')[0]
assert ck.startswith('zhixidao_auth='), sc[:80]

# 0) 幂等守卫：清掉残留测试数据（pages.dev 抖动 DELETE 可能静默失败 → 重试到清零）
def clean_test_date(ck, rounds=6):
    for _ in range(rounds):
        st, d, _h = req('GET', '/api/math/all', None, ck)
        assert st == 200 and d.get('ok'), (st, str(d)[:100])
        left_s = [x for x in d['sessions'] if x['date'] == TEST_DATE]
        left_m = [x for x in d['marks'] if x['date'] == TEST_DATE]
        if not left_s and not left_m:
            return d
        for s in left_s:
            st2, d2, _ = req('DELETE', f"/api/math/sessions/{s['id']}", None, ck)
            print('清测试场', s['id'], st2, d2.get('ok'))
        for m in left_m:
            st2, d2, _ = req('DELETE', f"/api/math/marks/{m['id']}", None, ck)
            print('清标记', m['id'], st2, d2.get('ok'))
        time.sleep(2)
    raise SystemExit('测试数据 6 轮未清零，人工检查')

d = clean_test_date(ck)

fails = []
def check(name, cond, detail=''):
    print(('✓' if cond else '✗ FAIL'), name, detail)
    if not cond: fails.append(name)

# 2) 测试场不存在时创建
st, d, _h = req('POST', '/api/math/sessions', {
    'date': TEST_DATE, 'topic_id': 1, 'duration_seconds': 100, 'total_questions': 22,
    'correct_count': 21, 'note': 'verify-selfcheck 测试场', 'wrong_items': [
        {'expr': '9+9', 'answer_given': '19', 'answer_correct': '18', 'note': '进位多1'}]}, ck)
check('POST 创建', st == 200 and d.get('ok'), str(d)[:80])
sid = d.get('id')

# 3) GET 验证存在
st, d, _h = req('GET', '/api/math/all', None, ck)
m = [s for s in d['sessions'] if s['date'] == TEST_DATE]
check('GET 出现测试场', st == 200 and len(m) == 1)
check('错题明细随场返回', m and len(m[0]['wrong_items']) == 1)

# 4) PUT 编辑
st, d, _h = req('PUT', f'/api/math/sessions/{sid}', {
    'date': TEST_DATE, 'session_no': 1, 'topic_id': 2, 'duration_seconds': 90,
    'duration_estimated': 1, 'total_questions': 22, 'correct_count': 22,
    'note': 'verify-selfcheck 编辑后', 'wrong_items': []}, ck)
check('PUT 编辑', st == 200 and d.get('ok'), str(d)[:80])
st, d, _h = req('GET', '/api/math/all', None, ck)
m = [s for s in d['sessions'] if s['date'] == TEST_DATE]
check('编辑生效（题型2/估算/22对/明细清空）',
      m and m[0]['topic_id'] == 2 and m[0]['duration_estimated'] == 1
      and m[0]['correct_count'] == 22 and len(m[0]['wrong_items']) == 0)

# 5) marks 写读删
st, d, _h = req('POST', '/api/math/marks', {'date': TEST_DATE, 'note': 'verify-selfcheck 标记'}, ck)
check('POST 标记', st == 200 and d.get('ok'), str(d)[:60])
st, d, _h = req('GET', '/api/math/all', None, ck)
mkid = [x for x in d['marks'] if x['date'] == TEST_DATE]
check('标记可见', len(mkid) == 1)

# 6) 清理
if sid:
    st, d, _h = req('DELETE', f'/api/math/sessions/{sid}', None, ck)
    check('DELETE 测试场', st == 200 and d.get('ok'))
if mkid:
    st, d, _h = req('DELETE', f"/api/math/marks/{mkid[0]['id']}", None, ck)
    check('DELETE 标记', st == 200 and d.get('ok'))

st, d, _h = req('GET', '/api/math/all', None, ck)
left_s = [s for s in d['sessions'] if s['date'] == TEST_DATE]
left_m = [m for m in d['marks'] if m['date'] == TEST_DATE]
check('测试数据清零', not left_s and not left_m, f'剩 {len(left_s)} 场 {len(left_m)} 标记')
check('真数据未受影响', len(d['sessions']) == 106 and len(d['marks']) == 1)

# 7) overview 摘要
st, d, _h = req('GET', '/api/overview', None, ck)
check('overview 口算摘要', st == 200 and d.get('math_last') and d.get('math_total') == 106,
      f"math_streak={d.get('math_streak')} math_total={d.get('math_total')}")

print()
print('FAIL:', fails if fails else '无 · 全绿')
