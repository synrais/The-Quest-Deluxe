The Quest (classic) - the faithful port
═══════════════════════════════════════
  Run:      python run_quest2.py            (needs Python 3.10+ and pygame-ce)
  Engine:   engine/            the port's code; it reads the original's own files
  Original: packs/TheQuest/    The Quest as released, unzipped: TheQuest.exe, data/, bgi/, the manual
  Sprites:  sprites/           the pictures, drawn by the original's own code (tools/re)
  Levels:   engine/content/levels/*.qs      quest and event scripts
  Notes:    docs/REVERSE_ENGINEERING.md     how the original works, and its quirks
  Tools:    tools/re/                       disassembler, lifter, and an emulator that runs the
                                            original code to check the port against it
                                            (verify_bgi, verify_anims, verify_events, verify_deaths,
                                            verify_invshop, verify_saves; QUEST_ENGINE=deluxe runs
                                            them against The Quest Deluxe)
  Saves:    packs/TheQuest/data/save01.dat .. save20.dat, where the original keeps them, in its own
            format (the original's saves load here too)
  Sound:    PC-speaker tones like the original; put 0 in sound.txt (this folder) to turn them off
  Tests:    tests/test_phase3.py, tests/test_anims.py, tests/test_saves.py

This edition is locked: it stays exactly as the original, bugs included (docs/REVERSE_ENGINEERING.md
lists them). New features go into The Quest Deluxe (../deluxe).
