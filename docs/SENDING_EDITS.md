# Sending edits from the editor

The editor's **Send my edits...** button (toolbar, and Help menu) uploads everything added or changed in the packs
since the game came (new sprites, changed tables, `WISHES.txt`) to this repository as a **new branch**
`edits/<name>-<date>`. It never writes to `main`. **Make zip instead** in the same window makes the dated zip as before
(`Make Edits Zip.bat` still works too).

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
- `editor/pack_baseline.json` records the shipped pack; regenerate it with `python tools/pack_edits_zip.py --baseline`
  whenever the shipped pack changes.
