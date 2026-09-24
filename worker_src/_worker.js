// 智习岛 (zhixidao) — 家庭学习小站
// 基于 cf-crypto-site worker 改造：用户名+密码（PBKDF2 会话 + 登录限速）+ D1
// P0 API: /api/login /api/logout /api/me /api/me/password /api/overview /api/checkin /api/papers
// 隐私：站内只用昵称；全站登录后可见；kid 账号（P2）只能打卡页
const COOKIE = 'zhixidao_auth';
const SESSION_DAYS = 30;
const PBKDF2_ITER = 100000;
const PBKDF2_KEYLEN = 32;

// ---------- utils ----------
const enc = new TextEncoder();
function b64FromBytes(bytes) {
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) {
    s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  }
  return btoa(s);
}
function bytesFromB64(s) {
  const bin = atob(s);
  const u = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
  return u;
}
function json(data, status) {
  return new Response(JSON.stringify(data), {
    status: status || 200,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }
  });
}
function nowIso() { return new Date().toISOString(); }
function addDays(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString();
}
// 本地日期（站点用户固定 Asia/Shanghai，固定 +8 偏移）
function localToday(offsetDays) {
  return new Date(Date.now() + 8 * 3600 * 1000 + (offsetDays || 0) * 86400000).toISOString().slice(0, 10);
}

// ---------- password ----------
async function deriveBytes(passphrase, saltB64, iter, keylen) {
  const keyMaterial = await crypto.subtle.importKey('raw', enc.encode(passphrase), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', hash: 'SHA-256', salt: bytesFromB64(saltB64), iterations: iter },
    keyMaterial, keylen * 8);
  return new Uint8Array(bits);
}
async function hashPass(passphrase) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const bits = await deriveBytes(passphrase, b64FromBytes(salt), PBKDF2_ITER, PBKDF2_KEYLEN);
  return 'pbkdf2$' + PBKDF2_ITER + '$' + b64FromBytes(salt) + '$' + b64FromBytes(bits);
}
async function verifyPass(passphrase, stored) {
  try {
    const parts = (stored || '').split('$');
    if (parts.length !== 4 || parts[0] !== 'pbkdf2') return false;
    const iter = parseInt(parts[1], 10);
    const bits = await deriveBytes(passphrase, parts[2], iter, PBKDF2_KEYLEN);
    const expect = bytesFromB64(parts[3]);
    if (bits.length !== expect.length) return false;
    let diff = 0;
    for (let i = 0; i < bits.length; i++) diff |= bits[i] ^ expect[i];
    return diff === 0;
  } catch (e) { return false; }
}

// ---------- session ----------
function cookieToken(request) {
  const cookie = request.headers.get('Cookie') || '';
  const m = cookie.match(new RegExp('(?:^|;\\s*)' + COOKIE + '=([^;]+)'));
  return m ? m[1] : null;
}
async function currentUser(request, env) {
  const token = cookieToken(request);
  if (!token) return null;
  const row = await env.DB.prepare(
    `SELECT s.token, s.expires_at, u.id AS user_id, u.username, u.role, u.active
     FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?`
  ).bind(token).first();
  if (!row) return null;
  if (row.expires_at < nowIso() || !row.active) {
    await env.DB.prepare('DELETE FROM sessions WHERE token = ?').bind(token).run();
    return null;
  }
  return { token, userId: row.user_id, username: row.username, role: row.role };
}
function cookieFor(token) {
  return `${COOKIE}=${token}; Path=/; HttpOnly; SameSite=Strict; Secure; Max-Age=${SESSION_DAYS * 86400}`;
}
function clearCookieFor() {
  return `${COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Secure; Max-Age=0`;
}
async function serveStatic(urlstr, env) {
  const r = await env.ASSETS.fetch(urlstr);
  const h = new Headers(r.headers);
  h.set('Cache-Control', 'no-store');
  return new Response(r.body, { status: r.status, headers: h });
}
async function issueSession(user, env) {
  const token = crypto.randomUUID();
  const exp = addDays(SESSION_DAYS);
  await env.DB.prepare('INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)')
    .bind(token, user.id, exp).run();
  return new Response(JSON.stringify({ ok: true, username: user.username, role: user.role }), {
    status: 200,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      'Set-Cookie': cookieFor(token)
    }
  });
}

