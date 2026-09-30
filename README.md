The Quest II — a faithful remake of The Quest for Windows and Linux
════════════════════════════════════════════════════════════════════
  Run:      python run_quest2.py            (needs Python 3.10+ and pygame-ce)
  Windows:  python tools/build_release.py phase4  ->  dist/TheQuestII-phase4.zip; unzip it and
            double-click "Play The Quest II.bat" (finds or installs Python, then pygame-ce)
  Engine:   quest2/            reads the original data files from data/ or TheQuest.zip
  Levels:   quest2/content/levels/*.qs      quest and event scripts, see docs/EVENTS.md
            New level: add data/L00008.dat (+ level8.qs); it plays after level 7.
  Notes:    docs/REVERSE_ENGINEERING.md     how the original works, and its quirks
  Tools:    tools/re/                       disassembler, lifter, and an emulator that runs the
                                            original code to check the remake against it
  Saves:    data/save01.dat .. save20.dat, the original's own format (its saves load here too)
  Sound:    PC-speaker tones like the original; put 0 in sound.txt (game folder) to turn them off
  Tests:    tests/test_phase3.py, tests/test_anims.py, tests/test_saves.py

Quest Deluxe — the extended engine (the classic port above stays frozen as the faithful version)
  Run:      python run_deluxe.py            plays packs/quest1 (QUEST_PACK=<name> for another pack)
  Engine:   deluxe/            a fork of quest2/ that reads everything from a quest pack
  Packs:    packs/<name>/      items, creatures, spells, classes, tiles, text, levels, sprites as
                               JSON / text / PNG; see docs/QUEST_PACKS.md
            packs/quest1       The Quest itself, built by tools/make_pack.py from the original
  Editor:   python run_editor.py   (needs tkinter) maps and level settings, items, creatures,
                               classes, spells, tiles (floors, walls, doors, decorations), shops,
                               dialogue, stories, events, quest settings; a 16-colour painter for
                               every picture (Paint... beside it); new packs; Play (F5) test-plays
                               from the clicked square
  FPS mode: F in the game: the world through the hero's eyes (a retro EGA raycaster). Up/Down
                               walk, Left/Right turn (free), Q/E or , . step sideways; M shows or
                               hides the screen from above. The rules don't change: walking is the
                               classic move, so bumping fights, talks and opens doors
  Saves:    saves/<pack>/save01.dat .. save20.dat
  Tests:    tests/test_packs.py, tests/test_editor.py (under xvfb-run on Linux), tests/test_view3d.py
            (FPS mode plays the same games as the view from above), and
            tests/lockstep.py  classic and Deluxe side by side on random keys: every screen and
                               the whole game state must match; QUEST_ENGINE=deluxe runs the
                               tools/re verifiers against Deluxe

The Quest — Level Editor
Reads/writes L00001.dat – L00007.dat map files and SAVE*.dat save files.

════════════════════════════════════════════════════════════════════
MAP FILE FORMAT  (L00001.dat – L00007.dat)
════════════════════════════════════════════════════════════════════
  100×100 tiles, 10 000 lines of 8 encoded fields each:
    x  y  floor  wall  object  enemy  gold  extra
  Numbers: each decimal digit stored as (digit + 0x81).
           Negative prefix: 0x7E byte before the digits.
  Fields delimited by 0x20 (space), lines by CRLF.

════════════════════════════════════════════════════════════════════
SAVE FILE FORMAT  (SAVE*.dat)  — confirmed by binary analysis
════════════════════════════════════════════════════════════════════
  Line 0        : 10 fields — field[0]=Player Level, field[1]=Class ID,
                  remaining fields are screen/position data (preserved verbatim).
                  Class IDs: 1=Knight  2=Mage  3=Rogue  4=Monk

  Lines 1–9999  : Map tile data, column-major order (same codec as map files).
                  Tile (1,1) is absent from this section.

  Lines 10000–10099 : Screen cache — 100 lines of 8 fields each:
                  [lx, ly, floor, wall, object, enemy, gold, extra]
                  lx/ly are 1-based coords within the current 10×10 screen block.

  Line 10100    : Player position — [abs_x, abs_y, rel_x, rel_y]

  Line 10101    : Player combat stats — 10 fields:
                  [0] Max Life   [1] Cur Life   [2] Max Mana   [3] Cur Mana
                  [4] Strength   [5] Intelligence [6] Dexterity [7] Accuracy
                  [8] Reputation [9] EXP Needed

  Line 10102    : Gold + potion counts — 12 fields:
                  [0–2] unknown (preserved verbatim)   [3] Gold
                  [4] Half Life Potion   [5] Full Life Potion
                  [6] Half Mana Potion   [7] Full Mana Potion
                  [8] Half Restoration   [9] Full Restoration
                  [10] Cure Poison       [11] Berserker Potion

  Lines 10103+  : World flags / inventory — preserved verbatim.

  Line 11358–11367 : Spell book LEFT column  — 10 spell slot IDs (0 = empty).
  Lines 11368–11387: Unknown gap             — never written, preserved verbatim.
  Lines 11388–11397: Spell book RIGHT column — 10 spell slot IDs (0 = empty).
  Lines 11398–11417: Spell learned flags     — 20 lines, one per spell ID (0/1).

  Line 11645    : Skill/Fault flags — 8 fields (each 0 or 1):
                  [0] Ambidexterity  [1] Bargaining  [2] Scholar
                  [3] Memorisation   [4] Markmanship
                  [5] Cowardice      [6] Honor        [7] Rashness

  Line 11649    : Skill/fault secondary encoding — preserved verbatim.
                  (Written by the game itself; exact format not fully decoded.)

SPELL IDs (lines 11358–11397 and 11398–11417):
   1=Heal            2=Flame           3=Teleport        4=Shield
   5=Ring of Ice     6=Black Ward      7=Invisibility    8=Summon Skeleton
   9=Inferno        10=Restore        11=Life Drain      12=Thunder Bolt
  13=Shield of Fire 14=Deteriorate   15=Summon Stone Knight
  16=Earthquake     17=Cure          18=Summon Scorpion
  19=Meteor         20=Dark Hour
