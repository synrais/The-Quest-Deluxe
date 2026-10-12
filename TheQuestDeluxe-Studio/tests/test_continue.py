"""Carrying on past the original's last level: the Death Bringer ends level 7 by sending the hero on to the next level. With no level 8
the game ends there (ending pages, credits) and the Doctor says so; once a level 8 is added, the hero goes on to it.

Run:  xvfb-run -a python tests/test_continue.py
"""
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ['QUEST_NO_UPDATE_CHECK'] = '1'

tmp = tempfile.mkdtemp()
pack = os.path.join(tmp, 'Seven')
shutil.copytree(os.path.join(ROOT, 'packs', 'TheQuest'), pack)
import tkinter as tk                                                        # noqa: E402
from studio import doctor                                                   # noqa: E402
from studio.model import Session                                            # noqa: E402

root = tk.Tk()
root.withdraw()
s = Session(root, pack)
notes = lambda: [p.key for p in doctor.check(s) if p.key.startswith('lastends')]        # noqa: E731
assert notes() == ['lastends:7'], notes()
n = s.project.add_level()
s.project.save()
assert n == 8 and notes() == [], 'adding a level 8 takes the note away'
root.destroy()

os.environ['QUEST_PACK'] = pack
import pygame                                                               # noqa: E402
pygame.init()
window = pygame.display.set_mode((640, 480))
from compare import state                                                   # noqa: E402
from engine.game import Game                                                # noqa: E402

g = Game(window, settings={'fixes': 'off', 'sound': 'off'})
assert g.levels == 8
state.start(g, 7, (79, 6), cls=1, story=(0, 7))                             # the Death Bringer is gone for good (mission 2 is 7)
g.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT, unicode='', mod=0))
for _ in range(10):                                                         # (the page shown before level 8 closes on a key)
    if g.overlay:
        g.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, unicode=' ', mod=0))
assert g.world.level == 8, g.world.level
print('quest: past the Death Bringer the hero goes on to a level 8 when there is one, and the Doctor says when there is not: ok')
