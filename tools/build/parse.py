"""Turning one OCS law version (getLawDoc JSON) into files.

A version is a list of sections in document order, each with a type (sectionTypeId) and an HTML body:
  1 title (ชื่อกฎหมาย) -- also the title of each amending instrument whose own provisions the consolidation reprints
    after the main text (its transitional provisions), 2 royal name and date (พระปรมาภิไธย), 3 preamble (คำปรารภ),
  4 section (มาตรา), 8 chapter (หมวด), 9 part (ส่วน), 10 clause (ข้อ), 13 transitional provisions (บทเฉพาะกาล),
  14 countersignature (ผู้รับสนองพระบรมราชโองการ), 15 note (หมายเหตุ, the reasons for the act), 16 fee schedule.
Footnotes (the Gazette reference of each instrument, and "มาตรา ๘๓ แก้ไขเพิ่มเติมโดย..." notes naming the amending act)
are anchored in the HTML by <span href="#foot-<uuid>" class="footnote-detect">.

Files: the main text is one file per section (s-083.md = มาตรา ๘๓, s-011-1.md = มาตรา ๑๑/๑), with the headings of the
chapters and parts that begin with it on top; title.md (title, royal name, preamble), and one file for each block
the consolidation reprints after the main text: end/<n>.md (n = its place, 01, 02, ...: the countersignature, the
note, and each amending instrument's reprinted provisions, in the order the consolidation prints them).
Each <p> is one line; text nodes are joined as they stand, runs of white space become one space. A footnote anchor
gets a marker [^n] after its text, and the file ends with the footnote lines `[^n]: <text>`.
"""
from __future__ import annotations

import html
import re

from lxml import etree, html as lhtml

WS = re.compile(r'[ \t\r\n ​   ﻿]+')
BLOCK = {'p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'tbody', 'thead', 'ol', 'ul', 'br',
         'blockquote', 'section', 'td', 'th'}
THAI_DIGITS = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')


class Lines:
    def __init__(self):
        self.lines: list[str] = []
        self.cur: list[str] = []

    def text(self, s: str):
        if s:
            self.cur.append(s)

    def brk(self):
        t = WS.sub(' ', ''.join(self.cur)).strip()
        if t:
            self.lines.append(t)
        self.cur = []


def render_html(src: str, notes: list, fn_index: dict) -> list[str]:
    """The lines of one section's HTML. Table rows become `| a | b |` lines. A footnote anchor appends [^n]."""
    if not src.strip():
        return []
    root = lhtml.fragment_fromstring(src, create_parent='div')
    out = Lines()

    def walk(e):
        tag = e.tag if isinstance(e.tag, str) else ''
        if tag in ('script', 'style'):
            return
        if tag == 'tr':
            out.brk()
            cells = []
            for td in e:
                if isinstance(td.tag, str) and td.tag in ('td', 'th'):
                    sub = Lines()
                    _inline(td, sub, notes, fn_index)
                    sub.brk()
                    cells.append(' '.join(sub.lines))
            out.lines.append('| ' + ' | '.join(cells) + ' |')
            return
        if tag in BLOCK:
            out.brk()
        if tag == 'span' and 'footnote-detect' in (e.get('class') or ''):
            _inline(e, out, notes, fn_index)
            out.text(_mark(e, notes, fn_index))
        else:
            out.text(e.text or '')
            for c in e:
                walk(c)
                out.text(c.tail or '')
        if tag in BLOCK:
            out.brk()

    walk(root)
    out.brk()
    return out.lines


def _inline(e, out: Lines, notes, fn_index):
    """All text below e, flattened (used inside table cells and footnote anchors)."""
    if isinstance(e.tag, str) and e.tag == 'br':
        out.text(' ')
    out.text(e.text or '')
    for c in e:
        if isinstance(c.tag, str) and 'footnote-detect' in (c.get('class') or '') and c.get('href'):
            _inline(c, out, notes, fn_index)
            out.text(_mark(c, notes, fn_index))
        else:
            _inline(c, out, notes, fn_index)
        out.text(c.tail or '')


def _mark(e, notes: list, fn_index: dict) -> str:
    href = e.get('href') or ''
    uid = href[len('#foot-'):] if href.startswith('#foot-') else ''
    if uid not in fn_index:
        raise SystemExit(f'footnote anchor {href!r} has no footnote')
    notes.append(uid)
    return f'[^{len(notes)}]'


SECTION_NO = re.compile(r'(\d+)(?:/(\d+))?')