// ---------- 登录限速：每 IP 每小时最多 10 次失败（成功即清零） ----------
const LOGIN_MAX_FAILS = 10;
const LOGIN_WINDOW_MS = 3600 * 1000;
function clientIp(request) {
  return request.headers.get('CF-Connecting-IP')
    || (request.headers.get('X-Forwarded-For') || '').split(',')[0].trim()
    || 'unknown';
}
async function throttleStatus(request, env) {
  const ip = clientIp(request);
  const row = await env.DB.prepare('SELECT fail_count, window_start FROM login_throttle WHERE ip = ?')
    .bind(ip).first();
  if (!row) return { ip, blocked: false };
  const cutoff = new Date(Date.now() - LOGIN_WINDOW_MS).toISOString();
  if (row.window_start > cutoff && row.fail_count >= LOGIN_MAX_FAILS) {
    const retryAfter = Math.max(1, Math.ceil((Date.parse(row.window_start) + LOGIN_WINDOW_MS - Date.now()) / 1000));
    return { ip, blocked: true, retryAfter };
  }
  return { ip, blocked: false };
}
async function throttleRecordFail(env, ip) {
  const now = new Date().toISOString();
  const cutoff = new Date(Date.now() - LOGIN_WINDOW_MS).toISOString();
  await env.DB.prepare(
    `INSERT INTO login_throttle (ip, fail_count, window_start) VALUES (?1, 1, ?2)
     ON CONFLICT(ip) DO UPDATE SET
       fail_count = CASE WHEN login_throttle.window_start <= ?3 THEN 1 ELSE login_throttle.fail_count + 1 END,
       window_start = CASE WHEN login_throttle.window_start <= ?3 THEN ?2 ELSE login_throttle.window_start END`
  ).bind(ip, now, cutoff).run();
}
async function throttleClear(env, ip) {
  await env.DB.prepare('DELETE FROM login_throttle WHERE ip = ?').bind(ip).run();
}

// ---------- login/logout/me ----------
async function apiLogin(request, env) {
  const throttle = await throttleStatus(request, env);
  if (throttle.blocked) {
    return new Response(JSON.stringify({ error: '失败次数过多，请稍后再试' }), {
      status: 429,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-store',
        'Retry-After': String(throttle.retryAfter)
      }
    });
  }
  let body = {};
  try { body = await request.json(); } catch (e) {}
  const username = (body.username || '').trim();
  const password = body.password || '';
  if (!username || !password) return json({ error: '请输入用户名和密码' }, 400);
  const user = await env.DB.prepare('SELECT * FROM users WHERE username = ? AND active = 1').bind(username).first();
  const ok = user ? await verifyPass(password, user.pw_hash) : false;
  if (!ok) {
    await throttleRecordFail(env, throttle.ip);
    return json({ error: '用户名或密码错误' }, 401);
  }
  await throttleClear(env, throttle.ip);
  return issueSession(user, env);
}
async function apiLogout(request, env) {
  const token = cookieToken(request);
  if (token) await env.DB.prepare('DELETE FROM sessions WHERE token = ?').bind(token).run();
  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'Set-Cookie': clearCookieFor() }
  });
}
async function apiMe(request, env) {
  const u = await currentUser(request, env);
  if (!u) return json({ authed: false }, 200);
  return json({ authed: true, username: u.username, role: u.role });
}

// ---------- 改密码（保留当前会话，踢掉其他设备） ----------
async function changeMyPassword(request, env, u) {
  let body = {};
  try { body = await request.json(); } catch (e) {}
  const current = body.current || '';
  const next = (body.next || '').trim();
  if (!next || next.length < 6) return json({ error: '新密码至少 6 位' }, 400);
  const user = await env.DB.prepare('SELECT * FROM users WHERE id = ?').bind(u.userId).first();
  if (!user) return json({ error: '用户不存在' }, 404);
  const ok = await verifyPass(current, user.pw_hash);
  if (!ok) return json({ error: '当前密码错误' }, 400);
  const hash = await hashPass(next);
  await env.DB.prepare('UPDATE users SET pw_hash = ? WHERE id = ?').bind(hash, u.userId).run();
  await env.DB.prepare('DELETE FROM sessions WHERE user_id = ? AND token != ?').bind(u.userId, u.token).run();
  return json({ ok: true });
}

