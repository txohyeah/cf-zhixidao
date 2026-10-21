#!/usr/bin/env python3
"""过关卡纸卡构建：media/<源>.html → dist/<目标>.html。
自动追加：顶部工具条（返回/打印按钮，@media print 隐藏）+ 屏幕纸张感。
源文件内容更新后重跑本脚本即可（python3 scripts/build_cards.py）。
支持多张卡：往 CARDS 里加一项即可（主题色随卡走）。
"""
import os

WS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MEDIA = os.path.join(WS, 'media')
DIST = os.path.join(WS, 'projects', 'zhixidao', 'dist')

CARDS = [
    dict(src='yueyue_zici_guoguanka.html', dst='cards.html',
         fg='#c2456f', bg='#fdf3f5', border='#f2c7d3',
         tip='打印对话框里选「另存为 PDF」可得电子版 · 答案页（最后一页）家长收好，别让孩子看到',
         marker='字词过关卡', min_pages=5),
    dict(src='yueyue_kousuan_koujueka.html', dst='cards-math.html',
         fg='#3a6ea5', bg='#eef4fb', border='#bcd0e8',
         tip='打印对话框里选「另存为 PDF」可得电子版 · 最后 1 页是家长页（规矩+记录表），孩子用前两页',
         marker='口算口诀卡', min_pages=3),
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


def main():
    for card in CARDS:
        build_one(card)


if __name__ == '__main__':
    main()
