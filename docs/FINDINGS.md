# Findings: what we learned about The Quest

Everything here was found by reading `TheQuest.exe` with the tools in `TheQuestClassic/tools/re/`, by running
its own code in an emulator, and by comparing the port with screenshots of the original in DOSBox.
The function-by-function notes (rules, formulas, screens, saves) are in
[TheQuestClassic/docs/REVERSE_ENGINEERING.md](../TheQuestClassic/docs/REVERSE_ENGINEERING.md); this page collects the
discoveries, the original's bugs, and the corrections they led to.

## The program

- **Borland C++ 3.1**, 16-bit real-mode DOS, BGI graphics at 640×480 in the 16 EGA colours.
- **Its debug symbols are still inside** (Turbo Debugger TDS v4.01): every function, global, local
  variable, struct and source line has its original name. That is what made an exact port possible:
  `tools/re/qdis.py` disassembles with those names and `tools/re/lift.py` turns the code into readable
  pseudo-C.
- Four source files: `RPG.CPP` (the main loop, conversations, combat), `ICONS.CPP` (one drawing
  function per picture), `FUNCS.CPP` (saves, stories, character creation, the HUD) and `FUNCS2.CPP`
  (inventory, shops, kills, spell animations). It uses the Lawrenceville Press `vector`/`matrix`
  classes, a high-school C++ library.
- **Every picture is drawn in code**, by its own function (`deer()`, `chest()`, `lockeddoor()` ...).
  The port's pictures were made by running those functions in the emulator (`tools/re/emu.py`,
  `tools/re/bag_icons.py`), so they are the original's pixels.
- **The whole story is code, not data**: conversations, quests and scripted scenes are long chains of
  checks in `talk()`, `deadenemycheck()`, `main2()` and `newmap()`. The ports turn them into level
  scripts ([EVENTS.md](../TheQuestDeluxe/docs/EVENTS.md)).
- The data files use a light cipher: every byte except space, CR and LF is stored as `char + 0x51`.

## The original's bugs

The classic edition keeps all of these on purpose, and so does The Quest Deluxe's `packs/TheQuest` (it
must play exactly like the original, so the tests can hold it to that). The Quest Deluxe fixes them as
it is shipped: its `settings.ini` says `fixes = on`, which fixes those with a name in the last column
in every pack. `off` keeps them; `pack` leaves it to each pack's quest.json `fixes` (the editor's
Quest tab), picked one by one. The rest are in a pack's own scripts or data, where the editor can
change them, or are kept. `TheQuestDeluxe/tests/test_fixes.py` checks
each fix with and without it.

| Bug | What happens | Fixed in a Deluxe pack by |
|---|---|---|
| **Shield and Ring of Ice swapped** | The Shield spell (4) absorbs blows up to the power of spell 5, and the Ring of Ice (5) freezes if the power of spell 4 beats the target's magic armour. Both spells have power 10, so in Quest I it never shows. | `shield_ice` |
| **An item in a tree** | Level 6, square (24,82): a decayed tree holding item −5, which isn't an item. | `map` (`map_fixes`: removed) |
| **A shield that doesn't exist** | Level 7, square (45,65): item 311, which has no stats, no picture and no price (the shields are 301-306). The author did not remember it ("little errors I made"); "if anything seems weird or out of place... probably is a bug". | `map` (`map_fixes`: removed) |
| **`Talk.dat` reading** | To skip a line it counts two `"` or `;` characters, but two-line entries have three, so the reader can fall out of step. One-line messages are drawn 3 pixels off the left edge, quote marks and all. A line that is never found hangs the game. | `talk` |
| **Shops remember the last shop** | `peddler()` never clears its file-name buffer: on a screen without a shop of its own, a shopkeeper sells the last shop's stock, even from an earlier level. | `shop_memory` |
| **Dead creatures skip a neighbour** | `deadenemycheck()` removes the dead in place, so the creature that slides into the gap isn't checked until next time; some scripted scenes only fire while a creature is on the screen. | `dead_scan` |
| **Fatebringer's scan** | When the Woman becomes Fatebringer (level 6), the scan restarts at index 1, and later kills in that pass are credited to creature 0, not the hero. | `dead_scan` (the restart) |
| **The current screen's map is stale** | The screen is copied out on arrival and written back on leaving, so quest checks that read the map see the screen as it was on arrival. | kept |
| **Conversations move the hero through walls** | The level 1 farmer and the level 6 father move the hero without checking walls. | the level scripts |
| **Quiz ties favour the Monk** | A tie involving the Monk, or any three- or four-way tie, gives a Monk. | `quiz_ties` |
| **Blank rows in character creation** | Marksmanship is meant to be the Rogues' own: its name is only drawn for Rogues, who get it free. For the other classes its row is left blank, but the cursor still stops there, and Enter does nothing. The fault list does the same with the fault a class can't have (Cowardice for Knights, Rashness for Mages, Honor for Rogues). | `blank_rows` (the rows are left out) and `marksmanship` (the author: "all classes should have access to Marksmanship", so every class is offered and can choose it) |
| **Fault colours** | With Cowardice active, the lines below it on the character sheet stay yellow instead of red. | `fault_colours` |
| **Invisible wraiths are never drawn** | `clean2()` has no case for them, even when they should show. The author (Alex, 1 Oct): "the invisible monsters should always be invisible". | kept: it is as meant |
| **Items never raise max life or mana** | `inventory()` gets the hero by value, so what it adds is thrown away. The author: "I don't remember if items were meant to raise max-life and mana. Probably not". | kept: it is as meant |
| **A save number is never written** | `save()` hands `fprintf` five numbers for four `%d`s, so `st.saveslot` is lost; every save also ends with a doubled newline. | kept (the save format) |
| **Load Game stops at a gap** | The list stops at the first missing or reserved slot; games after it can't be picked. | `load_gaps` |
| **Only levels 1-9** | `newmap()` writes `'0' + level` into a file name, and level 8 is hardcoded as the ending. | none needed: a pack has as many levels as its `levels` says |
| **Negative angles in arcs** | The graphics library compares arc angles unsigned, so a negative start angle counts as a large one. | kept (the graphics) |

