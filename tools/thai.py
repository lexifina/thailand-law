"""Read Thai law in this repository as it stood on a day. Standard library only.

    python tools/thai.py <YYYY-MM-DD> <act> [<section>]      the act (or one section) in force that day
    python tools/thai.py changes <act> <section>             every change to a section: day, instrument, commit

<act> is a folder: constitution, labour-protection. <section> is a section number as the Thai text writes it in
Arabic digits (83, 11/1), or a file name without .md (title, end/03).

The version is chosen by the In-force trailer of each commit (the day the change took effect), never by commit
dates, so the answer does not depend on the reader's time zone.
"""
import re
import subprocess
import sys


def git(*args: str) -> str:
    out = subprocess.run(['git', *args], capture_output=True, text=True, encoding='utf-8')
    if out.returncode:
        raise SystemExit(out.stderr.strip())
    return out.stdout


def history(act: str) -> list[tuple[str, str]]:
    """(in-force day, commit) of every commit that changed the act, oldest first."""
    out = git('log', '--no-merges', '--reverse', '--format=%H%x09%(trailers:key=In-force,valueonly,separator=)',
              'main', '--', f'{act}/')
    rows = []
    for line in out.split('\n'):
        if line.strip():
            h, day = line.split('\t')
            rows.append((day.strip(), h))
    return rows


def commit_on(day: str, act: str) -> str | None:
    best = None
    for d, h in history(act):
        if d <= day:
            best = h
    return best


def key_of(section: str) -> str:
    m = re.fullmatch(r'(\d+)(?:/(\d+))?', section)
    if not m:
        return section
    return f's-{int(m.group(1)):03d}' + (f'-{m.group(2)}' if m.group(2) else '')


def order(path: str) -> tuple:
    name = path.rsplit('/', 1)[-1][:-3] if path.count('/') == 1 else path.split('/', 1)[1][:-3]
    if name == 'title':
        return (0,)
    m = re.fullmatch(r's-(\d+)(?:-(\d+))?', name)
    if m:
        return (1, int(m.group(1)), int(m.group(2) or 0))
    m = re.fullmatch(r'end/(\d+)', name)
    if m:
        return (2, int(m.group(1)))
    return (3, name)


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[0] == 'changes':
        act, key = argv[1], key_of(argv[2])
        out = git('log', '--no-merges', '--reverse', '--format=%(trailers:key=In-force,valueonly,separator=)%x09%an%x09%h',
                  'main', '--', f'{act}/{key}.md')
        if not out.strip():
            print(f'no such provision: {act}/{key}.md', file=sys.stderr)
            return 1
        sys.stdout.write(out)
        return 0
    if len(argv) not in (2, 3) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', argv[0]):
        print(__doc__, file=sys.stderr)
        return 2
    day, act = argv[0], argv[1]
    h = commit_on(day, act)
    if h is None:
        first = history(act)
        print(f'{act} was not in force on {day}' + (f' (first in force {first[0][0]})' if first else ''),
              file=sys.stderr)
        return 1
    if len(argv) == 3:
        key = key_of(argv[2])
        out = subprocess.run(['git', 'show', f'{h}:{act}/{key}.md'], capture_output=True, text=True, encoding='utf-8')
        if out.returncode:
            print(f'{act}/{key}.md did not exist on {day}', file=sys.stderr)
            return 1
        sys.stdout.write(out.stdout)
        return 0
    files = [f for f in git('ls-tree', '-r', '--name-only', h, f'{act}/').split('\n')
             if f.endswith('.md') and not f.endswith('/README.md')]
    files = sorted(files, key=order)
    data = subprocess.run(['git', 'cat-file', '--batch'], capture_output=True,
                          input=''.join(f'{h}:{f}\n' for f in files).encode('utf-8')).stdout
    pos = 0
    for _ in files:
        nl = data.index(b'\n', pos)
        size = int(data[pos:nl].split()[2])
        sys.stdout.write(data[nl + 1:nl + 1 + size].decode('utf-8') + '\n')
        pos = nl + 1 + size + 1
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main(sys.argv[1:]))
