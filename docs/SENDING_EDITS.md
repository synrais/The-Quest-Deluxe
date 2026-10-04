# Sending edits from the editor

The editor's **Send my edits...** button (toolbar, and Help menu) uploads everything added or changed in the packs
since the game came (new sprites, changed tables, `WISHES.txt`) to this repository as a **new branch**
`edits/<name>-<date>`. It never writes to `main`. **Make zip instead** in the same window makes the dated zip as before
.

## One-time setup (owner)

1. GitHub > Settings > Developer settings > Fine-grained personal access tokens > Generate new token.
   - Resource owner: you; **Only select repositories**: `The-Quest-I-II` only.
   - Repository permissions: **Contents: Read and write**. Nothing else.
   - Set an expiry; make a new one when it runs out.
2. Protect `main`: Settings > Rules > Rulesets > new branch ruleset targeting `main`, requiring a pull request
   (or restrict updates). A key holder can then only create branches, never change `main`.
3. Give the token to your brother. He pastes it once into the Send window (Key field). It is stored in
   `~/.quest_editor.json` on his computer, outside the game folder, so it is never zipped or committed.
   Never commit it. To revoke it, delete the token on GitHub.

## Receiving

Look at the branch (`edits_inbox/<name>-<date>/WHAT_CHANGED.txt` has the report and his wishes), then merge it
or hand it to Claude to build the features he asked for.

## Notes

- Removed files are not sent; only new and changed ones.
- `editor/pack_baseline.json` records the shipped pack; regenerate it with `python TheQuestDeluxe/editor/pack_edits.py --baseline`
  whenever the shipped pack changes.

## Keeping the additions safe when the game is updated

The editor saves his work in his own pack, `TheQuestDeluxe/Custom Maps/<name>/` (a copy of the locked `packs/TheQuest`, which the editor
never opens), so a new game dragged over his old one leaves it alone. Edits made before Custom Maps existed (in `packs/TheQuest`)
were replaced by such an update. To make sure nothing is ever lost:

- **Every Save** in the editor makes another zip, `QuestEdits_<date>_<time>.zip`, in `QuestDeluxeEdits` in his home folder
  (outside the game folder): a copy of the same additions Send my edits sends, plus the changed table rows by number.
  Nothing in the game is moved, and no earlier zip is replaced or deleted (a Save with nothing new makes no new zip).
- **After an update** the editor offers, on start, to put the additions back, merging his rows by number into the new
  game's tables. **File > Restore my saved edits...** does it by hand, from any of those zips (or an old Make Edits Zip zip:
  then only rows that are missing come back).
- **File > Recover pictures without entries** makes a plain "Recovered ..." entry for every picture whose table row is gone,
  so it can be reached and filled in again.
- Better still: make his own pack (File > New pack) and work in that; updates never touch `packs/<his pack>`.
