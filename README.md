# Thai law, change by change

Two Thai laws as a git repository: the Constitution of the Kingdom of Thailand B.E. 2560 (2017)
(รัฐธรรมนูญแห่งราชอาณาจักรไทย) and the Labour Protection Act B.E. 2541 (1998) (พระราชบัญญัติคุ้มครองแรงงาน).
Each amending instrument is one commit, credited to it and dated the day it took effect, at noon in Bangkok. The text
is the consolidated text published by the Office of the Council of State (สำนักงานคณะกรรมการกฤษฎีกา, the OCS) at
<https://searchlaw.ocs.go.th/council-of-state/>.

## The questions, as commands

| Question | Command |
| --- | --- |
| What did section 83 of the Constitution say on 1 January 2020? | `python tools/thai.py 2020-01-01 constitution 83` |
| And after the 2021 amendment? | `python tools/thai.py 2021-11-22 constitution 83` |
| The whole Labour Protection Act on 1 January 2010 | `python tools/thai.py 2010-01-01 labour-protection` |
| Every change to section 118 (severance pay), with the day and the instrument | `python tools/thai.py changes labour-protection 118` |
| Which instrument wrote each paragraph of section 5 (definitions)? | `git blame labour-protection/s-005.md` |
| The words each change made to section 118 | `git log -p --word-diff labour-protection/s-118.md` |
| Everything that changed on one day | `git show --stat labour-protection/2019-05-05` |
| Everything one Gazette instrument did | `git show --stat rg/136-43a-21` |
| Changes credited to the instrument the OCS reprints (no amending act listed) | `git log --format="%as %an" --grep="^Evidence: OCS consolidation of this day newly reprints"` |
| The instruments with all their dates | [`laws.csv`](laws.csv) |

Use `tools/thai.py`, not `git rev-list --before=`: it picks the version by the `In-force:` trailer, so the answer does
not depend on your time zone. After a rebuild, refresh tags with `git fetch --force --tags`.

## The dates

A Thai act is published in the Royal Gazette (ราชกิจจานุเบกษา) and takes effect on the day its section 2 sets
(often the day after publication, or 30, 90, 180 days later). **Commits are dated the day the change took effect**, at
noon in Bangkok (UTC+7), as the OCS dates each consolidated text. `Promulgated:` is the day of publication in the
Gazette and `Gazette:` the Gazette reference (volume, issue, page, date), both as the OCS prints them.

## What "author" means

The author of a commit is the instrument that made the change: an amending act, a royal decree, an NCPO order or a
general act. Its address is made of its Gazette reference, `rg-<volume>-<issue><section letter>-<page>@ratchakitcha.invalid`
(a = ก, b = ข, c = ค, d = ง; `sp` for a special issue), which cannot exist. The committer is always `Lexifina`.

The OCS keeps each act as a list of texts: the act as enacted, each amending act, and one consolidated text for each
day the act changed. A change is credited to the amending act the OCS lists for that day (`Evidence: OCS timeline
lists this amending act in force this day`). For four days the OCS lists none; there the change is credited to the
instrument whose provisions that day's consolidation newly reprints at its end, and whose name the changed text's
footnotes or notes carry (`Evidence: OCS consolidation of this day newly reprints this instrument`). Every change
commit counts how many of the changed files name the instrument (`Files-naming-it:`).

Blame credits whole paragraphs; use `git log -p --word-diff` for the words.

### One text rebuilt (Labour Protection Act, 2008)

Act No. 3 B.E. 2551 took effect on 2008-02-28 and Act No. 2 B.E. 2551 on 2008-05-27, but the OCS consolidated No. 3
after No. 2: its text dated 2008-02-28 also prints No. 2's changes, and its text dated 2008-05-27 lacks No. 3. Here
the 2008-02-28 commit is the 2002 text plus only the files that No. 3 changed (in section 5, which both acts change,
only the paragraphs No. 3 changed), and the 2008-05-27 commit is the OCS text dated 2008-02-28, which holds both.
Both commits say so (`Text:` trailers).

## Files

Each act is a folder. Each section (มาตรา) is one file: `s-083.md` is มาตรา ๘๓, `s-011-1.md` is มาตรา ๑๑/๑. The
headings of the chapters and parts (หมวด, ส่วน) that begin with a section are `##` lines at its top. `title.md` holds
the title, the royal name and date and the preamble. Everything the consolidation prints after the main text is in
`end/`, numbered in its order: the countersignature, the fee schedule, the note of reasons (หมายเหตุ), and, for each
amending instrument, the provisions of it the OCS reprints (its commencement and transitional provisions) and its
note. Each paragraph is one line. A footnote of the OCS (the Gazette reference, or the note naming the amending act)
is a marker `[^n]` and a line `[^n]: ...` at the end of the file. The text keeps Thai digits, as published.

## What it does not show

- Only what the OCS consolidates. Its consolidations are not the official text: the Royal Gazette is.
- Changes by instruments that do not alter the words (a ministerial regulation made under the act, a court ruling)
  are not here.
- The text before the Constitution of 2017 and other acts are not here.

## How it is checked

`tools/build/check_repo.py` reads every text in force back from git on its day and compares it with the OCS text,
file by file and, independently of the parser, letter by letter against the raw HTML the OCS serves.
`tools/build/test_repo.py` checks that the commands above work. See [`REPRODUCE.md`](REPRODUCE.md).

## Licence

The texts of Thai acts are not copyright works (Copyright Act B.E. 2537, section 7). The arrangement, scripts and
documentation are by Lexifina; see [LICENSE](LICENSE). This repository is private.
