# The Quest Deluxe

The extended engine for The Quest, **standalone**: it needs nothing from the classic edition. It plays
**quest packs**: folders of plain JSON, text and PNG files that hold a whole quest. `packs/TheQuest` is
the original game, converted, and plays exactly like the faithful port. New quests, items, creatures,
classes and levels are made with the editor.

## Running

```
python run_deluxe.py                       a new game of packs/TheQuest
python run_deluxe.py --pack mypack         another pack (a folder, or a name under packs/)
python run_deluxe.py --quick 1 --level 2   start at once with a Knight on level 2 (testing)
python run_editor.py                       The Quest Deluxe Editor (needs tkinter)
```

It needs Python 3.10+ and pygame-ce. On Windows, double-click **Play The Quest Deluxe.bat** or
**The Quest Deluxe Editor.bat**: the first time they find Python (or offer to install it) and set up
pygame-ce.

## What it adds to the original

| Feature | Keys | What it does |
|---|---|---|
| **FPS mode** | F | The world through the hero's eyes: a retro EGA raycaster drawn from the pack's own pictures. Up/Down walk, Left/Right turn (a free action), Q/E or `,` `.` step sideways (hold any of them to keep going), the panel's Map box shows the screen from above (M: the level map), the weapon in hand swings, thrusts or shoots as you attack, arrows and stones fly to their targets, and the hero's bust by the coins shows his class, his eye colours and his amulet. The rules don't change: walking is the classic move, so bumping fights, talks and opens doors. |
| **Map switch** | M | In FPS mode, switches the panel's Map box between the current screen from above (with an arrow for the way you face) and the level map of the screens you've visited. From above, the box is always the level map. |
| **Combat log** | D | "You hit the imp for 4.", "The orc hits you for 3.", misses, spells, pick-ups, locked doors ("You need the gold key.") and deaths over the bottom of the map; in FPS mode the damage can also rise off whoever took it (`floating_numbers` in settings.ini). |
| **Easier editing** | | The editor and the game open in the middle of the screen. The mouse wheel scrolls every tab, Ctrl+wheel zooms the map, and the Map tab can show a grid round every square. The Events tab's **Add an event...** builds a rule from drop-down menus (when, only if, then) and writes the script and the Dialogue lines for you; its pickers put an item, creature, story or message number into a script, and the Map tab's Stories box picks from the Stories list. |
| **More ways to build** | | Ladders, rope, stairs, holes and jump pads to other levels (the Map tab's Link tool); walls that an item moves (a boulder and a crowbar); creatures on 2 x 2 squares; creatures that rise again from blood; spells that burn blood off the ground, freeze water to ice or call shadow clones around the hero; weapons and arrows that burn, freeze, poison or drain; a potion of foresight; shields and offhand weapons in view in FPS mode. `docs/QUEST_PACKS.md` has the fields. |
| **Quest packs** | | Everything the original hardcodes (items, creatures and their traits, classes, spells, tiles, stories, dialogue, shops, level scripts) is data in the pack. |
| **Bug fixes** | | The original's bugs (the Shield / Ring of Ice swap, the shop memory, questionnaire ties, the item in a tree and more) are fixed: `settings.ini` has them on for every pack, or leaves it to each pack, whose author picks them one by one. `packs/TheQuest` itself keeps them all, so the tests can hold it to the original. |
| **Past the original's limits** | 9, 0 | More than 20 spells (a spell book with pages), potions 9 and 10, more key colours, and new classes in class changes and the questionnaire. |
| **The editor** | | Maps and level settings, items, creatures, classes, spells, tiles, shops, dialogue, stories and events; a 16-colour painter for every picture; a 3D preview; Play (F5) test-plays from the clicked square; new packs. |

The original's keys all work as in [the classic edition](../TheQuestClassic/README.md#keys).

## What is here

| Path | What it is |
|---|---|
| `Play The Quest Deluxe.bat`, `The Quest Deluxe Editor.bat` | The Windows launchers. |
| `settings.ini` | The player's settings: bug fixes and sound. |
| `run_deluxe.py`, `run_editor.py` | Start the game and the editor. |
| `engine/` | The Quest Deluxe's code (a fork of the classic port's engine, reading everything from a pack). |
| `editor/` | The editor (tkinter). |
| `packs/TheQuest/` | The original quest as a pack. |
| `docs/QUEST_PACKS.md` | Every file of a pack, and every field. |
| `docs/EVENTS.md` | The level scripts: the language, the handlers and the functions they can call. |
| `tools/make_pack.py` | Rebuilds `packs/TheQuest` from the original (the only thing here that reads `../TheQuestClassic`). |
| `tests/` | `test_packs.py`, `test_limits.py`, `test_fixes.py`, `test_editor.py` (under `xvfb-run` on Linux), and `test_standalone.py`: a copy of this folder alone must play, opening nothing outside itself. |

