#!/usr/bin/env python3
"""给 pw.py 的部署核对注入验证会话（可重复执行，失效就重跑）。
会话账号：qwenpaw（测试账号，专用；密码在 .secrets/zhixidao_qwenpaw，不回显）。
产出：workspace/.secrets/verify-cookie-zhixidao.txt（600，内容 `zhixidao_auth=<token>`）。
说明：改密码等操作会清理同账号其他会话，导致 cookie 失效（v3 部署时踩过）；
     重跑本脚本即可恢复 pw.py 自动核对能力。
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.request
import uuid

WS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import cf_d1  # noqa: E402

COOKIE_FILE = os.path.join(WS, '.secrets', 'verify-cookie-zhixidao.txt')
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36'


def main():
    pw = open(os.path.join(WS, '.secrets', 'zhixidao_qwenpaw')).read().strip()
    db = cf_d1.find_db()
    ok, rows, _, errs = cf_d1.execute_sql(db, "SELECT id FROM users WHERE username='qwenpaw'")
    assert ok and rows, errs or 'qwenpaw 用户不存在'
    uid = rows[0]['id']

    token = str(uuid.uuid4())
    exp = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    cf_d1.execute_sql(db, "DELETE FROM sessions WHERE token LIKE 'verify-%'")
    # 旧的注入会话（若有）按 expires_at 接近 30 天且非 verify 前缀不好区分，直接全清 qwenpaw 会话后重注
    cf_d1.execute_sql(db, "DELETE FROM sessions WHERE user_id = %d" % uid)
    ok, _, _, errs = cf_d1.execute_sql(
        db, "INSERT INTO sessions (token, user_id, expires_at) VALUES ('%s', %d, '%s')" % (token, uid, exp))
    assert ok, errs

    with open(COOKIE_FILE, 'w') as f:
        f.write('zhixidao_auth=%s\n' % token)
    os.chmod(COOKIE_FILE, 0o600)

    # 线上冒烟：带 cookie 请求 / 应 200
    req = urllib.request.Request('https://zhixidao.pages.dev/', headers={'Cookie': 'zhixidao_auth=' + token, 'User-Agent': UA})
    try:
        with urllib.request.urlopen(req) as r:
            print('验证会话已注入并冒烟通过（/ → %d）' % r.status)
    except urllib.error.HTTPError as e:
        raise SystemExit('冒烟失败：/ → %d（部署未生效或会话异常）' % e.code)


if __name__ == '__main__':
    main()
