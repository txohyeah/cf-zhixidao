#!/usr/bin/env python3
"""过关卡纸卡构建：media/<源>.html → dist/<目标>.html。
自动追加：顶部工具条（返回/打印按钮，@media print 隐藏）+ 屏幕纸张感。
源文件内容更新后重跑本脚本即可（python3 scripts/build_cards.py）。
支持多张卡：往 CARDS 里加一项即可（主题色随卡走）。
"""
import os
from html import escape

WS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA = os.path.join(PROJECT, 'media')
LEGACY_MEDIA = os.path.join(WS, 'media')
DIST = os.path.join(PROJECT, 'dist')

CARDS = [
    dict(src='yueyue_zici_guoguanka.html', dst='cards.html',
         fg='#c2456f', bg='#fdf3f5', border='#f2c7d3',
         tip='打印对话框里选「另存为 PDF」可得电子版 · 答案页（最后一页）家长收好，别让孩子看到',
         marker='字词过关卡', min_pages=5),
    dict(src='yueyue_kousuan_koujueka.html', dst='cards-math.html',
         fg='#3a6ea5', bg='#eef4fb', border='#bcd0e8',
         tip='打印对话框里选「另存为 PDF」可得电子版 · 最后 1 页是家长页（规矩+记录表），孩子用前两页',
         marker='口算口诀卡', min_pages=3),
    dict(src='yueyue_koujue99.html', dst='cards-koujue99.html',
         fg='#2F7D6D', bg='#EDF5F2', border='#BFE0D6',
         tip='页1全表贴墙 · 页2挖空自填 · 页3默写全对才算过关',
         marker='乘法口诀表', min_pages=3),
]

CSS_TPL = '''
  /* ---- 屏幕模式工具条与纸张感（打印时不生效/隐藏） ---- */
  .toolbar { position:sticky; top:0; z-index:9; display:flex; gap:14px; align-items:center; flex-wrap:wrap; background:%(bg)s; border-bottom:1pt solid %(border)s; padding:10px 16px; font-size:13px; color:%(fg)s; }
  .toolbar button { background:%(fg)s; color:#fff; border:none; border-radius:6px; padding:7px 14px; font-size:13px; cursor:pointer; }
  .toolbar a { color:%(fg)s; }
  .toolbar .tip { color:#8b857a; font-size:12px; }
  @media screen {
    body { background:#f3eef0; padding:14px 8px; }
    .page { background:#fff; max-width:186mm; margin:0 auto 16px; padding:8mm 12mm; box-shadow:0 2px 10px rgba(0,0,0,.12); border-radius:4px; }
  }
  @media print { .toolbar { display:none !important; } body { background:#fff; padding:0; } }
'''

TOOLBAR = ('<body>\n<div class="toolbar">\n'
           '  <a href="/">← 返回智习岛</a>\n'
           '  <button onclick="window.print()">🖨 打印 / 存为 PDF</button>\n'
           '  <span class="tip">%(tip)s</span>\n'
           '</div>')


def build_one(card):
    src_path = os.path.join(MEDIA, card['src'])
    # 老卡源仍保留在工作区 media，只读兼容；新卡源收在项目内。
    if not os.path.isfile(src_path):
        src_path = os.path.join(LEGACY_MEDIA, card['src'])
    dst_path = os.path.join(DIST, card['dst'])
    src = open(src_path).read()
    assert src.count('<body>') == 1 and '</style>' in src, '源文件结构异常: ' + card['src']
    src = src.replace('</style>', CSS_TPL % card + '</style>', 1)
    src = src.replace('<body>', TOOLBAR % card, 1)
    open(dst_path, 'w').write(src)
    n_pages = src.count('class="page')
    assert card['marker'] in src, '内容标记缺失: ' + card['marker']
    assert n_pages >= card['min_pages'], '分页块数量异常: %s (%d)' % (card['dst'], n_pages)
    print('%s 已生成: %d bytes | 分页块 %d | 工具条 OK | 标记「%s」在' %
          (card['dst'], len(src), n_pages, card['marker']))