Saves go to `saves/<pack>/save01.dat` to `save20.dat`.

## settings.ini

The player's settings, in this folder:

| Setting | Values |
|---|---|
| `fixes` | `on` (shipped): the original's bugs are fixed in every pack, and the title screen says "Bug fixes: on". `off`: every bug kept, exactly as the original plays. `pack`: as each quest pack says (the editor's Quest tab). |
| `sound` | `on` or `off`: the PC-speaker tones. Without it, a `sound.txt` holding `0` turns them off, as in the original. |
| `items_on_top` | `on` (shipped): gold and items are drawn over a creature or the hero standing on them. `off`: under them, as the original draws them. Blood, remains and footprints stay underneath either way. In FPS mode they are always in front. |
| `floating_numbers` | `off` (shipped): in FPS mode the combat log's lines only. `on`: the damage, "miss" and the like also rise off whoever took them. |

| `render_quality` | `normal` (shipped): one switch for how finely FPS mode is drawn. `high`: `fps_quality = high`. `ultra`: `fps_quality = max`, three times the detail averaged down, so distant things pixelate much less (slower). It does not blur the picture. |
| `smooth_scaling` | `off` (shipped): the picture is scaled to the window in whole pixels, crisp. `on`: blended, filling the window: softer. |
| `fps_fog_start` | `45` (shipped): where the fog fade begins in FPS mode, in percent of the view distance. `100`: everything stays crisp to the edge of the view. |
| `fps_quality` | `normal` (shipped): how finely FPS mode is drawn: `low`, `normal`, `high`, `ultra` or `max`. Higher is sharper, and slower. |
| `fps_view_distance` | `level` (shipped): FPS mode sees as far as each level says. A number, 2 to 30, makes the eye see at least that many squares. |
| `show_gear` | `on` (shipped): the hero shows what he wears on the map: a weapon in his hand, a shield, a helmet, armour, an amulet (each item's own *Worn on the hero* picture, or a small copy of its icon). `off`: as the original. |
| `fps_transition` | `on` (shipped): pressing F zooms the map in on the hero, then the eye drops down into the FPS view (and rises and zooms back out when you leave it). `off`: it just switches. |
| `fps_texture_filter` | `off` (shipped): in FPS mode, pixels far away are skipped, as a plain scaler does: crisp, and a distant path of pebbles can break into dashes. `on`: the ground, walls and things far away are averaged down, so they fade smoothly. |
| `fps_dither` | `ordered` (shipped): the fog in FPS mode is a 4 x 4 dither. `fine`: an 8 x 8 one. `smooth`: a plain blend. `off`: no fading with distance. |

`run_deluxe.py --fixes on|off|pack` and `--sound on|off` override them for one game. The tests never
read this file: they play each pack as it is.

## How it stays true to the original

The repository's `tests/lockstep.py` plays The Quest Deluxe and the classic port side by side on random
keys and requires the same screens and game state after every key, and the classic edition's exe
verifiers run against it with `QUEST_ENGINE=deluxe`. See
[docs/VERIFICATION.md](../docs/VERIFICATION.md).
