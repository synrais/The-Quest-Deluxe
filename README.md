# The Quest I-II

Two editions of **The Quest**, a DOS role-playing game by Alex Kutsenok (2001), each in its own folder
and each standing on its own:

| Edition | Folder | What it is |
|---|---|---|
| **The Quest** (classic) | [`TheQuestClassic/`](TheQuestClassic/README.md) | The faithful port, locked. It plays the original exactly, bugs included, and is checked against the original `TheQuest.exe` running in an emulator. The original game itself is kept unzipped in `TheQuestClassic/packs/TheQuest`. |
| **The Quest Deluxe + Studio** | [`TheQuestDeluxe-Studio/`](TheQuestDeluxe-Studio/README.md) | The game and the Quest Studio editor in one standalone folder, with the compare-to-DOS recorder and no old editor. Start here. |
| *The Quest Deluxe* (earlier, archived) | [`archive/TheQuestDeluxe/`](archive/TheQuestDeluxe/README.md) | The extended engine: FPS mode, a combat log, a full quest editor and quest packs for new stories. It needs nothing from `TheQuestClassic/`. Its `packs/TheQuest` is the original quest, converted, and plays the same as the classic port. |

## Playing

On Windows, double-click a launcher in an edition's folder. The first time, it finds Python (or
offers to install it) and sets up pygame-ce:

| Edition | Launchers |
|---|---|
| The Quest | `TheQuestClassic/Play The Quest.bat` |
| The Quest Deluxe + Studio | `TheQuestDeluxe-Studio/Play The Quest Deluxe.bat`, `TheQuestDeluxe-Studio/The Quest Studio.bat` |

Or build the release zips, one per edition, with the same launchers and pygame-ce bundled:

```
python tools/build_release.py 10    ->  dist/TheQuestClassic-10.zip, dist/TheQuestDeluxe-Studio-10.zip
```

From the source, with Python 3.10+ and pygame-ce (`requirements.txt`):

```
python TheQuestClassic/run_quest2.py     The Quest
python TheQuestDeluxe-Studio/run_deluxe.py   The Quest Deluxe (standalone)
python TheQuestDeluxe-Studio/run_studio.py   The Quest Studio (needs tkinter)
```

## The repository

| Folder | Holds |
|---|---|
| editor's **Send my edits...** button | Sends what was added in the editor (new pictures, items, creatures, spells, tiles, maps, wishes) to the repository as a branch of its own, or makes a dated `QuestEdits_<date>_<time>.zip` instead (**Make zip instead**). See `docs/SENDING_EDITS.md`. `TheQuestDeluxe-Studio/core/pack_edits.py` does the gathering (`--all` packs every pack whole; `--baseline` re-records the shipped pack it compares with; the tests fail until you do, after changing the shipped pack). |
| `TheQuestClassic/` | The faithful port: `engine/` (its code), `packs/TheQuest/` (the original as released), `sprites/`, its reverse-engineering tools and exe verifiers (`tools/re/`), notes and tests. |
| `archive/TheQuestDeluxe/` | The earlier Quest Deluxe with its first editor, kept for reference (not built, not updated): `engine/` (its code), `editor/`, `studio/`, `packs/`, `docs/`, tests and `tools/make_pack.py`. |
| `TheQuestDeluxe-Studio/` | The standalone Quest Deluxe and The Quest Studio, with no old editor: `engine/`, `studio/` (the editor), `core/` (what it works on), `compare/` and `dos/` (the comparison with The Quest DOS), `packs/`, `docs/` and its own tests. |
| `docs/` | Everything learned along the way: [findings about the original](docs/FINDINGS.md), [how the ports are verified](docs/VERIFICATION.md) and [the project's decisions and plans](docs/PROJECT.md). Start at [docs/README.md](docs/README.md). |
| `tests/` | The checks between the two editions: [`lockstep.py`](tests/lockstep.py) plays both side by side on random keys and requires the same screens and game state after every key; `test_view3d.py` and `test_combat_log.py` build on it to show that FPS mode and the combat log change nothing. |
| `tools/` | `build_release.py` (one Windows zip per edition) and `launcher.bat`, the double-click launcher it adapts for each program (`python tools/build_release.py --launchers` rewrites the ones in the edition folders). |

The reverse-engineering tools also need `capstone` and `unicorn`.