PRINT_INDEX = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>智习岛 · 打印素材</title>
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<style>
  :root { --paper:#FBFBF8; --grid-line:#D9E6EC; --ink-blue:#34558B; --highlight:#FFE066; --ink:#2A2B28; --muted:#626A70; --line:rgba(52,85,139,.18); --hand:KaiTi,STKaiti,"Kaiti SC",serif; --mono:ui-monospace,SFMono-Regular,Consolas,monospace; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { font-family:"PingFang SC","Microsoft YaHei",sans-serif; color:var(--ink); line-height:1.65; background-color:var(--paper); background-image:linear-gradient(rgba(217,230,236,.38) 1px,transparent 1px),linear-gradient(90deg,rgba(217,230,236,.38) 1px,transparent 1px); background-size:24px 24px; padding-bottom:48px; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
  header,main { max-width:1080px; margin:auto; padding:24px 20px; }
  header { display:flex; align-items:baseline; justify-content:space-between; gap:16px; border-bottom:1px solid var(--line); }
  .brand,h1,h2,h3 { font-family:var(--hand); }
  .brand { font-size:25px; color:var(--ink-blue); }
  a { color:var(--ink-blue); text-underline-offset:4px; }
  h1 { font-size:32px; font-weight:500; }
  h2 { font-size:25px; margin-bottom:10px; }
  .intro { color:var(--muted); margin:6px 0 24px; }
  .catalog { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:18px; margin-bottom:32px; }
  .material { background:#fff; border:1px solid var(--card-border); border-top:4px solid var(--card-fg); padding:22px; border-radius:6px; display:flex; flex-direction:column; gap:12px; box-shadow:2px 3px 0 rgba(52,85,139,.04); }
  .material h2 { font-size:23px; color:var(--card-fg); margin:0; }
  .material p { font-size:13px; color:var(--muted); flex:1; }
  .material .meta { display:flex; align-items:center; justify-content:space-between; gap:12px; font-size:13px; }
  .pages { padding:2px 8px; background:var(--card-bg); color:var(--card-fg); font-family:var(--mono); }
  .generator { background:#fff; border:1px solid var(--line); border-radius:6px; padding:24px; }
  .assistant-tip { display:inline; background:linear-gradient(transparent 55%,var(--highlight) 55%,var(--highlight) 95%,transparent 95%); font-size:13px; }
  .generator h2 { margin-top:12px; }
  fieldset { border:1px solid var(--line); border-radius:4px; padding:14px 16px; margin-top:16px; min-width:0; }
  legend { padding:0 6px; font-weight:600; font-size:14px; }
  label { cursor:pointer; }
  input[type="checkbox"] { accent-color:var(--ink-blue); width:16px; height:16px; vertical-align:-3px; margin-right:6px; }
  .type-row + .type-row { margin-top:14px; padding-top:14px; border-top:1px solid var(--line); }
  .sub-options { margin:8px 0 0 24px; display:flex; gap:10px 18px; flex-wrap:wrap; font-size:13px; color:var(--muted); }
  .sub-options label { white-space:nowrap; }
  .scope-note { font-size:12px; color:var(--muted); margin:8px 0 0 24px; }
  .options { display:flex; align-items:center; flex-wrap:wrap; gap:16px 24px; margin:20px 0; font-size:14px; }
  select { background:var(--paper); border:1px solid var(--line); border-radius:4px; padding:6px 12px; font:inherit; color:var(--ink); }
  button { background:var(--ink-blue); color:#fff; padding:10px 18px; border:1px solid var(--ink-blue); border-radius:4px; font:inherit; cursor:pointer; }
  button.secondary { background:var(--paper); color:var(--ink-blue); }
  button:disabled { opacity:.45; cursor:not-allowed; }
  .actions { display:flex; flex-wrap:wrap; gap:12px; }
  :focus-visible { outline:2px solid var(--ink-blue); outline-offset:4px; }
  .message { min-height:24px; margin-top:12px; font-size:13px; color:var(--muted); }
  .message.error { color:var(--ink); text-decoration:underline wavy var(--ink-blue); text-underline-offset:4px; }
  [hidden] { display:none !important; }
  .worksheet { margin-top:28px; }
  .page { background:#fff; color:#222; width:186mm; max-width:100%; margin:0 auto 20px; padding:8mm 10mm; box-shadow:0 2px 10px rgba(0,0,0,.1); page-break-after:always; }
  .page:last-child { page-break-after:auto; }
  .sheet-head { display:flex; align-items:baseline; justify-content:space-between; gap:4mm; padding-bottom:3mm; border-bottom:1pt solid #34558B; }
  .sheet-head h2 { color:#34558B; font-size:18pt; margin:0; }
  .sheet-head small { font:9pt Arial,sans-serif; white-space:nowrap; }
  .sheet-meta { font-size:10pt; margin:4mm 0 5mm; display:flex; gap:8mm; align-items:center; flex-wrap:wrap; }
  .write-line { display:inline-block; width:25mm; height:5mm; border-bottom:.8pt solid #777; }
  .sheet-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:0 6mm; }
  .problem { display:flex; align-items:baseline; gap:2mm; font-family:Arial,"PingFang SC",sans-serif; font-size:16pt; line-height:1.2; min-height:8mm; padding:.5mm 0; break-inside:avoid; white-space:nowrap; }
  .qno { color:#666; font:9pt Arial,sans-serif; width:6mm; flex-shrink:0; }
  .answer-space { display:inline-block; width:14mm; height:5mm; border-bottom:1pt solid #555; }
  .sheet-answer { font-weight:700; }
  .sheet-foot { border-top:.6pt solid #ccc; padding-top:3mm; margin-top:6mm; color:#555; font-size:9pt; }
  @page { size:A4; margin:12mm 12mm 14mm; }
  @media(max-width:600px) { header,main { padding:18px 14px; } .generator { padding:18px; } .page { padding:6mm 4mm; } .problem { font-size:12pt; gap:1mm; } .answer-space { width:9mm; } .sheet-grid { column-gap:2mm; } .sheet-head h2 { font-size:16pt; } }
  @media print {
    body { background:#fff; padding:0; }
    header,.screen-only { display:none !important; }
    main { padding:0; max-width:none; margin:0; }
    .worksheet { margin:0; }
    .page { width:100%; max-width:none; margin:0; padding:0; box-shadow:none; border:0; break-after:page; }
    .page:last-child { break-after:auto; page-break-after:auto; }
    .sheet-grid { column-gap:6mm; }
    .problem { font-size:16pt; gap:2mm; }
    .answer-space { width:14mm; }
    .sheet-head h2 { font-size:18pt; }
  }
</style>
</head>
<body>
<header><div class="brand">智习岛 · 学习手账</div><a href="/">← 返回总览</a></header>
<main>
  <section class="screen-only" aria-labelledby="printTitle">
    <h1 id="printTitle">打印素材</h1>
    <p class="intro">点开卡片即可打印，练习纸现场生成。</p>
    <div class="catalog">__CARDS__</div>
  </section>
  <section class="generator screen-only" aria-labelledby="generatorTitle">
    <p class="assistant-tip">做完拍照发给助教批改，自动记入口算记录</p>
    <h2 id="generatorTitle">口算练习纸生成器</h2>
    <p class="intro">选好范围，生成一套不重复的题目；重新生成会替换当前练习纸。</p>
    <form id="generatorForm">
      <fieldset><legend>题型 · 可多选</legend>
        <div class="type-row"><label><input type="checkbox" name="type" value="within20" checked>20 以内加减</label></div>
        <div class="type-row"><label><input type="checkbox" name="type" value="within100" checked>100 以内加减</label>
          <div class="sub-options"><label><input type="checkbox" id="carry" checked>含进位</label><label><input type="checkbox" id="borrow" checked>含退位</label></div>
        </div>
        <div class="type-row"><label><input type="checkbox" name="type" value="multiply" checked>表内乘法</label>
          <div class="sub-options" role="group" aria-label="乘数范围">__FACTORS__</div>
          <p class="scope-note">乘法与除法共用以上乘数范围，另一个乘数为 1–9。</p>
        </div>
        <div class="type-row"><label><input type="checkbox" name="type" value="divide">表内除法</label></div>
      </fieldset>
      <div class="options"><label for="count">题数 <select id="count"><option value="20">20 题</option><option value="30">30 题</option><option value="50">50 题</option></select></label><label><input type="checkbox" id="withAnswers" checked>附答案页</label></div>
      <div class="actions"><button type="submit">生成练习纸</button><button class="secondary" type="button" id="printSheet" disabled>🖨 打印练习纸</button></div>
      <p class="message" id="generatorMessage" role="status" aria-live="polite">尚未生成练习纸。</p>
    </form>
  </section>
  <div class="worksheet" id="worksheet" aria-label="生成的口算练习纸"></div>
</main>
<script>
'use strict';
// 枚举全部合法算式再抽样：容量明确，无随机重试死循环；各题型共享去重集合。
function shuffle(items, random = Math.random) {
  for (let i = items.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [items[i], items[j]] = [items[j], items[i]];
  }
  return items;
}
function questionPool(type, options) {
  const pool = new Map();
  function add(a, op, b, answer) {
    const expr = `${a} ${op} ${b}`;
    pool.set(expr, {a, b, op, answer, expr, type});
  }
  if (type === 'within20' || type === 'within100') {
    const max = type === 'within20' ? 20 : 100;
    for (let a = 1; a <= max; a++) for (let b = 1; b <= max; b++) {
      if (a+b <= max && (max === 20 || options.carry || a%10+b%10 <= 9)) add(a,'+',b,a+b);
      if (a >= b && (max === 20 || options.borrow || a%10 >= b%10)) add(a,'−',b,a-b);
    }
  } else if (type === 'multiply' || type === 'divide') {
    for (const a of options.factors) for (let b = 1; b <= 9; b++) {
      if (type === 'multiply') { add(a,'×',b,a*b); add(b,'×',a,a*b); }
      else { add(a*b,'÷',a,b); add(a*b,'÷',b,a); }
    }
  }
  return [...pool.values()];
}
function generateQuestions(options, random = Math.random) {
  const validTypes = ['within20','within100','multiply','divide'];
  if (!Array.isArray(options.types) || !options.types.length || options.types.some(t=>!validTypes.includes(t))) throw new Error('请至少勾选一种题型。');
  if (![20,30,50].includes(options.count)) throw new Error('题数请选择 20、30 或 50。');
  if (options.types.some(t=>t==='multiply'||t==='divide') && (!Array.isArray(options.factors) || !options.factors.length || options.factors.some(n=>!Number.isInteger(n)||n<2||n>9))) throw new Error('请至少选择一个 2–9 的乘数。');
  const pools = shuffle([...new Set(options.types)].map(type=>shuffle(questionPool(type,options),random)),random);
  const result = [], used = new Set();
  while (result.length < options.count) {
    let added = false;
    for (const pool of pools) {
      while (pool.length && used.has(pool[pool.length-1].expr)) pool.pop();
      if (!pool.length) continue;
      const q = pool.pop(); used.add(q.expr); result.push(q); added = true;
      if (result.length === options.count) return result;
    }
    if (!added) throw new Error(`当前范围只有 ${result.length} 道不重复的题，请增加题型或乘数范围，或减少题数。`);
  }
  return result;
}
function readOptions() {
  return {
    types:[...document.querySelectorAll('input[name="type"]:checked')].map(e=>e.value),
    factors:[...document.querySelectorAll('input[name="factor"]:checked')].map(e=>Number(e.value)),
    carry:document.getElementById('carry').checked,
    borrow:document.getElementById('borrow').checked,
    count:Number(document.getElementById('count').value),
    withAnswers:document.getElementById('withAnswers').checked
  };
}
function renderWorksheet(questions, withAnswers) {
  // 所有插值均来自已校验的数值和固定算符，不插入用户文本。
  function page(answers) {
    return `<section class="page ${answers?'answers':'exercises'}">
      <div class="sheet-head"><h2>${answers?'答案页 · 家长收好':'口算练习纸'}</h2><small>${questions.length} 题 · ${answers?'2':'1'} / ${withAnswers?'2':'1'}</small></div>
      <div class="sheet-meta"><span>姓名 <span class="write-line"></span></span><span>日期 <span class="write-line"></span></span>${answers?'':'<span>用时 <span class="write-line"></span></span>'}</div>
      <div class="sheet-grid">${questions.map((q,i)=>`<div class="problem"><span class="qno">${i+1}.</span><span>${q.expr} =</span>${answers?`<span class="sheet-answer">${q.answer}</span>`:'<span class="answer-space"></span>'}</div>`).join('')}</div>
      <p class="sheet-foot">${answers?'答案按题号对应，请在练习完成后核对。':'独立完成后检查；做完拍照发给助教批改。'}</p>
    </section>`;
  }
  return page(false) + (withAnswers ? page(true) : '');
}
const generatorForm = document.getElementById('generatorForm');
const printButton = document.getElementById('printSheet');
const worksheet = document.getElementById('worksheet');
const generatorMessage = document.getElementById('generatorMessage');
function clearWorksheet() {
  worksheet.innerHTML = ''; printButton.disabled = true;
  generatorMessage.className = 'message';
  generatorMessage.textContent = '选项已调整，请重新生成练习纸。';
}
generatorForm.addEventListener('change', clearWorksheet);
generatorForm.addEventListener('submit', e=>{
  e.preventDefault();
  try {
    const options = readOptions();
    const questions = generateQuestions(options);
    worksheet.innerHTML = renderWorksheet(questions,options.withAnswers);
    printButton.disabled = false;
    generatorMessage.className = 'message';
    generatorMessage.textContent = `已生成 ${questions.length} 道不重复题目${options.withAnswers?'，附 1 页答案':''}。可先预览，再打印。`;
  } catch(error) {
    worksheet.innerHTML = ''; printButton.disabled = true;
    generatorMessage.className = 'message error'; generatorMessage.textContent = error.message;
  }
});
printButton.addEventListener('click',()=>{if(!printButton.disabled)window.print();});
</script>
</body>
</html>
'''


def build_print_index():
    # 清单只遍历 CARDS；新增卡片无需维护另一份名称、链接与用途。
    cards = []
    for card in CARDS:
        values = {key: escape(str(value), quote=True) for key, value in card.items()}
        cards.append(('''<article class="material" style="--card-fg:{fg};--card-bg:{bg};--card-border:{border}">
          <h2>{marker}</h2><p>{tip}</p><div class="meta"><span class="pages">{min_pages} 页 A4</span>
          <a href="/{dst}">打开并打印 →</a></div></article>''').format(**values))
    factors = ''.join('<label><input type="checkbox" name="factor" value="%d" checked>%d</label>' % (n, n) for n in range(2, 10))
    output = PRINT_INDEX.replace('__CARDS__', '\n'.join(cards)).replace('__FACTORS__', factors)
    with open(os.path.join(DIST, 'print.html'), 'w') as handle:
        handle.write(output)
    assert '__CARDS__' not in output and '__FACTORS__' not in output
    print('print.html 已生成: %d 张卡片 | 练习纸生成器 OK' % len(CARDS))


def main():
    for card in CARDS:
        build_one(card)
    build_print_index()


if __name__ == '__main__':
    main()
