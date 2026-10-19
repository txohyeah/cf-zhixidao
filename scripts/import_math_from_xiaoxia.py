#!/usr/bin/env python3
"""小虾站口算 JSON → zhixidao D1 导入。
纪律：对账断言前置（场次/题数/对数/秒数与导出概览一致才写库）；
显式 id 分配（ext_key→id 固定映射，INSERT OR IGNORE 幂等可重跑）；
导入后 SELECT 复验四指标 + 每题型场次分布。
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
from cf_d1 import find_db, execute_sql

BASE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(os.path.dirname(os.path.dirname(BASE)))  # scripts→zhixidao→projects→workspace 根
SRC = os.path.join(WS, 'temp_script/xiaoxia_math_mail',
                   'mail0_uid8_玥玥口算记录_全量_20260910-20261019.json')

def sq(s):
    """SQL 字符串内插：单引号转义。"""
    if s is None: return 'NULL'
    return "'" + str(s).replace("'", "''") + "'"

d = json.load(open(SRC))
recs = d['records']

# ---------- 前置对账 ----------
assert len(recs) == 106, f'场次 {len(recs)} != 106'
tot = sum(r['total'] for r in recs); cor = sum(r['correct'] for r in recs)
dur = sum(r['duration_sec'] for r in recs)
assert tot == 2398 and cor == 2351 and dur == 19673, (tot, cor, dur)
keys = [r['ext_key'] for r in recs]
assert len(keys) == len(set(keys)), 'ext_key 重复'
for r in recs:
    assert r['wrong'] == len(r['wrongItems']), r['ext_key']
    assert r['correct'] == r['total'] - r['wrong'], r['ext_key']
print('[对账] 源数据断言全过：106 场 / 2398 题 / 2351 对 / 19673s')

db = find_db()
sid_row = execute_sql(db, "SELECT id FROM students WHERE code='yueyue' AND active=1")[1]
SID = sid_row[0]['id']
topics = execute_sql(db, 'SELECT id, name FROM math_topics')[1]
TMAP = {t['name']: t['id'] for t in topics}
assert len(TMAP) == 6, TMAP

# ext_key → 显式 id（按 date, session_no 排序保证稳定）
recs_sorted = sorted(recs, key=lambda r: (r['date'], int(r['ext_key'].rsplit('-', 1)[1])))
IDMAP = {}
for i, r in enumerate(recs_sorted, 1):
    IDMAP[r['ext_key']] = i

# ---------- 生成语句（幂等 OR IGNORE） ----------
sess_stmts, wi_rows, mark_rows = [], [], []
for r in recs_sorted:
    est = 1 if ('未记录实际用时' in (r.get('note') or '') or '估算' in (r.get('note') or '')[:30]) else 0
    tid = TMAP.get(r['category'])
    assert tid, f"未知题型: {r['category']}"
    sess_stmts.append(
        f"INSERT OR IGNORE INTO math_sessions (id, student_id, date, session_no, topic_id, "
        f"duration_seconds, duration_estimated, total_questions, correct_count, ext_key, note, source) VALUES ("
        f"{IDMAP[r['ext_key']]}, {SID}, {sq(r['date'])}, {int(r['ext_key'].rsplit('-',1)[1])}, {tid}, "
        f"{r['duration_sec']}, {est}, {r['total']}, {r['correct']}, {sq(r['ext_key'])}, {sq(r['note'])}, 'import_xiaoxia')")
    for w in r['wrongItems']:
        wi_rows.append(f"({IDMAP[r['ext_key']]}, {sq(w['expr'])}, {sq(w.get('ans'))}, {sq(w.get('correct'))}, NULL)")

for m in d['marks']:
    mark_rows.append(f"({SID}, {sq(m['date'])}, {sq(m['note'])})")

def run_batches(rows, tmpl, batch=90, label=''):
    n = 0
    for i in range(0, len(rows), batch):
        chunk = rows[i:i+batch]
        stmt = tmpl + ','.join(chunk)
        ok, _r, meta, err = execute_sql(db, stmt)
        if not ok:
            print(f'[FAIL] {label} 批 {i}:', json.dumps(err, ensure_ascii=False)[:300]); raise SystemExit(1)
        n += meta.get('rows_changed', 0)
    print(f'[导入] {label}: {len(rows)} 行（written {n}）')

run_batches(sess_stmts, '', 1, '场次')  # 每条一个语句（VALUES 单行）
run_batches(wi_rows, 'INSERT OR IGNORE INTO math_wrong_items (session_id, expr, answer_given, answer_correct, note) VALUES ', 90, '错题明细')
run_batches(mark_rows, 'INSERT OR IGNORE INTO math_marks (student_id, date, note) VALUES ', 90, '日历标记')

# ---------- 导入后复验 ----------
q = lambda s: execute_sql(db, s)[1]
c = q('SELECT COUNT(*) n, SUM(total_questions) t, SUM(correct_count) c, SUM(duration_seconds) d FROM math_sessions')[0]
assert c['n'] == 106 and c['t'] == 2398 and c['c'] == 2351 and c['d'] == 19673, c
wi = q('SELECT COUNT(*) n FROM math_wrong_items')[0]['n']
mk = q('SELECT COUNT(*) n FROM math_marks')[0]['n']
est = q('SELECT COUNT(*) n FROM math_sessions WHERE duration_estimated=1')[0]['n']
bytopic = q('SELECT t.name, COUNT(s.id) n FROM math_topics t LEFT JOIN math_sessions s ON s.topic_id=t.id GROUP BY t.id ORDER BY t.sort_no')
print('[复验] 场次=106 总题=2398 对=2351 秒=19673 ✓')
print(f'[复验] 错题明细={wi}（源 47）日历标记={mk}（源 {len(d["marks"])}）估算场={est}')
assert wi == 47 and mk == len(d['marks'])
src_bytopic = {}
for r in recs: src_bytopic[r['category']] = src_bytopic.get(r['category'], 0) + 1
for row in bytopic:
    assert src_bytopic.get(row['name'], 0) == row['n'], row
    print(f"  {row['name']}: {row['n']} 场 ✓")
print('[完成] 导入+对账全部通过')
