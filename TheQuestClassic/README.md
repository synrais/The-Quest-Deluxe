# The Quest (classic): the faithful port

The Quest (Alex Kutsenok, 2001), remade to play **exactly** like the original DOS game: the same
screens pixel for pixel, the same rules, the same random numbers, the same saves, and the original's
bugs too. It is checked against the original `TheQuest.exe`, running in an emulator.

This edition is **locked**: it stays as the original was. New features go into
[The Quest Deluxe](../TheQuestDeluxe/README.md).

## Running

```
python run_quest2.py                start at the title
python run_quest2.py --level 3      start on level 3 (testing)
```

It needs Python 3.10+ and pygame-ce. On Windows, double-click **Play The Quest.bat**: the first time
it finds Python (or offers to install it) and sets up pygame-ce.

## What is here

| Path | What it is |
|---|---|
| `Play The Quest.bat` | The Windows launcher. |
| `run_quest2.py` | Starts the game. |
| `engine/` | The port's code: the rules, the screens, the original's animations and sounds, BGI graphics, saves. |
| `engine/content/` | The level scripts (`levels/*.qs`) and the tables the original hardcodes. |
| `packs/TheQuest/` | **The original game as released**, unzipped: `TheQuest.exe`, `data/`, `bgi/` (Borland's drivers and fonts), the manual. The port reads its files from here. |
| `sprites/` | Every picture, drawn by the original's own code in the emulator. |
| `docs/REVERSE_ENGINEERING.md` | How the original works, function by function, and its quirks. |
| `tools/re/` | The reverse-engineering tools: a disassembler and lifter using the exe's own debug symbols, an emulator that runs the original's code, and the verifiers (see below). |
| `tests/` | `test_phase3.py`, `test_anims.py`, `test_saves.py`. |

## Keys

| Key | Action | Key | Action |
|---|---|---|---|
| arrows | move, attack, open doors, talk | Enter | pick up |
| 1-8 | drink a potion | Space / Tab | shoot / choose a target |
| s | spell book | F1-F9 | cast a bound spell |
| i | inventory | c | character sheet |
| k | killer switch | v / Home | save |
| l / Insert | load | Esc | quit to the title |

## Saves and sound

Saves go where the original keeps them, `packs/TheQuest/data/save01.dat` to `save20.dat`, in the
original's own format, so saves from the original load here and the other way round. PC-speaker tones
play like the original's; a `sound.txt` in this folder containing `0` turns them off.

## Verification

The verifiers in `tools/re/` run the original's own code next to the port and compare the results
(drawing, animations, conversations, deaths, inventory and shops, saves). With `QUEST_ENGINE=deluxe`
they check The Quest Deluxe instead. What they compare, and the latest results, are in
[docs/VERIFICATION.md](../docs/VERIFICATION.md) at the top of the repository.
