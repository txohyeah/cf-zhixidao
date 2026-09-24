#!/usr/bin/env python3
"""cuoti 错题工作库 → 智习岛 D1 错题展示副本（单向同步，全量替换）。
源头：~/.cuoti/cuoti.db（只读模式打开，绝不写源库）。
隐私红线：只迁 STUDENT_MAP 映射表内的题；不带姓名/学校/班级/alias；
测试学生（alias=test）数据一律不迁；题图不上云（P3 决策：隐私+存储）。
口径：wrong_count = practice_records.result='incorrect' 次数；顽固题 = 近 30 天错 ≥3 次。
用法：python3 scripts/sync_cuoti.py [--dry-run]
"""
import datetime
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cf_d1

STUDENT_MAP = {'joy': 'yueyue'}  # cuoti alias → 智习岛 student code
STUBBORN_DAYS = 30
STUBBORN_MIN = 3


def q1(v):
    """SQL 值转义：None→NULL，int→数字，str→单引号转义。"""
    if v is None:
        return 'NULL'
    if isinstance(v, int):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def main():
    dry = '--dry-run' in sys.argv
    src = os.path.expanduser('~/.cuoti/cuoti.db')
    if not os.path.exists(src):
        raise SystemExit('源库不存在: %s' % src)
    conn = sqlite3.connect('file:%s?mode=ro' % src, uri=True)
    conn.row_factory = sqlite3.Row

    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=STUBBORN_DAYS)).strftime('%Y-%m-%d')

    db = cf_d1.find_db()
    total_wq = total_wp = 0
    for r in conn.execute("SELECT id, alias FROM students WHERE is_deleted = 0"):
        alias, cuoti_sid = r['alias'], r['id']
        if alias not in STUDENT_MAP:
            print('跳过学生 alias=%s（不在映射表）' % alias)
            continue
        code = STUDENT_MAP[alias]

        rows = conn.execute(
            """SELECT q.*,
              (SELECT COUNT(*) FROM practice_records p WHERE p.question_id=q.id AND p.result='incorrect' AND substr(p.practiced_at,1,10) >= ?) AS wrong_30d,
              (SELECT COUNT(*) FROM practice_records p WHERE p.question_id=q.id AND p.result='incorrect') AS wrong_count,
              (SELECT COUNT(*) FROM practice_records p WHERE p.question_id=q.id AND p.result='correct')   AS correct_count,
              (SELECT MAX(p.practiced_at) FROM practice_records p WHERE p.question_id=q.id) AS last_practice_at,
              (SELECT MAX(p.practiced_at) FROM practice_records p WHERE p.question_id=q.id AND p.result='incorrect') AS last_wrong_at
            FROM questions q WHERE q.student_id = ?""",
            (cutoff, cuoti_sid)).fetchall()
        kp_map = {}
        for r in conn.execute(
            """SELECT qkp.question_id, kp.code, kp.name
               FROM question_knowledge_points qkp
               JOIN questions q ON q.id = qkp.question_id
               JOIN knowledge_points kp ON kp.code = qkp.knowledge_point_code
               WHERE q.student_id = ?""", (cuoti_sid,)):
            kp_map.setdefault(r['question_id'], []).append((r['code'], r['name']))

        wq_rows = []
        agg = {}
        for q in rows:
            stubborn = 1 if q['wrong_30d'] >= STUBBORN_MIN else 0
            kps = kp_map.get(q['id'], [])
            wq_rows.append((
                q['id'], code, q['subject_code'], q['title'], q['stem'], q['answer'], q['analysis'],
                q['question_type'], q['difficulty'] or 1, q['status'], q['is_archived'] or 0,
                q['wrong_count'], q['correct_count'], q['last_wrong_at'], q['last_practice_at'],
                q['created_at'],
                json.dumps([k for k, _ in kps], ensure_ascii=False),
                json.dumps([n for _, n in kps], ensure_ascii=False),
                stubborn, now))
            for kcode, kname in kps:
                a = agg.setdefault(kcode, {'name': kname, 'subject': q['subject_code'],
                                           'qn': 0, 'wrong': 0, 'last_wrong': None, 'stub': 0})
                a['qn'] += 1
                a['wrong'] += q['wrong_count'] or 0
                a['stub'] += stubborn
                if q['last_wrong_at'] and (not a['last_wrong'] or q['last_wrong_at'] > a['last_wrong']):
                    a['last_wrong'] = q['last_wrong_at']
        wp_rows = [(code, k, v['name'], v['subject'], v['qn'], v['wrong'], v['last_wrong'], v['stub'], now)
                   for k, v in agg.items()]

        stub_n = sum(r[18] for r in wq_rows)
        print('[%s] 源题 %d（顽固 %d）、弱项 %d' % (code, len(wq_rows), stub_n, len(wp_rows)))
        if dry:
            continue

        cf_d1.execute_sql(db, "DELETE FROM wrong_questions WHERE student_code = %s" % q1(code))
        for r in wq_rows:
            sql = ("INSERT INTO wrong_questions (id,student_code,subject_code,title,stem,answer,analysis,"
                   "question_type,difficulty,status,is_archived,wrong_count,correct_count,last_wrong_at,"
                   "last_practice_at,created_at,kp_codes,kp_names,stubborn,sync_at) VALUES (%s)"
                   % ','.join(q1(v) for v in r))
            ok, _, _, errs = cf_d1.execute_sql(db, sql)
            if not ok:
                raise SystemExit('写错题失败: %s' % json.dumps(errs, ensure_ascii=False)[:300])
        cf_d1.execute_sql(db, "DELETE FROM weak_points WHERE student_code = %s" % q1(code))
        for r in wp_rows:
            sql = ("INSERT INTO weak_points (student_code,kp_code,kp_name,subject_code,question_count,"
                   "wrong_count,last_wrong_at,stubborn_count,sync_at) VALUES (%s)" % ','.join(q1(v) for v in r))
            ok, _, _, errs = cf_d1.execute_sql(db, sql)
            if not ok:
                raise SystemExit('写弱项失败: %s' % json.dumps(errs, ensure_ascii=False)[:300])
        total_wq += len(wq_rows)
        total_wp += len(wp_rows)

    if not dry:
        print('D1 写入完成：错题 %d 行、弱项 %d 行（全量替换，sync_at=%s）' % (total_wq, total_wp, now))


if __name__ == '__main__':
    main()
