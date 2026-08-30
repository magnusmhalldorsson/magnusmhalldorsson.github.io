#!/usr/bin/env python3
"""Generate publications.html from a DBLP author record.

Standard library only.

    python3 scripts/dblp2html.py
    python3 scripts/dblp2html.py --pid h/MMHalldorsson -o publications.html

DBLP is the source of truth: it already carries consistent, accented author
names and per-paper DBLP keys, so there is no local .bib file to keep in
sync and no author-name matching to get wrong. Entries are grouped by year,
newest first.

Every arXiv preprint DBLP lists (journal "CoRR", publtype "informal") is
matched to its published counterpart by normalised title. When a match is
found, the arXiv link is attached to the published entry instead of listed
as a separate row. An unmatched preprint (no venue publication yet) is kept
as its own entry, linked straight to arXiv.

Re-run this instead of hand-editing publications.html.
"""

import argparse
import html
import re
import sys
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET

DBLP_XML = 'https://dblp.org/pid/%s.xml'

PUB_TYPES = {'article', 'inproceedings', 'incollection'}


def norm_title(t):
    t = unicodedata.normalize('NFKD', t or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', t.lower())


def arxiv_id_of(pub):
    for ee in pub.findall('ee'):
        m = re.search(r'arXiv\.(\S+)$', ee.text or '')
        if m:
            return m.group(1)
    vol = pub.findtext('volume', '')
    m = re.match(r'abs/(\S+)', vol)
    return m.group(1) if m else None


def doi_url_of(pub):
    for ee in pub.findall('ee'):
        url = ee.text or ''
        if 'arXiv' not in url:
            return url
    return ''


def venue_of(pub):
    if pub.tag == 'article':
        return pub.findtext('journal', '')
    return pub.findtext('booktitle', '')


def authors_of(pub, my_pid):
    out = []
    for a in pub.findall('author'):
        mine = a.get('pid') == my_pid
        # DBLP appends a disambiguation number ("Christian Konrad 0001") when
        # the name is shared with someone else in their database
        name = html.escape(re.sub(r'\s+\d{4}$', '', a.text or ''))
        out.append('<strong>%s</strong>' % name if mine else name)
    if len(out) > 1:
        return ', '.join(out[:-1]) + ' and ' + out[-1]
    return out[0] if out else ''


def fetch(pid):
    url = DBLP_XML % pid
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pid', default='h/MMHalldorsson', help='DBLP person id')
    ap.add_argument('-o', '--out', default='publications.html')
    args = ap.parse_args()

    try:
        xml_bytes = fetch(args.pid)
    except OSError as err:
        sys.exit('Could not reach DBLP: %s' % err)

    root = ET.fromstring(xml_bytes)
    records = [list(r)[0] for r in root.findall('r')]

    published, preprints = [], []
    for pub in records:
        if pub.tag == 'article' and pub.get('publtype') == 'informal':
            preprints.append(pub)
        elif pub.tag in PUB_TYPES:
            published.append(pub)

    arxiv_by_title = {}
    for pub in preprints:
        key = norm_title(pub.findtext('title', ''))
        if key:
            arxiv_by_title.setdefault(key, pub)

    entries = []
    for pub in published:
        key = norm_title(pub.findtext('title', ''))
        arxiv_pub = arxiv_by_title.pop(key, None)
        entries.append({
            'title': (pub.findtext('title', 'Untitled')).rstrip('.'),
            'year': int(pub.findtext('year', '0') or 0),
            'venue': venue_of(pub),
            'url': doi_url_of(pub),
            'authors': authors_of(pub, args.pid),
            'arxiv': arxiv_id_of(arxiv_pub) if arxiv_pub is not None else None,
        })

    # leftover preprints: no published version yet, listed as arXiv entries themselves
    for pub in arxiv_by_title.values():
        aid = arxiv_id_of(pub)
        entries.append({
            'title': (pub.findtext('title', 'Untitled')).rstrip('.'),
            'year': int(pub.findtext('year', '0') or 0),
            'venue': 'arXiv',
            'url': 'https://arxiv.org/abs/%s' % aid if aid else '',
            'authors': authors_of(pub, args.pid),
            'arxiv': None,
        })

    entries.sort(key=lambda e: (-e['year'], e['title']))

    rows, current = [], None
    for e in entries:
        y = e['year'] or 'Undated'
        if y != current:
            if current is not None:
                rows.append('  </ul>')
            current = y
            rows.append('  <h2>%s</h2>\n  <ul>' % y)
        title = html.escape(e['title'])
        head = '<a href="%s">%s</a>' % (html.escape(e['url']), title) if e['url'] else title
        line = '    <li>%s' % head
        if e['venue']:
            line += '<span class="venue">%s</span>' % html.escape(e['venue'])
        if e['arxiv']:
            line += ' <a class="arxiv" href="https://arxiv.org/abs/%s">arXiv</a>' % e['arxiv']
        if e['authors']:
            line += '<br><span class="meta">%s</span>' % e['authors']
        rows.append(line + '</li>')
    rows.append('  </ul>')

    page = PAGE % {'count': len(entries), 'body': '\n'.join(rows)}
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write(page)
    print('Wrote %s — %d publications from DBLP (%s).' % (args.out, len(entries), args.pid))


PAGE = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Publications — Magnús M. Halldórsson</title>
<style>
  :root{--bg:#fbfaf7;--fg:#1c1e1d;--soft:#5b625f;--faint:#8d9591;
        --rule:#dcdcd6;--link:#1a5f52;--mark:#f0ede4;
        --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
        --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
  @media (prefers-color-scheme:dark){:root{--bg:#14171a;--fg:#e6e9e7;--soft:#a3adaa;
        --faint:#77817e;--rule:#2b3134;--link:#63c3ae;--mark:#1e2427}}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--serif);
       font-size:17px;line-height:1.55;padding:clamp(1.5rem,5vw,4rem) 1.25rem 6rem}
  .wrap{max-width:44rem;margin:0 auto}
  a{color:var(--link);text-decoration:none;border-bottom:1px solid rgba(128,128,128,.35)}
  a:hover{border-bottom-color:currentColor}
  h1{font-size:1.9rem;margin:0 0 .2rem;letter-spacing:-.02em}
  .back{font-family:var(--sans);font-size:.85rem}
  h2{font-family:var(--sans);font-size:.72rem;text-transform:uppercase;letter-spacing:.15em;
     color:var(--faint);font-weight:700;margin:2.2rem 0 .6rem;
     border-bottom:1px solid var(--rule);padding-bottom:.3rem}
  ul{margin:0;padding-left:1.15rem}
  li{margin-bottom:.7rem}
  .venue{font-family:var(--sans);font-size:.76rem;color:var(--faint);background:var(--mark);
         padding:.1rem .4rem;border-radius:3px;margin-left:.35rem}
  .arxiv{font-family:var(--sans);font-size:.76rem;margin-left:.35rem;white-space:nowrap}
  .meta{font-family:var(--sans);font-size:.8rem;color:var(--soft)}
  .note{font-family:var(--sans);font-size:.8rem;color:var(--faint);margin:.4rem 0 2rem}
</style>
</head>
<body>
<div class="wrap">
  <h1>Publications</h1>
  <p class="back"><a href="index.html">&larr; Magnús M. Halldórsson</a></p>
  <p class="note">%(count)d entries, generated from <a href="https://dblp.org/pid/h/MMHalldorsson.html">DBLP</a>. Not hand-maintained.</p>
%(body)s
</div>
</body>
</html>
'''

if __name__ == '__main__':
    main()
