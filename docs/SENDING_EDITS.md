# Sending edits from the editor

The Studio's **Send my edits...** button (File menu, and the toolbar) uploads everything added or changed in the packs
since the game came (new sprites, changed tables, `WISHES.txt`, and the recordings in `Custom Maps/compare zips`) to this
repository. **One branch per person**: `edits/<username>`. The first send makes it; every later send adds a commit on top
of it, so the branch's history is a backup of each send and nobody's work mixes with anyone else's. It never writes to
`main`. **Make zip instead** in the same window makes a dated zip.

Inside the branch, everything of a person is in `edits_inbox/<username>/`:

| Folder | Holds |
|---|---|
| `files/` | The new and changed files, with the paths they have in the game folder (copy them over it to use them). |
| `compare zips/` | The recordings of comparisons with the DOS game (`compare_<date>_<name>.zip`, each with its questionnaire in `report.txt`). |
| `latest/WHAT_CHANGED.txt` | The report of the last send (what changed, wishes, the note). |
| `sends/<date-time>/WHAT_CHANGED.txt` | The report of every send. |

The window asks for a **Username** (letters and numbers; you choose it and tell them), their name and the **Key**. All three are
remembered on that computer. After a compare recording is saved, the compare window offers to send it straight away.

## One-time setup (owner)

1. GitHub > Settings > Developer settings > Fine-grained personal access tokens > Generate new token.
   - Resource owner: you; **Only select repositories**: `The-Quest-I-II` only.
   - Repository permissions: **Contents: Read and write**. Nothing else.
   - Set an expiry; make a new one when it runs out.
2. Protect `main`: Settings > Rules > Rulesets > new branch ruleset targeting `main`, requiring a pull request
   (or restrict updates). A key holder can then only create branches, never change `main`.
3. Give the token and a username to your brother. He types them once into the Send window (Username and Key fields). It is stored in
   `~/.quest_editor.json` on his computer, outside the game folder, so it is never zipped or committed.
   Never commit it. To revoke it, delete the token on GitHub.

## Receiving

Look at `edits/<username>` (`edits_inbox/<username>/latest/WHAT_CHANGED.txt` has the report and his wishes; `git log edits/<username>`
lists every send), then merge what you want or hand it to Claude to build the features he asked for. `git branch -r --list 'edits/*'`
lists everyone's branches: one line per person.

## Notes

- Removed files are not sent; only new and changed ones.
- `core/pack_baseline.json` records the shipped pack; regenerate it with `python TheQuestDeluxe-Studio/core/pack_edits.py --baseline`
  whenever the shipped pack changes.

## Keeping the additions safe when the game is updated

The editor saves his work in his own pack, `TheQuestDeluxe/Custom Maps/<name>/` (a copy of the locked `packs/TheQuest`, which the editor
never opens), so a new game dragged over his old one leaves it alone. Edits made before Custom Maps existed (in `packs/TheQuest`)
were replaced by such an update. To make sure nothing is ever lost:

- **Every Save** in the editor makes another zip, `QuestEdits_<date>_<time>.zip`, in the folder `zips` inside `Custom Maps`
  (a new game dragged over the old one leaves `Custom Maps` alone; the first versions used `QuestDeluxeEdits` in the home folder, still read): a copy of the same additions Send my edits sends, plus the changed table rows by number.
  Nothing in the game is moved, and no earlier zip is replaced or deleted (a Save with nothing new makes no new zip).
- **After an update** the editor offers, on start, to put the additions back, merging his rows by number into the new
  game's tables. **File > Restore my saved edits...** does it by hand, from any of those zips (or an old Make Edits Zip zip:
  then only rows that are missing come back).
- **File > Recover pictures without entries** makes a plain "Recovered ..." entry for every picture whose table row is gone,
  so it can be reached and filled in again.
- Better still: make his own pack (File > New pack) and work in that; updates never touch `packs/<his pack>`.
