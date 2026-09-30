# The Quest I-II

Two editions of **The Quest**, a DOS role-playing game by Alex Kutsenok (2001), each in its own folder
and each standing on its own:

| Edition | Folder | What it is |
|---|---|---|
| **The Quest** (classic) | [`classic/`](classic/README.md) | The faithful port, locked. It plays the original exactly, bugs included, and is checked against the original `TheQuest.exe` running in an emulator. The original game itself is kept unzipped in `classic/packs/TheQuest`. |
| **The Quest Deluxe** | [`TheQuestDeluxe/`](TheQuestDeluxe/README.md) | The extended engine: FPS mode, a combat log, a full quest editor and quest packs for new stories. It needs nothing from `classic/`. Its `packs/TheQuest` is the original quest, converted, and plays the same as the classic port. |

## Playing

On Windows, build the release zips and double-click a launcher (it finds or installs Python, then
pygame-ce, the first time):

```
python tools/build_release.py 8        ->  dist/TheQuest-Classic-8.zip     "Play The Quest.bat"
                                            dist/TheQuestDeluxe-8.zip      "Play The Quest Deluxe.bat",
                                                                           "The Quest Deluxe Editor.bat"
```

From the source, with Python 3.10+ and pygame-ce (`requirements.txt`):

```
python classic/run_quest2.py               The Quest
python TheQuestDeluxe/run_deluxe.py        The Quest Deluxe
python TheQuestDeluxe/run_editor.py        The Quest Deluxe Editor (needs tkinter)
```

## The repository

| Folder | Holds |
|---|---|
| `classic/` | The faithful port: `engine/` (its code), `packs/TheQuest/` (the original as released), `sprites/`, its reverse-engineering tools and exe verifiers (`tools/re/`), notes and tests. |
| `TheQuestDeluxe/` | The Quest Deluxe: `engine/` (its code), `editor/`, `packs/`, `docs/`, tests and `tools/make_pack.py`. |
| `docs/` | Everything learned along the way: [findings about the original](docs/FINDINGS.md), [how the ports are verified](docs/VERIFICATION.md) and [the project's decisions and plans](docs/PROJECT.md). Start at [docs/README.md](docs/README.md). |
| `tests/` | The checks between the two editions: [`lockstep.py`](tests/lockstep.py) plays both side by side on random keys and requires the same screens and game state after every key; `test_view3d.py` and `test_combat_log.py` build on it to show that FPS mode and the combat log change nothing. |
| `tools/` | `build_release.py` (one Windows zip per edition) and `launcher.bat` (the double-click launcher it adapts for each program). |

The reverse-engineering tools also need `capstone` and `unicorn`.
