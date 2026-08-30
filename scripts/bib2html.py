#!/usr/bin/env python3
"""Generate publications.html from BibTeX files.

Standard library only. Point it at one or more .bib files, or at a directory
tree to search:

    python3 scripts/bib2html.py refs.bib
    python3 scripts/bib2html.py ~/Library/CloudStorage/.../Apps/Overleaf
    python3 scripts/bib2html.py *.bib --author Halldorsson

Entries are grouped by year, newest first, and deduplicated by title. Only
entries naming the given author are kept, so pointing it at a whole Overleaf
folder full of other people's bibliographies still does the right thing.

The point is that the list stops going stale: re-run it instead of hand-editing
HTML, which is how the old page ended up three years behind.
"""

import argparse
import html
import re
import sys
import unicodedata
from pathlib import Path

# --------------------------------------------------------------------------
# BibTeX parsing. Not a general parser -- it handles the subset that real
# .bib files in this field actually use.
# --------------------------------------------------------------------------

ENTRY_RE = re.compile(r'@(\w+)\s*\{\s*([^,]*),', re.S)


def strip_braces(value):
    value = value.strip()
    while len(value) > 1 and value[0] in '{"' and value[-1] in '}"':
        value = value[1:-1].strip()
    return value


def clean_tex(value):
    """Turn the common TeX-isms into plain text."""
    repl = {
        r'\\&': '&', r'\\%': '%', r'\\_': '_', r'\\#': '#', r'\\\$': '$',
        r'---': '\u2014', r'--': '\u2013', r'``': '\u201c', r"''": '\u201d',
        r'\\ldots': '\u2026',
    }
    for pat, to in repl.items():
        value = re.sub(pat, to, value)
    # accents: \'{o} \"o \aa etc.
    value = re.sub(r"\\['`^\"~=.]\s*\{?(\w)\}?",
                   lambda m: unicodedata.normalize('NFC', m.group(1)), value)
    value = value.replace(r'\aa', 'å').replace(r'\o', 'ø').replace(r'\ss', 'ß')
    # common math macros, rendered as plain-text unicode rather than dropped
    math_repl = {
        r'\\Delta': 'Δ', r'\\delta': 'δ', r'\\chi': 'χ',
        r'\\varepsilon': 'ε', r'\\epsilon': 'ε',
        r'\\Omega': 'Ω', r'\\omega': 'ω',
        r'\\Theta': 'Θ', r'\\theta': 'θ',
        r'\\Lambda': 'Λ', r'\\lambda': 'λ',
        r'\\times': '×', r'\\leq': '≤', r'\\geq': '≥',
        r'\\le\b': '≤', r'\\ge\b': '≥', r'\\log': 'log', r'\\sqrt': '√',
    }
    for pat, to in math_repl.items():
        value = re.sub(pat + r'\s*', to, value)
    value = re.sub(r'\\[()\[\]]', '', value)          # math delimiters \( \) \[ \]
    value = value.replace('$', '')                    # math delimiters $ ... $
    value = re.sub(r'\\[ ,;:!]', ' ', value)          # TeX spacing: "Proc.\ 38th"
    value = re.sub(r'\\[a-zA-Z]+\s*', '', value)      # leftover macros
    value = value.replace('{', '').replace('}', '')
    return re.sub(r'\s+', ' ', value).strip()


def deaccent(s):
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()


def parse_fields(body):
    """Pull key = value pairs, respecting nested braces."""
    fields, i, n = {}, 0, len(body)
    while i < n:
        m = re.compile(r'(\w+)\s*=\s*').match(body, i)
        if not m:
            i += 1
            continue
        key = m.group(1).lower()
        i = m.end()
        if i < n and body[i] == '{':
            depth, start = 0, i
            while i < n:
                if body[i] == '{':
                    depth += 1
                elif body[i] == '}':
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
            fields[key] = strip_braces(body[start:i])
        elif i < n and body[i] == '"':
            start = i + 1
            i += 1
            while i < n and body[i] != '"':
                i += 1
            fields[key] = body[start:i]
            i += 1
        else:
            start = i
            while i < n and body[i] not in ',}':
                i += 1
            fields[key] = body[start:i].strip()
    return fields


def parse_bib(text):
    out = []
    for m in ENTRY_RE.finditer(text):
        start = m.end()
        depth, i = 1, m.start()
        while i < len(text) and text[i] != '{':
            i += 1
        j, depth = i + 1, 1
        while j < len(text) and depth:
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
            j += 1
        fields = parse_fields(text[start:j - 1])
        fields['_type'] = m.group(1).lower()
        out.append(fields)
    return out


# --------------------------------------------------------------------------

