"""Functional smoke test of the built Thai law repository: the things a reader does with it work. Standard library only.

    python -X utf8 scripts/thailand-law/test_repo.py [--repo ../thailand-law] [--record]
    python -X utf8 tools/build/test_repo.py             # from inside the repository

It asserts that:
1. `git blame` on a changed section names instruments (Gazette addresses) as authors of its lines;
2. tools/thai.py gives the text before and after a known amendment, and each equals the file at that day's tag;
3. `git log --follow` on a file lists its changes in the order they took effect;
4. every tag resolves to a commit, every commit has an `In-force:` trailer, and every trailer block parses;
5. no commit is authored by Lexifina except the documentation commit (the last one);
6. every command in the README's table runs and prints something;
7. the working tree is clean.
With --record the result is written to verification.json next to this script (for REPRODUCE.md).
"""
import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EMAIL = re.compile(r'^rg-\d+-(sp)?\d+[abcd]-\d+@ratchakitcha\.invalid$')


def default_repo() -> Path:
    if HERE.name == 'build' and HERE.parent.name == 'tools':
        return HERE.parent.parent
    return HERE.parents[2] / 'thailand-law'


class Smoke:
    def __init__(self, repo: Path):
        self.repo = repo
        self.results: list[tuple[str, bool, str]] = []

    def git(self, *args: str) -> str:
        out = subprocess.run(['git', *args], cwd=self.repo, capture_output=True, text=True, encoding='utf-8')
        if out.returncode:
            raise AssertionError(f'git {" ".join(args)}: {out.stderr.strip()}')
        return out.stdout

    def tool(self, *args: str) -> str:
        out = subprocess.run([sys.executable, 'tools/thai.py', *args], cwd=self.repo, capture_output=True, text=True,
                             encoding='utf-8')
        if out.returncode:
            raise AssertionError(f'thai.py {" ".join(args)}: {out.stderr.strip()}')
        return out.stdout

    def check(self, name: str, fn):
        try:
            detail = fn() or ''
            self.results.append((name, True, detail))
            print(f'PASS {name}: {detail}')
        except AssertionError as exc:
            self.results.append((name, False, str(exc)))
            print(f'FAIL {name}: {exc}')

    def blame(self):
        out = self.git('blame', '--line-porcelain', 'main', '--', 'labour-protection/s-005.md')
        mails = {l[12:].strip('<>') for l in out.splitlines() if l.startswith('author-mail ')}
        assert mails and all(EMAIL.match(m) for m in mails), f'unexpected authors {mails}'
        assert len(mails) >= 3, f'only {mails}'
        return f'labour-protection/s-005.md lines by {len(mails)} instruments'

    def on_date(self):
        done = []
        for act, sec, path, before, after, tag in [
                ('constitution', '83', 'constitution/s-083.md', '2021-11-21', '2021-11-22', 'constitution/2021-11-22'),
                ('labour-protection', '118', 'labour-protection/s-118.md', '2019-05-04', '2019-05-05',
                 'labour-protection/2019-05-05')]:
            a, b = self.tool(before, act, sec), self.tool(after, act, sec)
            assert a != b, f'{act} {sec}: same text on {before} and {after}'
            at = self.git('show', f'{tag}:{path}')
            assert b == at, f'{act} {sec} on {after} differs from {tag}'
            done.append(f'{act} s.{sec} {before}->{after}')
        r = subprocess.run([sys.executable, 'tools/thai.py', '1990-01-01', 'labour-protection'], cwd=self.repo,
                           capture_output=True, text=True, encoding='utf-8')
        assert r.returncode == 1 and 'not in force' in r.stderr, 'no refusal before the act was in force'
        return '; '.join(done) + '; refuses 1990'

    def follow(self):
        out = self.git('log', '--follow', '--format=%(trailers:key=In-force,valueonly,separator=)', 'main', '--',
                       'labour-protection/s-118.md')
        days = [d.strip() for d in out.split('\n') if d.strip()]
        assert len(days) >= 2 and days == sorted(days, reverse=True), f'not in date order: {days}'
        return f's-118: {len(days)} changes, newest first, in date order'

    def tags_and_trailers(self):
        tags = self.git('tag').split()
        for t in tags:
            self.git('rev-parse', '--verify', f'{t}^{{commit}}')
        rows = self.git('log', '--format=%H%x00%B%x01', 'main').split('\x01')
        n = 0
        for r in rows:
            if not r.strip():
                continue
            h, body = r.strip('\n').split('\x00', 1)
            parsed = subprocess.run(['git', 'interpret-trailers', '--parse'], cwd=self.repo, input=body.encode('utf-8'),
                                    capture_output=True).stdout.decode('utf-8')
            assert re.search(r'^In-force: \d{4}-\d{2}-\d{2}$', parsed, re.M), f'{h}: no In-force trailer parsed'
            n += 1
        days = [d.strip() for d in self.git('log', '--reverse', '--format=%(trailers:key=In-force,valueonly,separator=)',
                                            'main').split('\n') if d.strip()]
        assert days == sorted(days), 'In-force days go backwards'
        return f'{len(tags)} tags resolve; {n} commits with parsed In-force, in order'

    def lexifina(self):
        rows = [l.split('\t') for l in self.git('log', '--format=%an\t%ae', 'main').split('\n') if l]
        lex = [i for i, (a, e) in enumerate(rows) if a == 'Lexifina']
        assert lex == [0], f'Lexifina authors commits {lex}'
        others = rows[1:]
        assert all(EMAIL.match(e) or e == 'ocs@ocs.invalid' for _, e in others), 'bad author email'
        return f'only the documentation commit is by Lexifina; {len(others)} by instruments'

    def readme(self):
        text = (self.repo / 'README.md').read_text(encoding='utf-8')
        cmds = re.findall(r'^\| [^|]+ \| `([^`]+)` \|$', text, re.M)
        assert cmds, 'no commands in README'
        for c in cmds:
            args = shlex.split(c)
            if args[0] == 'python':
                args[0] = sys.executable
            out = subprocess.run(args, cwd=self.repo, capture_output=True, text=True, encoding='utf-8')
            assert out.returncode == 0 and out.stdout.strip(), f'{c}: {out.stderr.strip()[:200]}'
        return f'{len(cmds)} README commands run'

    def clean(self):
        st = self.git('status', '--porcelain')
        assert not st.strip(), f'dirty: {st[:200]}'
        return 'working tree clean'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=str(default_repo()))
    ap.add_argument('--record', action='store_true')
    args = ap.parse_args()
    s = Smoke(Path(args.repo))
    for name, fn in [('blame', s.blame), ('on-date', s.on_date), ('follow', s.follow),
                     ('tags-and-trailers', s.tags_and_trailers), ('lexifina-only-docs', s.lexifina),
                     ('readme-commands', s.readme), ('clean', s.clean)]:
        s.check(name, fn)
    passed = sum(1 for _, ok, _ in s.results if ok)
    print(f'{passed} of {len(s.results)} passed')
    if args.record:
        p = HERE / 'verification.json'
        rec = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        rec['tests'] = {'passed': passed, 'total': len(s.results),
                        'results': [{'name': n, 'ok': ok, 'detail': d} for n, ok, d in s.results]}
        p.write_text(json.dumps(rec, indent=1, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8',
                     newline='\n')
    raise SystemExit(0 if passed == len(s.results) else 1)


if __name__ == '__main__':
    main()
