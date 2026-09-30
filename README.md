The Quest I-II
══════════════
Two editions of The Quest (Alex Kutsenok, 2001), each in its own folder:

  classic/         The Quest, the faithful port (locked). It plays the original exactly, checked
                   against the original TheQuest.exe. classic/packs/TheQuest is the original game as
                   released, unzipped; classic/engine is the port's code. See classic/README.md.

  TheQuestDeluxe/  The Quest Deluxe, standalone. The extended engine, the editor and quest packs; it
                   needs nothing from classic/. packs/TheQuest is the original quest, converted, and
                   plays the same as the classic port. See TheQuestDeluxe/README.md.

  tests/           The checks between the two: tests/lockstep.py plays both side by side on random
                   keys and requires the same screens and game state after every key;
                   tests/test_view3d.py and tests/test_combat_log.py use it to check that FPS mode
                   and the combat log change nothing.
  tools/           build_release.py: one Windows zip per edition (dist/TheQuest-Classic-<name>.zip,
                   dist/TheQuestDeluxe-<name>.zip), each with double-click launchers
                   (tools/launcher.bat).

Needs Python 3.10+ and pygame-ce (requirements.txt); the editor also needs tkinter, and the
reverse-engineering tools capstone and unicorn.