def section_key(no: str) -> str:
    """'83' -> 's-083', '11/1' -> 's-011-1'."""
    m = SECTION_NO.fullmatch(no or '')
    if not m:
        raise SystemExit(f'unexpected section number {no!r}')
    return f's-{int(m.group(1)):03d}' + (f'-{m.group(2)}' if m.group(2) else '')


def key_order(key: str) -> tuple:
    if key == 'title':
        return (0,)
    m = re.fullmatch(r's-(\d+)(?:-(\d+))?', key)
    if m:
        return (1, int(m.group(1)), int(m.group(2) or 0))
    m = re.fullmatch(r'end/(\d+)', key)
    if m:
        return (2, int(m.group(1)))
    raise SystemExit(f'unknown key {key}')


HEADINGS = {'8': '##', '9': '###'}


def read_version(doc: dict) -> dict:
    """{'units': {key: {'key','label','text','notes': [footnote text]}}, 'order': [...]}"""
    fns = {f['footnoteUuid']: f for f in doc['footnoteList']}
    units: dict[str, dict] = {}
    order: list[str] = []
    pending: list[str] = []
    pending_notes: list = []
    phase = 'head'          # head -> main -> end
    cur = None

    def new(key, label):
        nonlocal cur
        if key in units:
            raise SystemExit(f'duplicate unit {key}')
        cur = {'key': key, 'label': label, 'lines': [], 'notes': []}
        units[key] = cur
        order.append(key)

    secs = sorted(doc['lawSections'], key=lambda s: s['sectionSeq'])
    if [s['sectionSeq'] for s in secs] != list(range(1, len(secs) + 1)):
        raise SystemExit('section sequence has gaps')
    for s in secs:
        t = s['sectionTypeId']
        notes_here: list = []
        lines = render_html(s['sectionContent'], notes_here, fns)
        if phase == 'head':
            if t == '1' and not units:
                new('title', 'ชื่อกฎหมาย')
            elif t in ('2', '3') and cur is not None and cur['key'] == 'title':
                pass
            elif t in ('8', '9', '4'):
                phase = 'main'
            else:
                raise SystemExit(f'unexpected section type {t} before the main text')
        if phase == 'main':
            if t in HEADINGS:
                pending.extend(f'{HEADINGS[t]} {l}' for l in lines)
                pending_notes.extend(notes_here)
                continue
            if t == '4':
                new(section_key(s.get('sectionNo')), s.get('sectionLabel') or '')
                if pending:
                    cur['lines'].extend(pending)
                    cur['notes'].extend(pending_notes)
                    pending.clear()
                    pending_notes.clear()
            elif t in ('13',) and not pending:
                # บทเฉพาะกาล heading inside the main text: kept as a heading of the next section
                pending.extend(f'## {l}' for l in lines)
                pending_notes.extend(notes_here)
                continue
            else:
                if pending:
                    raise SystemExit(f'headings with no section after them: {pending[:2]}')
                phase = 'end'
        if phase == 'end':
            if t in ('1', '14', '15', '16') or cur is None or not cur['key'].startswith('end/'):
                n = sum(1 for k in units if k.startswith('end/')) + 1
                new(f'end/{n:02d}', s.get('sectionLabel') or '')
            if t in HEADINGS or t == '13':
                lines = [f'## {l}' for l in lines]
        cur['lines'].extend(lines)
        cur['notes'].extend(notes_here)
    if pending:
        raise SystemExit('headings at the end with no section after them')
    for k in order:
        u = units[k]
        body = list(u['lines'])
        if u['notes']:
            body.append('')
            body.extend(f'[^{i}]: {WS.sub(" ", fns[n]["footnoteContent"]).strip()}' for i, n in enumerate(u['notes'], 1))
        # markers were numbered per section; renumber per file
        u['text'] = renumber(_join(body)) + '\n'
        u['footnotes'] = [fns[n]['footnoteContent'] for n in u['notes']]
    used = {n for u in units.values() for n in u['notes']}
    unused = [f for f in doc['footnoteList'] if f['footnoteUuid'] not in used]
    return {'units': units, 'order': order, 'unused_footnotes': unused}


def _join(body: list[str]) -> str:
    out = []
    for l in body:
        if l == '':
            continue
        out.append(l)
    return '\n\n'.join(out)


MARK = re.compile(r'\[\^(\d+)\](?!:)')


def renumber(text: str) -> str:
    """Markers were numbered per HTML section; number them 1, 2, ... through the file, in order, matching the
    footnote lines (which are already in that order)."""
    n = [0]

    def rep(m):
        n[0] += 1
        return f'[^{n[0]}]'
    return MARK.sub(rep, text)
