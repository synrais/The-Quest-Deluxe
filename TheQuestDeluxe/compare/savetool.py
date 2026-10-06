"""(run as a child process, on the ORIGINAL pack) Make the save the original loads: python -m compare.savetool OUT_DIR LEVEL X Y [--hero FILE] [--class N]

The engine reads its pack when it is imported, so this runs apart from the game being compared. It writes OUT_DIR/save01.dat and prints
one line, 'READY'.
"""
import argparse
import os
import sys

os.environ.pop('QUEST_PACK', None)                      # the original pack
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('level', type=int)
    ap.add_argument('x', type=int)
    ap.add_argument('y', type=int)
    ap.add_argument('--hero')
    ap.add_argument('--class', dest='cls', type=int, default=1)
    a = ap.parse_args()
    import pygame
    pygame.init()
    window = pygame.display.set_mode((640, 480))
    from engine import savefile
    from engine.game import Game
    from compare import state
    g = Game(window, settings={'fixes': 'off', 'sound': 'off'})
    hero = None
    if a.hero:
        with open(a.hero, 'rb') as fh:
            hero = savefile.from_bytes(fh.read())
    state.start(g, a.level, (a.x, a.y), hero=hero, cls=a.cls)
    if (g.player.X, g.player.Y) != (a.x, a.y):
        print(f'BLOCKED {g.player.X} {g.player.Y}')
        return 2
    state.write_dos_save(a.out, state.save_bytes(g))
    print('READY')
    return 0


if __name__ == '__main__':
    sys.exit(main())