## What the original doesn't have

- **No combat text at all.** Hits, misses, parries, spells and deaths show only as short animations
  over the map with PC-speaker tones. (The Quest Deluxe's combat log is new.)
- **No pacing on two screen wipes.** The black circle that opens and closes every story page (410
  `fillellipse()` calls) and the black box after "Want to load? No" (350 `bar()` calls) have no
  `delay()`: they ran as fast as the PC could draw. The ports give them a pace of their own, about
  0.75 s and 0.7 s (`Pace` in `engine/anim.py`), which the animation verifier leaves out of its
  record of the original's delays.
- **The hero is drawn in code** (`guy2()`), not from a picture. The eye colour shows the hero's state:
  green when poisoned (and visible), dark red with the killer switch, light red under a Berserker
  potion, white otherwise, in that order of priority. Shield draws a yellow ring, Shield of Fire a red
  one, and an invisible hero is only a pair of eyes. Nothing else about the hero changes.

## The graphics (Borland's BGI)

- **The driver does very little.** `EGAVGA.BGI` only draws pixels, 1-pixel lines and bars. The rest is
  the graphics kernel linked into the exe: it clips every line to the screen, draws thick lines as
  three thin ones, and draws arcs, ellipses, filled ellipses, polygons, pie slices, `bar3d` and the
  stroked text itself. The port reproduces that kernel exactly (`engine/bgi.py`).
- **Clipping changes pixels.** The kernel clips a line before drawing it (Cohen-Sutherland, rounding
  toward zero), so the visible part of a line running off the screen isn't the same pixels as the
  whole line would have been.
- **Thick circles** (the key outlines) are one point per degree from the kernel's own sine table,
  joined by thick lines: a pixel narrower than a brushed circle, slightly lopsided, with a stray
  pixel at the top.
- **The fill patterns are the driver's.** LINE_FILL (pattern 2) is two rows on, two off. The port had
  it as two on, six off, which showed as thin stripes on the title screen's menu boxes; a DOSBox
  screenshot caught it, and the port now reads the same table as `EGAVGA.BGI`.
- **Stroked text** (the `.CHR` fonts) is drawn by the kernel as pen strokes, each clipped before it is
  drawn, and always 1 pixel thick whatever the line style. The Gothic font's small letters have gaps
  between their strokes by design, which is why the title screen's yellow text is hard to read in the
  original too.
- The fonts the game uses: Gothic (4) for titles, Complex (8) for the stat sheet, Simplex (6) for
  stories and talk, Triplex (1) for the spell book, Triplex Script (7) for the message strip, Sans (3)
  for gold.

## Corrections the screenshots forced

Screenshots of the original in DOSBox, compared with the port pixel by pixel:

| Screen | What differed | Now |
|---|---|---|
| **The potion belt** | The belt wiped the last row of the hatched border (it drew one row too high). | Drawn from row 411, as the original. |
| **The key panel** | The thick key outlines. | Drawn as the kernel draws thick arcs. |
| **The title screen** | 5,844 pixels: the striped tops and sides of the menu boxes (LINE_FILL). | Identical: 0 pixels differ. |

More screenshots (the inventory, a shop, the character sheet, the spell book) can be compared the same
way.
