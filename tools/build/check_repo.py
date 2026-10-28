"""Checks the git repository against the official OCS texts (from the cache, no network).

    python -X utf8 scripts/thailand-law/check_repo.py [--repo ../thailand-law] [--no-record]

For every text in force (each day the act changed), read back from git with tools/thai.py's day rule:
1. File by file: the act's files in git on that day are exactly the files the build's parser makes from the OCS
   consolidation of that day (same set of files, same bytes). The one rebuilt text (an amendment consolidated out of
   order, see the README) is checked against its rule instead: every file equals the file of the earlier
   consolidation, or of the consolidation that holds the amendment, or (where both amendments meet) the paragraph
   merge, and nothing else.
2. Word for word, independently of the parser: the letters and digits of the whole act printed by tools/thai.py
   (footnote markers, footnote lines and markdown removed) equal the letters and digits of every text node of the
   OCS's raw section HTML, in order (tags stripped by a regular expression, entities decoded); and the footnotes in
   the files, in order, equal the OCS footnotes in the order their anchors appear in the raw HTML.
Every OCS consolidation is reported: which commit holds it, or why none does.
"""
import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build  # noqa: E402
import ocs  # noqa: E402

KEEP = re.compile(r'[^0-9A-Za-z฀-๿]+')
TAG = re.compile(r'<[^>]+>')
ANCHOR = re.compile(r'href="#foot-([0-9a-f-]+)"')
REPO_MARK = re.compile(r'\[\^\d+\]')
REPO_FN = re.compile(r'^\[\^\d+\]: (.*)$')


def letters(s: str) -> str:
    return KEEP.sub('', html.unescape(s)).casefold()


def official(doc: dict) -> tuple[str, list[str]]:
    secs = sorted(doc['lawSections'], key=lambda s: s['sectionSeq'])
    fns = {f['footnoteUuid']: f['footnoteContent'] for f in doc['footnoteList']}
    body = ''.join(letters(TAG.sub(' ', s['sectionContent'])) for s in secs)
    notes = [letters(fns[u]) for s in secs for u in ANCHOR.findall(s['sectionContent'])]
    return body, notes


def from_repo(text: str) -> tuple[str, list[str]]:
    body, notes = [], []
    for line in text.split('\n'):
        m = REPO_FN.match(line)
        if m:
            notes.append(letters(m.group(1)))
        else:
            body.append(letters(REPO_MARK.sub('', re.sub(r'^#+ ', '', line))))
    return ''.join(body), notes


def tool(repo: str, *args: str) -> str:
    out = subprocess.run([sys.executable, 'tools/thai.py', *args], cwd=repo, capture_output=True, text=True,
                         encoding='utf-8')
    if out.returncode:
        raise SystemExit(f'thai.py {" ".join(args)}: {out.stderr}')
    return out.stdout


def files_at(repo: str, commit: str, slug: str) -> dict[str, str]:
    out = subprocess.run(['git', 'ls-tree', '-r', commit, f'{slug}/'], cwd=repo, capture_output=True,
                         text=True, encoding='utf-8').stdout.split('\n')
    blobs = []
    for line in out:
        if line:
            info, f = line.split('\t', 1)
            if f.endswith('.md') and not f.endswith('/README.md'):
                blobs.append((f[len(slug) + 1:-3], info.split()[2]))
    data = subprocess.run(['git', 'cat-file', '--batch'], cwd=repo, capture_output=True,
                          input=''.join(f'{sha}\n' for _, sha in blobs).encode()).stdout
    res, pos = {}, 0
    for name, _ in blobs:
        nl = data.index(b'\n', pos)
        size = int(data[pos:nl].split()[2])
        res[name] = data[nl + 1:nl + 1 + size].decode('utf-8')
        pos = nl + 1 + size + 1
    return res


