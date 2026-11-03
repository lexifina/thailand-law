# How this repository was made

Everything here is generated from the data of one source. No AI wrote or edited legal text, and no model
runs when the repository is built.

## Source

- The Office of the Council of State (สำนักงานคณะกรรมการกฤษฎีกา, OCS), law database
  <https://searchlaw.ocs.go.th/council-of-state/>: for each act, the act as enacted (ฉบับหลัก), each
  amending act (ฉบับแก้ไข) and the consolidated text of each day the act changed (ฉบับปรับปรุง), each
  with the day it took effect, as the site's own document view serves them.
- No terms of use are published on ocs.go.th (its policy pages cover privacy and data governance only).
- Thai Copyright Act B.E. 2537 (1994), section 7: Acts, the Constitution and official texts of law are not
  copyright works.
- Gazette references are the ones the OCS prints in its footnotes.

## Acts

| Folder | Title | English | Texts in force | First | Last |
| --- | --- | --- | ---: | --- | --- |
| `constitution` | รัฐธรรมนูญแห่งราชอาณาจักรไทย | Constitution of the Kingdom of Thailand, B.E. 2560 (2017) | 2 | 2017-04-06 | 2021-11-22 |
| `labour-protection` | พระราชบัญญัติคุ้มครองแรงงาน พ.ศ. 2541 | Labour Protection Act, B.E. 2541 (1998) | 13 | 1998-08-19 | 2025-12-07 |
| `labour-relations` | พระราชบัญญัติแรงงานสัมพันธ์ พ.ศ. 2518 | Labour Relations Act, B.E. 2518 (1975) | 6 | 1975-03-28 | 2023-10-25 |
| `criminal-code` | ประมวลกฎหมายอาญา | Criminal Code | 35 | 1956-11-16 | 2025-12-30 |
| `civil-commercial-code` | ประมวลกฎหมายแพ่งและพาณิชย์ | Civil and Commercial Code | 38 | 1926-01-01 | 2025-03-25 |
| `civil-procedure-code` | ประมวลกฎหมายวิธีพิจารณาความแพ่ง | Civil Procedure Code | 35 | 1935-06-20 | 2025-09-10 |

## Growth

The history is append-only. Acts added after the first build are appended after the published head, each
act's commits in in-force order, so `git log` order is not date order across acts: read the `In-force:`
trailer (tools/thai.py does). Commits for days before 1970 carry the date 1 January 1970 (git cannot store
earlier dates) and say so in the message.

- This growth (2026-11-03): 35 law commits for civil-procedure-code, and 1 documentation commit.
- check_repo: 32 texts (13029 files), 0 mismatches; 24 texts word for word (6125275 letters), 0 mismatches.
- Second append from the same head into a scratch clone: identical = true (39 commits).

## Decisions made by hand

- Where the OCS lists no amending act for a day, the change is credited to the instrument its
  consolidation of that day newly reprints at the end; each such commit says so and counts how many
  changed files name it. Where it names none, the publisher is the author and no law is credited.
- Where the OCS consolidated an amendment after a later one, the earlier day's text is rebuilt from the
  text before it plus only that amendment's files; the commit says so (`Text:` trailer).
- Files that differ only in spacing are committed with the change of that day and listed as
  `Respaced:`, not `Affecting:`.

## What the AI did

Claude Code with Claude Opus 5.5 (`claude-opus-5-5`) found the source, checked its terms, and wrote the
scripts. It did not write or edit any legal text; commit message wording comes from templates, and no
model runs at build time.
