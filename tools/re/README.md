# Reverse-engineering tools for TheQuest.exe

`TheQuest.exe` (Borland C++ 3.1, 16-bit DOS) still contains its **Turbo Debugger
symbols**: every function name, global, local variable, struct layout and
source-line table. These scripts use them to produce readable output.

All scripts read the exe straight out of `../../TheQuest.zip`. They need
Python 3.10+ and `pip install capstone`.

| Script | What it does |
|---|---|
| `tds.py` | Parses the TDS debug tables (symbols, modules, scopes, types, members, names). |
| `structs.py` | Prints the game's structs (`heroo`, `inve`, `monsters`, `skills`, `statuss`, `square`). |
| `qdis.py` | Annotated disassembly. Writes `out/asm/<SEG>_<func>.asm`. Call names, globals, locals and string literals are resolved. |
| `lift.py` | "Lifts" the unoptimised Borland code into pseudo-C with gotos. Writes `out/pc/<SEG>_<func>.c`. This is the easiest way to read the game logic. |

```bash
cd tools/re
python qdis.py --list          # every game function with its address
python qdis.py --data          # data-segment globals
python lift.py talk newmap     # lift specific functions
python lift.py --all           # lift everything (~600 KB of pseudo-C)
```

## What the lifter understands

- `map[x][y].field` for the LVP `matrix<square>` / `matrix<int>` template calls.
- Struct fields of the globals `hero`, `inv`, `st`, `skill`, and of `enemies[i]`.
- `random(N)`: Borland's `rand()*N/32768` pattern, including the shift form used for powers of two.
- The x87 emulator (`INT 34h`–`3Dh`), rewritten back into real FPU opcodes.
- `cdecl` argument lists, far pointers, and string literals in the data segment.

It is not a real decompiler. Control flow stays as `if (...) goto L1234;`,
and a few register tricks come out as raw `__asm`. When in doubt, check the
matching `.asm` file.

## Code segments

| Segment | Source file | Contents |
|---|---|---|
| `0a45` | RPG.CPP | Main loop (`main2`), `talk`, `newmap`, `goroom`, combat, `deadenemycheck` |
| `1987` | ICONS.CPP | One BGI drawing function per sprite (replaced by the PNGs in `sprites/`) |
| `2972` | FUNCS.CPP | Save/load, story, character creation, level-up, HUD drawing, `enemycheck` |
| `362f` | FUNCS2.CPP | Inventory, shops (`peddler`), `monsdeath2` (exp and loot), spell visuals, `put3` |

## Running the game's own drawing code

| Script | What it does |
|---|---|
| `emu.py` | Loads the exe into the Unicorn x86 emulator and calls any game function. BGI calls are intercepted and drawn with `quest2/bgi.py`. `draw_tile(floor=…, wall=…, mon=…, item=…, deco=…, gold=…)` runs `clean2()` on one map square. |
| `sprite_check.py` | Compares every PNG in `sprites/` with what the game draws. It writes `out/sprites/report.txt`, plus an image (original, PNG, diff) for each sprite that differs. |
| `verify_anims.py` | Runs every animation, jingle and hero drawing in `quest2/anim.py` next to the original (`aflame()`, `ahit()`, `guy2()`, `song_key()` ...) with many arguments and the same `rand()` seed, and checks that both make exactly the same BGI calls, tones and delays. |
| `verify_saves.py` | Runs the exe's own `save()` and `load2()` on random game states next to `quest2/savefile.py`: the saved text must match character for character, and the loaded values must match. Also round-trips `data/SAVE01.DAT`. |
| `verify_arcs.py` | Runs the Borland graphics kernel's own emulated ARC (EGAVGA.BGI leaves arcs to the kernel) for thick full circles and random arcs, and compares its lines pixel for pixel with `BGI.ellipse()` at thickness 3. |
| `verify_invshop.py` | Runs the exe's `inventory()` and `peddler()` next to `quest2/invshop.py` with random bags, shops and key presses: the same drawing, tones, drops, purchases and resulting bag. |
| `bag_icons.py` | Renders the item pictures `bagdraw()` uses in the bag and the shop into `sprites/bag/`. |

```bash
pip install unicorn
python sprite_check.py            # all sprites
python sprite_check.py enemy_2    # just one
```

`bgi.py` matches Borland's lines, midpoint circles, thick (3-pixel) curves, fill patterns and 4-way
flood fill exactly. It approximates ellipses whose two radii differ, and `bar3d`/`fillpoly`. Where
a sprite uses one of those, a small difference is usually the emulator, not the sprite. The DOSBox
screenshots settled Wishing Well, Table and Moose that way.
