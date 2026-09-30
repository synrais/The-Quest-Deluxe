# Verification: how the ports are proven exact

"Exact" is checked, not assumed. There are three kinds of check:

1. **Against the original exe.** The verifiers in `TheQuestClassic/tools/re/` load `TheQuest.exe` into the
   Unicorn x86 emulator and run the original's own functions next to the port, with the same
   arguments and the same `rand()` seed, then compare what both did.
2. **Against the original on screen.** Screenshots of the original in DOSBox, compared with the port
   pixel by pixel.
3. **The two editions against each other.** The Quest Deluxe must play Quest I exactly like the
   classic port, and its additions must change nothing they aren't meant to.

## Against the original exe

Run from `TheQuestClassic/tools/re/`. Each checks the classic port; with `QUEST_ENGINE=deluxe` it checks
The Quest Deluxe (playing `packs/TheQuest`) instead.

| Verifier | What it compares | Latest result (classic / Deluxe) |
|---|---|---|
| `verify_bgi.py` | The graphics kernel inside the exe (line clipping, thick lines, arcs, ellipses, filled ellipses, pie slices, polygons, `bar3d`, and stroked text in every `.CHR` font, size and line thickness) against `engine/bgi.py`, pixel for pixel over random cases; and the fill-pattern table against `EGAVGA.BGI`'s. | 1000/1000 shapes and texts identical; fill patterns 11/11 |
| `verify_anims.py` | Every animation, jingle and hero drawing (`aflame()`, `ahit()`, `guy2()`, `song_key()` ...) with many arguments: the same BGI calls, tones and delays, in the same order, with the same `rand()` draws. | 385/385 / 385/385 |
| `verify_events.py` | Conversations: every talking person on every level, in many random game states (quest counters, reputation, gold, bag, visited screens, seed), through the original's `talk()` and the port's level scripts: the message, quest counters, reputation, gold, the hero's square, the bag, every map square and the creature list. | 1704/1704 conversations / 1704/1704 |
| `verify_deaths.py` | Deaths: random screens from every level with random creatures dead, a random killer and random quest counters and positions, through the original's `deadenemycheck()`: messages, experience, gold and items dropped, bodies, reputation, poison, quest counters, the hero's square, every map square and the creature list. | 280/280 / 280/280 |
| `verify_invshop.py` | The inventory and the shops (`inventory()`, `peddler()`) with random bags, shops and key presses: the drawing, tones, drops, purchases and the resulting bag. | inventory 60/60, shops 60/60 / the same |
| `verify_saves.py` | The original's `save()` and `load2()` on random game states: the saved text character for character, the loaded values, and a real save from the original (`SAVE01.DAT`) round-tripped. | saves 40/40, loads 40/40, SAVE01.DAT identical / the same |
| `sprite_check.py` | Every picture in `TheQuestClassic/sprites/` against what the original's drawing function draws. | All identical, except the invisible wraith, which the original never draws. |

```
cd TheQuestClassic/tools/re
python verify_bgi.py                        # the classic port
QUEST_ENGINE=deluxe python verify_events.py # The Quest Deluxe
```

They need `capstone` and `unicorn` (`pip install capstone unicorn`).

## Against the original on screen

DOSBox screenshots of the original, compared with the port pixel by pixel. See
[FINDINGS.md](FINDINGS.md#corrections-the-screenshots-forced) for what each one caught.

| Screen | Result |
|---|---|
| The potion belt | Identical (after drawing the belt from row 411). |
| The key panel | Identical (after drawing thick arcs as the kernel does). |
| The title screen | Identical: 0 of 307,200 pixels differ (after correcting LINE_FILL). |

## The two editions against each other

Run from the top of the repository.

| Test | What it checks |
|---|---|
| `tests/lockstep.py` | The classic port and The Quest Deluxe, side by side with the same seed, on random keys from random starts (every class, level and screen, rich and poor heroes): after every key the whole game state (hero, inventory, skills, status, bag, spells, the whole map, creatures, messages) and the screen must be identical. |
| `tests/test_view3d.py` | The same random games from above and in FPS mode (turning to face the way, then walking) reach the same state after every key; the 3D view draws everywhere and fast enough; the Quest I pack's 3D looks; animations carried into the view; and steps and turns every way in real time with a watchdog (it caught the facing-west hang). |
| `tests/test_combat_log.py` | The same random games with the combat log off and on reach the same state after every key; a fight is reported in order. |

## Each edition's own tests

| Test | What it checks |
|---|---|
| `TheQuestClassic/tests/test_phase3.py` | Play: a creature chasing and fighting, a Mage casting from the F-keys, a Rogue shooting, buying in a shop, a level-up, saving and loading. |
| `TheQuestClassic/tests/test_anims.py` | Every place the game plays one of the original's animations or sounds. |
| `TheQuestClassic/tests/test_saves.py` | The save system in play: a new game taking a slot, the silent save after creation, "Want to save?", "Want to load?", the Available Games list, "Want to quit?", loading after death. |
| `TheQuestDeluxe/tests/test_packs.py` | `packs/TheQuest` goes through the editor's model and back byte for byte; a blank pack; a new weapon picked up, worn and bought; a new class killing a new monster. |
| `TheQuestDeluxe/tests/test_editor.py` | The editor's window driven by simulated clicks: painting, undo, every tab, the painter, the 3D preview, saving. |
| `TheQuestDeluxe/tests/test_standalone.py` | A copy of `TheQuestDeluxe/` alone, somewhere empty, plays the title, the stories, a level, the bag, the spell book, FPS mode and the last level, opening nothing outside itself. |

Also, `TheQuestDeluxe/tools/make_pack.py` rebuilds `packs/TheQuest` from the original byte for byte.