// ---------- 业务：总览 ----------
async function getStudentId(env) {
  const s = await env.DB.prepare('SELECT id FROM students WHERE code = ? AND active = 1').bind('yueyue').first();
  return s ? s.id : null;
}
async function apiOverview(request, env) {
  const sid = await getStudentId(env);
  if (!sid) return json({ error: '学生数据未初始化' }, 500);
  const levels = (await env.DB.prepare(
    `SELECT l.id, l.kind, l.name, l.detail, l.sort,
            COUNT(c.id) AS attempts,
            SUM(CASE WHEN c.result = 'pass' THEN 1 ELSE 0 END) AS passes,
            MAX(CASE WHEN c.result = 'pass' THEN c.date END) AS last_pass,
            MAX(c.date) AS last_try
     FROM levels l LEFT JOIN checkin c
       ON c.level_id = l.id AND (c.note IS NULL OR c.note <> 'verify-selfcheck')
     WHERE l.student_id = ?
     GROUP BY l.id ORDER BY l.sort`).bind(sid).all()).results;
  const days = (await env.DB.prepare(
    `SELECT date, COUNT(*) AS n, SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) AS p
     FROM checkin WHERE student_id = ? AND date >= ?
       AND (note IS NULL OR note <> 'verify-selfcheck')
     GROUP BY date ORDER BY date DESC`).bind(sid, localToday(-29)).all()).results;
  // 连胜：今天过了从今天数，今天还没过则从昨天数（不提前断签）
  const passByDay = new Map(days.map(d => [d.date, d.p]));
  let streak = 0;
  let t = Date.now() + 8 * 3600 * 1000;
  if (!((passByDay.get(new Date(t).toISOString().slice(0, 10)) || 0) > 0)) t -= 86400000;
  for (;;) {
    const d = new Date(t).toISOString().slice(0, 10);
    if ((passByDay.get(d) || 0) > 0) { streak++; t -= 86400000; } else break;
  }
  // 总览只露最近 3 张考卷摘要（防时间线无限增长挤掉打卡区），全量进 /papers.html
  const papers = (await env.DB.prepare(
    `SELECT id, date, title, analysis_md, source, subject, term FROM papers
     WHERE student_id = ? ORDER BY date DESC, id DESC LIMIT 3`).bind(sid).all()).results;
  // P1：错题展示副本（sync_cuoti.py 全量替换，此处只读；student_code 是文本 'yueyue'）。
  // 防卡顿：归档过滤下推 SQL + LIMIT 兜底（错题 200 条/弱项 30 条封顶，超量再考虑分页）
  const wq = (await env.DB.prepare(
    `SELECT id, subject_code, title, stem, answer, analysis, question_type, status,
            wrong_count, correct_count, last_wrong_at, kp_names, stubborn, created_at
     FROM wrong_questions WHERE student_code = ? AND is_archived = 0
     ORDER BY stubborn DESC, wrong_count DESC, created_at DESC LIMIT 200`).bind('yueyue').all()).results;
  const wqTotal = (await env.DB.prepare(
    `SELECT COUNT(*) AS n FROM wrong_questions WHERE student_code = ? AND is_archived = 0`).bind('yueyue').first());
  const wps = (await env.DB.prepare(
    `SELECT kp_code, kp_name, subject_code, question_count, wrong_count, last_wrong_at, stubborn_count
     FROM weak_points WHERE student_code = ?
     ORDER BY wrong_count DESC, question_count DESC LIMIT 30`).bind('yueyue').all()).results;
  return json({ ok: true, today: localToday(0), levels, days, streak, papers,
                wrong_questions: wq, wq_total: wqTotal ? wqTotal.n : 0, weak_points: wps });
}

// ---------- 业务：打卡 ----------
async function apiCheckin(request, env, u) {
  if (u.role !== 'parent') return json({ error: '仅家长可代录打卡' }, 403);
  let body = {};
  try { body = await request.json(); } catch (e) {}
  const levelId = parseInt(body.level_id, 10);
  const result = body.result === 'pass' ? 'pass' : 'fail';
  const stars = Math.min(5, Math.max(0, parseInt(body.stars, 10) || (result === 'pass' ? 1 : 0)));
  const date = /^\d{4}-\d{2}-\d{2}$/.test(body.date || '') ? body.date : localToday(0);
  const note = (body.note || '').slice(0, 200) || null;
  const sid = await getStudentId(env);
  if (!sid) return json({ error: '学生数据未初始化' }, 500);
  const lv = await env.DB.prepare('SELECT id FROM levels WHERE id = ? AND student_id = ?').bind(levelId, sid).first();
  if (!lv) return json({ error: '关卡不存在' }, 404);
  await env.DB.prepare(
    `INSERT INTO checkin (student_id, level_id, date, result, stars, note, source)
     VALUES (?, ?, ?, ?, ?, ?, 'web_parent')`).bind(sid, levelId, date, result, stars, note).run();
  return json({ ok: true });
}

