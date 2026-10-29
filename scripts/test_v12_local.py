#!/usr/bin/env python3
"""本地 SQLite + Worker 双学生冒烟；不访问线上，也不使用实际账号。"""
import json, os, sqlite3, subprocess, sys, tempfile, threading, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if len(sys.argv) == 3 and sys.argv[1] == '--bridge':
    db = sqlite3.connect(sys.argv[2]); db.row_factory = sqlite3.Row; db.execute('PRAGMA foreign_keys=ON')
    ops = json.load(sys.stdin); out = []
    try:
        for op in ops:
            c = db.execute(op['sql'], op['args']); rows = [dict(x) for x in c.fetchall()] if c.description else []
            out.append({'results': rows, 'meta': {'last_row_id': c.lastrowid, 'changes': max(c.rowcount, 0)}})
        db.commit(); print(json.dumps(out))
    except Exception as e:
        db.rollback(); print(str(e), file=sys.stderr); sys.exit(1)
    sys.exit(0)
with tempfile.TemporaryDirectory() as td:
    dbfile = os.path.join(td, 'test.sqlite'); db = sqlite3.connect(dbfile); db.execute('PRAGMA foreign_keys=ON')
    db.executescript((ROOT/'schema.sql').read_text()); db.executescript((ROOT/'data/routine_schema_v12.sql').read_text())
    db.executemany('INSERT INTO students(id,code,display_name,active) VALUES(?,?,?,?)', [(1,'yueyue','玥玥',1),(2,'second','二宝',1),(3,'inactive','停用',0)])
    db.executemany('INSERT INTO users(id,username,pw_hash,role) VALUES(?,?,?,?)',[(1,'parent','test','parent'),(2,'second','test','kid')])
    db.executemany('INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)',[('p',1,'2999-01-01'),('k',2,'2999-01-01')])
    db.executescript((ROOT/'data/seed_routine_v12.sql').read_text()); db.executescript((ROOT/'data/seed_routine_v12.sql').read_text())
    db.execute("INSERT INTO routines(student_id,title,version,effective_from) VALUES(2,'二宝流程',1,'2026-01-01')")
    db.execute("INSERT INTO routine_steps(routine_id,seq,name) SELECT id,1,'二宝任务' FROM routines WHERE student_id=2")
    db.executemany('INSERT INTO papers(student_id,date,title) VALUES(?,?,?)',[(1,'2026-01-01','甲卷'),(2,'2026-01-01','乙卷')])
    db.executemany('INSERT INTO wrong_questions(id,student_code,subject_code,status) VALUES(?,?,?,?)',[('a','yueyue','math','new'),('b','second','math','mastered')])
    db.executemany('INSERT INTO levels(id,student_id,kind,name) VALUES(?,?,?,?)',[(1,1,'word_write','甲关'),(2,2,'word_write','乙关')])
    db.execute("INSERT INTO math_topics(id,name) VALUES(1,'测试题型')")
    db.executemany('INSERT INTO math_sessions(id,student_id,date,topic_id,total_questions,correct_count) VALUES(?,?,?,?,?,?)',[(1,1,'2026-01-01',1,10,9),(2,2,'2026-01-01',1,10,8)])
    db.commit(); db.close()
    request_file = Path(td) / 'request.json'
    response_file = Path(td) / 'response.json'
    stop = threading.Event()
    def serve():
        while not stop.is_set():
            if not request_file.exists():
                time.sleep(.005); continue
            try:
                ops = json.loads(request_file.read_text()); request_file.unlink()
                con = sqlite3.connect(dbfile); con.row_factory = sqlite3.Row; con.execute('PRAGMA foreign_keys=ON'); result = []
                for op in ops:
                    cur = con.execute(op['sql'], op['args'])
                    rows = [dict(x) for x in cur.fetchall()] if cur.description else []
                    result.append({'results': rows, 'meta': {'last_row_id': cur.lastrowid, 'changes': max(cur.rowcount, 0)}})
                con.commit(); con.close(); reply = {'result':result}
            except Exception as exc:
                reply = {'error':str(exc)}
            tmp = response_file.with_suffix('.tmp'); tmp.write_text(json.dumps(reply)); tmp.replace(response_file)
    thread = threading.Thread(target=serve, daemon=True); thread.start()
    js = r'''
import {readFileSync,writeFileSync,renameSync,existsSync,unlinkSync} from 'node:fs';
const [root, tmpdir] = process.argv.slice(1);
const source=readFileSync(root+'/worker_src/_worker.js','utf8');
const worker=(await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'))).default;
function execute(ops){const req=tmpdir+'/request.json', tmp=tmpdir+'/request.tmp', res=tmpdir+'/response.json';writeFileSync(tmp,JSON.stringify(ops));renameSync(tmp,req);const start=Date.now();while(!existsSync(res)){if(Date.now()-start>10000)throw Error('SQLite bridge timeout');Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,5)}const x=JSON.parse(readFileSync(res,'utf8'));unlinkSync(res);if(x.error)throw Error(x.error);return x.result}
const db={prepare(sql){return {sql,args:[],bind(...args){this.args=args;return this}, async first(){return execute([this])[0].results[0]||null},async all(){return execute([this])[0]},async run(){return execute([this])[0]}}},async batch(ops){return execute(ops)}};
async function call(path, method='GET', body, token='p'){let response=await worker.fetch(new Request('https://example.test'+path,{method,headers:{Cookie:'zhixidao_auth='+token,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)}),{DB:db});return {status:response.status,headers:response.headers,body:await response.json()}}
function ok(x,msg){if(!x)throw Error(msg)}
let a=await call('/api/routine'), b=await call('/api/routine?student=second');
ok(a.status===200 && a.body.routine.student_id===1 && a.body.steps.length===7 && a.body.pending_wrong===1,'默认/种子');
ok(b.status===200 && b.body.routine.student_id===2 && b.body.steps[0].name==='二宝任务' && b.body.pending_wrong===0,'流程隔离');
ok((await call('/api/routine?student=invalid')).status===403 && (await call('/api/routine?student=')).status===403 && (await call('/api/routine?student=inactive')).status===403,'无效拒绝');
let k=await call('/api/routine?student=yueyue','GET',undefined,'k');ok(k.body.routine.student_id===2,'kid 强制本人');
for (let code of ['yueyue','second']) {let x=await call('/api/overview?student='+code); ok(x.status===200 && x.body.papers.length===1 && x.body.papers[0].title===(code==='yueyue'?'甲卷':'乙卷') && x.body.wrong_questions.length===1 && x.body.wrong_questions[0].id===(code==='yueyue'?'a':'b'),'首页隔离');ok(x.headers.get('cache-control')==='no-store','缓存头');let y=await call('/api/assess?student='+code);ok(y.status===200 && y.body.student===code,'评估上下文')}
ok((await call('/api/assess?student=invalid')).status===403,'评估无效拒绝');
ok((await call('/api/papers/1?student=second','DELETE')).status===404,'跨学生考卷删除拒绝');
ok((await call('/api/checkin?student=second','POST',{level_id:1,result:'pass'})).status===404,'跨学生关卡拒绝');
let math=await call('/api/math/all?student=second');ok(math.status===200 && math.body.sessions.length===1 && math.body.sessions[0].id===2,'口算隔离');
ok((await call('/api/math/sessions/1?student=second','DELETE')).status===404,'跨学生口算删除拒绝');
let created=await call('/api/routine?student=second','POST',{student_id:2,title:'测试未来版',effective_from:'2099-01-01',steps:[{name:'测试'}]});ok(created.status===200 && created.body.version===2,'创建新版');
ok((await call('/api/routine?student=second')).body.routine.version===1,'未来版不影响当前');
ok((await call('/api/routine/'+created.body.id+'?student=yueyue','PUT',{title:'错误'})).status===404,'跨学生修改拒绝');
ok((await call('/api/routine/'+created.body.id+'?student=second','PUT',{title:'纠正'})).status===200,'未来版本纠正');
ok((await call('/api/routine/1','PUT',{title:'错误'})).status===400,'生效版本不可修改');
ok((await call('/api/routine?student=second','POST',{student_id:1,title:'错误',effective_from:'2099-01-01',steps:[{name:'x'}]})).status===400,'写入学生不匹配拒绝');
ok((await call('/api/routine','POST',{student_id:2,title:'错误',effective_from:'2099-01-01',steps:[{name:'x'}]},'k')).status===403,'kid 禁止写入');
execute([{sql:'DELETE FROM routine_steps WHERE routine_id=?',args:[created.body.id]},{sql:'DELETE FROM routines WHERE id=?',args:[created.body.id]}]);
console.log('Worker 双学生冒烟通过：默认、无效、kid、流程/考卷/错题隔离、评估、关卡/口算隔离、未来版、权限、缓存、外键清理');
'''
    try:
        subprocess.run(['node','--input-type=module','-e',js,str(ROOT),td],check=True)
    finally:
        stop.set(); thread.join()