def commit_on(repo: str, day: str, slug: str) -> str:
    return subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0, "tools"); import thai; '
                           f'print(thai.commit_on("{day}", "{slug}"))'], cwd=repo, capture_output=True,
                          text=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=str(build.ROOT.parent / 'thailand-law'))
    ap.add_argument('--no-record', action='store_true')
    args = ap.parse_args()
    texts = files = bad = wchecks = wbad = nletters = 0
    report = []
    for act in build.ACTS:
        b = build.load_act(act, offline=True)
        sts = build.states(b)
        held = {}
        for st in sts:
            slug = act['slug']
            commit = commit_on(args.repo, st['day'], slug)
            got = files_at(args.repo, commit, slug)
            expected = {k: u['text'] for k, u in st['units'].items()}
            texts += 1
            files += len(expected)
            if got != expected:
                bad += 1
                diff = sorted(set(got) ^ set(expected)) or [k for k in expected if got.get(k) != expected[k]]
                print(f'MISMATCH {slug} {st["day"]}: {diff[:6]}')
            if 'rebuilt' in st:
                r = st['rebuilt']
                base = r['base']['parsed']['units']
                full = st['version']['parsed']['units']
                for k, u in st['units'].items():
                    ok = (k in r['merged']) or (u['text'] == (full.get(k) or {}).get('text') and k in r['delta']) \
                        or (k not in r['delta'] and u['text'] == (base.get(k) or {}).get('text'))
                    if not ok:
                        bad += 1
                        print(f'REBUILT RULE {slug} {st["day"]} {k}')
                for k in r['merged']:
                    mk = build.merge_file(base[k]['text'], r['later']['parsed']['units'][k]['text'], full[k]['text'])
                    if mk != st['units'][k]['text']:
                        bad += 1
                        print(f'MERGE {slug} {st["day"]} {k}')
                report.append({'act': slug, 'day': st['day'], 'text': 'rebuilt', 'from': [r['base']['code'],
                               st['version']['code'], r['later']['code']], 'merged': r['merged']})
                continue
            v = st['text_of'] if 'missing' in st else st['version']
            held[v['code']] = st['day']
            whole = tool(args.repo, st['day'], slug)
            ob, on = official(v['doc'])
            rb, rn = from_repo(whole)
            wchecks += 1
            nletters += len(ob)
            if ob != rb or on != rn:
                wbad += 1
                i = next((i for i, (x, y) in enumerate(zip(ob, rb)) if x != y), min(len(ob), len(rb)))
                print(f'WORDS {slug} {st["day"]}: {len(ob)} vs {len(rb)} letters, first difference at {i}: '
                      f'{ob[max(0, i - 20):i + 20]!r} / {rb[max(0, i - 20):i + 20]!r}; footnotes {len(on)} vs {len(rn)}'
                      f' {"same" if on == rn else "differ"}')
            report.append({'act': slug, 'day': st['day'], 'text': v['code'], 'ocs_day': v['day']})
        for v in b['versions']:
            if v['code'] not in held:
                st = next((s for s in sts if s['version'] is v), None)
                why = 'consolidated before an amendment in force earlier; superseded by ' + \
                      st['text_of']['code'] if st and 'missing' in st else 'rebuilt (see above)'
                report.append({'act': act['slug'], 'ocs_version': v['code'], 'ocs_day': v['day'], 'not_held': why})
    for r in report:
        print(json.dumps(r, ensure_ascii=False))
    print(f'{texts} texts checked ({files} files), {bad} mismatches; {wchecks} texts word for word '
          f'({nletters} letters), {wbad} mismatches')
    if not args.no_record:
        p = HERE / 'verification.json'
        rec = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        rec['check'] = {'texts': texts, 'files': files, 'mismatches': bad, 'wordcheck': wchecks,
                        'letters': nletters, 'word_mismatches': wbad, 'report': report}
        p.write_text(json.dumps(rec, indent=1, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8',
                     newline='\n')
    raise SystemExit(1 if bad or wbad else 0)


if __name__ == '__main__':
    main()
