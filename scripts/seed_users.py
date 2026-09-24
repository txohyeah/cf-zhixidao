#!/usr/bin/env python3
"""智习岛用户种子 SQL（baba + mama + qwenpaw，role=parent）。
密码来源：workspace/.secrets/zhixidao_pass_baba / _mama / zhixidao_qwenpaw（绝不回显/落日志）。
输出：data/seed_users.sql（仅含 PBKDF2 哈希，无明文）。格式与 worker 一致：pbkdf2$100000$salt_b64$hash_b64
"""
import base64
import hashlib
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(os.path.dirname(ROOT))
ITER = 100000
KEYLEN = 32


def hash_pass(pw: str) -> str:
    salt = os.urandom(16)
    bits = hashlib.pbkdf2_hmac('sha256', pw.encode(), salt, ITER, KEYLEN)
    return 'pbkdf2$%d$%s$%s' % (ITER, base64.b64encode(salt).decode(), base64.b64encode(bits).decode())


def sqlq(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def main():
    rows = []
    for who, display in [('baba', '爸爸'), ('mama', '妈妈'), ('qwenpaw', '助教')]:
        pw = open(os.path.join(WORKSPACE, '.secrets', 'zhixidao_pass_%s' % who)).read().strip()
        if len(pw) < 6:
            raise SystemExit('%s 密码文件异常（<6 位）' % who)
        rows.append((who, hash_pass(pw), display))
    lines = [
        '-- 用户种子（哈希含随机盐；重跑前会先删同名单。注意：重跑会使所有会话失效）',
        "DELETE FROM users WHERE username IN ('baba', 'mama', 'qwenpaw');",
    ]
    for who, h, display in rows:
        lines.append(
            "INSERT INTO users (username, pw_hash, role, display_name, active, created_at) "
            "VALUES (%s, %s, 'parent', %s, 1, '2026-09-24T00:00:00Z');" % (sqlq(who), sqlq(h), sqlq(display))
        )
    out = os.path.join(ROOT, 'data', 'seed_users.sql')
    with open(out, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print('已生成', out, '（密码未回显）')


if __name__ == '__main__':
    main()