// ---------- 业务：考卷库（时间线 + 分页） ----------
async function apiPapers(request, env) {
  const sid = await getStudentId(env);
  const url = new URL(request.url);
  const limit = Math.min(50, Math.max(1, parseInt(url.searchParams.get('limit'), 10) || 20));
  const offset = Math.max(0, parseInt(url.searchParams.get('offset'), 10) || 0);
  const papers = (await env.DB.prepare(
    `SELECT id, date, title, analysis_md, source, subject, term FROM papers
     WHERE student_id = ? ORDER BY date DESC, id DESC LIMIT ? OFFSET ?`).bind(sid, limit, offset).all()).results;
  const total = (await env.DB.prepare(
    `SELECT COUNT(*) AS n FROM papers WHERE student_id = ?`).bind(sid).first());
  const n = total ? total.n : 0;
  return json({ ok: true, papers, total: n, has_more: offset + papers.length < n });
}
// 考卷表单公共校验（创建/编辑共用）
function parsePaperBody(body) {
  const title = (body.title || '').trim().slice(0, 120);
  if (!title) return { error: '考卷标题必填' };
  const date = /^\d{4}-\d{2}-\d{2}$/.test(body.date || '') ? body.date : localToday(0);
  const analysisMd = (body.analysis_md || '').slice(0, 8000) || null;
  const subject = ['chinese', 'math', 'english'].includes(body.subject) ? body.subject : 'chinese';
  const term = (body.term || '').trim().slice(0, 20) || '2026秋';
  return { title, date, analysisMd, subject, term };
}
async function apiPaperCreate(request, env, u) {
  if (u.role !== 'parent') return json({ error: '仅家长可录入' }, 403);
  let body = {};
  try { body = await request.json(); } catch (e) {}
  const pb = parsePaperBody(body);
  if (pb.error) return json({ error: pb.error }, 400);
  const sid = await getStudentId(env);
  await env.DB.prepare(
    `INSERT INTO papers (student_id, date, title, analysis_md, source, subject, term)
     VALUES (?, ?, ?, ?, 'manual', ?, ?)`)
    .bind(sid, pb.date, pb.title, pb.analysisMd, pb.subject, pb.term).run();
  return json({ ok: true });
}
async function apiPaperUpdate(request, env, u, id) {
  if (u.role !== 'parent') return json({ error: '仅家长可编辑' }, 403);
  let body = {};
  try { body = await request.json(); } catch (e) {}
  const pb = parsePaperBody(body);
  if (pb.error) return json({ error: pb.error }, 400);
  const sid = await getStudentId(env);
  const r = await env.DB.prepare(
    `UPDATE papers SET date = ?, title = ?, analysis_md = ?, subject = ?, term = ?
     WHERE id = ? AND student_id = ?`)
    .bind(pb.date, pb.title, pb.analysisMd, pb.subject, pb.term, id, sid).run();
  if (!r.meta.changes) return json({ error: '考卷不存在' }, 404);
  return json({ ok: true });
}
async function apiPaperDelete(request, env, u, id) {
  if (u.role !== 'parent') return json({ error: '仅家长可删除' }, 403);
  const sid = await getStudentId(env);
  const r = await env.DB.prepare(
    `DELETE FROM papers WHERE id = ? AND student_id = ?`).bind(id, sid).run();
  if (!r.meta.changes) return json({ error: '考卷不存在' }, 404);
  return json({ ok: true });
}

// ---------- main fetch ----------
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const p = url.pathname;
    const method = request.method;

    if (p === '/api/health') return json({ ok: true, t: nowIso() });
    if (p === '/api/login' && method === 'POST') return apiLogin(request, env);

    if (p.startsWith('/api/')) {
      const u = await currentUser(request, env);
      if (!u) return json({ error: '未登录' }, 401);
      if (p === '/api/logout' && method === 'POST') return apiLogout(request, env);
      if (p === '/api/me') return apiMe(request, env);
      if (p === '/api/me/password' && method === 'POST') return changeMyPassword(request, env, u);
      if (p === '/api/overview') return apiOverview(request, env);
      if (p === '/api/checkin' && method === 'POST') return apiCheckin(request, env, u);
      if (p === '/api/papers' && method === 'GET') return apiPapers(request, env);
      if (p === '/api/papers' && method === 'POST') return apiPaperCreate(request, env, u);
      const pm = p.match(/^\/api\/papers\/(\d+)$/);
      if (pm && method === 'PUT') return apiPaperUpdate(request, env, u, parseInt(pm[1], 10));
      if (pm && method === 'DELETE') return apiPaperDelete(request, env, u, parseInt(pm[1], 10));
      return json({ error: '未找到' }, 404);
    }

    // 白名单静态：登录页 + 图标
    if (p === '/login' || p === '/login.html') return serveStatic(url.origin + '/login.html', env);
    if (p === '/favicon.svg' || p === '/favicon.ico' || p === '/robots.txt') return serveStatic(url.origin + p, env);

    // 其余页面：必须登录
    const u = await currentUser(request, env);
    if (!u) {
      return new Response(null, { status: 302, headers: { Location: '/login', 'Cache-Control': 'no-store' } });
    }
    const target = p === '/' ? '/index.html' : p;
    return serveStatic(url.origin + target, env);
  }
};
