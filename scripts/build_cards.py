#!/usr/bin/env python3
"""过关卡纸卡构建：media/yueyue_zici_guoguanka.html → dist/cards.html。
自动追加：顶部工具条（返回/打印按钮，@media print 隐藏）+ 屏幕纸张感。
源文件内容更新后重跑本脚本即可（python3 scripts/build_cards.py）。
"""
import os

WS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SRC = os.path.join(WS, 'media', 'yueyue_zici_guoguanka.html')
DST = os.path.join(WS, 'projects', 'zhixidao', 'dist', 'cards.html')

CSS_ADD = '''
  /* ---- 屏幕模式工具条与纸张感（打印时不生效/隐藏） ---- */
  .toolbar { position:sticky; top:0; z-index:9; display:flex; gap:14px; align-items:center; flex-wrap:wrap; background:#fdf3f5; border-bottom:1pt solid #f2c7d3; padding:10px 16px; font-size:13px; color:#c2456f; }
  .toolbar button { background:#c2456f; color:#fff; border:none; border-radius:6px; padding:7px 14px; font-size:13px; cursor:pointer; }
  .toolbar a { color:#c2456f; }
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
           '  <span class="tip">打印对话框里选「另存为 PDF」可得电子版 · 答案页（最后一页）家长收好，别让孩子看到</span>\n'
           '</div>')


def main():
    src = open(SRC).read()
    assert src.count('<body>') == 1 and '</style>' in src, '源文件结构异常'
    src = src.replace('</style>', CSS_ADD + '</style>', 1)
    src = src.replace('<body>', TOOLBAR, 1)
    open(DST, 'w').write(src)
    n_pages = src.count('class="page')
    print('cards.html 已生成: %d bytes | 分页块 %d | 工具条 OK' % (len(src), n_pages))
    assert n_pages >= 5, '分页块数量异常'


if __name__ == '__main__':
    main()
