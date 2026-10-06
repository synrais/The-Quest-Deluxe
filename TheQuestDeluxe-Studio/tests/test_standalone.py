"""The Quest Deluxe stands alone: a copy of this folder, and nothing else, plays.

The TheQuestDeluxe-Studio/ folder is copied somewhere empty (no ../TheQuestClassic beside it) and played
there in a fresh Python: the title, the story pages, a level, the bag, the spell book, FPS mode and
the last level. Every file it opens must be inside the copy.

    python tests/test_standalone.py
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # TheQuestDeluxe-Studio/

PLAY = r'''
import builtins, os, sys, zipfile
os.environ['SDL_VIDEODRIVER'] = 'dummy'; os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.getcwd())
opened = set()
real_open, real_zip = builtins.open, zipfile.ZipFile
builtins.open = lambda f, *a, **k: (opened.add(str(f)), real_open(f, *a, **k))[1]
zipfile.ZipFile = lambda f, *a, **k: (opened.add(str(f)), real_zip(f, *a, **k))[1]
import pygame
pygame.init(); pygame.display.set_mode((640, 480))
from engine.game import Game
g = Game(pygame.Surface((640, 480)))
for k in [pygame.K_RETURN] * 3:
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode='\r'))
g.quick_start(1, 1)
for k in [pygame.K_UP, pygame.K_LEFT, pygame.K_UP, pygame.K_i, pygame.K_ESCAPE, pygame.K_s, pygame.K_ESCAPE,
          pygame.K_f, pygame.K_UP]:
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=''))
    g.renderer.draw(g, present=False)
g.goto_level(g.levels)
g.renderer.draw(g, present=False)
here = os.path.realpath(os.getcwd())
outside = sorted(f for f in opened if not os.path.realpath(os.path.abspath(f)).startswith(here))
print('OUTSIDE', outside)
'''


def main():
    tmp = tempfile.mkdtemp()
    copy = os.path.join(tmp, 'TheQuestDeluxe')
    shutil.copytree(HERE, copy, ignore=shutil.ignore_patterns('__pycache__', 'saves', 'tests'))
    out = subprocess.run([sys.executable, '-c', PLAY], cwd=copy, capture_output=True, text=True, timeout=600)
    line = next((ln for ln in out.stdout.splitlines() if ln.startswith('OUTSIDE')), None)
    shutil.rmtree(tmp, ignore_errors=True)
    if line is None:
        print(out.stdout[-2000:], out.stderr[-4000:])
        sys.exit('The Quest Deluxe did not run from a copy of its own folder')
    outside = eval(line[len('OUTSIDE '):])
    # no old editor anywhere: no folder of it, and nothing imports it
    assert not os.path.exists(os.path.join(HERE, 'editor')), 'the old editor folder is gone'
    for folder, _, names in os.walk(HERE):
        if '__pycache__' in folder or 'Custom Maps' in folder or os.sep + 'dos' in folder:
            continue
        for n in names:
            if n.endswith('.py'):
                text = open(os.path.join(folder, n), encoding='utf-8').read()
                assert not re.search(r'^\s*(from|import) editor\b', text, re.M), f'{n} still imports the old editor'
    assert not outside, f'The Quest Deluxe reached outside its folder: {outside}'
    print('a copy of TheQuestDeluxe-Studio/ alone played the title, stories, a level, the bag, the spell book, FPS mode '
          'and the last level, opening nothing outside itself: ok')


if __name__ == '__main__':
    main()
