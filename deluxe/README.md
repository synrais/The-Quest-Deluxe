Quest Deluxe - the extended engine, standalone
═══════════════════════════════════════════════
  Run:      python run_deluxe.py            plays packs/quest1 (QUEST_PACK=<name> for another pack)
  Engine:   deluxe/            reads everything from a quest pack; needs nothing of ../classic
  Packs:    packs/<name>/      items, creatures, spells, classes, tiles, text, levels, sprites as
                               JSON / text / PNG; see docs/QUEST_PACKS.md and docs/EVENTS.md
            packs/quest1       The Quest itself, converted from the original by tools/make_pack.py
                               (the only thing here that reads ../classic, and only to rebuild it)
  Editor:   python run_editor.py   (needs tkinter) maps and level settings, items, creatures,
                               classes, spells, tiles (floors, walls, doors, decorations), shops,
                               dialogue, stories, events, quest settings; a 16-colour painter for
                               every picture (Paint... beside it); new packs; Play (F5) test-plays
                               from the clicked square
  FPS mode: F in the game: the world through the hero's eyes (a retro EGA raycaster). Up/Down
                               walk, Left/Right turn (free), Q/E or , . step sideways; M shows or
                               hides the screen from above. The rules don't change: walking is the
                               classic move, so bumping fights, talks and opens doors
  Combat:   D in the game: the combat log (on by default): "You hit the imp for 4.", "The orc hits
                               you for 3.", misses, spells, pick-ups, locked doors and deaths over
                               the bottom of the map; in FPS mode the damage rises off whoever took it
  Saves:    saves/<pack>/save01.dat .. save20.dat
  Tests:    tests/test_packs.py, tests/test_editor.py (under xvfb-run on Linux), and
            tests/test_standalone.py (a copy of this folder alone plays); ../tests checks Deluxe
            against the classic port