def authors_of(entry):
    raw = clean_tex(entry.get('author', ''))
    if not raw:
        return []
    return [a.strip() for a in re.split(r'\s+and\s+', raw) if a.strip()]


def fmt_authors(names, me):
    out = []
    for name in names:
        if ',' in name:
            last, first = [p.strip() for p in name.split(',', 1)]
            name = first + ' ' + last
        # match without accents, so Halldórsson and Halldorsson both bold
        mine = deaccent(me).lower() in deaccent(name).lower()
        out.append('<strong>%s</strong>' % html.escape(name) if mine else html.escape(name))
    if len(out) > 1:
        return ', '.join(out[:-1]) + ' and ' + out[-1]
    return out[0] if out else ''


def venue_of(entry):
    """Prefer a short conference acronym over a full proceedings title.

    'Proceedings of the 2024 ACM-SIAM Symposium on Discrete Algorithms, SODA
    2024, Alexandria, VA' is accurate and unreadable in a list; 'SODA 2024'
    is what a reader wants. Falls back to the full string when no acronym is
    recognisable.
    """
    for key in ('booktitle', 'journal', 'school', 'publisher', 'howpublished'):
        raw = entry.get(key)
        if not raw:
            continue
        full = clean_tex(raw)
        if key == 'booktitle':
            m = re.search(r"\b([A-Z]{3,6})\s*'?\s*(\d{2,4})\b", full)
            if m:
                return '%s %s' % (m.group(1), m.group(2))
        return full
    return ''


def norm_title(t):
    return re.sub(r'[^a-z0-9]', '', clean_tex(t).lower())


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paths', nargs='+', help='.bib files, or directories to search')
    ap.add_argument('--author', default='Halldorsson',
                    help='keep only entries naming this author (default: Halldorsson)')
    ap.add_argument('-o', '--out', default='publications.html')
    args = ap.parse_args()

    files = []
    for p in args.paths:
        path = Path(p).expanduser()
        if path.is_dir():
            files += sorted(path.rglob('*.bib'))
        elif path.exists():
            files.append(path)
        else:
            print('skipping (not found): %s' % p, file=sys.stderr)

    if not files:
        sys.exit('No .bib files found.')

    entries, seen = [], set()
    for f in files:
        try:
            text = f.read_text(encoding='utf-8', errors='replace')
        except OSError as err:
            print('skipping %s: %s' % (f, err), file=sys.stderr)
            continue
        for e in parse_bib(text):
            names = authors_of(e)
            # match on the accent-free surname so Halldórsson/Halldorsson both hit
            flat = unicodedata.normalize('NFKD', ' '.join(names))
            flat = flat.encode('ascii', 'ignore').decode()
            if args.author.lower() not in flat.lower():
                continue
            key = norm_title(e.get('title', ''))
            if not key or key in seen:
                continue
            seen.add(key)
            entries.append(e)

    def year_of(e):
        m = re.search(r'\d{4}', e.get('year', ''))
        return int(m.group()) if m else 0

    entries.sort(key=lambda e: (-year_of(e), clean_tex(e.get('title', ''))))

    rows, current = [], None
    for e in entries:
        y = year_of(e) or 'Undated'
        if y != current:
            if current is not None:
                rows.append('  </ul>')
            current = y
            rows.append('  <h2>%s</h2>\n  <ul>' % y)
        title = html.escape(clean_tex(e.get('title', 'Untitled')))
        who = fmt_authors(authors_of(e), args.author)
        venue = html.escape(venue_of(e))
        url = e.get('url') or (('https://doi.org/' + e['doi']) if e.get('doi') else '')
        head = '<a href="%s">%s</a>' % (html.escape(url), title) if url else title
        line = '    <li>%s' % head
        if venue:
            line += '<span class="venue">%s</span>' % venue
        if who:
            line += '<br><span class="meta">%s</span>' % who
        rows.append(line + '</li>')
    rows.append('  </ul>')

    page = PAGE % {'count': len(entries), 'body': '\n'.join(rows)}
    Path(args.out).write_text(page, encoding='utf-8')
    print('Wrote %s — %d publications from %d file(s).' % (args.out, len(entries), len(files)))


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
  .meta{font-family:var(--sans);font-size:.8rem;color:var(--soft)}
  .note{font-family:var(--sans);font-size:.8rem;color:var(--faint);margin:.4rem 0 2rem}
</style>
</head>
<body>
<div class="wrap">
  <h1>Publications</h1>
  <p class="back"><a href="index.html">&larr; Magnús M. Halldórsson</a></p>
  <p class="note">%(count)d entries, generated from BibTeX. Not hand-maintained.</p>
%(body)s
</div>
</body>
</html>
'''

if __name__ == '__main__':
    main()
