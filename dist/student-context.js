(() => {
  const originalFetch = window.fetch.bind(window);
  const url = new URL(location.href);
  let student = url.searchParams.has('student') ? url.searchParams.get('student') : null;
  window.studentContext = { get code() { return student; } };
  window.fetch = (input, options) => {
    const target = new URL(typeof input === 'string' ? input : input.url, location.href);
    if (target.origin === location.origin && target.pathname.startsWith('/api/') && !['/api/students','/api/me','/api/me/password','/api/logout','/api/login','/api/health'].includes(target.pathname) && student !== null && !target.searchParams.has('student')) target.searchParams.set('student', student);
    return originalFetch(typeof input === 'string' ? target.href : new Request(target, input), options);
  };
  function updateLinks(root = document) {
    if (student === null) return;
    root.querySelectorAll('a[href]').forEach(a => {
      const u = new URL(a.getAttribute('href'), location.href);
      if (u.origin === location.origin && !u.pathname.startsWith('/api/') && !u.pathname.startsWith('/login')) {
        u.searchParams.set('student', student); a.href = u.pathname + u.search + u.hash;
      }
    });
  }
  async function init() {
    try {
      const res = await originalFetch('/api/students');
      if (!res.ok) throw new Error('无法读取孩子列表');
      const { students } = await res.json();
      const meResponse = await originalFetch('/api/me');
      const me = meResponse.ok ? await meResponse.json() : {};
      if (me.role === 'kid' && students.length === 1) { student = students[0].code; const pinned = new URL(location.href); pinned.searchParams.set('student', student); history.replaceState(null, '', pinned); }
      if (student === null && students.length) { student = students[0].code; if (location.pathname === '/routine.html') { const pinned = new URL(location.href); pinned.searchParams.set('student', student); history.replaceState(null, '', pinned); } }
      const current = students.find(s => s.code === student);
      const slot = document.getElementById('student-switch');
      if (!current) { if (slot) slot.textContent = '孩子无效或无权访问'; return; }
      if (slot && students.length === 1) slot.textContent = '👦 ' + current.display_name;
      else if (slot) {
        const select = document.createElement('select'); select.setAttribute('aria-label','切换孩子');
        students.forEach(s => { const option = document.createElement('option'); option.value = s.code; option.textContent = s.display_name; select.append(option); });
        select.value = student; select.addEventListener('change', () => { const next = new URL(location.href); next.searchParams.set('student', select.value); location.assign(next.href); }); slot.append(select);
      }
      updateLinks();
      new MutationObserver(() => updateLinks()).observe(document.body, {childList:true, subtree:true});
    } catch (error) { const slot = document.getElementById('student-switch'); if (slot) slot.textContent = '孩子信息暂不可用'; }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
